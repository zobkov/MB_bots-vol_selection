#!/usr/bin/env python3
"""
Скрипт для инициализации проекта бота
Создает необходимые файлы конфигурации и проверяет настройки
"""

import os
import shutil
from pathlib import Path

def main():
    print("🤖 Инициализация проекта бота для отбора волонтеров МБ 2026\n")
    
    # Проверяем существование .env файла
    if not os.path.exists('.env'):
        print("📝 Создание файла .env из .env.example...")
        shutil.copy('.env.example', '.env')
        print("✅ Файл .env создан. Не забудьте заполнить переменные окружения!")
    else:
        print("✅ Файл .env уже существует")
    
    # Проверяем Google credentials
    google_creds_path = Path('config/google_credentials.json')
    google_example_path = Path('config/google_credentials.json.example')
    
    if google_example_path.exists() and not google_creds_path.exists():
        print("📝 Найден пример Google credentials. Не забудьте настроить config/google_credentials.json")
    
    # Создаем директории для логов если нужно
    logs_dir = Path('logs')
    if not logs_dir.exists():
        logs_dir.mkdir()
        print("📁 Создана директория logs/")
    
    print("\n🎯 Что нужно сделать дальше:")
    print("1. Заполните переменные в файле .env")
    print("2. Установите зависимости: poetry install")
    print("3. Настройте PostgreSQL и Redis")
    print("4. При необходимости настройте Google Sheets (опционально)")
    print("5. Запустите: ./start.sh или poetry run python main.py")
    print("\n📖 Подробная инструкция в README.md")

if __name__ == "__main__":
    main()
