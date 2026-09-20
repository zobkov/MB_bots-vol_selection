"""Getters for Stage 2 Review dialog."""

import logging
import math
from typing import Any

from aiogram_dialog import DialogManager

from database.db import Database
from database.repositories import UserRepository, ApplicationRepository, Stage2Repository

from utils.emojis import emoji, num_emoji, combo_emojis

logger = logging.getLogger(__name__)

_PAGE_SIZE = 10
_TG_LIMIT = 2800


def _v(val: str | None) -> str:
    if not val:
        return "—"
    return str(val).strip()


def _yn(val: bool | None) -> str:
    if val is None:
        return "—"
    return "Да" if val else "Нет"


def _build_review_pages(sections: list[str], limit: int = _TG_LIMIT) -> list[str]:
    """
    Объединяет логические секции в страницы длиной не более limit символов.
    Если секция слишком большая, разбивает её по абзацам.
    """
    flat_blocks: list[str] = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        if len(sec) <= limit:
            flat_blocks.append(sec)
        else:
            paragraphs = sec.split("\n\n")
            cur_p = ""
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                if not cur_p:
                    cur_p = p
                elif len(cur_p) + len(p) + 2 <= limit:
                    cur_p += "\n\n" + p
                else:
                    flat_blocks.append(cur_p)
                    cur_p = p
            if cur_p:
                flat_blocks.append(cur_p)

    pages: list[str] = []
    current_page = ""
    for block in flat_blocks:
        if not current_page:
            current_page = block
        elif len(current_page) + len(block) + 2 <= limit:
            current_page += "\n\n" + block
        else:
            pages.append(current_page)
            current_page = block
    if current_page:
        pages.append(current_page)

    return pages or ["⚠️ Заявка пуста."]


