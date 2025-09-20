# Унифицированная система тестирования

## Обзор

Современная система тестирования для Telegram бота отбора волонтеров с нулевым дублированием кода между отделами.

## Ключевые особенности

✅ **DRY принцип**: Один код для всех тестов  
✅ **User-изоляция**: `user_{user_id}_{test_type}_q{question}` ключи таймеров  
✅ **Progress виджеты**: Современные обратные отсчеты  
✅ **Автосохранение**: Встроенная persistence в БД  
✅ **Type-safe**: Полная валидация через dataclasses  

## Быстрый старт

```python
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog

# 1. Определяем вопросы
questions = [
    TestQuestion(1, "Текст вопроса", 60, "правильный_ответ"),
    TestQuestion(2, "Еще вопрос", 90)
]

# 2. Создаем конфигурацию
config = TestConfig(
    test_type="new_department",
    display_name="Новый отдел",
    icon="🆕",
    questions=questions,
    states_group=NewDepartmentTestSG,
    checkpoint_callback=save_new_department_checkpoint
)

# 3. Генерируем диалог (одна строка!)
new_department_dialog = create_test_dialog(config)
```

## Архитектура

### Компоненты
- **TestEngine**: Основной движок тестирования
- **EnhancedTimerManager**: User-based изоляция таймеров  
- **UniversalTestDialogGenerator**: Автогенерация aiogram-dialog
- **TestQuestion/TestConfig**: Type-safe модели данных

### Схема работы
1. **Конфигурация** → Описание теста в dataclasses
2. **Генерация** → Автоматическое создание диалога  
3. **Выполнение** → User-изолированные таймеры + Progress UI
4. **Сохранение** → Автоматический checkpoint после теста

## Миграция с legacy

```python
# Старый подход (НЕ используйте)
from bot.dialogs.logistics_test import logistics_test_dialog

# Новый подход (ИСПОЛЬЗУЙТЕ)  
from bot.dialogs.logistics_test_unified import logistics_test_dialog
```

Просто замените импорт в `bot/dialogs/__init__.py`!

## Файловая структура

```
bot/dialogs/unified_testing/
├── __init__.py              # Экспорты
├── models.py                # TestQuestion, TestConfig, etc.
├── test_engine.py           # Основной движок
├── enhanced_timer_utils.py  # User-based таймеры
└── dialog_generator.py      # Автогенерация диалогов

# Примеры использования
logistics_test_unified.py    # Логистика на новой системе
test_unified_logistics.py    # Тесты системы
```

## API Reference

### TestQuestion
```python
@dataclass
class TestQuestion:
    number: int              # Номер вопроса (1, 2, 3...)
    text: str               # Текст вопроса
    time_limit: int         # Лимит времени в секундах  
    correct_answer: str     # Правильный ответ (опционально)
```

### TestConfig  
```python
@dataclass
class TestConfig:
    test_type: str          # "logistics", "pr", etc.
    display_name: str       # "Логистика", "PR", etc.
    icon: str              # "🔧", "📰", etc.
    questions: List[TestQuestion]
    states_group: StatesGroup
    checkpoint_callback: Callable  # Опционально
```

## Преимущества vs Legacy

| Аспект | Legacy | Unified |
|--------|--------|---------|
| Дублирование кода | 5+ файлов | 1 система |  
| Изоляция пользователей | ❌ | ✅ user_* ключи |
| Progress UI | Текст | Progress виджеты |
| Валидация | Ручная | Type-safe |
| Добавление тестов | Копирование | Конфигурация |
| Поддержка | 5+ файлов | 1 место |

## Тестирование

```bash
# Тесты конфигурации
python3 test_unified_logistics.py

# Unit тесты (планируется)  
python3 test_unified_system_unit.py

# Интеграционное тестирование
python3 main.py  # → Telegram бот
```

## Производительность

- **Таймеры**: User-изоляция предотвращает конфликты
- **Память**: Автоочистка неактивных таймеров
- **UI**: 2-секундные обновления (оптимизация Telegram flood control)
- **БД**: Эффективное сохранение через repositories

## Roadmap

- [ ] Миграция всех отделов на unified систему
- [ ] Расширенные метрики тестирования  
- [ ] A/B тестирование вопросов
- [ ] Адаптивные лимиты времени
- [ ] Визуализация результатов

---

Создано командой разработки vol_selection_MB_bot • 2025