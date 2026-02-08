"""
Настройка логирования для проекта.
Использует ротацию файлов и разделение логов на основной и API.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from config import config


def setup_logging():
    """
    Настройка системы логирования.
    
    Создает два логгера:
    - Основной logger: для всех событий бота
    - API logger: специально для HTTP запросов к API
    
    Оба логгера пишут в файлы с ротацией и в консоль.
    """
    # Формат логов
    log_format = '[%(asctime)s] %(levelname)-8s [%(name)s:%(lineno)d] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Уровень логирования из конфига
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # =======================
    # Корневой логгер
    # =======================
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие handlers (на случай повторного вызова)
    root_logger.handlers.clear()
    
    # Handler для основного лог-файла (с ротацией)
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(file_handler)
    
    # Handler для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)
    
    # =======================
    # API логгер
    # =======================
    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.INFO)
    api_logger.propagate = False  # Не передавать в root logger
    
    # Handler для API лог-файла
    api_handler = RotatingFileHandler(
        config.API_LOG_FILE,
        maxBytes=config.API_LOG_MAX_BYTES,
        backupCount=config.API_LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    api_handler.setLevel(logging.INFO)
    api_handler.setFormatter(logging.Formatter(log_format, date_format))
    api_logger.addHandler(api_handler)
    
    # API логи также в консоль (но только WARNING и выше)
    api_console_handler = logging.StreamHandler(sys.stdout)
    api_console_handler.setLevel(logging.WARNING)
    api_console_handler.setFormatter(logging.Formatter(log_format, date_format))
    api_logger.addHandler(api_console_handler)
    
    # Логируем успешную инициализацию
    root_logger.info("=" * 60)
    root_logger.info("Logging system initialized")
    root_logger.info(f"Log level: {config.LOG_LEVEL}")
    root_logger.info(f"Main log file: {config.LOG_FILE}")
    root_logger.info(f"API log file: {config.API_LOG_FILE}")
    root_logger.info("=" * 60)
    
    return root_logger, api_logger


# Инициализация при импорте
logger, api_logger = setup_logging()


# Удобные функции для быстрого логирования
def log_info(message: str):
    """Быстрая функция для info логирования."""
    logger.info(message)


def log_warning(message: str):
    """Быстрая функция для warning логирования."""
    logger.warning(message)


def log_error(message: str, exc_info=False):
    """Быстрая функция для error логирования."""
    logger.error(message, exc_info=exc_info)


def log_api_request(method: str, url: str, status_code: int = None, duration_ms: int = None, error: str = None):
    """
    Логирование API запроса.
    
    Args:
        method: HTTP метод (GET, POST, etc.)
        url: URL endpoint
        status_code: HTTP статус код ответа
        duration_ms: Длительность запроса в миллисекундах
        error: Текст ошибки (если была)
    """
    if error:
        api_logger.error(f"{method} {url} -> ERROR: {error}")
    elif status_code:
        level = logging.INFO if status_code < 400 else logging.WARNING
        duration_str = f" ({duration_ms}ms)" if duration_ms else ""
        api_logger.log(level, f"{method} {url} -> {status_code}{duration_str}")
    else:
        api_logger.info(f"{method} {url} -> pending...")
