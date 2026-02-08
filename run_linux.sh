#!/bin/bash

# 🐝 Bee Bot Management Script
# Скрипт для управления ботом на Linux

set -e

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$BOT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
BOT_SCRIPT="$BOT_DIR/telegram_bot.py"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}Виртуальное окружение не найдено. Создаю...${NC}"
        python3 -m venv "$VENV_DIR"
        echo -e "${GREEN}✅ Виртуальное окружение создано${NC}"
    fi
}

install_deps() {
    echo -e "${YELLOW}Устанавливаю зависимости...${NC}"
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q -r "$BOT_DIR/requirements.txt"
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
}

check_env() {
    if [ ! -f "$BOT_DIR/.env" ]; then
        echo -e "${RED}❌ Файл .env не найден!${NC}"
        echo -e "${YELLOW}Создайте файл .env с токеном бота:${NC}"
        echo "  TELEGRAM_BOT_TOKEN=ваш_токен"
        echo "  TELEGRAM_ADMIN_CHAT_IDS=ваш_chat_id"
        exit 1
    fi
}

start_bot() {
    echo -e "${YELLOW}Запускаю бота...${NC}"
    cd "$BOT_DIR"
    "$PYTHON" "$BOT_SCRIPT"
}

# Основная логика
case "${1:-start}" in
    start)
        check_venv
        check_env
        if [ ! -f "$VENV_DIR/bin/python" ]; then
            install_deps
        fi
        start_bot
        ;;
    
    install)
        check_venv
        install_deps
        echo -e "${GREEN}✅ Установка завершена${NC}"
        ;;
    
    screen)
        check_venv
        check_env
        echo -e "${YELLOW}Запускаю бота в screen сессии 'bot'...${NC}"
        screen -dmS bot bash -c "cd $BOT_DIR && $PYTHON $BOT_SCRIPT"
        sleep 1
        if screen -list | grep -q "bot"; then
            echo -e "${GREEN}✅ Бот запущен в фоне${NC}"
            echo -e "${YELLOW}Подключиться: screen -r bot${NC}"
            echo -e "${YELLOW}Отключиться: Ctrl+A, затем D${NC}"
        else
            echo -e "${RED}❌ Не удалось запустить бота${NC}"
            exit 1
        fi
        ;;
    
    tmux)
        check_venv
        check_env
        echo -e "${YELLOW}Запускаю бота в tmux сессии 'bot'...${NC}"
        tmux new-session -d -s bot "cd $BOT_DIR && $PYTHON $BOT_SCRIPT"
        sleep 1
        if tmux has-session -t bot 2>/dev/null; then
            echo -e "${GREEN}✅ Бот запущен в фоне${NC}"
            echo -e "${YELLOW}Подключиться: tmux attach -t bot${NC}"
            echo -e "${YELLOW}Отключиться: Ctrl+B, затем D${NC}"
        else
            echo -e "${RED}❌ Не удалось запустить бота${NC}"
            exit 1
        fi
        ;;
    
    stop)
        echo -e "${YELLOW}Останавливаю бота...${NC}"
        if pkill -f "$BOT_SCRIPT"; then
            echo -e "${GREEN}✅ Бот остановлен${NC}"
        else
            echo -e "${RED}❌ Бот не запущен${NC}"
            exit 1
        fi
        ;;
    
    status)
        if pgrep -f "$BOT_SCRIPT" > /dev/null; then
            PID=$(pgrep -f "$BOT_SCRIPT")
            echo -e "${GREEN}✅ Бот работает (PID: $PID)${NC}"
            echo ""
            echo "Последние записи в логе:"
            tail -5 "$BOT_DIR/bot.log" 2>/dev/null || echo "Лог-файл не найден"
        else
            echo -e "${RED}❌ Бот не запущен${NC}"
            exit 1
        fi
        ;;
    
    logs)
        if [ -f "$BOT_DIR/bot.log" ]; then
            tail -f "$BOT_DIR/bot.log"
        else
            echo -e "${RED}❌ Лог-файл не найден${NC}"
            exit 1
        fi
        ;;
    
    restart)
        echo -e "${YELLOW}Перезапускаю бота...${NC}"
        $0 stop 2>/dev/null || true
        sleep 2
        $0 "${2:-start}"
        ;;
    
    help|--help|-h)
        echo "🐝 Bee Bot - Management Script"
        echo ""
        echo "Использование: ./run_linux.sh [команда]"
        echo ""
        echo "Команды:"
        echo "  start      - Запустить бота в текущем терминале (по умолчанию)"
        echo "  screen     - Запустить бота в фоне (screen)"
        echo "  tmux       - Запустить бота в фоне (tmux)"
        echo "  stop       - Остановить бота"
        echo "  restart    - Перезапустить бота"
        echo "  status     - Проверить статус бота"
        echo "  logs       - Показать логи в реальном времени"
        echo "  install    - Установить зависимости"
        echo "  help       - Показать эту справку"
        echo ""
        echo "Примеры:"
        echo "  ./run_linux.sh              # Запуск в текущем терминале"
        echo "  ./run_linux.sh screen       # Запуск в фоне (screen)"
        echo "  ./run_linux.sh status       # Проверить работает ли бот"
        echo "  ./run_linux.sh logs         # Смотреть логи (Ctrl+C для выхода)"
        echo ""
        echo "Для systemd сервиса смотрите: LINUX_GUIDE.md"
        ;;
    
    *)
        echo -e "${RED}❌ Неизвестная команда: $1${NC}"
        echo "Используйте: ./run_linux.sh help"
        exit 1
        ;;
esac
