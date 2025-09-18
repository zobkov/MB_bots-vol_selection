"""
Утилиты для сохранения чекпоинтов (промежуточных состояний) во время тестирования
"""
import logging
from aiogram_dialog import DialogManager
from database.repositories import UserRepository, DepartmentTestRepository, Stage2Repository
from database.db import Database

logger = logging.getLogger(__name__)


async def save_department_completion_checkpoint(dialog_manager: DialogManager, department_name: str):
    """Сохранение чекпоинта завершения тестирования отдела"""
    try:
        db: Database = dialog_manager.middleware_data.get("db")
        if not db:
            logger.error("Database not found in middleware_data")
            return
        
        user_id = dialog_manager.event.from_user.id
        session = await db.get_session()
        try:
            dept_repo = DepartmentTestRepository(session)
            user_repo = UserRepository(session)
            user = await user_repo.get_user_by_telegram_id(user_id)
            if user:
                await dept_repo.complete_test(user.id, department_name)
                logger.info(f"Checkpoint: {department_name} department test completed for user {user_id}")
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error saving {department_name} department completion checkpoint: {e}")


async def save_department_completion_checkpoint_with_session(user_id: int, department_name: str, session):
    """Сохранение чекпоинта завершения тестирования отдела с готовой сессией"""
    try:
        dept_repo = DepartmentTestRepository(session)
        await dept_repo.complete_test(user_id, department_name)
        logger.info(f"Checkpoint: {department_name} department test completed for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving {department_name} department completion checkpoint: {e}")


async def save_general_questions_completion_checkpoint(dialog_manager: DialogManager):
    """Сохранение чекпоинта завершения всех общих вопросов"""
    try:
        db: Database = dialog_manager.middleware_data.get("db")
        if not db:
            logger.error("Database not found in middleware_data")
            return
        
        user_id = dialog_manager.dialog_data.get("user_id")
        
        session = await db.get_session()
        try:
            stage2_repo = Stage2Repository(session)
            await stage2_repo.mark_general_questions_completed(user_id)
            logger.info(f"Checkpoint: General questions completed for user {user_id}")
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error saving general questions completion checkpoint: {e}")


async def save_stage2_completion_checkpoint(dialog_manager: DialogManager, participation_data: dict):
    """Сохранение чекпоинта завершения второго этапа (вопросы участия)"""
    try:
        db: Database = dialog_manager.middleware_data.get("db")
        if not db:
            logger.error("Database not found in middleware_data")
            return
        
        user_id = dialog_manager.event.from_user.id
        session = await db.get_session()
        try:
            stage2_repo = Stage2Repository(session)
            user_repo = UserRepository(session)
            
            user = await user_repo.get_user_by_telegram_id(user_id)
            if user:
                await stage2_repo.get_or_create_stage2_record(user.id)
                await stage2_repo.update_participation_data(
                    user.id, 
                    participation_data.get("days", []), 
                    participation_data.get("time", [])
                )
                await stage2_repo.mark_general_questions_started(user.id)
                
                logger.info(f"Checkpoint: Stage2 data saved for user {user_id}: {participation_data}")
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error saving stage2 completion checkpoint: {e}")