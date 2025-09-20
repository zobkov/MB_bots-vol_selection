"""
Унифицированный диалог тестирования отдела PR
"""
import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import PRTestSG

logger = logging.getLogger(__name__)

# Вопросы для тестирования отдела PR
PR_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Как ты думаешь, в чем может возникнуть сложность при работе волонтером PR отдела? Кратко изложи ответ.",
        time_limit=60
    ),
    TestQuestion(
        number=2,
        text="Представь ситуацию: в первый день конференции на площадку приехали крупные СМИ, твой тим-лидер и менеджеры отдела заняты и не успели провести инструктаж для подобных случаев. Как бы ты поступил(а)?",
        time_limit=120
    ),
    TestQuestion(
        number=3,
        text="Представь, что СМИ захотели взять интервью у конкретного спикера и подошли к тебе за помощью. Как бы ты это организовал(а)?",
        time_limit=90
    ),
    TestQuestion(
        number=4,
        text="Что из перечисленного является основанием немедленно обратиться к тим-лидеру или организатору:\nа) журналисты просят показать им кафетерий\nб) кому-то из гостей на площадке стало плохо\nв) СМИ мешают проведению мероприятия\nг) требуется техническая помощь в аудитории\nд) все вышеперечисленное\n\nНапиши букву или буквы (строчные, без пробелов).",
        time_limit=30,
        correct_answer="д"
    )
]


async def save_pr_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования отдела PR"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "pr")
        logger.info("PR test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving pr checkpoint: {e}", exc_info=True)


# Конфигурация теста отдела PR
PR_CONFIG = TestConfig(
    test_type="pr",
    display_name="PR",
    icon="📺",
    questions=PR_QUESTIONS,
    states_group=PRTestSG,
    checkpoint_callback=save_pr_checkpoint
)

# Создание диалога
pr_test_dialog = create_test_dialog(PR_CONFIG)