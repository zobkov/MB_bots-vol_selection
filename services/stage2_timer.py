"""Background timer service for Stage 2 testing."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Duration for the whole stage 2 (in minutes)
STAGE2_DURATION_MIN = 35
MSK_OFFSET = timedelta(hours=3)

# Active timers: user_id -> asyncio.Task / TimerHandle
_active_timers: dict[int, asyncio.TimerHandle] = {}

STARTED_TEXT = (
    "⏱ <b>Время пошло!</b>\n\n"
    "Начало: <b>{started} (МСК)</b>\n"
    "Дедлайн прохождения: <b>{deadline} (МСК)</b>\n\n"
    "У тебя есть <b>35 минут</b> на выполнение всех заданий (письменных и видеоинтервью)."
)

TIMEOUT_TEXT = (
    "⏰ <b>Время на прохождение 2-го этапа истекло!</b>\n\n"
    "Пожалуйста, заверши отправку оставшихся ответов как можно скорее."
)


def _on_timer_expired(user_id: int, bot=None) -> None:
    """Callback when timer expires"""
    logger.info("[STAGE2_TIMER] Timer expired for user_id=%d", user_id)
    _active_timers.pop(user_id, None)
    if bot:
        asyncio.create_task(_send_timeout_notification(user_id, bot))


async def _send_timeout_notification(user_id: int, bot) -> None:
    try:
        await bot.send_message(user_id, TIMEOUT_TEXT)
    except Exception as e:
        logger.warning("[STAGE2_TIMER] Could not send timeout notification to %d: %s", user_id, e)


def schedule_user_timer(user_id: int, bot=None, minutes: int = STAGE2_DURATION_MIN) -> None:
    """Schedule expiration timer for a user"""
    cancel_user_timer(user_id)
    loop = asyncio.get_running_loop()
    handle = loop.call_later(minutes * 60, _on_timer_expired, user_id, bot)
    _active_timers[user_id] = handle
    logger.info("[STAGE2_TIMER] Scheduled %d min timer for user_id=%d", minutes, user_id)


def cancel_user_timer(user_id: int) -> None:
    """Cancel timer for a user if active"""
    handle = _active_timers.pop(user_id, None)
    if handle:
        handle.cancel()
        logger.info("[STAGE2_TIMER] Cancelled timer for user_id=%d", user_id)
