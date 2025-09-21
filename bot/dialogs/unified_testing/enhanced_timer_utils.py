"""
Улучшенная система таймеров с поддержкой user-based ключей
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from aiogram_dialog import DialogManager, BaseDialogManager
from aiogram_dialog.widgets.text import Format, Progress
from aiogram_dialog.api.exceptions import OutdatedIntent

logger = logging.getLogger(__name__)


class EnhancedTimerManager:
    """Улучшенный менеджер таймеров с изоляцией по пользователям"""
    
    def __init__(self):
        # Структура: user_id -> {timer_key -> task}
        self.user_timers: Dict[int, Dict[str, asyncio.Task]] = {}
        # Глобальный индекс всех активных таймеров для совместимости
        self.global_timers: Dict[str, asyncio.Task] = {}
    
    def _extract_user_id_from_key(self, timer_key: str) -> Optional[int]:
        """Извлечение user_id из ключа таймера"""
        try:
            # Ожидаемый формат: user_{user_id}_{test_type}_q{question}
            if timer_key.startswith("user_"):
                parts = timer_key.split("_")
                if len(parts) >= 2:
                    return int(parts[1])
        except (ValueError, IndexError):
            pass
        return None
    
    async def start_timer_background(self, dialog_manager: DialogManager, timer_key: str, 
                                   duration: int, on_timeout_callback=None):
        """Запуск таймера в фоновом режиме с user-based изоляцией"""
        try:
            user_id = self._extract_user_id_from_key(timer_key)
            if user_id is None:
                # Fallback для старых ключей
                user_id = dialog_manager.event.from_user.id if dialog_manager.event else 0
                logger.warning(f"Could not extract user_id from timer_key {timer_key}, using {user_id}")
            
            # Проверяем, не запущен ли уже таймер
            if self._is_timer_active(user_id, timer_key):
                logger.debug(f"Timer {timer_key} already active for user {user_id}, skipping")
                return
            
            logger.debug(f"Starting timer {timer_key} for user {user_id}, duration: {duration}s")
            
            # Останавливаем предыдущий таймер если есть
            await self._stop_timer_internal(user_id, timer_key)
            
            # Инициализируем данные таймера
            dialog_manager.dialog_data[f"{timer_key}_start_time"] = datetime.now().timestamp()
            dialog_manager.dialog_data[f"{timer_key}_duration"] = duration
            dialog_manager.dialog_data[f"{timer_key}_remaining"] = duration
            dialog_manager.dialog_data[f"{timer_key}_timeout"] = False
            dialog_manager.dialog_data[f"{timer_key}_stopped"] = False
            
            # Создаем фоновую задачу
            task = asyncio.create_task(
                self._timer_countdown_bg(dialog_manager.bg(), timer_key, duration, on_timeout_callback)
            )
            
            # Сохраняем в структурах данных
            if user_id not in self.user_timers:
                self.user_timers[user_id] = {}
            self.user_timers[user_id][timer_key] = task
            self.global_timers[timer_key] = task  # для совместимости
            
            logger.info(f"Timer started: {timer_key} for user {user_id}, duration: {duration}s")
            
        except Exception as e:
            logger.error(f"Error starting timer {timer_key}: {e}", exc_info=True)
    
    async def _timer_countdown_bg(self, bg_manager: BaseDialogManager, timer_key: str, 
                                duration: int, on_timeout_callback=None):
        """Фоновый обратный отсчет таймера"""
        try:
            user_id = self._extract_user_id_from_key(timer_key)
            logger.debug(f"Starting countdown for {timer_key}, user {user_id}, duration={duration}")
            
            # Обновляем прогресс каждые 2 секунды
            elapsed = 0
            while elapsed < duration:
                await asyncio.sleep(2)
                elapsed += 2
                
                # Проверяем, что задача не была отменена
                current_task = asyncio.current_task()
                if current_task and current_task.cancelled():
                    logger.debug(f"Timer {timer_key} cancelled")
                    return
                
                # Проверяем, что таймер все еще активен
                if not self._is_timer_active(user_id, timer_key):
                    logger.debug(f"Timer {timer_key} no longer active")
                    return
                
                actual_remaining = max(0, duration - elapsed)
                progress = (actual_remaining / duration) * 100
                
                # Обновляем данные через background manager
                try:
                    await bg_manager.update({
                        f"{timer_key}_remaining": actual_remaining,
                        f"{timer_key}_progress": progress,
                        f"{timer_key}_minutes": actual_remaining // 60,
                        f"{timer_key}_seconds": actual_remaining % 60,
                    })
                except OutdatedIntent as e:
                    # OutdatedIntent - это нормально при переходах между диалогами
                    logger.debug(f"Timer {timer_key} context outdated (OutdatedIntent), stopping timer gracefully: {e}")
                    return
                except Exception as e:
                    # Другие ошибки
                    error_type = type(e).__name__
                    logger.debug(f"Error updating bg_manager for {timer_key}: {error_type}: {e}")
                    return
            
            # Время истекло - вызываем callback
            logger.debug(f"Timer {timer_key} timed out")
            
            try:
                await bg_manager.update({
                    f"{timer_key}_remaining": 0,
                    f"{timer_key}_progress": 0,
                    f"{timer_key}_minutes": 0,
                    f"{timer_key}_seconds": 0,
                    f"{timer_key}_timeout": True,
                })
            except OutdatedIntent as e:
                # OutdatedIntent при timeout - это нормально
                logger.debug(f"Timer {timer_key} context outdated during timeout (OutdatedIntent), stopping gracefully: {e}")
            except Exception as e:
                # Другие ошибки
                error_type = type(e).__name__
                logger.debug(f"Error updating timeout data for {timer_key}: {error_type}: {e}")
            
            if on_timeout_callback:
                try:
                    logger.debug(f"Calling timeout callback for {timer_key}")
                    await on_timeout_callback(bg_manager, timer_key)
                    logger.debug(f"Timeout callback completed for {timer_key}")
                except Exception as e:
                    logger.error(f"Error in timeout callback for {timer_key}: {e}", exc_info=True)
            
            logger.info(f"Timer timeout: {timer_key}")
            
        except asyncio.CancelledError:
            logger.info(f"Timer cancelled: {timer_key}")
            raise
        except Exception as e:
            logger.error(f"Timer error for {timer_key}: {e}", exc_info=True)
        finally:
            # Очищаем из структур данных
            await self._cleanup_timer(user_id, timer_key)
    
    def _is_timer_active(self, user_id: Optional[int], timer_key: str) -> bool:
        """Проверка активности таймера"""
        if user_id and user_id in self.user_timers:
            if timer_key in self.user_timers[user_id]:
                task = self.user_timers[user_id][timer_key]
                return not task.done()
        return False
    
    async def _stop_timer_internal(self, user_id: Optional[int], timer_key: str):
        """Внутренняя остановка таймера"""
        if user_id and user_id in self.user_timers:
            if timer_key in self.user_timers[user_id]:
                task = self.user_timers[user_id][timer_key]
                if not task.done():
                    task.cancel()
                    logger.debug(f"Timer task cancelled: {timer_key}")
                del self.user_timers[user_id][timer_key]
        
        # Также удаляем из глобального индекса
        if timer_key in self.global_timers:
            del self.global_timers[timer_key]
    
    async def _cleanup_timer(self, user_id: Optional[int], timer_key: str):
        """Очистка таймера из всех структур данных"""
        if user_id and user_id in self.user_timers:
            if timer_key in self.user_timers[user_id]:
                del self.user_timers[user_id][timer_key]
                
            # Удаляем пустые записи пользователей
            if not self.user_timers[user_id]:
                del self.user_timers[user_id]
        
        if timer_key in self.global_timers:
            del self.global_timers[timer_key]
    
    async def stop_timer(self, dialog_manager: DialogManager, timer_key: str):
        """Остановка конкретного таймера"""
        try:
            user_id = self._extract_user_id_from_key(timer_key)
            if user_id is None:
                user_id = dialog_manager.event.from_user.id if dialog_manager.event else 0
            
            await self._stop_timer_internal(user_id, timer_key)
            
            # Отмечаем остановку в dialog_data
            dialog_manager.dialog_data[f"{timer_key}_stopped"] = True
            
            logger.info(f"Timer stopped: {timer_key} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error stopping timer {timer_key}: {e}", exc_info=True)
    
    async def stop_all_user_timers(self, user_id: int):
        """Остановка всех таймеров пользователя"""
        if user_id not in self.user_timers:
            logger.debug(f"No active timers for user {user_id}")
            return
        
        timer_keys = list(self.user_timers[user_id].keys())
        for timer_key in timer_keys:
            await self._stop_timer_internal(user_id, timer_key)
        
        logger.info(f"Stopped {len(timer_keys)} timers for user {user_id}: {timer_keys}")
    
    async def stop_all_timers(self):
        """Остановка всех активных таймеров"""
        total_stopped = 0
        for user_id in list(self.user_timers.keys()):
            timer_count = len(self.user_timers[user_id])
            await self.stop_all_user_timers(user_id)
            total_stopped += timer_count
        
        logger.info(f"Stopped all timers: {total_stopped} total")
    
    def calculate_time_taken(self, dialog_manager: DialogManager, timer_key: str) -> int:
        """Вычисление времени, потраченного на ответ"""
        try:
            start_time = dialog_manager.dialog_data.get(f"{timer_key}_start_time")
            remaining = dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)
            duration = dialog_manager.dialog_data.get(f"{timer_key}_duration", 0)
            
            if start_time is None or duration == 0:
                return 0
            
            time_taken = duration - remaining
            return max(0, min(time_taken, duration))
            
        except Exception:
            return 0
    
    def get_timer_progress_data(self, timer_key: str):
        """Геттер для данных прогресса таймера"""
        async def getter(dialog_manager: DialogManager, **kwargs):
            remaining = dialog_manager.dialog_data.get(f"{timer_key}_remaining", 0)
            duration = dialog_manager.dialog_data.get(f"{timer_key}_duration", 1)
            timeout = dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
            
            progress = dialog_manager.dialog_data.get(f"{timer_key}_progress", 0)
            minutes = remaining // 60
            seconds = remaining % 60
            
            # Если таймер еще не запущен, показываем полное время
            if remaining == 0 and not timeout:
                # Используем длительность из dialog_data если есть
                if duration > 1:
                    remaining = duration
                    progress = 100.0
                    minutes = remaining // 60
                    seconds = remaining % 60
            
            # Если прогресс не установлен, вычисляем его
            if progress == 0 and remaining > 0 and duration > 0:
                progress = (remaining / duration) * 100
            
            result = {
                "timer_remaining": remaining,
                "timer_duration": duration,
                "timer_progress": max(0, min(100, progress)),
                "timer_minutes": minutes,
                "timer_seconds": seconds,
                "timer_timeout": timeout
            }
            
            return result
        return getter
    
    def create_timer_display(self, timer_key: str):
        """Создание виджетов отображения таймера"""
        return [
            Format("⏱️ Оставшееся время: {timer_minutes:02d}:{timer_seconds:02d}"),
            Progress(
                "timer_progress",
                filled="🟩",
                empty="⬜",
                width=10
            )
        ]
    
    def get_user_timer_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики таймеров пользователя"""
        if user_id not in self.user_timers:
            return {"active_timers": 0, "timer_keys": [], "active_count": 0, "timers": []}
        
        active_timers = []
        for timer_key, task in self.user_timers[user_id].items():
            if task and not task.done():
                active_timers.append(timer_key)
        
        # Для обратной совместимости возвращаем два формата
        return {
            "active_timers": len(active_timers),
            "timer_keys": active_timers,
            "active_count": len(active_timers),
            "timers": list(self.user_timers[user_id].keys()),
        }
    
    def _is_timer_active(self, user_id: int, timer_key: str) -> bool:
        """Проверка активности конкретного таймера"""
        if user_id not in self.user_timers:
            return False
        
        task = self.user_timers[user_id].get(timer_key)
        return task is not None and not task.done()


# Глобальный экземпляр менеджера таймеров
enhanced_timer_manager = EnhancedTimerManager()