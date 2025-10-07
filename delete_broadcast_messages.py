#!/usr/bin/env python3
"""
Скрипт для удаления отправленных сообщений рассылки
Читает файл sent_messages_broadcast.json и удаляет сообщения
"""

import asyncio
import logging
import json
import os
from typing import List, Dict
from dataclasses import dataclass
from aiogram import Bot
from config.config import load_config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class MessageToDelete:
    """Класс для хранения информации о сообщении для удаления"""
    message_id: int
    chat_id: int
    volunteer_name: str
    volunteer_username: str
    department: str
    sent_at: str

class MessageDeletionService:
    """Сервис для удаления отправленных сообщений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        
    def load_sent_messages(self, file_path: str) -> List[MessageToDelete]:
        """Загружает список отправленных сообщений из файла"""
        messages_to_delete = []
        
        try:
            if not os.path.exists(file_path):
                logger.error(f"Файл {file_path} не найден")
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for msg_data in data:
                try:
                    volunteer = msg_data.get('volunteer', {})
                    message_to_delete = MessageToDelete(
                        message_id=msg_data['message_id'],
                        chat_id=msg_data['chat_id'],
                        volunteer_name=volunteer.get('full_name', 'Неизвестно'),
                        volunteer_username=volunteer.get('username', 'без_username'),
                        department=volunteer.get('department', 'Неизвестный отдел'),
                        sent_at=msg_data.get('sent_at', 'Неизвестно')
                    )
                    messages_to_delete.append(message_to_delete)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Пропускаем некорректную запись: {msg_data}, ошибка: {e}")
            
            logger.info(f"Загружено {len(messages_to_delete)} сообщений для удаления")
            return messages_to_delete
            
        except Exception as e:
            logger.error(f"Ошибка при чтении файла {file_path}: {e}")
            return []
    
    async def delete_message(self, message: MessageToDelete, dry_run: bool = False) -> bool:
        """
        Удаляет одно сообщение
        
        Args:
            message: Информация о сообщении
            dry_run: Режим драй-рана (не удалять реально)
            
        Returns:
            bool: Успешность удаления
        """
        if dry_run:
            logger.info(f"[DRY RUN] Удаление сообщения {message.message_id} у {message.volunteer_name}")
            return True
        
        try:
            await self.bot.delete_message(
                chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"✅ Удалено сообщение {message.message_id} у {message.volunteer_name} ({message.volunteer_username})")
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "message to delete not found" in error_msg:
                logger.warning(f"⚠️  Сообщение {message.message_id} у {message.volunteer_name} уже удалено")
            elif "message can't be deleted" in error_msg:
                logger.warning(f"⚠️  Сообщение {message.message_id} у {message.volunteer_name} нельзя удалить (слишком старое)")
            elif "bot was blocked by the user" in error_msg:
                logger.warning(f"⚠️  {message.volunteer_name} заблокировал бота")
            else:
                logger.error(f"❌ Ошибка удаления сообщения {message.message_id} у {message.volunteer_name}: {e}")
            
            return False
    
    async def delete_all_messages(
        self, 
        messages: List[MessageToDelete], 
        delay: float = 0.1,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Удаляет все сообщения из списка
        
        Args:
            messages: Список сообщений для удаления
            delay: Задержка между удалениями (в секундах)
            dry_run: Режим драй-рана
            
        Returns:
            dict: Статистика удаления
        """
        if not messages:
            logger.warning("Нет сообщений для удаления")
            return {"total": 0, "deleted": 0, "failed": 0}
        
        stats = {
            "total": len(messages),
            "deleted": 0,
            "failed": 0
        }
        
        mode_text = "[DRY RUN] " if dry_run else ""
        logger.info(f"{mode_text}Начинаем удаление {stats['total']} сообщений...")
        
        for i, message in enumerate(messages, 1):
            success = await self.delete_message(message, dry_run)
            
            if success:
                stats["deleted"] += 1
            else:
                stats["failed"] += 1
            
            # Прогресс каждые 10 сообщений
            if i % 10 == 0:
                logger.info(f"{mode_text}Прогресс: {i}/{stats['total']} ({stats['deleted']} удалено, {stats['failed']} ошибок)")
            
            # Задержка между удалениями (не для драй-рана)
            if delay > 0 and not dry_run:
                await asyncio.sleep(delay)
        
        logger.info(f"{mode_text}Удаление завершено. Удалено: {stats['deleted']}, ошибок: {stats['failed']}")
        return stats
    
    def get_messages_by_department(self, messages: List[MessageToDelete]) -> Dict[str, List[MessageToDelete]]:
        """Группирует сообщения по департаментам"""
        departments = {}
        for message in messages:
            if message.department not in departments:
                departments[message.department] = []
            departments[message.department].append(message)
        return departments

