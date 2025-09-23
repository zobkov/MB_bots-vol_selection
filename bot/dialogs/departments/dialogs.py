from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, Group, Radio, Column
from aiogram_dialog.widgets.text import Const, Format

from bot.states import DepartmentSelectionSG
from .handlers import (
    on_logistics_rating, on_marketing_rating, on_pr_rating, 
    on_program_rating, on_partners_rating, on_departments_done, 
    on_departments_edit
)
from .getters import (
    get_logistics_data, get_marketing_data, get_pr_data,
    get_program_data, get_partners_data, get_dept_overview_data
)


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
            Button(Const("✏️ Изменить"), id="edit", on_click=on_departments_edit),
            width=1,
        ),
        state=DepartmentSelectionSG.overview,
        getter=get_dept_overview_data,
    ),
)