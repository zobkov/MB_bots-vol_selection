"""
Обновленный диалог общих вопросов с новой архитектурой таймеров
"""

from bot.dialogs.unified_testing import TestQuestion, TestConfig
from bot.dialogs.unified_testing.dialog_generator_v2 import create_test_dialog
from bot.states import GeneralQuestionsSG


# Конфигурация общих вопросов
GENERAL_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Что конференция может дать тебе? И что ты можешь дать конференции взамен? Подробно раскрой ответ.",
        time_limit=180  # 3 минуты
    ),
    TestQuestion(
        number=2,
        text="Опиши свой опыт участия в волонтерских проектах или мероприятиях. Если такого опыта нет, расскажи о готовности и мотивации стать волонтером.",
        time_limit=180
    ),
    TestQuestion(
        number=3,
        text="Как ты планируешь совмещать волонтерскую деятельность с основными обязанностями (учеба, работа)?",
        time_limit=120  # 2 минуты
    ),
    TestQuestion(
        number=4,
        text="Опиши ситуацию, когда тебе пришлось работать в команде. Какую роль ты выполнял и как способствовал достижению общей цели?",
        time_limit=180
    ),
    TestQuestion(
        number=5,
        text="Как ты относишься к критике и обратной связи? Приведи пример, когда критика помогла тебе улучшить результат.",
        time_limit=150
    ),
    TestQuestion(
        number=6,
        text="Что для тебя означает быть частью команды волонтеров МБ? Какие ценности важны для тебя в работе?",
        time_limit=180
    )
]

# Конфигурация теста
GENERAL_CONFIG = TestConfig(
    test_type="general",
    display_name="Общие вопросы",
    icon="📝",
    questions=GENERAL_QUESTIONS,
    states_group=GeneralQuestionsSG
)

# Создание диалога с новой архитектурой
general_testing_dialog_v2 = create_test_dialog(GENERAL_CONFIG)