def get_user_confirmation(prompt: str) -> bool:
    """Получает подтверждение от пользователя"""
    while True:
        response = input(f"{prompt} (y/N): ").strip().lower()
        if response == 'y':
            return True
        elif response in ['n', '']:
            return False
        else:
            print("❌ Введите 'y' для подтверждения или 'n' для отмены")

def display_messages_preview(messages: List[MessageToDelete], max_display: int = 10):
    """Показывает превью списка сообщений"""
    print(f"\n📧 Список сообщений для удаления (показано {min(len(messages), max_display)} из {len(messages)}):")
    
    for i, message in enumerate(messages[:max_display]):
        print(f"  {i+1}. {message.volunteer_name} (@{message.volunteer_username}) - {message.department}")
        print(f"      Сообщение ID: {message.message_id}, Отправлено: {message.sent_at}")
    
    if len(messages) > max_display:
        print(f"  ... и еще {len(messages) - max_display} сообщений")

def display_department_stats(messages_by_dept: Dict[str, List[MessageToDelete]]):
    """Показывает статистику по департаментам"""
    print(f"\n📊 Статистика сообщений по департаментам:")
    total = 0
    for dept, msg_list in messages_by_dept.items():
        count = len(msg_list)
        total += count
        print(f"  • {dept}: {count} сообщений")
    print(f"  • Всего: {total} сообщений")

