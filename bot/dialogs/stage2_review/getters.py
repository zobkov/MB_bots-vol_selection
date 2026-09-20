"""Getters for Stage 2 Review dialog."""

import logging
import math
from typing import Any

from aiogram_dialog import DialogManager

from database.db import Database
from database.repositories import UserRepository, ApplicationRepository, Stage2Repository

logger = logging.getLogger(__name__)

_PAGE_SIZE = 10
_TG_LIMIT = 3500


def _split_pages(text: str, limit: int = _TG_LIMIT) -> list[str]:
    """Split text into chunks <= limit chars, breaking at paragraph boundaries."""
    if len(text) <= limit:
        return [text]
    pages: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            pages.append(remaining)
            break
        split_pos = remaining.rfind("\n\n", 0, limit)
        if split_pos == -1:
            split_pos = remaining.rfind("\n", 0, limit)
        if split_pos == -1:
            split_pos = limit
        pages.append(remaining[:split_pos])
        remaining = remaining[split_pos:].lstrip("\n")
    return pages


def _v(val: str | None) -> str:
    return val if val else "—"


def _yn(val: bool | None) -> str:
    if val is None:
        return "—"
    return "Да" if val else "Нет"


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
    """Load selected Stage 2 application and format details."""
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
                phone_str = _v(stage1_app.phone if stage1_app else None)
                email_str = _v(stage1_app.email_st if stage1_app else None)
                faculty_str = _v(stage1_app.faculty if stage1_app else None)
                course_str = _v(stage1_app.course if stage1_app else None)
                pref_role_str = _v(stage1_app.preferred_role if stage1_app else stage2_app.role_type)
                submitted_at_str = stage2_app.created_at.strftime('%d.%m.%Y %H:%M:%S') if stage2_app.created_at else "—"

                if stage2_app.role_type == "general":
                    has_videos = bool(
                        stage2_app.vq1_file_id
                        or stage2_app.vq2_file_id
                        or stage2_app.vq3_file_id
                        or stage2_app.vq4_file_id
                        or stage2_app.vq5_file_id
                    )
                    full_text = (
                        f"👤 <b>{full_name}</b> ({username_str})\n"
                        f"📱 {phone_str} | 📧 {email_str}\n"
                        f"🎓 {faculty_str}, {course_str}\n"
                        f"🎭 <b>Роль:</b> {pref_role_str} (Общий функционал)\n"
                        f"🕒 <b>Сдано:</b> {submitted_at_str}\n"
                        f"👀 <b>Проверено:</b> {'Да' if is_reviewed else 'Нет'}\n\n"
                        f"──────── ПИСЬМЕННЫЕ ВОПРОСЫ ────────\n\n"
                        f"<b>1. О Конференции МБ:</b>\n{_v(stage2_app.q1_about_mb)}\n\n"
                        f"<b>2. Мотивация:</b>\n{_v(stage2_app.q2_motivation)}\n\n"
                        f"<b>3. Что делает мероприятие хорошим:</b>\n{_v(stage2_app.q3_well_organized)}\n\n"
                        f"──────── ВИДЕОИНТЕРВЬЮ ────────\n"
                        f"📹 1. Самостоятельное решение: {'✅' if stage2_app.vq1_file_id else '❌'}\n"
                        f"📹 2. Жертва комфортом: {'✅' if stage2_app.vq2_file_id else '❌'}\n"
                        f"📹 3. Кейс с приоритетами: {'✅' if stage2_app.vq3_file_id else '❌'}\n"
                        f"📹 4. Решение руководителя: {'✅' if stage2_app.vq4_file_id else '❌'}\n"
                        f"📹 5. Сложный человек в команде: {'✅' if stage2_app.vq5_file_id else '❌'}\n"
                    )
                else:
                    full_text = (
                        f"👤 <b>{full_name}</b> ({username_str})\n"
                        f"📱 {phone_str} | 📧 {email_str}\n"
                        f"🎓 {faculty_str}, {course_str}\n"
                        f"📸 <b>Роль:</b> {pref_role_str} (Медиа)\n"
                        f"🕒 <b>Сдано:</b> {submitted_at_str}\n"
                        f"👀 <b>Проверено:</b> {'Да' if is_reviewed else 'Нет'}\n\n"
                        f"──────── ЗАДАНИЯ МЕДИА ────────\n\n"
                        f"<b>1. Свое оборудование:</b> {_yn(stage2_app.media_has_equipment)}\n\n"
                        f"<b>2. Опыт профессиональной съемки:</b>\n{_v(stage2_app.media_experience)}\n\n"
                        f"<b>3. Портфолио:</b>\n{_v(stage2_app.media_portfolio)}\n"
                    )

                pages = _split_pages(full_text)
                total_pages = len(pages)
                idx = dialog_manager.dialog_data.get("detail_page_idx", 0)
                idx = max(0, min(idx, total_pages - 1))
                dialog_manager.dialog_data["detail_page_idx"] = idx

                page_text = pages[idx]
                if total_pages > 1:
                    page_text = f"<i>📄 Часть {idx + 1}/{total_pages}</i>\n\n" + page_text

                detail_text = page_text
                has_detail_prev = idx > 0
                has_detail_next = idx < total_pages - 1
        except Exception as e:
            logger.error("[STAGE2_REVIEW] get_app_detail_data failed: %s", e)
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
            f"🎥 <b>Видеоинтервью кандидата</b>\n"
            f"👤 <b>{full_name}</b>\n\n"
            "Все видео-кружочки отправлены ниже в этот чат.\n"
            "При возврате назад они будут автоматически удалены."
        )
    }
