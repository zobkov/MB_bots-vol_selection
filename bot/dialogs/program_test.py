"""
Диалог тестирования отдела Программы
"""
from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Start, Cancel
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput

from bot.states import ProgramTestSG, TestingSG
from bot.dialogs.timer_utils import get_timer_progress_data, create_timer_display, calculate_time_taken, start_timer_background, stop_timer
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
import logging

logger = logging.getLogger(__name__)


# Async геттеры для вопросов program
async def get_program_q1_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_program_q1_data called with dialog_manager: {dialog_manager}")
    
    # Запускаем таймер если он еще не запущен
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == ProgramTestSG.q1:
            logger.debug("Starting timer for program_q1")
            await start_timer_background(dialog_manager, "program_q1", 120, on_program_q1_timeout_bg)
    
    return {"question_text": PROGRAM_QUESTIONS[1]["text"]}

async def get_program_q2_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_program_q2_data called with dialog_manager: {dialog_manager}")
    
    # Запускаем таймер если он еще не запущен
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == ProgramTestSG.q2:
            logger.debug("Starting timer for program_q2")
            await start_timer_background(dialog_manager, "program_q2", 30, on_program_q2_timeout_bg)
    
    return {"question_text": PROGRAM_QUESTIONS[2]["text"]}

async def get_program_q3_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_program_q3_data called with dialog_manager: {dialog_manager}")
    
    # Запускаем таймер если он еще не запущен
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == ProgramTestSG.q3:
            logger.debug("Starting timer for program_q3")
            await start_timer_background(dialog_manager, "program_q3", 90, on_program_q3_timeout_bg)
    
    return {"question_text": PROGRAM_QUESTIONS[3]["text"]}

async def get_program_q4_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_program_q4_data called with dialog_manager: {dialog_manager}")
    
    # Запускаем таймер если он еще не запущен
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == ProgramTestSG.q4:
            logger.debug("Starting timer for program_q4")
            await start_timer_background(dialog_manager, "program_q4", 90, on_program_q4_timeout_bg)
    
    return {"question_text": PROGRAM_QUESTIONS[4]["text"]}

async def get_program_q5_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_program_q5_data called with dialog_manager: {dialog_manager}")
    
    # Запускаем таймер если он еще не запущен
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == ProgramTestSG.q5:
            logger.debug("Starting timer for program_q5")
            await start_timer_background(dialog_manager, "program_q5", 90, on_program_q5_timeout_bg)
    
    return {"question_text": PROGRAM_QUESTIONS[5]["text"]}

async def get_program_q6_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_program_q6_data called with dialog_manager: {dialog_manager}")
    
    # Запускаем таймер если он еще не запущен
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == ProgramTestSG.q6:
            logger.debug("Starting timer for program_q6")
            await start_timer_background(dialog_manager, "program_q6", 90, on_program_q6_timeout_bg)
    
    return {"question_text": PROGRAM_QUESTIONS[6]["text"]}



# Данные вопросов программы
PROGRAM_QUESTIONS = {
    1: {
        "text": "Представьте, что в первый день число гостей превзошло все ожидания и в гардеробе скопилась большая очередь, создающая помехи для прохода. Как вы поступите? Возьмете ли вы на себя инициативу решить проблему?",
        "time_limit": 120
    },
    2: {
        "text": "Что поможет распознать гостя на площадке (например, участник, спикер, представитель компании, журналист)?\nНапиши свой вариант ответа.",
        "time_limit": 30
    },
    3: {
        "text": "Что вы сделаете, если именного бейджа для спикера, который пришел регистрироваться, не будет среди всех подготовленных бейджей?",
        "time_limit": 90
    },
    4: {
        "text": "Представь ситуацию: во время мероприятия в гибридной аудитории резко оборвалось собрание в Microsoft Teams, через которое транслировалось онлайн-выступление спикера. Ваш тим-лидер не рядом, а решить проблему нужно за считанные минуты. Коротко опишите свои действия.",
        "time_limit": 90
    },
    5: {
        "text": "Что вы будете делать, если к вам подойдет спикер, который опаздывает на мероприятие с его участием и не знает, куда идти?",
        "time_limit": 90
    },
    6: {
        "text": "Вы можете описать себя как пунктуального и ответственного человека? Можете ли привести нестандартный пример, чтобы продемонстрировать это качество?",
        "time_limit": 90
    }
}


