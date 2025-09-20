"""
Унифицированный диалог общих вопросов тестирования
"""
import logging
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from bot.dialogs.unified_testing import TestQuestion, TestConfig, UniversalTestDialogGenerator
from bot.dialogs.unified_testing.test_engine import test_engine
from bot.dialogs.checkpoint_utils import save_general_questions_completion_checkpoint
from bot.states import GeneralQuestionsSG
from database.repositories import UserRepository, Stage2Repository
from database.db import Database

logger = logging.getLogger(__name__)

# Вопросы для общего тестирования
GENERAL_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Что конференция может дать тебе? И что ты можешь дать конференции взамен? Подробно раскрой ответ.",
        time_limit=180
    ),
    TestQuestion(
        number=2,
        text="Какая в этом году тема конференции?",
        time_limit=30,
        correct_answer="искусство жить в переменах"
    ),
    TestQuestion(
        number=3,
        text="Какой по счёту в этом году будет конференция? Укажи число.",
        time_limit=15,
        correct_answer="13"
    ),
    TestQuestion(
        number=4,
        text="Когда будет проходить конференция? Укажи даты в формате «xx-xx месяц».",
        time_limit=15,
        correct_answer="23-25 октября"
    ),
    TestQuestion(
        number=5,
        text="Расположение аудиторий на 1-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 1206, 1222, 1212, 1301, 1216, 1215.",
        time_limit=90,
        correct_answer="абвгде"
        # Note: has_image functionality will need to be added to unified system if needed
    ),
    TestQuestion(
        number=6,
        text="Расположение аудиторий на 2-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 2222, 2229.",
        time_limit=30,
        correct_answer="аб"
        # Note: has_image functionality will need to be added to unified system if needed
    )
]


