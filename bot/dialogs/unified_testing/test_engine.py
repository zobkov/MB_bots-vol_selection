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
from .enhanced_timer_utils import EnhancedTimerManager

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
    """Основной движок для управления тестированием"""
    
    def __init__(self):
        self.timer_manager = EnhancedTimerManager()
        self.active_tests: Dict[int, TestProgress] = {}  # user_id -> TestProgress
        
    def get_user_timer_key(self, user_id: int, test_type: str, question_num: int) -> str:
        """Генерация ключа таймера для конкретного пользователя"""
        return f"user_{user_id}_{test_type}_q{question_num}"
    
    async def start_test(self, dialog_manager: DialogManager, config: TestConfig) -> TestProgress:
        """Запуск нового теста"""
        user_id = dialog_manager.event.from_user.id
        
        logger.info(f"Starting {config.test_type} test for user {user_id}")
        
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
        
        # Сохраняем начало теста в dialog_data
        dialog_manager.dialog_data[f"test_{config.test_type}_started"] = True
        dialog_manager.dialog_data[f"test_{config.test_type}_config"] = config
        dialog_manager.dialog_data[f"test_{config.test_type}_progress"] = progress
        
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
        """Сохранение ответа и переход к следующему вопросу"""
        user_id = dialog_manager.event.from_user.id
        timer_key = self.get_user_timer_key(user_id, config.test_type, question_num)
        
        logger.info(f"Saving answer for user {user_id}, {config.test_type} q{question_num}: '{answer}' (timeout: {is_timeout})")
        
        try:
            # Останавливаем таймер
            await self.timer_manager.stop_timer(dialog_manager, timer_key)
            
            # Вычисляем время ответа
            time_taken = self.timer_manager.calculate_time_taken(dialog_manager, timer_key)
            
            # Получаем вопрос
            question = next((q for q in config.questions if q.number == question_num), None)
            if not question:
                logger.error(f"Question {question_num} not found in config")
                return False
            
            # Сохраняем в БД
            success = await self._save_answer_to_db(
                dialog_manager, config, question, answer, time_taken, is_timeout
            )
            
            if not success:
                logger.error(f"Failed to save answer to database")
                return False
            
            # Обновляем прогресс
            if user_id in self.active_tests:
                progress = self.active_tests[user_id]
                progress.answers[question_num] = answer
                
                # Проверяем завершение теста
                if len(progress.answers) >= progress.total_questions:
                    await self.complete_test(dialog_manager, config)
                else:
                    progress.current_question = question_num + 1
            
            logger.info(f"Answer saved successfully for user {user_id}, {config.test_type} q{question_num}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving answer for user {user_id}, {config.test_type} q{question_num}: {e}", exc_info=True)
            return False
    
    async def handle_timeout(self, bg_manager, config: TestConfig, question_num: int, timer_key: str):
        """Обработка таймаута вопроса с прямым переходом"""
        user_id_str = timer_key.split('_')[1]  # извлекаем user_id из ключа
        user_id = int(user_id_str)
        
        logger.info(f"Timeout for user {user_id}, {config.test_type} q{question_num}")
        
        try:
            # Получаем dialog_manager из bg_manager для сохранения ответа
            dialog_manager = getattr(bg_manager, '_manager', None)
            if dialog_manager:
                # Сохраняем пустой ответ при таймауте
                try:
                    await self.save_answer(dialog_manager, config, question_num, "", is_timeout=True)
                    logger.info(f"Saved timeout answer for {config.test_type} q{question_num}")
                except Exception as save_error:
                    logger.error(f"Error saving timeout answer: {save_error}", exc_info=True)
            
            # Выполняем прямой переход к следующему состоянию
            if question_num < len(config.questions):
                # Переходим к следующему вопросу через bg_manager.switch_to()
                next_question_num = question_num + 1
                next_state = getattr(config.states_group, f'q{next_question_num}')
                logger.info(f"Transitioning from q{question_num} to q{next_question_num} via bg_manager.switch_to({next_state})")
                await bg_manager.switch_to(next_state)
            else:
                # Это последний вопрос - завершаем тест здесь, а не в completion_getter
                logger.info(f"Last question {question_num} timed out - completing test directly")
                try:
                    # Завершаем тест в background
                    if dialog_manager:
                        # Устанавливаем флаг завершения в dialog_data
                        test_completed_key = f"test_{config.test_type}_completed"
                        dialog_manager.dialog_data[test_completed_key] = True
                        
                        # Выполняем завершение теста
                        await self.complete_test(dialog_manager, config)
                        logger.info(f"Test {config.test_type} completed during timeout processing")
                    
                    # Переходим к состоянию завершения только после завершения теста - используем next()
                    logger.info(f"Using bg_manager.next() to transition to completed state")
                    await bg_manager.next()
                except Exception as completion_error:
                    logger.error(f"Error completing test during timeout: {completion_error}", exc_info=True)
                    # Все равно переходим к completed state с next()
                    logger.info(f"Using bg_manager.next() as fallback")
                    await bg_manager.next()
                
        except Exception as e:
            logger.error(f"Error handling timeout for {timer_key}: {e}", exc_info=True)
    
    async def complete_test(self, dialog_manager: DialogManager, config: TestConfig):
        """Завершение теста"""
        user_id = dialog_manager.event.from_user.id
        
        logger.info(f"Completing {config.test_type} test for user {user_id}")
        
        try:
            # Пытаемся сохранить все failed ответы перед завершением
            retry_success = await self.retry_failed_answers(dialog_manager)
            if not retry_success:
                retry_stats = await self.get_retry_stats(dialog_manager)
                logger.warning(f"Some answers still pending retry: {retry_stats}")
            
            # Останавливаем все таймеры пользователя
            await self.timer_manager.stop_all_user_timers(user_id)
            
            # Обновляем прогресс
            if user_id in self.active_tests:
                progress = self.active_tests[user_id]
                progress.is_completed = True
            
            # Обновляем is_completed в базе данных
            await self._mark_test_completed(dialog_manager, config)
            
            # Вызываем checkpoint callback если есть
            if config.checkpoint_callback:
                await config.checkpoint_callback(dialog_manager)
            
            logger.info(f"Test {config.test_type} completed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error completing test {config.test_type} for user {user_id}: {e}", exc_info=True)
    
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