async def save_program_answer_and_proceed(dialog_manager: DialogManager, question_num: int, answer: str):
    """Сохранить ответ и перейти к следующему вопросу"""
    logger.debug(f"save_program_answer_and_proceed called with question_num: {question_num}, answer: {answer}")
    try:
        # Останавливаем таймер
        timer_key = f"program_q{question_num}"
        await stop_timer(dialog_manager, timer_key)
        
        # Вычисляем время ответа
        time_taken = calculate_time_taken(dialog_manager, timer_key)
        is_timeout = dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
        
        # Сохраняем в БД
        db: Database = dialog_manager.middleware_data.get("db")
        if db:
            user_id = dialog_manager.event.from_user.id
            session = await db.get_session()
            try:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)
                
                # Получаем пользователя
                user = await user_repo.get_user_by_telegram_id(user_id)
                if user:
                    # Получаем или создаем результат теста
                    test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                    
                    # Сохраняем ответ
                    question_data = PROGRAM_QUESTIONS[question_num]
                    await dept_repo.save_answer(
                        test_result.id,
                        question_num,
                        question_data["text"],
                        answer,
                        question_data["time_limit"],
                        time_taken,
                        is_timeout
                    )
            finally:
                await session.close()
        
        logger.info(f"Saved program answer for question {question_num}, time: {time_taken}s")
        
        # Переходим к следующему вопросу или завершаем
        if question_num < 6:
            logger.debug(f"Transitioning from question {question_num} to next question")
            next_state = getattr(ProgramTestSG, f"q{question_num + 1}")
            logger.debug(f"Switching to state: {next_state}")
            await dialog_manager.switch_to(next_state)
            logger.debug(f"After switch_to(), current state: {dialog_manager.current_context().state}")
        else:
            # Отмечаем тест как завершенный
            if db:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        await dept_repo.complete_test(user.id, "program")
                        # Save checkpoint after completing all program questions
                        await save_department_completion_checkpoint_with_session(user.id, "program", session)
                finally:
                    await session.close()
            
            await dialog_manager.switch_to(ProgramTestSG.completed)
        
    except Exception as e:
        logger.error(f"Error saving program answer for question {question_num}: {e}")
        await dialog_manager.event.answer("Произошла ошибка. Попробуйте еще раз.")


# Обработчики ввода
async def on_program_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_program_q1_input called with text: {text}")
    await save_program_answer_and_proceed(dialog_manager, 1, text)

async def on_program_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_program_q2_input called with text: {text}")
    await save_program_answer_and_proceed(dialog_manager, 2, text)

async def on_program_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_program_q3_input called with text: {text}")
    await save_program_answer_and_proceed(dialog_manager, 3, text)

async def on_program_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_program_q4_input called with text: {text}")
    await save_program_answer_and_proceed(dialog_manager, 4, text)

async def on_program_q5_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_program_q5_input called with text: {text}")
    await save_program_answer_and_proceed(dialog_manager, 5, text)

async def on_program_q6_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_program_q6_input called with text: {text}")
    await save_program_answer_and_proceed(dialog_manager, 6, text)