async def save_general_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения общих вопросов"""
    try:
        await save_general_questions_completion_checkpoint(dialog_manager)
        logger.info("General questions checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving general questions checkpoint: {e}", exc_info=True)


# Специальная функция сохранения ответов для общих вопросов
async def save_general_answer(dialog_manager: DialogManager, config: TestConfig, question_number: int, answer_text: str):
    """Сохранение ответа на общий вопрос в stage2_answers"""
    try:
        user_id = dialog_manager.event.from_user.id
        timer_key = test_engine.get_user_timer_key(user_id, config.test_type, question_number)
        
        # Останавливаем таймер
        await test_engine.timer_manager.stop_timer(dialog_manager, timer_key)
        
        # Вычисляем время ответа
        time_taken = test_engine.timer_manager.calculate_time_taken(dialog_manager, timer_key)
        
        # Сохраняем в базу данных через Stage2Repository
        db: Database = dialog_manager.middleware_data.get("db")
        if not db:
            logger.error("Database not found in middleware_data")
            return False
        
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            stage2_repo = Stage2Repository(session)
            
            # Получаем пользователя
            user = await user_repo.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"User not found: {user_id}")
                return False
            
            # Сохраняем ответ через Stage2Repository
            await stage2_repo.save_general_answer(user.id, question_number, answer_text, time_taken)
            await session.commit()
            
            logger.info(f"General answer saved: user_id={user.id}, question={question_number}, time_taken={time_taken}")
            return True
            
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error saving general answer: {e}", exc_info=True)
        return False


# Специальный обработчик ввода для общих вопросов
def create_general_input_handler(config: TestConfig, question: TestQuestion):
    """Создание обработчика ввода для общих вопросов"""
    async def on_input(message: Message, widget, dialog_manager: DialogManager, text: str):
        logger.debug(f"General input received for q{question.number}: '{text}'")
        
        success = await save_general_answer(dialog_manager, config, question.number, text)
        
        if success:
            # Переходим к следующему вопросу или завершаем
            if question.number < len(config.questions):
                await dialog_manager.next()
            else:
                # Тест завершен, переходим к состоянию completed
                await dialog_manager.switch_to(config.states_group.completed)
        else:
            logger.error(f"Failed to save general answer for q{question.number}")
            
    return on_input


# Создание диалога с кастомными обработчиками для общих вопросов
def create_general_test_dialog(config: TestConfig):
    """Создание диалога для общих вопросов с специальными обработчиками"""
    # Создаем стандартный диалог но заменяем обработчики ввода
    windows = []
    
    # Создаем окна для каждого вопроса
    for question in config.questions:
        question_getter = UniversalTestDialogGenerator.create_question_getter(config, question)
        input_handler = create_general_input_handler(config, question)  # Используем специальный обработчик
        
        # Создаем геттер таймера с динамическим ключом
        def create_timer_getter(q_num):
            async def timer_getter(dialog_manager: DialogManager, **kwargs):
                user_id = dialog_manager.event.from_user.id
                timer_key = f"user_{user_id}_{config.test_type}_q{q_num}"
                return await test_engine.timer_manager.get_timer_progress_data(timer_key)(dialog_manager, **kwargs)
            return timer_getter
        
        timer_getter = create_timer_getter(question.number)
        
        # Создаем окно вопроса
        from aiogram_dialog import Window
        from aiogram_dialog.widgets.text import Format
        from aiogram_dialog.widgets.input import TextInput
        
        window = Window(
            Format(
                "{test_icon} <b>{test_display_name} - Вопрос {question_number}/{total_questions}</b>\n\n"
                "{question_text}\n\n"
                "(Время на ответ: {time_limit} секунд)"
            ),
            *test_engine.timer_manager.create_timer_display(f"timer_{config.test_type}_q{question.number}"),
            TextInput(
                id=f"{config.test_type}_q{question.number}_input",
                on_success=input_handler
            ),
            state=getattr(config.states_group, f'q{question.number}'),
            getter=[question_getter, timer_getter]
        )
        
        windows.append(window)
    
    # Создаем окно завершения теста
    from aiogram_dialog.widgets.kbd import Button
    from aiogram_dialog.widgets.text import Const
    
    async def general_back_to_departments_handler(callback, button, dialog_manager):
        """Специальный обработчик для перехода к выбору отделов после общих вопросов"""
        # Возвращаемся к выбору отделов через TestingSG
        from bot.states import TestingSG
        await dialog_manager.start(TestingSG.department_selection, mode=StartMode.RESET_STACK)
    
    async def completion_getter(dialog_manager: DialogManager = None, **kwargs):
        if dialog_manager:
            # Проверяем, нужно ли выполнить checkpoint
            test_completed_key = f"test_{config.test_type}_completed"
            if not dialog_manager.dialog_data.get(test_completed_key, False):
                # Выполняем checkpoint только один раз
                if config.checkpoint_callback:
                    await config.checkpoint_callback(dialog_manager)
                dialog_manager.dialog_data[test_completed_key] = True
                
        return {
            "test_display_name": config.display_name,
            "test_icon": config.icon
        }
    
    completion_window = Window(
        Format(
            "{test_icon} <b>Общие вопросы завершены!</b>\n\n"
            "✅ Все ответы сохранены\n"
            "📊 Результаты будут учтены при оценке\n\n"
            "Выберите действие:"
        ),
        Button(
            Const("🏢 Вернуться к выбору отделов"),
            id="back_to_departments",
            on_click=general_back_to_departments_handler
        ),
        state=config.states_group.completed,
        getter=completion_getter
    )
    
    windows.append(completion_window)
    
    from aiogram_dialog import Dialog
    dialog = Dialog(*windows)
    logger.info(f"General questions dialog created with {len(windows)} windows")
    
    return dialog


# Конфигурация общих вопросов
GENERAL_CONFIG = TestConfig(
    test_type="general",
    display_name="Общие вопросы",
    icon="📝",
    questions=GENERAL_QUESTIONS,
    states_group=GeneralQuestionsSG,
    checkpoint_callback=save_general_checkpoint
)

# Создание диалога
general_testing_dialog = create_general_test_dialog(GENERAL_CONFIG)