#!/usr/bin/env python3
"""
Скрипт для рассылки результатов отбора волонтеров МБ 2025
Включает обязательное подтверждение, драй-ран и тестовый режим
"""

import asyncio
import logging
import csv
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.config import load_config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Volunteer:
    """Класс для хранения данных волонтера"""
    full_name: str
    username: str
    user_id: int
    department: str

@dataclass
class SentMessage:
    """Класс для хранения информации об отправленном сообщении"""
    message_id: int
    chat_id: int
    volunteer: Volunteer
    sent_at: str

# Файл для сохранения отправленных сообщений
SENT_MESSAGES_FILE = "sent_messages_broadcast.json"

class SelectionResultsBroadcastService:
    """Сервис для рассылки результатов отбора волонтеров"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.sent_messages: List[SentMessage] = []
        
    def create_response_keyboard(self) -> InlineKeyboardMarkup:
        """Создает клавиатуру с кнопками ответа"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Нет, не смогу",
                    callback_data="decline_participation"
                )
            ]
        ])
        return keyboard
    
    def save_sent_messages(self):
        """Сохраняет список отправленных сообщений в файл"""
        try:
            # Конвертируем в формат для JSON
            messages_data = []
            for msg in self.sent_messages:
                messages_data.append({
                    "message_id": msg.message_id,
                    "chat_id": msg.chat_id,
                    "volunteer": asdict(msg.volunteer),
                    "sent_at": msg.sent_at
                })
            
            with open(SENT_MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(messages_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Сохранено {len(messages_data)} сообщений в {SENT_MESSAGES_FILE}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщений: {e}")
    
    def format_message(self, volunteer: Volunteer, message_template: str) -> str:
        """
        Форматирует сообщение с подстановкой данных волонтера
        
        Args:
            volunteer: Данные волонтера
            message_template: Шаблон сообщения
            
        Returns:
            str: Отформатированное сообщение
        """
        return message_template.format(
            department=volunteer.department,
            full_name=volunteer.full_name,
            username=volunteer.username
        )
        
    async def load_volunteers_from_csv(self, csv_file_path: str) -> List[Volunteer]:
        """
        Загружает список волонтеров из CSV файла
        
        Args:
            csv_file_path: Путь к CSV файлу
            
        Returns:
            List[Volunteer]: Список волонтеров
        """
        volunteers = []
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        volunteer = Volunteer(
                            full_name=row['full_name'].strip(),
                            username=row['username'].strip(),
                            user_id=int(row['user_id']),
                            department=row['department'].strip()
                        )
                        
                        if volunteer.user_id > 0:
                            volunteers.append(volunteer)
                        else:
                            logger.warning(f"Некорректный user_id в строке {row_num}: {volunteer.user_id}")
                            
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Пропускаем некорректную строку {row_num}: {row}, ошибка: {e}")
                        
            logger.info(f"Загружено {len(volunteers)} волонтеров из CSV")
            return volunteers
            
        except Exception as e:
            logger.error(f"Ошибка при чтении CSV файла: {e}")
            return []
    
    def get_volunteers_by_department(self, volunteers: List[Volunteer]) -> Dict[str, List[Volunteer]]:
        """Группирует волонтеров по департаментам"""
        departments = {}
        for volunteer in volunteers:
            if volunteer.department not in departments:
                departments[volunteer.department] = []
            departments[volunteer.department].append(volunteer)
        return departments
    
    async def send_message_to_volunteer(
        self, 
        volunteer: Volunteer, 
        message_text: str, 
        dry_run: bool = False
    ) -> bool:
        """
        Отправить сообщение одному волонтеру
        
        Args:
            volunteer: Данные волонтера
            message_text: Текст сообщения
            dry_run: Режим драй-рана (не отправлять реально)
            
        Returns:
            bool: Успешность отправки
        """
        if dry_run:
            logger.info(f"[DRY RUN] Сообщение волонтеру {volunteer.full_name} ({volunteer.user_id})")
            return True
            
        try:
            keyboard = self.create_response_keyboard()
            
            message = await self.bot.send_message(
                chat_id=volunteer.user_id,
                text=message_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            
            # Сохраняем информацию об отправленном сообщении
            sent_message = SentMessage(
                message_id=message.message_id,
                chat_id=volunteer.user_id,
                volunteer=volunteer,
                sent_at=datetime.now().isoformat()
            )
            self.sent_messages.append(sent_message)
            
            logger.info(f"✅ Сообщение отправлено волонтеру {volunteer.full_name} ({volunteer.user_id})")
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "bot was blocked by the user" in error_msg:
                logger.warning(f"⚠️  Волонтер {volunteer.full_name} ({volunteer.user_id}) заблокировал бота")
            elif "user not found" in error_msg:
                logger.warning(f"⚠️  Волонтер {volunteer.full_name} ({volunteer.user_id}) не найден")
            elif "chat not found" in error_msg:
                logger.warning(f"⚠️  Чат с волонтером {volunteer.full_name} ({volunteer.user_id}) не найден")
            else:
                logger.error(f"❌ Ошибка отправки волонтеру {volunteer.full_name} ({volunteer.user_id}): {e}")
            
            return False

    async def broadcast_to_volunteers(
        self, 
        volunteers: List[Volunteer], 
        message_template: str, 
        delay: float = 0.1,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Отправить сообщения списку волонтеров
        
        Args:
            volunteers: Список волонтеров
            message_template: Шаблон сообщения
            delay: Задержка между отправками (в секундах)
            dry_run: Режим драй-рана
            
        Returns:
            dict: Статистика рассылки
        """
        if not volunteers:
            logger.warning("Нет волонтеров для рассылки")
            return {"total": 0, "sent": 0, "failed": 0}
        
        stats = {
            "total": len(volunteers), 
            "sent": 0, 
            "failed": 0
        }
        
        mode_text = "[DRY RUN] " if dry_run else ""
        logger.info(f"{mode_text}Начинаем рассылку для {stats['total']} волонтеров...")
        
        for i, volunteer in enumerate(volunteers, 1):
            # Форматируем сообщение для каждого волонтера
            formatted_message = self.format_message(volunteer, message_template)
            
            success = await self.send_message_to_volunteer(volunteer, formatted_message, dry_run)
            
            if success:
                stats["sent"] += 1
            else:
                stats["failed"] += 1
            
            # Прогресс каждые 5 волонтеров
            if i % 5 == 0:
                logger.info(f"{mode_text}Прогресс: {i}/{stats['total']} ({stats['sent']} успешно, {stats['failed']} ошибок)")
            
            # Задержка между отправками (не для драй-рана)
            if delay > 0 and not dry_run:
                await asyncio.sleep(delay)
        
        logger.info(f"{mode_text}Рассылка завершена. Отправлено: {stats['sent']}, ошибок: {stats['failed']}")
        
        # Сохраняем отправленные сообщения (только для реальной отправки)
        if not dry_run and stats['sent'] > 0:
            self.save_sent_messages()
            
        return stats

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

def display_volunteers_preview(volunteers: List[Volunteer], max_display: int = 10):
    """Показывает превью списка волонтеров"""
    print(f"\n👥 Список волонтеров (показано {min(len(volunteers), max_display)} из {len(volunteers)}):")
    
    for i, volunteer in enumerate(volunteers[:max_display]):
        print(f"  {i+1}. {volunteer.full_name} (@{volunteer.username}) - {volunteer.department} - ID: {volunteer.user_id}")
    
    if len(volunteers) > max_display:
        print(f"  ... и еще {len(volunteers) - max_display} волонтеров")

def display_department_stats(volunteers_by_dept: Dict[str, List[Volunteer]]):
    """Показывает статистику по департаментам"""
    print(f"\n📊 Статистика по департаментам:")
    total = 0
    for dept, vol_list in volunteers_by_dept.items():
        count = len(vol_list)
        total += count
        print(f"  • {dept}: {count} волонтеров")
    print(f"  • Всего: {total} волонтеров")

async def main():
    """Основная функция для запуска рассылки результатов отбора"""
    
    # Путь к CSV файлу
    csv_file_path = "/Users/artyomzobkov/vol_selection_MB_bot/list_for_broadcast.csv"
    
    # Тестовые пользователи
    TEST_USER_IDS = [257026813,866915193]
    
    # Шаблон сообщения для рассылки
    message_template = """Привет! 
Поздравляем с успешным прохождением отбора на "Менеджмент Будущего 2025"!

Мы будем счастливы видеть тебя в составе отдела <b>{department}</b> 🥰

Если ты готов(-а) принимать участие в волонтерстве на Конференции 23-25 октября, переходи в общий чат по <a href="https://t.me/+EkQtedyGdNY0Y2My">ссылке</a> до 12.00 8 октября.

Если ты понимаешь, что не сможешь помогать в эти даты, жми на кнопку "нет"😔

Если у тебя возникли вопросы, самое время задать их Даше @drkirna"""
    
    polling_task = None
    
    try:
        print("🎉 Рассылка результатов отбора волонтеров МБ 2025")
        print("=" * 70)
        
        # Загружаем конфигурацию
        config = load_config()
        
        # Создаем бота
        bot = Bot(token=config.tg_bot.token)
        
        # Создаем сервис рассылки
        broadcast_service = SelectionResultsBroadcastService(bot)
        
        print(f"📁 CSV файл: {csv_file_path}")
        
        # Проверяем существование файла
        if not os.path.exists(csv_file_path):
            print(f"❌ CSV файл не найден: {csv_file_path}")
            return
        
        # Загружаем волонтеров из CSV
        all_volunteers = await broadcast_service.load_volunteers_from_csv(csv_file_path)
        
        if not all_volunteers:
            print("❌ Не удалось загрузить волонтеров из CSV файла")
            return
        
        # Группируем по департаментам
        volunteers_by_dept = broadcast_service.get_volunteers_by_department(all_volunteers)
        
        # Показываем статистику
        display_department_stats(volunteers_by_dept)
        display_volunteers_preview(all_volunteers)
        
        print(f"\n📝 Шаблон сообщения:")
        print("-" * 50)
        print(message_template)
        print("-" * 50)
        
        # Выбор режима рассылки
        print("\n🚀 Выберите режим рассылки:")
        print("1. Драй-ран (проверка без отправки)")
        print("2. Тестовая отправка (только тестовым пользователям)")
        print("3. Полная рассылка (всем волонтерам)")
        
        while True:
            choice = input("\nВведите номер (1, 2 или 3): ").strip()
            if choice in ['1', '2', '3']:
                choice = int(choice)
                break
            print("❌ Неверный выбор. Введите 1, 2 или 3.")
        
        if choice == 1:
            # Драй-ран режим
            print(f"\n🧪 Режим драй-рана (проверка без отправки)")
            print(f"📊 Будет проверено {len(all_volunteers)} волонтеров")
            
            if not get_user_confirmation("Запустить драй-ран?"):
                print("❌ Драй-ран отменен")
                return
            
            print(f"\n🔍 Запускаем драй-ран...")
            stats = await broadcast_service.broadcast_to_volunteers(
                all_volunteers, 
                message_template,
                delay=0,  # Без задержки в драй-ране
                dry_run=True
            )
            
            print(f"\n✅ Драй-ран завершен!")
            print(f"📊 Результаты проверки:")
            print(f"  • Всего волонтеров: {stats['total']}")
            print(f"  • Прошли проверку: {stats['sent']}")
            print(f"  • Ошибки: {stats['failed']}")
            
        elif choice == 2:
            # Тестовая отправка
            test_volunteers = [v for v in all_volunteers if v.user_id in TEST_USER_IDS]
            
            if not test_volunteers:
                print(f"❌ Тестовые пользователи {TEST_USER_IDS} не найдены в списке волонтеров")
                return
            
            print(f"\n🧪 Тестовая отправка")
            print(f"👥 Тестовые пользователи:")
            for volunteer in test_volunteers:
                print(f"  • {volunteer.full_name} ({volunteer.user_id}) - {volunteer.department}")
            
            if not get_user_confirmation(f"Отправить сообщения {len(test_volunteers)} тестовым пользователям?"):
                print("❌ Тестовая отправка отменена")
                return
            
            print(f"\n🚀 Отправляем тестовые сообщения...")
            stats = await broadcast_service.broadcast_to_volunteers(
                test_volunteers, 
                message_template,
                delay=0.1
            )
            
            print(f"\n✅ Тестовая отправка завершена!")
            print(f"📊 Результаты:")
            print(f"  • Отправлено: {stats['sent']}")
            print(f"  • Ошибок: {stats['failed']}")
            
        else:
            # Полная рассылка
            print(f"\n📢 Полная рассылка всем волонтерам")
            print(f"👥 Всего волонтеров: {len(all_volunteers)}")
            print(f"⏱️  Задержка между отправками: 0.1 секунды")
            print(f"⏰ Примерное время выполнения: {len(all_volunteers) * 0.1 / 60:.1f} минут")
            
            # Двойное подтверждение для полной рассылки
            print(f"\n⚠️  ВНИМАНИЕ: Вы собираетесь отправить сообщения {len(all_volunteers)} волонтерам!")
            
            if not get_user_confirmation("Вы уверены, что хотите запустить полную рассылку?"):
                print("❌ Полная рассылка отменена")
                return
            
            print(f"\n🚨 ПОСЛЕДНЕЕ ПОДТВЕРЖДЕНИЕ:")
            if not get_user_confirmation(f"ОТПРАВИТЬ СООБЩЕНИЯ {len(all_volunteers)} ВОЛОНТЕРАМ? ЭТО ДЕЙСТВИЕ НЕЛЬЗЯ ОТМЕНИТЬ!"):
                print("❌ Полная рассылка отменена")
                return
            
            print(f"\n🚀 Запускаем полную рассылку...")
            stats = await broadcast_service.broadcast_to_volunteers(
                all_volunteers, 
                message_template,
                delay=0.1
            )
            
            print(f"\n✅ Полная рассылка завершена!")
            print(f"📊 Итоговая статистика:")
            print(f"  • Всего волонтеров: {stats['total']}")
            print(f"  • Успешно отправлено: {stats['sent']}")
            print(f"  • Ошибок: {stats['failed']}")
            
            if stats['failed'] > 0:
                success_rate = (stats['sent'] / stats['total']) * 100
                print(f"  • Процент успешности: {success_rate:.1f}%")
            
            print(f"\n💡 Примечание: Ошибки могут возникать из-за:")
            print(f"  • Пользователи заблокировали бота")
            print(f"  • Неактивные аккаунты")
            print(f"  • Некорректные user_id")
            
        # Информация о том, что callback'и обрабатывает основной бот
        if choice != 1:
            print(f"\n🤖 Основной бот будет обрабатывать ответы волонтеров...")
            print(f"💾 Отправленные сообщения сохранены в файл: {SENT_MESSAGES_FILE}")
            print(f"📧 Уведомления об отказах будут отправляться основным ботом")
        
    except KeyboardInterrupt:
        print(f"\n🛑 Получен сигнал остановки...")
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
    print("🎉 Скрипт рассылки результатов отбора волонтеров МБ 2025")
    print("=" * 70)
    asyncio.run(main())