# Обработчики таймаута для background manager
async def on_program_q1_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: on_program_q1_timeout_bg вызван для {timer_key}")
    
    # Сохраняем пустой ответ в БД при таймауте
    try:
        # Получаем dialog_manager из bg_manager
        from aiogram_dialog.manager.manager import ManagerImpl
        dialog_manager = None
        if hasattr(bg_manager, '_manager'):
            dialog_manager = bg_manager._manager
        elif isinstance(bg_manager, ManagerImpl):
            dialog_manager = bg_manager
            
        if dialog_manager and hasattr(dialog_manager, 'middleware_data'):
            db = dialog_manager.middleware_data.get("db")
            if db and hasattr(dialog_manager, 'event') and dialog_manager.event:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    from database.repositories import DepartmentTestRepository, UserRepository
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                        question_data = PROGRAM_QUESTIONS[1]
                        time_taken = calculate_time_taken(dialog_manager, timer_key)
                        await dept_repo.save_answer(
                            test_result.id, 1, question_data["text"], "", 
                            question_data["time_limit"], time_taken, True
                        )
                        logger.info(f"Saved timeout answer for program question 1")
                finally:
                    await session.close()
    except Exception as e:
        logger.error(f"Error saving timeout answer for question 1: {e}")
    
    # Отмечаем таймаут в данных и переходим к следующему вопросу
    await bg_manager.update({
        f"{timer_key}_answer": "",
        f"{timer_key}_timeout": True,
        f"{timer_key}_stopped": True,
    })
    # Используем next() вместо switch_to() для более безопасного перехода
    await bg_manager.next()

async def on_program_q2_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: on_program_q2_timeout_bg вызван для {timer_key}")
    
    # Сохраняем пустой ответ в БД при таймауте (аналогично q1)
    try:
        from aiogram_dialog.manager.manager import ManagerImpl
        dialog_manager = None
        if hasattr(bg_manager, '_manager'):
            dialog_manager = bg_manager._manager
        elif isinstance(bg_manager, ManagerImpl):
            dialog_manager = bg_manager
            
        if dialog_manager and hasattr(dialog_manager, 'middleware_data'):
            db = dialog_manager.middleware_data.get("db")
            if db and hasattr(dialog_manager, 'event') and dialog_manager.event:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    from database.repositories import DepartmentTestRepository, UserRepository
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                        question_data = PROGRAM_QUESTIONS[2]
                        time_taken = calculate_time_taken(dialog_manager, timer_key)
                        await dept_repo.save_answer(
                            test_result.id, 2, question_data["text"], "", 
                            question_data["time_limit"], time_taken, True
                        )
                        logger.info(f"Saved timeout answer for program question 2")
                finally:
                    await session.close()
    except Exception as e:
        logger.error(f"Error saving timeout answer for question 2: {e}")
    
    await bg_manager.update({
        f"{timer_key}_answer": "",
        f"{timer_key}_timeout": True,
        f"{timer_key}_stopped": True,
    })
    await bg_manager.next()

async def on_program_q3_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: on_program_q3_timeout_bg вызван для {timer_key}")
    
    # Сохраняем пустой ответ в БД при таймауте
    try:
        from aiogram_dialog.manager.manager import ManagerImpl
        dialog_manager = None
        if hasattr(bg_manager, '_manager'):
            dialog_manager = bg_manager._manager
        elif isinstance(bg_manager, ManagerImpl):
            dialog_manager = bg_manager
            
        if dialog_manager and hasattr(dialog_manager, 'middleware_data'):
            db = dialog_manager.middleware_data.get("db")
            if db and hasattr(dialog_manager, 'event') and dialog_manager.event:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    from database.repositories import DepartmentTestRepository, UserRepository
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                        question_data = PROGRAM_QUESTIONS[3]
                        time_taken = calculate_time_taken(dialog_manager, timer_key)
                        await dept_repo.save_answer(
                            test_result.id, 3, question_data["text"], "", 
                            question_data["time_limit"], time_taken, True
                        )
                        logger.info(f"Saved timeout answer for program question 3")
                finally:
                    await session.close()
    except Exception as e:
        logger.error(f"Error saving timeout answer for question 3: {e}")
    
    await bg_manager.update({
        f"{timer_key}_answer": "",
        f"{timer_key}_timeout": True,
        f"{timer_key}_stopped": True,
    })
    await bg_manager.next()

