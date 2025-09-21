"""
APScheduler-based Enhanced Timer Utils for Unified Testing System
Replaces asyncio-based timers with persistent, Redis-backed scheduling
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.text import Format, Progress
from aiogram.types import User

from utils.scheduler_utils import (
    APSchedulerTimerManager, TimerConfig, TimerStats,
    get_scheduler_manager
)

logger = logging.getLogger(__name__)


@dataclass
class ProgressData:
    """Progress data for timer display"""
    timer_progress: float  # 0.0 to 100.0
    remaining_seconds: int
    total_seconds: int
    is_active: bool


class APSchedulerEnhancedTimerManager:
    """
    Enhanced Timer Manager using APScheduler for persistence
    
    Key improvements over old asyncio-based system:
    - Redis persistence survives bot restarts
    - User-isolated timer management
    - Automatic timeout handling
    - Progress tracking with countdown display
    """
    
    def __init__(self):
        self.scheduler_manager: Optional[APSchedulerTimerManager] = None
        self.active_timers: Dict[str, Dict[str, Any]] = {}  # timer_key -> metadata
        
    def _get_scheduler(self) -> APSchedulerTimerManager:
        """Get scheduler manager instance"""
        if self.scheduler_manager is None:
            self.scheduler_manager = get_scheduler_manager()
            if self.scheduler_manager is None:
                raise RuntimeError("Scheduler manager not initialized")
        return self.scheduler_manager
    
    def _generate_timer_key(self, user_id: int, test_type: str, question_number: int) -> str:
        """Generate user-isolated timer key"""
        return f"user_{user_id}_{test_type}_q{question_number}"
    
    def _parse_timer_key(self, timer_key: str) -> Optional[Dict[str, Any]]:
        """Parse timer key to extract components"""
        try:
            # Expected format: user_{user_id}_{test_type}_q{question_number}
            if timer_key.startswith("user_"):
                parts = timer_key.split("_")
                if len(parts) >= 4 and parts[-1].startswith("q"):
                    user_id = int(parts[1])
                    test_type = "_".join(parts[2:-1])
                    question_number = int(parts[-1][1:])
                    return {
                        "user_id": user_id,
                        "test_type": test_type,
                        "question_number": question_number
                    }
        except (ValueError, IndexError):
            pass
        return None
    
    async def start_timer_background(
        self,
        dialog_manager: DialogManager,
        timer_key: str,
        duration: int,
        on_timeout_callback: Optional[Callable] = None
    ) -> bool:
        """
        Start a timer using APScheduler
        
        Args:
            dialog_manager: Dialog manager instance
            timer_key: Timer identifier (user_{user_id}_{test_type}_q{question})
            duration: Timer duration in seconds
            on_timeout_callback: Optional callback for timeout handling
            
        Returns:
            bool: True if timer started successfully
        """
        try:
            scheduler = self._get_scheduler()
            
            # Parse timer key
            key_parts = self._parse_timer_key(timer_key)
            if not key_parts:
                logger.error(f"Invalid timer key format: {timer_key}")
                return False
            
            # Get user and chat info
            user: User = dialog_manager.event.from_user
            chat_id = dialog_manager.event.chat.id
            bot_token = dialog_manager.middleware_data.get("bot").token
            
            # Create timer configuration
            timer_config = TimerConfig(
                user_id=user.id,
                chat_id=chat_id,
                test_type=key_parts["test_type"],
                question_number=key_parts["question_number"],
                time_limit=duration,
                bot_token=bot_token
            )
            
            # Start scheduler timer
            job_id = await scheduler.start_question_timer(
                config=timer_config,
                timeout_callback=on_timeout_callback
            )
            
            # Store timer metadata
            self.active_timers[timer_key] = {
                "job_id": job_id,
                "start_time": datetime.utcnow(),
                "duration": duration,
                "user_id": user.id,
                "test_type": key_parts["test_type"],
                "question_number": key_parts["question_number"]
            }
            
            logger.info(f"APScheduler timer started: {timer_key} -> {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start APScheduler timer {timer_key}: {e}", exc_info=True)
            return False
    
    async def stop_timer(self, dialog_manager: DialogManager, timer_key: str) -> bool:
        """
        Stop a specific timer
        
        Args:
            dialog_manager: Dialog manager instance
            timer_key: Timer identifier
            
        Returns:
            bool: True if timer was stopped
        """
        try:
            scheduler = self._get_scheduler()
            
            # Get timer metadata
            timer_meta = self.active_timers.get(timer_key)
            if not timer_meta:
                logger.debug(f"Timer metadata not found: {timer_key}")
                return False
            
            # Cancel scheduler job
            job_id = timer_meta.get("job_id")
            if job_id:
                cancelled = await scheduler.cancel_timer(job_id)
                if cancelled:
                    logger.info(f"APScheduler timer stopped: {timer_key}")
                else:
                    logger.warning(f"APScheduler job not found: {job_id}")
            
            # Remove from active timers
            self.active_timers.pop(timer_key, None)
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop APScheduler timer {timer_key}: {e}", exc_info=True)
            return False
    
    async def stop_all_user_timers(self, user_id: int, test_type: Optional[str] = None) -> int:
        """
        Stop all timers for a specific user
        
        Args:
            user_id: User identifier
            test_type: Optional test type filter
            
        Returns:
            int: Number of stopped timers
        """
        try:
            scheduler = self._get_scheduler()
            
            # Cancel scheduler jobs
            cancelled_count = await scheduler.cancel_user_timers(user_id, test_type)
            
            # Remove from active timers
            keys_to_remove = []
            for timer_key, timer_meta in self.active_timers.items():
                if timer_meta.get("user_id") == user_id:
                    if test_type is None or timer_meta.get("test_type") == test_type:
                        keys_to_remove.append(timer_key)
            
            for key in keys_to_remove:
                self.active_timers.pop(key, None)
            
            logger.info(f"Stopped {cancelled_count} APScheduler timers for user {user_id}")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Failed to stop user timers for {user_id}: {e}", exc_info=True)
            return 0
    
    async def get_timer_progress(self, timer_key: str) -> Optional[ProgressData]:
        """
        Get progress data for a timer
        
        Args:
            timer_key: Timer identifier
            
        Returns:
            ProgressData or None if timer not found
        """
        try:
            scheduler = self._get_scheduler()
            timer_meta = self.active_timers.get(timer_key)
            
            if not timer_meta:
                return ProgressData(0.0, 0, 0, False)
            
            # Get timer info from scheduler
            job_id = timer_meta.get("job_id")
            if job_id:
                timer_info = await scheduler.get_timer_info(job_id)
                if timer_info:
                    remaining = timer_info.get("remaining_seconds", 0)
                    total_duration = timer_meta.get("duration", 0)
                    
                    # Calculate progress (countdown: 100% -> 0%)
                    if total_duration > 0:
                        progress = (remaining / total_duration) * 100
                    else:
                        progress = 0.0
                    
                    return ProgressData(
                        timer_progress=max(0.0, min(100.0, progress)),
                        remaining_seconds=int(remaining),
                        total_seconds=total_duration,
                        is_active=remaining > 0
                    )
            
            return ProgressData(0.0, 0, 0, False)
            
        except Exception as e:
            logger.error(f"Failed to get timer progress for {timer_key}: {e}", exc_info=True)
            return ProgressData(0.0, 0, 0, False)
    
    async def get_user_timer_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get timer statistics for a specific user
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with timer statistics
        """
        try:
            scheduler = self._get_scheduler()
            user_timers = await scheduler.get_user_timers(user_id)
            
            active_count = len([t for t in user_timers if t.get("remaining_seconds", 0) > 0])
            
            return {
                "user_id": user_id,
                "total_timers": len(user_timers),
                "active_count": active_count,
                "timers": user_timers
            }
            
        except Exception as e:
            logger.error(f"Failed to get user timer stats for {user_id}: {e}", exc_info=True)
            return {"user_id": user_id, "total_timers": 0, "active_count": 0, "timers": []}
    
    def calculate_time_taken(self, dialog_manager: DialogManager, timer_key: str) -> float:
        """
        Calculate time taken for a question (for compatibility with old system)
        
        Args:
            dialog_manager: Dialog manager instance (not used in new system)
            timer_key: Timer identifier
            
        Returns:
            Time taken in seconds (estimated based on timer metadata)
        """
        try:
            timer_meta = self.active_timers.get(timer_key)
            if timer_meta:
                start_time = timer_meta.get("start_time")
                duration = timer_meta.get("duration", 0)
                
                if start_time:
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    # Return the time actually taken (up to the total duration)
                    return min(elapsed, duration)
            
            # Fallback: return 0 if timer not found
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate time taken for {timer_key}: {e}", exc_info=True)
            return 0.0
    
    def create_timer_display(self, timer_key: str) -> List[Format]:
        """
        Create timer display widgets for aiogram-dialog
        
        Args:
            timer_key: Timer identifier
            
        Returns:
            List of Format widgets for timer display
        """
        return [
            Format("⏱️ Осталось времени: {remaining_time} сек"),
            Progress(
                "timer_progress",
                filled="🟩",      # Green filled blocks
                empty="⬜",        # White empty blocks
                width=10          # Total blocks
            ),
            Format("🔄 Прогресс: {progress_percent}%")
        ]


