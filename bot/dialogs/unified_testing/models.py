"""
Модели данных для унифицированной системы тестирования
"""
from dataclasses import dataclass
from typing import List, Optional, Callable, Any
from aiogram.fsm.state import StatesGroup


@dataclass
class TestQuestion:
    """Модель вопроса теста"""
    number: int
    text: str
    time_limit: int  # секунды
    correct_answer: Optional[str] = None
    
    def __post_init__(self):
        """Валидация данных"""
        if self.number <= 0:
            raise ValueError("Question number must be positive")
        if self.time_limit <= 0:
            raise ValueError("Time limit must be positive")
        if not self.text.strip():
            raise ValueError("Question text cannot be empty")


@dataclass
class TestConfig:
    """Конфигурация теста"""
    test_type: str  # 'logistics', 'pr', 'marketing', etc.
    display_name: str  # "Логистика", "PR", etc.
    icon: str  # "🔧", "📰", etc.
    questions: List[TestQuestion]
    states_group: StatesGroup
    checkpoint_callback: Optional[Callable] = None
    
    def __post_init__(self):
        """Валидация конфигурации"""
        if not self.test_type:
            raise ValueError("Test type cannot be empty")
        if not self.questions:
            raise ValueError("Questions list cannot be empty")
        if not self.states_group:
            raise ValueError("States group is required")
            
        # Проверяем, что номера вопросов последовательны
        expected_numbers = list(range(1, len(self.questions) + 1))
        actual_numbers = [q.number for q in self.questions]
        if actual_numbers != expected_numbers:
            raise ValueError(f"Question numbers must be sequential 1-{len(self.questions)}, got {actual_numbers}")


@dataclass
class TestProgress:
    """Состояние прогресса теста"""
    user_id: int
    test_type: str
    current_question: int
    total_questions: int
    is_completed: bool = False
    is_started: bool = False
    answers: dict = None  # question_number -> answer_text
    
    def __post_init__(self):
        if self.answers is None:
            self.answers = {}
    
    @property
    def completion_percentage(self) -> float:
        """Процент завершения теста"""
        if self.total_questions == 0:
            return 0.0
        return (len(self.answers) / self.total_questions) * 100
    
    @property
    def questions_left(self) -> int:
        """Количество оставшихся вопросов"""
        return self.total_questions - len(self.answers)


@dataclass  
class TimerData:
    """Данные активного таймера"""
    timer_key: str
    user_id: int
    test_type: str
    question_number: int
    duration: int
    start_time: float
    is_active: bool = True
    
    @property
    def full_timer_key(self) -> str:
        """Полный ключ таймера с user_id"""
        return f"user_{self.user_id}_{self.test_type}_q{self.question_number}"