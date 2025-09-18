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
from bot.dialogs.timer_utils import timer_manager, get_timer_progress_data, create_timer_display, calculate_time_taken
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database
import logging

logger = logging.getLogger(__name__)


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
    try:
        # Останавливаем таймер
        timer_key = f"program_q{question_num}"
        await timer_manager.stop_timer(timer_key)
        
        # Вычисляем время ответа
        time_taken = calculate_time_taken(dialog_manager, timer_key)
        is_timeout = dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
        
        # Сохраняем в БД
        db: Database = dialog_manager.middleware_data.get("db")
        if db:
            user_id = dialog_manager.event.from_user.id
            async with db.session() as session:
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
        
        logger.info(f"Saved program answer for question {question_num}, time: {time_taken}s")
        
        # Переходим к следующему вопросу или завершаем
        if question_num < 6:
            await dialog_manager.next()
        else:
            # Отмечаем тест как завершенный
            if db:
                user_id = dialog_manager.event.from_user.id
                async with db.session() as session:
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        await dept_repo.complete_test(user.id, "program")
            
            await dialog_manager.switch_to(ProgramTestSG.completed)
        
    except Exception as e:
        logger.error(f"Error saving program answer for question {question_num}: {e}")
        await dialog_manager.event.answer("Произошла ошибка. Попробуйте еще раз.")


# Обработчики ввода
async def on_program_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_program_answer_and_proceed(dialog_manager, 1, text)

async def on_program_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_program_answer_and_proceed(dialog_manager, 2, text)

async def on_program_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_program_answer_and_proceed(dialog_manager, 3, text)

async def on_program_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_program_answer_and_proceed(dialog_manager, 4, text)

async def on_program_q5_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_program_answer_and_proceed(dialog_manager, 5, text)

async def on_program_q6_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_program_answer_and_proceed(dialog_manager, 6, text)


# Обработчики таймаута
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


# Функции запуска таймеров
async def start_program_timer_q1(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "program_q1", 120, on_program_q1_timeout)

async def start_program_timer_q2(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "program_q2", 30, on_program_q2_timeout)

async def start_program_timer_q3(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "program_q3", 90, on_program_q3_timeout)

async def start_program_timer_q4(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "program_q4", 90, on_program_q4_timeout)

async def start_program_timer_q5(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "program_q5", 90, on_program_q5_timeout)

async def start_program_timer_q6(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "program_q6", 90, on_program_q6_timeout)


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
            lambda **kwargs: {"question_text": PROGRAM_QUESTIONS[1]["text"]},
            get_timer_progress_data("program_q1")
        ],
        on_process_result=start_program_timer_q1,
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
            lambda **kwargs: {"question_text": PROGRAM_QUESTIONS[2]["text"]},
            get_timer_progress_data("program_q2")
        ],
        on_process_result=start_program_timer_q2,
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
            lambda **kwargs: {"question_text": PROGRAM_QUESTIONS[3]["text"]},
            get_timer_progress_data("program_q3")
        ],
        on_process_result=start_program_timer_q3,
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
            lambda **kwargs: {"question_text": PROGRAM_QUESTIONS[4]["text"]},
            get_timer_progress_data("program_q4")
        ],
        on_process_result=start_program_timer_q4,
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
            lambda **kwargs: {"question_text": PROGRAM_QUESTIONS[5]["text"]},
            get_timer_progress_data("program_q5")
        ],
        on_process_result=start_program_timer_q5,
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
            lambda **kwargs: {"question_text": PROGRAM_QUESTIONS[6]["text"]},
            get_timer_progress_data("program_q6")
        ],
        on_process_result=start_program_timer_q6,
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