"""
Унифицированный диалог общих вопросов тестирования (новая версия)
"""
import logging
import os
from bot.states import GeneralQuestionsSG
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_general_questions_completion_checkpoint

logger = logging.getLogger(__name__)


def get_image_path(filename: str) -> str:
    """Получение полного пути к изображению"""
    base_path = "/Users/artyomzobkov/vol_selection_MB_bot"
    return os.path.join(base_path, "bot", "assets", "images", filename)


# Вопросы для общего тестирования
GENERAL_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Что конференция может дать тебе? И что ты можешь дать конференции взамен? Подробно раскрой ответ.",
        time_limit=180
    ),
    TestQuestion(
        number=2,
        text="Какая в этом году тема конференции?",
        time_limit=30,
        correct_answer="искусство жить в переменах"
    ),
    TestQuestion(
        number=3,
        text="Какой по счёту в этом году будет конференция? Укажи число.",
        time_limit=15,
        correct_answer="13"
    ),
    TestQuestion(
        number=4,
        text="Когда будет проходить конференция? Укажи даты в формате «xx-xx месяц».",
        time_limit=15,
        correct_answer="23-25 октября"
    ),
    TestQuestion(
        number=5,
        text="Расположение аудиторий на 1-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 1206, 1222, 1212, 1301, 1216, 1215.",
        time_limit=90,
        correct_answer="абвгде",
        media_path=get_image_path("first_floor.jpeg"),
        media_caption="📍 Схема 1-го этажа для навигации"
    ),
    TestQuestion(
        number=6,
        text="Расположение аудиторий на 2-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 2222, 2229.",
        time_limit=30,
        correct_answer="аб",
        media_path=get_image_path("second_floor.jpeg"),
        media_caption="📍 Схема 2-го этажа для навигации"
    )
]


async def save_general_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения общих вопросов"""
    try:
        await save_general_questions_completion_checkpoint(dialog_manager)
        logger.info("General questions checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving general questions checkpoint: {e}", exc_info=True)


# Конфигурация общих вопросов (без отправки медиа в начале)
GENERAL_CONFIG = TestConfig(
    test_type="general",
    display_name="Общие вопросы",
    icon="📝",
    questions=GENERAL_QUESTIONS,
    states_group=GeneralQuestionsSG,
    checkpoint_callback=save_general_checkpoint
)

# Создание диалога с использованием универсальной системы
general_testing_dialog = create_test_dialog(GENERAL_CONFIG)