import re
import logging
from aiogram import types
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode, ShowMode
from aiogram_dialog.widgets.kbd import Button, Group, Start, SwitchTo, Cancel, Radio, Column
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput, MessageInput

from bot.states import ApplicationSG, StartSG, MenuSG
from database.repositories import UserRepository, ApplicationRepository
from database.db import Database
from utils.logging_config import log_user_action, log_user_debug
from utils.emojis import emoji, num_emoji

logger = logging.getLogger(__name__)


def _log_app_debug(user, action: str, details: str = ""):
    """Вспомогательная функция для дебаг-логирования действий в анкете"""
    if not user:
        return
    username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
    log_user_debug(user.id, username, f"APPLICATION:{action}", details)


# ============================================================================
# ВАЛИДАТОРЫ
# ============================================================================

def full_name_check(text: str) -> str:
    cleaned = text.strip()
    parts = cleaned.split()
    if len(parts) < 2:
        raise ValueError("❌ Пожалуйста, введите полное ФИО (как минимум Фамилию и Имя).")
    return cleaned


def email_st_check(text: str) -> str:
    cleaned = text.strip()
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, cleaned):
        raise ValueError("❌ Введите корректный email (например: st123456@student.spbu.ru).")
    return cleaned


def phone_check(text: str) -> str:
    cleaned = text.strip()
    phone_digits = re.sub(r'[^\d]', '', cleaned)
    if len(phone_digits) < 10:
        raise ValueError("❌ Введите корректный номер телефона (не менее 10 цифр).")
    return cleaned


# ============================================================================
# ОБРАБОТЧИКИ ВВОДА
# ============================================================================

async def on_full_name_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(message.from_user, "INPUT_FULL_NAME", f"value='{text}', is_editing={is_editing}")
    dialog_manager.dialog_data["full_name"] = text
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_email_st_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(message.from_user, "INPUT_EMAIL_ST", f"value='{text}', is_editing={is_editing}")
    dialog_manager.dialog_data["email_st"] = text
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_phone_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(message.from_user, "INPUT_PHONE", f"value='{text}', is_editing={is_editing}")
    dialog_manager.dialog_data["phone"] = text
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_contact_received(message: types.Message, widget, dialog_manager: DialogManager):
    if message.contact:
        is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
        dialog_manager.dialog_data["phone"] = message.contact.phone_number
        _log_app_debug(message.from_user, "CONTACT_RECEIVED", f"phone='{message.contact.phone_number}', is_editing={is_editing}")
        if is_editing:
            dialog_manager.dialog_data["is_editing"] = False
            await dialog_manager.switch_to(ApplicationSG.overview)
        else:
            await dialog_manager.next()
    else:
        _log_app_debug(message.from_user, "CONTACT_INVALID", "Received message without contact")
        await message.answer("❌ Пожалуйста, отправьте контакт через кнопку или напишите номер текстом.")


