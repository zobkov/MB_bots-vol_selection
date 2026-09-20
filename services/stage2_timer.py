"""Background timer service for Stage 2 testing (Basic & Individual modes)."""

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

# Default duration for basic whole stage 2 (35 minutes = 2100 seconds)
DEFAULT_STAGE2_DURATION_SEC = 35 * 60
MSK_OFFSET = timedelta(hours=3)

# Timer mode: "basic" or "ind"
_timer_mode: str = "basic"

# Configurable basic duration
_current_duration_sec: int = DEFAULT_STAGE2_DURATION_SEC

# Configurable individual question durations
_ind_written_sec: int = 180  # 3 minutes for written questions (q1, q2, q3)
_ind_video_sec: int = 180    # 3 minutes for video questions (vq1..vq5)
_ind_grace_sec: int = 30     # 30 seconds grace period for video upload

# Active timers: user_id -> list of asyncio.TimerHandle (for warnings + final timeout + grace period)
_active_user_timers: dict[int, list[asyncio.TimerHandle]] = {}

# Background dialog manager factory from aiogram_dialog
_bg_manager_factory: Any = None


def set_bg_manager_factory(factory: Any) -> None:
    """Register aiogram_dialog BgManagerFactory."""
    global _bg_manager_factory
    _bg_manager_factory = factory
    logger.info("[STAGE2_TIMER] BgManagerFactory registered successfully")


def get_timer_mode() -> str:
    """Get active timer mode: 'basic' or 'ind'."""
    return _timer_mode


def set_timer_mode(mode: str) -> None:
    """Set active timer mode: 'basic' or 'ind'."""
    global _timer_mode
    if mode in ("basic", "ind"):
        _timer_mode = mode
        logger.info("[STAGE2_TIMER] Timer mode set to: %s", _timer_mode)


def get_stage2_duration_sec() -> int:
    """Get current configured duration in seconds (for basic mode)."""
    return _current_duration_sec


def set_stage2_duration_sec(seconds: int) -> None:
    """Set configured duration in seconds (for basic mode)."""
    global _current_duration_sec
    _current_duration_sec = max(5, seconds)
    logger.info("[STAGE2_TIMER] Basic duration updated to %d seconds", _current_duration_sec)


def get_ind_timer_settings() -> tuple[int, int, int]:
    """Get individual timer settings: (written_sec, video_sec, grace_sec)."""
    return _ind_written_sec, _ind_video_sec, _ind_grace_sec


def set_ind_timer_settings(written_sec: int, video_sec: int, grace_sec: int) -> None:
    """Set individual timer settings."""
    global _ind_written_sec, _ind_video_sec, _ind_grace_sec
    _ind_written_sec = max(5, written_sec)
    _ind_video_sec = max(5, video_sec)
    _ind_grace_sec = max(0, grace_sec)
    logger.info(
        "[STAGE2_TIMER] Ind timer settings updated: written=%ds, video=%ds, grace=%ds",
        _ind_written_sec,
        _ind_video_sec,
        _ind_grace_sec,
    )


def format_duration(seconds: int) -> str:
    """Format seconds into readable Russian string."""
    if seconds < 60:
        return f"{seconds} сек."
    mins = seconds // 60
    rem_sec = seconds % 60
    if rem_sec == 0:
        return f"{mins} мин."
    return f"{mins} мин. {rem_sec} сек."


# ============================================================================
# ТЕКСТЫ ОПОВЕЩЕНИЙ
# ============================================================================

STARTED_TEXT = (
    "<b>Время пошло!</b>\n\n"
    "Начало: <b>{started} (МСК)</b>\n"
    "Дедлайн прохождения: <b>{deadline} (МСК)</b>\n\n"
    "У тебя есть <b>{duration}</b> на выполнение всех заданий (письменных и видеоинтервью)."
)

