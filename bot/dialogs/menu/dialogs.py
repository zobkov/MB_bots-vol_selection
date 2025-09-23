from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from bot.states import MenuSG, ApplicationSG, DepartmentSelectionSG
from .getters import get_menu_data, get_support_data


menu_dialog = Dialog(
    Window(
        Format("{menu_text}"),
        Start(
            Const("📝 Заполнить анкету"),
            id="fill_application",
            state=ApplicationSG.full_name,
            when="show_application_button"
        ),
        Start(
            Const("🏢 Выбрать отделы"),
            id="select_departments",
            state=DepartmentSelectionSG.logistics,
            when="show_departments_button"
        ),
        SwitchTo(
            Const("📞 Поддержка"),
            id="support",
            state=MenuSG.support
        ),
        state=MenuSG.main,
        getter=get_menu_data,
    ),
    Window(
        Format("{support_text}"),
        SwitchTo(
            Const("🔙 Назад в меню"),
            id="back_to_menu",
            state=MenuSG.main
        ),
        state=MenuSG.support,
        getter=get_support_data,
    ),
)