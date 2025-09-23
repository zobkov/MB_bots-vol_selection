"""
Партнеры - Unified Testing System
"""

import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import PartnersTestSG

logger = logging.getLogger(__name__)

# Вопросы теста департамента партнеров
PARTNERS_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Опишите ваш опыт взаимодействия с партнерами, спонсорами или внешними организациями.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Как вы видите процесс поиска и привлечения партнеров для мероприятий?",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Готовы ли вы к переговорам и презентации проектов потенциальным партнерам?",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Как вы будете поддерживать долгосрочные отношения с партнерами?",
        time_limit=120
    ),
    TestQuestion(
        number=5,
        text="Какие навыки коммуникации и нетворкинга у вас есть?",
        time_limit=120
    ),
    TestQuestion(
        number=6,
        text="Готовы ли вы к работе с документооборотом и договорами?",
        time_limit=120
    )
]

async def save_partners_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования департамента партнеров"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "partners")
        logger.info("Partners test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving partners checkpoint: {e}", exc_info=True)

# Конфигурация теста департамента партнеров
PARTNERS_CONFIG = TestConfig(
    test_type="partners",
    display_name="Партнеры",
    icon="🤝",
    questions=PARTNERS_QUESTIONS,
    states_group=PartnersTestSG,
    checkpoint_callback=save_partners_checkpoint
)

# Генерируем диалог
partners_test_dialog = create_test_dialog(PARTNERS_CONFIG)