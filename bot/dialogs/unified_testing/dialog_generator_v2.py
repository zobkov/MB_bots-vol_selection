"""
Обновленный генератор диалогов для новой архитектуры таймеров
Использует BgManager для плавного обновления UI
"""

import logging
from typing import List, Callable, Any, Dict

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager, LaunchMode, StartMode
from aiogram_dialog.widgets.text import Format, Progress
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Start

from .models import TestConfig, TestQuestion
from .test_engine_v2 import get_test_engine

logger = logging.getLogger(__name__)


class UniversalTestDialogGeneratorV2:
    """
    Обновленный генератор диалогов для унифицированной системы тестирования
    Использует новую архитектуру таймеров с BgManager
    """
    
    @staticmethod
    def create_question_getter(config: TestConfig, question: TestQuestion):
        """Создание геттера данных для вопроса"""
        async def question_getter(dialog_manager: DialogManager = None, **kwargs):
            if not dialog_manager:
                return {}
            
            test_engine = get_test_engine()
            user_id = dialog_manager.event.from_user.id
            
            # Проверяем, не завершен ли уже тест
            completion_pending = dialog_manager.dialog_data.get(f"test_{config.test_type}_completion_pending", False)
            completion_done = dialog_manager.dialog_data.get(f"test_{config.test_type}_completion_done", False)
            
            if completion_pending or completion_done:
                await dialog_manager.switch_to(getattr(config.states_group, 'completed'))
                return {
                    "question_text": question.text,
                    "question_number": question.number,
                    "total_questions": len(config.questions),
                    "time_limit": question.time_limit,
                    "test_display_name": config.display_name,
                    "test_icon": config.icon
                }
            
            # Инициализируем тест если еще не инициализирован
            if user_id not in test_engine.active_tests:
                await test_engine.start_test(dialog_manager, config)
            
            # Запускаем таймер для вопроса (если еще не запущен)
            if dialog_manager and hasattr(dialog_manager, 'current_context') and getattr(dialog_manager, 'event', None):
                current_state = dialog_manager.current_context().state
                expected_state = getattr(config.states_group, f'q{question.number}')
                
                if current_state == expected_state:
                    # Проверяем флаг запуска таймера
                    timer_key = f"timer_{config.test_type}_q{question.number}_started"
                    if not dialog_manager.dialog_data.get(timer_key):
                        # Проверяем, не отвечен ли уже этот вопрос
                        if not dialog_manager.dialog_data.get(f"test_{config.test_type}_q{question.number}_answered"):
                            try:
                                await test_engine.start_question_timer(dialog_manager, config, question)
                                dialog_manager.dialog_data[timer_key] = True  # Устанавливаем флаг
                                logger.debug(f"Started timer for {config.test_type} question {question.number}")
                            except Exception as e:
                                logger.error(f"Failed to start timer: {e}")
            
            return {
                "question_text": question.text,
                "question_number": question.number,
                "total_questions": len(config.questions),
                "time_limit": question.time_limit,
                "test_display_name": config.display_name,
                "test_icon": config.icon
            }
        
        return question_getter
    
    @staticmethod
    def create_timer_getter(config: TestConfig, question: TestQuestion):
        """
        Создание геттера для данных таймера
        BgManager будет автоматически обновлять эти данные
        """
        async def timer_getter(dialog_manager: DialogManager = None, **kwargs) -> Dict[str, Any]:
            # Данные по умолчанию (будут обновляться через BgManager)
            default_data = {
                "timer_minutes": 3,  # Начальные значения
                "timer_seconds": 0,
                "remaining_time": question.time_limit,
                "progress_percent": 100,
                "timer_progress": 100.0,
                "is_timer_active": True,
                "timer_status": "starting"
            }
            
            # Логируем первые несколько вызовов
            user_id = None
            if dialog_manager and hasattr(dialog_manager, 'event') and getattr(dialog_manager, 'event', None):
                user_id = dialog_manager.event.from_user.id
                timer_key = f"timer_{config.test_type}_getter_calls"
                call_count = dialog_manager.dialog_data.get(timer_key, 0) + 1
                dialog_manager.dialog_data[timer_key] = call_count
                
                if call_count <= 5:  # Логируем первые 5 вызовов
                    logger.info(f"🎯 timer_getter call #{call_count} for user {user_id}, {config.test_type} q{question.number}")
                    logger.debug(f"📋 dialog_data keys: {list(dialog_manager.dialog_data.keys())}")
                    
                    # Проверяем, есть ли обновленные данные от BgManager
                    if 'timer_minutes' in dialog_manager.dialog_data:
                        bg_data = {
                            "timer_minutes": dialog_manager.dialog_data.get('timer_minutes', default_data['timer_minutes']),
                            "timer_seconds": dialog_manager.dialog_data.get('timer_seconds', default_data['timer_seconds']),
                            "remaining_time": dialog_manager.dialog_data.get('remaining_time', default_data['remaining_time']),
                            "progress_percent": dialog_manager.dialog_data.get('progress_percent', default_data['progress_percent']),
                            "timer_progress": dialog_manager.dialog_data.get('timer_progress', default_data['timer_progress']),
                            "is_timer_active": dialog_manager.dialog_data.get('is_timer_active', default_data['is_timer_active']),
                            "timer_status": dialog_manager.dialog_data.get('timer_status', default_data['timer_status'])
                        }
                        logger.info(f"🔄 Found BgManager data: {bg_data}")
                        
                        # 🚨 ЛОГИРУЕМ ФИНАЛЬНЫЕ ДАННЫЕ ДЛЯ UI БОТА 🚨
                        logger.error(f"🎭 FINAL UI DATA for {config.test_type} q{question.number}: {bg_data['timer_minutes']:02d}:{bg_data['timer_seconds']:02d} (remaining: {bg_data['remaining_time']:.1f}s, progress: {bg_data['timer_progress']:.1f}%, active: {bg_data['is_timer_active']}, status: {bg_data['timer_status']})")
                        
                        return bg_data
                    else:
                        logger.warning(f"⚠️ No BgManager timer data found, using defaults: {default_data}")
                        
                        # 🚨 ЛОГИРУЕМ ДЕФОЛТНЫЕ ДАННЫЕ ДЛЯ UI БОТА 🚨
                        logger.error(f"🎭 FINAL UI DATA (DEFAULT) for {config.test_type} q{question.number}: {default_data['timer_minutes']:02d}:{default_data['timer_seconds']:02d} (remaining: {default_data['remaining_time']:.1f}s, progress: {default_data['timer_progress']:.1f}%, active: {default_data['is_timer_active']}, status: {default_data['timer_status']})")
            
            # Если нет логирования, все равно логируем финальные данные
            if dialog_manager and 'timer_minutes' in dialog_manager.dialog_data:
                # Берем данные от BgManager
                final_data = {
                    "timer_minutes": dialog_manager.dialog_data.get('timer_minutes', default_data['timer_minutes']),
                    "timer_seconds": dialog_manager.dialog_data.get('timer_seconds', default_data['timer_seconds']),
                    "remaining_time": dialog_manager.dialog_data.get('remaining_time', default_data['remaining_time']),
                    "progress_percent": dialog_manager.dialog_data.get('progress_percent', default_data['progress_percent']),
                    "timer_progress": dialog_manager.dialog_data.get('timer_progress', default_data['timer_progress']),
                    "is_timer_active": dialog_manager.dialog_data.get('is_timer_active', default_data['is_timer_active']),
                    "timer_status": dialog_manager.dialog_data.get('timer_status', default_data['timer_status'])
                }
                
                if user_id:
                    call_count = dialog_manager.dialog_data.get(f"timer_{config.test_type}_getter_calls", 0)
                    if call_count > 5:  # Для вызовов после 5-го
                        logger.error(f"🎭 FINAL UI DATA (call #{call_count}) for {config.test_type} q{question.number}: {final_data['timer_minutes']:02d}:{final_data['timer_seconds']:02d} (remaining: {final_data['remaining_time']:.1f}s, progress: {final_data['timer_progress']:.1f}%, active: {final_data['is_timer_active']}, status: {final_data['timer_status']})")
                
                return final_data
            
            # Дефолтные данные только если нет BgManager данных
            logger.error(f"🎭 FINAL UI DATA (DEFAULT) for {config.test_type} q{question.number}: {default_data['timer_minutes']:02d}:{default_data['timer_seconds']:02d} (remaining: {default_data['remaining_time']:.1f}s, progress: {default_data['timer_progress']:.1f}%, active: {default_data['is_timer_active']}, status: {default_data['timer_status']})")
            return default_data
        
        return timer_getter
    
    @staticmethod
    def create_input_handler(config: TestConfig, question: TestQuestion):
        """Создание обработчика ввода ответа"""
        async def on_input(message: Message, widget, dialog_manager: DialogManager, text: str):
            if not dialog_manager or not text.strip():
                return
            
            user_id = message.from_user.id
            test_engine = get_test_engine()
            
            # Проверяем состояние диалога
            current_state = dialog_manager.current_context().state
            expected_state = getattr(config.states_group, f'q{question.number}')
            
            # Проверяем, не отвечен ли уже этот вопрос
            answered_key = f"test_{config.test_type}_q{question.number}_answered"
            if dialog_manager.dialog_data.get(answered_key):
                logger.debug(f"Question {question.number} already answered, ignoring input")
                if current_state == expected_state:
                    if question.number < len(config.questions):
                        await dialog_manager.next()
                    else:
                        await dialog_manager.switch_to(config.states_group.completed)
                return
            
            # Проверяем завершение теста
            completion_pending = dialog_manager.dialog_data.get(f"test_{config.test_type}_completion_pending", False)
            completion_done = dialog_manager.dialog_data.get(f"test_{config.test_type}_completion_done", False)
            if completion_pending or completion_done:
                await dialog_manager.switch_to(config.states_group.completed)
                return
            
            # Сохраняем ответ
            saved = await test_engine.save_answer(dialog_manager, config, question.number, text.strip())
            
            if saved:
                # Отмечаем вопрос как отвеченный
                dialog_manager.dialog_data[answered_key] = True
                
                # Переходим к следующему вопросу или завершению
                if current_state == expected_state:
                    if question.number < len(config.questions):
                        await dialog_manager.next()
                    else:
                        await dialog_manager.switch_to(config.states_group.completed)
                else:
                    logger.debug(f"State changed during answer processing for {config.test_type} q{question.number}")
        
        return on_input
    
    @staticmethod
    def create_back_to_departments_handler():
        """Создание обработчика возврата к выбору отделов"""
        async def on_back_to_departments(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
            user_id = callback.from_user.id
            test_engine = get_test_engine()
            
            # Очищаем данные теста пользователя
            await test_engine.cleanup_user_test(user_id)
            
            # Возвращаемся к выбору отделов
            from bot.states import TestingDepartmentsSelectionSG
            await dialog_manager.start(TestingDepartmentsSelectionSG.selection, mode=StartMode.RESET_STACK)
        
        return on_back_to_departments
    
    @staticmethod
    def create_test_dialog(config: TestConfig) -> Dialog:
        """Создание полного диалога тестирования с новой архитектурой таймеров"""
        logger.info(f"Creating dialog for {config.test_type} test with {len(config.questions)} questions")
        
        windows = []
        
        # Создаем окна для каждого вопроса
        for question in config.questions:
            question_getter = UniversalTestDialogGeneratorV2.create_question_getter(config, question)
            timer_getter = UniversalTestDialogGeneratorV2.create_timer_getter(config, question)
            input_handler = UniversalTestDialogGeneratorV2.create_input_handler(config, question)
            
            # Создаем окно вопроса с таймером
            window = Window(
                Format(
                    "{test_icon} <b>{test_display_name} - Вопрос {question_number}/{total_questions}</b>\n\n"
                    "{question_text}\n\n"
                    "(Время на ответ: {time_limit} секунд)"
                ),
                # Отображение таймера
                Format("⏱️ Оставшееся время: {timer_minutes:02d}:{timer_seconds:02d}"),
                # Progress bar для визуального отображения
                Progress(
                    "timer_progress",
                    filled="🟩",
                    empty="⬜",
                    width=10
                ),
                # Поле ввода ответа
                TextInput(
                    id=f"{config.test_type}_q{question.number}_input",
                    on_success=input_handler
                ),
                state=getattr(config.states_group, f'q{question.number}'),
                getter=[question_getter, timer_getter]  # Комбинируем геттеры
            )
            
            windows.append(window)
        
        # Создаем окно завершения теста
        async def completion_getter(dialog_manager: DialogManager = None, **kwargs):
            if dialog_manager:
                test_engine = get_test_engine()
                
                # Завершаем тест при первом рендере окна
                done_key = f"test_{config.test_type}_completion_done"
                if not dialog_manager.dialog_data.get(done_key, False):
                    try:
                        await test_engine.complete_test(dialog_manager, config)
                        dialog_manager.dialog_data[done_key] = True
                        
                        # Снимаем флаг ожидания
                        pend_key = f"test_{config.test_type}_completion_pending"
                        dialog_manager.dialog_data.pop(pend_key, None)
                        
                    except Exception as e:
                        logger.error(f"Error completing test in completion window: {e}", exc_info=True)
            
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
                text="🏢 Вернуться к выбору отделов",
                id="back_to_departments",
                on_click=UniversalTestDialogGeneratorV2.create_back_to_departments_handler()
            ),
            state=config.states_group.completed,
            getter=completion_getter
        )
        
        windows.append(completion_window)
        
        # Создаем диалог
        dialog = Dialog(*windows, launch_mode=LaunchMode.SINGLE_TOP)
        
        logger.info(f"Created dialog for {config.test_type} with {len(windows)} windows")
        return dialog


def create_test_dialog(config: TestConfig) -> Dialog:
    """Обертка для создания диалога теста"""
    return UniversalTestDialogGeneratorV2.create_test_dialog(config)