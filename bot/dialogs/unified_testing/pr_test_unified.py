"""
PR департамент - Unified Testing System
"""

import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import PRTestSG

logger = logging.getLogger(__name__)

# Вопросы теста PR департамента
PR_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Опишите ваш опыт в области PR, рекламы или работы с медиа.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Как вы видите роль PR в продвижении мероприятий Молодежного балла?",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Готовы ли вы к созданию контента для социальных сетей и других медиаплатформ?",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Как вы будете действовать в кризисной ситуации, требующей быстрого PR-реагирования?",
        time_limit=120
    ),
    TestQuestion(
        number=5,
        text="Какие навыки работы с текстом, фото- и видеоконтентом у вас есть?",
        time_limit=120
    ),
    TestQuestion(
        number=6,
        text="Готовы ли вы к взаимодействию с журналистами и блогерами?",
        time_limit=120
    )
]

async def save_pr_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования PR департамента"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "pr")
        logger.info("PR test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving PR checkpoint: {e}", exc_info=True)

# Конфигурация теста PR департамента
PR_CONFIG = TestConfig(
    test_type="pr",
    display_name="PR департамент",
    icon="📢",
    questions=PR_QUESTIONS,
    states_group=PRTestSG,
    checkpoint_callback=save_pr_checkpoint
)

# Генерируем диалог
pr_test_dialog = create_test_dialog(PR_CONFIG)