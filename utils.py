"""
Утилиты для безопасной работы с API:
- RateLimiter: ограничение частоты запросов
- retry_with_backoff: повторные попытки при ошибках
"""
import time
import urllib.error
from threading import Lock
from typing import Callable, TypeVar

T = TypeVar('T')


class RateLimiter:
    """
    Ограничитель частоты запросов для защиты от блокировки API.
    
    Гарантирует минимальный интервал между запросами в многопоточной среде.
    """
    
    def __init__(self, min_interval: float = 2.0):
        """
        Args:
            min_interval: Минимальное время между запросами в секундах
        """
        self.min_interval = min_interval
        self.last_request = 0.0
        self.lock = Lock()
    
    def wait_if_needed(self):
        """
        Ждет если с последнего запроса прошло меньше min_interval.
        Потокобезопасно.
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_request = time.time()


def retry_with_backoff(
    func: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0
) -> T:
    """
    Выполняет функцию с повторными попытками и экспоненциальным backoff.
    
    Стратегия повторов:
    - Попытка 1: сразу
    - Попытка 2: задержка 2 сек
    - Попытка 3: задержка 4 сек
    - Попытка 4: задержка 8 сек (но не более max_delay)
    
    Обработка ошибок:
    - 429 (Too Many Requests): пауза 60 секунд
    - 5xx (Server Error): retry с backoff
    - 4xx (кроме 429): не retry, пробрасываем ошибку
    - Сетевые ошибки: retry с backoff
    
    Args:
        func: Функция для выполнения (без аргументов)
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        
    Returns:
        Результат выполнения функции
        
    Raises:
        Последнее исключение, если все попытки исчерпаны
    """
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
            
        except urllib.error.HTTPError as e:
            last_exception = e
            
            from logger import logger
            
            # 429 Too Many Requests - долгая пауза
            if e.code == 429:
                delay = 60.0
                logger.warning(f"Rate limited (429), waiting {delay}s...")
            # 5xx - серверная ошибка, retry
            elif 500 <= e.code < 600:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning(f"Server error {e.code}, attempt {attempt}/{max_attempts}, retry in {delay:.1f}s")
            # 4xx (кроме 429) - клиентская ошибка, не retry
            else:
                logger.error(f"Client error {e.code}, not retrying")
                raise
            
            if attempt < max_attempts:
                time.sleep(delay)
        
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_exception = e
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            
            from logger import logger
            logger.warning(f"Network error: {e}, attempt {attempt}/{max_attempts}, retry in {delay:.1f}s")
            
            if attempt < max_attempts:
                time.sleep(delay)
    
    # Все попытки исчерпаны
    from logger import logger
    logger.error(f"All {max_attempts} attempts failed")
    raise last_exception
