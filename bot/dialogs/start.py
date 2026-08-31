from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Start
from aiogram_dialog.widgets.text import Const

from bot.states import StartSG, ApplicationSG


start_dialog = Dialog(
    Window(
        Const(
            "Привет! Это бот для отбора экипажа волонтеров на Конференцию «Менеджмент Будущего» 2026 🌍\n\n"
            "Чтобы начать заполнение анкеты нажми «старт» ⬇️"
        ),
        Start(
            Const("🚀 Старт"),
            id="start_application",
            state=ApplicationSG.full_name
        ),
        state=StartSG.welcome,
    ),
)

