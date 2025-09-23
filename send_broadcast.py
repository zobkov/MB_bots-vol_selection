import asyncio
import logging
from typing import List
from aiogram import Bot
from config.config import load_config
from database.db import Database
from database.repositories import UserRepository
from sqlalchemy import select
from database.models import User

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BroadcastService:
    """Сервис для массовой рассылки сообщений"""
    
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        
    async def get_stage1_users(self) -> List[User]:
        """Получить всех пользователей, которые завершили первый этап"""
        session = await self.db.get_session()
        try:
            result = await session.execute(
                select(User).where(
                    User.stage1_submitted == "submitted",
                    User.is_alive == True,
                    User.is_blocked == False
                )
            )
            users = result.scalars().all()
            logger.info(f"Найдено {len(users)} пользователей для рассылки")
            return list(users)
        finally:
            await session.close()
    
    async def send_message_to_user(self, user: User, message_text: str) -> bool:
        """Отправить сообщение одному пользователю"""
        try:
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message_text,
                parse_mode='HTML'
            )
            logger.info(f"✅ Сообщение отправлено пользователю {user.telegram_id} (@{user.telegram_username})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {user.telegram_id} (@{user.telegram_username}): {e}")
            
            # Если пользователь заблокировал бота - помечаем его как заблокированного
            if "bot was blocked by the user" in str(e).lower():
                await self._mark_user_blocked(user.telegram_id)
            
            return False
    
    async def _mark_user_blocked(self, telegram_id: int):
        """Пометить пользователя как заблокировавшего бота"""
        session = await self.db.get_session()
        try:
            user_repo = UserRepository(session)
            # Используем существующий метод update или создаем новый
            from sqlalchemy import update
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(is_blocked=True)
            )
            await session.commit()
            logger.info(f"Пользователь {telegram_id} помечен как заблокированный")
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса блокировки для {telegram_id}: {e}")
        finally:
            await session.close()
    
    async def broadcast_to_stage1_users(self, message_text: str, delay: float = 0.1) -> dict:
        """
        Отправить сообщение всем пользователям первого этапа
        
        Args:
            message_text: Текст сообщения для отправки
            delay: Задержка между отправками (в секундах) для избежания rate limit
            
        Returns:
            dict: Статистика рассылки
        """
        users = await self.get_stage1_users()
        
        if not users:
            logger.warning("Нет пользователей для рассылки")
            return {"total": 0, "sent": 0, "failed": 0}
        
        stats = {"total": len(users), "sent": 0, "failed": 0}
        
        logger.info(f"Начинаем рассылку для {stats['total']} пользователей...")
        
        for i, user in enumerate(users, 1):
            success = await self.send_message_to_user(user, message_text)
            
            if success:
                stats["sent"] += 1
            else:
                stats["failed"] += 1
            
            # Прогресс каждые 10 пользователей
            if i % 10 == 0:
                logger.info(f"Прогресс: {i}/{stats['total']} ({stats['sent']} успешно, {stats['failed']} ошибок)")
            
            # Задержка между отправками
            if delay > 0:
                await asyncio.sleep(delay)
        
        logger.info(f"Рассылка завершена. Отправлено: {stats['sent']}, ошибок: {stats['failed']}")
        return stats

async def main():
    """Основная функция для запуска рассылки"""
    
    # Текст сообщения для рассылки - ИЗМЕНИТЕ ПО НЕОБХОДИМОСТИ
    MESSAGE_TEXT = """<b>Привет!</b>

Приносим извинения за задержку результатов.🙏 Они придут всем в скором времени. 
А пока просим не отписываться от бота, чтобы не пропустить следующий этап отбора🤍

Спасибо за понимание,
Организаторы МБ'25"""

    try:
        # Загружаем конфигурацию
        config = load_config()
        
        # Создаем подключения
        bot = Bot(token=config.tg_bot.token)
        db = Database(config)
        
        # Создаем сервис рассылки
        broadcast_service = BroadcastService(bot, db)
        
        # Подтверждение перед отправкой
        print("📝 Текст сообщения для рассылки:")
        print("-" * 50)
        print(MESSAGE_TEXT)
        print("-" * 50)
        
        users = await broadcast_service.get_stage1_users()
        print(f"\n👥 Найдено пользователей для рассылки: {len(users)}")
        
        if len(users) == 0:
            print("❌ Нет пользователей для рассылки")
            return
        
        # Показываем несколько примеров пользователей
        print("\n📋 Примеры пользователей (первые 5):")
        for user in users[:5]:
            print(f"  - {user.telegram_id} (@{user.telegram_username or 'no_username'})")
        if len(users) > 5:
            print(f"  ... и еще {len(users) - 5} пользователей")
        
        confirm = input(f"\n❓ Отправить сообщение {len(users)} пользователям? (y/N): ")
        
        if confirm.lower() != 'y':
            print("❌ Рассылка отменена")
            return
        
        # Запускаем рассылку
        print("\n🚀 Запускаем рассылку...")
        stats = await broadcast_service.broadcast_to_stage1_users(
            MESSAGE_TEXT, 
            delay=0.1  # 100ms между сообщениями
        )
        
        print(f"\n✅ Рассылка завершена!")
        print(f"📊 Статистика:")
        print(f"  • Всего пользователей: {stats['total']}")
        print(f"  • Успешно отправлено: {stats['sent']}")
        print(f"  • Ошибок: {stats['failed']}")
        
        if stats['failed'] > 0:
            print(f"\n⚠️  Пользователи с ошибками помечены как заблокированные (если заблокировали бота)")
        
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
    print("🤖 Скрипт рассылки для волонтеров МБ 2025")
    print("=" * 50)
    asyncio.run(main())