async def on_faculty_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    faculty_val = text.strip()
    _log_app_debug(message.from_user, "INPUT_FACULTY", f"value='{faculty_val}', is_editing={is_editing}")
    dialog_manager.dialog_data["faculty"] = faculty_val
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_course_selected(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    courses_map = {
        "1_bachelor": "1 курс бакалавриат",
        "2_bachelor": "2 курс бакалавриат",
        "3_bachelor": "3 курс бакалавриат",
        "4_bachelor": "4 курс бакалавриат",
        "1_master": "1 курс магистратура",
        "2_master": "2 курс магистратура",
        "other": "Другое"
    }
    course_display = courses_map.get(item_id, item_id)
    dialog_manager.dialog_data["course"] = course_display
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(callback.from_user, "SELECT_COURSE", f"item_id='{item_id}', course='{course_display}', is_editing={is_editing}")
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_days_count_selected(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    days_map = {
        "2_days": "2 дня",
        "3_days": "3 дня"
    }
    days_display = days_map.get(item_id, item_id)
    dialog_manager.dialog_data["days_count"] = days_display
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(callback.from_user, "SELECT_DAYS_COUNT", f"item_id='{item_id}', days='{days_display}', is_editing={is_editing}")
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_day_zero_selected(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    is_available = item_id == "yes"
    dialog_manager.dialog_data["day_zero_available"] = is_available
    dialog_manager.dialog_data["day_zero_display"] = "Да" if is_available else "Нет"
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(callback.from_user, "SELECT_DAY_ZERO", f"item_id='{item_id}', available={is_available}, is_editing={is_editing}")
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_role_selected(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    roles_map = {
        "general": "Волонтёр общего функционала",
        "photographer": "Фотограф",
        "videographer": "Видеограф"
    }
    role_display = roles_map.get(item_id, item_id)
    dialog_manager.dialog_data["preferred_role"] = role_display
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(callback.from_user, "SELECT_ROLE", f"item_id='{item_id}', role='{role_display}', is_editing={is_editing}")
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_motivation_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(message.from_user, "INPUT_MOTIVATION", f"chars={len(text.strip())}, is_editing={is_editing}")
    dialog_manager.dialog_data["motivation"] = text.strip()
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.next()


async def on_experience_input(message: types.Message, widget, dialog_manager: DialogManager, text: str):
    is_editing = bool(dialog_manager.dialog_data.get("is_editing"))
    _log_app_debug(message.from_user, "INPUT_EXPERIENCE", f"chars={len(text.strip())}, is_editing={is_editing}")
    dialog_manager.dialog_data["volunteer_experience"] = text.strip()
    if is_editing:
        dialog_manager.dialog_data["is_editing"] = False
        await dialog_manager.switch_to(ApplicationSG.overview)
    else:
        await dialog_manager.switch_to(ApplicationSG.overview)


# ============================================================================
# ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ
# ============================================================================

async def on_edit_field(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    target_state_name = button.widget_id.replace("edit_", "")
    target_state = getattr(ApplicationSG, target_state_name)
    dialog_manager.dialog_data["is_editing"] = True
    _log_app_debug(callback.from_user, "EDIT_FIELD_CHOSEN", f"target_state={target_state_name}")
    await dialog_manager.switch_to(target_state)


async def on_to_edit_menu(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    _log_app_debug(callback.from_user, "OPEN_EDIT_MENU", "Opened edit menu from overview")
    await dialog_manager.switch_to(ApplicationSG.edit_menu)


async def on_back_to_overview(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    _log_app_debug(callback.from_user, "BACK_TO_OVERVIEW", "Returned to overview from edit menu")
    await dialog_manager.switch_to(ApplicationSG.overview)


async def on_application_cancelled(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    state = dialog_manager.current_context().state if dialog_manager.current_context() else "unknown"
    _log_app_debug(callback.from_user, "APPLICATION_CANCELLED", f"User cancelled application at state {state}")


# ============================================================================
# ГЕТТЕРЫ ДАННЫХ
# ============================================================================

async def get_courses_options(dialog_manager: DialogManager, **kwargs):
    return {
        "courses": [
            {"id": "1_bachelor", "text": "1 курс бакалавриат"},
            {"id": "2_bachelor", "text": "2 курс бакалавриат"},
            {"id": "3_bachelor", "text": "3 курс бакалавриат"},
            {"id": "4_bachelor", "text": "4 курс бакалавриат"},
            {"id": "1_master", "text": "1 курс магистратура"},
            {"id": "2_master", "text": "2 курс магистратура"},
            {"id": "other", "text": "Другое"},
        ]
    }


async def get_days_options(dialog_manager: DialogManager, **kwargs):
    return {
        "days": [
            {"id": "2_days", "text": "2 дня"},
            {"id": "3_days", "text": "3 дня"},
        ]
    }


async def get_day_zero_options(dialog_manager: DialogManager, **kwargs):
    return {
        "options": [
            {"id": "yes", "text": "Да"},
            {"id": "no", "text": "Нет"},
        ]
    }


async def get_roles_options(dialog_manager: DialogManager, **kwargs):
    return {
        "roles": [
            {"id": "general", "text": "Волонтёр общего функционала"},
            {"id": "photographer", "text": "Фотограф"},
            {"id": "videographer", "text": "Видеограф"},
        ]
    }


def _truncate_preview(text: str | None, max_len: int = 350) -> str:
    """Безопасно обрезает длинный текст для экрана подтверждения, чтобы не превысить лимит сообщения Telegram"""
    if not text:
        return "—"
    cleaned = text.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + " ... <i>(сокращено для предпросмотра)</i>"


async def get_overview_data(dialog_manager: DialogManager, **kwargs):
    data = dialog_manager.dialog_data
    
    day_zero_text = data.get('day_zero_display') or ("Да" if data.get('day_zero_available') else "Нет")
    motivation_preview = _truncate_preview(data.get('motivation'), 350)
    experience_preview = _truncate_preview(data.get('volunteer_experience'), 350)
    
    overview_text = f"""📋 <b>Проверь свои ответы перед отправкой:</b>

{num_emoji(1)} <b>ФИО:</b> {data.get('full_name', '—')}
{num_emoji(2)} <b>Почта st:</b> {data.get('email_st', '—')}
{num_emoji(3)} <b>Телефон:</b> {data.get('phone', '—')}
{num_emoji(4)} <b>Факультет/направление:</b> {data.get('faculty', '—')}
{num_emoji(5)} <b>Курс:</b> {data.get('course', '—')}
{num_emoji(6)} <b>Готовность (дней):</b> {data.get('days_count', '—')}
{num_emoji(7)} <b>0-й день (21 октября):</b> {day_zero_text}
{num_emoji(8)} <b>Желаемая роль:</b> {data.get('preferred_role', '—')}

{num_emoji(9)} <b>Почему ты - идеальный волонтер:</b>
{motivation_preview}

{num_emoji(10)} <b>Опыт волонтерства:</b>
{experience_preview}"""

    return {"overview_text": overview_text}


# ============================================================================
# ОТПРАВКА АНКЕТЫ
# ============================================================================

async def on_submit_application(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    data = dialog_manager.dialog_data
    user = dialog_manager.event.from_user
    db: Database = dialog_manager.middleware_data.get("db")
    google_sheets_service = dialog_manager.middleware_data.get("google_sheets_service")
    
    _log_app_debug(user, "SUBMIT_APPLICATION_ATTEMPT", f"data_keys={list(data.keys())}")
    
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        app_repo = ApplicationRepository(session, google_sheets_service)
        
        db_user = await user_repo.get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username
        )
        
        application_data = {
            "full_name": data["full_name"],
            "email_st": data["email_st"],
            "phone": data["phone"],
            "faculty": data["faculty"],
            "course": data["course"],
            "days_count": data["days_count"],
            "day_zero_available": bool(data.get("day_zero_available")),
            "preferred_role": data["preferred_role"],
            "motivation": data["motivation"],
            "volunteer_experience": data["volunteer_experience"],
        }
        
        user_telegram_data = {
            "telegram_id": user.id,
            "telegram_username": user.username or "",
        }
        
        await app_repo.create_application(db_user.id, application_data, user_telegram_data)
        await user_repo.update_status(user.id, "submitted")
        
        username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
        logger.info(f"✅ Пользователь {user.id} (@{user.username}) успешно заполнил и отправил анкету: {data.get('full_name')}")
        log_user_action(user.id, username, "APPLICATION_SUBMITTED", f"ФИО: {data.get('full_name')}, Email: {data.get('email_st')}")
        _log_app_debug(user, "APPLICATION_SAVED_SUCCESS", f"app_id for user {user.id}")
    finally:
        await session.close()
    
    await dialog_manager.switch_to(ApplicationSG.submitted)


# ============================================================================
# ДИАЛОГ
# ============================================================================

application_dialog = Dialog(
    # 1) ФИО
    Window(
        Const(f"{num_emoji(1)} <b>Укажи свое ФИО</b> (пример: Иванов Иван Иванович):"),
        TextInput(
            id="full_name_input",
            on_success=on_full_name_input,
            type_factory=full_name_check,
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.full_name,
    ),
    
    # 2) Почта st
    Window(
        Const(f"{num_emoji(2)} <b>Укажи свою почту st целиком</b> (например: st123456@student.spbu.ru):"),
        TextInput(
            id="email_st_input",
            on_success=on_email_st_input,
            type_factory=email_st_check,
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.email_st,
    ),
    
    # 3) Телефон
    Window(
        Const(f"{num_emoji(3)} <b>Укажи свой номер телефона:</b>"),
        TextInput(
            id="phone_input",
            on_success=on_phone_input,
            type_factory=phone_check,
        ),
        MessageInput(
            func=on_contact_received,
            content_types=[ContentType.CONTACT],
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.phone,
    ),
    
    # 4) Факультет / направление
    Window(
        Const(f"{num_emoji(4)} <b>С какого ты факультета/направления?</b>\n(пример: Менеджмент, Международный менеджмент):"),
        TextInput(
            id="faculty_input",
            on_success=on_faculty_input,
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.faculty,
    ),
    
    # 5) Курс обучения
    Window(
        Const(f"{num_emoji(5)} <b>На каком курсе ты обучаешься?</b>"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="course_radio",
                item_id_getter=lambda item: item["id"],
                items="courses",
                on_click=on_course_selected
            ),
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.course,
        getter=get_courses_options,
    ),
    
    # 6) Количество дней
    Window(
        Const(
            f"{num_emoji(6)} <b>Сколько дней ты готов(-а) помогать на Конференции?</b>\n\n"
            "Напоминаем, что на площадке нужно будет присутствовать минимум два дня с 9.00 до 21.00."
        ),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="days_radio",
                item_id_getter=lambda item: item["id"],
                items="days",
                on_click=on_days_count_selected
            ),
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.days_count,
        getter=get_days_options,
    ),
    
    # 7) 0-й день (21 октября)
    Window(
        Const(f"{num_emoji(7)} <b>Можешь ли ты помогать в 0 день Конференции (21 октября)?</b>"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="day_zero_radio",
                item_id_getter=lambda item: item["id"],
                items="options",
                on_click=on_day_zero_selected
            ),
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.day_zero,
        getter=get_day_zero_options,
    ),
    
    # 8) Роль на площадке
    Window(
        Const(f"{num_emoji(8)} <b>Какую роль ты хочешь выполнять на площадке: волонтер общего функционала, фотограф, видеограф?</b>"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="role_radio",
                item_id_getter=lambda item: item["id"],
                items="roles",
                on_click=on_role_selected
            ),
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.role,
        getter=get_roles_options,
    ),
    
    # 9) Мотивация
    Window(
        Const(f"{num_emoji(9)} <b>Почему именно ты - идеальный волонтер Конференции?</b>"),
        TextInput(
            id="motivation_input",
            on_success=on_motivation_input,
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.motivation,
    ),
    
    # 10) Опыт волонтерства
    Window(
        Const(f"{num_emoji(10)} <b>Есть ли у тебя опыт волонтерства?</b> Если да, опиши его подробно, пожалуйста:"),
        TextInput(
            id="experience_input",
            on_success=on_experience_input,
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.experience,
    ),
    
    # 11) Обзор ответов
    Window(
        Format("{overview_text}"),
        Group(
            Button(Const("✅ Подтвердить и отправить"), id="submit_app", on_click=on_submit_application),
            Button(Const("✏️ Изменить ответы"), id="edit_app", on_click=on_to_edit_menu),
            width=1,
        ),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.overview,
        getter=get_overview_data,
    ),
    
    # 12) Меню изменения заявки
    Window(
        Const("✏️ <b>Какое поле ты хочешь изменить?</b>"),
        Group(
            Button(Const("1. 👤 ФИО"), id="edit_full_name", on_click=on_edit_field),
            Button(Const("2. 📧 Почта st"), id="edit_email_st", on_click=on_edit_field),
            Button(Const("3. 📱 Телефон"), id="edit_phone", on_click=on_edit_field),
            Button(Const("4. 🎓 Факультет"), id="edit_faculty", on_click=on_edit_field),
            Button(Const("5. 📚 Курс"), id="edit_course", on_click=on_edit_field),
            Button(Const("6. 📅 Дни помощи"), id="edit_days_count", on_click=on_edit_field),
            Button(Const("7. 🗓️ 0-й день"), id="edit_day_zero", on_click=on_edit_field),
            Button(Const("8. 🎭 Роль"), id="edit_role", on_click=on_edit_field),
            Button(Const("9. 🌟 Мотивация"), id="edit_motivation", on_click=on_edit_field),
            Button(Const("10. 🤝 Опыт"), id="edit_experience", on_click=on_edit_field),
            width=2,
        ),
        Button(Const("🔙 Назад к обзору"), id="back_to_overview", on_click=on_back_to_overview),
        Cancel(Const("❌ Отмена"), on_click=on_application_cancelled),
        state=ApplicationSG.edit_menu,
    ),
    
    # 13) Успешное завершение
    Window(
        Const(
            "Спасибо за отклик! Мы вернемся с заданиями следующего этапа <b>22 сентября.</b> "
            'Обязательно включи уведомления бота, чтобы не потерять связь с нашей орбитой <tg-emoji emoji-id="5255731027480975263">🕐</tg-emoji>'
        ),
        Start(
            Const("🏠 Личный кабинет"),
            id="to_menu_from_submitted",
            state=MenuSG.main,
            mode=StartMode.RESET_STACK
        ),
        state=ApplicationSG.submitted,
    ),
)

