"""Background timer service for Stage 2 testing."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Default duration for the whole stage 2 (35 minutes = 2100 seconds)
DEFAULT_STAGE2_DURATION_SEC = 35 * 60
MSK_OFFSET = timedelta(hours=3)

# Configurable runtime duration in seconds
_current_duration_sec = DEFAULT_STAGE2_DURATION_SEC

# Active timers: user_id -> list of asyncio.TimerHandle (for warnings + final timeout)
_active_user_timers: dict[int, list[asyncio.TimerHandle]] = {}


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

TIMEOUT_TEXT = (
    "⏰ <b>Время на прохождение 2-го этапа истекло!</b>\n\n"
    "Пожалуйста, заверши отправку оставшихся ответов как можно скорее."
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


def _on_timer_expired(user_id: int, bot=None) -> None:
    """Callback when timer expires."""
    logger.info("[STAGE2_TIMER] Timer expired for user_id=%d", user_id)
    _active_user_timers.pop(user_id, None)
    if bot:
        asyncio.create_task(_safe_send_message(user_id, TIMEOUT_TEXT, bot))


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

    # 3. Final timeout expiration
    h_timeout = loop.call_later(duration, _on_timer_expired, user_id, bot)
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

