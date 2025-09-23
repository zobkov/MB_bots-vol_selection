from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode, ShowMode
from aiogram_dialog.widgets.kbd import Button

from bot.states import DepartmentSelectionSG, ApplicationSG, MenuSG
from database.repositories import UserRepository, ApplicationRepository
from database.db import Database
import re
import logging

logger = logging.getLogger(__name__)


# Валидация email
def email_check(text: str) -> str:
    # Проверяем корректность формата email с помощью регулярного выражения
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, text):
        raise ValueError("❌ Введите корректный email адрес")
    return text


# Валидация телефона
def phone_check(text: str) -> str:
    # Простая проверка что это похоже на номер телефона
    phone_digits = re.sub(r'[^\d]', '', text)
    if len(phone_digits) < 10:
        raise ValueError("❌ Введите корректный номер телефона")
    return text


# Обработка ввода ФИО
async def on_full_name_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    dialog_manager.dialog_data["full_name"] = text
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.next()


# Обработка ввода email
async def on_email_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    dialog_manager.dialog_data["email"] = text
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.next()


# Обработка ввода личных качеств
async def on_qualities_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    dialog_manager.dialog_data["personal_qualities"] = text
    
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        # Отправляем сообщение и сразу переходим к выбору отделов
        await message.answer(
            "📊 Теперь оцени свой интерес к каждому отделу от 1 до 5, "
            "где 1 - наименее интересный, 5 - очень хотелось бы попасть в этот отдел."
        )
        await dialog_manager.start(DepartmentSelectionSG.logistics)


# Обработка ввода мотивации
async def on_motivation_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    dialog_manager.dialog_data["motivation"] = text
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.next()


# Обработка ввода телефона
async def on_phone_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    dialog_manager.dialog_data["phone"] = text
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.next()


# Обработка контакта
async def on_contact_received(message: types.Message, widget, dialog_manager: DialogManager):
    if message.contact:
        dialog_manager.dialog_data["phone"] = message.contact.phone_number
        # Проверяем, находимся ли в режиме редактирования
        if dialog_manager.dialog_data.get("is_editing", False):
            await dialog_manager.switch_to(ApplicationSG.edit_menu)
        else:
            await dialog_manager.next()
    else:
        await message.answer("❌ Пожалуйста, поделитесь контактом через кнопку или введите номер текстом")