async def on_program_q4_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: on_program_q4_timeout_bg вызван для {timer_key}")
    
    # Сохраняем пустой ответ в БД при таймауте
    try:
        from aiogram_dialog.manager.manager import ManagerImpl
        dialog_manager = None
        if hasattr(bg_manager, '_manager'):
            dialog_manager = bg_manager._manager
        elif isinstance(bg_manager, ManagerImpl):
            dialog_manager = bg_manager
            
        if dialog_manager and hasattr(dialog_manager, 'middleware_data'):
            db = dialog_manager.middleware_data.get("db")
            if db and hasattr(dialog_manager, 'event') and dialog_manager.event:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    from database.repositories import DepartmentTestRepository, UserRepository
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                        question_data = PROGRAM_QUESTIONS[4]
                        time_taken = calculate_time_taken(dialog_manager, timer_key)
                        await dept_repo.save_answer(
                            test_result.id, 4, question_data["text"], "", 
                            question_data["time_limit"], time_taken, True
                        )
                        logger.info(f"Saved timeout answer for program question 4")
                finally:
                    await session.close()
    except Exception as e:
        logger.error(f"Error saving timeout answer for question 4: {e}")
    
    await bg_manager.update({
        f"{timer_key}_answer": "",
        f"{timer_key}_timeout": True,
        f"{timer_key}_stopped": True,
    })
    await bg_manager.next()

async def on_program_q5_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: on_program_q5_timeout_bg вызван для {timer_key}")
    
    # Сохраняем пустой ответ в БД при таймауте
    try:
        from aiogram_dialog.manager.manager import ManagerImpl
        dialog_manager = None
        if hasattr(bg_manager, '_manager'):
            dialog_manager = bg_manager._manager
        elif isinstance(bg_manager, ManagerImpl):
            dialog_manager = bg_manager
            
        if dialog_manager and hasattr(dialog_manager, 'middleware_data'):
            db = dialog_manager.middleware_data.get("db")
            if db and hasattr(dialog_manager, 'event') and dialog_manager.event:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    from database.repositories import DepartmentTestRepository, UserRepository
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                        question_data = PROGRAM_QUESTIONS[5]
                        time_taken = calculate_time_taken(dialog_manager, timer_key)
                        await dept_repo.save_answer(
                            test_result.id, 5, question_data["text"], "", 
                            question_data["time_limit"], time_taken, True
                        )
                        logger.info(f"Saved timeout answer for program question 5")
                finally:
                    await session.close()
    except Exception as e:
        logger.error(f"Error saving timeout answer for question 5: {e}")
    
    await bg_manager.update({
        f"{timer_key}_answer": "",
        f"{timer_key}_timeout": True,
        f"{timer_key}_stopped": True,
    })
    await bg_manager.next()

async def on_program_q6_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: on_program_q6_timeout_bg вызван для {timer_key}")
    
    # Сохраняем пустой ответ в БД при таймауте
    try:
        from aiogram_dialog.manager.manager import ManagerImpl
        dialog_manager = None
        if hasattr(bg_manager, '_manager'):
            dialog_manager = bg_manager._manager
        elif isinstance(bg_manager, ManagerImpl):
            dialog_manager = bg_manager
            
        if dialog_manager and hasattr(dialog_manager, 'middleware_data'):
            db = dialog_manager.middleware_data.get("db")
            if db and hasattr(dialog_manager, 'event') and dialog_manager.event:
                user_id = dialog_manager.event.from_user.id
                session = await db.get_session()
                try:
                    from database.repositories import DepartmentTestRepository, UserRepository
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        test_result = await dept_repo.get_or_create_test_result(user.id, "program")
                        question_data = PROGRAM_QUESTIONS[6]
                        time_taken = calculate_time_taken(dialog_manager, timer_key)
                        await dept_repo.save_answer(
                            test_result.id, 6, question_data["text"], "", 
                            question_data["time_limit"], time_taken, True
                        )
                        # Отмечаем тест как завершенный
                        await dept_repo.complete_test(user.id, "program")
                        # Save checkpoint after completing all program questions
                        await save_department_completion_checkpoint_with_session(user.id, "program", session)
                        logger.info(f"Saved timeout answer for program question 6 and completed test")
                finally:
                    await session.close()
    except Exception as e:
        logger.error(f"Error saving timeout answer for question 6: {e}")
    
    await bg_manager.update({
        f"{timer_key}_answer": "",
        f"{timer_key}_timeout": True,
        f"{timer_key}_stopped": True,
    })
    # После 6-го вопроса переходим к завершению - используем next() вместо switch_to()
    await bg_manager.next()


