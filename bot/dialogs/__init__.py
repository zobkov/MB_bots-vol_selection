
from bot.dialogs.start import start_dialog
from bot.dialogs.menu import menu_dialog
from bot.dialogs.application import application_dialog
from bot.dialogs.departments import department_selection_dialog
from bot.dialogs.testing import (
    testing_dialog, general_test_dialog, department_test_selection_dialog,
    logistics_test_dialog, program_test_dialog, partners_test_dialog,
    pr_test_dialog, marketing_test_dialog
)
from bot.dialogs.dialog_error_handler import dialog_error_handler


__all__ = [
    "start_dialog",
    "menu_dialog", 
    "application_dialog",
    "department_selection_dialog",
    "testing_dialog",
    "general_test_dialog",
    "department_test_selection_dialog",
    "logistics_test_dialog",
    "program_test_dialog",
    "partners_test_dialog",
    "pr_test_dialog",
    "marketing_test_dialog",
    "dialog_error_handler"
]
