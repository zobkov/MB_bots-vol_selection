"""
Логистика - Unified Testing System
"""

import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import LogisticsTestSG

logger = logging.getLogger(__name__)

# Вопросы теста по логистике
LOGISTICS_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Опишите ваш опыт в организации мероприятий или управлении материальными ресурсами.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Как вы подходите к решению логистических задач? Приведите пример.",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Готовы ли вы работать с материально-техническим обеспечением мероприятий?",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Как вы будете действовать, если во время мероприятия возникнет нехватка оборудования?",
        time_limit=120
    ),
    TestQuestion(
        number=5,
        text="Опишите ваше понимание роли логистики в успешном проведении мероприятия.",
        time_limit=120
    ),
    TestQuestion(
        number=6,
        text="Готовы ли вы к физической работе (переноска оборудования, установка декораций)?",
        time_limit=120
    )
]

async def save_logistics_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования логистики"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "logistics")
        logger.info("Logistics test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving logistics checkpoint: {e}", exc_info=True)

# Конфигурация теста логистики
LOGISTICS_CONFIG = TestConfig(
    test_type="logistics",
    display_name="Логистика",
    icon="📦",
    questions=LOGISTICS_QUESTIONS,
    states_group=LogisticsTestSG,
    checkpoint_callback=save_logistics_checkpoint
)

# Генерируем диалог
logistics_test_dialog = create_test_dialog(LOGISTICS_CONFIG)