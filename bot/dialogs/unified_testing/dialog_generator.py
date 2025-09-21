"""
Генератор универсальных диалогов тестирования
"""
import asyncio
import logging
from typing import List, Dict, Any, Callable
from aiogram.types import Message, CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const, Format, Progress
from aiogram_dialog.widgets.input import TextInput

from .models import TestConfig, TestQuestion
from .test_engine import test_engine

logger = logging.getLogger(__name__)


class UniversalTestDialogGenerator:
    """Генератор диалогов для унифицированной системы тестирования"""
    
    @staticmethod
    def create_question_getter(config: TestConfig, question: TestQuestion):
        """Создание геттера для конкретного вопроса"""
        async def get_question_data(dialog_manager: DialogManager = None, **kwargs):
            logger.debug(f"Getting data for {config.test_type} question {question.number}")
            
                        # Проверяем глобальные pending timeout переходы - больше не используется
            # Переходы теперь выполняются прямо в timeout callback через bg_manager.next()
            
            # Запускаем таймер если находимся в правильном состоянии
            
            # Проверяем флаги таймаута от bg_manager и обрабатываем если есть (устаревшая система)
            # Больше не используем эту систему, всё переведено на глобальное состояние pending_transitions
            
            # На первом вопросе инициализируем прогресс теста (in-memory)
            if question.number == 1:
                started_key = f"test_{config.test_type}_started"
                if not dialog_manager.dialog_data.get(started_key, False):
                    await test_engine.start_test(dialog_manager, config)

            # Отправляем медиа при первом вопросе если требуется (старый способ)
            if question.number == 1 and config.send_media_on_start:
                await test_engine.send_test_media(dialog_manager, config)
            
            # Отправляем медиа для конкретного вопроса (новый способ)
            if question.media_path:
                await test_engine.send_question_media(dialog_manager, config, question)
            
            # Запускаем таймер если находимся в правильном состоянии
            if dialog_manager and hasattr(dialog_manager, 'current_context'):
                current_state = dialog_manager.current_context().state
                expected_state = getattr(config.states_group, f'q{question.number}')
                
                if current_state == expected_state:
                    # Проверяем, не запущен ли уже таймер
                    user_id = dialog_manager.event.from_user.id
                    timer_key = test_engine.get_user_timer_key(user_id, config.test_type, question.number)
                    
                    timer_started_key = f"{timer_key}_timer_started"
                    timer_stopped_key = f"{timer_key}_stopped"
                    
                    # Проверяем и dialog_data и реальное состояние таймера
                    timer_already_started_in_data = dialog_manager.dialog_data.get(timer_started_key, False)
                    timer_stopped = dialog_manager.dialog_data.get(timer_stopped_key, False)
                    timer_active_in_manager = test_engine.timer_manager._is_timer_active(user_id, timer_key)
                    
                    if (not timer_already_started_in_data and not timer_stopped and not timer_active_in_manager):
                        logger.debug(f"Starting timer for {config.test_type} question {question.number}")
                        dialog_manager.dialog_data[timer_started_key] = True
                        await test_engine.start_question_timer(dialog_manager, config, question)
            
            return {
                "question_text": question.text,
                "question_number": question.number,
                "total_questions": len(config.questions),
                "time_limit": question.time_limit,
                "test_display_name": config.display_name,
                "test_icon": config.icon
            }
        
        return get_question_data
    
    @staticmethod
    def create_input_handler(config: TestConfig, question: TestQuestion):
        """Создание обработчика ввода для конкретного вопроса"""
        async def on_input(message: Message, widget, dialog_manager: DialogManager, text: str):
            logger.debug(f"Input received for {config.test_type} q{question.number}: '{text}'")
            
            # Записываем ответ в память. Даже если был таймаут почти одновременно, save_answer вернёт False
            await test_engine.save_answer(dialog_manager, config, question.number, text)
            
            # Переходим к следующему вопросу или к завершению
            if question.number < len(config.questions):
                await dialog_manager.next()
            else:
                await dialog_manager.switch_to(config.states_group.completed)
                
        return on_input
    
    @staticmethod
    def create_back_to_departments_handler():
        """Создание обработчика возврата к выбору отделов"""
        async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
            # Очищаем данные теста пользователя
            user_id = callback.from_user.id
            await test_engine.cleanup_user_test(user_id)
            
            # Возвращаемся к новому диалогу выбора отделов тестирования
            from bot.states import TestingDepartmentsSelectionSG
            await dialog_manager.start(TestingDepartmentsSelectionSG.selection, mode=StartMode.RESET_STACK)
            
        return on_back_to_departments
    
    @staticmethod
    def create_test_dialog(config: TestConfig) -> Dialog:
        """Создание полного диалога тестирования"""
        logger.info(f"Creating dialog for {config.test_type} test with {len(config.questions)} questions")
        
        windows = []
        
        # Создаем окна для каждого вопроса
        for question in config.questions:
            question_getter = UniversalTestDialogGenerator.create_question_getter(config, question)
            input_handler = UniversalTestDialogGenerator.create_input_handler(config, question)
            
            # Создаем геттер таймера с динамическим ключом
            def create_timer_getter(q_num):
                async def timer_getter(dialog_manager: DialogManager, **kwargs):
                    user_id = dialog_manager.event.from_user.id
                    timer_key = f"user_{user_id}_{config.test_type}_q{q_num}"
                    return await test_engine.timer_manager.get_timer_progress_data(timer_key)(dialog_manager, **kwargs)
                return timer_getter
            
            timer_getter = create_timer_getter(question.number)
            
            # Создаем окно вопроса  
            def create_timer_display_dynamic(q_num):
                async def dynamic_getter(dialog_manager: DialogManager, **kwargs):
                    user_id = dialog_manager.event.from_user.id
                    timer_key = f"user_{user_id}_{config.test_type}_q{q_num}"
                    timer_data = await test_engine.timer_manager.get_timer_progress_data(timer_key)(dialog_manager, **kwargs)
                    return timer_data
                return dynamic_getter
            
            dynamic_timer_getter = create_timer_display_dynamic(question.number)
            
            window = Window(
                Format(
                    "{test_icon} <b>{test_display_name} - Вопрос {question_number}/{total_questions}</b>\n\n"
                    "{question_text}\n\n"
                    "(Время на ответ: {time_limit} секунд)"
                ),
                Format("⏱️ Оставшееся время: {timer_minutes:02d}:{timer_seconds:02d}"),
                Progress(
                    "timer_progress",
                    filled="🟩",
                    empty="⬜",
                    width=10
                ),
                TextInput(
                    id=f"{config.test_type}_q{question.number}_input",
                    on_success=input_handler
                ),
                state=getattr(config.states_group, f'q{question.number}'),
                getter=[question_getter, dynamic_timer_getter]
            )
            
            windows.append(window)
        
        # Создаем окно завершения теста
        async def completion_getter(dialog_manager: DialogManager = None, **kwargs):
            if dialog_manager:
                # Идем по новой схеме: сохраняем ВСЕ ответы одним коммитом при первом рендере окна
                test_persisted_key = f"test_{config.test_type}_persisted"
                if not dialog_manager.dialog_data.get(test_persisted_key, False):
                    dialog_manager.dialog_data[test_persisted_key] = True
                    try:
                        await test_engine.persist_results(dialog_manager, config)
                    except Exception as e:
                        logger.error(f"Error persisting results in completion window: {e}", exc_info=True)
                    
            return {
                "test_display_name": config.display_name,
                "test_icon": config.icon
            }
        
        completion_window = Window(
            Format(
                "{test_icon} <b>Тестирование по отделу \"{test_display_name}\" завершено!</b>\n\n"
                "✅ Все ответы сохранены\n"
                "📊 Результаты будут учтены при оценке\n\n"
                "Выберите действие:"
            ),
            Button(
                Const("🏢 Вернуться к выбору отделов"),
                id="back_to_departments",
                on_click=UniversalTestDialogGenerator.create_back_to_departments_handler()
            ),
            state=config.states_group.completed,
            getter=completion_getter
        )
        
        windows.append(completion_window)
        
        dialog = Dialog(*windows)
        logger.info(f"Dialog created for {config.test_type} with {len(windows)} windows")
        
        return dialog


def create_test_dialog(config: TestConfig) -> Dialog:
    """Удобная функция для создания диалога тестирования"""
    return UniversalTestDialogGenerator.create_test_dialog(config)