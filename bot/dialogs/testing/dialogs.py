import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram_dialog import (
    Dialog, Window, DialogManager, StartMode
)
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, Row, Back

from bot.states import (
    TestingSG, GeneralTestSG, DepartmentTestSelectionSG,
    LogisticsTestSG, ProgramTestSG, PartnersTestSG, PRTestSG, MarketingTestSG,
    MenuSG
)

logger = logging.getLogger(__name__)

# =======================
# Данные тестов
# =======================

# Общие вопросы
GENERAL_QUESTIONS = {
    1: {
        "text": "Что конференция может дать тебе? И что ты можешь дать конференции взамен? Подробно раскрой ответ.",
        "duration": 180
    },
    2: {
        "text": "Какая в этом году тема конференции?",
        "duration": 30,
        "correct_answer": "Искусство жить в переменах"
    },
    3: {
        "text": "Какой по счёту в этом году будет конференция? Укажи число.",
        "duration": 15,
        "correct_answer": "13"
    },
    4: {
        "text": "Когда будет проходить конференция? Укажи даты в формате «xx-xx месяц».",
        "duration": 15,
        "correct_answer": "23-25 октября"
    },
    5: {
        "text": "Расположение аудиторий на 1-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 1206, 1222, 1212, 1301, 1216, 1215.",
        "duration": 90,
        "correct_answer": "АБВГДЕ",
        "image": "first_floor"
    },
    6: {
        "text": "Расположение аудиторий на 2-ом этаже. Укажи последовательность букв, которыми обозначены следующие аудитории: 2222, 2229.",
        "duration": 30,
        "correct_answer": "АБ",
        "image": "second_floor"
    }
}

# Вопросы по отделам
LOGISTICS_QUESTIONS = {
    1: {
        "text": "Представь ситуацию: прямо сейчас в параллели проходят два мероприятия, и ты встречаешь в главном холле заблудившегося гостя с бейджем участника. Коротко опиши свои действия.",
        "duration": 90
    },
    2: {
        "text": """Что из перечисленного можно делать во время кофе-брейка:
а) прибирать пустые столики
б) болтать с гостями
в) поднимать упавший на пол мусор
г) следить, чтобы еду брали только гости с бейджиками
д) пробовать еду

Напиши букву или буквы (строчные, без пробелов и других символов).""",
        "duration": 45,
        "correct_answer": "авг"
    },
    3: {
        "text": "Представь ситуацию: во время конференции около одного из туалетов (например, при входе в Центральный холл) образовалась очередь из участников, спикеров и гостей. Коротко опиши свои действия.",
        "duration": 90
    },
    4: {
        "text": """Что из перечисленного является основанием немедленно обратиться к тим-лидеру или организатору:
а) в аудитории не запускается компьютер или презентация
б) в спикерской закончились вода/еда, и подходят новые гости
в) вам срочно нужно уйти с площадки
г) после мероприятия в аудитории закончились листы флипчарта/вода/пишущие маркеры
д) при регистрации не удается найти имя участника/спикера в базе
е) все вышеперечисленное

Напиши букву или буквы (строчные, без пробелов и других символов).""",
        "duration": 90,
        "correct_answer": "е"
    },
    5: {
        "text": "Представь ситуацию: во второй день важный спикер из Газпромбанка приехал за 2,5 часа до своего выступления, твой тим-лидер просит тебя бросить текущие задачи и провести с гостем всё оставшееся время до начала мероприятия. Опиши, чем бы ты занял спикера, какого маршрута бы придерживался и о чём бы вёл беседу?",
        "duration": 120
    },
    6: {
        "text": "Представь ситуацию: гость обращается к тебе за медицинской помощью. Важно: в здании будет дежурить врач. Коротко опиши свои действия.",
        "duration": 60
    }
}

