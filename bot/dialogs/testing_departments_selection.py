"""
Диалог выбора отделов для тестирования (Stage 2)
"""
import logging
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Group, Row
from aiogram_dialog.widgets.text import Const, Format
from bot.states import TestingDepartmentsSelectionSG, GeneralQuestionsSG, LogisticsTestSG, ProgramTestSG, PartnersTestSG, PRTestSG, MarketingTestSG

logger = logging.getLogger(__name__)


# Список доступных отделов для тестирования
TESTING_DEPARTMENTS = [
    {"id": "logistics", "name": "Логистика", "icon": "🔧", "state": LogisticsTestSG.q1},
    {"id": "program", "name": "Программа", "icon": "📋", "state": ProgramTestSG.q1},
    {"id": "partners", "name": "Партнеры", "icon": "🤝", "state": PartnersTestSG.q1},
    {"id": "pr", "name": "PR", "icon": "📢", "state": PRTestSG.q1},
    {"id": "marketing", "name": "Маркетинг", "icon": "📈", "state": MarketingTestSG.q1},
]


async def get_departments_data(**kwargs):
    """Получение данных отделов"""
    return {
        "departments": TESTING_DEPARTMENTS
    }


async def on_general_testing_start(callback: CallbackQuery, button, dialog_manager: DialogManager):
    """Запуск общего тестирования"""
    logger.info(f"Starting general testing for user {callback.from_user.id}")
    await dialog_manager.start(GeneralQuestionsSG.q1, mode=StartMode.NORMAL)


async def on_department_button_click(callback: CallbackQuery, button, dialog_manager: DialogManager, department_id: str):
    """Обработка клика по кнопке отдела"""
    logger.info(f"Department selected for testing: {department_id} by user {callback.from_user.id}")
    
    # Находим отдел и запускаем соответствующий тест
    department = next((dept for dept in TESTING_DEPARTMENTS if dept["id"] == department_id), None)
    if department:
        await dialog_manager.start(department["state"], mode=StartMode.NORMAL)
    else:
        logger.error(f"Unknown department: {department_id}")


async def on_testing_complete(callback: CallbackQuery, button, dialog_manager: DialogManager):
    """Завершение всего тестирования"""
    logger.info(f"Testing completed for user {callback.from_user.id}")
    # Возвращаемся к основному меню или следующему этапу
    from bot.states import MenuSG
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


# Создание диалога выбора отделов тестирования
testing_departments_dialog = Dialog(
    Window(
        Format(
            "📝 <b>Тестирование отделов - Этап 2</b>\n\n"
            "Выберите отдел для прохождения тестирования:\n\n"
            "🎯 <b>Обязательно:</b>\n"
            "• Общие вопросы\n\n"
            "🏢 <b>Отделы (выберите интересующие):</b>"
        ),
        
        # Кнопка общих вопросов
        Button(
            Const("📝 Общие вопросы"),
            id="general_testing",
            on_click=on_general_testing_start
        ),
        
        # Список отделов
        Group(
            Button(
                Const("🔧 Логистика"),
                id="dept_logistics",
                on_click=lambda c, b, dm: on_department_button_click(c, b, dm, "logistics")
            ),
            Button(
                Const("📋 Программа"),
                id="dept_program", 
                on_click=lambda c, b, dm: on_department_button_click(c, b, dm, "program")
            ),
            Button(
                Const("🤝 Партнеры"),
                id="dept_partners",
                on_click=lambda c, b, dm: on_department_button_click(c, b, dm, "partners")
            ),
            Button(
                Const("📢 PR"),
                id="dept_pr",
                on_click=lambda c, b, dm: on_department_button_click(c, b, dm, "pr")
            ),
            Button(
                Const("📈 Маркетинг"),
                id="dept_marketing",
                on_click=lambda c, b, dm: on_department_button_click(c, b, dm, "marketing")
            ),
            width=2
        ),
        
        # Кнопка завершения
        Row(
            Button(
                Const("✅ Завершить тестирование"),
                id="complete_testing",
                on_click=on_testing_complete
            )
        ),
        
        state=TestingDepartmentsSelectionSG.selection,
        getter=get_departments_data
    )
)