from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Start
from aiogram_dialog.widgets.text import Const

from bot.states import StartSG, ApplicationSG
from utils.emojis import emoji


start_dialog = Dialog(
    Window(
        Const(
            f'Привет! Это бот для отбора экипажа волонтеров на Конференцию «Менеджмент Будущего» 2026 {emoji("earth")}\n\n'
            f'Чтобы начать заполнение анкеты нажми «старт» {emoji("arrow_down")}'
        ),
        Start(
            Const("🚀 Старт"),
            id="start_application",
            state=ApplicationSG.full_name
        ),
        state=StartSG.welcome,
    ),
)