STARTED_IND_WRITTEN_TEXT = (
    "<b>Вопрос открыт!</b>\n\n"
    "На выполнение этого вопроса у тебя есть <b>{duration}</b>.\n"
    "После окончания времени бот автоматически переведет тебя к следующему вопросу."
)

STARTED_IND_VIDEO_TEXT = (
    "<b>Видео-вопрос открыт!</b>\n\n"
    "На подготовку и отправку видео-кружка у тебя есть <b>{duration}</b>.\n"
    "Пожалуйста, начни запись кружка заранее."
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
    "❗ <b>Основное время на прохождение 2-го этапа вышло!</b>\n\n"
    "Через <b>{grace_duration}</b> тестирование автоматически завершится, "
    "и все сохраненные ответы будут зафиксированы."
)

FINAL_TERMINATED_TEXT = (
    "✅ <b>Тестирование завершено!</b>\n\n"
    "Время на выполнение заданий 2-го этапа истекло. Твои ответы были автоматически сохранены."
)

# Индивидуальные уведомления для письменных вопросов
IND_WRITTEN_WARN_2MIN = "⏳ До перехода к следующему вопросу осталось: <b>2 минуты</b>."
IND_WRITTEN_WARN_1MIN = "⏳ До перехода к следующему вопросу осталась: <b>1 минута</b>. Завершай мысль и отправляй ответ."
IND_WRITTEN_WARN_30SEC = "⚠️ До перехода к следующему вопросу осталось <b>30 секунд</b>! Пожалуйста, отправь написанный текст прямо сейчас."

# Индивидуальные уведомления для видео-вопросов
IND_VIDEO_WARN_2MIN = "⏳ На обдумывание ответа осталось <b>2 минуты</b>."
IND_VIDEO_WARN_1MIN = "⏳ Осталась <b>1 минута</b>! Самое время начать запись видео-кружка."
IND_VIDEO_WARN_30SEC = "⚠️ Осталось <b>30 секунд</b>! Твой видео-кружок уже должен отправляться и загружаться."
IND_VIDEO_GRACE_STARTED = (
    "⏰ <b>Основное время на вопрос вышло!</b>\n\n"
    "У тебя есть еще <b>{grace_duration}</b>, чтобы видео-кружок успел догрузиться. "
    "После этого бот автоматически переключит задание."
)
IND_QUESTION_TIMEOUT_TEXT = "❗ <b>Время на текущий вопрос вышло!</b> Переходим дальше..."


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


# ============================================================================
# BASIC РЕЖИМ (Глобальный таймер)
# ============================================================================

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
    """Callback when main timer expires: send alert and start grace period."""
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

    loop = asyncio.get_running_loop()
    h_grace = loop.call_later(grace_sec, _on_grace_period_expired, user_id, bot)
    _active_user_timers[user_id] = [h_grace]
    logger.info(
        "[STAGE2_TIMER] Scheduled grace period timer (%d sec) for user_id=%d",
        grace_sec,
        user_id,
    )


def schedule_user_timer(user_id: int, bot=None, seconds: Optional[int] = None) -> None:
    """Schedule basic global expiration timer and proportional warning notifications for a user."""
    cancel_user_timer(user_id)
    duration = seconds if seconds is not None else _current_duration_sec
    loop = asyncio.get_running_loop()
    handles: list[asyncio.TimerHandle] = []

    # 1. Half-time warning (50% elapsed, 50% remaining)
    half_time = duration / 2.0
    if half_time >= 5:
        remaining_half_str = format_duration(int(duration - half_time))
        msg_half = WARNING_HALF_TEXT.format(remaining=remaining_half_str)
        h_half = loop.call_later(half_time, _trigger_warning, user_id, msg_half, bot)
        handles.append(h_half)

    # 2. Final warning (80% elapsed, 20% remaining)
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
        "[STAGE2_TIMER] Scheduled basic timer (%d sec, %d alerts) for user_id=%d",
        duration,
        len(handles),
        user_id,
    )