PROGRAM_QUESTIONS = {
    1: {
        "text": "Представьте, что в первый день число гостей превзошло все ожидания и в гардеробе скопилась большая очередь, создающая помехи для прохода. Как вы поступите? Возьмете ли вы на себя инициативу решить проблему?",
        "duration": 120
    },
    2: {
        "text": "Что поможет распознать гостя на площадке (например, участник, спикер, представитель компании, журналист)? Напиши свой вариант ответа.",
        "duration": 30
    },
    3: {
        "text": "Что вы сделаете, если именного бейджа для спикера, который пришел регистрироваться, не будет среди всех подготовленных бейджей?",
        "duration": 90
    },
    4: {
        "text": "Представь ситуацию: во время мероприятия в гибридной аудитории резко оборвалось собрание в Microsoft Teams, через которое транслировалось онлайн-выступление спикера. Ваш тим-лидер не рядом, а решить проблему нужно за считанные минуты. Коротко опишите свои действия.",
        "duration": 90
    },
    5: {
        "text": "Что вы будете делать, если к вам подойдет спикер, который опаздывает на мероприятие с его участием и не знает, куда идти?",
        "duration": 90
    },
    6: {
        "text": "Вы можете описать себя как пунктуального и ответственного человека? Можете ли привести нестандартный пример, чтобы продемонстрировать это качество?",
        "duration": 90
    }
}

PARTNERS_QUESTIONS = {
    1: {
        "text": "Вы встретили делегацию компании у КПП и ведёте ее в Михайловскую дачу. О чем будете говорить с представителями компании? Начнёте ли диалог сами или подождёте первого шага с их стороны? Подробно опишите свои действия.",
        "duration": 120
    },
    2: {
        "text": "Представитель компании просит латте. В спикерской закончились сливки (вы не знаете, есть ли сливки где-то ещё на площадке Конференции), есть только чёрный кофе. Ваши действия?",
        "duration": 90
    },
    3: {
        "text": """Укажи, какие из следующих компаний являются постоянными партнёрами конференции? (ответ запиши строчными буквами без пробелов и других символов)
а) ВТБ
б) Сибур
в) VK
г) Telegram
д) Северсталь

Напиши букву или буквы.""",
        "duration": 60,
        "correct_answer": "авд"
    },
    4: {
        "text": "Представитель компании спрашивает вас об организационных моментах, про которые вы ничего не знаете. Незаметно написать коллегам не получилось – они заняты и не отвечают. Ваши действия?",
        "duration": 90
    },
    5: {
        "text": "Вам срочно нужно убежать с площадки по семейным обстоятельствам, но через 10 минут вы должны встретить делегацию компании и проводить ее до спикерской. Все менеджеры отдела по работе с партнерами заняты. Ваши действия?",
        "duration": 90
    },
    6: {
        "text": "Через 10 минут представитель компании должен быть на мероприятии в 1301. Вы не можете найти его (отвлеклись на пару минут, а он куда-то делся). Ваши действия?",
        "duration": 90
    }
}

PR_QUESTIONS = {
    1: {
        "text": "Как ты думаешь, в чем может возникнуть сложность при работе волонтером PR отдела? Кратко изложи ответ.",
        "duration": 60
    },
    2: {
        "text": "Представь ситуацию: в первый день конференции на площадку приехали крупные СМИ, твой тим-лидер и менеджеры отдела заняты и не успели провести инструктаж для подобных случаев. Как бы ты поступил(а)?",
        "duration": 120
    },
    3: {
        "text": "Представь, что СМИ захотели взять интервью у конкретного спикера и подошли к тебе за помощью. Как бы ты это организовал(а)?",
        "duration": 90
    },
    4: {
        "text": """Что из перечисленного является основанием немедленно обратиться к тим-лидеру или организатору:
а) журналисты просят показать им кафетерий
б) кому-то из гостей на площадке стало плохо 
в) СМИ мешают проведению мероприятия
г) требуется техническая помощь в аудитории
д) все вышеперечисленное

Напиши букву или буквы (строчные, без пробелов).""",
        "duration": 30,
        "correct_answer": "д"
    }
}

