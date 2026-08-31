from aiogram import types
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Group, Start, Radio, Column
from aiogram_dialog.widgets.text import Const, Format

from bot.states import DepartmentSelectionSG, ApplicationSG


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


# Геттеры данных
async def get_rating_options(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для выбора рейтинга"""
    ratings = [
        {"id": "1", "text": "1"},
        {"id": "2", "text": "2"},
        {"id": "3", "text": "3"},
        {"id": "4", "text": "4"},
        {"id": "5", "text": "5"},
    ]
    
    return {"ratings": ratings}


async def get_logistics_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Логистика"
    return result


async def get_marketing_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Маркетинг"
    return result


async def get_pr_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "PR"
    return result


async def get_program_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Программа"
    return result


async def get_partners_data(dialog_manager: DialogManager, **kwargs):
    data = get_rating_options(dialog_manager, **kwargs)
    result = await data
    result["department"] = "Партнеры"
    return result


async def get_dept_overview_data(dialog_manager: DialogManager, **kwargs):
    data = dialog_manager.dialog_data
    
    overview_text = f"""📊 Ваши оценки отделов:

• Логистика: {data.get('logistics_rating', 'Не указано')}
• Маркетинг: {data.get('marketing_rating', 'Не указано')}
• PR: {data.get('pr_rating', 'Не указано')}
• Программа: {data.get('program_rating', 'Не указано')}
• Партнеры: {data.get('partners_rating', 'Не указано')}

Проверьте свои оценки и нажмите "Продолжить" для завершения или "Изменить" для корректировки."""

    return {"overview_text": overview_text}


department_selection_dialog = Dialog(
    # Логистика
    Window(
        Format("📊 Оцените отдел '{department}' от 1 до 5:"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="logistics_rating_radio",
                item_id_getter=lambda item: item["id"],
                items="ratings",
                on_click=on_logistics_rating
            ),
        ),
        state=DepartmentSelectionSG.logistics,
        getter=get_logistics_data,
    ),
    
    # Маркетинг
    Window(
        Format("📊 Оцените отдел '{department}' от 1 до 5:"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="marketing_rating_radio",
                item_id_getter=lambda item: item["id"],
                items="ratings",
                on_click=on_marketing_rating
            ),
        ),
        state=DepartmentSelectionSG.marketing,
        getter=get_marketing_data,
    ),
    
    # PR
    Window(
        Format("📊 Оцените отдел '{department}' от 1 до 5:"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="pr_rating_radio",
                item_id_getter=lambda item: item["id"],
                items="ratings",
                on_click=on_pr_rating
            ),
        ),
        state=DepartmentSelectionSG.pr,
        getter=get_pr_data,
    ),
    
    # Программа
    Window(
        Format("📊 Оцените отдел '{department}' от 1 до 5:"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="program_rating_radio",
                item_id_getter=lambda item: item["id"],
                items="ratings",
                on_click=on_program_rating
            ),
        ),
        state=DepartmentSelectionSG.program,
        getter=get_program_data,
    ),
    
    # Партнеры
    Window(
        Format("📊 Оцените отдел '{department}' от 1 до 5:"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="partners_rating_radio",
                item_id_getter=lambda item: item["id"],
                items="ratings",
                on_click=on_partners_rating
            ),
        ),
        state=DepartmentSelectionSG.partners,
        getter=get_partners_data,
    ),
    
    # Обзор выбранных оценок
    Window(
        Format("{overview_text}"),
        Group(
            Button(Const("✅ Продолжить"), id="continue", on_click=on_departments_done),
            Button(Const("✏️ Изменить"), id="edit", on_click=lambda c, b, m: m.switch_to(DepartmentSelectionSG.logistics)),
            width=1,
        ),
        state=DepartmentSelectionSG.overview,
        getter=get_dept_overview_data,
    ),
)
