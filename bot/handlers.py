from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram_dialog import DialogManager, StartMode
import logging
import json
import os
from datetime import datetime

from bot.states import StartSG, MenuSG
from database.repositories import UserRepository
from database.db import Database

router = Router()
logger = logging.getLogger(__name__)

# ID администраторов для уведомлений об отказах
ADMIN_IDS = [721299210,257026813] # 721299210,

# Файл для поиска данных о волонтерах
SENT_MESSAGES_FILE = "sent_messages_broadcast.json"


@router.message(Command("start"))
async def cmd_start(message: Message, dialog_manager: DialogManager):
    """Обработчик команды /start"""
    # Получаем базу данных из middleware
    db: Database = dialog_manager.middleware_data.get("db")
    
    # Создаем/получаем пользователя при первом запуске
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        await user_repo.get_or_create_user(
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.username
        )
    finally:
        await session.close()
    
    await dialog_manager.start(StartSG.start, mode=StartMode.RESET_STACK)


@router.message(Command("menu"))
async def cmd_menu(message: Message, dialog_manager: DialogManager):
    """Обработчик команды /menu"""
    # Получаем базу данных из middleware
    db: Database = dialog_manager.middleware_data.get("db")
    
    # Создаем/получаем пользователя
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        await user_repo.get_or_create_user(
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.username
        )
    finally:
        await session.close()
    
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)

@router.message(Command("test"))
async def cmd_test(message: Message, dialog_manager: DialogManager):
    """Обработчик команды /test"""
    # Получаем базу данных из middleware
    db: Database = dialog_manager.middleware_data.get("db")
    
    # Создаем/получаем пользователя
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        await user_repo.get_or_create_user(
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.username
        )
    finally:
        await session.close()
    
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


@router.callback_query(F.data == "decline_participation")
async def handle_decline_participation(callback_query: CallbackQuery):
    """Обработчик отказа от участия в волонтерстве"""
    try:
        user_id = callback_query.from_user.id
        username = callback_query.from_user.username or "без_username"
        full_name = callback_query.from_user.full_name or "Неизвестно"
        
        logger.info(f"🔄 Начинаем обработку отказа от участия для пользователя {user_id} ({username})")
        
        # Пытаемся найти данные волонтера из файла отправленных сообщений
        volunteer_data = None
        department = "Неизвестный отдел"
        
        try:
            if os.path.exists(SENT_MESSAGES_FILE):
                logger.info(f"📁 Читаем файл {SENT_MESSAGES_FILE}")
                with open(SENT_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    sent_messages = json.load(f)
                
                # Ищем сообщение для этого пользователя
                for msg_data in sent_messages:
                    if msg_data.get('chat_id') == user_id:
                        volunteer = msg_data.get('volunteer', {})
                        full_name = volunteer.get('full_name', full_name)
                        username = volunteer.get('username', username)
                        department = volunteer.get('department', department)
                        logger.info(f"✅ Найдены данные волонтера: {full_name} ({username}) - {department}")
                        break
                else:
                    logger.warning(f"⚠️ Данные волонтера с ID {user_id} не найдены в файле")
            else:
                logger.warning(f"⚠️ Файл {SENT_MESSAGES_FILE} не существует")
        except Exception as e:
            logger.error(f"❌ Ошибка чтения файла {SENT_MESSAGES_FILE}: {e}")
        
        # Отправляем уведомление администраторам
        admin_message = f"Кандидат @{username} – {full_name} отклонил предложение в отдел {department}"
        logger.info(f"📧 Отправляем уведомления администраторам: {ADMIN_IDS}")
        
        # Получаем бота из callback_query
        bot = callback_query.bot
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_message
                )
                logger.info(f"✅ Уведомление об отказе отправлено администратору {admin_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления администратору {admin_id}: {e}")
        
        # Удаляем исходное сообщение с кнопкой
        try:
            logger.info(f"🗑️ Пытаемся удалить сообщение {callback_query.message.message_id} в чате {user_id}")
            await callback_query.message.delete()
            logger.info(f"✅ Сообщение рассылки успешно удалено для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось удалить сообщение для пользователя {user_id}: {e}")
            # Если не получилось удалить, редактируем сообщение
            try:
                logger.info(f"🔄 Пытаемся отредактировать сообщение вместо удаления")
                await callback_query.message.edit_text(
                    text="Сообщение обработано",
                    reply_markup=None
                )
                logger.info(f"✅ Сообщение отредактировано для пользователя {user_id}")
            except Exception as edit_error:
                logger.error(f"❌ Не удалось отредактировать сообщение: {edit_error}")
        
        # Отправляем новое сообщение пользователю
        decline_message = "Очень жаль, что у тебя не получится. Если передумаешь или есть вопросы, пиши @drkirna"
        
        try:
            logger.info(f"📤 Отправляем новое сообщение пользователю {user_id}")
            await bot.send_message(
                chat_id=user_id,
                text=decline_message
            )
            logger.info(f"✅ Новое сообщение об отказе отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки нового сообщения пользователю {user_id}: {e}")
        
        # Отвечаем на callback
        try:
            await callback_query.answer("Спасибо за ответ!")
            logger.info(f"✅ Callback answer отправлен пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки callback answer: {e}")
        
        logger.info(f"🎯 Обработка отказа завершена для пользователя {user_id} ({username}) из отдела {department}")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при обработке отказа от участия: {e}", exc_info=True)
        try:
            await callback_query.answer("Произошла ошибка, попробуйте еще раз")
        except:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке пользователю")