MARKETING_QUESTIONS = {
    1: {
        "text": "Представь ситуацию: ты работаешь фотографом на конференции, и после мероприятия к тебе подходит важный спикер с просьбой не публиковать кадры с его лицом в СМИ. Как бы ты поступил(а) в такой ситуации? Кратко опиши свои действия.",
        "duration": 120
    },
    2: {
        "text": "Вам немедленно нужно убежать с площадки по непредвиденным обстоятельствам, но через пару минут начнётся мероприятие, на котором вы – единственный копирайтер. Все менеджеры отдела Маркетинга заняты. Ваши действия?",
        "duration": 90
    },
    3: {
        "text": "Расскажи, есть ли у тебя навыки работы в графических редакторах? Если да, то в каких?",
        "duration": 60
    },
    4: {
        "text": "Если ты хочешь помогать нам в роли копирайтера, то это задание для тебя (пропусти его, поставив прочерк, если ты хочешь быть фотографом – задание для фотографов следует сразу после). Представь, что тебе нужно написать пост-релиз к одному из роликов TED (ты можешь выбрать любой интересный тебе ролик на русском или английском, мы тебя не ограничиваем), обязательно прикрепи ссылку на ролик. В пост-релизе должны быть цитаты спикера, при этом текст должен быть подходящим по объему для соц.сетей (не лонгрид статья).",
        "duration": None  # Время не ограничено
    },
    5: {
        "text": "Если ты хочешь помогать нам в роли фотографа, напиши, пожалуйста, ссылку на диск с примерами твоих фото.",
        "duration": None  # Время не ограничено
    }
}

# =======================
# Служебные функции APScheduler
# =======================

async def next_question_general(manager: DialogManager):
    """Переход к следующему общему вопросу"""
    current_q = manager.dialog_data.get("current_q", 1)
    if current_q < 6:
        next_q = current_q + 1
        manager.dialog_data["current_q"] = next_q
        await manager.dialog().switch_to(getattr(GeneralTestSG, f'q{next_q}'))
    else:
        await manager.dialog().switch_to(GeneralTestSG.completed)


async def next_question_department(manager: DialogManager, states_group, max_questions: int):
    """Переход к следующему вопросу отдела"""
    current_q = manager.dialog_data.get("current_q", 1)
    if current_q < max_questions:
        next_q = current_q + 1
        manager.dialog_data["current_q"] = next_q
        await manager.dialog().switch_to(getattr(states_group, f'q{next_q}'))
    else:
        await manager.dialog().switch_to(states_group.completed)


async def record_timeout(user_id: int, chat_id: int, qid: int, test_type: str):
    """Таймаут от APScheduler"""
    from aiogram_dialog.manager.manager import ManagerImpl
    import main

    context = main.dp.fsm.get_context(bot=main.bot, user_id=user_id, chat_id=chat_id)
    manager = ManagerImpl(main.dp, main.bot, context)

    # Записываем пустой ответ при таймауте
    if manager.dialog_data.get("answers") is None:
        manager.dialog_data["answers"] = {}
    
    manager.dialog_data["answers"][qid] = None

    # Переходим к следующему вопросу
    if test_type == "general":
        await next_question_general(manager)
    elif test_type == "logistics":
        await next_question_department(manager, LogisticsTestSG, 6)
    elif test_type == "program":
        await next_question_department(manager, ProgramTestSG, 6)
    elif test_type == "partners":
        await next_question_department(manager, PartnersTestSG, 6)
    elif test_type == "pr":
        await next_question_department(manager, PRTestSG, 4)
    elif test_type == "marketing":
        await next_question_department(manager, MarketingTestSG, 5)


