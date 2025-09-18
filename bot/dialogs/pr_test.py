"""
Диалог тестирования отдела PR
"""
from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Start, Cancel
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput

from bot.states import PRTestSG, TestingSG
from bot.dialogs.timer_utils import timer_manager, get_timer_progress_data, create_timer_display, calculate_time_taken
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database
import logging

logger = logging.getLogger(__name__)


# Данные вопросов PR
PR_QUESTIONS = {
    1: {
        "text": "Как ты думаешь, в чем может возникнуть сложность при работе волонтером PR отдела? Кратко изложи ответ.",
        "time_limit": 60
    },
    2: {
        "text": "Представь ситуацию: в первый день конференции на площадку приехали крупные СМИ, твой тим-лидер и менеджеры отдела заняты и не успели провести инструктаж для подобных случаев. Как бы ты поступил(а)?",
        "time_limit": 120
    },
    3: {
        "text": "Представь, что СМИ захотели взять интервью у конкретного спикера и подошли к тебе за помощью. Как бы ты это организовал(а)?",
        "time_limit": 90
    },
    4: {
        "text": "Что из перечисленного является основанием немедленно обратиться к тим-лидеру или организатору:\nа) журналисты просят показать им кафетерий\nб) кому-то из гостей на площадке стало плохо\nв) СМИ мешают проведению мероприятия\nг) требуется техническая помощь в аудитории\nд) все вышеперечисленное\n\nНапиши букву или буквы (строчные, без пробелов).",
        "time_limit": 30,
        "correct_answer": "д"
    }
}


async def save_pr_answer_and_proceed(dialog_manager: DialogManager, question_num: int, answer: str):
    """Сохранить ответ и перейти к следующему вопросу"""
    try:
        timer_key = f"pr_q{question_num}"
        await timer_manager.stop_timer(timer_key)
        
        time_taken = calculate_time_taken(dialog_manager, timer_key)
        is_timeout = dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
        
        db: Database = dialog_manager.middleware_data.get("db")
        if db:
            user_id = dialog_manager.event.from_user.id
            async with db.session() as session:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)
                
                user = await user_repo.get_user_by_telegram_id(user_id)
                if user:
                    test_result = await dept_repo.get_or_create_test_result(user.id, "pr")
                    
                    question_data = PR_QUESTIONS[question_num]
                    correct_answer = question_data.get("correct_answer")
                    is_correct = None
                    
                    if correct_answer and answer.strip():
                        is_correct = answer.strip().lower() == correct_answer.lower()
                    
                    await dept_repo.save_answer(
                        test_result.id,
                        question_num,
                        question_data["text"],
                        answer,
                        question_data["time_limit"],
                        time_taken,
                        is_timeout,
                        correct_answer,
                        is_correct
                    )
        
        logger.info(f"Saved PR answer for question {question_num}, time: {time_taken}s")
        
        if question_num < 4:
            await dialog_manager.next()
        else:
            if db:
                user_id = dialog_manager.event.from_user.id
                async with db.session() as session:
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        await dept_repo.complete_test(user.id, "pr")
            
            await dialog_manager.switch_to(PRTestSG.completed)
        
    except Exception as e:
        logger.error(f"Error saving PR answer for question {question_num}: {e}")


# Обработчики ввода
async def on_pr_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_pr_answer_and_proceed(dialog_manager, 1, text)

async def on_pr_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_pr_answer_and_proceed(dialog_manager, 2, text)

async def on_pr_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_pr_answer_and_proceed(dialog_manager, 3, text)

async def on_pr_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_pr_answer_and_proceed(dialog_manager, 4, text)


# Обработчики таймаута
async def on_pr_q1_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_pr_answer_and_proceed(dialog_manager, 1, "")

async def on_pr_q2_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_pr_answer_and_proceed(dialog_manager, 2, "")

async def on_pr_q3_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_pr_answer_and_proceed(dialog_manager, 3, "")

async def on_pr_q4_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_pr_answer_and_proceed(dialog_manager, 4, "")


# Функции запуска таймеров
async def start_pr_timer_q1(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "pr_q1", 60, on_pr_q1_timeout)

async def start_pr_timer_q2(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "pr_q2", 120, on_pr_q2_timeout)

async def start_pr_timer_q3(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "pr_q3", 90, on_pr_q3_timeout)

async def start_pr_timer_q4(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "pr_q4", 30, on_pr_q4_timeout)


async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    await dialog_manager.start(TestingSG.department_selection, mode=StartMode.RESET_STACK)


pr_test_dialog = Dialog(
    Window(
        Format("📰 <b>PR - Вопрос 1/4</b>\n\n{question_text}\n\n(Время на ответ: 60 секунд)"),
        *create_timer_display("pr_q1"),
        TextInput(id="pr_q1_input", on_success=on_pr_q1_input),
        state=PRTestSG.q1,
        getter=[lambda **kwargs: {"question_text": PR_QUESTIONS[1]["text"]}, get_timer_progress_data("pr_q1")],
        on_process_result=start_pr_timer_q1,
    ),
    Window(
        Format("📰 <b>PR - Вопрос 2/4</b>\n\n{question_text}\n\n(Время на ответ: 120 секунд)"),
        *create_timer_display("pr_q2"),
        TextInput(id="pr_q2_input", on_success=on_pr_q2_input),
        state=PRTestSG.q2,
        getter=[lambda **kwargs: {"question_text": PR_QUESTIONS[2]["text"]}, get_timer_progress_data("pr_q2")],
        on_process_result=start_pr_timer_q2,
    ),
    Window(
        Format("📰 <b>PR - Вопрос 3/4</b>\n\n{question_text}\n\n(Время на ответ: 90 секунд)"),
        *create_timer_display("pr_q3"),
        TextInput(id="pr_q3_input", on_success=on_pr_q3_input),
        state=PRTestSG.q3,
        getter=[lambda **kwargs: {"question_text": PR_QUESTIONS[3]["text"]}, get_timer_progress_data("pr_q3")],
        on_process_result=start_pr_timer_q3,
    ),
    Window(
        Format("📰 <b>PR - Вопрос 4/4</b>\n\n{question_text}\n\n(Время на ответ: 30 секунд)"),
        *create_timer_display("pr_q4"),
        TextInput(id="pr_q4_input", on_success=on_pr_q4_input),
        state=PRTestSG.q4,
        getter=[lambda **kwargs: {"question_text": PR_QUESTIONS[4]["text"]}, get_timer_progress_data("pr_q4")],
        on_process_result=start_pr_timer_q4,
    ),
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела PR!</b>\n\n"
              "Тест пройден! Ты можешь вернуться к выбору отделов и пройти тесты "
              "по другим интересующим тебя направлениям, или завершить тестирование."),
        Button(Const("🔙 Вернуться к выбору отделов"), id="back_to_departments", on_click=on_back_to_departments),
        state=PRTestSG.completed,
    ),
)