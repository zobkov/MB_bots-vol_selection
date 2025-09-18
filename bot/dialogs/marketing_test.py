"""
Диалог тестирования отдела Маркетинг
"""
from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Start, Cancel
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput

from bot.states import MarketingTestSG, TestingSG
from bot.dialogs.timer_utils import timer_manager, get_timer_progress_data, create_timer_display, calculate_time_taken
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database
import logging

logger = logging.getLogger(__name__)


# Данные вопросов маркетинга
MARKETING_QUESTIONS = {
    1: {
        "text": "Представь ситуацию: ты работаешь фотографом на конференции, и после мероприятия к тебе подходит важный спикер с просьбой не публиковать кадры с его лицом в СМИ. Как бы ты поступил(а) в такой ситуации? Кратко опиши свои действия.",
        "time_limit": 120
    },
    2: {
        "text": "Вам немедленно нужно убежать с площадки по непредвиденным обстоятельствам, но через пару минут начнётся мероприятие, на котором вы – единственный копирайтер. Все менеджеры отдела Маркетинга заняты. Ваши действия?",
        "time_limit": 90
    },
    3: {
        "text": "Расскажи, есть ли у тебя навыки работы в графических редакторах? Если да, то в каких?",
        "time_limit": 60
    },
    4: {
        "text": "Если ты хочешь помогать нам в роли копирайтера, то это задание для тебя (пропусти его, поставив прочерк, если ты хочешь быть фотографом – задание для фотографов следует сразу после).\nПредставь, что тебе нужно написать пост-релиз к одному из роликов TED (ты можешь выбрать любой интересный тебе ролик на русском или английском, мы тебя не ограничиваем), обязательно прикрепи ссылку на ролик. В пост-релизе должны быть цитаты спикера, при этом текст должен быть подходящим по объему для соц.сетей (не лонгрид статья).",
        "time_limit": 0  # Время не ограничено
    },
    5: {
        "text": "Если ты хочешь помогать нам в роли фотографа, напиши, пожалуйста, ссылку на диск с примерами твоих фото.",
        "time_limit": 0  # Время не ограничено
    }
}


async def save_marketing_answer_and_proceed(dialog_manager: DialogManager, question_num: int, answer: str):
    """Сохранить ответ и перейти к следующему вопросу"""
    try:
        # Для вопросов 4 и 5 таймера нет
        if question_num <= 3:
            timer_key = f"marketing_q{question_num}"
            await timer_manager.stop_timer(timer_key)
            time_taken = calculate_time_taken(dialog_manager, timer_key)
            is_timeout = dialog_manager.dialog_data.get(f"{timer_key}_timeout", False)
        else:
            time_taken = 0
            is_timeout = False
        
        db: Database = dialog_manager.middleware_data.get("db")
        if db:
            user_id = dialog_manager.event.from_user.id
            async with db.session() as session:
                dept_repo = DepartmentTestRepository(session)
                user_repo = UserRepository(session)
                
                user = await user_repo.get_user_by_telegram_id(user_id)
                if user:
                    test_result = await dept_repo.get_or_create_test_result(user.id, "marketing")
                    
                    question_data = MARKETING_QUESTIONS[question_num]
                    await dept_repo.save_answer(
                        test_result.id,
                        question_num,
                        question_data["text"],
                        answer,
                        question_data["time_limit"],
                        time_taken,
                        is_timeout
                    )
        
        logger.info(f"Saved marketing answer for question {question_num}, time: {time_taken}s")
        
        if question_num < 5:
            await dialog_manager.next()
        else:
            if db:
                user_id = dialog_manager.event.from_user.id
                async with db.session() as session:
                    dept_repo = DepartmentTestRepository(session)
                    user_repo = UserRepository(session)
                    user = await user_repo.get_user_by_telegram_id(user_id)
                    if user:
                        await dept_repo.complete_test(user.id, "marketing")
            
            await dialog_manager.switch_to(MarketingTestSG.completed)
        
    except Exception as e:
        logger.error(f"Error saving marketing answer for question {question_num}: {e}")


# Обработчики ввода
async def on_marketing_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_marketing_answer_and_proceed(dialog_manager, 1, text)

async def on_marketing_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_marketing_answer_and_proceed(dialog_manager, 2, text)

