"""
Утилиты для работы с медиа в универсальных тестах
"""
import logging
import os
from typing import List, Optional
from aiogram import Bot
from aiogram.types import FSInputFile, Message
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram_dialog import DialogManager

logger = logging.getLogger(__name__)


class MediaHandler:
    """Класс для работы с медиа в тестах"""
    
    @staticmethod
    async def send_test_images(dialog_manager: DialogManager, image_paths: List[str], caption: str = "") -> Optional[List[int]]:
        """
        Отправляет изображения в чат и возвращает список message_id для последующего удаления
        
        Args:
            dialog_manager: Менеджер диалога
            image_paths: Список путей к изображениям относительно корня проекта
            caption: Подпись к альбому
            
        Returns:
            Список message_id отправленных сообщений или None при ошибке
        """
        try:
            # Получаем бота из middleware
            bot: Bot = dialog_manager.middleware_data.get("bot")
            if not bot:
                logger.error("Bot not found in middleware_data")
                return None
            
            # Получаем chat_id из события
            chat_id = dialog_manager.event.from_user.id
            
            # Проверяем существование файлов
            for image_path in image_paths:
                if not os.path.exists(image_path):
                    logger.error(f"Image file not found: {image_path}")
                    return None
            
            # Создаем MediaGroup
            album_builder = MediaGroupBuilder(caption=caption)
            for image_path in image_paths:
                album_builder.add_photo(media=FSInputFile(image_path))
            
            # Отправляем альбом
            messages = await bot.send_media_group(
                chat_id=chat_id,
                media=album_builder.build()
            )
            
            # Извлекаем message_id из отправленных сообщений
            message_ids = [msg.message_id for msg in messages]
            
            logger.info(f"Sent {len(messages)} images to chat {chat_id}, message_ids: {message_ids}")
            return message_ids
            
        except Exception as e:
            logger.error(f"Error sending test images: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def delete_test_images(dialog_manager: DialogManager, message_ids: List[int]) -> bool:
        """
        Удаляет отправленные ранее изображения
        
        Args:
            dialog_manager: Менеджер диалога
            message_ids: Список message_id для удаления
            
        Returns:
            True если удаление прошло успешно, False при ошибке
        """
        try:
            # Получаем бота из middleware
            bot: Bot = dialog_manager.middleware_data.get("bot")
            if not bot:
                logger.error("Bot not found in middleware_data")
                return False
            
            # Получаем chat_id из события
            chat_id = dialog_manager.event.from_user.id
            
            # Удаляем сообщения
            deleted_count = 0
            for message_id in message_ids:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete message {message_id}: {e}")
            
            logger.info(f"Successfully deleted {deleted_count}/{len(message_ids)} messages from chat {chat_id}")
            return deleted_count == len(message_ids)
            
        except Exception as e:
            logger.error(f"Error deleting test images: {e}", exc_info=True)
            return False
    
    @staticmethod
    def get_general_questions_images() -> List[str]:
        """Возвращает пути к изображениям для общих вопросов"""
        base_path = "/Users/artyomzobkov/vol_selection_MB_bot"
        return [
            os.path.join(base_path, "bot", "assets", "images", "first_floor.jpeg"),
            os.path.join(base_path, "bot", "assets", "images", "second_floor.jpeg")
        ]


# Константы для ключей в dialog_data
MEDIA_MESSAGE_IDS_KEY = "test_media_message_ids"
MEDIA_SENT_KEY = "test_media_sent"