async def tick_update(user_id: int, chat_id: int, qid: int, test_type: str):
    """Тикающее обновление UI"""
    from aiogram_dialog.manager.manager import ManagerImpl
    import main

    context = main.dp.fsm.get_context(bot=main.bot, user_id=user_id, chat_id=chat_id)
    manager = ManagerImpl(main.dp, main.bot, context)

    # если мы всё ещё в этом вопросе — обновляем экран
    if manager.dialog_data.get("current_q") == qid:
        await manager.update()


# =======================
# Обработчики ввода
# =======================

async def on_general_answer(message: Message, message_input: MessageInput, manager: DialogManager):
    """Обработка ответа на общий вопрос"""
    qid = manager.dialog_data.get("current_q", 1)
    
    # Инициализируем ответы если не существуют
    if manager.dialog_data.get("answers") is None:
        manager.dialog_data["answers"] = {}
    
    manager.dialog_data["answers"][qid] = message.text

    # Снимаем задачи APScheduler
    try:
        import main
        if main.scheduler:
            main.scheduler.remove_job(f"timeout:general:{message.from_user.id}:{qid}")
            main.scheduler.remove_job(f"tick:general:{message.from_user.id}:{qid}")
    except Exception as e:
        logger.debug(f"Failed to remove scheduler jobs: {e}")

    await next_question_general(manager)


async def on_department_answer(message: Message, message_input: MessageInput, manager: DialogManager, test_type: str, states_group, max_questions: int):
    """Обработка ответа на вопрос отдела"""
    qid = manager.dialog_data.get("current_q", 1)
    
    # Инициализируем ответы отдела если не существуют
    if manager.dialog_data.get(f"{test_type}_answers") is None:
        manager.dialog_data[f"{test_type}_answers"] = {}
    
    manager.dialog_data[f"{test_type}_answers"][qid] = message.text

    # Снимаем задачи APScheduler
    try:
        import main
        if main.scheduler:
            main.scheduler.remove_job(f"timeout:{test_type}:{message.from_user.id}:{qid}")
            main.scheduler.remove_job(f"tick:{test_type}:{message.from_user.id}:{qid}")
    except Exception as e:
        logger.debug(f"Failed to remove scheduler jobs: {e}")

    await next_question_department(manager, states_group, max_questions)


# =======================
# Обработчики кнопок
# =======================

async def on_start_testing(callback: CallbackQuery, button: Button, manager: DialogManager):
    """Начать общее тестирование"""
    # Инициализируем данные теста
    manager.dialog_data["current_q"] = 1
    manager.dialog_data["answers"] = {}
    
    await manager.start(GeneralTestSG.q1, mode=StartMode.NORMAL)


async def on_back_to_menu(callback: CallbackQuery, button: Button, manager: DialogManager):
    """Вернуться в главное меню"""
    await manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


async def on_department_test_start(callback: CallbackQuery, button: Button, manager: DialogManager, 
                                  test_type: str, states_group, department_name: str):
    """Начать тестирование отдела"""
    # Инициализируем данные теста отдела
    manager.dialog_data["current_q"] = 1
    manager.dialog_data[f"{test_type}_answers"] = {}
    manager.dialog_data["current_department"] = test_type
    
    await manager.start(states_group.q1, mode=StartMode.NORMAL)


async def on_department_completed(callback: CallbackQuery, button: Button, manager: DialogManager):
    """Отдел завершен, вернуться к выбору отделов"""
    # Отмечаем отдел как завершенный
    current_dept = manager.dialog_data.get("current_department")
    if current_dept:
        if manager.dialog_data.get("completed_departments") is None:
            manager.dialog_data["completed_departments"] = []
        
        if current_dept not in manager.dialog_data["completed_departments"]:
            manager.dialog_data["completed_departments"].append(current_dept)
    
    await manager.start(DepartmentTestSelectionSG.selection, mode=StartMode.NORMAL)


async def on_finish_testing(callback: CallbackQuery, button: Button, manager: DialogManager):
    """Завершить все тестирование"""
    # Здесь можно добавить сохранение в БД в будущем
    await manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


# =======================
# Геттеры
# =======================

