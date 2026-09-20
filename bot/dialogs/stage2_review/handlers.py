"""Handlers for the Stage 2 Review dialog."""

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select

from bot.states import Stage2ReviewSG
from database.db import Database
from database.repositories import UserRepository, ApplicationRepository, Stage2Repository
from utils.google_services import GoogleSheetsService
from utils.emojis import emoji, num_emoji, combo_emojis

logger = logging.getLogger(__name__)


async def on_page_selected(
    callback: CallbackQuery,
    _widget: Select,
    manager: DialogManager,
    item_id: str,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    manager.dialog_data["current_page"] = int(item_id)
    await manager.switch_to(Stage2ReviewSG.PAGE)


async def on_app_selected(
    callback: CallbackQuery,
    _widget: Select,
    manager: DialogManager,
    item_id: str,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    manager.dialog_data["selected_user_id"] = int(item_id)
    manager.dialog_data["detail_page_idx"] = 0
    await manager.switch_to(Stage2ReviewSG.APP_DETAIL)


async def on_prev_page(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    current = manager.dialog_data.get("current_page", 0)
    manager.dialog_data["current_page"] = max(0, current - 1)
    await manager.switch_to(Stage2ReviewSG.PAGE)


async def on_next_page(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    current = manager.dialog_data.get("current_page", 0)
    manager.dialog_data["current_page"] = current + 1
    await manager.switch_to(Stage2ReviewSG.PAGE)


async def on_back_to_pages(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    await manager.switch_to(Stage2ReviewSG.PAGE_SELECT)


async def on_back_to_page(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    manager.dialog_data["detail_page_idx"] = 0
    await manager.switch_to(Stage2ReviewSG.PAGE)


async def on_detail_next(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    idx = manager.dialog_data.get("detail_page_idx", 0)
    manager.dialog_data["detail_page_idx"] = idx + 1
    await manager.switch_to(Stage2ReviewSG.APP_DETAIL)


async def on_detail_prev(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    idx = manager.dialog_data.get("detail_page_idx", 0)
    manager.dialog_data["detail_page_idx"] = max(0, idx - 1)
    await manager.switch_to(Stage2ReviewSG.APP_DETAIL)


async def on_toggle_reviewed(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    await callback.answer()
    db: Database | None = manager.middleware_data.get("db")
    selected_user_id: int | None = manager.dialog_data.get("selected_user_id")
    if not db or selected_user_id is None:
        return

    session = await db.get_session()
    try:
        stage2_repo = Stage2Repository(session)
        app = await stage2_repo.get_by_user_id(selected_user_id)
        if app:
            new_val = not app.reviewed
            await stage2_repo.set_reviewed(selected_user_id, new_val)
            await manager.switch_to(Stage2ReviewSG.APP_DETAIL)
    except Exception as e:
        logger.error("[STAGE2_REVIEW] toggle_reviewed failed: %s", e)
        await callback.message.answer(f"❌ Ошибка обновления статуса: {e}")
    finally:
        await session.close()


async def on_to_videos(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    """Send all video notes of the candidate to the admin chat."""
    await callback.answer()

    bot: Bot = manager.middleware_data["bot"]
    chat_id = callback.message.chat.id
    db: Database | None = manager.middleware_data.get("db")
    selected_user_id: int | None = manager.dialog_data.get("selected_user_id")

    if not db or selected_user_id is None:
        await callback.message.answer("❌ Данные недоступны.")
        return

    session = await db.get_session()
    try:
        stage2_repo = Stage2Repository(session)
        app = await stage2_repo.get_by_user_id(selected_user_id)
        if not app:
            await callback.message.answer("❌ Заявка не найдена.")
            return

        sent_ids: list[int] = []
        video_questions = [
            (f"{num_emoji(1, "orange")} Самостоятельное решение проблемы", app.vq1_file_id),
            (f"{num_emoji(2, "orange")} Жертва личным комфортом ради цели", app.vq2_file_id),
            (f"{num_emoji(3, "orange")} Приоритезация (руководитель/участник/спикер)", app.vq3_file_id),
            (f"{num_emoji(4, "orange")} Сомнения в решении руководителя", app.vq4_file_id),
            (f"{num_emoji(5, "orange")} Работа в команде со сложным человеком", app.vq5_file_id),
        ]

        for label, file_id in video_questions:
            if not file_id:
                msg = await bot.send_message(chat_id, f"⚠️ <b>{label}</b>: видео отсутствует")
                sent_ids.append(msg.message_id)
                continue
            try:
                label_msg = await bot.send_message(chat_id, f"<b>{label}</b>")
                sent_ids.append(label_msg.message_id)
                video_msg = await bot.send_video_note(chat_id, file_id)
                sent_ids.append(video_msg.message_id)
            except Exception as e:
                logger.error("[STAGE2_REVIEW] Failed to send video note %s: %s", label, e)
                err_msg = await bot.send_message(chat_id, f"❌ <b>{label}</b>: ошибка отправки ({e})")
                sent_ids.append(err_msg.message_id)

        manager.dialog_data["video_msg_ids"] = sent_ids
        await manager.switch_to(Stage2ReviewSG.VIDEO)
    finally:
        await session.close()


async def on_video_back(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    """Delete previously sent video messages and return to APP_DETAIL."""
    await callback.answer()

    bot: Bot = manager.middleware_data["bot"]
    chat_id = callback.message.chat.id
    sent_ids: list[int] = manager.dialog_data.pop("video_msg_ids", [])

    for msg_id in sent_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception as e:
            logger.warning("[STAGE2_REVIEW] Could not delete msg %d: %s", msg_id, e)

    await manager.switch_to(Stage2ReviewSG.APP_DETAIL)


async def on_sync_to_sheets(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    **_kwargs: Any,
) -> None:
    """Trigger manual export/sync of Stage 2 applications to Google Sheets."""
    await callback.answer("⏳ Синхронизируем...", show_alert=False)

    db: Database | None = manager.middleware_data.get("db")
    google_sheets_service: GoogleSheetsService | None = manager.middleware_data.get("google_sheets_service")

    if not google_sheets_service:
        await callback.message.answer("❌ Google Sheets сервис не настроен.")
        return

    if not db:
        await callback.message.answer("❌ База данных недоступна.")
        return

    session = await db.get_session()
    try:
        stage2_repo = Stage2Repository(session)
        user_repo = UserRepository(session)
        app_repo = ApplicationRepository(session)

        apps = await stage2_repo.list_all()
        stage2_payloads = []

        for app in apps:
            user = await user_repo.get_user_by_id(app.user_id)
            stage1_app = await app_repo.get_latest_application_by_user_id(app.user_id)

            faculty_course = ""
            if stage1_app:
                faculty_course = f"{stage1_app.faculty}, {stage1_app.course}"

            item = {
                "telegram_id": user.telegram_id if user else "",
                "telegram_username": user.telegram_username if user else "",
                "full_name": stage1_app.full_name if stage1_app else "",
                "phone": stage1_app.phone if stage1_app else "",
                "email_st": stage1_app.email_st if stage1_app else "",
                "faculty_course": faculty_course,
                "preferred_role": stage1_app.preferred_role if stage1_app else app.role_type,
                "q1_about_mb": app.q1_about_mb or "",
                "q2_motivation": app.q2_motivation or "",
                "q3_well_organized": app.q3_well_organized or "",
                "vq1_file_id": app.vq1_file_id,
                "vq2_file_id": app.vq2_file_id,
                "vq3_file_id": app.vq3_file_id,
                "vq4_file_id": app.vq4_file_id,
                "vq5_file_id": app.vq5_file_id,
                "media_has_equipment": app.media_has_equipment,
                "media_experience": app.media_experience or "",
                "media_portfolio": app.media_portfolio or "",
                "reviewed": app.reviewed,
                "created_at": app.created_at.strftime('%Y-%m-%d %H:%M:%S') if app.created_at else "",
            }
            stage2_payloads.append(item)

        success = await google_sheets_service.sync_stage2_applications(stage2_payloads)
        if success:
            await callback.message.answer(f"✅ Успешно выгружено {len(stage2_payloads)} заявок в Google Sheets!")
        else:
            await callback.message.answer("❌ Ошибка при выгрузке в Google Sheets.")
    except Exception as e:
        logger.error("[STAGE2_REVIEW] on_sync_to_sheets failed: %s", e)
        await callback.message.answer(f"❌ Ошибка: {e}")
    finally:
        await session.close()