async def main():
    """Основная функция для удаления сообщений"""
    
    # Путь к файлу с отправленными сообщениями
    sent_messages_file = "sent_messages_broadcast.json"
    
    try:
        print("🗑️  Удаление отправленных сообщений рассылки")
        print("=" * 70)
        
        # Загружаем конфигурацию
        config = load_config()
        
        # Создаем бота
        bot = Bot(token=config.tg_bot.token)
        
        # Создаем сервис удаления
        deletion_service = MessageDeletionService(bot)
        
        print(f"📁 Файл с сообщениями: {sent_messages_file}")
        
        # Загружаем сообщения для удаления
        messages_to_delete = deletion_service.load_sent_messages(sent_messages_file)
        
        if not messages_to_delete:
            print("❌ Нет сообщений для удаления")
            return
        
        # Группируем по департаментам
        messages_by_dept = deletion_service.get_messages_by_department(messages_to_delete)
        
        # Показываем статистику
        display_department_stats(messages_by_dept)
        display_messages_preview(messages_to_delete)
        
        # Выбор режима удаления
        print("\n🗑️  Выберите режим удаления:")
        print("1. Драй-ран (проверка без удаления)")
        print("2. Удаление всех сообщений")
        print("3. Удаление по департаментам")
        
        while True:
            choice = input("\nВведите номер (1, 2 или 3): ").strip()
            if choice in ['1', '2', '3']:
                choice = int(choice)
                break
            print("❌ Неверный выбор. Введите 1, 2 или 3.")
        
        if choice == 1:
            # Драй-ран режим
            print(f"\n🧪 Режим драй-рана (проверка без удаления)")
            print(f"📊 Будет проверено {len(messages_to_delete)} сообщений")
            
            if not get_user_confirmation("Запустить драй-ран?"):
                print("❌ Драй-ран отменен")
                return
            
            print(f"\n🔍 Запускаем драй-ран...")
            stats = await deletion_service.delete_all_messages(
                messages_to_delete,
                delay=0,  # Без задержки в драй-ране
                dry_run=True
            )
            
            print(f"\n✅ Драй-ран завершен!")
            print(f"📊 Результаты проверки:")
            print(f"  • Всего сообщений: {stats['total']}")
            print(f"  • Готовы к удалению: {stats['deleted']}")
            print(f"  • Проблемы: {stats['failed']}")
            
        elif choice == 2:
            # Полное удаление
            print(f"\n🗑️  Удаление всех сообщений")
            print(f"📧 Всего сообщений: {len(messages_to_delete)}")
            print(f"⏱️  Задержка между удалениями: 0.1 секунды")
            print(f"⏰ Примерное время выполнения: {len(messages_to_delete) * 0.1 / 60:.1f} минут")
            
            # Двойное подтверждение
            print(f"\n⚠️  ВНИМАНИЕ: Вы собираетесь удалить {len(messages_to_delete)} сообщений!")
            
            if not get_user_confirmation("Вы уверены, что хотите удалить все сообщения?"):
                print("❌ Удаление отменено")
                return
            
            print(f"\n🚨 ПОСЛЕДНЕЕ ПОДТВЕРЖДЕНИЕ:")
            if not get_user_confirmation(f"УДАЛИТЬ {len(messages_to_delete)} СООБЩЕНИЙ? ЭТО ДЕЙСТВИЕ НЕЛЬЗЯ ОТМЕНИТЬ!"):
                print("❌ Удаление отменено")
                return
            
            print(f"\n🗑️  Запускаем удаление...")
            stats = await deletion_service.delete_all_messages(
                messages_to_delete,
                delay=0.1
            )
            
            print(f"\n✅ Удаление завершено!")
            print(f"📊 Итоговая статистика:")
            print(f"  • Всего сообщений: {stats['total']}")
            print(f"  • Успешно удалено: {stats['deleted']}")
            print(f"  • Ошибок: {stats['failed']}")
            
            if stats['failed'] > 0:
                success_rate = (stats['deleted'] / stats['total']) * 100
                print(f"  • Процент успешности: {success_rate:.1f}%")
            
            # Удаляем файл с сообщениями после успешного удаления
            if stats['deleted'] > 0:
                try:
                    os.remove(sent_messages_file)
                    print(f"\n🗑️  Файл {sent_messages_file} удален")
                except Exception as e:
                    logger.warning(f"Не удалось удалить файл {sent_messages_file}: {e}")
            
        else:
            # Удаление по департаментам
            print(f"\n🏢 Удаление по департаментам")
            print(f"📊 Доступные департаменты:")
            
            dept_list = list(messages_by_dept.keys())
            for i, dept in enumerate(dept_list, 1):
                count = len(messages_by_dept[dept])
                print(f"  {i}. {dept} ({count} сообщений)")
            
            while True:
                dept_choice = input(f"\nВыберите департамент (1-{len(dept_list)}): ").strip()
                try:
                    dept_index = int(dept_choice) - 1
                    if 0 <= dept_index < len(dept_list):
                        selected_dept = dept_list[dept_index]
                        break
                    else:
                        print(f"❌ Введите число от 1 до {len(dept_list)}")
                except ValueError:
                    print(f"❌ Введите корректное число")
            
            dept_messages = messages_by_dept[selected_dept]
            print(f"\n🏢 Выбран департамент: {selected_dept}")
            print(f"📧 Сообщений для удаления: {len(dept_messages)}")
            
            if not get_user_confirmation(f"Удалить {len(dept_messages)} сообщений для департамента {selected_dept}?"):
                print("❌ Удаление отменено")
                return
            
            print(f"\n🗑️  Удаляем сообщения для департамента {selected_dept}...")
            stats = await deletion_service.delete_all_messages(
                dept_messages,
                delay=0.1
            )
            
            print(f"\n✅ Удаление для департамента {selected_dept} завершено!")
            print(f"📊 Результаты:")
            print(f"  • Удалено: {stats['deleted']}")
            print(f"  • Ошибок: {stats['failed']}")
        
        print(f"\n💡 Примечание: Некоторые сообщения могут не удаляться из-за:")
        print(f"  • Сообщения уже удалены пользователями")
        print(f"  • Сообщения слишком старые (более 48 часов)")
        print(f"  • Пользователи заблокировали бота")
        
    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}", exc_info=True)
        print(f"❌ Критическая ошибка: {e}")
    finally:
        # Закрываем сессию бота
        try:
            await bot.session.close()
        except:
            pass

if __name__ == "__main__":
    print("🗑️  Скрипт удаления сообщений рассылки")
    print("=" * 70)
    asyncio.run(main())