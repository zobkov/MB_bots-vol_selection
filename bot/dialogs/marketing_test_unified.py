"""
Унифицированный диалог тестирования отдела Маркетинг
"""
import logging
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import MarketingTestSG

logger = logging.getLogger(__name__)

# Вопросы для тестирования отдела Маркетинг
MARKETING_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Представь ситуацию: ты работаешь фотографом на конференции, и после мероприятия к тебе подходит важный спикер с просьбой не публиковать кадры с его лицом в СМИ. Как бы ты поступил(а) в такой ситуации? Кратко опиши свои действия.",
        time_limit=120
    ),
    TestQuestion(
        number=2,
        text="Вам немедленно нужно убежать с площадки по непредвиденным обстоятельствам, но через пару минут начнётся мероприятие, на котором вы – единственный копирайтер. Все менеджеры отдела Маркетинга заняты. Ваши действия?",
        time_limit=90
    ),
    TestQuestion(
        number=3,
        text="Расскажи, есть ли у тебя навыки работы в графических редакторах? Если да, то в каких?",
        time_limit=60
    ),
    TestQuestion(
        number=4,
        text="Если ты хочешь помогать нам в роли копирайтера, то это задание для тебя (пропусти его, поставив прочерк, если ты хочешь быть фотографом – задание для фотографов следует сразу после).\nПредставь, что тебе нужно написать пост-релиз к одному из роликов TED (ты можешь выбрать любой интересный тебе ролик на русском или английском, мы тебя не ограничиваем), обязательно прикрепи ссылку на ролик. В пост-релизе должны быть цитаты спикера, при этом текст должен быть подходящим по объему для соц.сетей (не лонгрид статья).",
        time_limit=600  # 10 минут вместо неограниченного времени
    ),
    TestQuestion(
        number=5,
        text="Если ты хочешь помогать нам в роли фотографа, напиши, пожалуйста, ссылку на диск с примерами твоих фото.",
        time_limit=300  # 5 минут вместо неограниченного времени
    )
]


async def save_marketing_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования отдела Маркетинг"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "marketing")
        logger.info("Marketing test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving marketing checkpoint: {e}", exc_info=True)


# Конфигурация теста отдела Маркетинг
MARKETING_CONFIG = TestConfig(
    test_type="marketing",
    display_name="Маркетинг",
    icon="📸",
    questions=MARKETING_QUESTIONS,
    states_group=MarketingTestSG,
    checkpoint_callback=save_marketing_checkpoint
)

# Создание диалога
marketing_test_dialog = create_test_dialog(MARKETING_CONFIG)