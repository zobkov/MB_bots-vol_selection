#!/usr/bin/env python3
"""
Скрипт для проверки состояния department_test_results в базе данных
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import Database
from database.repositories import DepartmentTestRepository, UserRepository
from config.config import load_config


async def check_test_completion_status():
    """Проверка статуса завершения тестов"""
    print("🔍 Проверка статуса тестов в базе данных...")
    
    config = load_config()
    db = Database(config.database_url)
    await db.connect()
    
    session = await db.get_session()
    try:
        dept_repo = DepartmentTestRepository(session)
        user_repo = UserRepository(session)
        
        # Получаем всех пользователей с тестами
        users = await user_repo.get_all_users()
        
        print(f"\n📊 Найдено пользователей: {len(users)}")
        
        for user in users:
            print(f"\n👤 Пользователь {user.telegram_id} ({user.username or 'без username'}):")
            
            # Проверяем все типы тестов
            test_types = ["logistics", "pr", "marketing", "program", "partners"]
            
            for test_type in test_types:
                try:
                    # Получаем результат теста если есть
                    test_result = await dept_repo.get_test_result(user.id, test_type)
                    
                    if test_result:
                        status_icon = "✅" if test_result.is_completed else "⏳"
                        completed_text = "завершен" if test_result.is_completed else "не завершен"
                        
                        # Считаем количество ответов
                        answers_count = len(test_result.answers) if test_result.answers else 0
                        
                        print(f"   {status_icon} {test_type}: {completed_text} ({answers_count} ответов)")
                        
                        if test_result.started_at:
                            print(f"      Начат: {test_result.started_at}")
                        if test_result.completed_at:
                            print(f"      Завершен: {test_result.completed_at}")
                    else:
                        print(f"   ❌ {test_type}: тест не найден")
                        
                except Exception as e:
                    print(f"   ⚠️ {test_type}: ошибка проверки - {e}")
    
    finally:
        await session.close()
        await db.disconnect()


async def check_specific_user(telegram_id: int):
    """Проверка конкретного пользователя"""
    print(f"🔍 Проверка пользователя {telegram_id}...")
    
    config = load_config()
    db = Database(config)
    
    session = await db.get_session()
    try:
        dept_repo = DepartmentTestRepository(session)
        user_repo = UserRepository(session)
        
        user = await user_repo.get_user_by_telegram_id(telegram_id)
        if not user:
            print(f"❌ Пользователь {telegram_id} не найден")
            return
        
        print(f"👤 Пользователь: {user.telegram_username or 'без username'} (ID: {user.id})")
        
        # Детальная проверка логистики
        logistics_result = await dept_repo.get_test_with_answers(user.id, "logistics")
        if logistics_result:
            print(f"\n🔧 Логистика:")
            print(f"   ID результата: {logistics_result.id}")
            print(f"   Завершен: {logistics_result.is_completed}")
            print(f"   Начат: {logistics_result.started_at}")
            print(f"   Завершен: {logistics_result.completed_at}")
            print(f"   Количество ответов: {len(logistics_result.answers) if logistics_result.answers else 0}")
            
            if logistics_result.answers:
                print(f"   Ответы:")
                for answer in logistics_result.answers:
                    timeout_text = " (timeout)" if answer.is_timeout else ""
                    print(f"     Q{answer.question_number}: '{answer.answer_text}'{timeout_text}")
        else:
            print(f"\n❌ Тест логистики не найден")
    
    finally:
        await session.close()


async def main():
    """Основная функция"""
    if len(sys.argv) > 1:
        try:
            telegram_id = int(sys.argv[1])
            await check_specific_user(telegram_id)
        except ValueError:
            print("❌ Некорректный telegram_id")
            return 1
    else:
        await check_test_completion_status()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)