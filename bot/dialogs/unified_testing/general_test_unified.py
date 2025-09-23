"""
Общие вопросы - Unified Testing System
"""

import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import GeneralQuestionsSG

logger = logging.getLogger(__name__)

# Вопросы общего теста
GENERAL_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Что мотивирует вас стать волонтером Молодежного балла?",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Есть ли у вас опыт работы в команде? Расскажите о нем.",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Как вы планируете совмещать волонтерство с учебой/работой?",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Что для вас означает быть частью команды Молодежного балла?",
        time_limit=120
    ),
    TestQuestion(
        number=5,
        text="Какие навыки вы хотели бы развить в рамках волонтерской деятельности?",
        time_limit=120
    ),
    TestQuestion(
        number=6,
        text="Готовы ли вы к активной работе в выходные дни и вечернее время?",
        time_limit=120
    )
]

async def save_general_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения общего тестирования"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "general")
        logger.info("General test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving general checkpoint: {e}", exc_info=True)

# Конфигурация общего теста
GENERAL_CONFIG = TestConfig(
    test_type="general",
    display_name="Общие вопросы",
    icon="📝",
    questions=GENERAL_QUESTIONS,
    states_group=GeneralQuestionsSG,
    checkpoint_callback=save_general_checkpoint
)

# Генерируем диалог
general_test_dialog = create_test_dialog(GENERAL_CONFIG)