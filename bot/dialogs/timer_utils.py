"""
Утилиты для работы с таймерами в диалогах
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from aiogram_dialog import DialogManager, BaseDialogManager
from aiogram_dialog.widgets.text import Format, Const, Progress
from aiogram_dialog.widgets.kbd import Button

logger = logging.getLogger(__name__)


async def start_timer_background(dialog_manager: DialogManager, timer_key: str, 
                                duration: int, on_timeout_callback=None):
    """Запустить таймер в фоновом режиме согласно документации aiogram-dialog"""
    try:
        # Инициализируем данные таймера
        dialog_manager.dialog_data[f"{timer_key}_start_time"] = datetime.now().timestamp()
        dialog_manager.dialog_data[f"{timer_key}_duration"] = duration
        dialog_manager.dialog_data[f"{timer_key}_remaining"] = duration
        dialog_manager.dialog_data[f"{timer_key}_timeout"] = False
        
        # Создаем фоновую задачу для таймера
        asyncio.create_task(timer_countdown_bg(dialog_manager.bg(), timer_key, duration, on_timeout_callback))
        
        logger.info(f"Timer started: {timer_key}, duration: {duration}s")
        
    except Exception as e:
        logger.error(f"Error starting timer {timer_key}: {e}")


async def timer_countdown_bg(bg_manager: BaseDialogManager, timer_key: str, 
                           duration: int, on_timeout_callback=None):
    """Фоновый обратный отсчет таймера"""
    try:
        # Обновляем прогресс каждую секунду
        for remaining in range(duration, 0, -1):
            await asyncio.sleep(1)
            
            # Вычисляем прогресс (от 100 до 0)
            progress = (remaining / duration) * 100
            
            # Обновляем данные через background manager
            await bg_manager.update({
                f"{timer_key}_remaining": remaining,
                f"{timer_key}_progress": progress,
                f"{timer_key}_minutes": remaining // 60,
                f"{timer_key}_seconds": remaining % 60,
            })
        
        # Время истекло
        await bg_manager.update({
            f"{timer_key}_remaining": 0,
            f"{timer_key}_progress": 0,
            f"{timer_key}_minutes": 0,
            f"{timer_key}_seconds": 0,
            f"{timer_key}_timeout": True,
        })
        
        # Вызываем callback если есть
        if on_timeout_callback:
            await on_timeout_callback(bg_manager, timer_key)
            
        logger.info(f"Timer timeout: {timer_key}")
        
    except asyncio.CancelledError:
        logger.info(f"Timer cancelled: {timer_key}")
    except Exception as e:
        logger.error(f"Timer error for {timer_key}: {e}")


def get_timer_progress_data(timer_key: str):
    """Геттер для данных прогресса таймера"""
    async def getter(dialog_manager: DialogManager, **kwargs):
        remaining = dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)
        duration = dialog_manager.dialog_data.get(f"{timer_key}_duration", 1)
        
        # Вычисляем прогресс (от 100 до 0)
        progress = dialog_manager.dialog_data.get(f"{timer_key}_progress", 0)
        if progress == 0 and remaining > 0:
            progress = (remaining / duration) * 100
        
        return {
            "timer_remaining": remaining,
            "timer_duration": duration,
            "timer_progress": max(0, min(100, progress)),
            "timer_minutes": dialog_manager.dialog_data.get(f"{timer_key}_minutes", remaining // 60),
            "timer_seconds": dialog_manager.dialog_data.get(f"{timer_key}_seconds", remaining % 60),
            "timer_timeout": dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
        }
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
        # Отмечаем таймаут в данных
        await bg_manager.update({
            f"{timer_key}_answer": "",
            f"{timer_key}_time_taken": bg_manager.dialog_data.get(f"{timer_key}_duration", 0),
            f"{timer_key}_timeout": True,
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