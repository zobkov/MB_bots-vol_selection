"""
Диалог тестирования отдела Партнеры
"""
from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Start, Cancel
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput

from bot.states import PartnersTestSG, TestingSG
from bot.dialogs.timer_utils import timer_manager, get_timer_progress_data, create_timer_display, calculate_time_taken
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database
import logging

logger = logging.getLogger(__name__)


# Async геттеры для вопросов partners
async def get_partners_q1_data(**kwargs):
    return {"question_text": PARTNERS_QUESTIONS[1]["text"]}

async def get_partners_q2_data(**kwargs):
    return {"question_text": PARTNERS_QUESTIONS[2]["text"]}

async def get_partners_q3_data(**kwargs):
    return {"question_text": PARTNERS_QUESTIONS[3]["text"]}

async def get_partners_q4_data(**kwargs):
    return {"question_text": PARTNERS_QUESTIONS[4]["text"]}

async def get_partners_q5_data(**kwargs):
    return {"question_text": PARTNERS_QUESTIONS[5]["text"]}



# Данные вопросов партнеров
PARTNERS_QUESTIONS = {
    1: {
        "text": "Вы встретили делегацию компании у КПП и ведёте ее в Михайловскую дачу. О чем будете говорить с представителями компании? Начнёте ли диалог сами или подождёте первого шага с их стороны?\nПодробно опишите свои действия.",
        "time_limit": 120
    },
    2: {
        "text": "Представитель компании просит латте. В спикерской закончились сливки (вы не знаете, есть ли сливки где-то ещё на площадке Конференции), есть только чёрный кофе. Ваши действия?",
        "time_limit": 90
    },
    3: {
        "text": "Укажи, какие из следующих компаний являются постоянными партнёрами конференции? (ответ запиши строчными буквами без пробелов и других символов)\nа) ВТБ\nб) Сибур\nв) VK\nг) Telegram\nд) Северсталь\n\nНапиши букву или буквы.",
        "time_limit": 60,
        "correct_answer": "авд"
    },
    4: {
        "text": "Представитель компании спрашивает вас об организационных моментах, про которые вы ничего не знаете. Незаметно написать коллегам не получилось – они заняты и не отвечают. Ваши действия?",
        "time_limit": 90
    },
    5: {
        "text": "Вам срочно нужно убежать с площадки по семейным обстоятельствам, но через 10 минут вы должны встретить делегацию компании и проводить ее до спикерской. Все менеджеры отдела по работе с партнерами заняты. Ваши действия?",
        "time_limit": 90
    },
    6: {
        "text": "Через 10 минут представитель компании должен быть на мероприятии в 1301. Вы не можете найти его (отвлеклись на пару минут, а он куда-то делся). Ваши действия?",
        "time_limit": 90
    }
}


async def save_partners_answer_and_proceed(dialog_manager: DialogManager, question_num: int, answer: str):
    """Сохранить ответ и перейти к следующему вопросу"""
    try:
        # Останавливаем таймер
        timer_key = f"partners_q{question_num}"
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
                
                user = await user_repo.get_user_by_telegram_id(user_id)
                if user:
                    test_result = await dept_repo.get_or_create_test_result(user.id, "partners")
                    
                    question_data = PARTNERS_QUESTIONS[question_num]
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
        
        logger.info(f"Saved partners answer for question {question_num}, time: {time_taken}s")
        
        if question_num < 6:
            await dialog_manager.next()
        else:
            if db:
                user_id = dialog_manager.event.from_user.id
                async with db.session() as session:
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        await dept_repo.complete_test(user.id, "partners")
            
            await dialog_manager.switch_to(PartnersTestSG.completed)
        
    except Exception as e:
        logger.error(f"Error saving partners answer for question {question_num}: {e}")


# Обработчики ввода
async def on_partners_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_partners_answer_and_proceed(dialog_manager, 1, text)

async def on_partners_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_partners_answer_and_proceed(dialog_manager, 2, text)

async def on_partners_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_partners_answer_and_proceed(dialog_manager, 3, text)

async def on_partners_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_partners_answer_and_proceed(dialog_manager, 4, text)

async def on_partners_q5_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_partners_answer_and_proceed(dialog_manager, 5, text)

async def on_partners_q6_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_partners_answer_and_proceed(dialog_manager, 6, text)


# Обработчики таймаута
async def on_partners_q1_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_partners_answer_and_proceed(dialog_manager, 1, "")

