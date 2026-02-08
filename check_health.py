"""
Скрипт для проверки базовой работоспособности проекта.
Импортирует все модули и проверяет основные компоненты.
"""

import sys


def check_imports():
    """Проверка импорта всех модулей."""
    print("🔍 Проверка импортов...")
    
    try:
        import config
        print("  ✅ config.py")
    except Exception as e:
        print(f"  ❌ config.py: {e}")
        return False
    
    try:
        import logger
        print("  ✅ logger.py")
    except Exception as e:
        print(f"  ❌ logger.py: {e}")
        return False
    
    try:
        import database
        print("  ✅ database.py")
    except Exception as e:
        print(f"  ❌ database.py: {e}")
        return False
    
    try:
        import models
        print("  ✅ models.py")
    except Exception as e:
        print(f"  ❌ models.py: {e}")
        return False
    
    try:
        import utils
        print("  ✅ utils.py")
    except Exception as e:
        print(f"  ❌ utils.py: {e}")
        return False
    
    try:
        import parser_gate
        print("  ✅ parser_gate.py")
    except Exception as e:
        print(f"  ❌ parser_gate.py: {e}")
        return False
    
    try:
        import telegram_bot
        print("  ✅ telegram_bot.py")
    except Exception as e:
        print(f"  ❌ telegram_bot.py: {e}")
        return False
    
    return True


def check_components():
    """Проверка основных компонентов."""
    print("\n🔧 Проверка компонентов...")
    
    # Config
    from config import config
    print(f"  ✅ Config: BASE_URL={config.BASE_URL[:30]}...")
    print(f"  ✅ Config: MAX_WORKERS={config.MAX_WORKERS}")
    print(f"  ✅ Config: CHECK_INTERVAL_SEC={config.CHECK_INTERVAL_SEC}")
    
    # Logger
    from logger import logger, api_logger
    print(f"  ✅ Logger: {type(logger).__name__}")
    print(f"  ✅ API Logger: {type(api_logger).__name__}")
    
    # Database
    from database import Database
    db = Database(':memory:')  # Используем in-memory для теста
    print(f"  ✅ Database: {type(db).__name__}")
    
    # Models
    from models import TokenStatus
    status = TokenStatus(coin="test", fixed_list=[1, 2], fixable_list=[1])
    print(f"  ✅ TokenStatus: {status.coin} - {status.get_status_emoji()}")
    
    # Utils
    from utils import RateLimiter, retry_with_backoff
    limiter = RateLimiter(min_interval=1.0)
    print(f"  ✅ RateLimiter: min_interval={limiter.min_interval}")
    
    # Parser
    from parser_gate import ProjectCache
    cache = ProjectCache()
    print(f"  ✅ ProjectCache: {type(cache).__name__}")
    
    return True


def main():
    """Главная функция проверки."""
    print("=" * 60)
    print("🐝 Проверка работоспособности Bee Bot")
    print("=" * 60)
    
    if not check_imports():
        print("\n❌ Ошибка при импорте модулей!")
        sys.exit(1)
    
    if not check_components():
        print("\n❌ Ошибка при проверке компонентов!")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Все проверки пройдены успешно!")
    print("=" * 60)
    print("\n📝 Следующие шаги:")
    print("  1. Настройте .env файл (скопируйте .env.example)")
    print("  2. Установите TELEGRAM_BOT_TOKEN")
    print("  3. Запустите: python telegram_bot.py")
    print("\n📊 Тестирование:")
    print("  - Запуск тестов: pytest tests/ -v")
    print("  - Покрытие: pytest tests/ --cov=. --cov-report=html")


if __name__ == "__main__":
    main()
