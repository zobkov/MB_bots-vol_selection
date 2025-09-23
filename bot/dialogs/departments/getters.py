from aiogram_dialog import DialogManager


async def get_rating_options(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для выбора рейтинга"""
    ratings = [
        {"id": "1", "text": "1"},
        {"id": "2", "text": "2"},
        {"id": "3", "text": "3"},
        {"id": "4", "text": "4"},
        {"id": "5", "text": "5"},
    ]
    
    return {"ratings": ratings}


async def get_logistics_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Логистика"
    return result


async def get_marketing_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Маркетинг"
    return result


async def get_pr_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "PR"
    return result


async def get_program_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Программа"
    return result


async def get_partners_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Партнеры"
    return result


async def get_dept_overview_data(dialog_manager: DialogManager, **kwargs):
    data = dialog_manager.dialog_data
    
    overview_text = f"""📊 Ваши оценки отделов:

• Логистика: {data.get('logistics_rating', 'Не указано')}
• Маркетинг: {data.get('marketing_rating', 'Не указано')}
• PR: {data.get('pr_rating', 'Не указано')}
• Программа: {data.get('program_rating', 'Не указано')}
• Партнеры: {data.get('partners_rating', 'Не указано')}

Проверьте свои оценки и нажмите "Продолжить" для завершения или "Изменить" для корректировки."""

    return {"overview_text": overview_text}