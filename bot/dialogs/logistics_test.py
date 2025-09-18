"""
Диалог тестирования отдела Логистики
"""
from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Start, Cancel
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput

from bot.states import LogisticsTestSG, TestingSG
from bot.dialogs.timer_utils import (
    start_timer_background, get_timer_progress_data, create_timer_display,
    calculate_time_taken, stop_timer, cancel_dialog_with_timers
)
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint
from database.repositories import UserRepository, DepartmentTestRepository
from database.db import Database
import logging

logger = logging.getLogger(__name__)


# Async геттеры для вопросов логистики с запуском таймеров
async def get_logistics_q1_data(**kwargs):
    logger.debug(f"🔧 DEBUG: get_logistics_q1_data вызван с kwargs: {list(kwargs.keys())}")
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        current_state = dialog_manager.current_context().state
        if current_state == LogisticsTestSG.q1:
            # Проверяем, не запущен ли уже таймер
            if not dialog_manager.dialog_data.get("logistics_q1_timer_started"):
                logger.debug("🔧 DEBUG: Запуск таймера для логистики вопроса 1 из геттера")
                dialog_manager.dialog_data["logistics_q1_timer_started"] = True
                await start_timer_background(dialog_manager, "logistics_q1", 60, on_logistics_q1_timeout)
        else:
            logger.debug(f"🔧 DEBUG: Текущее состояние {current_state}, ожидаем {LogisticsTestSG.q1}")
    else:
        logger.debug("🔧 DEBUG: dialog_manager не найден или не имеет current_context")
    return {"question_text": LOGISTICS_QUESTIONS[1]["text"]}

