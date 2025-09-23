from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from bot.states import StartSG, MenuSG
from database.repositories import UserRepository
from database.db import Database

router = Router()


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
