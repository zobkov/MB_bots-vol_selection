from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Start
from aiogram_dialog.widgets.text import Const

from bot.states import StartSG, MenuSG
from .getters import get_start_data


start_dialog = Dialog(
    Window(
        Const("🌟 Добро пожаловать в бот отбора волонтеров МБ 2025!\n\n"
              "Здесь ты сможешь подать заявку на участие в команде волонтеров "
              "и пройти все этапы отбора.\n\n"
              "Нажми кнопку ниже, чтобы перейти в главное меню."),
        Start(
            Const("🏠 Перейти в главное меню"),
            id="to_menu",
            state=MenuSG.main
        ),
        state=StartSG.start,
        getter=get_start_data,
    ),
)