async def get_logistics_q2_data(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        current_state = dialog_manager.current_context().state
        if current_state == LogisticsTestSG.q2:
            if not dialog_manager.dialog_data.get("logistics_q2_timer_started"):
                logger.debug("🔧 DEBUG: Запуск таймера для логистики вопроса 2 из геттера")
                dialog_manager.dialog_data["logistics_q2_timer_started"] = True
                await start_timer_background(dialog_manager, "logistics_q2", 90, on_logistics_q2_timeout)
    return {"question_text": LOGISTICS_QUESTIONS[2]["text"]}

async def get_logistics_q3_data(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        current_state = dialog_manager.current_context().state
        if current_state == LogisticsTestSG.q3:
            if not dialog_manager.dialog_data.get("logistics_q3_timer_started"):
                logger.debug("🔧 DEBUG: Запуск таймера для логистики вопроса 3 из геттера")
                dialog_manager.dialog_data["logistics_q3_timer_started"] = True
                await start_timer_background(dialog_manager, "logistics_q3", 120, on_logistics_q3_timeout)
    return {"question_text": LOGISTICS_QUESTIONS[3]["text"]}

async def get_logistics_q4_data(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        current_state = dialog_manager.current_context().state
        if current_state == LogisticsTestSG.q4:
            if not dialog_manager.dialog_data.get("logistics_q4_timer_started"):
                logger.debug("🔧 DEBUG: Запуск таймера для логистики вопроса 4 из геттера")
                dialog_manager.dialog_data["logistics_q4_timer_started"] = True
                await start_timer_background(dialog_manager, "logistics_q4", 60, on_logistics_q4_timeout)
    return {"question_text": LOGISTICS_QUESTIONS[4]["text"]}

async def get_logistics_q5_data(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        current_state = dialog_manager.current_context().state
        if current_state == LogisticsTestSG.q5:
            if not dialog_manager.dialog_data.get("logistics_q5_timer_started"):
                logger.debug("🔧 DEBUG: Запуск таймера для логистики вопроса 5 из геттера")
                dialog_manager.dialog_data["logistics_q5_timer_started"] = True
                await start_timer_background(dialog_manager, "logistics_q5", 90, on_logistics_q5_timeout)
    return {"question_text": LOGISTICS_QUESTIONS[5]["text"]}

async def get_logistics_q6_data(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        current_state = dialog_manager.current_context().state
        if current_state == LogisticsTestSG.q6:
            if not dialog_manager.dialog_data.get("logistics_q6_timer_started"):
                logger.debug("🔧 DEBUG: Запуск таймера для логистики вопроса 6 из геттера")
                dialog_manager.dialog_data["logistics_q6_timer_started"] = True
                await start_timer_background(dialog_manager, "logistics_q6", 60, on_logistics_q6_timeout)
    return {"question_text": LOGISTICS_QUESTIONS[6]["text"]}


# Данные вопросов логистики
LOGISTICS_QUESTIONS = {
    1: {
        "text": "Представь ситуацию: прямо сейчас в параллели проходят два мероприятия, и ты встречаешь в главном холле заблудившегося гостя с бейджем участника. Коротко опиши свои действия.",
        "time_limit": 90
    },
    2: {
        "text": "Что из перечисленного можно делать во время кофе-брейка:\nа) прибирать пустые столики\nб) болтать с гостями\nв) поднимать упавший на пол мусор\nг) следить, чтобы еду брали только гости с бейджиками\nд) пробовать еду\n\nНапиши букву или буквы (строчные, без пробелов и других символов).",
        "time_limit": 45,
        "correct_answer": "авг"
    },
    3: {
        "text": "Представь ситуацию: во время конференции около одного из туалетов (например, при входе в Центральный холл) образовалась очередь из участников, спикеров и гостей. Коротко опиши свои действия.",
        "time_limit": 90
    },
    4: {
        "text": "Что из перечисленного является основанием немедленно обратиться к тим-лидеру или организатору:\nа) в аудитории не запускается компьютер или презентация\nб) в спикерской закончились вода/еда, и подходят новые гости\nв) вам срочно нужно уйти с площадки\nг) после мероприятия в аудитории закончились листы флипчарта/вода/пишущие маркеры\nд) при регистрации не удается найти имя участника/спикера в базе\nе) все вышеперечисленное\n\nНапиши букву или буквы (строчные, без пробелов и других символов).",
        "time_limit": 90,
        "correct_answer": "е"
    },
    5: {
        "text": "Представь ситуацию: во второй день важный спикер из Газпромбанка приехал за 2,5 часа до своего выступления, твой тим-лидер просит тебя бросить текущие задачи и провести с гостем всё оставшееся время до начала мероприятия. Опиши, чем бы ты занял спикера, какого маршрута бы придерживался и о чём бы вёл беседу?",
        "time_limit": 120
    },
    6: {
        "text": "Представь ситуацию: гость обращается к тебе за медицинской помощью. Важно: в здании будет дежурить врач. Коротко опиши свои действия.",
        "time_limit": 60
    }
}


async def save_logistics_answer_and_proceed(dialog_manager: DialogManager, question_num: int, answer: str):
    """Сохранить ответ и перейти к следующему вопросу"""
    logger.info(f"🔧 DEBUG: save_logistics_answer_and_proceed вызвана для вопроса {question_num} с ответом '{answer}'")
    try:
        # Останавливаем таймер
        timer_key = f"logistics_q{question_num}"
        await stop_timer(dialog_manager, timer_key)
        logger.info(f"🔧 DEBUG: Таймер {timer_key} остановлен")
        
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
                    test_result = await dept_repo.get_or_create_test_result(user.id, "logistics")
                    
                    # Определяем правильность ответа если есть эталон
                    question_data = LOGISTICS_QUESTIONS[question_num]
                    correct_answer = question_data.get("correct_answer")
                    is_correct = None
                    
                    if correct_answer and answer.strip():
                        is_correct = answer.strip().lower() == correct_answer.lower()
                    
                    # Сохраняем ответ
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
            finally:
                await session.close()
        
        logger.info(f"Saved logistics answer for question {question_num}, time: {time_taken}s")
        
        # Переходим к следующему вопросу или завершаем
        if question_num < 6:
            await dialog_manager.next()
        else:
            # Последний вопрос - сохраняем чекпоинт завершения отдела
            await save_department_completion_checkpoint(dialog_manager, "logistics")
            await dialog_manager.switch_to(LogisticsTestSG.completed)
        
    except Exception as e:
        logger.error(f"Error saving logistics answer for question {question_num}: {e}")
        await dialog_manager.event.answer("Произошла ошибка. Попробуйте еще раз.")


# Обработчики ввода для каждого вопроса
async def on_logistics_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.info(f"🔧 DEBUG: on_logistics_q1_input вызван с текстом: '{text}'")
    await save_logistics_answer_and_proceed(dialog_manager, 1, text)

async def on_logistics_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.info(f"🔧 DEBUG: on_logistics_q2_input вызван с текстом: '{text}'")
    await save_logistics_answer_and_proceed(dialog_manager, 2, text)

async def on_logistics_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_logistics_answer_and_proceed(dialog_manager, 3, text)

async def on_logistics_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_logistics_answer_and_proceed(dialog_manager, 4, text)

async def on_logistics_q5_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_logistics_answer_and_proceed(dialog_manager, 5, text)

async def on_logistics_q6_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_logistics_answer_and_proceed(dialog_manager, 6, text)


# Обработчики таймаута
async def on_logistics_q1_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_logistics_answer_and_proceed(dialog_manager, 1, "")

async def on_logistics_q2_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_logistics_answer_and_proceed(dialog_manager, 2, "")

async def on_logistics_q3_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_logistics_answer_and_proceed(dialog_manager, 3, "")

async def on_logistics_q4_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_logistics_answer_and_proceed(dialog_manager, 4, "")

async def on_logistics_q5_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_logistics_answer_and_proceed(dialog_manager, 5, "")

async def on_logistics_q6_timeout(dialog_manager: DialogManager, timer_key: str):
    await save_logistics_answer_and_proceed(dialog_manager, 6, "")

# Обработчик возврата к выбору отделов
async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Возврат к выбору отделов"""
    await dialog_manager.start(TestingSG.department_selection, mode=StartMode.RESET_STACK)


logistics_test_dialog = Dialog(
    # Вопрос 1 (60 секунд)
    Window(
        Format("🔧 <b>Логистика - Вопрос 1/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 60 секунд)"),
        *create_timer_display("logistics_q1"),
        TextInput(
            id="logistics_q1_input",
            on_success=on_logistics_q1_input
        ),
        state=LogisticsTestSG.q1,
        getter=[
            get_logistics_q1_data,
            get_timer_progress_data("logistics_q1")
        ],
    ),
    
    # Вопрос 2 (90 секунд)
    Window(
        Format("🔧 <b>Логистика - Вопрос 2/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("logistics_q2"),
        TextInput(
            id="logistics_q2_input",
            on_success=on_logistics_q2_input
        ),
        state=LogisticsTestSG.q2,
        getter=[
            get_logistics_q2_data,
            get_timer_progress_data("logistics_q2")
        ],
    ),
    
    # Вопрос 3 (120 секунд)
    Window(
        Format("🔧 <b>Логистика - Вопрос 3/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 120 секунд)"),
        *create_timer_display("logistics_q3"),
        TextInput(
            id="logistics_q3_input",
            on_success=on_logistics_q3_input
        ),
        state=LogisticsTestSG.q3,
        getter=[
            get_logistics_q3_data,
            get_timer_progress_data("logistics_q3")
        ],
    ),
    
    # Вопрос 4 (60 секунд)
    Window(
        Format("🔧 <b>Логистика - Вопрос 4/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 60 секунд)"),
        *create_timer_display("logistics_q4"),
        TextInput(
            id="logistics_q4_input",
            on_success=on_logistics_q4_input
        ),
        state=LogisticsTestSG.q4,
        getter=[
            get_logistics_q4_data,
            get_timer_progress_data("logistics_q4")
        ],
    ),
    
    # Вопрос 5 (90 секунд)
    Window(
        Format("🔧 <b>Логистика - Вопрос 5/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("logistics_q5"),
        TextInput(
            id="logistics_q5_input",
            on_success=on_logistics_q5_input
        ),
        state=LogisticsTestSG.q5,
        getter=[
            get_logistics_q5_data,
            get_timer_progress_data("logistics_q5")
        ],
    ),
    
    # Вопрос 6 (60 секунд)
    Window(
        Format("🔧 <b>Логистика - Вопрос 6/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 60 секунд)"),
        *create_timer_display("logistics_q6"),
        TextInput(
            id="logistics_q6_input",
            on_success=on_logistics_q6_input
        ),
        state=LogisticsTestSG.q6,
        getter=[
            get_logistics_q6_data,
            get_timer_progress_data("logistics_q6")
        ],
    ),
    
    # Завершение теста
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Логистики!</b>\n\n"
              "Тест пройден! Ты можешь вернуться к выбору отделов и пройти тесты "
              "по другим интересующим тебя направлениям, или завершить тестирование."),
        Button(
            Const("🔙 Вернуться к выбору отделов"),
            id="back_to_departments",
            on_click=on_back_to_departments
        ),
        state=LogisticsTestSG.completed,
    ),
)