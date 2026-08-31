#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🤖 Запуск бота для отбора волонтеров МБ 2026${NC}"

# Проверка существования .env файла
if [ ! -f .env ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo -e "${YELLOW}Скопируйте .env.example в .env и заполните необходимые переменные.${NC}"
    exit 1
fi

# Проверка установки зависимостей через Poetry
echo -e "${BLUE}📦 Проверка и установка зависимостей через Poetry...${NC}"
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}❌ Poetry не установлен! Установите Poetry: https://python-poetry.org/docs/#installation${NC}"
    exit 1
fi

poetry install

# Проверка подключения к Redis
echo -e "${BLUE}🔧 Проверка Redis...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ Redis не запущен. Попытка запуска...${NC}"
    # Для macOS
    if command -v brew &> /dev/null; then
        brew services start redis
    # Для Linux
    elif command -v systemctl &> /dev/null; then
        sudo systemctl start redis-server
    else
        echo -e "${RED}❌ Не удалось запустить Redis автоматически. Запустите его вручную.${NC}"
        exit 1
    fi
fi

# Применение миграций (если используются)
if [ -d "alembic" ] && [ -f "alembic.ini" ]; then
    echo -e "${BLUE}🗄️ Применение миграций базы данных...${NC}"
    poetry run alembic upgrade head || true
fi

# Запуск бота
echo -e "${GREEN}🚀 Запуск бота...${NC}"
poetry run python main.py
