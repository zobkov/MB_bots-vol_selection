from aiogram_dialog import DialogManager


async def get_yes_no_options(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для выбора Да/Нет"""
    options = [
        {"id": "yes", "text": "Да"},
        {"id": "no", "text": "Нет"},
    ]
    
    return {"options": options}


async def get_dormitory_options(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для выбора общежития"""
    options = [
        {"id": "yes", "text": "Да"},
        {"id": "no", "text": "Нет"},
    ]
    
    return {"dormitory_options": options}


async def get_course_options(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для выбора курса"""
    courses = [
        {"id": "1_bachelor", "text": "1 курс бакалавриат"},
        {"id": "2_bachelor", "text": "2 курс бакалавриат"},
        {"id": "3_bachelor", "text": "3 курс бакалавриат"},
        {"id": "4_bachelor", "text": "4 курс бакалавриат"},
        {"id": "1_master", "text": "1 курс магистратура"},
        {"id": "2_master", "text": "2 курс магистратура"},
    ]
    
    return {"courses": courses}


async def get_overview_data(dialog_manager: DialogManager, **kwargs):
    data = dialog_manager.dialog_data
    
    # Безопасно получаем значение общежития
    dormitory_value = data.get("dormitory")
    dormitory_text = "Да" if dormitory_value == "yes" else "Нет"
    vsm_text = "Да" if data.get("is_from_vsm") else "Нет"
    spbu_text = "Да" if data.get("is_from_spbu") else "Нет"
    
    # Показываем общежитие только если ИЗ ВШМ
    is_from_vsm = data.get("is_from_vsm", False)
    dormitory_line = f"🏠 Общежитие: {dormitory_text}\n" if is_from_vsm else ""
    
    overview_text = f"""📋 Проверьте введенные данные:

👤 ФИО: {data.get('full_name', 'Не указано')}
🎓 Курс: {data.get('course_display', 'Не указан')}
🏛️ Из ВШМ: {vsm_text}
🎓 Из СПбГУ: {spbu_text}
🏫 ВУЗ: {data.get('university', 'Не указан')}
{dormitory_line}📧 Email: {data.get('email', 'Не указан')}
📱 Телефон: {data.get('phone', 'Не указан')}

🌸 Личные качества:
{data.get('personal_qualities', 'Не указано')}

🌟 Мотивация:
{data.get('motivation', 'Не указано')}

📊 Оценки отделов:
• Логистика: {data.get('logistics_rating', 'Не указано')}
• Маркетинг: {data.get('marketing_rating', 'Не указано')}
• PR: {data.get('pr_rating', 'Не указано')}
• Программа: {data.get('program_rating', 'Не указано')}
• Партнеры: {data.get('partners_rating', 'Не указано')}"""

    return {"overview_text": overview_text}


async def get_edit_menu_data(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для меню изменения заявки"""
    data = dialog_manager.dialog_data
    is_from_vsm = data.get("is_from_vsm", False)
    
    # Сбрасываем флаг редактирования при входе в меню
    dialog_manager.dialog_data["is_editing"] = False
    
    return {
        "show_dormitory_edit": is_from_vsm  # Показываем редактирование общежития только если ИЗ ВШМ
    }