async def testing_intro_getter(dialog_manager: DialogManager, **kwargs):
    """Геттер для стартового окна тестирования"""
    return {}


async def general_question_getter(dialog_manager: DialogManager, **kwargs):
    """Геттер для общих вопросов"""
    qid = dialog_manager.dialog_data.get("current_q", 1)
    question = GENERAL_QUESTIONS.get(qid, {})
    
    # Отправляем изображение если есть
    if "image" in question:
        bot = dialog_manager.middleware_data.get("bot")
        if bot:
            image_path = f"bot/assets/images/{question['image']}.jpeg"
            try:
                with open(image_path, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=dialog_manager.event.chat.id,
                        photo=photo
                    )
            except Exception as e:
                logger.error(f"Failed to send image {image_path}: {e}")
    
    # Устанавливаем таймер при старте вопроса
    await setup_question_timer(dialog_manager, qid, "general", question.get("duration"))
    
    end_time = dialog_manager.dialog_data.get("end_time", datetime.now().timestamp())
    remaining = int(end_time - datetime.now().timestamp())
    
    return {
        "question_num": qid,
        "total_questions": len(GENERAL_QUESTIONS),
        "question_text": question.get("text", ""),
        "remaining_time": max(0, remaining),
        "has_image": "image" in question,
        "image_name": question.get("image", "")
    }


async def department_question_getter(dialog_manager: DialogManager, test_type: str, questions_dict: Dict[int, Dict[str, Any]], **kwargs):
    """Геттер для вопросов отдела"""
    qid = dialog_manager.dialog_data.get("current_q", 1)
    question = questions_dict.get(qid, {})
    
    # Устанавливаем таймер при старте вопроса
    duration = question.get("duration")
    if duration is not None:
        await setup_question_timer(dialog_manager, qid, test_type, duration)
    
    end_time = dialog_manager.dialog_data.get("end_time", datetime.now().timestamp())
    remaining = int(end_time - datetime.now().timestamp()) if duration else None
    
    return {
        "question_num": qid,
        "total_questions": len(questions_dict),
        "question_text": question.get("text", ""),
        "remaining_time": max(0, remaining) if remaining is not None else None,
        "has_timer": duration is not None
    }


async def department_selection_getter(dialog_manager: DialogManager, **kwargs):
    """Геттер для выбора отделов"""
    completed = dialog_manager.dialog_data.get("completed_departments", [])
    
    return {
        "logistics_completed": "logistics" in completed,
        "program_completed": "program" in completed, 
        "partners_completed": "partners" in completed,
        "pr_completed": "pr" in completed,
        "marketing_completed": "marketing" in completed,
        "can_finish": len(completed) > 0  # Можно завершить если хотя бы один отдел пройден
    }


async def setup_question_timer(manager: DialogManager, qid: int, test_type: str, duration: int):
    """Настройка таймера для вопроса"""
    if duration is None:
        return
        
    # Импортируем scheduler внутри функции, чтобы избежать циклических импортов
    import main
    
    end_time = datetime.now() + timedelta(seconds=duration)
    manager.dialog_data["end_time"] = end_time.timestamp()

    uid = manager.event.from_user.id
    cid = manager.event.chat.id

    # Удаляем старые задачи если есть
    try:
        if main.scheduler:
            main.scheduler.remove_job(f"timeout:{test_type}:{uid}:{qid}")
            main.scheduler.remove_job(f"tick:{test_type}:{uid}:{qid}")
    except Exception:
        pass

    # Добавляем новые задачи только если scheduler существует
    if main.scheduler:
        # Таймаут
        main.scheduler.add_job(
            record_timeout,
            trigger="date",
            run_date=end_time,
            id=f"timeout:{test_type}:{uid}:{qid}",
            args=[uid, cid, qid, test_type]
        )

        # Тикающий апдейт каждые 2 сек
        main.scheduler.add_job(
            tick_update,
            trigger="interval",
            seconds=2,
            id=f"tick:{test_type}:{uid}:{qid}",
            args=[uid, cid, qid, test_type],
            end_date=end_time
        )


