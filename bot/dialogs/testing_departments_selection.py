"""
Диалог выбора отделов для тестирования (Stage 2)
"""
import logging
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Group, Row, Select, Column
from aiogram_dialog.widgets.text import Const, Format
from bot.states import TestingDepartmentsSelectionSG, GeneralQuestionsSG, LogisticsTestSG, ProgramTestSG, PartnersTestSG, PRTestSG, MarketingTestSG
from database.repositories import Stage2Repository, DepartmentTestRepository, UserRepository

logger = logging.getLogger(__name__)


# Список доступных отделов для тестирования
TESTING_DEPARTMENTS = [
    {"id": "logistics", "name": "Логистика", "icon": "🔧", "state": LogisticsTestSG.q1},
    {"id": "program", "name": "Программа", "icon": "📋", "state": ProgramTestSG.q1},
    {"id": "partners", "name": "Партнеры", "icon": "🤝", "state": PartnersTestSG.q1},
    {"id": "pr", "name": "PR", "icon": "📢", "state": PRTestSG.q1},
    {"id": "marketing", "name": "Маркетинг", "icon": "📈", "state": MarketingTestSG.q1},
]


async def get_departments_data(dialog_manager: DialogManager, **kwargs):
    """Получение данных отделов с проверкой статуса завершения"""
    try:
        # Получаем пользователя
        db = dialog_manager.middleware_data.get("db")
        if not db:
            logger.error("Database not found in middleware")
            return {"departments": TESTING_DEPARTMENTS, "general_completed": False}
            
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            stage2_repo = Stage2Repository(session)
            dept_repo = DepartmentTestRepository(session)
            
            # Получаем telegram_id из event
            event = dialog_manager.event
            if hasattr(event, 'from_user'):
                telegram_id = event.from_user.id
            else:
                logger.error("Cannot get telegram_id from event")
                return {"departments": TESTING_DEPARTMENTS, "general_completed": False}
            
            # Получаем пользователя
            user = await user_repo.get_user_by_telegram_id(telegram_id)
            if not user:
                logger.error(f"User not found for telegram_id: {telegram_id}")
                return {"departments": TESTING_DEPARTMENTS, "general_completed": False}
            
            # Проверяем завершение общих вопросов
            # Проверяем в обеих системах - старой (stage2_answers) и новой (department_test_results)
            general_completed_old = await stage2_repo.is_general_questions_completed(user.id)
            general_completed_new = await dept_repo.is_department_completed(user.id, "general")
            general_completed = general_completed_old or general_completed_new
            
            logger.debug(f"General questions status for user {telegram_id}: "
                        f"old_system={general_completed_old}, new_system={general_completed_new}, "
                        f"final={general_completed}")
            
            # Получаем список завершенных отделов
            completed_departments = await dept_repo.get_completed_departments(user.id)
            
            # Фильтруем отделы, оставляя только не завершенные
            available_departments = [
                dept for dept in TESTING_DEPARTMENTS 
                if dept["id"] not in completed_departments
            ]
            
            logger.info(f"User {telegram_id}: general_completed={general_completed}, "
                       f"completed_departments={completed_departments}, "
                       f"available_departments={[d['id'] for d in available_departments]}")
            
            logger.debug(f"Conditions for user {telegram_id}: "
                        f"general_not_completed={not general_completed}, "
                        f"departments_available={len(available_departments) > 0}, "
                        f"all_tests_completed={general_completed and len(available_departments) == 0}")
            
            # Форматируем статус отделов
            departments_status = ""
            for dept in TESTING_DEPARTMENTS:
                if dept["id"] in completed_departments:
                    departments_status += f"• {dept['icon']} {dept['name']} ✅\n"
                else:
                    departments_status += f"• {dept['icon']} {dept['name']} ❌\n"
            
            return {
                "departments": available_departments,
                "general_completed": general_completed,
                "general_not_completed": not general_completed,
                "departments_available": len(available_departments) > 0,
                "all_tests_completed": general_completed and len(available_departments) == 0,
                "general_status": "✅" if general_completed else "❌",
                "departments_status": departments_status.strip(),
                "completed_departments": completed_departments
            }
            
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error in get_departments_data: {e}", exc_info=True)
        return {"departments": TESTING_DEPARTMENTS, "general_completed": False}


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


async def on_department_select(callback: CallbackQuery, widget, dialog_manager: DialogManager, item_id: str):
    """Обработка выбора отдела из динамического списка"""
    logger.info(f"Department selected for testing: {item_id} by user {callback.from_user.id}")
    
    # Находим отдел и запускаем соответствующий тест
    department = next((dept for dept in TESTING_DEPARTMENTS if dept["id"] == item_id), None)
    if department:
        await dialog_manager.start(department["state"], mode=StartMode.NORMAL)
    else:
        logger.error(f"Unknown department: {item_id}")


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
            "Статус прохождения:\n\n"
            "🎯 <b>Обязательные:</b>\n"
            "• Общие вопросы {general_status}\n\n"
            "🏢 <b>Отделы:</b>\n"
            "{departments_status}"
        ),
        
        # Кнопка общих вопросов (показывается только если не завершены)
        Button(
            Const("📝 Пройти общие вопросы"),
            id="general_testing",
            on_click=on_general_testing_start,
            when="general_not_completed"
        ),
        
        # Динамический выбор отделов
        Column(
            Select(
                Format("{item[icon]} {item[name]}"),
                id="dept_select",
                item_id_getter=lambda item: item["id"],
                items="departments",
                on_click=on_department_select,
                when="departments_available"
            ),
        ),

        # Информационное сообщение если все тесты завершены
        Format(
            "✅ <b>Все доступные тесты завершены!</b>",
            when="all_tests_completed"
        ),
        
        # Кнопка возврата в меню
        Row(
            Button(
                Const("✅ Заврешить тестирование"),
                id="back_to_menu",
                on_click=on_testing_complete
            )
        ),
        
        state=TestingDepartmentsSelectionSG.selection,
        getter=get_departments_data
    )
)