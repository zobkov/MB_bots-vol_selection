"""
Унифицированный диалог тестирования отдела Программы
"""
import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import ProgramTestSG

logger = logging.getLogger(__name__)

# Вопросы для тестирования отдела Программы
PROGRAM_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Представьте, что в первый день число гостей превзошло все ожидания и в гардеробе скопилась большая очередь, создающая помехи для прохода. Как вы поступите? Возьмете ли вы на себя инициативу решить проблему?",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Что поможет распознать гостя на площадке (например, участник, спикер, представитель компании, журналист)?\nНапиши свой вариант ответа.",
        time_limit=30
    ),
    TestQuestion(
        number=3,
        text="Что вы сделаете, если именного бейджа для спикера, который пришел регистрироваться, не будет среди всех подготовленных бейджей?",
        time_limit=90
    ),
    TestQuestion(
        number=4,
        text="Представь ситуацию: во время мероприятия в гибридной аудитории резко оборвалось собрание в Microsoft Teams, через которое транслировалось онлайн-выступление спикера. Ваш тим-лидер не рядом, а решить проблему нужно за считанные минуты. Коротко опишите свои действия.",
        time_limit=90
    ),
    TestQuestion(
        number=5,
        text="Что вы будете делать, если к вам подойдет спикер, который опаздывает на мероприятие с его участием и не знает, куда идти?",
        time_limit=90
    ),
    TestQuestion(
        number=6,
        text="Вы можете описать себя как пунктуального и ответственного человека? Можете ли привести нестандартный пример, чтобы продемонстрировать это качество?",
        time_limit=90
    )
]


async def save_program_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования отдела Программы"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "program")
        logger.info("Program test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving program checkpoint: {e}", exc_info=True)


# Конфигурация теста отдела Программы
PROGRAM_CONFIG = TestConfig(
    test_type="program",
    display_name="Программа",
    icon="📋",
    questions=PROGRAM_QUESTIONS,
    states_group=ProgramTestSG,
    checkpoint_callback=save_program_checkpoint
)

# Создание диалога
program_test_dialog = create_test_dialog(PROGRAM_CONFIG)