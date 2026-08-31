from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Start
from aiogram_dialog.widgets.text import Const

from bot.states import StartSG, ApplicationSG


start_dialog = Dialog(
    Window(
        Const(
            'Привет! Это бот для отбора экипажа волонтеров на Конференцию «Менеджмент Будущего» 2026 <tg-emoji emoji-id="5255880273299545143">🌍</tg-emoji>\n\n'
            'Чтобы начать заполнение анкеты нажми «старт» <tg-emoji emoji-id="5256101678863654703">⬇️</tg-emoji>'
        ),
        Start(
            Const("🚀 Старт"),
            id="start_application",
            state=ApplicationSG.full_name
        ),
        state=StartSG.welcome,
    ),
)

