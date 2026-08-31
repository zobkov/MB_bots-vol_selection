from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from bot.states import StartSG, ApplicationSG, MenuSG
from database.repositories import UserRepository
from database.db import Database

router = Router()


@router.message(Command("start", "menu"))
async def cmd_start_or_menu(message: Message, dialog_manager: DialogManager):
    """Единый обработчик команд /start и /menu с проверкой статуса заявки"""
    db: Database = dialog_manager.middleware_data.get("db")
    is_submitted = False
    
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
            )
            is_submitted = (db_user.status == "submitted")
        finally:
            await session.close()
    
    if is_submitted:
        await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)
    else:
        await dialog_manager.start(StartSG.welcome, mode=StartMode.RESET_STACK)


@router.message(Command("apply"))
async def cmd_apply(message: Message, dialog_manager: DialogManager):
    """Прямой запуск анкеты по команде /apply"""
    db: Database = dialog_manager.middleware_data.get("db")
    
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
            )
        finally:
            await session.close()
    
    await dialog_manager.start(ApplicationSG.full_name, mode=StartMode.RESET_STACK)

    """Прямой запуск анкеты по команде /apply"""
    db: Database = dialog_manager.middleware_data.get("db")
    
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
            )
        finally:
            await session.close()
    
    await dialog_manager.start(ApplicationSG.full_name, mode=StartMode.RESET_STACK)

