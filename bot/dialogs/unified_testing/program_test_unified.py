"""
Программный департамент - Unified Testing System
"""

import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import ProgramTestSG

logger = logging.getLogger(__name__)

# Вопросы теста программного департамента
PROGRAM_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Опишите ваш опыт в разработке программ мероприятий или проектов.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Как вы видите свою роль в создании образовательных и развлекательных программ?",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Какие форматы мероприятий вам нравятся больше всего и почему?",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Как вы будете действовать, если во время мероприятия программа идет не по плану?",
        time_limit=120
    ),
    TestQuestion(
        number=5,
        text="Готовы ли вы к работе с различными возрастными группами участников?",
        time_limit=120
    ),
    TestQuestion(
        number=6,
        text="Какие навыки ведущего или организатора у вас есть?",
        time_limit=120
    )
]

async def save_program_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования программного департамента"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "program")
        logger.info("Program test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving program checkpoint: {e}", exc_info=True)

# Конфигурация теста программного департамента
PROGRAM_CONFIG = TestConfig(
    test_type="program",
    display_name="Программный департамент",
    icon="🎭",
    questions=PROGRAM_QUESTIONS,
    states_group=ProgramTestSG,
    checkpoint_callback=save_program_checkpoint
)

# Генерируем диалог
program_test_dialog = create_test_dialog(PROGRAM_CONFIG)