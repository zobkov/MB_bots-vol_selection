"""Background timer service for Stage 2 testing."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from aiogram_dialog import StartMode, ShowMode
from bot.states import Stage2SG
from config.config import load_config
from database.db import Database
from database.repositories import UserRepository, Stage2Repository

logger = logging.getLogger(__name__)

# Default duration for the whole stage 2 (35 minutes = 2100 seconds)
DEFAULT_STAGE2_DURATION_SEC = 35 * 60
MSK_OFFSET = timedelta(hours=3)

# Configurable runtime duration in seconds
_current_duration_sec = DEFAULT_STAGE2_DURATION_SEC

# Active timers: user_id -> list of asyncio.TimerHandle (for warnings + final timeout + grace period)
_active_user_timers: dict[int, list[asyncio.TimerHandle]] = {}

# Background dialog manager factory from aiogram_dialog
_bg_manager_factory: Any = None


def set_bg_manager_factory(factory: Any) -> None:
    """Register aiogram_dialog BgManagerFactory."""
    global _bg_manager_factory
    _bg_manager_factory = factory
    logger.info("[STAGE2_TIMER] BgManagerFactory registered successfully")


def get_stage2_duration_sec() -> int:
    """Get current configured duration in seconds."""
    return _current_duration_sec


def set_stage2_duration_sec(seconds: int) -> None:
    """Set configured duration in seconds."""
    global _current_duration_sec
    _current_duration_sec = max(5, seconds)
    logger.info("[STAGE2_TIMER] Global duration updated to %d seconds", _current_duration_sec)


def format_duration(seconds: int) -> str:
    """Format seconds into readable Russian string."""
    if seconds < 60:
        return f"{seconds} сек."
    mins = seconds // 60
    rem_sec = seconds % 60
    if rem_sec == 0:
        return f"{mins} мин."
    return f"{mins} мин. {rem_sec} сек."


STARTED_TEXT = (
    "⏱ <b>Время пошло!</b>\n\n"
    "Начало: <b>{started} (МСК)</b>\n"
    "Дедлайн прохождения: <b>{deadline} (МСК)</b>\n\n"
    "У тебя есть <b>{duration}</b> на выполнение всех заданий (письменных и видеоинтервью)."
)

WARNING_HALF_TEXT = (
    "⏳ <b>Прошла половина времени!</b>\n\n"
    "Осталось: <b>{remaining}</b>.\n"
    "Убедись, что переходишь к видеоинтервью."
)

WARNING_LAST_TEXT = (
    "⚠️ <b>Внимание! Время на исходе</b>\n\n"
    "До окончания 2-го этапа осталось: <b>{remaining}</b>!\n"
    "Пожалуйста, поторопись с записью оставшихся видео-ответов."
)

TIMER_EXPIRED_WARNING_TEXT = (
    "⏰ <b>Основное время на прохождение 2-го этапа вышло!</b>\n\n"
    "Через <b>{grace_duration}</b> тестирование автоматически завершится, "
    "и все сохраненные ответы будут зафиксированы."
)

FINAL_TERMINATED_TEXT = (
    "⌛ <b>Тестирование завершено!</b>\n\n"
    "Время на выполнение заданий 2-го этапа истекло. Твои ответы были автоматически сохранены."
)


async def _safe_send_message(user_id: int, text: str, bot) -> None:
    if not bot:
        return
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.warning("[STAGE2_TIMER] Could not send message to %d: %s", user_id, e)


def _trigger_warning(user_id: int, text: str, bot) -> None:
    logger.info("[STAGE2_TIMER] Sending intermediate notification to user_id=%d", user_id)
    if bot:
        asyncio.create_task(_safe_send_message(user_id, text, bot))


async def _force_complete_stage2(user_id: int, bot) -> None:
    """Force transition to success screen in aiogram_dialog and mark is_completed in DB."""
    logger.info("[STAGE2_TIMER] Executing forced completion for user_id=%d", user_id)
    _active_user_timers.pop(user_id, None)

    # 1. Update database record to mark as completed
    try:
        config = load_config()
        db = Database(config)
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            stage2_repo = Stage2Repository(session)
            db_user = await user_repo.get_user_by_telegram_id(user_id)
            if db_user:
                await stage2_repo.mark_completed(db_user.id)
                logger.info("[STAGE2_TIMER] Marked is_completed=True in DB for user_id=%d", user_id)
        finally:
            await session.close()
            await db.close()
    except Exception as e:
        logger.error("[STAGE2_TIMER] Failed to mark is_completed in DB for %d: %s", user_id, e)

    # 2. Send termination notice
    await _safe_send_message(user_id, FINAL_TERMINATED_TEXT, bot)

    # 3. Switch dialog to success screen if factory is available
    if _bg_manager_factory and bot:
        try:
            bg_manager = _bg_manager_factory.bg(bot=bot, user_id=user_id, chat_id=user_id)
            await bg_manager.start(
                Stage2SG.success,
                mode=StartMode.RESET_STACK,
                show_mode=ShowMode.DELETE_AND_SEND
            )
            logger.info("[STAGE2_TIMER] User %d successfully switched to Stage2SG.success", user_id)
        except Exception as e:
            logger.error("[STAGE2_TIMER] Failed to switch dialog for user %d: %s", user_id, e)


def _on_grace_period_expired(user_id: int, bot=None) -> None:
    """Callback when grace period expires -> force complete test."""
    logger.info("[STAGE2_TIMER] Grace period expired for user_id=%d", user_id)
    if bot:
        asyncio.create_task(_force_complete_stage2(user_id, bot))


def _on_main_timer_expired(user_id: int, bot=None, duration: int = DEFAULT_STAGE2_DURATION_SEC) -> None:
    """Callback when main timer expires: send 1-min alert and start grace period."""
    logger.info("[STAGE2_TIMER] Main timer expired for user_id=%d", user_id)

    # Grace period: 60s for standard duration, or scaled for short test durations
    if duration >= 120:
        grace_sec = 60
    else:
        grace_sec = max(5, int(duration * 0.25))

    grace_duration_str = format_duration(grace_sec)
    msg = TIMER_EXPIRED_WARNING_TEXT.format(grace_duration=grace_duration_str)

    if bot:
        asyncio.create_task(_safe_send_message(user_id, msg, bot))

    # Schedule grace period timer
    loop = asyncio.get_running_loop()
    h_grace = loop.call_later(grace_sec, _on_grace_period_expired, user_id, bot)
    
    # Store grace handle
    _active_user_timers[user_id] = [h_grace]
    logger.info(
        "[STAGE2_TIMER] Scheduled grace period timer (%d sec) for user_id=%d",
        grace_sec,
        user_id,
    )


def schedule_user_timer(user_id: int, bot=None, seconds: Optional[int] = None) -> None:
    """
    Schedule expiration timer and proportional warning notifications for a user.
    """
    cancel_user_timer(user_id)
    duration = seconds if seconds is not None else _current_duration_sec
    loop = asyncio.get_running_loop()
    handles: list[asyncio.TimerHandle] = []

    # 1. Half-time warning (50% elapsed, 50% remaining)
    half_time = duration / 2.0
    if half_time >= 5:  # Only schedule if reasonable
        remaining_half_str = format_duration(int(duration - half_time))
        msg_half = WARNING_HALF_TEXT.format(remaining=remaining_half_str)
        h_half = loop.call_later(half_time, _trigger_warning, user_id, msg_half, bot)
        handles.append(h_half)

    # 2. Final warning (80% elapsed, 20% remaining) if total duration is long enough
    last_warn_time = duration * 0.8
    if duration >= 45 and (duration - last_warn_time) >= 5 and (last_warn_time > half_time + 5):
        remaining_last_str = format_duration(int(duration - last_warn_time))
        msg_last = WARNING_LAST_TEXT.format(remaining=remaining_last_str)
        h_last = loop.call_later(last_warn_time, _trigger_warning, user_id, msg_last, bot)
        handles.append(h_last)

    # 3. Main timeout expiration -> starts grace period
    h_timeout = loop.call_later(duration, _on_main_timer_expired, user_id, bot, duration)
    handles.append(h_timeout)

    _active_user_timers[user_id] = handles
    logger.info(
        "[STAGE2_TIMER] Scheduled timer (%d sec, %d alerts) for user_id=%d",
        duration,
        len(handles),
        user_id,
    )


def cancel_user_timer(user_id: int) -> None:
    """Cancel all active timer handles for a user."""
    handles = _active_user_timers.pop(user_id, None)
    if handles:
        for h in handles:
            try:
                h.cancel()
            except Exception:
                pass
        logger.info("[STAGE2_TIMER] Cancelled %d timer handles for user_id=%d", len(handles), user_id)


    _active_user_timers[user_id] = handles
    logger.info(
        "[STAGE2_TIMER] Scheduled timer (%d sec, %d alerts) for user_id=%d",
        duration,
        len(handles),
        user_id,
    )


def cancel_user_timer(user_id: int) -> None:
    """Cancel all active timer handles for a user."""
    handles = _active_user_timers.pop(user_id, None)
    if handles:
        for h in handles:
            try:
                h.cancel()
            except Exception:
                pass
        logger.info("[STAGE2_TIMER] Cancelled %d timer handles for user_id=%d", len(handles), user_id)

