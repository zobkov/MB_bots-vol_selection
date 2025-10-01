from aiogram_dialog import DialogManager
from config.config import Config
from database.repositories import UserRepository
from database.db import Database


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
        
        # Формируем статус заявки первого этапа
        stage1_status_text = "Заявка подана" if is_stage1_submitted else "Заявка не подана"
        if is_stage1_submitted:
            # Если заявка подана - показываем когда придут результаты
            stage1_additional_info = f"\n📊 Результаты придут: {config.selection.stages['stage1']['results_date']}"
        else:
            # Если заявка не подана - показываем дедлайн
            stage1_additional_info = f"\n⏰ Дедлайн: {config.selection.stages['stage1']['deadline']}"
        
        # Определяем какие кнопки показывать
        show_application_button = not is_stage1_submitted
        show_testing_button = is_stage1_submitted  # Показываем кнопку тестирования после подачи анкеты
        
    finally:
        await session.close()
    
    menu_text = f"""🏠 Личный кабинет кандидата в команду волонтеров МБ 2025

📅 Отбор завершен!

📝 Статус заявки: {stage1_status_text}

Результаты тестирования: <b>06.10.2025</b>"""

    return {
        "menu_text": menu_text,
        "show_application_button": show_application_button,
        "show_testing_button": show_testing_button
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