# ============================================================================
# INDIVIDUAL РЕЖИМ (Индивидуальный таймер на каждый вопрос)
# ============================================================================

# Карта переходов между вопросами
_NEXT_QUESTION_MAP = {
    "q1_about_mb": ("q2_motivation", Stage2SG.q2_motivation, False),
    "q2_motivation": ("q3_well_organized", Stage2SG.q3_well_organized, False),
    "q3_well_organized": ("video_intro", Stage2SG.video_intro, False),
    "vq1": ("vq2", Stage2SG.vq2, True),
    "vq2": ("vq3", Stage2SG.vq3, True),
    "vq3": ("vq4", Stage2SG.vq4, True),
    "vq4": ("vq5", Stage2SG.vq5, True),
    "vq5": ("success", Stage2SG.success, False),
}


async def _auto_advance_individual_question(user_id: int, current_question_key: str, bot) -> None:
    """Auto advance user to the next question when individual timer runs out."""
    logger.info(
        "[STAGE2_TIMER] Auto advancing user %d from question %s",
        user_id,
        current_question_key,
    )
    _active_user_timers.pop(user_id, None)

    next_info = _NEXT_QUESTION_MAP.get(current_question_key)
    if not next_info:
        return

    next_key, next_state, is_next_video = next_info

    # 1. Если это был последний вопрос vq5 — финализируем в БД
    if current_question_key == "vq5":
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
            finally:
                await session.close()
                await db.close()
        except Exception as e:
            logger.error("[STAGE2_TIMER] Failed to mark completed on ind timeout for %d: %s", user_id, e)

    # 2. Уведомление пользователю
    if current_question_key == "vq5":
        await _safe_send_message(user_id, FINAL_TERMINATED_TEXT, bot)
    else:
        await _safe_send_message(user_id, IND_QUESTION_TIMEOUT_TEXT, bot)

    # 3. Переключаем окно диалога
    if _bg_manager_factory and bot:
        try:
            bg_manager = _bg_manager_factory.bg(bot=bot, user_id=user_id, chat_id=user_id)
            await bg_manager.switch_to(next_state, show_mode=ShowMode.DELETE_AND_SEND)
            logger.info("[STAGE2_TIMER] User %d switched to state %s", user_id, next_state)
        except Exception as e:
            logger.error("[STAGE2_TIMER] Failed to switch dialog state for %d: %s", user_id, e)

    # 4. Если следующий вопрос требует индивидуального таймера (q2, q3, vq2..vq5) — запускаем его
    if next_key in ("q2_motivation", "q3_well_organized", "vq2", "vq3", "vq4", "vq5"):
        schedule_individual_question_timer(user_id, next_key, bot)


def _on_ind_video_grace_expired(user_id: int, question_key: str, bot=None) -> None:
    """Callback when individual video grace period expires."""
    logger.info("[STAGE2_TIMER] Ind video grace expired for user %d on %s", user_id, question_key)
    if bot:
        asyncio.create_task(_auto_advance_individual_question(user_id, question_key, bot))


def _on_ind_video_main_expired(user_id: int, question_key: str, bot=None, grace_sec: int = 30) -> None:
    """Callback when individual video main timer expires -> send grace warning."""
    logger.info("[STAGE2_TIMER] Ind video main timer expired for user %d on %s", user_id, question_key)
    if grace_sec > 0:
        msg = IND_VIDEO_GRACE_STARTED.format(grace_duration=format_duration(grace_sec))
        if bot:
            asyncio.create_task(_safe_send_message(user_id, msg, bot))

        loop = asyncio.get_running_loop()
        h_grace = loop.call_later(grace_sec, _on_ind_video_grace_expired, user_id, question_key, bot)
        _active_user_timers[user_id] = [h_grace]
    else:
        if bot:
            asyncio.create_task(_auto_advance_individual_question(user_id, question_key, bot))


