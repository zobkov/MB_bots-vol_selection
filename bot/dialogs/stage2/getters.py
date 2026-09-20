"""Getters for the Stage 2 volunteer selection dialog."""

import logging
from typing import Any

from aiogram.types import User
from aiogram_dialog import DialogManager

from database.db import Database
from database.repositories import UserRepository, ApplicationRepository, Stage2Repository
from services.stage2_timer import (
    get_timer_mode,
    get_stage2_duration_sec,
    get_ind_timer_settings,
    format_duration,
)
from utils.emojis import emoji, num_emoji

logger = logging.getLogger(__name__)


def _is_media_role(preferred_role: str | None) -> bool:
    """Check if applicant applied for photographer or videographer"""
    if not preferred_role:
        return False
    role_lower = preferred_role.lower()
    return "фотограф" in role_lower or "видеограф" in role_lower or "media" in role_lower


async def get_stage2_main_data(
    dialog_manager: DialogManager,
    event_from_user: User,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Check Stage 1 completion, Stage 2 completion and role type"""
    db: Database | None = dialog_manager.middleware_data.get("db")
    has_stage1 = False
    already_completed = False
    role_type = "general"
    role_title = "Волонтёр общего функционала"

    if db and event_from_user:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            app_repo = ApplicationRepository(session)
            stage2_repo = Stage2Repository(session)

            user = await user_repo.get_user_by_telegram_id(event_from_user.id)
            if user:
                stage1_app = await app_repo.get_latest_application_by_user_id(user.id)
                has_stage1 = (user.status == "submitted") or (stage1_app is not None)
                if stage1_app and user.status != "submitted":
                    await user_repo.update_status(user.telegram_id, "submitted")

                if stage1_app and stage1_app.preferred_role:
                    if _is_media_role(stage1_app.preferred_role):
                        role_type = "media"
                        role_title = stage1_app.preferred_role
                    else:
                        role_type = "general"
                        role_title = stage1_app.preferred_role

                stage2_app = await stage2_repo.get_by_user_id(user.id)
                if stage2_app:
                    if stage2_app.is_completed:
                        already_completed = True
                    elif stage2_app.role_type == "general":
                        already_completed = bool(
                            stage2_app.vq1_file_id
                            and stage2_app.vq2_file_id
                            and stage2_app.vq3_file_id
                            and stage2_app.vq4_file_id
                            and stage2_app.vq5_file_id
                        )
                    else:
                        already_completed = bool(stage2_app.media_portfolio or stage2_app.media_experience)
        except Exception as e:
            logger.error("[STAGE2] get_stage2_main_data failed for user_id=%d: %s", event_from_user.id, e)
        finally:
            await session.close()

    can_start = has_stage1 and not already_completed
    dialog_manager.dialog_data["role_type"] = role_type
    
    timer_mode = get_timer_mode()
    if timer_mode == "basic":
        current_sec = get_stage2_duration_sec()
        duration_str = f"общий таймер: {format_duration(current_sec)}"
        timer_warning_text = (
            f"На выполнение всех заданий (письменных и видеоинтервью) отводится <b>{format_duration(current_sec)}</b> "
            "с момента нажатия кнопки «Да, начать»."
        )
    else:
        written_sec, video_sec, grace_sec = get_ind_timer_settings()
        duration_str = (
            f"{format_duration(written_sec)} на каждый письменный вопрос и "
            f"{format_duration(video_sec)} на каждый видео-кружок"
        )
        timer_warning_text = (
            f"На каждый письменный вопрос отводится <b>{format_duration(written_sec)}</b>, "
            f"а на каждый видео-кружок — <b>{format_duration(video_sec)}</b>.\n\n"
            "После окончания времени бот автоматически переключит вопрос, поэтому отвечать нужно сразу."
        )

    return {
        "has_stage1": has_stage1,
        "no_stage1": not has_stage1,
        "already_completed": already_completed,
        "can_start": can_start,
        "is_general": role_type == "general",
        "is_media": role_type == "media",
        "role_title": role_title,
        "duration_str": duration_str,
        "timer_warning_text": timer_warning_text,
        "arrow_emoji": emoji("➡️"),
        "num_emoji_1": num_emoji(1),
        "num_emoji_2": num_emoji(2),
        "num_emoji_3": num_emoji(3),
        "exclamation_emoji": emoji("exclamation", "orange")
    }


async def get_media_equipment_options(dialog_manager: DialogManager, **kwargs):
    return {
        "options": [
            {"id": "yes", "text": "Да"},
            {"id": "no", "text": "Нет"},
        ]
    }
