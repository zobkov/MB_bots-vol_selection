from aiogram import types
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from config.config import Config
from database.repositories import UserRepository
from database.db import Database

from bot.states import *


async def get_menu_data(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для главного меню"""
    # Получаем конфигурацию
    config: Config = dialog_manager.middleware_data.get("config")
    db: Database = dialog_manager.middleware_data.get("db")
    
    # Получаем информацию о пользователе
    user = dialog_manager.event.from_user
    
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        # Создаем/получаем пользователя (дополнительная защита)
        db_user = await user_repo.get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username
        )
        
        is_stage1_submitted = db_user.stage1_submitted == "submitted"
        is_stage2_submitted = db_user.stage2_submitted
        
        # Формируем статус заявки первого этапа
        stage1_status_text = "Заявка подана" if is_stage1_submitted else "Заявка не подана"
        if is_stage1_submitted:
            # Если заявка подана - показываем когда придут результаты
            stage1_additional_info = f"\n📊 Результаты придут: {config.selection.stages['stage1']['results_date']}"
        else:
            # Если заявка не подана - показываем дедлайн
            stage1_additional_info = f"\n⏰ Дедлайн: {config.selection.stages['stage1']['deadline']}"
        
        # Формируем статус второго этапа
        stage2_status_text = "Тестирование завершено" if is_stage2_submitted else "Тестирование не пройдено"
        
        # Определяем доступность кнопки второго этапа
        stage2_available = not is_stage2_submitted
        
    finally:
        await session.close()
    
    menu_text = f"""🏠 Личный кабинет кандидата в команду волонтеров МБ 2025 - тест второго этапа

📅 Первый этап: Анкетирование
📝 Статус заявки: {stage1_status_text}

📋 Второй этап: Тестирование
⏰ Дедлайн: 25 октября
📝 Статус: {stage2_status_text}"""

    return {
        "menu_text": menu_text,
        "stage2_available": stage2_available,
        "stage2_completed": is_stage2_submitted
    }


async def get_support_data(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для поддержки"""
    config: Config = dialog_manager.middleware_data.get("config")
    
    support_text = "📞 Контакты для связи:\n\n"
    for key, contact in config.selection.support_contacts.items():
        if key == "main":
            support_text += f"🔹 Основные вопросы: {contact}\n"
        elif key == "technical":
            support_text += f"🔹 Технические вопросы: {contact}\n"
        else:
            support_text += f"🔹 {key.title()}: {contact}\n"
    
    return {
        "support_text": support_text
    }


menu_dialog = Dialog(
    Window(
        Format("{menu_text}"),
        Start(
            Const("📝 Перейти ко второму этапу"),
            id="fill_application",
            state=Stage2SG.start,
            when="stage2_available"
        ),
        Format(
            "\n✅ <b>Второй этап завершен!</b>\nПовторное прохождение недоступно.",
            when="stage2_completed"
        ),
        SwitchTo(
            Const("📞 Поддержка"),
            id="support",
            state=MenuSG.support
        ),
        state=MenuSG.main,
        getter=get_menu_data,
    ),
    Window(
        Format("{support_text}"),
        SwitchTo(
            Const("🔙 Назад в меню"),
            id="back_to_menu",
            state=MenuSG.main
        ),
        state=MenuSG.support,
        getter=get_support_data,
    ),
)