# =======================
# Диалоги
# =======================

# Стартовое окно тестирования
testing_dialog = Dialog(
    Window(
        Const(
            "🎯 <b>Тестирование волонтеров</b>\n\n"
            "Чудесно! Следующий этап – проверка твоих знаний. Пожалуйста, ответь на несколько вопросов касательно твоего участия в МБ, чтобы мы были уверены в тебе!\n\n"
            "Мы начнем с общих вопросов для всех отделов, а затем тебе нужно будет пройти опрос по интересующим тебя отделам.\n\n"
            "⚠️ <b>Важно:</b> у каждого вопроса есть ограниченное время на ответ, которое указано в скобках после вопроса. По истечении этого времени ответ не будет записан, тебе сразу придет следующий вопрос. Поэтому перед началом опроса убедитесь, что ты сможешь уделить ему 20-60 минут (зависит от отдела). На вопросы нужно отвечать одним сообщением, ответ нельзя редактировать. После ответа на вопрос сразу приходит следующий."
        ),
        Column(
            Button(
                Const("🚀 Начать тестирование"),
                id="start_testing",
                on_click=on_start_testing
            ),
            Button(
                Const("⬅️ Вернуться назад"),
                id="back_to_menu",
                on_click=on_back_to_menu
            )
        ),
        state=TestingSG.intro,
        getter=testing_intro_getter
    )
)

# Общее тестирование
general_test_dialog = Dialog(
    # Вопросы 1-4 (без изображений)
    Window(
        Format("📝 <b>Общие вопросы - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}\n\n"
               "⏰ Оставшееся время: {remaining_time} сек."),
        MessageInput(on_general_answer),
        state=GeneralTestSG.q1,
        getter=general_question_getter
    ),
    Window(
        Format("📝 <b>Общие вопросы - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}\n\n"
               "⏰ Оставшееся время: {remaining_time} сек."),
        MessageInput(on_general_answer),
        state=GeneralTestSG.q2,
        getter=general_question_getter
    ),
    Window(
        Format("📝 <b>Общие вопросы - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}\n\n"
               "⏰ Оставшееся время: {remaining_time} сек."),
        MessageInput(on_general_answer),
        state=GeneralTestSG.q3,
        getter=general_question_getter
    ),
    Window(
        Format("📝 <b>Общие вопросы - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}\n\n"
               "⏰ Оставшееся время: {remaining_time} сек."),
        MessageInput(on_general_answer),
        state=GeneralTestSG.q4,
        getter=general_question_getter
    ),
    # Вопрос 5 (с изображением первого этажа)
    Window(
        Format("📝 <b>Общие вопросы - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}\n\n"
               "⏰ Оставшееся время: {remaining_time} сек."),
        MessageInput(on_general_answer),
        state=GeneralTestSG.q5,
        getter=general_question_getter
    ),
    # Вопрос 6 (с изображением второго этажа)  
    Window(
        Format("📝 <b>Общие вопросы - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}\n\n"
               "⏰ Оставшееся время: {remaining_time} сек."),
        MessageInput(on_general_answer),
        state=GeneralTestSG.q6,
        getter=general_question_getter
    ),
    # Завершение общего тестирования
    Window(
        Const(
            "🎉 <b>Общие вопросы завершены!</b>\n\n"
            "Ура! Теперь ты можешь перейти к опросу по отделам."
        ),
        Button(
            Const("➡️ Дальше"),
            id="to_departments",
            on_click=lambda c, b, m: m.start(DepartmentTestSelectionSG.selection, mode=StartMode.NORMAL)
        ),
        state=GeneralTestSG.completed
    )
)

