"""
Диалог тестирования отдела Логистики (новая унифицированная версия)
"""
import logging
from bot.states import LogisticsTestSG
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session

logger = logging.getLogger(__name__)


# Конфигурация вопросов логистики
LOGISTICS_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Представь ситуацию: прямо сейчас в параллели проходят два мероприятия, и ты встречаешь в главном холле заблудившегося гостя с бейджем участника. Коротко опиши свои действия.",
        time_limit=60  # Обновлено время согласно существующей логике
    ),
    TestQuestion(
        number=2,
        text="Что из перечисленного можно делать во время кофе-брейка:\nа) прибирать пустые столики\nб) болтать с гостями\nв) поднимать упавший на пол мусор\nг) следить, чтобы еду брали только гости с бейджиками\nд) пробовать еду\n\nНапиши букву или буквы (строчные, без пробелов и других символов).",
        time_limit=90,
        correct_answer="авг"
    ),
    TestQuestion(
        number=3,
        text="Представь ситуацию: во время конференции около одного из туалетов (например, при входе в Центральный холл) образовалась очередь из участников, спикеров и гостей. Коротко опиши свои действия.",
        time_limit=120
    ),
    TestQuestion(
        number=4,
        text="Что из перечисленного является основанием немедленно обратиться к тим-лидеру или организатору:\nа) в аудитории не запускается компьютер или презентация\nб) в спикерской закончились вода/еда, и подходят новые гости\nв) вам срочно нужно уйти с площадки\nг) после мероприятия в аудитории закончились листы флипчарта/вода/пишущие маркеры\nд) при регистрации не удается найти имя участника/спикера в базе\nе) все вышеперечисленное\n\nНапиши букву или буквы (строчные, без пробелов и других символов).",
        time_limit=60,
        correct_answer="е"
    ),
    TestQuestion(
        number=5,
        text="Представь ситуацию: во второй день важный спикер из Газпромбанка приехал за 2,5 часа до своего выступления, твой тим-лидер просит тебя бросить текущие задачи и провести с гостем всё оставшееся время до начала мероприятия. Опиши, чем бы ты занял спикера, какого маршрута бы придерживался и о чём бы вёл беседу?",
        time_limit=90
    ),
    TestQuestion(
        number=6,
        text="Представь ситуацию: гость обращается к тебе за медицинской помощью. Важно: в здании будет дежурить врач. Коротко опиши свои действия.",
        time_limit=60
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
    icon="🔧",
    questions=LOGISTICS_QUESTIONS,
    states_group=LogisticsTestSG,
    checkpoint_callback=save_logistics_checkpoint
)


# Создание диалога с использованием универсальной системы
logistics_test_dialog = create_test_dialog(LOGISTICS_CONFIG)