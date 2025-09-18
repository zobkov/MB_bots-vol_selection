"""
Диалог общих вопросов тестирования с таймерами
"""
from aiogram import types
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Start, Cancel
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput

from bot.states import TestingSG, LogisticsTestSG, ProgramTestSG, PartnersTestSG, PRTestSG, MarketingTestSG, MenuSG
from bot.dialogs.timer_utils import (
    start_timer_background,
    get_timer_progress_data,
    stop_timer,
    create_timer_display,
    stop_active_timer,
    cancel_dialog_with_timers
)
from bot.dialogs.checkpoint_utils import save_general_questions_completion_checkpoint

# Функция для сохранения всех ответов общего тестирования
from database.repositories import UserRepository, Stage2Repository
from database.db import Database
from config.config import Config
import logging

logger = logging.getLogger(__name__)


# Async геттеры для вопросов
async def get_question_data(question_num: int, **kwargs):
    """Получить данные для вопроса"""
    return {"question_text": GENERAL_QUESTIONS[question_num]["text"]}

# Функция для сохранения всех ответов общего тестирования

# Async геттеры для вопросов с автозапуском таймера
async def get_q1_data_with_timer(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager:
        # Проверяем, не запущен ли уже таймер
        if not dialog_manager.dialog_data.get("general_q1_timer_started"):
            logger.debug("🔧 DEBUG: Запуск таймера для вопроса 1 из геттера")
            dialog_manager.dialog_data["general_q1_timer_started"] = True
            await start_timer_background(dialog_manager, "general_q1", 180, on_q1_timeout_bg)
    return {"question_text": GENERAL_QUESTIONS[1]["text"]}

async def get_q2_data_with_timer(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager:
        if not dialog_manager.dialog_data.get("general_q2_timer_started"):
            logger.debug("🔧 DEBUG: Запуск таймера для вопроса 2 из геттера")
            dialog_manager.dialog_data["general_q2_timer_started"] = True
            await start_timer_background(dialog_manager, "general_q2", 30, on_q2_timeout_bg)
    return {"question_text": GENERAL_QUESTIONS[2]["text"]}

async def get_q3_data_with_timer(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager:
        if not dialog_manager.dialog_data.get("general_q3_timer_started"):
            logger.debug("🔧 DEBUG: Запуск таймера для вопроса 3 из геттера")
            dialog_manager.dialog_data["general_q3_timer_started"] = True
            await start_timer_background(dialog_manager, "general_q3", 15, on_q3_timeout_bg)
    return {"question_text": GENERAL_QUESTIONS[3]["text"]}

async def get_q4_data_with_timer(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager:
        if not dialog_manager.dialog_data.get("general_q4_timer_started"):
            logger.debug("🔧 DEBUG: Запуск таймера для вопроса 4 из геттера")
            dialog_manager.dialog_data["general_q4_timer_started"] = True
            await start_timer_background(dialog_manager, "general_q4", 15, on_q4_timeout_bg)
    return {"question_text": GENERAL_QUESTIONS[4]["text"]}

async def get_q5_data_with_timer(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager:
        if not dialog_manager.dialog_data.get("general_q5_timer_started"):
            logger.debug("🔧 DEBUG: Запуск таймера для вопроса 5 из геттера")
            dialog_manager.dialog_data["general_q5_timer_started"] = True
            await start_timer_background(dialog_manager, "general_q5", 90, on_q5_timeout_bg)
    return {"question_text": GENERAL_QUESTIONS[5]["text"]}

async def get_q6_data_with_timer(**kwargs):
    dialog_manager = kwargs.get('dialog_manager')
    if dialog_manager:
        if not dialog_manager.dialog_data.get("general_q6_timer_started"):
            logger.debug("🔧 DEBUG: Запуск таймера для вопроса 6 из геттера")
            dialog_manager.dialog_data["general_q6_timer_started"] = True
            await start_timer_background(dialog_manager, "general_q6", 30, on_q6_timeout_bg)
    return {"question_text": GENERAL_QUESTIONS[6]["text"]}

async def get_q1_data(**kwargs):
    return {"question_text": GENERAL_QUESTIONS[1]["text"]}

async def get_q2_data(**kwargs):
    return {"question_text": GENERAL_QUESTIONS[2]["text"]}

async def get_q3_data(**kwargs):
    return {"question_text": GENERAL_QUESTIONS[3]["text"]}

async def get_q4_data(**kwargs):
    return {"question_text": GENERAL_QUESTIONS[4]["text"]}

async def get_q5_data(**kwargs):
    return {"question_text": GENERAL_QUESTIONS[5]["text"]}

async def get_q6_data(**kwargs):
    return {"question_text": GENERAL_QUESTIONS[6]["text"]}


# Данные вопросов
GENERAL_QUESTIONS = {
    1: {
        "text": "Что конференция может дать тебе? И что ты можешь дать конференции взамен? Подробно раскрой ответ.",
        "time_limit": 180
    },
    2: {
        "text": "Какая в этом году тема конференции?",
        "time_limit": 30,
        "correct_answer": "искусство жить в переменах"
    },
    3: {
        "text": "Какой по счёту в этом году будет конференция? Укажи число.",
        "time_limit": 15,
        "correct_answer": "13"
    },
    4: {
        "text": "Когда будет проходить конференция? Укажи даты в формате «xx-xx месяц».",
        "time_limit": 15,
        "correct_answer": "23-25 октября"
    },
    5: {
        "text": "Расположение аудиторий на 1-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 1206, 1222, 1212, 1301, 1216, 1215.",
        "time_limit": 90,
        "correct_answer": "абвгде",
        "has_image": "map_gsom_first_floor"
    },
    6: {
        "text": "Расположение аудиторий на 2-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 2222, 2229.",
        "time_limit": 30,
        "correct_answer": "аб",
        "has_image": "map_gsom_second_floor"
    }
}


async def save_answer_and_proceed_from_input(dialog_manager: DialogManager, question_num: int, answer_text: str):
    """Сохранение ответа из текстового ввода и переход к следующему вопросу"""
    try:
        logger.info(f"Saving input answer for question {question_num}: {answer_text}")
        
        # Останавливаем текущий таймер
        timer_key = f"general_q{question_num}"
        await stop_active_timer(timer_key)
        dialog_manager.dialog_data[f"{timer_key}_stopped"] = True
        
        # Получаем зависимости из middleware_data
        db: Database = dialog_manager.middleware_data.get("db")
        if not db:
            logger.error("Database not found in middleware_data")
            return
        
        user_id = dialog_manager.dialog_data.get("user_id")
        
        # Сохраняем ответ в базу данных
        session = await db.get_session()
        try:
            # Используем Stage2Repository для сохранения общих ответов
            stage2_repo = Stage2Repository(session)
            await stage2_repo.save_general_answer(user_id, question_num, answer_text, time_taken=0)
            logger.info(f"Successfully saved general answer {question_num}: {answer_text}")
        finally:
            await session.close()
        
        # Переходим к следующему вопросу
        if question_num < 6:
            next_state = getattr(TestingSG, f"general_q{question_num + 1}")
            await dialog_manager.switch_to(next_state)
        else:
            # Последний вопрос - сохраняем чекпоинт завершения общих вопросов
            await save_general_questions_completion_checkpoint(dialog_manager)
            # Переходим к завершению
            await dialog_manager.switch_to(TestingSG.department_selection)
            
    except Exception as e:
        logger.error(f"Error saving input answer for question {question_num}: {e}")


async def save_answer_and_proceed(
    event,  # Can be CallbackQuery or Message
    widget,
    dialog_manager: DialogManager,
    data: dict,
    db: Database,
    config: Config,
    **kwargs
):
    """Сохранение ответа и переход к следующему вопросу"""
    try:
        logger.info(f"Saving answer for question {data['question']}: {data}")
        
        user_id = dialog_manager.dialog_data.get("user_id")
        question_num = data["question"]
        answer_value = data["answer"]
        
        # Останавливаем текущий таймер
        timer_key = f"general_q{question_num}"
        await stop_active_timer(timer_key)
        dialog_manager.dialog_data[f"{timer_key}_stopped"] = True
        
        # Сохраняем ответ в базу данных
        session = await db.get_session()
        try:
            # Используем Stage2Repository для сохранения общих ответов
            stage2_repo = Stage2Repository(session)
            await stage2_repo.save_general_answer(user_id, question_num, answer_value, time_taken=0)
            logger.info(f"Successfully saved general answer {question_num}: {answer_value}")
        finally:
            await session.close()
        
        # Переходим к следующему вопросу
        if question_num < 6:
            next_state = getattr(TestingSG, f"general_q{question_num + 1}")
            await dialog_manager.switch_to(next_state)
        else:
            # Последний вопрос - сохраняем чекпоинт завершения общих вопросов
            await save_general_questions_completion_checkpoint(dialog_manager)
            # Переходим к завершению
            await dialog_manager.switch_to(TestingSG.department_selection)
            
    except Exception as e:
        logger.error(f"Error saving answer for question {question_num}: {e}")
        # Handle both CallbackQuery and Message
        if hasattr(event, 'answer'):
            await event.answer("❌ Ошибка при сохранении ответа")


# Обработчики ввода для каждого вопроса
async def on_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_answer_and_proceed_from_input(dialog_manager, 1, text)

async def on_q2_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_answer_and_proceed_from_input(dialog_manager, 2, text)

async def on_q3_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_answer_and_proceed_from_input(dialog_manager, 3, text)

async def on_q4_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_answer_and_proceed_from_input(dialog_manager, 4, text)

async def on_q5_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_answer_and_proceed_from_input(dialog_manager, 5, text)

async def on_q6_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    await save_answer_and_proceed_from_input(dialog_manager, 6, text)


# Обработчики таймаута для background manager
async def on_q1_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: Таймаут для вопроса 1, переход к следующему вопросу")
    from bot.states import TestingSG
    await bg_manager.switch_to(TestingSG.general_q2)

async def on_q2_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: Таймаут для вопроса 2, переход к следующему вопросу")
    from bot.states import TestingSG
    await bg_manager.switch_to(TestingSG.general_q3)

async def on_q3_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: Таймаут для вопроса 3, переход к следующему вопросу")
    from bot.states import TestingSG
    await bg_manager.switch_to(TestingSG.general_q4)

async def on_q4_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: Таймаут для вопроса 4, переход к следующему вопросу")
    from bot.states import TestingSG
    await bg_manager.switch_to(TestingSG.general_q5)

async def on_q5_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: Таймаут для вопроса 5, переход к следующему вопросу")
    from bot.states import TestingSG
    await bg_manager.switch_to(TestingSG.general_q6)

async def on_q6_timeout_bg(bg_manager, timer_key: str):
    logger.debug(f"🔧 DEBUG: Таймаут для вопроса 6, переход к выбору отдела")
    from bot.states import TestingSG
    await bg_manager.switch_to(TestingSG.department_selection)


# Функции запуска таймеров
async def start_timer_q1(dialog_manager: DialogManager, **kwargs):
    logger.debug("🔧 DEBUG: Запуск таймера для вопроса 1")
    await start_timer_background(dialog_manager, "general_q1", 180, on_q1_timeout_bg)

async def start_timer_q2(dialog_manager: DialogManager, **kwargs):
    logger.debug("🔧 DEBUG: Запуск таймера для вопроса 2")
    await start_timer_background(dialog_manager, "general_q2", 30, on_q2_timeout_bg)

async def start_timer_q3(dialog_manager: DialogManager, **kwargs):
    logger.debug("🔧 DEBUG: Запуск таймера для вопроса 3")
    await start_timer_background(dialog_manager, "general_q3", 15, on_q3_timeout_bg)

async def start_timer_q4(dialog_manager: DialogManager, **kwargs):
    logger.debug("🔧 DEBUG: Запуск таймера для вопроса 4")
    await start_timer_background(dialog_manager, "general_q4", 15, on_q4_timeout_bg)

async def start_timer_q5(dialog_manager: DialogManager, **kwargs):
    logger.debug("🔧 DEBUG: Запуск таймера для вопроса 5")
    await start_timer_background(dialog_manager, "general_q5", 90, on_q5_timeout_bg)

async def start_timer_q6(dialog_manager: DialogManager, **kwargs):
    logger.debug("🔧 DEBUG: Запуск таймера для вопроса 6")
    await start_timer_background(dialog_manager, "general_q6", 30, on_q6_timeout_bg)


# Обработчик перехода к выбору отделов
async def on_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Переход к выбору отделов"""
    try:
        # Отмечаем завершение общих вопросов в БД
        db: Database = dialog_manager.middleware_data.get("db")
        if db:
            user_id = callback.from_user.id
            session = await db.get_session()
            try:
                stage2_repo = Stage2Repository(session)
                user_repo = UserRepository(session)
                
                user = await user_repo.get_user_by_telegram_id(user_id)
                if user:
                    await stage2_repo.mark_general_questions_completed(user.id)
            finally:
                await session.close()
        
        await dialog_manager.switch_to(TestingSG.department_selection)
        
    except Exception as e:
        logger.error(f"Error transitioning to departments: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")


# Обработчик завершения тестирования
async def on_finish_testing(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Завершение тестирования и возврат в меню"""
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


# Геттер для статуса отделов
async def get_department_status(dialog_manager: DialogManager, **kwargs):
    """Получить статус прохождения тестов по отделам"""
    try:
        db: Database = dialog_manager.middleware_data.get("db")
        if not db:
            return {
                "logistics_available": True,
                "program_available": True,
                "partners_available": True,
                "pr_available": True,
                "marketing_available": True,
                "logistics_prefix": "",
                "program_prefix": "",
                "partners_prefix": "",
                "pr_prefix": "",
                "marketing_prefix": "",
                "completed_departments": ""
            }
        
        user_id = dialog_manager.event.from_user.id
        
        session = await db.get_session()
        try:
            from database.repositories import DepartmentTestRepository, UserRepository
            dept_repo = DepartmentTestRepository(session)
            user_repo = UserRepository(session)
            
            user = await user_repo.get_user_by_telegram_id(user_id)
            if not user:
                return {
                    "logistics_available": True,
                    "program_available": True,
                    "partners_available": True,
                    "pr_available": True,
                    "marketing_available": True,
                    "logistics_prefix": "",
                    "program_prefix": "",
                    "partners_prefix": "",
                    "pr_prefix": "",
                    "marketing_prefix": "",
                    "completed_departments": ""
                }
            
            # Проверяем статус каждого отдела
            departments = ["logistics", "program", "partners", "pr", "marketing"]
            department_names = {
                "logistics": "Логистика",
                "program": "Программа", 
                "partners": "Партнеры",
                "pr": "PR",
                "marketing": "Маркетинг"
            }
            
            completed = []
            result = {}
            
            for dept in departments:
                is_completed = await dept_repo.is_department_completed(user.id, dept)
                
                # Настройки доступности и префикса
                result[f"{dept}_available"] = not is_completed  # Недоступен если уже пройден
                result[f"{dept}_prefix"] = "🔒 " if is_completed else ""
                
                if is_completed:
                    completed.append(department_names[dept])
            
            # Формируем текст о пройденных отделах
            if completed:
                result["completed_departments"] = f"✅ <b>Пройденные тесты:</b> {', '.join(completed)}\n\n"
            else:
                result["completed_departments"] = ""
            
            return result
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error getting department status: {e}")
        return {
            "logistics_available": True,
            "program_available": True,
            "partners_available": True,
            "pr_available": True,
            "marketing_available": True,
            "logistics_prefix": "",
            "program_prefix": "",
            "partners_prefix": "",
            "pr_prefix": "",
            "marketing_prefix": "",
            "completed_departments": ""
        }


general_testing_dialog = Dialog(
    # Стартовое окно
    Window(
        Const("🚀 <b>Начинаем общие вопросы!</b>\n\n"
              "Сейчас тебе предстоит ответить на 6 общих вопросов. "
              "У каждого вопроса есть ограничение по времени.\n\n"
              "⚠️ <b>Важно:</b>\n"
              "• Отвечай одним сообщением\n"
              "• После отправки ответа сразу придет следующий вопрос\n"
              "• Ответ нельзя изменить\n"
              "• Если время истечет, вопрос будет пропущен\n\n"
              "Готов? Нажми кнопку ниже!"),
        Button(
            Const("▶️ Начать"),
            id="start_questions",
            on_click=lambda c, b, dm: dm.next()
        ),
        Button(
            Const("❌ Отмена"),
            id="cancel_testing",
            on_click=cancel_dialog_with_timers
        ),
        state=TestingSG.start,
    ),
    
    # Вопрос 1 (180 секунд)
    Window(
        Format("📝 <b>Вопрос 1/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 180 секунд)"),
        *create_timer_display("general_q1"),
        TextInput(
            id="q1_input",
            on_success=on_q1_input
        ),
        state=TestingSG.general_q1,
        getter=[
            get_q1_data_with_timer,
            get_timer_progress_data("general_q1")
        ],
    ),
    
    # Вопрос 2 (30 секунд)
    Window(
        Format("📝 <b>Вопрос 2/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 30 секунд)"),
        *create_timer_display("general_q2"),
        TextInput(
            id="q2_input",
            on_success=on_q2_input
        ),
        state=TestingSG.general_q2,
        getter=[
            get_q2_data_with_timer,
            get_timer_progress_data("general_q2")
        ],
    ),
    
    # Вопрос 3 (15 секунд)
    Window(
        Format("📝 <b>Вопрос 3/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 15 секунд)"),
        *create_timer_display("general_q3"),
        TextInput(
            id="q3_input",
            on_success=on_q3_input
        ),
        state=TestingSG.general_q3,
        getter=[
            get_q3_data_with_timer,
            get_timer_progress_data("general_q3")
        ],
    ),
    
    # Вопрос 4 (15 секунд)
    Window(
        Format("📝 <b>Вопрос 4/6</b>\n\n"
               "{question_text}\n\n"
               "(Время на ответ: 15 секунд)"),
        *create_timer_display("general_q4"),
        TextInput(
            id="q4_input",
            on_success=on_q4_input
        ),
        state=TestingSG.general_q4,
        getter=[
            get_q4_data_with_timer,
            get_timer_progress_data("general_q4")
        ],
    ),
    
    # Вопрос 5 (90 секунд) - с картинкой
    Window(
        Format("📝 <b>Вопрос 5/6</b>\n\n"
               "{question_text}\n\n"
               "🖼️ <i>Изображение карты прикреплено выше</i>\n\n"
               "(Время на ответ: 90 секунд)"),
        *create_timer_display("general_q5"),
        TextInput(
            id="q5_input",
            on_success=on_q5_input
        ),
        state=TestingSG.general_q5,
        getter=[
            get_q5_data_with_timer,
            get_timer_progress_data("general_q5")
        ],
    ),
    
    # Вопрос 6 (30 секунд) - с картинкой
    Window(
        Format("📝 <b>Вопрос 6/6</b>\n\n"
               "{question_text}\n\n"
               "🖼️ <i>Изображение карты прикреплено выше</i>\n\n"
               "(Время на ответ: 30 секунд)"),
        *create_timer_display("general_q6"),
        TextInput(
            id="q6_input",
            on_success=on_q6_input
        ),
        state=TestingSG.general_q6,
        getter=[
            get_q6_data_with_timer,
            get_timer_progress_data("general_q6")
        ],
    ),
    
    # Промежуточное окно
    Window(
        Const("🎉 <b>Ура! Теперь ты можешь перейти к опросу по отделам.</b>\n\n"
              "Общие вопросы пройдены! Следующий этап - выбор отделов для тестирования."),
        Button(
            Const("➡️ Дальше"),
            id="to_departments",
            on_click=on_to_departments
        ),
        state=TestingSG.intermediate,
    ),
    
    # Окно выбора отделов
    Window(
        Format("🏢 <b>Выбери отдел для прохождения опроса</b>\n\n"
               "Для какого отдела ты бы хотел(а) пройти опрос? "
               "Если тебе интересны несколько отделов, то после завершения одного опроса "
               "ты сможешь перейти к другому. Не забудь, что здесь тоже действуют временные ограничения!\n\n"
               "<b>Напомним о 5 волонтёрских блоках:</b>\n\n"
               "🔧 <b>Логистика:</b> экскурсии для гостей, регистрация участников, гардероб, "
               "кейтеринг, навигация в холле, вынос подарков, монтаж и демонтаж;\n\n"
               "📋 <b>Программа:</b> техническая и организационная помощь в аудиториях, "
               "регистрация и сопровождение спикеров, помощь в спикерской;\n\n"
               "🤝 <b>Партнеры:</b> встреча партнеров и их сопровождение на площадке;\n\n"
               "📰 <b>PR:</b> встреча и координация журналистов, интервью с участниками, "
               "написание статей о Конференции;\n\n"
               "📸 <b>Маркетинг:</b> волонтеры-фотографы, волонтеры с навыками копирайтинга, "
               "которые будут создавать мини-конспект каждого мероприятия.\n\n"
               "{completed_departments}"),
        Start(
            Format("{logistics_prefix}🔧 Логистика"),
            id="logistics_test",
            state=LogisticsTestSG.q1,
            when="logistics_available"
        ),
        Start(
            Format("{program_prefix}📋 Программа"),
            id="program_test",
            state=ProgramTestSG.q1,
            when="program_available"
        ),
        Start(
            Format("{partners_prefix}🤝 Партнеры"),
            id="partners_test",
            state=PartnersTestSG.q1,
            when="partners_available"
        ),
        Start(
            Format("{pr_prefix}📰 PR"),
            id="pr_test",
            state=PRTestSG.q1,
            when="pr_available"
        ),
        Start(
            Format("{marketing_prefix}📸 Маркетинг"),
            id="marketing_test",
            state=MarketingTestSG.q1,
            when="marketing_available"
        ),
        Button(
            Const("✅ Закончить тестирование"),
            id="finish_testing",
            on_click=on_finish_testing
        ),
        state=TestingSG.department_selection,
        getter=get_department_status,
    ),
)