def _on_ind_written_expired(user_id: int, question_key: str, bot=None) -> None:
    """Callback when individual written timer expires -> auto advance."""
    logger.info("[STAGE2_TIMER] Ind written timer expired for user %d on %s", user_id, question_key)
    if bot:
        asyncio.create_task(_auto_advance_individual_question(user_id, question_key, bot))


def schedule_individual_question_timer(user_id: int, question_key: str, bot=None) -> None:
    """
    Schedule individual timers and notifications for specific question (q1..q3, vq1..vq5).
    """
    cancel_user_timer(user_id)
    loop = asyncio.get_running_loop()
    handles: list[asyncio.TimerHandle] = []

    is_video = question_key.startswith("vq")
    total_duration = _ind_video_sec if is_video else _ind_written_sec
    grace_sec = _ind_grace_sec if is_video else 0

    # 1. Оповещения за 2 мин (120 сек), 1 мин (60 сек) и 30 сек
    # Если таймер стандартный (например 180с):
    # - за 2 мин: через 60с (осталось 120с)
    # - за 1 мин: через 120с (осталось 60с)
    # - за 30 сек: через 150с (осталось 30с)
    if total_duration >= 180:
        # 120 сек до конца -> через total_duration - 120
        t_2min = total_duration - 120
        msg_2min = IND_VIDEO_WARN_2MIN if is_video else IND_WRITTEN_WARN_2MIN
        h_2min = loop.call_later(t_2min, _trigger_warning, user_id, msg_2min, bot)
        handles.append(h_2min)

        # 60 сек до конца -> через total_duration - 60
        t_1min = total_duration - 60
        msg_1min = IND_VIDEO_WARN_1MIN if is_video else IND_WRITTEN_WARN_1MIN
        h_1min = loop.call_later(t_1min, _trigger_warning, user_id, msg_1min, bot)
        handles.append(h_1min)

        # 30 сек до конца -> через total_duration - 30
        t_30sec = total_duration - 30
        msg_30sec = IND_VIDEO_WARN_30SEC if is_video else IND_WRITTEN_WARN_30SEC
        h_30sec = loop.call_later(t_30sec, _trigger_warning, user_id, msg_30sec, bot)
        handles.append(h_30sec)
    else:
        # Для коротких тестовых длительностей (< 180 сек) пропорционально:
        # 50% времени
        half_t = total_duration * 0.5
        if half_t >= 4:
            rem_str = format_duration(int(total_duration - half_t))
            msg_half = (
                f"⏳ Осталось <b>{rem_str}</b>! Самое время начать запись кружка."
                if is_video
                else f"⏳ До конца вопроса осталось: <b>{rem_str}</b>."
            )
            h_half = loop.call_later(half_t, _trigger_warning, user_id, msg_half, bot)
            handles.append(h_half)

        # 80% времени
        last_t = total_duration * 0.8
        if total_duration >= 20 and (total_duration - last_t) >= 4 and last_t > half_t:
            rem_str = format_duration(int(total_duration - last_t))
            msg_last = (
                f"⚠️ Осталось <b>{rem_str}</b>! Кружок должен отправляться."
                if is_video
                else f"⚠️ До конца вопроса осталось <b>{rem_str}</b>! Отправляй текст."
            )
            h_last = loop.call_later(last_t, _trigger_warning, user_id, msg_last, bot)
            handles.append(h_last)

    # 2. Окончание основного времени вопроса
    if is_video:
        h_main = loop.call_later(total_duration, _on_ind_video_main_expired, user_id, question_key, bot, grace_sec)
        handles.append(h_main)
    else:
        h_main = loop.call_later(total_duration, _on_ind_written_expired, user_id, question_key, bot)
        handles.append(h_main)

    _active_user_timers[user_id] = handles
    logger.info(
        "[STAGE2_TIMER] Scheduled ind timer for user %d on %s (duration=%ds, grace=%ds, %d alerts)",
        user_id,
        question_key,
        total_duration,
        grace_sec,
        len(handles),
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


