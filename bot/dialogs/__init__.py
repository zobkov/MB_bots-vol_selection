
from bot.dialogs.start import start_dialog
from bot.dialogs.menu import menu_dialog
from bot.dialogs.application import application_dialog
from bot.dialogs.departments import department_selection_dialog
from bot.dialogs.dialog_error_handler import dialog_error_handler
from bot.dialogs.stage_2 import stage2_dialog
from bot.dialogs.general_testing import general_testing_dialog
from bot.dialogs.logistics_test_unified import logistics_test_dialog
from bot.dialogs.program_test import program_test_dialog
from bot.dialogs.partners_test import partners_test_dialog
from bot.dialogs.pr_test import pr_test_dialog
from bot.dialogs.marketing_test import marketing_test_dialog


__all__ = [
    "start_dialog",
    "menu_dialog", 
    "application_dialog",
    "department_selection_dialog",
    "dialog_error_handler",
    "stage2_dialog",
    "general_testing_dialog",
    "logistics_test_dialog",
    "program_test_dialog",
    "partners_test_dialog",
    "pr_test_dialog",
    "marketing_test_dialog"
]
