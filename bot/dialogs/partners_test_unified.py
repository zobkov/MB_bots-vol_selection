"""
Унифицированный диалог тестирования отдела Партнеры
"""
import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import PartnersTestSG

logger = logging.getLogger(__name__)

# Вопросы для тестирования отдела Партнеры
PARTNERS_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Вы встретили делегацию компании у КПП и ведёте ее в Михайловскую дачу. О чем будете говорить с представителями компании? Начнёте ли диалог сами или подождёте первого шага с их стороны?\nПодробно опишите свои действия.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Представитель компании просит латте. В спикерской закончились сливки (вы не знаете, есть ли сливки где-то ещё на площадке Конференции), есть только чёрный кофе. Ваши действия?",
        time_limit=90
    ),
    TestQuestion(
        number=3,
        text="Укажи, какие из следующих компаний являются постоянными партнёрами конференции? (ответ запиши строчными буквами без пробелов и других символов)\nа) ВТБ\nб) Сибур\nв) VK\nг) Telegram\nд) Северсталь\n\nНапиши букву или буквы.",
        time_limit=60,
        correct_answer="авд"
    ),
    TestQuestion(
        number=4,
        text="Представитель компании спрашивает вас об организационных моментах, про которые вы ничего не знаете. Незаметно написать коллегам не получилось – они заняты и не отвечают. Ваши действия?",
        time_limit=90
    ),
    TestQuestion(
        number=5,
        text="Вам срочно нужно убежать с площадки по семейным обстоятельствам, но через 10 минут вы должны встретить делегацию компании и проводить ее до спикерской. Все менеджеры отдела по работе с партнерами заняты. Ваши действия?",
        time_limit=90
    ),
    TestQuestion(
        number=6,
        text="Через 10 минут представитель компании должен быть на мероприятии в 1301. Вы не можете найти его (отвлеклись на пару минут, а он куда-то делся). Ваши действия?",
        time_limit=90
    )
]


async def save_partners_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования отдела Партнеры"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "partners")
        logger.info("Partners test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving partners checkpoint: {e}", exc_info=True)


# Конфигурация теста отдела Партнеры
PARTNERS_CONFIG = TestConfig(
    test_type="partners",
    display_name="Партнеры",
    icon="🤝",
    questions=PARTNERS_QUESTIONS,
    states_group=PartnersTestSG,
    checkpoint_callback=save_partners_checkpoint
)

# Создание диалога
partners_test_dialog = create_test_dialog(PARTNERS_CONFIG)