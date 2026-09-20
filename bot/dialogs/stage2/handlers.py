"""Handlers for the Stage 2 volunteer selection dialog."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.input import MessageInput

from bot.states import Stage2SG
from database.db import Database
from database.repositories import UserRepository, Stage2Repository
from services.stage2_timer import (
    schedule_user_timer,
    cancel_user_timer,
    get_stage2_duration_sec,
    format_duration,
    STARTED_TEXT,
    MSK_OFFSET,
)
from utils.logging_config import log_user_action

logger = logging.getLogger(__name__)

_MAX_LEN = 4000
_TOO_LONG_MSG = (
    f"⚠️ Ответ слишком длинный (максимум {_MAX_LEN} символов). "
    "Пожалуйста, сократи текст и отправь снова."
)


# ============================================================================
# НАВИГАЦИЯ И СТАРТ
# ============================================================================

async def on_proceed_to_test(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    """Route user according to their role (general or media)"""
    await callback.answer()
    role_type = dialog_manager.dialog_data.get("role_type", "general")
    if role_type == "media":
        await dialog_manager.switch_to(Stage2SG.intro_media)
    else:
        await dialog_manager.switch_to(Stage2SG.intro_general)


async def on_proceed_to_timer_warning(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    await dialog_manager.switch_to(Stage2SG.timer_warning)


async def on_start_general_yes(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    """Start timer and proceed to general questions"""
    await callback.answer()

    user_id = callback.from_user.id
    duration_sec = get_stage2_duration_sec()
    now_utc = datetime.now(tz=timezone.utc)
    now_msk = now_utc + MSK_OFFSET
    deadline_msk = now_msk + timedelta(seconds=duration_sec)

    bot: Bot | None = dialog_manager.middleware_data.get("bot")
    schedule_user_timer(user_id, bot=bot, seconds=duration_sec)

    time_fmt = "%H:%M:%S" if duration_sec < 300 else "%H:%M"
    await callback.message.answer(
        STARTED_TEXT.format(
            started=now_msk.strftime(time_fmt),
            deadline=deadline_msk.strftime(time_fmt),
            duration=format_duration(duration_sec),
        ),
        parse_mode="HTML",
    )

    await dialog_manager.switch_to(Stage2SG.q1_about_mb, show_mode=ShowMode.DELETE_AND_SEND)


async def on_start_general_no(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    """Return to main guard screen"""
    await callback.answer()
    await dialog_manager.switch_to(Stage2SG.MAIN)


async def on_stage2_dialog_close(result: Any, manager: DialogManager) -> None:
    """Cancel timer if user leaves or closes the dialog."""
    try:
        user_id = None
        if manager.event and hasattr(manager.event, "from_user") and manager.event.from_user:
            user_id = manager.event.from_user.id
        elif manager.middleware_data.get("event_from_user"):
            user_id = manager.middleware_data["event_from_user"].id

        if user_id:
            cancel_user_timer(user_id)
            logger.info("[STAGE2] Timer cancelled on dialog close for user_id=%d", user_id)
    except Exception as e:
        logger.warning("[STAGE2] Failed to cancel timer on dialog close: %s", e)


# ============================================================================
# ПИСЬМЕННЫЕ ВОПРОСЫ (ОБЩИЙ ФУНКЦИОНАЛ)
# ============================================================================

async def on_q1_entered(
    message: Message,
    _widget: Any,
    dialog_manager: DialogManager,
    value: str,
    **_kwargs: Any,
) -> None:
    if len(value) > _MAX_LEN:
        await message.answer(_TOO_LONG_MSG)
        return
    dialog_manager.dialog_data["q1_about_mb"] = value.strip()
    await dialog_manager.switch_to(Stage2SG.q2_motivation)


async def on_q2_entered(
    message: Message,
    _widget: Any,
    dialog_manager: DialogManager,
    value: str,
    **_kwargs: Any,
) -> None:
    if len(value) > _MAX_LEN:
        await message.answer(_TOO_LONG_MSG)
        return
    dialog_manager.dialog_data["q2_motivation"] = value.strip()
    await dialog_manager.switch_to(Stage2SG.q3_well_organized)


async def on_q3_entered(
    message: Message,
    _widget: Any,
    dialog_manager: DialogManager,
    value: str,
    **_kwargs: Any,
) -> None:
    if len(value) > _MAX_LEN:
        await message.answer(_TOO_LONG_MSG)
        return
    dialog_manager.dialog_data["q3_well_organized"] = value.strip()
    await dialog_manager.switch_to(Stage2SG.video_intro)


# ============================================================================
# ВИДЕОИНТЕРВЬЮ (ОБЩИЙ ФУНКЦИОНАЛ)
# ============================================================================

async def on_video_proceed(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    await dialog_manager.switch_to(Stage2SG.vq1)


async def on_wrong_content_type(
    message: Message,
    _widget: Any,
    _dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await message.answer(
        "⚠️ Пожалуйста, отправь именно <b>видео-кружок</b> (видеосообщение до 1 минуты).\n"
        "Текстовые сообщения, фото и обычные видеофайлы в этом блоке не принимаются."
    )


async def on_vq1(
    message: Message,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    dialog_manager.dialog_data["vq1_file_id"] = message.video_note.file_id
    await dialog_manager.switch_to(Stage2SG.vq2)


async def on_vq2(
    message: Message,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    dialog_manager.dialog_data["vq2_file_id"] = message.video_note.file_id
    await dialog_manager.switch_to(Stage2SG.vq3)


async def on_vq3(
    message: Message,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    dialog_manager.dialog_data["vq3_file_id"] = message.video_note.file_id
    await dialog_manager.switch_to(Stage2SG.vq4)


async def on_vq4(
    message: Message,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    dialog_manager.dialog_data["vq4_file_id"] = message.video_note.file_id
    await dialog_manager.switch_to(Stage2SG.vq5)


async def on_vq5(
    message: Message,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    dialog_manager.dialog_data["vq5_file_id"] = message.video_note.file_id

    user = message.from_user
    cancel_user_timer(user.id)

    db: Database | None = dialog_manager.middleware_data.get("db")
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            stage2_repo = Stage2Repository(session)
            db_user = await user_repo.get_user_by_telegram_id(user.id)
            if db_user:
                dd = dialog_manager.dialog_data
                payload = {
                    "role_type": "general",
                    "q1_about_mb": dd.get("q1_about_mb"),
                    "q2_motivation": dd.get("q2_motivation"),
                    "q3_well_organized": dd.get("q3_well_organized"),
                    "vq1_file_id": dd.get("vq1_file_id"),
                    "vq2_file_id": dd.get("vq2_file_id"),
                    "vq3_file_id": dd.get("vq3_file_id"),
                    "vq4_file_id": dd.get("vq4_file_id"),
                    "vq5_file_id": dd.get("vq5_file_id"),
                }
                await stage2_repo.upsert_application(db_user.id, payload)
                username = user.username or f"{user.first_name or ''}".strip()
                log_user_action(user.id, username, "STAGE2_SUBMITTED_GENERAL", "Stage 2 general submitted")
        except Exception as e:
            logger.error("[STAGE2] Failed to save general application for %d: %s", user.id, e, exc_info=True)
            await message.answer("❌ Произошла ошибка при сохранении ответов. Напиши, пожалуйста, @zobko.")
            return
        finally:
            await session.close()

    await dialog_manager.switch_to(Stage2SG.success, show_mode=ShowMode.DELETE_AND_SEND)


# ============================================================================
# ВОПРОСЫ МЕДИА (ФОТО / ВИДЕО)
# ============================================================================

async def on_start_media_proceed(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    await dialog_manager.switch_to(Stage2SG.media_q1_equipment)


async def on_media_equipment_yes(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    dialog_manager.dialog_data["media_has_equipment"] = True
    await dialog_manager.switch_to(Stage2SG.media_q2_experience)


async def on_media_equipment_no(
    callback: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    dialog_manager.dialog_data["media_has_equipment"] = False
    await dialog_manager.switch_to(Stage2SG.media_q2_experience)


async def on_media_experience_entered(
    message: Message,
    _widget: Any,
    dialog_manager: DialogManager,
    value: str,
    **_kwargs: Any,
) -> None:
    if len(value) > _MAX_LEN:
        await message.answer(_TOO_LONG_MSG)
        return
    dialog_manager.dialog_data["media_experience"] = value.strip()
    await dialog_manager.switch_to(Stage2SG.media_q3_portfolio)


async def on_media_portfolio_entered(
    message: Message,
    _widget: Any,
    dialog_manager: DialogManager,
    value: str,
    **_kwargs: Any,
) -> None:
    if len(value) > _MAX_LEN:
        await message.answer(_TOO_LONG_MSG)
        return
    dialog_manager.dialog_data["media_portfolio"] = value.strip()

    user = message.from_user
    db: Database | None = dialog_manager.middleware_data.get("db")
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            stage2_repo = Stage2Repository(session)
            db_user = await user_repo.get_user_by_telegram_id(user.id)
            if db_user:
                dd = dialog_manager.dialog_data
                payload = {
                    "role_type": "media",
                    "media_has_equipment": dd.get("media_has_equipment"),
                    "media_experience": dd.get("media_experience"),
                    "media_portfolio": dd.get("media_portfolio"),
                }
                await stage2_repo.upsert_application(db_user.id, payload)
                username = user.username or f"{user.first_name or ''}".strip()
                log_user_action(user.id, username, "STAGE2_SUBMITTED_MEDIA", "Stage 2 media submitted")
        except Exception as e:
            logger.error("[STAGE2] Failed to save media application for %d: %s", user.id, e, exc_info=True)
            await message.answer("❌ Произошла ошибка при сохранении ответов. Напиши, пожалуйста, @zobko.")
            return
        finally:
            await session.close()

    await dialog_manager.switch_to(Stage2SG.success, show_mode=ShowMode.DELETE_AND_SEND)
