import json
import os
import random
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from config import config
from logger import logger, api_logger
from utils import RateLimiter, retry_with_backoff

OUTPUT_FILE = "earn_apr_gt_250.json"

# Rate Limiter для защиты от блокировки
rate_limiter = RateLimiter(min_interval=config.MIN_REQUEST_INTERVAL)


class CacheEntry:
    """Запись в кэше с временем создания"""
    def __init__(self, data: List[Dict], timestamp: float):
        self.data = data
        self.timestamp = timestamp
    
    def is_expired(self, ttl: int = 300) -> bool:
        """TTL в секундах (по умолчанию 5 минут)"""
        return time.time() - self.timestamp > ttl


class ProjectCache:
    """
    Кэш для результатов парсинга.
    Экономит время и снижает нагрузку на API.
    """
    def __init__(self):
        self._cache: Dict[float, CacheEntry] = {}  # threshold -> CacheEntry
    
    def get(self, threshold: float, ttl: int = 300) -> Optional[List[Dict]]:
        """Получить данные из кэша если не устарели"""
        entry = self._cache.get(threshold)
        if entry and not entry.is_expired(ttl):
            return entry.data
        return None
    
    def set(self, threshold: float, data: List[Dict]):
        """Сохранить данные в кэш"""
        self._cache[threshold] = CacheEntry(data, time.time())
    
    def clear(self):
        """Очистить весь кэш"""
        self._cache.clear()


# Глобальный кэш проектов
project_cache = ProjectCache()


def _parse_apr_percent(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("%", "").replace("\xa0", " ")
        cleaned = cleaned.replace(" ", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _sort_apr_percent(item: Dict[str, Any]) -> Optional[float]:
    parsed = _parse_apr_percent(item.get("sort_apr"))
    return parsed


def _fetch_page(page_number: int) -> Dict[str, Any]:
    """Запрос страницы с retry и rate limiting"""
    def do_request():
        # Rate limiting - ждем если нужно
        rate_limiter.wait_if_needed()
        
        # Задержка для human-like поведения
        time.sleep(random.uniform(config.MIN_DELAY, config.MAX_DELAY))
        
        params = {
            "available": "false",
            "limit": str(config.LIMIT_PER_PAGE),
            "have_balance": "2",
            "have_award": "0",
            "is_subscribed": "0",
            "sort_business": "1",
            "search_type": "0",
            "page": str(page_number),
        }
        url = f"{config.BASE_URL}?{urllib.parse.urlencode(params)}"
        
        # Gate.com блокирует запросы с кастомными заголовками - используем дефолтные
        with urllib.request.urlopen(url, timeout=config.REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    
    # Retry с exponential backoff
    return retry_with_backoff(do_request, max_attempts=config.MAX_RETRIES)


def _fetch_page_with_search(search_coin: str) -> Dict[str, Any]:
    """Запрос страницы поиска монеты с retry и rate limiting"""
    def do_request():
        # Rate limiting - ждем если нужно
        rate_limiter.wait_if_needed()
        
        # Задержка для human-like поведения
        time.sleep(random.uniform(config.MIN_DELAY, config.MAX_DELAY))
        
        params = {
            "search_coin": search_coin,
            "available": "false",
            "limit": str(config.LIMIT_PER_PAGE),
            "have_balance": "2",
            "have_award": "0",
            "is_subscribed": "0",
            "sort_business": "1",
            "search_type": "0",
            "page": "1",
        }
        url = f"{config.BASE_URL}?{urllib.parse.urlencode(params)}"
        
        # Gate.com блокирует запросы с кастомными заголовками - используем дефолтные
        with urllib.request.urlopen(url, timeout=config.REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    
    # Retry с exponential backoff
    return retry_with_backoff(do_request, max_attempts=3)


def _extract_projects(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("data", "list", "result", "rows"):
        if isinstance(payload.get(key), list):
            return payload[key]
    if isinstance(payload.get("data"), dict):
        for key in ("list", "rows", "data"):
            if isinstance(payload["data"].get(key), list):
                return payload["data"][key]
    return []


def extract_sale_statuses(item: Dict[str, Any]) -> Dict[str, List[int]]:
    statuses: Dict[str, List[int]] = {"fixed_list": [], "fixable_list": []}
    
    # Извлекаем fixed_list (фиксированные продукты с блокировкой)
    fixed_lst = item.get("fixed_list")
    if isinstance(fixed_lst, list):
        for entry in fixed_lst:
            if isinstance(entry, dict) and "sale_status" in entry:
                statuses["fixed_list"].append(entry["sale_status"])
    
    # Извлекаем fixable_list (гибкие продукты без блокировки)
    fixable_lst = item.get("fixable_list")
    if isinstance(fixable_lst, list):
        for entry in fixable_lst:
            if isinstance(entry, dict) and "sale_status" in entry:
                statuses["fixable_list"].append(entry["sale_status"])
    
    return statuses


def fetch_token_info(search_coin: str) -> Optional[Dict[str, Any]]:
    payload = _fetch_page_with_search(search_coin)
    items = _extract_projects(payload)
    if not items:
        return None
    search_lower = search_coin.strip().lower()
    for item in items:
        asset = str(item.get("asset", "")).lower()
        if asset == search_lower:
            return item
    return items[0] if items else None


def _process_page(page_number: int, threshold: float) -> List[Dict[str, Any]]:
    payload = _fetch_page(page_number)
    items = _extract_projects(payload)
    matched: List[Dict[str, Any]] = []
    for item in items:
        apr_value = _sort_apr_percent(item)
        if apr_value is not None and apr_value > threshold:
            matched.append(item)
    return matched


def fetch_projects_with_apr_gt(threshold: float, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Запрос проектов с APR выше threshold с кэшированием.
    
    Args:
        threshold: Минимальный APR (в долях, не процентах)
        force_refresh: Принудительное обновление, игнорируя кэш
    
    Returns:
        Список проектов
    """
    # Проверяем кэш если не force_refresh
    if not force_refresh:
        cached = project_cache.get(threshold, ttl=300)  # 5 минут
        if cached:
            cache_age = int(time.time() - project_cache._cache[threshold].timestamp)
            logger.info(f"✅ Данные из кэша: {len(cached)} проектов (обновлено {cache_age} сек назад)")
            return cached
    
    results: List[Dict[str, Any]] = []
    # Используем все доступные страницы
    pages_to_fetch = config.TOTAL_PAGES
    page_numbers = list(range(1, pages_to_fetch + 1))
    logger.info(f"🔍 Запрос {pages_to_fetch} страниц ({config.MAX_WORKERS} потоков)...")

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process_page, page_number, threshold): page_number
            for page_number in page_numbers
        }
        completed = 0
        for future in as_completed(futures):
            page_number = futures[future]
            try:
                matched = future.result()
                results.extend(matched)
                completed += 1
                logger.info(f"✅ Страница {page_number}/{pages_to_fetch} ({completed}/{len(page_numbers)}) — {len(matched)} совпадений")
            except Exception as exc:
                logger.error(f"❌ Страница {page_number}/{pages_to_fetch} — ошибка: {exc}")

    # Сохраняем в кэш
    project_cache.set(threshold, results)
    logger.info(f"✅ Найдено: {len(results)} проектов (сохранено в кэш)")
    return results


if __name__ == "__main__":
    items = fetch_projects_with_apr_gt(2.0)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
    logger.info(f"Сохранено: {len(items)} записей в {OUTPUT_FILE}")
