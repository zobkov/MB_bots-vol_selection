"""
APScheduler-based timer system with Redis jobstore for Telegram bot
Provides reliable, persistent timers that survive bot restarts.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


@dataclass
class TimerConfig:
    """Configuration for question timer"""
    user_id: int
    chat_id: int
    test_type: str
    question_number: int
    time_limit: int  # seconds
    bot_token: str


@dataclass
class TimerStats:
    """Timer statistics for monitoring"""
    total_jobs: int
    pending_jobs: int
    running_jobs: int
    user_jobs: Dict[int, int]  # user_id -> job_count


# Independent timeout handler function (not a class method)
async def _handle_question_timeout_independent(config_dict: Dict[str, Any]) -> None:
    """
    Independent handler for question timeout
    
    Args:
        config_dict: Timer configuration as dictionary (serializable)
    """
    try:
        # Recreate TimerConfig from dict
        config = TimerConfig(**config_dict)
        job_id = f"timer_{config.user_id}_{config.test_type}_q{config.question_number}"
        
        logger.info(f"Question timeout triggered: {job_id}")
        
        # Send timeout notification to user
        await _send_timeout_notification_independent(config)
        
    except Exception as e:
        logger.error(f"Error in timeout handler: {e}", exc_info=True)


async def _send_timeout_notification_independent(config: TimerConfig) -> None:
    """
    Independent function to send timeout notification to user
    
    Args:
        config: Timer configuration
    """
    try:
        bot = Bot(token=config.bot_token)
        
        message = (
            f"⏰ <b>Время вышло!</b>\n\n"
            f"Время на вопрос {config.question_number} в тесте "
            f"<b>{config.test_type}</b> истекло.\n\n"
            f"Переходим к следующему вопросу..."
        )
        
        await bot.send_message(
            chat_id=config.chat_id,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"Timeout notification sent to user {config.user_id}")
        
    except TelegramBadRequest as e:
        if "chat not found" in str(e).lower():
            logger.warning(f"Chat {config.chat_id} not found for timeout notification")
        else:
            logger.error(f"Telegram error sending timeout notification: {e}")
    except Exception as e:
        logger.error(f"Failed to send timeout notification: {e}", exc_info=True)
    finally:
        try:
            await bot.session.close()
        except:
            pass


class APSchedulerTimerManager:
    """
    APScheduler-based timer manager with Redis persistence
    
    Key features:
    - Redis jobstore for persistence across restarts
    - User-isolated timer management
    - Automatic timeout handling with bot notifications
    - Comprehensive error handling and logging
    """
    
    def __init__(self, redis_config: Dict[str, Any]):
        """
        Initialize APScheduler with Redis jobstore
        
        Args:
            redis_config: Redis connection configuration
        """
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.redis_config = redis_config
        self._timeout_callbacks: Dict[str, Callable] = {}
        
        # Job statistics
        self._job_stats: Dict[str, int] = {
            "executed": 0,
            "errors": 0,
            "missed": 0
        }
        
    async def initialize(self) -> None:
        """Initialize and start the scheduler"""
        try:
            # Configure Redis jobstore
            jobstore_config = {
                'default': RedisJobStore(
                    host=self.redis_config.get('host', 'localhost'),
                    port=self.redis_config.get('port', 6379),
                    password=self.redis_config.get('password'),
                    db=self.redis_config.get('jobstore_db', 1),  # Different DB from FSM
                    jobs_key='apscheduler.jobs',
                    run_times_key='apscheduler.run_times',
                )
            }
            
            # Configure executor
            executor_config = {
                'default': AsyncIOExecutor()
            }
            
            # Job defaults
            job_defaults = {
                'coalesce': True,  # Combine multiple pending executions
                'max_instances': 3,  # Maximum concurrent instances
                'misfire_grace_time': 30  # Grace period for missed jobs
            }
            
            # Create scheduler
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstore_config,
                executors=executor_config,
                job_defaults=job_defaults,
                timezone='UTC'
            )
            
            # Add event listeners for monitoring
            self.scheduler.add_listener(
                self._on_job_executed,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
            )
            
            # Start scheduler
            self.scheduler.start()
            logger.info("APScheduler timer manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize APScheduler: {e}", exc_info=True)
            raise
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the scheduler"""
        if self.scheduler:
            try:
                self.scheduler.shutdown(wait=True)
                logger.info("APScheduler timer manager shut down successfully")
            except Exception as e:
                logger.error(f"Error during scheduler shutdown: {e}", exc_info=True)
    
    def _generate_job_id(self, config: TimerConfig) -> str:
        """Generate unique job ID for timer"""
        return f"timer_{config.user_id}_{config.test_type}_q{config.question_number}"
    
    def _generate_user_key(self, user_id: int, test_type: str) -> str:
        """Generate user-specific key for timer management"""
        return f"user_{user_id}_{test_type}"
    
    async def start_question_timer(
        self,
        config: TimerConfig,
        timeout_callback: Optional[Callable] = None
    ) -> str:
        """
        Start a timer for a specific question
        
        Args:
            config: Timer configuration
            timeout_callback: Optional callback to execute on timeout
            
        Returns:
            job_id: Unique identifier for the scheduled job
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        job_id = self._generate_job_id(config)
        
        try:
            # Cancel existing timer for same question if exists
            await self.cancel_timer(job_id)
            
            # Schedule timeout job
            run_time = datetime.utcnow() + timedelta(seconds=config.time_limit)
            
            # Store timeout callback for later use
            if timeout_callback:
                self._timeout_callbacks[job_id] = timeout_callback
            
            # Convert TimerConfig to dict for serialization
            config_dict = {
                'user_id': config.user_id,
                'chat_id': config.chat_id,
                'test_type': config.test_type,
                'question_number': config.question_number,
                'time_limit': config.time_limit,
                'bot_token': config.bot_token
            }
            
            job = self.scheduler.add_job(
                func=_handle_question_timeout_independent,
                trigger='date',
                run_date=run_time,
                args=[config_dict],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=30
            )
            
            logger.info(f"Timer started: {job_id} for {config.time_limit}s")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to start timer {job_id}: {e}", exc_info=True)
            raise
    
    async def cancel_timer(self, job_id: str) -> bool:
        """
        Cancel a specific timer
        
        Args:
            job_id: Timer job identifier
            
        Returns:
            bool: True if timer was cancelled, False if not found
        """
        if not self.scheduler:
            return False
        
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.remove()
                # Clean up callback
                self._timeout_callbacks.pop(job_id, None)
                logger.info(f"Timer cancelled: {job_id}")
                return True
            else:
                logger.debug(f"Timer not found for cancellation: {job_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to cancel timer {job_id}: {e}", exc_info=True)
            return False
    
    async def cancel_user_timers(self, user_id: int, test_type: Optional[str] = None) -> int:
        """
        Cancel all timers for a specific user or user+test_type
        
        Args:
            user_id: User identifier
            test_type: Optional test type filter
            
        Returns:
            int: Number of cancelled timers
        """
        if not self.scheduler:
            return 0
        
        cancelled = 0
        try:
            # Get all jobs
            jobs = self.scheduler.get_jobs()
            
            for job in jobs:
                job_id = job.id
                
                # Parse job_id: timer_{user_id}_{test_type}_q{question_number}
                if job_id.startswith(f"timer_{user_id}_"):
                    if test_type is None or f"_{test_type}_" in job_id:
                        job.remove()
                        self._timeout_callbacks.pop(job_id, None)
                        cancelled += 1
                        logger.debug(f"Cancelled user timer: {job_id}")
            
            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} timers for user {user_id}")
            
            return cancelled
            
        except Exception as e:
            logger.error(f"Failed to cancel user timers for {user_id}: {e}", exc_info=True)
            return 0
    
    async def get_timer_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific timer
        
        Args:
            job_id: Timer job identifier
            
        Returns:
            Dict with timer information or None if not found
        """
        if not self.scheduler:
            return None
        
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                next_run = job.next_run_time
                remaining = None
                if next_run:
                    remaining = (next_run - datetime.now(next_run.tzinfo)).total_seconds()
                
                return {
                    'job_id': job_id,
                    'next_run_time': next_run,
                    'remaining_seconds': max(0, remaining) if remaining else 0,
                    'func_name': job.func.__name__ if job.func else None
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get timer info for {job_id}: {e}", exc_info=True)
            return None
    
    async def get_user_timers(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all active timers for a specific user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of timer information dictionaries
        """
        if not self.scheduler:
            return []
        
        user_timers = []
        try:
            jobs = self.scheduler.get_jobs()
            
            for job in jobs:
                if job.id.startswith(f"timer_{user_id}_"):
                    timer_info = await self.get_timer_info(job.id)
                    if timer_info:
                        user_timers.append(timer_info)
            
            return user_timers
            
        except Exception as e:
            logger.error(f"Failed to get user timers for {user_id}: {e}", exc_info=True)
            return []
    
    async def get_stats(self) -> TimerStats:
        """Get timer system statistics"""
        if not self.scheduler:
            return TimerStats(0, 0, 0, {})
        
        try:
            jobs = self.scheduler.get_jobs()
            total_jobs = len(jobs)
            
            # Count user jobs
            user_jobs = {}
            for job in jobs:
                if job.id.startswith("timer_"):
                    parts = job.id.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        user_id = int(parts[1])
                        user_jobs[user_id] = user_jobs.get(user_id, 0) + 1
            
            return TimerStats(
                total_jobs=total_jobs,
                pending_jobs=total_jobs,  # All jobs are pending until executed
                running_jobs=0,  # APScheduler doesn't distinguish running vs pending
                user_jobs=user_jobs
            )
            
        except Exception as e:
            logger.error(f"Failed to get timer stats: {e}", exc_info=True)
            return TimerStats(0, 0, 0, {})
    
    def _on_job_executed(self, event) -> None:
        """Event listener for job execution monitoring"""
        try:
            if event.exception:
                self._job_stats["errors"] += 1
                logger.error(f"Job {event.job_id} failed: {event.exception}")
            else:
                self._job_stats["executed"] += 1
                logger.debug(f"Job {event.job_id} executed successfully")
                
        except Exception as e:
            logger.error(f"Error in job event listener: {e}")


# Global scheduler instance
_scheduler_manager: Optional[APSchedulerTimerManager] = None


def get_scheduler_manager() -> Optional[APSchedulerTimerManager]:
    """Get global scheduler manager instance"""
    return _scheduler_manager


def set_scheduler_manager(manager: APSchedulerTimerManager) -> None:
    """Set global scheduler manager instance"""
    global _scheduler_manager
    _scheduler_manager = manager


async def init_scheduler_manager(redis_config: Dict[str, Any]) -> APSchedulerTimerManager:
    """
    Initialize global scheduler manager
    
    Args:
        redis_config: Redis connection configuration
        
    Returns:
        Initialized scheduler manager
    """
    global _scheduler_manager
    
    if _scheduler_manager is None:
        _scheduler_manager = APSchedulerTimerManager(redis_config)
        await _scheduler_manager.initialize()
    
    return _scheduler_manager


async def shutdown_scheduler_manager() -> None:
    """Shutdown global scheduler manager"""
    global _scheduler_manager
    
    if _scheduler_manager:
        await _scheduler_manager.shutdown()
        _scheduler_manager = None