
from bot.dialogs.start import start_dialog
from bot.dialogs.menu import menu_dialog
from bot.dialogs.application import application_dialog
from bot.dialogs.departments import department_selection_dialog
from bot.dialogs.dialog_error_handler import dialog_error_handler

__all__ = [
    "start_dialog",
    "menu_dialog", 
    "application_dialog",
    "department_selection_dialog",
    "dialog_error_handler"
]
