#!/usr/bin/env python3
"""
Простая проверка статуса тестов в базе данных
"""
import asyncio
import sys
import logging
from sqlalchemy import text

from config.config import load_config
from database.db import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_test_status(telegram_id: int):
    """Простая проверка через SQL"""
    config = load_config()
    db = Database(config)
    
    session = await db.get_session()
    try:
        # Находим пользователя
        user_query = text("""
            SELECT id, telegram_username, telegram_id 
            FROM users 
            WHERE telegram_id = :telegram_id
        """)
        user_result = await session.execute(user_query, {"telegram_id": telegram_id})
        user_row = user_result.fetchone()
        
        if not user_row:
            print(f"❌ Пользователь {telegram_id} не найден")
            return
        
        user_id, username, tg_id = user_row
        print(f"👤 Пользователь: {username or 'без username'} (ID: {user_id}, TG: {tg_id})")
        
        # Проверяем статус тестов
        test_query = text("""
            SELECT department, is_completed, started_at, completed_at, created_at
            FROM department_test_results 
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """)
        test_result = await session.execute(test_query, {"user_id": user_id})
        test_rows = test_result.fetchall()
        
        if test_rows:
            print(f"\n📊 Найдено тестов: {len(test_rows)}")
            for row in test_rows:
                department, is_completed, started_at, completed_at, created_at = row
                status = "✅ Завершен" if is_completed else "⏳ В процессе"
                print(f"   🔧 {department}: {status}")
                print(f"      Создан: {created_at}")
                print(f"      Начат: {started_at}")
                if completed_at:
                    print(f"      Завершен: {completed_at}")
                print()
        else:
            print(f"\n❌ Тесты не найдены")
            
        # Проверяем ответы для логистики
        answers_query = text("""
            SELECT dtr.department, dta.question_number, dta.answer_text, dta.is_timeout
            FROM department_test_results dtr
            JOIN department_test_answers dta ON dtr.id = dta.test_result_id
            WHERE dtr.user_id = :user_id AND dtr.department = 'logistics'
            ORDER BY dta.question_number
        """)
        answers_result = await session.execute(answers_query, {"user_id": user_id})
        answers_rows = answers_result.fetchall()
        
        if answers_rows:
            print(f"📝 Ответы логистики:")
            for row in answers_rows:
                department, q_num, answer, is_timeout = row
                timeout_text = " (timeout)" if is_timeout else ""
                print(f"   Q{q_num}: '{answer}'{timeout_text}")
        else:
            print(f"❌ Ответов логистики не найдено")
            
    finally:
        await session.close()

async def main():
    if len(sys.argv) > 1:
        try:
            telegram_id = int(sys.argv[1])
            await check_test_status(telegram_id)
        except ValueError:
            print("❌ Некорректный telegram_id")
            return 1
    else:
        print("Использование: python3 check_test_simple.py <telegram_id>")
        return 1
        
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)