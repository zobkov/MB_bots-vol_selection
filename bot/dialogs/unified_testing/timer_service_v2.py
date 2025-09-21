"""
Новая архитектура таймера на базе APScheduler + Redis pub/sub + BgManager
Разделение ответственности:
- APScheduler: только персистентные timeout события
- Redis pub/sub: уведомления между процессами 
- BgManager: локальное обновление UI
- Локальный asyncio loop: плавная визуализация
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.base import JobLookupError

from aiogram_dialog import DialogManager

logger = logging.getLogger(__name__)

# Константы
REDIS_URL = "redis://localhost:6379/1"  # DB 1 для APScheduler
PUBSUB_CHANNEL = "vol_selection:quiz:timeouts"


class APSchedulerRedisService:
    """Обёртка над APScheduler с RedisJobStore для персистентных timeout событий"""
    
    def __init__(self, redis_config: dict):
        """
        Инициализация APScheduler с Redis jobstore
        
        Args:
            redis_config: Конфигурация Redis {host, port, password, db}
        """
        jobstores = {
            "default": RedisJobStore(
                jobs_key="apscheduler.jobs",
                run_times_key="apscheduler.runtimes",
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                password=redis_config.get("password"),
                db=redis_config.get("jobstore_db", 1)
            )
        }
        
        self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        self._redis_config = redis_config
        self._started = False
        
    async def start(self):
        """Запуск scheduler"""
        if not self._started:
            self._scheduler.start()
            self._started = True
            logger.info("APScheduler Redis service started")
    
    async def shutdown(self):
        """Остановка scheduler"""
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("APScheduler Redis service shut down")
    
    def schedule_timeout(self, job_id: str, run_at: datetime, payload: dict):
        """
        Создаёт job, который опубликует timeout событие в Redis channel
        
        Args:
            job_id: Уникальный ID job
            run_at: Время срабатывания
            payload: Данные для публикации
        """
        # Удаляем существующий job если есть
        try:
            self._scheduler.remove_job(job_id)
        except JobLookupError:
            pass
            
        # Добавляем новый job с статической функцией
        redis_config = {
            'host': self._redis_config.get('host', 'localhost'),
            'port': self._redis_config.get('port', 6379),
            'password': self._redis_config.get('password'),
            'db': 0  # DB 0 для pub/sub
        }
        
        self._scheduler.add_job(
            _publish_timeout_event_static,
            "date",
            run_date=run_at,
            args=[payload, redis_config],
            id=job_id,
            replace_existing=True
        )
        
        logger.debug(f"Scheduled timeout job {job_id} for {run_at}")


async def _publish_timeout_event_static(payload: dict, redis_config: dict):
    """Статическая функция для публикации timeout события в Redis channel"""
    logger = logging.getLogger(__name__)
    
    redis_client = aioredis.from_url(
        f"redis://{redis_config.get('host', 'localhost')}:"
        f"{redis_config.get('port', 6379)}/{redis_config.get('db', 0)}",
        password=redis_config.get('password')
    )
    
    try:
        message = json.dumps(payload)
        await redis_client.publish(PUBSUB_CHANNEL, message)
        logger.info(f"Published timeout event: {payload.get('job_id')}")
    except Exception as e:
        logger.error(f"Failed to publish timeout event: {e}")
    finally:
        await redis_client.close()
    
    def cancel_job(self, job_id: str):
        """Отменяет job"""
        try:
            self._scheduler.remove_job(job_id)
            logger.debug(f"Cancelled job {job_id}")
        except JobLookupError:
            logger.debug(f"Job {job_id} not found for cancellation")


class DialogTimerService:
    """
    Сервис управления таймерами диалогов
    Использует BgManager для локального обновления UI + APScheduler для timeout событий
    """
    
    def __init__(self, bot, redis_config: dict, scheduler_service: APSchedulerRedisService = None):
        """
        Инициализация сервиса
        
        Args:
            bot: Экземпляр бота
            redis_config: Конфигурация Redis
            scheduler_service: Опциональный scheduler service
        """
        self.bot = bot
        self.redis_config = redis_config
        self.scheduler = scheduler_service or APSchedulerRedisService(redis_config)
        
        # Локальные активные таймеры: job_id -> timer_info
        self.active_timers: Dict[str, dict] = {}
        
        # Задача для прослушивания Redis pub/sub
        self._pubsub_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
    async def start(self):
        """Запуск сервиса"""
        await self.scheduler.start()
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())
        logger.info("Dialog timer service started")
    
    async def shutdown(self):
        """Остановка сервиса"""
        self._shutdown_event.set()
        
        # Отменяем все активные таймеры
        for job_id in list(self.active_timers.keys()):
            await self.cancel_timer(job_id)
        
        # Останавливаем pub/sub loop
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        
        # Останавливаем scheduler
        await self.scheduler.shutdown()
        logger.info("Dialog timer service shut down")
    
    async def start_question_timer(self,
                                   dialog_manager: DialogManager,
                                   user_id: int,
                                   chat_id: int,
                                   test_type: str,
                                   question_number: int,
                                   duration_seconds: int) -> str:
        """
        Запуск таймера для вопроса
        
        Args:
            dialog_manager: Менеджер диалога
            user_id: ID пользователя
            chat_id: ID чата
            test_type: Тип теста
            question_number: Номер вопроса
            duration_seconds: Длительность в секундах
            
        Returns:
            job_id: ID созданной задачи
        """
        run_at = datetime.now() + timedelta(seconds=duration_seconds)
        job_id = f"timer_{user_id}_{test_type}_q{question_number}"
        
        try:
            # 1. Создаем BgManager для UI updates
            bg_manager = dialog_manager.bg(
                user_id=user_id,
                chat_id=chat_id,
                load=True
            )
            
            logger.info(f"🎯 Created BgManager for {job_id}: user_id={user_id}, chat_id={chat_id}")
            
            # 2. Планируем APScheduler job для timeout события
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "chat_id": chat_id,
                "test_type": test_type,
                "question_number": question_number,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.scheduler.schedule_timeout(job_id, run_at, payload)
            logger.info(f"⏰ Scheduled APScheduler timeout for {job_id} at {run_at}")
            
            # 3. Запускаем локальный loop для обновления UI
            start_time = datetime.now()
            update_task = asyncio.create_task(
                self._local_ui_update_loop(bg_manager, job_id, start_time, duration_seconds)
            )
            
            logger.info(f"🔄 Started UI update loop task for {job_id}")
            logger.debug(f"🎭 BgManager type: {type(bg_manager)}, update_task type: {type(update_task)}")
            
            # 4. Сохраняем информацию о таймере
            self.active_timers[job_id] = {
                "bg_manager": bg_manager,
                "update_task": update_task,
                "run_at": run_at,
                "user_id": user_id,
                "chat_id": chat_id,
                "test_type": test_type,
                "question_number": question_number,
                "duration": duration_seconds
            }
            
            logger.info(f"Started question timer {job_id} for {duration_seconds}s")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to start question timer {job_id}: {e}", exc_info=True)
            # Cleanup при ошибке
            self.scheduler.cancel_job(job_id)
            raise
    
    async def cancel_timer(self, job_id: str):
        """
        Отменяет таймер (при ответе пользователя)
        
        Args:
            job_id: ID таймера для отмены
        """
        timer_info = self.active_timers.pop(job_id, None)
        if not timer_info:
            logger.debug(f"Timer {job_id} not found for cancellation")
            return
        
        try:
            # Отменяем локальный update loop
            update_task: asyncio.Task = timer_info["update_task"]
            if not update_task.done():
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
            
            # Отменяем APScheduler job
            try:
                self.scheduler._scheduler.remove_job(job_id)
                logger.debug(f"✅ APScheduler job {job_id} cancelled successfully")
            except Exception as job_error:
                logger.warning(f"⚠️ Failed to cancel APScheduler job {job_id}: {job_error}")
            
            # Обновляем UI - показываем что таймер остановлен
            bg_manager = timer_info["bg_manager"]
            try:
                await bg_manager.update({
                    "timer_seconds": 0,
                    "timer_minutes": 0,
                    "progress_percent": 0,
                    "is_timer_active": False,
                    "timer_status": "cancelled"
                })
            except Exception as e:
                logger.debug(f"Failed to update UI on timer cancel: {e}")
            
            logger.info(f"Cancelled timer {job_id}")
            
        except Exception as e:
            logger.error(f"Error cancelling timer {job_id}: {e}", exc_info=True)
    
    async def _local_ui_update_loop(self, bg_manager, job_id: str, start_time: datetime, duration_seconds: int):
        """
        Локальный asyncio loop для плавного обновления UI каждую секунду
        Независим от APScheduler - только для визуализации
        """
        logger.info(f"🔄 Starting UI update loop for {job_id}, duration: {duration_seconds}s")
        
        try:
            iteration = 0
            while True:
                current_time = datetime.now()
                elapsed = (current_time - start_time).total_seconds()
                remaining = max(0, duration_seconds - elapsed)
                
                # Обновляем данные в dialog через BgManager
                timer_minutes = int(remaining // 60)
                timer_seconds = int(remaining % 60)
                progress_percent = (remaining / duration_seconds) * 100
                
                iteration += 1
                
                # Постоянно логируем для отладки
                logger.info(f"📊 UI update {iteration} for {job_id}: {timer_minutes:02d}:{timer_seconds:02d} ({remaining:.1f}s left, {progress_percent:.1f}%)")
                
                if remaining <= 0:
                    logger.info(f"⏰ UI update loop finished for {job_id} - timer expired")
                    break
                
                try:
                    # BgManager API: обновляем данные в dialog_data 
                    update_data = {
                        "timer_minutes": timer_minutes,
                        "timer_seconds": timer_seconds,
                        "timer_progress": progress_percent,
                        "remaining_time": remaining,
                        "progress_percent": progress_percent,
                        "is_timer_active": True,
                        "timer_status": "running"
                    }
                    
                    logger.debug(f"🔄 About to call BgManager.update for {job_id} with data: {update_data}")
                    await bg_manager.update(update_data)
                    logger.debug(f"✅ BgManager.update completed for {job_id}")
                        
                except Exception as bg_error:
                    logger.error(f"❌ BgManager update failed for {job_id}: {bg_error}", exc_info=True)
                    # Продолжаем работу даже при ошибке BgManager
                
                await asyncio.sleep(2)  # Обновляем каждые 2 секунды
                
        except asyncio.CancelledError:
            logger.info(f"🛑 UI update loop cancelled for {job_id}")
        except Exception as e:
            logger.error(f"💥 Error in UI update loop for {job_id}: {e}", exc_info=True)
    
    async def _pubsub_loop(self):
        """
        Прослушивание Redis pub/sub для timeout событий от APScheduler
        """
        redis_client = aioredis.from_url(
            f"redis://{self.redis_config.get('host', 'localhost')}:"
            f"{self.redis_config.get('port', 6379)}/0",  # DB 0 для pub/sub
            password=self.redis_config.get('password')
        )
        
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(PUBSUB_CHANNEL)
            
            logger.info(f"Subscribed to Redis channel: {PUBSUB_CHANNEL}")
            
            async for message in pubsub.listen():
                if self._shutdown_event.is_set():
                    break
                    
                if not message or message.get("type") != "message":
                    continue
                
                try:
                    # Парсим событие
                    data = json.loads(message["data"])
                    job_id = data.get("job_id")
                    
                    if not job_id:
                        continue
                    
                    # Обрабатываем timeout только если это наш таймер
                    await self._handle_timeout_event(job_id, data)
                    
                except Exception as e:
                    logger.error(f"Error processing pubsub message: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error in pubsub loop: {e}", exc_info=True)
        finally:
            await redis_client.close()
    
    async def _handle_timeout_event(self, job_id: str, event_data: dict):
        """
        Обработка timeout события от APScheduler
        
        Args:
            job_id: ID таймера
            event_data: Данные события
        """
        timer_info = self.active_timers.get(job_id)
        if not timer_info:
            # Этот процесс не владеет таймером - игнорируем
            logger.debug(f"Timeout event for {job_id} - not our timer, ignoring")
            return
        
        try:
            # Останавливаем локальный update loop
            update_task: asyncio.Task = timer_info["update_task"]
            if not update_task.done():
                update_task.cancel()
            
            # Обновляем UI - показываем timeout
            bg_manager = timer_info["bg_manager"]
            await bg_manager.update({
                "timer_seconds": 0,
                "timer_minutes": 0,
                "progress_percent": 0,
                "is_timer_active": False,
                "timer_status": "timeout"
            })
            
            # Здесь можно добавить переход к следующему состоянию диалога
            # await bg_manager.switch_to(SomeState.completed)
            
            logger.info(f"Handled timeout event for {job_id}")
            
        except Exception as e:
            logger.error(f"Error handling timeout event for {job_id}: {e}", exc_info=True)
        finally:
            # Cleanup
            self.active_timers.pop(job_id, None)


# Глобальный экземпляр сервиса (будет инициализирован в main.py)
dialog_timer_service: Optional[DialogTimerService] = None


def get_dialog_timer_service() -> DialogTimerService:
    """Получение глобального экземпляра сервиса"""
    if dialog_timer_service is None:
        raise RuntimeError("Dialog timer service not initialized")
    return dialog_timer_service


async def init_dialog_timer_service(bot, redis_config: dict) -> DialogTimerService:
    """
    Инициализация глобального сервиса таймеров
    
    Args:
        bot: Экземпляр бота
        redis_config: Конфигурация Redis
        
    Returns:
        Инициализированный сервис
    """
    global dialog_timer_service
    
    if dialog_timer_service is not None:
        await dialog_timer_service.shutdown()
    
    dialog_timer_service = DialogTimerService(bot, redis_config)
    await dialog_timer_service.start()
    
    logger.info("Dialog timer service initialized globally")
    return dialog_timer_service


async def shutdown_dialog_timer_service():
    """Остановка глобального сервиса таймеров"""
    global dialog_timer_service
    
    if dialog_timer_service is not None:
        await dialog_timer_service.shutdown()
        dialog_timer_service = None
        logger.info("Dialog timer service shut down globally")