# Global instance for backward compatibility
enhanced_timer_manager = APSchedulerEnhancedTimerManager()


# Compatibility functions for existing code
async def start_timer_background(
    dialog_manager: DialogManager,
    timer_key: str,
    duration: int,
    on_timeout_callback: Optional[Callable] = None
) -> bool:
    """Compatibility wrapper for start_timer_background"""
    return await enhanced_timer_manager.start_timer_background(
        dialog_manager, timer_key, duration, on_timeout_callback
    )


async def stop_timer(dialog_manager: DialogManager, timer_key: str) -> bool:
    """Compatibility wrapper for stop_timer"""
    return await enhanced_timer_manager.stop_timer(dialog_manager, timer_key)


async def get_timer_progress_data(timer_key: str) -> Callable:
    """
    Compatibility wrapper for get_timer_progress_data
    Returns a getter function for aiogram-dialog
    """
    async def timer_getter(dialog_manager: DialogManager = None, **kwargs) -> Dict[str, Any]:
        progress_data = await enhanced_timer_manager.get_timer_progress(timer_key)
        
        if progress_data:
            return {
                "remaining_time": progress_data.remaining_seconds,
                "timer_progress": progress_data.timer_progress,
                "progress_percent": int(progress_data.timer_progress),
                "is_timer_active": progress_data.is_active
            }
        else:
            return {
                "remaining_time": 0,
                "timer_progress": 0.0,
                "progress_percent": 0,
                "is_timer_active": False
            }
    
    return timer_getter


def create_timer_display(timer_key: str) -> List[Format]:
    """Compatibility wrapper for create_timer_display"""
    return enhanced_timer_manager.create_timer_display(timer_key)


def calculate_time_taken(dialog_manager: DialogManager, timer_key: str) -> float:
    """Compatibility wrapper for calculate_time_taken"""
    return enhanced_timer_manager.calculate_time_taken(dialog_manager, timer_key)


# Migration helper
async def migrate_old_timers_to_scheduler():
    """
    Helper function to migrate from old asyncio-based timers to APScheduler
    This can be called during bot startup to clean up any old timer state
    """
    try:
        logger.info("Migrating old timer system to APScheduler...")
        # Any cleanup of old timer state can be done here
        logger.info("Timer migration completed")
    except Exception as e:
        logger.error(f"Timer migration failed: {e}", exc_info=True)