# Выбор отделов для тестирования
department_test_selection_dialog = Dialog(
    Window(
        Format(
            "🏢 <b>Выбор отдела для тестирования</b>\n\n"
            "Для какого отдела ты бы хотел(а) пройти опрос? Если тебе интересны несколько отделов, то после завершения одного опроса ты сможешь перейти к другому. Не забудь, что здесь тоже действуют временные ограничения!\n\n"
            "📋 <b>Напомним о 5 волонтёрских блоках:</b>\n\n"
            "– <b>Логистика:</b> экскурсии для гостей, регистрация участников, гардероб, кейтеринг, навигация в холле, вынос подарков, монтаж и демонтаж;\n\n"
            "– <b>Программа:</b> техническая и организационная помощь в аудиториях, регистрация и сопровождение спикеров, помощь в спикерской;\n\n"
            "– <b>Партнеры:</b> встреча партнеров и их сопровождение на площадке;\n\n"
            "– <b>PR:</b> встреча и координация журналистов, интервью с участниками, написание статей о Конференции;\n\n"
            "– <b>Маркетинг:</b> волонтеры-фотографы, волонтеры с навыками копирайтинга, которые будут создавать мини-конспект каждого мероприятия."
        ),
        Column(
            Button(
                Format("{'🔒 ' if logistics_completed else ''}🔧 Логистика"),
                id="logistics_test",
                on_click=lambda c, b, m: on_department_test_start(c, b, m, "logistics", LogisticsTestSG, "Логистика"),
                when="~logistics_completed"
            ),
            Button(
                Format("{'🔒 ' if program_completed else ''}📋 Программа"),
                id="program_test", 
                on_click=lambda c, b, m: on_department_test_start(c, b, m, "program", ProgramTestSG, "Программа"),
                when="~program_completed"
            ),
            Button(
                Format("{'🔒 ' if partners_completed else ''}🤝 Партнеры"),
                id="partners_test",
                on_click=lambda c, b, m: on_department_test_start(c, b, m, "partners", PartnersTestSG, "Партнеры"),
                when="~partners_completed"
            ),
            Button(
                Format("{'🔒 ' if pr_completed else ''}📰 PR"),
                id="pr_test",
                on_click=lambda c, b, m: on_department_test_start(c, b, m, "pr", PRTestSG, "PR"),
                when="~pr_completed"
            ),
            Button(
                Format("{'🔒 ' if marketing_completed else ''}📸 Маркетинг"),
                id="marketing_test",
                on_click=lambda c, b, m: on_department_test_start(c, b, m, "marketing", MarketingTestSG, "Маркетинг"),
                when="~marketing_completed"
            ),
            Button(
                Const("✅ Закончить тестирование"),
                id="finish_testing",
                on_click=on_finish_testing,
                when="can_finish"
            )
        ),
        state=DepartmentTestSelectionSG.selection,
        getter=department_selection_getter
    )
)


# Функции-геттеры для отделов
async def logistics_getter(dialog_manager: DialogManager, **kwargs):
    return await department_question_getter(dialog_manager, "logistics", LOGISTICS_QUESTIONS, **kwargs)

async def program_getter(dialog_manager: DialogManager, **kwargs):
    return await department_question_getter(dialog_manager, "program", PROGRAM_QUESTIONS, **kwargs)

async def partners_getter(dialog_manager: DialogManager, **kwargs):
    return await department_question_getter(dialog_manager, "partners", PARTNERS_QUESTIONS, **kwargs)

async def pr_getter(dialog_manager: DialogManager, **kwargs):
    return await department_question_getter(dialog_manager, "pr", PR_QUESTIONS, **kwargs)

async def marketing_getter(dialog_manager: DialogManager, **kwargs):
    return await department_question_getter(dialog_manager, "marketing", MARKETING_QUESTIONS, **kwargs)


# Функции-обработчики для отделов
async def on_logistics_answer(message: Message, message_input: MessageInput, manager: DialogManager):
    await on_department_answer(message, message_input, manager, "logistics", LogisticsTestSG, 6)

async def on_program_answer(message: Message, message_input: MessageInput, manager: DialogManager):
    await on_department_answer(message, message_input, manager, "program", ProgramTestSG, 6)