async def get_page_select_data(
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Build the grid of page buttons."""
    db: Database | None = dialog_manager.middleware_data.get("db")
    total = 0
    if db:
        session = await db.get_session()
        try:
            stage2_repo = Stage2Repository(session)
            total = await stage2_repo.count_all()
        except Exception as e:
            logger.error("[STAGE2_REVIEW] count_all failed: %s", e)
        finally:
            await session.close()

    total_pages = max(1, math.ceil(total / _PAGE_SIZE))
    pages = [(str(i), f"Стр {i + 1}") for i in range(total_pages)]

    return {
        "pages": pages,
        "total": total,
        "total_pages": total_pages,
    }


async def get_page_data(
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Load one page of Stage 2 applications."""
    db: Database | None = dialog_manager.middleware_data.get("db")
    current_page: int = dialog_manager.dialog_data.get("current_page", 0)

    apps: list[tuple[str, str]] = []
    total = 0

    if db:
        session = await db.get_session()
        try:
            stage2_repo = Stage2Repository(session)
            user_repo = UserRepository(session)
            app_repo = ApplicationRepository(session)

            total = await stage2_repo.count_all()
            entities = await stage2_repo.list_page(page=current_page, limit=_PAGE_SIZE)

            for entity in entities:
                user = await user_repo.get_user_by_id(entity.user_id)
                stage1_app = await app_repo.get_latest_application_by_user_id(entity.user_id)

                display_name = (
                    stage1_app.full_name
                    if stage1_app and stage1_app.full_name
                    else (f"@{user.telegram_username}" if user and user.telegram_username else f"User_{entity.user_id}")
                )
                role_icon = "📸" if entity.role_type == "media" else "👥"
                if entity.reviewed:
                    display_name = f"👀 {role_icon} {display_name}"
                else:
                    display_name = f"🆕 {role_icon} {display_name}"

                apps.append((str(entity.user_id), display_name))
        except Exception as e:
            logger.error("[STAGE2_REVIEW] get_page_data failed: %s", e)
        finally:
            await session.close()

    total_pages = max(1, math.ceil(total / _PAGE_SIZE))
    has_prev = current_page > 0
    has_next = current_page < total_pages - 1

    return {
        "apps": apps,
        "has_prev": has_prev,
        "has_next": has_next,
        "page_label": f"Стр {current_page + 1}/{total_pages}",
        "current_page": current_page,
    }


async def get_app_detail_data(
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Load selected Stage 2 application and format full details with Stage 1 and Stage 2 info."""
    db: Database | None = dialog_manager.middleware_data.get("db")
    selected_user_id: int | None = dialog_manager.dialog_data.get("selected_user_id")

    detail_text = "⚠️ Заявка не найдена."
    has_videos = False
    is_reviewed = False
    has_detail_prev = False
    has_detail_next = False

    if db and selected_user_id is not None:
        session = await db.get_session()
        try:
            stage2_repo = Stage2Repository(session)
            user_repo = UserRepository(session)
            app_repo = ApplicationRepository(session)

            stage2_app = await stage2_repo.get_by_user_id(selected_user_id)
            user = await user_repo.get_user_by_id(selected_user_id)
            stage1_app = await app_repo.get_latest_application_by_user_id(selected_user_id)

            if stage2_app:
                is_reviewed = stage2_app.reviewed
                full_name = stage1_app.full_name if stage1_app else f"User_{selected_user_id}"
                username_str = f"@{user.telegram_username}" if user and user.telegram_username else "—"
                tg_id_str = str(user.telegram_id) if user else str(selected_user_id)
                phone_str = _v(stage1_app.phone if stage1_app else None)
                email_str = _v(stage1_app.email_st if stage1_app else None)
                faculty_str = _v(stage1_app.faculty if stage1_app else None)
                course_str = _v(stage1_app.course if stage1_app else None)
                days_str = _v(stage1_app.days_count if stage1_app else None)
                day_zero_str = _yn(stage1_app.day_zero_available if stage1_app else None)
                pref_role_str = _v(stage1_app.preferred_role if stage1_app else stage2_app.role_type)

                stage1_date_str = stage1_app.created_at.strftime('%d.%m.%Y %H:%M') if (stage1_app and stage1_app.created_at) else "—"
                stage2_date_str = stage2_app.created_at.strftime('%d.%m.%Y %H:%M') if stage2_app.created_at else "—"
                stage2_completed_str = "✅ Завершен" if stage2_app.is_completed else "⏳ В процессе / оборван таймером"
                reviewed_str = "✅ Да" if is_reviewed else "❌ Нет"

                # Блок 1: Профиль и контактная информация
                sec1 = (
                    f"👤 <b>{full_name}</b> ({username_str})\n"
                    f"🆔 TG ID: <code>{tg_id_str}</code>\n"
                    f"📱 {phone_str} | 📧 {email_str}\n"
                    f"🎓 {faculty_str}, {course_str}\n"
                    f"📅 Дни: {days_str} | 0️⃣: {day_zero_str}\n\n" # TODO: dark blue 0
                    f"🎭 Роль: <b>{pref_role_str}</b>\n"
                    f"🕒 1-й этап: {stage1_date_str} | 2-й этап: {stage2_date_str}\n\n"
                    f"🏁 Статус 2-го этапа: <b>{stage2_completed_str}</b>\n"
                    f"👀 Проверено: <b>{reviewed_str}</b>"
                )

                sections = [sec1]

                # Блок 2: Эссе 1-го этапа (мотивация и опыт)
                if stage1_app:
                    sec_stage1 = (
                        f"{emoji("➡️", "light_blue")}<b>──────── 1-Й ЭТАП (АНКЕТА)</b>\n\n"
                        f"{emoji("⭐️", "light_blue")} <b>Почему ты - идеальный волонтер:</b>\n{_v(stage1_app.motivation)}\n\n"
                        f"{emoji("✨", "light_blue")} <b>Опыт волонтерства:</b>\n{_v(stage1_app.volunteer_experience)}"
                    )
                    sections.append(sec_stage1)

                # Блок 3 и 4: Задания 2-го этапа
                if stage2_app.role_type == "general":
                    has_videos = bool(
                        stage2_app.vq1_file_id
                        or stage2_app.vq2_file_id
                        or stage2_app.vq3_file_id
                        or stage2_app.vq4_file_id
                        or stage2_app.vq5_file_id
                    )
                    sec_stage2_written = (
                        f"{emoji("➡️", "dark_blue")}<b>──────── 2-Й ЭТАП: ПИСЬМЕННЫЕ ВОПРОСЫ</b>\n\n" # TODO: dark_blue arrow
                        f"<b>{num_emoji(1, "dark_blue")} О Конференции МБ:</b>\n{_v(stage2_app.q1_about_mb)}\n\n"
                        f"<b>{num_emoji(2, "dark_blue")} Мотивация на МБ:</b>\n{_v(stage2_app.q2_motivation)}\n\n"
                        f"<b>{num_emoji(3, "dark_blue")} Что делает мероприятие хорошим:</b>\n{_v(stage2_app.q3_well_organized)}"
                    )
                    sec_stage2_video = (
                        f"{emoji("➡️", "orange")}<b>──────── 2-Й ЭТАП: ВИДЕОИНТЕРВЬЮ</b>\n\n" # TODO: light_blue arrow
                        f"📹 {num_emoji(1, "orange")} Самостоятельное решение: {'✅ Записано' if stage2_app.vq1_file_id else '❌ Нет'}\n"
                        f"📹 {num_emoji(2, "orange")} Жертва комфортом: {'✅ Записано' if stage2_app.vq2_file_id else '❌ Нет'}\n"
                        f"📹 {num_emoji(3, "orange")} Кейс с приоритетами: {'✅ Записано' if stage2_app.vq3_file_id else '❌ Нет'}\n"
                        f"📹 {num_emoji(4, "orange")} Решение руководителя: {'✅ Записано' if stage2_app.vq4_file_id else '❌ Нет'}\n"
                        f"📹 {num_emoji(5, "orange")} Сложный человек в команде: {'✅ Записано' if stage2_app.vq5_file_id else '❌ Нет'}\n\n"
                        f"<i>💡 Нажмите кнопку «🎥 Видео ▶️» ниже, чтобы посмотреть все кружки в чате.</i>"
                    )
                    sections.append(sec_stage2_written)
                    sections.append(sec_stage2_video)
                else:
                    sec_stage2_media = (
                        "📸 <b>──────── 2-Й ЭТАП: ЗАДАНИЯ МЕДИА ────────</b>\n\n"
                        f"<b>1. Свое оборудование:</b> {_yn(stage2_app.media_has_equipment)}\n\n"
                        f"<b>2. Опыт профессиональной съемки:</b>\n{_v(stage2_app.media_experience)}\n\n"
                        f"<b>3. Портфолио:</b>\n{_v(stage2_app.media_portfolio)}"
                    )
                    sections.append(sec_stage2_media)

                pages = _build_review_pages(sections, limit=2800)
                total_pages = len(pages)
                idx = dialog_manager.dialog_data.get("detail_page_idx", 0)
                idx = max(0, min(idx, total_pages - 1))
                dialog_manager.dialog_data["detail_page_idx"] = idx

                page_text = pages[idx]
                if total_pages > 1:
                    page_text = f"<i>📄 Страница {idx + 1} из {total_pages}</i>\n\n" + page_text

                detail_text = page_text
                has_detail_prev = idx > 0
                has_detail_next = idx < total_pages - 1
        except Exception as e:
            logger.error("[STAGE2_REVIEW] get_app_detail_data failed: %s", e, exc_info=True)
            detail_text = f"❌ Ошибка загрузки данных: {e}"
        finally:
            await session.close()

    return {
        "detail_text": detail_text,
        "has_videos": has_videos,
        "is_reviewed": is_reviewed,
        "not_is_reviewed": not is_reviewed,
        "has_detail_prev": has_detail_prev,
        "has_detail_next": has_detail_next,
    }


async def get_video_data(
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> dict[str, Any]:
    db: Database | None = dialog_manager.middleware_data.get("db")
    selected_user_id: int | None = dialog_manager.dialog_data.get("selected_user_id")

    full_name = f"User_{selected_user_id}"
    if db and selected_user_id is not None:
        session = await db.get_session()
        try:
            app_repo = ApplicationRepository(session)
            stage1_app = await app_repo.get_latest_application_by_user_id(selected_user_id)
            if stage1_app and stage1_app.full_name:
                full_name = stage1_app.full_name
        except Exception:
            pass
        finally:
            await session.close()

    return {
        "video_header": (
            f"{emoji("⬇️", "orange")}  <b>Видеоинтервью кандидата</b>\n\n"
            f"👤 <b>{full_name}</b>\n\n"
        )
    }
