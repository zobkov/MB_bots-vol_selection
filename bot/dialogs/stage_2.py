from aiogram import types
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import Dialog, DialogManager, Window, StartMode, ShowMode
from aiogram_dialog.widgets.kbd import Button, Start, Group, Select, Back, Next, SwitchTo, Cancel, Radio, Column
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput, MessageInput

from bot.states import DepartmentSelectionSG, ApplicationSG, MenuSG, Stage2SG, TestingSG
from database.repositories import UserRepository, ApplicationRepository
from database.db import Database
import re
import logging

logger = logging.getLogger(__name__)


# Геттеры для данных
async def get_days_options(dialog_manager: DialogManager, **kwargs):
    """Геттер для вариантов количества дней участия"""
    return {
        "days_options": [
            {"id": "2", "text": "2 дня"},
            {"id": "3", "text": "3 дня"}
        ]
    }


async def get_time_options(dialog_manager: DialogManager, **kwargs):
    """Геттер для вариантов времени участия"""
    return {
        "time_options": [
            {"id": "full", "text": "Полный день (8:00 – 20:00)"},
            {"id": "morning", "text": "С утра (8:00 – 14:00)"},
            {"id": "afternoon", "text": "После обеда (14:00 – 20:00)"}
        ]
    }


# Обработчики выбора
async def on_days_selected(callback: CallbackQuery, widget, dialog_manager: DialogManager, item_id: str):
    """Обработка выбора количества дней"""
    dialog_manager.dialog_data["participation_days"] = item_id
    await dialog_manager.next()


async def on_time_selected(callback: CallbackQuery, widget, dialog_manager: DialogManager, item_id: str):
    """Обработка выбора времени участия"""
    dialog_manager.dialog_data["participation_time"] = item_id
    await dialog_manager.next()


# Обработчик перехода к следующему этапу
async def on_next_clicked(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Обработка перехода к следующему окну"""
    await dialog_manager.next()


# Обработчик начала тестирования
async def on_start_testing(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    """Обработка начала тестирования"""
    try:
        # Сохраняем данные второго этапа в базу данных
        user_id = callback.from_user.id
        db: Database = dialog_manager.middleware_data.get("db")
        
        if db:
            participation_data = {
                "days": dialog_manager.dialog_data.get("participation_days"),
                "time": dialog_manager.dialog_data.get("participation_time")
            }
            
            # Сохраняем данные участия
            async with db.session() as session:
                from database.repositories import Stage2Repository, UserRepository
                stage2_repo = Stage2Repository(session)
                user_repo = UserRepository(session)
                
                user = await user_repo.get_user_by_telegram_id(user_id)
                if user:
                    await stage2_repo.get_or_create_stage2_record(user.id)
                    await stage2_repo.update_participation_data(
                        user.id, 
                        participation_data["days"], 
                        participation_data["time"]
                    )
                    await stage2_repo.mark_general_questions_started(user.id)
            
            logger.info(f"Сохранение данных участия для пользователя {user_id}: {participation_data}")
        
        # Переходим к общему тестированию
        await dialog_manager.start(TestingSG.start, mode=StartMode.RESET_STACK)
        
    except Exception as e:
        logger.error(f"Ошибка при начале тестирования: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")


stage2_dialog = Dialog(
    # Окно 1: Приветствие второго этапа
    Window(
        Format("Привет еще раз! Теперь мы начинаем второй этап отбора. Для начала надо будет ответить на пару вопросов."),
        Next(Format("➡️ Перейти далее"), id="stage2_start_to_questions", on_click=on_next_clicked),
        state=Stage2SG.start,
    ),

    # Окно 2: Вопрос о количестве дней
    Window(
        Format("Сколько дней ты сможешь участвовать на конференции?\n\n"
               "⚠️ Обрати внимание, что наш кампус находится по адресу:\n"
               "📍 Санкт-Петербургское шоссе 109, г. Петергоф"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="days_radio",
                item_id_getter=lambda item: item["id"],
                items="days_options",
                on_click=on_days_selected
            ),
        ),
        Cancel(Const("❌ Отмена")),
        state=Stage2SG.start_question_1,
        getter=get_days_options,
    ),

    # Окно 3: Вопрос о времени участия
    Window(
        Format("Сколько времени ты готов(а) помогать на конференции?\n\n"
               "⚠️ <b>Важно:</b> тайминги условные, для каждого волонтера предусмотрено время отдыха."),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="time_radio",
                item_id_getter=lambda item: item["id"],
                items="time_options",
                on_click=on_time_selected
            ),
        ),
        Cancel(Const("❌ Отмена")),
        state=Stage2SG.start_question_2,
        getter=get_time_options,
    ),

    # Окно 4: Переход к тестированию
    Window(
        Format("Спасибо за информацию!\n\n"
               "Теперь мы переходим ко второму этапу. Мы начнем с общих вопросов для всех отделов, "
               "а затем тебе нужно будет пройти опрос по интересующим тебя отделам.\n\n"
               "⚠️ <b>ВАЖНО:</b>\n"
               "• У каждого вопроса есть ограниченное время на ответ, которое указано в скобках после вопроса\n"
               "• По истечении времени ответ не будет записан, тебе сразу придет следующий вопрос\n"
               "• Убедись, что сможешь уделить опросу 20-60 минут (зависит от отдела)\n"
               "• На вопросы нужно отвечать одним сообщением\n"
               "• Ответ нельзя редактировать\n"
               "• После ответа на вопрос сразу приходит следующий"),
        Start(
            Const("🚀 Начать тестирование"), 
            id="to_testing", 
            state=TestingSG.start,
            on_click=on_start_testing
        ),
        Cancel(Const("❌ Отмена")),
        state=Stage2SG.testing_start,
    ),
)