# Обработчики таймаута (устаревшие - для совместимости)
async def on_program_q1_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_program_answer_and_proceed(dialog_manager, 1, "")

async def on_program_q2_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_program_answer_and_proceed(dialog_manager, 2, "")

async def on_program_q3_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_program_answer_and_proceed(dialog_manager, 3, "")

async def on_program_q4_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_program_answer_and_proceed(dialog_manager, 4, "")

async def on_program_q5_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_program_answer_and_proceed(dialog_manager, 5, "")

async def on_program_q6_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_program_answer_and_proceed(dialog_manager, 6, "")


# Функции запуска таймеров удалены - таймеры запускаются через геттеры


# Обработчик возврата к выбору отделов
async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Возврат к выбору отделов"""
    await dialog_manager.start(TestingSG.department_selection, mode=StartMode.RESET_STACK)


program_test_dialog = Dialog(
    # Вопрос 1 (120 секунд)
    Window(
        Format("📋 <b>Программа - Вопрос 1/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 120 секунд)"),
        *create_timer_display("program_q1"),
        TextInput(
            id="program_q1_input",
            on_success=on_program_q1_input
        ),
        state=ProgramTestSG.q1,
        getter=[
            get_program_q1_data,
            get_timer_progress_data("program_q1")
        ],
    ),
    
    # Вопрос 2 (30 секунд)
    Window(
        Format("📋 <b>Программа - Вопрос 2/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 30 секунд)"),
        *create_timer_display("program_q2"),
        TextInput(
            id="program_q2_input",
            on_success=on_program_q2_input
        ),
        state=ProgramTestSG.q2,
        getter=[
            get_program_q2_data,
            get_timer_progress_data("program_q2")
        ],
    ),
    
    # Вопрос 3 (90 секунд)
    Window(
        Format("📋 <b>Программа - Вопрос 3/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("program_q3"),
        TextInput(
            id="program_q3_input",
            on_success=on_program_q3_input
        ),
        state=ProgramTestSG.q3,
        getter=[
            get_program_q3_data,
            get_timer_progress_data("program_q3")
        ],
    ),
    
    # Вопрос 4 (90 секунд)
    Window(
        Format("📋 <b>Программа - Вопрос 4/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("program_q4"),
        TextInput(
            id="program_q4_input",
            on_success=on_program_q4_input
        ),
        state=ProgramTestSG.q4,
        getter=[
            get_program_q4_data,
            get_timer_progress_data("program_q4")
        ],
    ),
    
    # Вопрос 5 (90 секунд)
    Window(
        Format("📋 <b>Программа - Вопрос 5/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("program_q5"),
        TextInput(
            id="program_q5_input",
            on_success=on_program_q5_input
        ),
        state=ProgramTestSG.q5,
        getter=[
            get_program_q5_data,
            get_timer_progress_data("program_q5")
        ],
    ),
    
    # Вопрос 6 (90 секунд)
    Window(
        Format("📋 <b>Программа - Вопрос 6/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("program_q6"),
        TextInput(
            id="program_q6_input",
            on_success=on_program_q6_input
        ),
        state=ProgramTestSG.q6,
        getter=[
            get_program_q6_data,
            get_timer_progress_data("program_q6")
        ],
    ),
    
    # Завершение теста
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Программы!</b>\n\n"
              "Тест пройден! Ты можешь вернуться к выбору отделов и пройти тесты "
              "по другим интересующим тебя направлениям, или завершить тестирование."),
        Button(
            Const("🔙 Вернуться к выбору отделов"),
            id="back_to_departments",
            on_click=on_back_to_departments
        ),
        state=ProgramTestSG.completed,
    ),
)