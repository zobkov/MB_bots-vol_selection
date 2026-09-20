import math
import logging
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Row, SwitchTo, Cancel
from aiogram_dialog.widgets.text import Const, Format

from bot.states import ViewUserSG
from database.db import Database
from database.repositories import UserRepository, ApplicationRepository
from utils.emojis import emoji, num_emoji

logger = logging.getLogger(__name__)


def build_application_pages(application) -> list[str]:
    """Разбивает анкету на логические и безопасные по длине страницы для Telegram"""
    if not application:
        return ["❌ Анкета не найдена."]

    created_at_str = application.created_at.strftime('%d.%m.%Y %H:%M:%S') if application.created_at else "—"
    day_zero_str = "Да" if application.day_zero_available else "Нет"

    # Страница 1: Основная контактная и организационная информация
    page1 = (
        f"📋 <b>Анкета кандидата (Часть 1: Данные и участие)</b>\n\n"
        f"{num_emoji(1)} <b>ФИО:</b> {application.full_name}\n"
        f"{num_emoji(2)} <b>Почта st:</b> {application.email_st}\n"
        f"{num_emoji(3)} <b>Телефон:</b> {application.phone}\n"
        f"{num_emoji(4)} <b>Факультет / направление:</b> {application.faculty}\n"
        f"{num_emoji(5)} <b>Курс:</b> {application.course}\n"
        f"{num_emoji(6)} <b>Дни участия:</b> {application.days_count}\n"
        f"{num_emoji(7)} <b>0-й день (21 октября):</b> {day_zero_str}\n"
        f"{num_emoji(8)} <b>Желаемая роль:</b> {application.preferred_role}\n"
        f"🕒 <b>Дата подачи:</b> {created_at_str}"
    )

    # Страница 2 (или более): Мотивация и опыт
    motivation_text = application.motivation or "—"
    experience_text = application.volunteer_experience or "—"

    combined_essay = (
        f"📋 <b>Анкета кандидата (Часть 2: Мотивация и опыт)</b>\n\n"
        f"{num_emoji(9)} <b>Почему именно ты - идеальный волонтер:</b>\n{motivation_text}\n\n"
        f"{num_emoji(10)} <b>Опыт волонтерства:</b>\n{experience_text}"
    )

    # Проверяем длину страницы 2. Telegram лимит 4096 символов.
    if len(combined_essay) <= 3500:
        pages = [page1, combined_essay]
    else:
        # Если суммарно превышает 3500 символов, разделяем мотивацию и опыт на отдельные страницы
        page2 = (
            f"📋 <b>Анкета кандидата (Часть 2: Мотивация)</b>\n\n"
            f"{num_emoji(9)} <b>Почему именно ты - идеальный волонтер:</b>\n{motivation_text}"
        )
        page3 = (
            f"📋 <b>Анкета кандидата (Часть 3: Опыт волонтерства)</b>\n\n"
            f"{num_emoji(10)} <b>Опыт волонтерства:</b>\n{experience_text}"
        )
        
        pages = [page1]
        
        # Если мотивация всё еще огромная (>3500), нарезаем на подстраницы
        def chunk_text(header: str, text: str, max_chunk=3200) -> list[str]:
            if len(text) <= max_chunk:
                return [f"{header}\n{text}"]
            chunks = []
            for i in range(0, len(text), max_chunk):
                part = text[i:i + max_chunk]
                chunks.append(f"{header} (продолжение):\n{part}")
            return chunks

        pages.extend(chunk_text(f"📋 <b>Анкета кандидата: Мотивация</b>\n\n{num_emoji(9)} <b>Почему именно ты - идеальный волонтер:</b>", motivation_text))
        pages.extend(chunk_text(f"📋 <b>Анкета кандидата: Опыт</b>\n\n{num_emoji(10)} <b>Опыт волонтерства:</b>", experience_text))

    return pages


# ============================================================================
# ГЕТТЕРЫ ДАННЫХ
# ============================================================================