async def on_partners_answer(message: Message, message_input: MessageInput, manager: DialogManager):
    await on_department_answer(message, message_input, manager, "partners", PartnersTestSG, 6)

async def on_pr_answer(message: Message, message_input: MessageInput, manager: DialogManager):
    await on_department_answer(message, message_input, manager, "pr", PRTestSG, 4)

async def on_marketing_answer(message: Message, message_input: MessageInput, manager: DialogManager):
    await on_department_answer(message, message_input, manager, "marketing", MarketingTestSG, 5)


# Диалог тестирования Логистики
logistics_test_dialog = Dialog(
    *[Window(
        Format("🔧 <b>Логистика - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}" + 
               ("\n\n⏰ Оставшееся время: {remaining_time} сек." if i <= 6 else "")),
        MessageInput(on_logistics_answer),
        state=getattr(LogisticsTestSG, f'q{i}'),
        getter=logistics_getter
    ) for i in range(1, 7)],
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Логистики!</b>"),
        Button(
            Const("⬅️ Вернуться к выбору отделов"),
            id="back_to_selection",
            on_click=on_department_completed
        ),
        state=LogisticsTestSG.completed
    )
)

# Диалог тестирования Программы
program_test_dialog = Dialog(
    *[Window(
        Format("📋 <b>Программа - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}" +
               ("\n\n⏰ Оставшееся время: {remaining_time} сек." if i <= 6 else "")),
        MessageInput(on_program_answer),
        state=getattr(ProgramTestSG, f'q{i}'),
        getter=program_getter
    ) for i in range(1, 7)],
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Программы!</b>"),
        Button(
            Const("⬅️ Вернуться к выбору отделов"),
            id="back_to_selection",
            on_click=on_department_completed
        ),
        state=ProgramTestSG.completed
    )
)

# Диалог тестирования Партнеров
partners_test_dialog = Dialog(
    *[Window(
        Format("🤝 <b>Партнеры - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}" +
               ("\n\n⏰ Оставшееся время: {remaining_time} сек." if i <= 6 else "")),
        MessageInput(on_partners_answer),
        state=getattr(PartnersTestSG, f'q{i}'),
        getter=partners_getter
    ) for i in range(1, 7)],
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Партнеров!</b>"),
        Button(
            Const("⬅️ Вернуться к выбору отделов"),
            id="back_to_selection",
            on_click=on_department_completed
        ),
        state=PartnersTestSG.completed
    )
)

# Диалог тестирования PR
pr_test_dialog = Dialog(
    *[Window(
        Format("📰 <b>PR - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}" +
               ("\n\n⏰ Оставшееся время: {remaining_time} сек." if i <= 4 else "")),
        MessageInput(on_pr_answer),
        state=getattr(PRTestSG, f'q{i}'),
        getter=pr_getter
    ) for i in range(1, 5)],
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела PR!</b>"),
        Button(
            Const("⬅️ Вернуться к выбору отделов"),
            id="back_to_selection",
            on_click=on_department_completed
        ),
        state=PRTestSG.completed
    )
)

# Диалог тестирования Маркетинга
marketing_test_dialog = Dialog(
    *[Window(
        Format("📸 <b>Маркетинг - Вопрос {question_num}/{total_questions}</b>\n\n"
               "{question_text}" +
               ("\n\n⏰ Оставшееся время: {remaining_time} сек." if i <= 3 else "")),
        MessageInput(on_marketing_answer),
        state=getattr(MarketingTestSG, f'q{i}'),
        getter=marketing_getter
    ) for i in range(1, 6)],
    Window(
        Const("🎉 <b>Огонь, ты закончил(а) опрос для отдела Маркетинга!</b>"),
        Button(
            Const("⬅️ Вернуться к выбору отделов"),
            id="back_to_selection",
            on_click=on_department_completed
        ),
        state=MarketingTestSG.completed
    )
)
