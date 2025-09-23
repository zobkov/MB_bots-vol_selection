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


def create_state_monitor_task(config, question, dialog_manager):
    """Создание seq-версионированного монитора состояния"""
    # берем текущую seq
    seq_key = f"seq_{config.test_type}"
    current_seq = dialog_manager.dialog_data.get(seq_key, 0)

    async def _monitor():
        await asyncio.sleep(2.0)
        # проверяем seq
        if dialog_manager.dialog_data.get(seq_key) != current_seq:
            logger.debug("⏭ Monitor stale (seq changed). Exit.")
            return

        # проверяем активен ли таймер
        timer_key = f"timer_{config.test_type}_q{question.number}_started"
        if not dialog_manager.dialog_data.get(timer_key):
            return

        current_state = dialog_manager.current_context().state
        expected_state = getattr(config.states_group, f"q{question.number}")
        if current_state != expected_state:
            logger.warning(f"Monitor forcing rollback: expected {expected_state}, got {current_state}")
            await dialog_manager.switch_to(expected_state)

    task = asyncio.create_task(_monitor())
    dialog_manager.dialog_data[f"monitor_task_{config.test_type}_q{question.number}"] = task


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
            
            # 🛡️ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Предварительная инициализация данных
            # Устанавливаем начальные данные в dialog_data для предотвращения возврата к старому состоянию
            parts = job_id.split('_')
            if len(parts) >= 4:
                test_type = parts[2]
                question_part = parts[3]  # q1, q2, etc.
                question_number = question_part[1:] if question_part.startswith('q') else question_part
                
                timer_key_prefix = f"timer_{test_type}_q{question_number}"
                initial_minutes = duration_seconds // 60
                initial_seconds = duration_seconds % 60
                
                # Предварительно заполняем данные для предотвращения реверта состояния
                initial_data = {
                    f"{timer_key_prefix}_minutes": initial_minutes,
                    f"{timer_key_prefix}_seconds": initial_seconds,
                    f"{timer_key_prefix}_progress": 100.0,
                    f"{timer_key_prefix}_remaining": float(duration_seconds),
                    f"{timer_key_prefix}_active": True,
                    f"{timer_key_prefix}_status": "initializing"
                }
                
                # Обновляем dialog_data напрямую
                dialog_manager.dialog_data.update(initial_data)
                logger.debug(f"🛡️ Pre-initialized timer data for {job_id}: {initial_data}")
            
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
            
            # 3. Запускаем локальный loop для обновления UI (с задержкой для стабилизации состояния)
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
                "duration": duration_seconds,
                "dialog_manager": dialog_manager  # Сохраняем для timeout handling
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
            
            # Обновляем UI - показываем что таймер остановлен с ИЗОЛИРОВАННЫМИ КЛЮЧАМИ
            bg_manager = timer_info["bg_manager"]
            try:
                # Извлекаем test_type и question_number из job_id для изолированных ключей
                parts = job_id.split('_')
                if len(parts) >= 4:
                    test_type = parts[2]
                    question_part = parts[3]  # q1, q2, etc.
                    question_number = question_part[1:] if question_part.startswith('q') else question_part
                    
                    timer_key_prefix = f"timer_{test_type}_q{question_number}"
                    
                    cancel_data = {
                        f"{timer_key_prefix}_seconds": 0,
                        f"{timer_key_prefix}_minutes": 0,
                        f"{timer_key_prefix}_progress": 0,
                        f"{timer_key_prefix}_active": False,
                        f"{timer_key_prefix}_status": "cancelled"
                    }
                    await bg_manager.update(cancel_data)
                    logger.debug(f"✅ Updated UI with isolated cancel data for {job_id}")
                else:
                    # Fallback
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
    
    async def cancel_all_user_timers(self, user_id: int):
        """
        Отменяет все активные таймеры для указанного пользователя
        
        Args:
            user_id: ID пользователя
        """
        cancelled_count = 0
        
        # Находим все таймеры пользователя по паттерну job_id
        user_timers = []
        for job_id in list(self.active_timers.keys()):
            # Паттерн job_id: timer_{user_id}_{test_type}_q{question_number}
            if job_id.startswith(f"timer_{user_id}_"):
                user_timers.append(job_id)
        
        # Отменяем каждый таймер
        for job_id in user_timers:
            try:
                await self.cancel_timer(job_id)
                cancelled_count += 1
                logger.debug(f"Cancelled user timer: {job_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel user timer {job_id}: {e}")
        
        logger.info(f"Cancelled {cancelled_count} timers for user {user_id}")
        return cancelled_count
    
    async def _local_ui_update_loop(self, bg_manager, job_id: str, start_time: datetime, duration_seconds: int):
        """
        Локальный asyncio loop для плавного обновления UI каждую секунду
        Независим от APScheduler - только для визуализации
        """
        logger.info(f"🔄 Starting UI update loop for {job_id}, duration: {duration_seconds}s")
        
        # КРИТИЧЕСКАЯ ЗАДЕРЖКА: Ждем стабилизации состояния диалога перед BgManager updates
        # Это предотвращает corruption состояния после переходов q1→q2→q3
        await asyncio.sleep(0.5)
        logger.debug(f"🛡️ State stabilization delay completed for {job_id}")
        
        try:
            iteration = 0
            while True:
                current_time = datetime.now()
                elapsed = (current_time - start_time).total_seconds()
                # Компенсируем задержку стабилизации в оставшемся времени
                remaining = max(0, duration_seconds - elapsed + 0.5)  # +0.5 для компенсации задержки
                
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
                    # 🚫 DISABLED: BgManager updates cause state corruption in aiogram-dialog
                    # The BgManager.update() call was causing q2→q1 state reversion
                    # Alternative: Use static timer display without live updates
                    
                    # ORIGINAL CODE (causes state reversion):
                    # BgManager API: обновляем данные в dialog_data с ИЗОЛИРОВАННЫМИ КЛЮЧАМИ
                    # Извлекаем test_type и question_number из job_id
                    # Формат: timer_{user_id}_{test_type}_q{question_number}
                    parts = job_id.split('_')
                    if len(parts) >= 4:
                        test_type = parts[2]
                        question_part = parts[3]  # q1, q2, etc.
                        question_number = question_part[1:] if question_part.startswith('q') else question_part
                        
                        # ИЗОЛИРОВАННЫЕ КЛЮЧИ для каждого вопроса - НО ОТКЛЮЧЕНО
                        timer_key_prefix = f"timer_{test_type}_q{question_number}"
                        
                        update_data = {
                            f"{timer_key_prefix}_minutes": timer_minutes,
                            f"{timer_key_prefix}_seconds": timer_seconds,
                            f"{timer_key_prefix}_progress": progress_percent,
                            f"{timer_key_prefix}_remaining": remaining,
                            f"{timer_key_prefix}_active": True,
                            f"{timer_key_prefix}_status": "running"
                        }
                        
                        logger.debug(f"� SKIPPED BgManager.update for {job_id} to prevent state corruption: {update_data}")
                        # await bg_manager.update(update_data)  # DISABLED
                        logger.debug(f"✅ BgManager.update SKIPPED for {job_id} - no state corruption")
                    else:
                        logger.debug(f"� SKIPPED fallback BgManager update for {job_id} (state corruption prevention)")
                        
                except Exception as bg_error:
                    logger.error(f"❌ BgManager logic error for {job_id}: {bg_error}", exc_info=True)
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
            
            # Обновляем UI - показываем timeout с ИЗОЛИРОВАННЫМИ КЛЮЧАМИ
            bg_manager = timer_info["bg_manager"]
            
            # Парсим job_id для получения информации о тесте
            # Формат: timer_{user_id}_{test_type}_q{question_number}
            parts = job_id.split('_')
            if len(parts) >= 4:
                test_type = parts[2]
                question_part = parts[3]  # q1, q2, etc.
                question_number = question_part[1:] if question_part.startswith('q') else question_part
                
                timer_key_prefix = f"timer_{test_type}_q{question_number}"
                
                timeout_data = {
                    f"{timer_key_prefix}_seconds": 0,
                    f"{timer_key_prefix}_minutes": 0,
                    f"{timer_key_prefix}_progress": 0,
                    f"{timer_key_prefix}_active": False,
                    f"{timer_key_prefix}_status": "timeout"
                }
                await bg_manager.update(timeout_data)
                logger.debug(f"✅ Updated UI with isolated timeout data for {job_id}")
                
                user_id = int(parts[1])
                test_type = parts[2]
                question_part = parts[3]  # q1, q2, etc.
                
                if question_part.startswith('q'):
                    current_question = int(question_part[1:])
                    
                    # Обрабатываем таймаут через Test Engine
                    await self._handle_question_timeout(user_id, test_type, current_question, bg_manager, timer_info)
            
            logger.info(f"Handled timeout event for {job_id}")
            
        except Exception as e:
            logger.error(f"Error handling timeout event for {job_id}: {e}", exc_info=True)
        finally:
            # Cleanup
            self.active_timers.pop(job_id, None)
    
    async def _handle_question_timeout(self, user_id: int, test_type: str, current_question: int, bg_manager, timer_info: dict):
        """
        Обработка таймаута конкретного вопроса - переход к следующему или завершение теста
        """
        try:
            from .test_engine_v2 import get_test_engine
            
            # Получаем dialog_manager из timer_info
            dialog_manager = timer_info.get("dialog_manager")
            if not dialog_manager:
                logger.error(f"No dialog_manager found for timeout handling of {test_type} q{current_question}")
                return
            
            test_engine = get_test_engine()
            
            # Сохраняем пустой ответ для пропущенного вопроса
            answer_key = f"{test_type}_q{current_question}_answer"
            time_key = f"{test_type}_q{current_question}_time"
            
            dialog_manager.dialog_data[answer_key] = "[TIMEOUT - NO ANSWER]"
            dialog_manager.dialog_data[time_key] = datetime.utcnow().isoformat()
            
            # Определяем следующий шаг (предполагаем 6 вопросов в тесте)
            if current_question >= 6:
                # Последний вопрос - завершаем тест
                logger.info(f"Timeout on last question {current_question} for {test_type}, completing test")
                
                # Создаем временную конфигурацию для завершения теста
                from .models import TestConfig
                from bot.states import GeneralQuestionsSG  # TODO: Использовать правильные состояния для разных тестов
                
                temp_config = TestConfig(
                    test_type=test_type,
                    display_name=test_type.title(),
                    icon="📝",
                    questions=[],  # Не нужны для завершения
                    states_group=GeneralQuestionsSG
                )
                
                await dialog_manager.switch_to(temp_config.states_group.completed)
            else:
                # Переходим к следующему вопросу
                next_question = current_question + 1
                logger.info(f"Timeout on question {current_question} for {test_type}, moving to question {next_question}")
                
                from bot.states import GeneralQuestionsSG  # TODO: Использовать правильные состояния
                next_state = getattr(GeneralQuestionsSG, f'q{next_question}')
                await dialog_manager.switch_to(next_state)
            
        except Exception as e:
            logger.error(f"Error handling question timeout: {e}", exc_info=True)


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