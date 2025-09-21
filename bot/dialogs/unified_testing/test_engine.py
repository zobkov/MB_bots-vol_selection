"""
Основной движок унифицированной системы тестирования
"""
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List, Callable, Any
from aiogram_dialog import DialogManager
from aiogram.types import Message

from .models import TestConfig, TestQuestion, TestProgress, TimerData
from .enhanced_scheduler_timer_utils import (
    APSchedulerEnhancedTimerManager, 
    start_timer_background, 
    stop_timer, 
    get_timer_progress_data,
    calculate_time_taken,
    migrate_old_timers_to_scheduler
)

# Глобальная переменная для доступа к БД в timeout случаях
_global_db = None

def set_global_database(db):
    """Установка глобального объекта БД для timeout обработки"""
    global _global_db
    _global_db = db

def get_global_database():
    """Получение глобального объекта БД"""
    return _global_db
from .media_utils import MediaHandler, MEDIA_MESSAGE_IDS_KEY, MEDIA_SENT_KEY
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database

logger = logging.getLogger(__name__)


class TestEngine:
    """Основной движок для управления тестированием

    Ключевые принципы новой реализации:
    - Ответы НЕ пишутся в БД по ходу теста. Мы копим их в памяти (TestProgress.answers)
      и одним коммитом сохраняем все ответы при показе окна завершения.
    - Таймаут вопроса = пустой ответ. По таймауту сохраняем в память и сразу переходим далее.
    - Дубли сохраняния (гонки «ответ + таймаут») предотвращаем флагом "answered" на таймер-ключ.
    - Все таймеры изолированы по пользователю; каждый переход останавливает предыдущие таймеры.
    """
    
    def __init__(self):
        self.timer_manager = APSchedulerEnhancedTimerManager()
        self.active_tests: Dict[int, TestProgress] = {}  # user_id -> TestProgress
        
    def get_user_timer_key(self, user_id: int, test_type: str, question_num: int) -> str:
        """Генерация ключа таймера для конкретного пользователя"""
        return f"user_{user_id}_{test_type}_q{question_num}"

    def _answered_flag_key(self, timer_key: str) -> str:
        """Ключ-флаг в dialog_data, помечающий, что ответ по этому вопросу уже сохранён."""
        return f"{timer_key}_answered"
    
    async def start_test(self, dialog_manager: DialogManager, config: TestConfig) -> TestProgress:
        """Запуск нового теста"""
        user_id = dialog_manager.event.from_user.id
        
        logger.info(f"Starting {config.test_type} test for user {user_id}")
        
        # Чистим возможные артефакты предыдущего запуска этого же теста в dialog_data
        try:
            dd = dialog_manager.dialog_data
            keys_to_delete = []
            prefixes = [
                f"user_{user_id}_{config.test_type}_",          # таймеры и answered-флаги
                f"test_{config.test_type}_",                    # persisted/completion/advance
                f"question_{config.test_type}_",                # медиа для вопросов
            ]
            for k in list(dd.keys()):
                if any(k.startswith(p) for p in prefixes):
                    keys_to_delete.append(k)
            for k in keys_to_delete:
                dd.pop(k, None)
            if keys_to_delete:
                logger.debug(
                    f"Cleared {len(keys_to_delete)} stale dialog_data keys for test {config.test_type}: {keys_to_delete}"
                )
        except Exception as e:
            logger.debug(f"Failed to cleanup stale dialog_data for {config.test_type}: {e}")

        # Останавливаем все активные таймеры пользователя
        await self.timer_manager.stop_all_user_timers(user_id)
        
        # Создаем новый прогресс теста
        progress = TestProgress(
            user_id=user_id,
            test_type=config.test_type,
            current_question=1,
            total_questions=len(config.questions),
            is_started=True
        )
        
        self.active_tests[user_id] = progress
        # Сохраняем только сериализуемый флаг старта (в Redis хранится JSON)
        dialog_manager.dialog_data[f"test_{config.test_type}_started"] = True

        logger.info(f"Test {config.test_type} started for user {user_id}, total questions: {len(config.questions)}")
        return progress
    
    async def start_question_timer(self, dialog_manager: DialogManager, config: TestConfig, 
                                 question: TestQuestion) -> str:
        """Запуск таймера для вопроса"""
        user_id = dialog_manager.event.from_user.id
        timer_key = self.get_user_timer_key(user_id, config.test_type, question.number)
        
        # ВАЖНО: Сначала останавливаем все старые таймеры пользователя
        # Это предотвращает OutdatedIntent ошибки при переходах между диалогами
        await self.timer_manager.stop_all_user_timers(user_id)
        logger.debug(f"Stopped all existing timers for user {user_id} before starting new timer")
        
        # Создаем callback для таймаута
        async def timeout_callback(bg_manager, timer_key: str):
            await self.handle_timeout(bg_manager, config, question.number, timer_key)
        
        # Запускаем таймер через enhanced timer manager
        await self.timer_manager.start_timer_background(
            dialog_manager, 
            timer_key, 
            question.time_limit,
            timeout_callback
        )
        
        logger.info(f"Timer started for user {user_id}, {config.test_type} q{question.number}, duration: {question.time_limit}s")
        return timer_key
    
    async def save_answer(self, dialog_manager: DialogManager, config: TestConfig, 
                         question_num: int, answer: str, is_timeout: bool = False) -> bool:
        """Сохранение ответа в память (без БД) и обновление прогресса.

        Возвращает True, если ответ был сохранён впервые; False, если ответ уже был.
        """
        user_id = dialog_manager.event.from_user.id
        timer_key = self.get_user_timer_key(user_id, config.test_type, question_num)
        flag_key = self._answered_flag_key(timer_key)
        
        # Если уже отвечали (гонка таймаута/ввода) — ничего не делаем
        if dialog_manager.dialog_data.get(flag_key):
            logger.debug(f"Answer already recorded for {timer_key}, skipping duplicate save")
            return False
        
        logger.info(
            f"Recording answer (in-memory) for user {user_id}, {config.test_type} q{question_num}: "
            f"'{answer}' (timeout: {is_timeout})"
        )
        
        try:
            # Останавливаем таймер (если ещё активен)
            await self.timer_manager.stop_timer(dialog_manager, timer_key)
            
            # Время ответа
            time_taken = calculate_time_taken(dialog_manager, timer_key)
            
            # Получаем вопрос
            question = next((q for q in config.questions if q.number == question_num), None)
            if not question:
                logger.error(f"Question {question_num} not found in config")
                return False
            
            # Подготавливаем запись ответа (пока только в память)
            answer_record = {
                "question_number": question.number,
                "question_text": question.text,
                "answer_text": answer or "",
                "time_limit": question.time_limit,
                "time_taken": time_taken,
                "is_timeout": is_timeout,
                "correct_answer": question.correct_answer,
            }
            
            # Обновляем прогресс
            if user_id in self.active_tests:
                progress = self.active_tests[user_id]
                progress.answers[question_num] = answer_record
                progress.current_question = min(question_num + 1, progress.total_questions)
            else:
                logger.warning(f"Active test not found for user {user_id} when saving answer")
            
            # Ставим флаг «ответ сохранён», чтобы таймаут не продублировал
            dialog_manager.dialog_data[flag_key] = True
            # Дополнительно ставим короткий флаг без user_id для бэкграунд-рендеров
            short_answered_key = f"test_{config.test_type}_q{question_num}_answered"
            dialog_manager.dialog_data[short_answered_key] = True
            # И обновляем текущий прогресс в dialog_data (без user_id)
            try:
                dialog_manager.dialog_data[f"test_{config.test_type}_current"] = progress.current_question
            except Exception:
                pass
            logger.info(f"Answer recorded (in-memory) for user {user_id}, {config.test_type} q{question_num}")
            return True
        except Exception as e:
            logger.error(
                f"Error recording answer for user {user_id}, {config.test_type} q{question_num}: {e}",
                exc_info=True
            )
            return False
    
    async def handle_timeout(self, bg_manager, config: TestConfig, question_num: int, timer_key: str):
        """Обработка таймаута вопроса: пишем пустой ответ в память и переходим далее.

        ВАЖНО: НИКАКИХ операций с БД здесь — сохранение произойдёт в окне завершения.
        """
        user_id_str = timer_key.split('_')[1]  # извлекаем user_id из ключа
        user_id = int(user_id_str)
        logger.info(f"Timeout handler called for user {user_id}, {config.test_type} q{question_num}")

        try:
            # Получаем dialog_manager из bg_manager разными способами
            dialog_manager = getattr(bg_manager, '_manager', None)
            if not dialog_manager:
                dialog_manager = getattr(bg_manager, 'manager', None)
            if not dialog_manager:
                # Попробуем получить доступ к data через bg_manager
                dialog_manager = bg_manager
            
            logger.debug(f"Dialog manager found: {dialog_manager is not None}")
            
            if dialog_manager:
                # Сразу устанавливаем флаги завершения вопроса без попытки получить event
                flag_key = self._answered_flag_key(timer_key)
                short_answered_key = f"test_{config.test_type}_q{question_num}_answered"
                advance_key = f"test_{config.test_type}_advance_to"
                
                # Проверяем, не был ли уже обработан этот таймаут
                if hasattr(dialog_manager, 'dialog_data') and dialog_manager.dialog_data.get(flag_key):
                    logger.debug(f"Timeout already processed for {timer_key}")
                    return
                
                # Устанавливаем флаги завершения вопроса
                if hasattr(dialog_manager, 'dialog_data'):
                    dialog_manager.dialog_data[flag_key] = True
                    dialog_manager.dialog_data[short_answered_key] = True
                    
                    # Устанавливаем следующее состояние
                    if question_num < len(config.questions):
                        dialog_manager.dialog_data[advance_key] = question_num + 1
                        logger.info(f"Timeout: advancing from q{question_num} to q{question_num+1}")
                    else:
                        dialog_manager.dialog_data[f"test_{config.test_type}_completion_pending"] = True
                        dialog_manager.dialog_data[advance_key] = "completed"
                        logger.info(f"Timeout: completing test {config.test_type}")
                
                # Пытаемся записать пустой ответ в память через engine
                try:
                    if user_id in self.active_tests:
                        progress = self.active_tests[user_id]
                        if question_num not in progress.answers:
                            # Получаем вопрос
                            question = next((q for q in config.questions if q.number == question_num), None)
                            if question:
                                answer_record = {
                                    "question_number": question.number,
                                    "question_text": question.text,
                                    "answer_text": "",
                                    "time_limit": question.time_limit,
                                    "time_taken": question.time_limit,
                                    "is_timeout": True,
                                    "correct_answer": question.correct_answer,
                                }
                                progress.answers[question_num] = answer_record
                                progress.current_question = min(question_num + 1, progress.total_questions)
                                logger.info(f"Timeout answer recorded in engine for {config.test_type} q{question_num}")
                except Exception as save_err:
                    logger.error(f"Error saving timeout answer in engine: {save_err}")

            # Переход к следующему состоянию через bg_manager.switch_to
            try:
                if question_num < len(config.questions):
                    next_state = getattr(config.states_group, f"q{question_num+1}")
                    # Устанавливаем аварийный флаг для надёжного редиректа геттерами на следующую страницу
                    try:
                        if dialog_manager:
                            advance_key = f"test_{config.test_type}_advance_to"
                            dialog_manager.dialog_data[advance_key] = question_num + 1
                    except Exception:
                        pass
                else:
                    # Помечаем, что завершение ожидается (для мгновенного редиректа геттеров)
                    try:
                        if dialog_manager:
                            dialog_manager.dialog_data[f"test_{config.test_type}_completion_pending"] = True
                            # Дополнительный флаг для синхронного редиректа в геттерах
                            dialog_manager.dialog_data[f"test_{config.test_type}_advance_to"] = "completed"
                    except Exception:
                        pass
                    # На всякий случай останавливаем все таймеры пользователя
                    try:
                        if dialog_manager and getattr(dialog_manager, 'event', None):
                            await self.timer_manager.stop_all_user_timers(dialog_manager.event.from_user.id)
                    except Exception:
                        pass
                    next_state = getattr(config.states_group, "completed")
                await bg_manager.switch_to(next_state)
            except Exception as trans_err:
                logger.error(f"Timeout transition error for {timer_key}: {trans_err}", exc_info=True)
                # Надёжный фоллбэк: помечаем целевое состояние и даём геттерам выполнить переход
                try:
                    if dialog_manager:
                        advance_key = f"test_{config.test_type}_advance_to"
                        if question_num < len(config.questions):
                            dialog_manager.dialog_data[advance_key] = question_num + 1
                        else:
                            dialog_manager.dialog_data[advance_key] = "completed"
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error handling timeout for {timer_key}: {e}", exc_info=True)
    
    async def persist_results(self, dialog_manager: DialogManager, config: TestConfig) -> bool:
        """Сохранение всех ответов в БД и отметка завершения (одним коммитом).

        Возвращает True при полном успехе.
        """
        user_id = dialog_manager.event.from_user.id
        logger.info(f"Persisting results for {config.test_type} test, user {user_id}")

        try:
            # Стоп всех таймеров пользователя
            await self.timer_manager.stop_all_user_timers(user_id)

            progress = self.active_tests.get(user_id)
            if not progress:
                logger.warning(f"No active progress found for user {user_id} during persist")
                return False

            db: Database = dialog_manager.middleware_data.get("db") or get_global_database()
            if not db:
                logger.error("No database connection to persist results")
                return False

            session = await db.get_session()
            try:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)

                user = await user_repo.get_user_by_telegram_id(user_id)
                if not user:
                    logger.error(f"User {user_id} not found for persist")
                    return False

                test_result = await dept_repo.get_or_create_test_result(user.id, config.test_type)

                # Сохраняем ответы в порядке вопросов
                for q in config.questions:
                    ans = progress.answers.get(q.number)
                    # Если по какой-то причине ответа нет — считаем пустым/таймаутом
                    if not ans:
                        ans = {
                            "question_number": q.number,
                            "question_text": q.text,
                            "answer_text": "",
                            "time_limit": q.time_limit,
                            "time_taken": q.time_limit,
                            "is_timeout": True,
                            "correct_answer": q.correct_answer,
                        }

                    # Определяем правильность при наличии эталона
                    is_correct = None
                    if q.correct_answer is not None:
                        is_correct = (ans.get("answer_text", "").strip().lower() == q.correct_answer.strip().lower())

                    await dept_repo.save_answer(
                        test_result.id,
                        ans["question_number"],
                        ans.get("question_text", q.text),
                        ans.get("answer_text", ""),
                        ans.get("time_limit", q.time_limit),
                        ans.get("time_taken", 0),
                        ans.get("is_timeout", False),
                        ans.get("correct_answer", q.correct_answer),
                        is_correct,
                    )

                # Отмечаем завершение
                await dept_repo.complete_test(user.id, config.test_type)

                await session.commit()

                # Медиа-очистка после удачного сохранения
                await self.cleanup_question_media(dialog_manager, config)
                await self.cleanup_test_media(dialog_manager, config)

                # Помечаем прогресс как завершённый и очищаем
                progress.is_completed = True
                # Отмечаем в dialog_data, что сохранение выполнено (для быстрых редиректов геттеров)
                try:
                    dialog_manager.dialog_data[f"test_{config.test_type}_persisted"] = True
                    dialog_manager.dialog_data[f"test_{config.test_type}_completion_pending"] = False
                    # На случай висящего advance_to очищаем
                    adv_key = f"test_{config.test_type}_advance_to"
                    if adv_key in dialog_manager.dialog_data:
                        dialog_manager.dialog_data.pop(adv_key, None)
                except Exception:
                    pass
                logger.info(f"Persist completed for {config.test_type}, user {user_id}")
                return True
            finally:
                await session.close()
        except Exception as e:
            logger.error(f"Error persisting results for {config.test_type}, user {user_id}: {e}", exc_info=True)
            return False
    
    async def _save_answer_to_db(self, dialog_manager: DialogManager, config: TestConfig, 
                               question: TestQuestion, answer: str, time_taken: int, 
                               is_timeout: bool) -> bool:
        """Сохранение ответа в базу данных"""
        try:
            # Пытаемся получить db из middleware_data
            db: Database = dialog_manager.middleware_data.get("db")
            
            # Если db нет в middleware (timeout случай), используем глобальную БД
            if not db:
                logger.warning("Database not available in middleware_data, trying global database")
                db = get_global_database()
                
            if not db:
                logger.error("Database not available in middleware_data and global database")
                # Сохраняем ответ локально для retry
                self._save_answer_for_retry(dialog_manager, config, question, answer, time_taken, is_timeout)
                return False
                
            user_id = dialog_manager.event.from_user.id
            session = await db.get_session()
            
            try:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)
                
                # Получаем пользователя
                user = await user_repo.get_user_by_telegram_id(user_id)
                if not user:
                    logger.error(f"User {user_id} not found")
                    return False
                
                # Получаем или создаем результат теста
                test_result = await dept_repo.get_or_create_test_result(user.id, config.test_type)
                
                # Определяем правильность ответа
                is_correct = None
                if question.correct_answer:
                    is_correct = answer.strip().lower() == question.correct_answer.strip().lower()
                
                # Сохраняем ответ
                await dept_repo.save_answer(
                    test_result.id,
                    question.number,
                    question.text,
                    answer,
                    question.time_limit,
                    time_taken,
                    is_timeout,
                    question.correct_answer,
                    is_correct
                )
                
                await session.commit()
                logger.info(f"Answer saved to DB: user {user_id}, {config.test_type} q{question.number}")
                return True
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Database error saving answer: {e}", exc_info=True)
            return False
    
    async def _mark_test_completed(self, dialog_manager: DialogManager, config: TestConfig) -> bool:
        """Отметка теста как завершенного в базе данных"""
        try:
            db: Database = dialog_manager.middleware_data.get("db")
            if not db:
                logger.warning("Database not available in middleware_data, using global database")
                db = get_global_database()
                
            if not db:
                logger.error("Database not available in middleware_data and global database")
                return False
                
            user_id = dialog_manager.event.from_user.id
            session = await db.get_session()
            
            try:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)
                
                # Получаем пользователя
                user = await user_repo.get_user_by_telegram_id(user_id)
                if not user:
                    logger.error(f"User {user_id} not found")
                    return False
                
                # Получаем результат теста
                test_result = await dept_repo.get_or_create_test_result(user.id, config.test_type)
                
                # Отмечаем тест как завершенный
                await dept_repo.complete_test(user.id, config.test_type)
                
                await session.commit()
                logger.info(f"Test marked as completed: user {user_id}, {config.test_type}")
                return True
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Database error marking test completed: {e}", exc_info=True)
            return False
    
    def get_progress(self, user_id: int) -> Optional[TestProgress]:
        """Получение текущего прогресса теста"""
        return self.active_tests.get(user_id)
    
    def get_question_by_number(self, config: TestConfig, question_num: int) -> Optional[TestQuestion]:
        """Получение вопроса по номеру"""
        return next((q for q in config.questions if q.number == question_num), None)
    
    async def cleanup_user_test(self, user_id: int):
        """Очистка данных теста пользователя"""
        await self.timer_manager.stop_all_user_timers(user_id)
        if user_id in self.active_tests:
            del self.active_tests[user_id]
        logger.info(f"Cleaned up test data for user {user_id}")
    
    async def send_test_media(self, dialog_manager: DialogManager, config: TestConfig) -> bool:
        """Отправка медиа при начале теста"""
        if not config.send_media_on_start or not config.media_paths:
            return True  # Медиа не требуется
        
        # Проверяем, не были ли уже отправлены медиа
        if dialog_manager.dialog_data.get(MEDIA_SENT_KEY, False):
            logger.debug(f"Media already sent for {config.test_type} test")
            return True
        
        logger.info(f"Sending media for {config.test_type} test")
        
        message_ids = await MediaHandler.send_test_images(
            dialog_manager=dialog_manager,
            image_paths=config.media_paths,
            caption=config.media_caption
        )
        
        if message_ids:
            # Сохраняем ID сообщений для последующего удаления
            dialog_manager.dialog_data[MEDIA_MESSAGE_IDS_KEY] = message_ids
            dialog_manager.dialog_data[MEDIA_SENT_KEY] = True
            logger.info(f"Media sent successfully for {config.test_type}, message_ids: {message_ids}")
            return True
        else:
            logger.error(f"Failed to send media for {config.test_type}")
            return False
    
    async def send_question_media(self, dialog_manager: DialogManager, config: TestConfig, question: TestQuestion) -> Optional[int]:
        """Отправка медиа для конкретного вопроса"""
        if not question.media_path:
            return None  # Медиа не требуется для этого вопроса
        
        user_id = dialog_manager.event.from_user.id
        question_media_key = f"question_{config.test_type}_q{question.number}_media_sent"
        
        # Проверяем, не было ли уже отправлено медиа для этого вопроса
        if dialog_manager.dialog_data.get(question_media_key, False):
            logger.debug(f"Media already sent for {config.test_type} question {question.number}")
            return None
        
        logger.info(f"Sending media for {config.test_type} question {question.number}")
        
        message_id = await MediaHandler.send_single_image(
            dialog_manager=dialog_manager,
            image_path=question.media_path,
            caption=question.media_caption
        )
        
        if message_id:
            # Сохраняем ID сообщения для последующего удаления
            question_media_ids_key = f"question_{config.test_type}_media_ids"
            existing_ids = dialog_manager.dialog_data.get(question_media_ids_key, [])
            existing_ids.append(message_id)
            dialog_manager.dialog_data[question_media_ids_key] = existing_ids
            dialog_manager.dialog_data[question_media_key] = True
            logger.info(f"Media sent successfully for {config.test_type} question {question.number}, message_id: {message_id}")
            return message_id
        else:
            logger.error(f"Failed to send media for {config.test_type} question {question.number}")
            return None
    
    async def cleanup_question_media(self, dialog_manager: DialogManager, config: TestConfig) -> bool:
        """Удаление медиа отправленных для вопросов после завершения теста"""
        question_media_ids_key = f"question_{config.test_type}_media_ids"
        message_ids = dialog_manager.dialog_data.get(question_media_ids_key)
        
        if not message_ids:
            logger.debug(f"No question media message IDs found for {config.test_type}")
            return True
        
        logger.info(f"Cleaning up question media for {config.test_type}, message_ids: {message_ids}")
        
        success = await MediaHandler.delete_test_images(dialog_manager, message_ids)
        
        if success:
            # Очищаем данные о медиа после успешного удаления
            dialog_manager.dialog_data.pop(question_media_ids_key, None)
            # Очищаем флаги отправки для каждого вопроса
            for question in config.questions:
                question_media_key = f"question_{config.test_type}_q{question.number}_media_sent"
                dialog_manager.dialog_data.pop(question_media_key, None)
            logger.info(f"Question media cleaned up successfully for {config.test_type}")
        
        return success
    
    async def cleanup_test_media(self, dialog_manager: DialogManager, config: TestConfig) -> bool:
        """Удаление медиа после завершения теста"""
        if not config.send_media_on_start:
            return True  # Медиа не отправлялись
        
        message_ids = dialog_manager.dialog_data.get(MEDIA_MESSAGE_IDS_KEY)
        if not message_ids:
            logger.debug(f"No media message IDs found for {config.test_type}")
            return True
        
        logger.info(f"Cleaning up media for {config.test_type}, message_ids: {message_ids}")
        
        success = await MediaHandler.delete_test_images(
            dialog_manager=dialog_manager,
            message_ids=message_ids
        )
        
        if success:
            # Очищаем данные из dialog_data
            dialog_manager.dialog_data.pop(MEDIA_MESSAGE_IDS_KEY, None)
            dialog_manager.dialog_data.pop(MEDIA_SENT_KEY, None)
            logger.info(f"Media cleaned up successfully for {config.test_type}")
        else:
            logger.warning(f"Failed to clean up some media for {config.test_type}")
        
        return success
    
    def _save_answer_for_retry(self, dialog_manager: DialogManager, config: TestConfig, 
                              question: TestQuestion, answer: str, time_taken: int, is_timeout: bool):
        """Локальное сохранение ответа для повторной попытки"""
        try:
            retry_answers = dialog_manager.dialog_data.setdefault("retry_answers", [])
            answer_data = {
                "test_type": config.test_type,
                "question_number": question.number,
                "answer": answer,
                "time_taken": time_taken,
                "is_timeout": is_timeout,
                "timestamp": int(time.time())
            }
            retry_answers.append(answer_data)
            logger.info(f"Answer saved for retry: {config.test_type} q{question.number}")
        except Exception as e:
            logger.error(f"Failed to save answer for retry: {e}", exc_info=True)
    
    async def retry_failed_answers(self, dialog_manager: DialogManager) -> bool:
        """Повторная попытка сохранения failed ответов"""
        retry_answers = dialog_manager.dialog_data.get("retry_answers", [])
        if not retry_answers:
            return True
        
        logger.info(f"Retrying {len(retry_answers)} failed answers")
        
        try:
            db: Database = dialog_manager.middleware_data.get("db")
            if not db:
                db = get_global_database()
                
            if not db:
                logger.error("No database connection available for retry")
                return False
            
            session = await db.get_session()
            successful_retries = []
            
            try:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)
                user_id = dialog_manager.event.from_user.id
                user = await user_repo.get_user_by_telegram_id(user_id)
                
                if not user:
                    logger.error(f"User {user_id} not found for retry")
                    return False
                
                for i, answer_data in enumerate(retry_answers):
                    try:
                        # Получаем или создаем результат теста
                        test_result = await dept_repo.get_or_create_test_result(user.id, answer_data["test_type"])
                        
                        # Сохраняем ответ
                        await dept_repo.save_answer(
                            test_result.id,
                            answer_data["question_number"],
                            answer_data["answer"],
                            answer_data["time_taken"],
                            is_correct=None,  # правильность не определяем при retry
                            is_timeout=answer_data["is_timeout"]
                        )
                        
                        successful_retries.append(i)
                        logger.info(f"Successfully retried answer: {answer_data['test_type']} q{answer_data['question_number']}")
                        
                    except Exception as answer_error:
                        logger.error(f"Failed to retry answer {i}: {answer_error}", exc_info=True)
                        continue
                
                await session.commit()
                
                # Удаляем успешно сохраненные ответы из retry списка
                for index in reversed(successful_retries):
                    retry_answers.pop(index)
                
                dialog_manager.dialog_data["retry_answers"] = retry_answers
                
                logger.info(f"Retry completed: {len(successful_retries)} successful, {len(retry_answers)} remaining")
                return len(retry_answers) == 0
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Error during retry operation: {e}", exc_info=True)
            return False
    
    async def get_retry_stats(self, dialog_manager: DialogManager) -> Dict[str, Any]:
        """Получение статистики retry ответов"""
        retry_answers = dialog_manager.dialog_data.get("retry_answers", [])
        stats = {
            "pending_retries": len(retry_answers),
            "retry_by_test": {},
            "oldest_timestamp": None,
            "newest_timestamp": None
        }
        
        if retry_answers:
            # Группировка по типам тестов
            for answer in retry_answers:
                test_type = answer["test_type"]
                if test_type not in stats["retry_by_test"]:
                    stats["retry_by_test"][test_type] = 0
                stats["retry_by_test"][test_type] += 1
            
            # Временные метки
            timestamps = [answer["timestamp"] for answer in retry_answers]
            stats["oldest_timestamp"] = min(timestamps)
            stats["newest_timestamp"] = max(timestamps)
        
        return stats


# Глобальный экземпляр движка
test_engine = TestEngine()