# Обработка выбора курса
async def on_course_selected(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    course_data = {
        "1_bachelor": "1 курс бакалавриат",
        "2_bachelor": "2 курс бакалавриат", 
        "3_bachelor": "3 курс бакалавриат",
        "4_bachelor": "4 курс бакалавриат",
        "1_master": "1 курс магистратура",
        "2_master": "2 курс магистратура"
    }
    
    dialog_manager.dialog_data["course"] = item_id
    dialog_manager.dialog_data["course_display"] = course_data[item_id]
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.next()


# Обработка выбора ВШМ
async def on_vsm_selected(callback: CallbackQuery, checkbox, dialog_manager: DialogManager, item_id: str):
    """Обработка выбора ВШМ"""
    # item_id теперь "yes" или "no"
    is_from_vsm = item_id == "yes"
    
    dialog_manager.dialog_data["is_from_vsm"] = is_from_vsm
    logger.debug(f"VSM selected: {is_from_vsm} (item_id: {item_id})")
    
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        if is_from_vsm:
            await dialog_manager.switch_to(ApplicationSG.dormitory)
        else:
            await dialog_manager.switch_to(ApplicationSG.is_from_spbu)


# Обработка выбора СПбГУ
async def on_spbu_selected(callback: CallbackQuery, checkbox, dialog_manager: DialogManager, item_id: str):
    """Обработка выбора СПбГУ"""
    is_from_spbu = item_id == "yes"
    
    dialog_manager.dialog_data["is_from_spbu"] = is_from_spbu
    
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        if is_from_spbu:
            await dialog_manager.switch_to(ApplicationSG.email)
        else:
            await dialog_manager.switch_to(ApplicationSG.university)


# Обработка ввода университета
async def on_university_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    university = text.strip()
    if not university:
        await message.answer("Пожалуйста, укажите название вашего университета.")
        return
    
    dialog_manager.dialog_data["university"] = university
    
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.switch_to(ApplicationSG.email)


# Обработка выбора общежития
async def on_dormitory_selected(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    dormitory_data = {
        "yes": "Да, нужно",
        "no": "Нет, не нужно"
    }
    
    dialog_manager.dialog_data["dormitory"] = item_id
    dialog_manager.dialog_data["dormitory_display"] = dormitory_data[item_id]
    
    # Проверяем, находимся ли в режиме редактирования
    if dialog_manager.dialog_data.get("is_editing", False):
        await dialog_manager.switch_to(ApplicationSG.edit_menu)
    else:
        await dialog_manager.next()


# Обработка завершения заполнения анкеты
async def on_submit_application(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    # Получаем данные
    data = dialog_manager.dialog_data
    user = dialog_manager.event.from_user
    db: Database = dialog_manager.middleware_data.get("db")
    google_sheets_service = dialog_manager.middleware_data.get("google_sheets_service")
    
    # Сохраняем в БД
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        app_repo = ApplicationRepository(session, google_sheets_service)
        
        # Получаем или создаем пользователя
        db_user = await user_repo.get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username
        )
        
        # Преобразуем dormitory из строки в bool, если значение есть
        dormitory_value = data.get("dormitory")
        dormitory_bool = None
        if dormitory_value == "yes":
            dormitory_bool = True
        elif dormitory_value == "no":
            dormitory_bool = False
        
        # Создаем заявку
        application_data = {
            "full_name": data["full_name"],
            "course": data["course"],
            "is_from_vsm": data.get("is_from_vsm"),
            "is_from_spbu": data.get("is_from_spbu"),
            "university": data.get("university"),
            "dormitory": dormitory_bool,  # Может быть True, False или None
            "email": data["email"],
            "phone": data["phone"],
            "personal_qualities": data["personal_qualities"],
            "motivation": data["motivation"],
            "logistics_rating": data["logistics_rating"],
            "marketing_rating": data["marketing_rating"],
            "pr_rating": data["pr_rating"],
            "program_rating": data["program_rating"],
            "partners_rating": data["partners_rating"],
        }
        
        # Дополнительные данные пользователя для Google Sheets
        user_telegram_data = {
            "telegram_id": user.id,
            "telegram_username": user.username or "",
        }
        
        await app_repo.create_application(db_user.id, application_data, user_telegram_data)
        
        # Обновляем статус пользователя
        await user_repo.update_stage1_status(user.id, "submitted")
    finally:
        await session.close()
    
    await callback.message.answer(
        "✅ Спасибо, что рассказал(а) о себе!\n"
        "Будем счастливы познакомиться вживую!"
        "\n\nЗа новостями следи в нашем телеграм-канале @managementfuture"
    )
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK, show_mode=ShowMode.DELETE_AND_SEND)


# Обработка возврата из диалога выбора отделов
async def on_departments_result(start_data, result, dialog_manager: DialogManager):
    """Обработка результата диалога выбора отделов"""
    if result:
        # Копируем данные об оценках отделов
        for key, value in result.items():
            dialog_manager.dialog_data[key] = value
    
    # Переходим к следующему шагу - мотивации
    await dialog_manager.switch_to(ApplicationSG.motivation)


# Обработчики для меню изменения заявки
async def on_edit_full_name(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.full_name)


async def on_edit_course(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.course)


async def on_edit_vsm(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.is_from_vsm)


async def on_edit_spbu(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.is_from_spbu)


async def on_edit_university(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.university)


async def on_edit_dormitory(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    # Проверяем, можно ли редактировать вопрос об общежитии
    is_from_vsm = dialog_manager.dialog_data.get("is_from_vsm", False)
    if not is_from_vsm:
        # Если НЕ из ВШМ, не даем редактировать общежитие
        await callback.answer("❌ Этот вопрос доступен только для студентов ВШМ", show_alert=True)
        return
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.dormitory)


async def on_edit_email(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.email)


async def on_edit_phone(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.phone)


async def on_edit_qualities(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.personal_qualities)


async def on_edit_motivation(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.switch_to(ApplicationSG.motivation)


async def on_edit_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data["is_editing"] = True
    await dialog_manager.start(DepartmentSelectionSG.logistics)