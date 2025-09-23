from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button

from bot.states import DepartmentSelectionSG


# Обработчики выбора рейтинга для каждого отдела
async def on_logistics_rating(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    rating = int(item_id)
    dialog_manager.dialog_data["logistics_rating"] = rating
    await dialog_manager.next()


async def on_marketing_rating(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    rating = int(item_id)
    dialog_manager.dialog_data["marketing_rating"] = rating
    await dialog_manager.next()


async def on_pr_rating(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    rating = int(item_id)
    dialog_manager.dialog_data["pr_rating"] = rating
    await dialog_manager.next()


async def on_program_rating(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    rating = int(item_id)
    dialog_manager.dialog_data["program_rating"] = rating
    await dialog_manager.next()


async def on_partners_rating(callback: CallbackQuery, radio, dialog_manager: DialogManager, item_id: str):
    rating = int(item_id)
    dialog_manager.dialog_data["partners_rating"] = rating
    await dialog_manager.next()


# Обработчик завершения выбора отделов
async def on_departments_done(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    # Получаем данные об оценках отделов
    result_data = {
        "logistics_rating": dialog_manager.dialog_data.get("logistics_rating"),
        "marketing_rating": dialog_manager.dialog_data.get("marketing_rating"),
        "pr_rating": dialog_manager.dialog_data.get("pr_rating"),
        "program_rating": dialog_manager.dialog_data.get("program_rating"),
        "partners_rating": dialog_manager.dialog_data.get("partners_rating"),
    }
    
    # Закрываем диалог с возвратом данных
    await dialog_manager.done(result=result_data)


# Обработчик возврата к редактированию
async def on_departments_edit(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    await dialog_manager.switch_to(DepartmentSelectionSG.logistics)