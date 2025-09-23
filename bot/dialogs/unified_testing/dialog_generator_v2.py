"""
Обновленный генератор диалогов для новой архитектуры таймеров
Использует BgManager для плавного обновления UI
"""

import asyncio
import logging
import uuid
from typing import List, Callable, Any, Dict

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager, LaunchMode, StartMode
from aiogram_dialog.widgets.text import Format, Progress
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Start

from .test_engine_v2 import perform_transition

from .models import TestConfig, TestQuestion
from .test_engine_v2 import get_test_engine

logger = logging.getLogger(__name__)


class UniversalTestDialogGeneratorV2:
    """
    Обновленный генератор диалогов для унифицированной системы тестирования
    Использует новую архитектуру таймеров с BgManager
    """
    
    @staticmethod
    async def cancel_state_tasks(config: TestConfig, question: TestQuestion, dialog_manager: DialogManager):
        """
        Отмена всех фоновых задач для вопроса (monitor + timers)
        КРИТИЧЕСКИ ВАЖНО вызывать перед переходом к следующему состоянию
        """
        try:
            # 1. Отмена монитор таска
            task_key = f"monitor_task_{config.test_type}_q{question.number}"
            monitor_task = dialog_manager.dialog_data.pop(task_key, None)
            
            # Инвалидируем monitor_id чтобы старые мониторы стали stale
            monitor_id_key = f"monitor_id_{config.test_type}_q{question.number}"
            old_monitor_id = dialog_manager.dialog_data.pop(monitor_id_key, None)
            
            if monitor_task and not monitor_task.done():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
                logger.info(f"🗑️ Cancelled monitor task for {config.test_type} q{question.number} (id: {old_monitor_id})")
            
            # 2. Останавливаем таймер
            timer_key = f"timer_{config.test_type}_q{question.number}_started"
            dialog_manager.dialog_data[timer_key] = False
            
            # 3. Отменяем APScheduler job если есть
            job_id_key = f"aps_job_{config.test_type}_q{question.number}"
            job_id = dialog_manager.dialog_data.pop(job_id_key, None)
            if job_id:
                try:
                    from .timer_service_v2 import get_dialog_timer_service
                    timer_service = get_dialog_timer_service()
                    await timer_service.cancel_timer(job_id)
                    logger.info(f"🗑️ Cancelled APScheduler job {job_id}")
                except Exception as e:
                    logger.exception(f"Failed to cancel APScheduler job {job_id}: {e}")
            
            logger.info(f"✅ All state tasks cancelled for {config.test_type} q{question.number}")
            
        except Exception as e:
            logger.error(f"Error cancelling state tasks for {config.test_type} q{question.number}: {e}", exc_info=True)
    
    @staticmethod
    async def perform_transition(dialog_manager: DialogManager, config: TestConfig, current_question: TestQuestion, next_question_number: int):
        """
        Централизованная функция перехода между состояниями (НОВАЯ ВЕРСИЯ)
        Использует seq версионирование и отмену фоновых задач
        """
        # Используем новую централизованную функцию
        await perform_transition(dialog_manager, config, current_question.number, next_question_number)
    
    @staticmethod
    def create_question_getter(config: TestConfig, question: TestQuestion):
        """Создание геттера данных для вопроса"""
        async def question_getter(dialog_manager: DialogManager = None, **kwargs):
            if not dialog_manager:
                return {}
            
            test_engine = get_test_engine()
            user_id = dialog_manager.event.from_user.id
            
            # Проверяем текущее состояние диалога
            current_state = dialog_manager.current_context().state
            expected_state = getattr(config.states_group, f'q{question.number}')
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: если состояние заблокировано, не позволяем изменения
            state_lock_key = f"state_lock_{config.test_type}"
            is_state_locked = dialog_manager.dialog_data.get(state_lock_key, False)
            
            if is_state_locked:
                logger.warning(f"🔒 STATE IS LOCKED for {config.test_type} - preventing state changes")
                # Если состояние заблокировано, возвращаем данные без изменения состояния
                return {
                    "question_text": f"⏳ Обработка перехода... ({question.text})",
                    "question_number": question.number,
                    "total_questions": len(config.questions),
                    "time_limit": question.time_limit,
                    "test_display_name": config.display_name,
                    "test_icon": config.icon
                }
            
            # Если мы не в ожидаемом состоянии для этого вопроса
            if current_state != expected_state:
                logger.warning(f"🔍 State mismatch in getter for {config.test_type} q{question.number}: current={current_state}, expected={expected_state}")
                
                # Проверяем блокировку - если вопрос уже отвечен, не возвращаемся к нему
                answered_key = f"test_{config.test_type}_q{question.number}_answered"
                if dialog_manager.dialog_data.get(answered_key):
                    logger.info(f"🚫 Question {config.test_type} q{question.number} already answered, not showing")
                    # Находим правильный следующий вопрос
                    for q_num in range(question.number + 1, len(config.questions) + 1):
                        next_answered_key = f"test_{config.test_type}_q{q_num}_answered"
                        if not dialog_manager.dialog_data.get(next_answered_key):
                            next_state = getattr(config.states_group, f'q{q_num}')
                            await dialog_manager.switch_to(next_state)
                            logger.info(f"🔧 Redirected to unanswered {config.test_type} q{q_num}")
                            break
                    else:
                        # Все вопросы отвечены - переходим к завершению
                        await dialog_manager.switch_to(config.states_group.completed)
                        logger.info(f"🔧 All questions answered, redirected to completion")
            
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
                                
                                # ВРЕМЕННО ОТКЛЮЧЕНО ДЛЯ ТЕСТИРОВАНИЯ
                                # UniversalTestDialogGeneratorV2.create_state_monitor_task(config, question, dialog_manager)
                                logger.info(f"🔍 State monitor DISABLED for testing {config.test_type} q{question.number}")
                                
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
            # ИЗОЛИРОВАННЫЕ КЛЮЧИ ДЛЯ КАЖДОГО ВОПРОСА - ИСПРАВЛЕНИЕ BgManager КОНФЛИКТА
            timer_key_prefix = f"timer_{config.test_type}_q{question.number}"
            
            # Данные по умолчанию (будут обновляться через BgManager)
            default_data = {
                f"{timer_key_prefix}_minutes": 3 if question.time_limit >= 180 else question.time_limit // 60,  
                f"{timer_key_prefix}_seconds": 0,
                f"{timer_key_prefix}_remaining": question.time_limit,
                f"{timer_key_prefix}_progress": 100.0,
                f"{timer_key_prefix}_active": True,
                f"{timer_key_prefix}_status": "starting"
            }
            
            # Финальные данные для UI (с короткими именами для совместимости)
            ui_data = {
                "timer_minutes": default_data[f"{timer_key_prefix}_minutes"],
                "timer_seconds": default_data[f"{timer_key_prefix}_seconds"],
                "remaining_time": default_data[f"{timer_key_prefix}_remaining"],
                "progress_percent": default_data[f"{timer_key_prefix}_progress"],
                "timer_progress": default_data[f"{timer_key_prefix}_progress"],
                "is_timer_active": default_data[f"{timer_key_prefix}_active"],
                "timer_status": default_data[f"{timer_key_prefix}_status"]
            }
            
            # Логируем первые несколько вызовов
            user_id = None
            if dialog_manager and hasattr(dialog_manager, 'event') and getattr(dialog_manager, 'event', None):
                user_id = dialog_manager.event.from_user.id
                call_count_key = f"timer_{config.test_type}_q{question.number}_getter_calls"
                call_count = dialog_manager.dialog_data.get(call_count_key, 0) + 1
                dialog_manager.dialog_data[call_count_key] = call_count
                
                if call_count <= 5:  # Логируем первые 5 вызовов
                    logger.info(f"🎯 timer_getter call #{call_count} for user {user_id}, {config.test_type} q{question.number}")
                    logger.debug(f"📋 dialog_data keys: {list(dialog_manager.dialog_data.keys())}")
                    
                    # Проверяем, есть ли обновленные данные от BgManager для ЭТОГО вопроса
                    if f"{timer_key_prefix}_minutes" in dialog_manager.dialog_data:
                        bg_data = {
                            "timer_minutes": dialog_manager.dialog_data.get(f"{timer_key_prefix}_minutes", ui_data["timer_minutes"]),
                            "timer_seconds": dialog_manager.dialog_data.get(f"{timer_key_prefix}_seconds", ui_data["timer_seconds"]),
                            "remaining_time": dialog_manager.dialog_data.get(f"{timer_key_prefix}_remaining", ui_data["remaining_time"]),
                            "progress_percent": dialog_manager.dialog_data.get(f"{timer_key_prefix}_progress", ui_data["progress_percent"]),
                            "timer_progress": dialog_manager.dialog_data.get(f"{timer_key_prefix}_progress", ui_data["timer_progress"]),
                            "is_timer_active": dialog_manager.dialog_data.get(f"{timer_key_prefix}_active", ui_data["is_timer_active"]),
                            "timer_status": dialog_manager.dialog_data.get(f"{timer_key_prefix}_status", ui_data["timer_status"])
                        }
                        logger.info(f"🔄 Found isolated BgManager data for q{question.number}: {bg_data}")
                        
                        # 🚨 ЛОГИРУЕМ ФИНАЛЬНЫЕ ДАННЫЕ ДЛЯ UI БОТА 🚨
                        logger.error(f"🎭 FINAL UI DATA for {config.test_type} q{question.number}: {bg_data['timer_minutes']:02d}:{bg_data['timer_seconds']:02d} (remaining: {bg_data['remaining_time']:.1f}s, progress: {bg_data['timer_progress']:.1f}%, active: {bg_data['is_timer_active']}, status: {bg_data['timer_status']})")
                        
                        return bg_data
                    else:
                        logger.warning(f"⚠️ No isolated BgManager timer data found for q{question.number}, using defaults: {ui_data}")
                        
                        # 🚨 ЛОГИРУЕМ ДЕФОЛТНЫЕ ДАННЫЕ ДЛЯ UI БОТА 🚨
                        logger.error(f"🎭 FINAL UI DATA (DEFAULT) for {config.test_type} q{question.number}: {ui_data['timer_minutes']:02d}:{ui_data['timer_seconds']:02d} (remaining: {ui_data['remaining_time']:.1f}s, progress: {ui_data['timer_progress']:.1f}%, active: {ui_data['is_timer_active']}, status: {ui_data['timer_status']})")
            
            # Если нет логирования, все равно проверяем изолированные данные
            if dialog_manager and f"{timer_key_prefix}_minutes" in dialog_manager.dialog_data:
                # 🚫 STATIC TIMER: BgManager updates disabled due to state corruption
                # Show static timer based on question duration instead of live updates
                duration = question.time_limit
                static_minutes = duration // 60
                static_seconds = duration % 60
                
                final_data = {
                    "timer_minutes": static_minutes,
                    "timer_seconds": static_seconds,
                    "remaining_time": float(duration),
                    "progress_percent": 100.0,
                    "timer_progress": 100.0,
                    "is_timer_active": True,
                    "timer_status": "static_display"
                }
                
                if user_id:
                    call_count_key = f"timer_{config.test_type}_q{question.number}_getter_calls"
                    call_count = dialog_manager.dialog_data.get(call_count_key, 0)
                    if call_count > 5:  # Для вызовов после 5-го
                        logger.error(f"🎭 FINAL UI DATA (STATIC) for {config.test_type} q{question.number}: {final_data['timer_minutes']:02d}:{final_data['timer_seconds']:02d} (remaining: {final_data['remaining_time']:.1f}s, progress: {final_data['timer_progress']:.1f}%, active: {final_data['is_timer_active']}, status: {final_data['timer_status']})")
                
                return final_data
            
            # Дефолтные данные только если нет изолированных BgManager данных
            logger.error(f"🎭 FINAL UI DATA (DEFAULT) for {config.test_type} q{question.number}: {ui_data['timer_minutes']:02d}:{ui_data['timer_seconds']:02d} (remaining: {ui_data['remaining_time']:.1f}s, progress: {ui_data['timer_progress']:.1f}%, active: {ui_data['is_timer_active']}, status: {ui_data['timer_status']})")
            return ui_data
        
        return timer_getter
    
    @staticmethod
    def create_state_monitor_task(config: TestConfig, question: TestQuestion, dialog_manager: DialogManager):
        """
        Создание задачи мониторинга состояния с версионированием и защитой от race conditions
        """
        # Генерируем уникальный ID для этого монитора
        monitor_id = str(uuid.uuid4())
        monitor_key = f"monitor_id_{config.test_type}_q{question.number}"
        task_key = f"monitor_task_{config.test_type}_q{question.number}"
        
        # Сохраняем ID текущего монитора
        dialog_manager.dialog_data[monitor_key] = monitor_id
        
        logger.info(f"🔍 MONITOR CREATED [{monitor_id}]: {config.test_type} q{question.number}")
        
        async def monitor_state():
            await asyncio.sleep(2.0)  # Ждем 2 секунды после запуска таймера
            
            try:
                # STALE CHECK: если наш monitor_id уже не актуален - выходим
                current_monitor_id = dialog_manager.dialog_data.get(monitor_key)
                if current_monitor_id != monitor_id:
                    logger.debug(f"🗑️ MONITOR STALE [{monitor_id}]: current_id={current_monitor_id}, exiting")
                    return
                
                # Проверяем, что таймер еще активен
                timer_key = f"timer_{config.test_type}_q{question.number}_started"
                if not dialog_manager.dialog_data.get(timer_key, False):
                    logger.debug(f"🛑 MONITOR EXIT [{monitor_id}]: timer not active")
                    return
                
                # Защита: если вопрос помечен как answered/blocked - не откатывать
                answered_key = f"test_{config.test_type}_q{question.number}_answered"
                block_key = f"block_{config.test_type}_q{question.number}"
                if dialog_manager.dialog_data.get(answered_key) or dialog_manager.dialog_data.get(block_key):
                    logger.debug(f"🚫 MONITOR EXIT [{monitor_id}]: question answered/blocked")
                    return
                
                # Проверяем состояние блокировки
                state_lock_key = f"state_lock_{config.test_type}"
                is_locked = dialog_manager.dialog_data.get(state_lock_key, False)
                if is_locked:
                    logger.debug(f"🔒 MONITOR EXIT [{monitor_id}]: state locked")
                    return
                
                # Наконец - только если всё ещё нужно, делаем переключение
                current_state = dialog_manager.current_context().state
                expected_state = getattr(config.states_group, f'q{question.number}')
                
                if current_state != expected_state:
                    logger.warning(f"🚨 MONITOR DRIFT DETECTED [{monitor_id}]: current={current_state}, expected={expected_state}")
                    logger.warning(f"🔧 MONITOR FORCING SWITCH [{monitor_id}]: {current_state} → {expected_state}")
                    await dialog_manager.switch_to(expected_state)
                    
                    # Проверяем результат коррекции
                    await asyncio.sleep(0.1)
                    corrected_state = dialog_manager.current_context().state
                    if corrected_state == expected_state:
                        logger.info(f"✅ MONITOR CORRECTION SUCCESS [{monitor_id}]")
                    else:
                        logger.error(f"🚨 MONITOR CORRECTION FAILED [{monitor_id}]: {corrected_state}")
                else:
                    logger.info(f"✅ MONITOR STABLE [{monitor_id}]: state correct")
                    
            except Exception as e:
                logger.error(f"💥 MONITOR ERROR [{monitor_id}]: {e}", exc_info=True)
        
        # Создаем и сохраняем задачу
        task = asyncio.create_task(monitor_state())
        dialog_manager.dialog_data[task_key] = task
        
        logger.debug(f"� Monitor task created and saved for {config.test_type} q{question.number}")
        
        return monitor_state
    
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
            
            logger.info(f"📝 Input received for {config.test_type} q{question.number}: '{text.strip()}' (current_state={current_state}, expected={expected_state})")
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: если состояние заблокировано, игнорируем ввод
            state_lock_key = f"state_lock_{config.test_type}"
            is_state_locked = dialog_manager.dialog_data.get(state_lock_key, False)
            
            if is_state_locked:
                logger.warning(f"🔒 Input ignored: state is locked for {config.test_type}")
                return
            
            # Проверяем блокировку возврата к этому вопросу
            block_key = f"block_{config.test_type}_q{question.number}"
            if dialog_manager.dialog_data.get(block_key):
                logger.warning(f"🚫 Input blocked for already completed {config.test_type} q{question.number}")
                # Принудительно переходим к следующему доступному вопросу
                next_question = test_engine.get_next_question_number(config, question.number)
                if next_question != -1:
                    next_state = getattr(config.states_group, f'q{next_question}')
                    await dialog_manager.switch_to(next_state)
                    logger.info(f"🔧 Redirected to {config.test_type} q{next_question}")
                else:
                    await dialog_manager.switch_to(config.states_group.completed)
                    logger.info(f"🔧 Redirected to {config.test_type} completion")
                return
            
            # Проверяем, не отвечен ли уже этот вопрос
            answered_key = f"test_{config.test_type}_q{question.number}_answered"
            if dialog_manager.dialog_data.get(answered_key):
                logger.debug(f"Question {question.number} already answered, ignoring input")
                if current_state == expected_state:
                    # Определяем следующий вопрос
                    next_question = test_engine.get_next_question_number(config, question.number)
                    if next_question != -1:
                        # Есть следующий вопрос - переходим к нему
                        next_state = getattr(config.states_group, f'q{next_question}')
                        await dialog_manager.switch_to(next_state)
                        logger.info(f"Already answered: {config.test_type} q{question.number} → q{next_question}")
                    else:
                        # Тест завершен - переходим к completed
                        await dialog_manager.switch_to(config.states_group.completed)
                        logger.info(f"Already answered: {config.test_type} q{question.number} → completed")
                return
            
            # Проверяем завершение теста
            completion_pending = dialog_manager.dialog_data.get(f"test_{config.test_type}_completion_pending", False)
            completion_done = dialog_manager.dialog_data.get(f"test_{config.test_type}_completion_done", False)
            if completion_pending or completion_done:
                await perform_transition(dialog_manager, config, question.number, -1)
                return
            
            # Сохраняем ответ
            saved = await test_engine.save_answer(dialog_manager, config, question.number, text.strip())
            
            if saved:
                # Останавливаем таймер для текущего вопроса (НОВАЯ СИСТЕМА с изолированными ключами)
                timer_key = f"timer_{user_id}_{config.test_type}_q{question.number}"
                from .timer_service_v2 import get_dialog_timer_service
                timer_service = get_dialog_timer_service()
                await timer_service.cancel_timer(timer_key)
                logger.info(f"⏹️ Timer stopped (V2) for {config.test_type} q{question.number}")
                
                # Отмечаем вопрос как отвеченный
                dialog_manager.dialog_data[answered_key] = True
                
                # Блокируем возможность возврата к этому вопросу
                block_key = f"block_{config.test_type}_q{question.number}"
                dialog_manager.dialog_data[block_key] = True
                logger.debug(f"🚫 Blocked return to {config.test_type} q{question.number}")
                
                # Устанавливаем СТРОГУЮ блокировку состояния
                state_lock_key = f"state_lock_{config.test_type}"
                dialog_manager.dialog_data[state_lock_key] = True
                dialog_manager.dialog_data[f"locked_from_q{question.number}"] = True
                logger.info(f"🔒 STATE LOCKED during transition from {config.test_type} q{question.number}")
                
                # Определяем следующий вопрос
                next_question = test_engine.get_next_question_number(config, question.number)
                
                # Логируем состояние для отладки
                logger.info(f"🔍 State check for {config.test_type} q{question.number}: current={current_state}, expected={expected_state}, match={current_state == expected_state}")
                
                # Переходим к следующему вопросу или завершению
                if current_state == expected_state:
                    if next_question != -1:
                        # Есть следующий вопрос - используем централизованный переход
                        logger.info(f"🔄 Transitioning: {config.test_type} q{question.number} → q{next_question}")
                        await perform_transition(dialog_manager, config, question.number, next_question)
                        logger.info(f"✅ Transition completed: {config.test_type} q{question.number} → q{next_question}")
                    else:
                        # Завершение теста - используем централизованный переход
                        logger.info(f"� Test completion: {config.test_type} q{question.number} → completed")
                        await perform_transition(dialog_manager, config, question.number, -1)
                                logger.info(f"✅ Retry successful: {config.test_type} q{question.number} → q{next_question}")
                            else:
                                logger.error(f"� CRITICAL: Retry failed for {config.test_type}: expected {next_state}, got {final_state}")
                    else:
                        # Тест завершен - переходим к completed
                        logger.info(f"🏁 Test completed: {config.test_type} q{question.number} → completed")
                        await dialog_manager.switch_to(config.states_group.completed)
                        
                        # Синхронная проверка завершения
                        await asyncio.sleep(0.1)
                        actual_state = dialog_manager.current_context().state
                        if actual_state == config.states_group.completed:
                            logger.info(f"✅ Completion verified: {config.test_type} → completed")
                            dialog_manager.dialog_data[state_lock_key] = False
                            logger.info(f"🔓 STATE UNLOCKED after completion")
                        else:
                            logger.warning(f"🚨 Completion failed: expected {config.states_group.completed}, got {actual_state}")
                else:
                    logger.warning(f"🚨 State mismatch for {config.test_type} q{question.number}: current={current_state} != expected={expected_state}")
                    # Принудительно переходим к следующему вопросу или завершению
                    if next_question != -1:
                        next_state = getattr(config.states_group, f'q{next_question}')
                        logger.info(f"🔧 Force transition: {config.test_type} q{question.number} → q{next_question}")
                        await dialog_manager.switch_to(next_state)
                        
                        # Проверка принудительного перехода
                        await asyncio.sleep(0.1)
                        actual_state = dialog_manager.current_context().state
                        if actual_state == next_state:
                            dialog_manager.dialog_data[state_lock_key] = False
                            logger.info(f"✅ Force transition successful: {config.test_type} → q{next_question}")
                        else:
                            logger.error(f"🚨 Force transition failed: expected {next_state}, got {actual_state}")
                    else:
                        logger.info(f"🔧 Force completion: {config.test_type} q{question.number} → completed")
                        await dialog_manager.switch_to(config.states_group.completed)
                        
                        # Проверка принудительного завершения
                        await asyncio.sleep(0.1)
                        actual_state = dialog_manager.current_context().state
                        if actual_state == config.states_group.completed:
                            dialog_manager.dialog_data[state_lock_key] = False
                            logger.info(f"✅ Force completion successful: {config.test_type}")
                        else:
                            logger.error(f"🚨 Force completion failed: expected {config.states_group.completed}, got {actual_state}")
        
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