async def get_user_overview_data(dialog_manager: DialogManager, **kwargs):
    """Геттер общей информации о пользователе"""
    db: Database = dialog_manager.middleware_data.get("db")
    target_user_id = dialog_manager.start_data.get("target_user_id") if dialog_manager.start_data else None
    if not target_user_id:
        target_user_id = dialog_manager.dialog_data.get("target_user_id")

    if not db or not target_user_id:
        return {
            "user_info_text": "❌ Информация о пользователе недоступна.",
            "has_application": False
        }

    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        app_repo = ApplicationRepository(session)

        user = await user_repo.get_user_by_id(target_user_id)
        if not user:
            return {
                "user_info_text": "❌ Пользователь не найден.",
                "has_application": False
            }

        dialog_manager.dialog_data["target_user_id"] = user.id
        application = await app_repo.get_latest_application_by_user_id(user.id)
        has_application = application is not None

        status_display = {
            "submitted": "✅ Заявка подана (submitted)",
            "registered": "📝 Зарегистрирован (registered)"
        }.get(user.status, user.status)

        reg_date = user.created_at.strftime('%d.%m.%Y %H:%M:%S') if user.created_at else "—"
        upd_date = user.updated_at.strftime('%d.%m.%Y %H:%M:%S') if user.updated_at else "—"
        username_display = f"@{user.telegram_username}" if user.telegram_username else "не указан"

        app_summary = ""
        if application:
            app_summary = (
                f"\n\n<b>Данные из анкеты:</b>\n"
                f"👤 ФИО: {application.full_name}\n"
                f"📧 Email: {application.email_st}\n"
                f"📱 Тел: {application.phone}\n"
                f"🎓 Факультет: {application.faculty}"
            )
        else:
            app_summary = "\n\n<i>⚠️ Анкета еще не заполнена</i>"

        user_info_text = (
            f"👤 <b>Профиль пользователя</b>\n\n"
            f"🆔 <b>ID в БД:</b> <code>{user.id}</code>\n"
            f"💬 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"🏷 <b>Username:</b> {username_display}\n"
            f"📊 <b>Статус:</b> {status_display}\n"
            f"🚫 <b>Заблокирован:</b> {'Да' if user.is_blocked else 'Нет'}\n"
            f"📅 <b>Регистрация:</b> {reg_date}\n"
            f"🔄 <b>Обновлен:</b> {upd_date}"
            f"{app_summary}"
        )

        return {
            "user_info_text": user_info_text,
            "has_application": has_application
        }
    finally:
        await session.close()


async def get_app_details_data(dialog_manager: DialogManager, **kwargs):
    """Геттер для постраничного просмотра анкеты"""
    db: Database = dialog_manager.middleware_data.get("db")
    target_user_id = dialog_manager.dialog_data.get("target_user_id")

    if not db or not target_user_id:
        return {
            "app_text": "❌ Ошибка загрузки анкеты.",
            "has_prev_page": False,
            "has_next_page": False,
            "page_counter": "0/0"
        }

    session = await db.get_session()
    try:
        app_repo = ApplicationRepository(session)
        application = await app_repo.get_latest_application_by_user_id(target_user_id)

        if not application:
            return {
                "app_text": "⚠️ У данного пользователя нет сохраненной анкеты.",
                "has_prev_page": False,
                "has_next_page": False,
                "page_counter": "0/0"
            }

        pages = build_application_pages(application)
        total_pages = len(pages)
        current_page = dialog_manager.dialog_data.get("app_page", 0)

        # Корректируем индекс страницы
        if current_page >= total_pages:
            current_page = total_pages - 1
        if current_page < 0:
            current_page = 0
        dialog_manager.dialog_data["app_page"] = current_page

        current_content = pages[current_page]
        footer = f"\n\n<i>📄 Страница {current_page + 1} из {total_pages}</i>"

        return {
            "app_text": f"{current_content}{footer}",
            "has_prev_page": current_page > 0,
            "has_next_page": current_page < total_pages - 1,
            "page_counter": f"{current_page + 1}/{total_pages}"
        }
    finally:
        await session.close()


# ============================================================================
# ОБРАБОТЧИКИ КНОПОК
# ============================================================================

async def on_view_app_clicked(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Переход к просмотру анкеты"""
    dialog_manager.dialog_data["app_page"] = 0
    await dialog_manager.switch_to(ViewUserSG.app_details)


async def on_prev_page_clicked(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Предыдущая страница анкеты"""
    await callback.answer()
    current_page = dialog_manager.dialog_data.get("app_page", 0)
    if current_page > 0:
        dialog_manager.dialog_data["app_page"] = current_page - 1
    await dialog_manager.switch_to(ViewUserSG.app_details)


async def on_next_page_clicked(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Следующая страница анкеты"""
    await callback.answer()
    current_page = dialog_manager.dialog_data.get("app_page", 0)
    dialog_manager.dialog_data["app_page"] = current_page + 1
    await dialog_manager.switch_to(ViewUserSG.app_details)


# ============================================================================
# ДИАЛОГ
# ============================================================================

view_user_dialog = Dialog(
    # Окно 1: Профиль пользователя
    Window(
        Format("{user_info_text}"),
        Button(
            Const("📋 Посмотреть анкету"),
            id="btn_view_app",
            on_click=on_view_app_clicked,
            when="has_application"
        ),
        Cancel(Const("❌ Закрыть")),
        state=ViewUserSG.user_info,
        getter=get_user_overview_data,
    ),
    # Окно 2: Детали анкеты с пагинацией
    Window(
        Format("{app_text}"),
        Row(
            Button(
                Const("⬅️ Предыдущая"),
                id="btn_prev_page",
                on_click=on_prev_page_clicked,
                when="has_prev_page"
            ),
            Button(
                Const("➡️ Следующая"),
                id="btn_next_page",
                on_click=on_next_page_clicked,
                when="has_next_page"
            ),
        ),
        SwitchTo(
            Const("🔙 К профилю"),
            id="btn_back_to_profile",
            state=ViewUserSG.user_info
        ),
        Cancel(Const("❌ Закрыть")),
        state=ViewUserSG.app_details,
        getter=get_app_details_data,
    ),
)
