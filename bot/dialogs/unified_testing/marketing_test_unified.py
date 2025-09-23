"""
Маркетинг - Unified Testing System
"""

import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import MarketingTestSG

logger = logging.getLogger(__name__)

# Вопросы теста департамента маркетинга
MARKETING_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Опишите ваш опыт в области маркетинга, рекламы или продвижения проектов.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Как вы видите маркетинговую стратегию для привлечения участников к мероприятиям?",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Готовы ли вы к работе с аналитикой и метриками эффективности?",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Как вы будете определять целевую аудиторию для разных мероприятий?",
        time_limit=120
    ),
    TestQuestion(
        number=5,
        text="Какие маркетинговые инструменты и платформы вы знаете?",
        time_limit=120
    ),
    TestQuestion(
        number=6,
        text="Готовы ли вы к созданию маркетинговых материалов и рекламных кампаний?",
        time_limit=120
    )
]

async def save_marketing_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования департамента маркетинга"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "marketing")
        logger.info("Marketing test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving marketing checkpoint: {e}", exc_info=True)

# Конфигурация теста департамента маркетинга
MARKETING_CONFIG = TestConfig(
    test_type="marketing",
    display_name="Маркетинг",
    icon="📈",
    questions=MARKETING_QUESTIONS,
    states_group=MarketingTestSG,
    checkpoint_callback=save_marketing_checkpoint
)

# Генерируем диалог
marketing_test_dialog = create_test_dialog(MARKETING_CONFIG)