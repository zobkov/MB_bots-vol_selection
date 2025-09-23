"""
Унифицированная система тестирования для Telegram бота отбора волонтеров
"""

from .models import TestQuestion, TestConfig, TestProgress, TimerData
from .test_engine import TestEngine, test_engine
from .test_engine_v2 import TestEngineV2, get_test_engine
from .enhanced_timer_utils import EnhancedTimerManager
from .enhanced_scheduler_timer_utils import (
    start_dialog_auto_update, 
    stop_dialog_auto_update,
    start_timer_background,
    stop_timer,
    get_timer_progress_data
)
# ИСПОЛЬЗУЕМ НОВУЮ СИСТЕМУ dialog_generator_v2 с timer_service_v2 и изолированными ключами BgManager
from .dialog_generator_v2 import UniversalTestDialogGeneratorV2, create_test_dialog
# Старая система остается для совместимости
from .dialog_generator import UniversalTestDialogGenerator
from .media_utils import MediaHandler, MEDIA_MESSAGE_IDS_KEY, MEDIA_SENT_KEY

__all__ = [
    'TestQuestion',
    'TestConfig', 
    'TestProgress',
    'TimerData',
    'TestEngine',
    'test_engine',
    'TestEngineV2',
    'get_test_engine',
    'EnhancedTimerManager',
    'start_dialog_auto_update',
    'stop_dialog_auto_update', 
    'start_timer_background',
    'stop_timer',
    'get_timer_progress_data',
    'UniversalTestDialogGenerator',
    'UniversalTestDialogGeneratorV2',
    'create_test_dialog',
    'MediaHandler',
    'MEDIA_MESSAGE_IDS_KEY',
    'MEDIA_SENT_KEY'
]