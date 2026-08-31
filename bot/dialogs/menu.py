from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from bot.states import MenuSG, ApplicationSG
from database.db import Database
from database.repositories import UserRepository
from utils.emojis import emoji


async def get_menu_data(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для главного меню"""
    db: Database = dialog_manager.middleware_data.get("db")
    user = dialog_manager.event.from_user
    
    is_submitted = False
    if db and user:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_or_create_user(
                telegram_id=user.id,
                telegram_username=user.username
            )
            is_submitted = (db_user.status == "submitted")
        finally:
            await session.close()
    
    status_text = "<b>Заявка подана</b>" if is_submitted else "<b>Заявка не подана</b>"
    
    menu_text = (
        f'{emoji("earth")} <b>Личный кабинет кандидата в команду волонтеров МБ</b>\n\n'
        f'{emoji("arrow_right")} Сбор заявок открыт до <b>21 сентября 23:59</b>\n\n'
        f'📝 Статус заявки: {status_text}'
    )
    
    return {
        "menu_text": menu_text,
        "is_submitted": is_submitted
    }


menu_dialog = Dialog(
    Window(
        Format("{menu_text}"),
        Start(
            Const("📝 Заполнить анкету"),
            id="start_app_from_menu",
            state=ApplicationSG.full_name,
            when=lambda data, widget, manager: not data.get("is_submitted", False)
        ),
        SwitchTo(
            Const("📞 Поддержка"),
            id="to_support",
            state=MenuSG.support
        ),
        state=MenuSG.main,
        getter=get_menu_data,
    ),
    Window(
        Const("С нами можно связаться через аккаунт поддержки: @mbconf_support"),
        SwitchTo(
            Const("🔙 Назад"),
            id="back_to_menu",
            state=MenuSG.main
        ),
        state=MenuSG.support,
    ),
)
