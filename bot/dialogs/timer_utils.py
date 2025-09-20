"""
Утилиты для работы с таймерами в диалогах
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from aiogram_dialog import DialogManager, BaseDialogManager, StartMode
from aiogram_dialog.widgets.text import Format, Const, Progress
from aiogram_dialog.widgets.kbd import Button

logger = logging.getLogger(__name__)

# Глобальный словарь для отслеживания активных таймеров
active_timers: Dict[str, asyncio.Task] = {}


async def stop_active_timer(timer_key: str):
    """Остановить активный таймер по ключу"""
    if timer_key in active_timers:
        task = active_timers[timer_key]
        if not task.done():
            task.cancel()
            logger.info(f"Timer cancelled: {timer_key}")
        del active_timers[timer_key]


async def stop_all_user_timers(user_id: int):
    """Остановить все активные таймеры пользователя"""
    user_timer_keys = []
    
    # Собираем все ключи таймеров пользователя
    for timer_key in list(active_timers.keys()):
        # Предполагаем, что ключи таймеров содержат информацию о пользователе
        # Например: "general_q1_123456789" или "logistics_q2_123456789"
        if str(user_id) in timer_key:
            user_timer_keys.append(timer_key)
    
    # Останавливаем найденные таймеры
    for timer_key in user_timer_keys:
        await stop_active_timer(timer_key)
    
    if user_timer_keys:
        logger.info(f"Stopped {len(user_timer_keys)} timers for user {user_id}: {user_timer_keys}")
    else:
        logger.debug(f"No active timers found for user {user_id}")


async def stop_all_user_timers_simple():
    """Остановить все активные таймеры (простая версия для случаев без user_id)"""
    timer_keys_to_stop = list(active_timers.keys())
    
    for timer_key in timer_keys_to_stop:
        await stop_active_timer(timer_key)
    
    if timer_keys_to_stop:
        logger.info(f"Stopped all active timers: {timer_keys_to_stop}")
    else:
        logger.debug("No active timers to stop")


async def cancel_dialog_with_timers(callback, button, dialog_manager: DialogManager):
    """Кастомный обработчик отмены диалога с остановкой таймеров"""
    try:
        # Останавливаем все таймеры (простая версия)
        await stop_all_user_timers_simple()
        
        # Возвращаемся в главное меню
        from bot.states import MenuSG
        await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)
        
    except Exception as e:
        logger.error(f"Error in cancel_dialog_with_timers: {e}")
        # Fallback: просто закрываем диалог
        await dialog_manager.done()


async def start_timer_background(dialog_manager: DialogManager, timer_key: str, 
                                duration: int, on_timeout_callback=None):
    """Запустить таймер в фоновом режиме согласно документации aiogram-dialog"""
    try:
        # Проверяем, не запущен ли уже таймер или не остановлен ли он
        if (timer_key in active_timers and not active_timers[timer_key].done()) or \
           dialog_manager.dialog_data.get(f"{timer_key}_stopped", False):
            logger.debug(f"🔧 DEBUG: Таймер {timer_key} уже запущен или остановлен, пропускаем")
            return
            
        logger.debug(f"🔧 DEBUG: Запуск таймера {timer_key} на {duration}s")
        
        # Останавливаем предыдущий таймер если он есть
        await stop_active_timer(timer_key)
        
        # Инициализируем данные таймера
        dialog_manager.dialog_data[f"{timer_key}_start_time"] = datetime.now().timestamp()
        dialog_manager.dialog_data[f"{timer_key}_duration"] = duration
        dialog_manager.dialog_data[f"{timer_key}_remaining"] = duration
        dialog_manager.dialog_data[f"{timer_key}_timeout"] = False
        dialog_manager.dialog_data[f"{timer_key}_stopped"] = False
        
        logger.debug(f"🔧 DEBUG: Данные таймера {timer_key} инициализированы")
        
        # Создаем фоновую задачу для таймера, передаем bg_manager
        task = asyncio.create_task(timer_countdown_bg(dialog_manager.bg(), timer_key, duration, on_timeout_callback))
        active_timers[timer_key] = task
        logger.debug(f"🔧 DEBUG: Фоновая задача для {timer_key} создана: {task}")
        
        logger.info(f"Timer started: {timer_key}, duration: {duration}s")
        
    except Exception as e:
        logger.error(f"Error starting timer {timer_key}: {e}", exc_info=True)


async def timer_countdown_bg(bg_manager: BaseDialogManager, timer_key: str, 
                           duration: int, on_timeout_callback=None):
    """Фоновый обратный отсчет таймера"""
    try:
        logger.debug(f"🔧 DEBUG: Начинаю обратный отсчет для {timer_key}, duration={duration}")
        
        # Обновляем прогресс каждые 2 секунды, чтобы избежать flood control
        for remaining in range(duration, 0, -2):
            await asyncio.sleep(2)
            
            # Проверяем, что задача не была отменена
            current_task = asyncio.current_task()
            if current_task and current_task.cancelled():
                logger.debug(f"🔧 DEBUG: {timer_key} - задача отменена, прекращаю обновления")
                break
            
            # Проверяем, что таймер все еще активен в глобальном списке
            if timer_key not in active_timers:
                logger.debug(f"🔧 DEBUG: {timer_key} - таймер удален из активных, прекращаю обновления")
                break
            
            # Проверяем, что остается время
            actual_remaining = max(0, remaining - 1)  # Учитываем что прошла еще одна секунда
            
            # Вычисляем прогресс (от 100 до 0)
            progress = (actual_remaining / duration) * 100
            
            logger.debug(f"🔧 DEBUG: {timer_key} remaining={actual_remaining}, progress={progress:.1f}%")
            
            # Обновляем данные через background manager только если таймер активен
            try:
                await bg_manager.update({
                    f"{timer_key}_remaining": actual_remaining,
                    f"{timer_key}_progress": progress,
                    f"{timer_key}_minutes": actual_remaining // 60,
                    f"{timer_key}_seconds": actual_remaining % 60,
                })
            except Exception as e:
                logger.debug(f"🔧 DEBUG: {timer_key} - ошибка обновления bg_manager: {e}, прекращаю обновления")
                break
            
            # Останавливаемся, если время истекло
            if actual_remaining <= 0:
                break
        
        # Проверяем еще раз, что задача не была отменена
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            logger.debug(f"🔧 DEBUG: {timer_key} - задача была отменена перед таймаутом")
            return
        
        # Время истекло
        logger.debug(f"🔧 DEBUG: {timer_key} - время истекло!")
        
        # Обновляем данные при таймауте
        try:
            await bg_manager.update({
                f"{timer_key}_remaining": 0,
                f"{timer_key}_progress": 0,
                f"{timer_key}_minutes": 0,
                f"{timer_key}_seconds": 0,
                f"{timer_key}_timeout": True,
            })
        except Exception as e:
            logger.debug(f"🔧 DEBUG: {timer_key} - ошибка обновления при таймауте: {e}")
        
        # Вызываем callback если есть
        if on_timeout_callback:
            logger.debug(f"🔧 DEBUG: {timer_key} - вызываю callback таймаута")
            try:
                await on_timeout_callback(bg_manager, timer_key)
            except Exception as e:
                logger.error(f"🔧 ERROR: Ошибка в callback таймаута {timer_key}: {e}", exc_info=True)
        
        logger.info(f"Timer timeout: {timer_key}")
        
    except asyncio.CancelledError:
        logger.info(f"Timer cancelled: {timer_key}")
        raise  # Важно: перебрасываем CancelledError
    except Exception as e:
        logger.error(f"Timer error for {timer_key}: {e}")
    finally:
        # Убираем таймер из активных
        if timer_key in active_timers:
            del active_timers[timer_key]


def get_timer_progress_data(timer_key: str):
    """Геттер для данных прогресса таймера"""
    async def getter(dialog_manager: DialogManager, **kwargs):
        # Получаем данные из dialog_data
        remaining = dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)
        duration = dialog_manager.dialog_data.get(f"{timer_key}_duration", 1)
        timeout = dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
        
        # Вычисляем прогресс и время
        progress = dialog_manager.dialog_data.get(f"{timer_key}_progress", 0)
        minutes = remaining // 60
        seconds = remaining % 60
        
        # Если таймер еще не запущен, показываем полное время
        if remaining == 0 and not timeout:
            # Получаем длительность из настроек таймера по ключу
            timer_durations = {
                "general_q1": 180,
                "general_q2": 30,
                "general_q3": 15,
                "general_q4": 15,
                "general_q5": 90,
                "general_q6": 30,
                "logistics_q1": 60,
                "logistics_q2": 90,
                "logistics_q3": 120,
                "logistics_q4": 60,
                "logistics_q5": 90,
                "logistics_q6": 60,
            }
            default_duration = timer_durations.get(timer_key, duration)
            remaining = default_duration
            duration = default_duration
            progress = 100.0  # Таймер еще не начался - 100% (обратный отсчет)
            minutes = remaining // 60
            seconds = remaining % 60
        
        # Если прогресс не установлен, вычисляем его
        if progress == 0 and remaining > 0 and duration > 0:
            progress = (remaining / duration) * 100
        
        logger.debug(f"🔧 DEBUG: Геттер {timer_key}: remaining={remaining}, duration={duration}, progress={progress:.1f}%, timeout={timeout}")
        
        result = {
            "timer_remaining": remaining,
            "timer_duration": duration,
            "timer_progress": max(0, min(100, progress)),
            "timer_minutes": minutes,
            "timer_seconds": seconds,
            "timer_timeout": timeout
        }
        
        logger.debug(f"🔧 DEBUG: Геттер {timer_key} возвращает: {result}")
        return result
    return getter


def create_timer_display(timer_key: str):
    """Создать виджеты для отображения таймера"""
    return [
        Format("⏱️ Оставшееся время: {timer_minutes:02d}:{timer_seconds:02d}"),
        Progress(
            "timer_progress",
            filled="🟩",
            empty="⬜",
            width=10
        )
    ]


async def handle_timeout_bg(bg_manager: BaseDialogManager, timer_key: str):
    """Обработчик таймаута для background manager"""
    try:
        # Останавливаем таймер
        await stop_active_timer(timer_key)
        
        # Отмечаем таймаут в данных (используем базовую длительность)
        await bg_manager.update({
            f"{timer_key}_answer": "",
            f"{timer_key}_timeout": True,
            f"{timer_key}_stopped": True,
        })
        
        # Переходим к следующему состоянию
        await bg_manager.next()
        
    except Exception as e:
        logger.error(f"Error handling timeout for {timer_key}: {e}")


def calculate_time_taken(dialog_manager: DialogManager, timer_key: str) -> int:
    """Вычислить время, потраченное на ответ"""
    try:
        start_time = dialog_manager.dialog_data.get(f"{timer_key}_start_time")
        remaining = dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)
        duration = dialog_manager.dialog_data.get(f"{timer_key}_duration", 0)
        
        if start_time is None or duration == 0:
            return 0
        
        # Время, потраченное на ответ
        time_taken = duration - remaining
        return max(0, min(time_taken, duration))
        
    except Exception:
        return 0


async def stop_timer(dialog_manager: DialogManager, timer_key: str):
    """Остановить таймер (отметить как завершенный)"""
    try:
        # Останавливаем активный таймер
        await stop_active_timer(timer_key)
        
        remaining = dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)
        dialog_manager.dialog_data[f"{timer_key}_stopped"] = True
        
        logger.info(f"Timer stopped: {timer_key}, remaining: {remaining}s")
        
    except Exception as e:
        logger.error(f"Error stopping timer {timer_key}: {e}")


# Устаревшие функции для совместимости (пока не обновим все диалоги)
class TimerManager:
    """Устаревший класс - для совместимости"""
    
    def __init__(self):
        self.active_timers: Dict[str, asyncio.Task] = {}
    
    async def start_timer(self, dialog_manager: DialogManager, timer_key: str, 
                         duration: int, on_timeout_callback=None):
        await start_timer_background(dialog_manager, timer_key, duration, on_timeout_callback)
    
    async def stop_timer(self, timer_key: str):
        pass  # Больше не нужно активно останавливать задачи
    
    async def get_remaining_time(self, dialog_manager: DialogManager, timer_key: str) -> int:
        return dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)


# Глобальный экземпляр для совместимости
timer_manager = TimerManager()