async def on_marketing_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_marketing_answer_and_proceed(dialog_manager, 3, text)

async def on_marketing_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_marketing_answer_and_proceed(dialog_manager, 4, text)

async def on_marketing_q5_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_marketing_answer_and_proceed(dialog_manager, 5, text)


# Обработчики таймаута (только для первых 3 вопросов)
async def on_marketing_q1_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_marketing_answer_and_proceed(dialog_manager, 1, "")

async def on_marketing_q2_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_marketing_answer_and_proceed(dialog_manager, 2, "")

async def on_marketing_q3_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_marketing_answer_and_proceed(dialog_manager, 3, "")


# Функции запуска таймеров (только для первых 3 вопросов)
async def start_marketing_timer_q1(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "marketing_q1", 120, on_marketing_q1_timeout)

async def start_marketing_timer_q2(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "marketing_q2", 90, on_marketing_q2_timeout)

async def start_marketing_timer_q3(dialog_manager: DialogManager, **kwargs):
    await timer_manager.start_timer(dialog_manager, "marketing_q3", 60, on_marketing_q3_timeout)


async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    await dialog_manager.start(TestingSG.department_selection, mode=StartMode.RESET_STACK)


marketing_test_dialog = Dialog(
    # Вопрос 1 (120 секунд)
    Window(
        Format("📸 <b>Маркетинг - Вопрос 1/5</b>\n\n{question_text}\n\n(Время на ответ: 120 секунд)"),
        *create_timer_display("marketing_q1"),
        TextInput(id="marketing_q1_input", on_success=on_marketing_q1_input),
        state=MarketingTestSG.q1,
        getter=[lambda **kwargs: {"question_text": MARKETING_QUESTIONS[1]["text"]}, get_timer_progress_data("marketing_q1")],
        on_process_result=start_marketing_timer_q1,
    ),
    
    # Вопрос 2 (90 секунд)
    Window(
        Format("📸 <b>Маркетинг - Вопрос 2/5</b>\n\n{question_text}\n\n(Время на ответ: 90 секунд)"),
        *create_timer_display("marketing_q2"),
        TextInput(id="marketing_q2_input", on_success=on_marketing_q2_input),
        state=MarketingTestSG.q2,
        getter=[lambda **kwargs: {"question_text": MARKETING_QUESTIONS[2]["text"]}, get_timer_progress_data("marketing_q2")],
        on_process_result=start_marketing_timer_q2,
    ),
    
    # Вопрос 3 (60 секунд)
    Window(
        Format("📸 <b>Маркетинг - Вопрос 3/5</b>\n\n{question_text}\n\n(Время на ответ: 60 секунд)"),
        *create_timer_display("marketing_q3"),
        TextInput(id="marketing_q3_input", on_success=on_marketing_q3_input),
        state=MarketingTestSG.q3,
        getter=[lambda **kwargs: {"question_text": MARKETING_QUESTIONS[3]["text"]}, get_timer_progress_data("marketing_q3")],
        on_process_result=start_marketing_timer_q3,
    ),
    
    # Вопрос 4 (без таймера - для копирайтеров)
    Window(
        Format("📸 <b>Маркетинг - Вопрос 4/5</b>\n\n{question_text}\n\n(Время не ограничено)"),
        TextInput(id="marketing_q4_input", on_success=on_marketing_q4_input),
        state=MarketingTestSG.q4,
        getter=lambda **kwargs: {"question_text": MARKETING_QUESTIONS[4]["text"]},
    ),
    
    # Вопрос 5 (без таймера - для фотографов)
    Window(
        Format("📸 <b>Маркетинг - Вопрос 5/5</b>\n\n{question_text}\n\n(Время не ограничено)"),
        TextInput(id="marketing_q5_input", on_success=on_marketing_q5_input),
        state=MarketingTestSG.q5,
        getter=lambda **kwargs: {"question_text": MARKETING_QUESTIONS[5]["text"]},
    ),
    
    # Завершение теста
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Маркетинга!</b>\n\n"
              "Тест пройден! Ты можешь вернуться к выбору отделов и пройти тесты "
              "по другим интересующим тебя направлениям, или завершить тестирование."),
        Button(Const("🔙 Вернуться к выбору отделов"), id="back_to_departments", on_click=on_back_to_departments),
        state=MarketingTestSG.completed,
    ),
)