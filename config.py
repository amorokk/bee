"""
Централизованная конфигурация проекта.
Все константы и настройки в одном месте.
"""

import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


@dataclass
class Config:
    """Конфигурация бота и парсера."""
    
    # =========================
    # Telegram Bot
    # =========================
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_ADMIN_CHAT_IDS: str = os.getenv('TELEGRAM_ADMIN_CHAT_IDS', '')
    
    # =========================
    # API Configuration
    # =========================
    BASE_URL: str = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list"
    REQUEST_TIMEOUT: int = 30
    
    # User-Agent rotation для human-like поведения
    USER_AGENTS: List[str] = None  # Инициализируется в __post_init__
    
    # =========================
    # Парсинг
    # =========================
    MAX_WORKERS: int = 2  # Было 8 - слишком агрессивно!
    TOTAL_PAGES: int = 112
    MAX_PAGES_TO_FETCH: int = 20  # Ограничение для /filter
    LIMIT_PER_PAGE: int = 7
    
    # =========================
    # Rate Limiting
    # =========================
    MIN_REQUEST_INTERVAL: float = 2.0  # секунды между запросами
    MIN_DELAY: float = 2.0  # минимальная задержка
    MAX_DELAY: float = 4.0  # максимальная задержка
    
    # =========================
    # Интервалы проверки
    # =========================
    CHECK_INTERVAL_SEC: float = 60.0  # Было 10 - слишком часто!
    POLL_INTERVAL_SEC: float = 1.0
    
    # =========================
    # Кэширование
    # =========================
    CACHE_TTL_SEC: int = 300  # 5 минут
    
    # =========================
    # База данных
    # =========================
    DB_PATH: str = 'bot_data.db'
    DB_BACKUP_INTERVAL_HOURS: int = 24
    DB_LOG_RETENTION_DAYS: int = 30
    
    # =========================
    # Retry Logic
    # =========================
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_BASE: float = 2.0  # секунды
    RETRY_MAX_DELAY: float = 60.0
    RETRY_429_DELAY: float = 60.0  # Задержка при rate limit
    
    # =========================
    # Alerting
    # =========================
    FAILURE_THRESHOLD: int = 1
    COIN_FAILURE_THRESHOLD: int = 1
    
    # =========================
    # Logging
    # =========================
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = 'bot.log'
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5
    
    API_LOG_FILE: str = 'api.log'
    API_LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
    API_LOG_BACKUP_COUNT: int = 3
    
    def __post_init__(self):
        """Инициализация значений, которые не могут быть в дефолтах."""
        if self.USER_AGENTS is None:
            self.USER_AGENTS = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]
    
    def validate(self) -> None:
        """Проверка конфигурации при старте."""
        warnings = []
        errors = []
        
        # Критические проверки
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN не установлен!")
        
        if not self.BASE_URL.startswith('https://'):
            errors.append(f"BASE_URL должен начинаться с https:// (текущий: {self.BASE_URL})")
        
        # Предупреждения
        if self.MAX_WORKERS > 3:
            warnings.append(
                f"⚠️  MAX_WORKERS={self.MAX_WORKERS} слишком высокий! "
                f"Риск блокировки API. Рекомендуется 2-3."
            )
        
        if self.CHECK_INTERVAL_SEC < 30:
            warnings.append(
                f"⚠️  CHECK_INTERVAL_SEC={self.CHECK_INTERVAL_SEC} слишком низкий! "
                f"Риск блокировки API. Рекомендуется >= 60 секунд."
            )
        
        if self.MIN_REQUEST_INTERVAL < 1.0:
            warnings.append(
                f"⚠️  MIN_REQUEST_INTERVAL={self.MIN_REQUEST_INTERVAL} слишком низкий! "
                f"Рекомендуется >= 2.0 секунд."
            )
        
        if self.MAX_PAGES_TO_FETCH > 30:
            warnings.append(
                f"⚠️  MAX_PAGES_TO_FETCH={self.MAX_PAGES_TO_FETCH} может быть слишком много. "
                f"Рекомендуется 20-30 для баланса между скоростью и полнотой данных."
            )
        
        # Вывод результатов валидации
        if errors:
            raise ValueError("Ошибки в конфигурации:\n" + "\n".join(f"  - {e}" for e in errors))
        
        if warnings:
            import logging
            log = logging.getLogger(__name__)
            log.warning("Предупреждения конфигурации:")
            for w in warnings:
                log.warning(f"  {w}")
    
    def get_admin_chat_ids(self) -> List[str]:
        """Получить список admin chat IDs."""
        return [s.strip() for s in self.TELEGRAM_ADMIN_CHAT_IDS.split(",") if s.strip()]


# Глобальный экземпляр конфигурации
config = Config()

# Валидация при импорте
config.validate()
