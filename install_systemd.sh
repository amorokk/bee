#!/bin/bash

# 🚀 Быстрая установка Bee Bot на Linux
# Этот скрипт автоматизирует установку systemd сервиса

set -e

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Bee Bot - Установка systemd сервиса ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Проверка что запущен от root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Запустите скрипт с sudo:${NC}"
    echo -e "   sudo ./install_systemd.sh"
    exit 1
fi

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}⚠️ Python3 не найден. Устанавливаю...${NC}"
    apt update
    apt install -y python3 python3-pip python3-venv
fi

# Выбор варианта установки
echo -e "${YELLOW}Выберите вариант установки:${NC}"
echo "  1) Root (простой, быстрый, менее безопасный)"
echo "  2) Отдельный пользователь (безопасный, рекомендуется для продакшена)"
echo ""
read -p "Ваш выбор [1-2]: " choice

case $choice in
    1)
        echo -e "${BLUE}Выбран вариант: Root${NC}"
        VARIANT="root"
        SERVICE_FILE="bee-bot-root.service"
        ;;
    2)
        echo -e "${BLUE}Выбран вариант: Отдельный пользователь${NC}"
        VARIANT="user"
        SERVICE_FILE="bee-bot-user.service"
        ;;
    *)
        echo -e "${RED}❌ Неверный выбор${NC}"
        exit 1
        ;;
esac

# Проверка наличия файла сервиса
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}❌ Файл $SERVICE_FILE не найден!${NC}"
    echo -e "   Убедитесь что запускаете скрипт из директории проекта"
    exit 1
fi

# Установка директории
echo ""
echo -e "${YELLOW}📁 Установка файлов в /opt/bee...${NC}"
mkdir -p /opt/bee
cp -r ./* /opt/bee/ 2>/dev/null || true
cd /opt/bee

# Создание пользователя если нужно
if [ "$VARIANT" = "user" ]; then
    if id "bee-user" &>/dev/null; then
        echo -e "${YELLOW}⚠️ Пользователь bee-user уже существует${NC}"
    else
        echo -e "${YELLOW}👤 Создаю пользователя bee-user...${NC}"
        useradd -r -s /bin/bash -d /opt/bee -M bee-user
        echo -e "${GREEN}✅ Пользователь создан${NC}"
    fi
    
    echo -e "${YELLOW}🔐 Настройка прав доступа...${NC}"
    chown -R bee-user:bee-user /opt/bee
fi

# Проверка .env файла
if [ ! -f "/opt/bee/.env" ]; then
    echo ""
    echo -e "${YELLOW}⚠️ Файл .env не найден!${NC}"
    echo -e "${YELLOW}Создаю файл .env...${NC}"
    
    read -p "Введите TELEGRAM_BOT_TOKEN: " bot_token
    read -p "Введите TELEGRAM_ADMIN_CHAT_IDS: " admin_ids
    
    cat > /opt/bee/.env << EOF
# Конфигурация Telegram бота
TELEGRAM_BOT_TOKEN=$bot_token
TELEGRAM_ADMIN_CHAT_IDS=$admin_ids

# Уровень логирования
LOG_LEVEL=INFO
EOF
    
    if [ "$VARIANT" = "user" ]; then
        chown bee-user:bee-user /opt/bee/.env
    fi
    
    echo -e "${GREEN}✅ Файл .env создан${NC}"
fi

# Установка зависимостей
echo ""
echo -e "${YELLOW}📦 Установка зависимостей...${NC}"

if [ "$VARIANT" = "user" ]; then
    sudo -u bee-user bash << 'EOF'
    cd /opt/bee
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
EOF
else
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
fi

echo -e "${GREEN}✅ Зависимости установлены${NC}"

# Копирование systemd сервиса
echo ""
echo -e "${YELLOW}⚙️ Установка systemd сервиса...${NC}"
cp "/opt/bee/$SERVICE_FILE" /etc/systemd/system/bee-bot.service
systemctl daemon-reload
echo -e "${GREEN}✅ Сервис установлен${NC}"

# Запуск
echo ""
echo -e "${YELLOW}🚀 Запуск бота...${NC}"
systemctl start bee-bot
sleep 2

# Проверка статуса
if systemctl is-active --quiet bee-bot; then
    echo -e "${GREEN}✅ Бот успешно запущен!${NC}"
    echo ""
    echo -e "${BLUE}Последние записи в логе:${NC}"
    journalctl -u bee-bot -n 5 --no-pager
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Установка завершена успешно! 🎉${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Полезные команды:${NC}"
    echo "  Статус:      sudo systemctl status bee-bot"
    echo "  Остановить:  sudo systemctl stop bee-bot"
    echo "  Перезапуск:  sudo systemctl restart bee-bot"
    echo "  Логи:        sudo journalctl -u bee-bot -f"
    echo "  Автозапуск:  sudo systemctl enable bee-bot"
    echo ""
    
    # Предложение включить автозапуск
    read -p "Включить автозапуск при перезагрузке? [y/N]: " auto_start
    if [[ "$auto_start" =~ ^[Yy]$ ]]; then
        systemctl enable bee-bot
        echo -e "${GREEN}✅ Автозапуск включен${NC}"
    fi
else
    echo -e "${RED}❌ Ошибка запуска бота${NC}"
    echo ""
    echo -e "${YELLOW}Проверьте логи:${NC}"
    journalctl -u bee-bot -n 20 --no-pager
    exit 1
fi