async def on_partners_q2_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_partners_answer_and_proceed(dialog_manager, 2, "")

async def on_partners_q3_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_partners_answer_and_proceed(dialog_manager, 3, "")

async def on_partners_q4_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_partners_answer_and_proceed(dialog_manager, 4, "")

async def on_partners_q5_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_partners_answer_and_proceed(dialog_manager, 5, "")

async def on_partners_q6_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_partners_answer_and_proceed(dialog_manager, 6, "")


# Функции запуска таймеров
async def start_partners_timer_q1(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "partners_q1", 120, on_partners_q1_timeout)

async def start_partners_timer_q2(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "partners_q2", 90, on_partners_q2_timeout)

async def start_partners_timer_q3(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "partners_q3", 60, on_partners_q3_timeout)

async def start_partners_timer_q4(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "partners_q4", 90, on_partners_q4_timeout)

async def start_partners_timer_q5(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "partners_q5", 90, on_partners_q5_timeout)

async def start_partners_timer_q6(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "partners_q6", 90, on_partners_q6_timeout)


async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    await dialog_manager.start(TestingSG.department_selection, mode=StartMode.RESET_STACK)


partners_test_dialog = Dialog(
    Window(
        Format("🤝 <b>Партнеры - Вопрос 1/6</b>\n\n{question_text}\n\n(Время на ответ: 120 секунд)"),
        *create_timer_display("partners_q1"),
        TextInput(id="partners_q1_input", on_success=on_partners_q1_input),
        state=PartnersTestSG.q1,
        getter=[get_partners_q1_data, get_timer_progress_data("partners_q1")],
        on_process_result=start_partners_timer_q1,
    ),
    Window(
        Format("🤝 <b>Партнеры - Вопрос 2/6</b>\n\n{question_text}\n\n(Время на ответ: 90 секунд)"),
        *create_timer_display("partners_q2"),
        TextInput(id="partners_q2_input", on_success=on_partners_q2_input),
        state=PartnersTestSG.q2,
        getter=[get_partners_q2_data, get_timer_progress_data("partners_q2")],
        on_process_result=start_partners_timer_q2,
    ),
    Window(
        Format("🤝 <b>Партнеры - Вопрос 3/6</b>\n\n{question_text}\n\n(Время на ответ: 60 секунд)"),
        *create_timer_display("partners_q3"),
        TextInput(id="partners_q3_input", on_success=on_partners_q3_input),
        state=PartnersTestSG.q3,
        getter=[get_partners_q3_data, get_timer_progress_data("partners_q3")],
        on_process_result=start_partners_timer_q3,
    ),
    Window(
        Format("🤝 <b>Партнеры - Вопрос 4/6</b>\n\n{question_text}\n\n(Время на ответ: 90 секунд)"),
        *create_timer_display("partners_q4"),
        TextInput(id="partners_q4_input", on_success=on_partners_q4_input),
        state=PartnersTestSG.q4,
        getter=[get_partners_q4_data, get_timer_progress_data("partners_q4")],
        on_process_result=start_partners_timer_q4,
    ),
    Window(
        Format("🤝 <b>Партнеры - Вопрос 5/6</b>\n\n{question_text}\n\n(Время на ответ: 90 секунд)"),
        *create_timer_display("partners_q5"),
        TextInput(id="partners_q5_input", on_success=on_partners_q5_input),
        state=PartnersTestSG.q5,
        getter=[get_partners_q5_data, get_timer_progress_data("partners_q5")],
        on_process_result=start_partners_timer_q5,
    ),
    Window(
        Format("🤝 <b>Партнеры - Вопрос 6/6</b>\n\n{question_text}\n\n(Время на ответ: 90 секунд)"),
        *create_timer_display("partners_q6"),
        TextInput(id="partners_q6_input", on_success=on_partners_q6_input),
        state=PartnersTestSG.q6,
        getter=[lambda **kwargs: {"question_text": PARTNERS_QUESTIONS[6]["text"]}, get_timer_progress_data("partners_q6")],
        on_process_result=start_partners_timer_q6,
    ),
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Партнеров!</b>\n\n"
              "Тест пройден! Ты можешь вернуться к выбору отделов и пройти тесты "
              "по другим интересующим тебя направлениям, или завершить тестирование."),
        Button(Const("🔙 Вернуться к выбору отделов"), id="back_to_departments", on_click=on_back_to_departments),
        state=PartnersTestSG.completed,
    ),
)