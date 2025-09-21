# Telegram Bot для отбора волонтеров МБ 2025 - AI Coding Guidelines

## Architecture Overview

This is a **Telegram bot for volunteer selection** built with **aiogram 3.x + aiogram-dialog** for dialog-driven UI. The bot manages multi-stage volunteer applications with form validation, department ratings, and Google Sheets integration.

### Core Components
- **`bot/dialogs/`** - aiogram-dialog based UI flows (start, menu, application, departments)
- **`database/`** - SQLAlchemy models (User, Application) + repositories pattern
- **`config/`** - Configuration loading from ENV + JSON (`selection_config.json`)
- **`utils/`** - Google Sheets integration and logging setup

### Data Flow
1. **User registration** → `User` table with telegram_id
2. **Application flow** → Multi-stage dialog → `Application` table with department ratings
3. **State management** → Redis-backed FSM for dialog persistence
4. **Export** → Google Sheets integration for data export

## Key Patterns & Conventions

### Dialog Architecture (aiogram-dialog)
All user interactions use **aiogram-dialog** for structured conversational flows:

```python
# Pattern: State-driven dialogs with validation
from aiogram_dialog import Dialog, Window, DialogManager
from bot.states import ApplicationSG  # FSM states

# Dialog windows have validators for input
def email_check(text: str) -> str:
    if not re.match(email_pattern, text):
        raise ValueError("❌ Введите корректный email адрес")
    return text
```

**Critical**: When modifying dialogs, always update corresponding states in `bot/states/` and handle both normal flow + edit mode (`is_editing` flag in dialog_data).

#### Dialog Launch and Start Modes (aiogram-dialog)
Two important mode systems control dialog behavior:

**LaunchMode** - Controls dialog stack management when creating dialogs:
```python
from aiogram_dialog import Dialog, LaunchMode

dialog = Dialog(
    Window(...),
    launch_mode=LaunchMode.SINGLE_TOP,  # Dialog-level configuration
)
```

LaunchMode options:
- `LaunchMode.ROOT` - Always root dialog, resets stack (main menu)
- `LaunchMode.EXCLUSIVE` - Only single dialog allowed, prevents stacking (banners)
- `LaunchMode.SINGLE_TOP` - No duplicates on top, replaces itself (product pages)
- `LaunchMode.STANDARD` - No limitations (default)

**StartMode** - Controls stack behavior when starting dialogs:
```python
from aiogram_dialog import StartMode

# In dialog handlers
await dialog_manager.start(SomeStateSG.state, mode=StartMode.NORMAL)
```

StartMode options:
- `StartMode.NORMAL` - Default, continues current state (most common)
- `StartMode.RESET_STACK` - Clears existing stack, starts fresh
- `StartMode.NEW_STACK` - Creates new stack alongside current one

**Critical**: Use `StartMode.NORMAL` (not STANDARD) for regular dialog transitions. Use `StartMode.RESET_STACK` for main menu returns.

### Database Pattern
Uses **Repository pattern** with manual session management:

```python
# Always use repositories, not direct SQLAlchemy
user_repo = UserRepository(db)
app_repo = ApplicationRepository(db)

# Pattern: Manual session management (new API)
db: Database = dialog_manager.middleware_data.get("db")
if db:
    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        user = await user_repo.create_user(telegram_id, username)
        await session.commit()
    finally:
        await session.close()  # Always close explicitly

# OLD pattern (deprecated): async context manager
# async with db.session() as session:  # Don't use this anymore
```

**Critical**: The `async with db.session()` pattern is deprecated. Always use `db.get_session()` + manual `session.close()` for proper resource management.

### Configuration Management
**Dual configuration**: ENV vars for secrets + JSON for business logic:

```python
# config/config.py loads both:
# - .env for BOT_TOKEN, DB credentials, Redis, Google API keys
# - selection_config.json for stages, departments, support contacts
config = load_config()  # Returns unified Config object
```

**Important**: When adding new config options, decide if it's a secret (→ .env) or business logic (→ selection_config.json).

### Middleware Pattern
Custom middleware injection in `main.py`:

```python
# Pattern: Inject shared dependencies via middleware
async def config_middleware(handler, event, data):
    data["config"] = config
    data["db"] = db
    data["google_sheets_service"] = google_sheets_service
    return await handler(event, data)

# Access in handlers:
async def handler(callback: CallbackQuery, dialog_manager: DialogManager, db: Database, config: Config):
```

### Unified Testing System (NEW - Preferred Approach)
**Complete unified system** for all department testing with zero code duplication. Located in `bot/dialogs/unified_testing/` package.

#### Core Architecture Components

**Package Structure**:
```
bot/dialogs/unified_testing/
├── __init__.py          # Exports all components
├── models.py            # Data models (TestQuestion, TestConfig, etc.)
├── test_engine.py       # Core business logic (TestEngine singleton)
├── enhanced_timer_utils.py  # User-isolated timer management
├── dialog_generator.py  # Automatic aiogram-dialog creation
└── README.md           # Documentation
```

#### Implementation Pattern (Complete Example)

**1. Define Questions & Configuration** (`{department}_test_unified.py`):
```python
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import LogisticsTestSG

# Question definitions with time limits
LOGISTICS_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Вопрос о логистике 1...",
        time_limit=120,  # seconds
        correct_answer=None  # optional for validation
    ),
    TestQuestion(
        number=2,
        text="Вопрос о логистике 2...",
        time_limit=120
    ),
    # ... up to 6 questions
]

# Checkpoint callback function (optional)
async def save_logistics_checkpoint(dialog_manager):
    """Checkpoint функция для сохранения завершения тестирования логистики"""
    try:
        await save_department_completion_checkpoint_with_session(dialog_manager, "logistics")
        logger.info("Logistics test checkpoint saved successfully")
    except Exception as e:
        logger.error(f"Error saving logistics checkpoint: {e}", exc_info=True)

# Configuration object
LOGISTICS_CONFIG = TestConfig(
    test_type="logistics",          # Database identifier
    display_name="Логистика",       # Human-readable name
    icon="🔧",                     # Emoji for UI
    questions=LOGISTICS_QUESTIONS,
    states_group=LogisticsTestSG,   # aiogram FSM states
    checkpoint_callback=save_logistics_checkpoint  # optional
)

# Generate dialog (single line!)
logistics_test_dialog = create_test_dialog(LOGISTICS_CONFIG)
```

**2. States Group Definition** (`bot/states/`):
```python
from aiogram.fsm.state import State, StatesGroup

class LogisticsTestSG(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    completed = State()
```

#### Core Features & Benefits

**User-Isolated Timer System**:
- Timer keys: `user_{user_id}_{test_type}_q{question_number}`
- Zero conflicts between users and departments
- Automatic cleanup on completion/timeout
- Progress widgets with 2-second updates (prevents Telegram flood)

**Database Integration**:
- Automatic answer saving to `department_test_results` table
- Completion status tracking (`is_completed` field)
- Time tracking for each answer
- Checkpoint system integration

**Dialog Generation**:
- Automatic window creation for each question
- Built-in timer display with Progress widgets
- Completion window with navigation
- Error handling and validation

**Type Safety & Validation**:
- Dataclass models with full validation
- Runtime type checking
- Configuration validation

#### Technical Implementation Details

**Timer Management** (`EnhancedTimerManager`):
```python
# User-based timer isolation
self.user_timers: Dict[int, Dict[str, asyncio.Task]] = {}

# Timer key format for isolation
timer_key = f"user_{user_id}_{test_type}_q{question_number}"

# Progress calculation (countdown style: 100% → 0%)
progress = (remaining_time / total_duration) * 100
```

**Test Engine** (`TestEngine` singleton):
```python
# Answer saving with time tracking
async def save_answer(self, dialog_manager, config, question_number, answer_text):
    time_taken = self.timer_manager.calculate_time_taken(dialog_manager, timer_key)
    # Saves to department_test_results table

# Test completion with database update
async def complete_test(self, dialog_manager, config):
    await self._mark_test_completed(user_id, config.test_type)
    # Calls dept_repo.complete_test() for is_completed=True
```

**Dialog Generation** (`UniversalTestDialogGenerator`):
```python
# Question window with timer
Window(
    Format("{test_icon} <b>{test_display_name} - Вопрос {question_number}/{total_questions}</b>"),
    *timer_manager.create_timer_display(),
    TextInput(id=f"{test_type}_q{number}_input", on_success=input_handler),
    state=states_group.q{number},
    getter=[question_getter, timer_getter]
)
```

#### Migration Pattern for Existing Tests

1. **Create Unified Version**:
   ```python
   # Create {department}_test_unified.py
   from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
   ```

2. **Define Questions Array**:
   ```python
   DEPARTMENT_QUESTIONS = [
       TestQuestion(number=1, text="...", time_limit=120),
       # ... all questions
   ]
   ```

3. **Create Configuration**:
   ```python
   DEPARTMENT_CONFIG = TestConfig(
       test_type="department_name",
       display_name="Department Display Name", 
       icon="🏢",
       questions=DEPARTMENT_QUESTIONS,
       states_group=DepartmentTestSG,
       checkpoint_callback=save_department_checkpoint  # optional
   )
   ```

4. **Generate Dialog**:
   ```python
   department_test_dialog = create_test_dialog(DEPARTMENT_CONFIG)
   ```

5. **Update Imports** in `bot/dialogs/__init__.py`:
   ```python
   from .department_test_unified import department_test_dialog
   ```

#### Critical Technical Requirements

**Database Session Management**:
```python
# ALWAYS use new session API, not deprecated context manager
db: Database = dialog_manager.middleware_data.get("db")
session = await db.get_session()
try:
    # Repository operations
    dept_repo = DepartmentTestRepository(session)
    await dept_repo.complete_test(user.id, test_type)
    await session.commit()
finally:
    await session.close()  # Explicit cleanup required
```

**Timer State Checking**:
```python
# Prevent duplicate timer launches
if (dialog_manager and hasattr(dialog_manager, 'current_context')):
    current_state = dialog_manager.current_context().state
    expected_state = getattr(config.states_group, f'q{question.number}')
    if current_state == expected_state and not timer_already_started:
        await start_timer()
```

**Progress Widget Configuration**:
```python
# Countdown display (100% → 0% for intuitive countdown)
Progress(
    "timer_progress",
    filled="🟩",     # Green filled blocks
    empty="⬜",       # White empty blocks  
    width=10         # Total blocks
)
```

#### Error Handling & Debugging

**Logging Integration**:
```python
logger = logging.getLogger(__name__)
logger.debug(f"Starting timer for {test_type} question {question_number}")
logger.info(f"Test completed: {test_type} for user {user_id}")
logger.error(f"Timer error: {e}", exc_info=True)
```

**Completion Verification**:
```python
# completion_getter ensures database update on first render
async def completion_getter(dialog_manager=None, **kwargs):
    test_completed_key = f"test_{config.test_type}_completed"
    if not dialog_manager.dialog_data.get(test_completed_key, False):
        await test_engine.complete_test(dialog_manager, config)
        dialog_manager.dialog_data[test_completed_key] = True
```

#### Dependencies & Requirements

**Required Imports for Unified Tests**:
```python
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog
from bot.dialogs.checkpoint_utils import save_department_completion_checkpoint_with_session
from bot.states import {Department}TestSG
import logging
```

**Database Schema Requirements**:
- `department_test_results` table with `is_completed` field
- User-based foreign keys for answer tracking
- Timestamp fields for completion tracking

**State Management**:
- FSM states: `q1`, `q2`, ..., `q6`, `completed`
- Dialog data persistence across question transitions
- Cleanup on dialog exit or completion

### APScheduler Timer System (NEW - Current Approach)
**Production-ready timer system** with Redis persistence for reliability across bot restarts. Located in `utils/scheduler_utils.py` and `bot/dialogs/unified_testing/enhanced_scheduler_timer_utils.py`.

#### Core Architecture Components

**APScheduler + Redis JobStore**:
```python
# Redis-backed job persistence
from utils.scheduler_utils import APSchedulerTimerManager, TimerConfig
from bot.dialogs.unified_testing.enhanced_scheduler_timer_utils import (
    APSchedulerEnhancedTimerManager, start_timer_background, stop_timer
)

# Timer configuration with full context
timer_config = TimerConfig(
    user_id=user.id,
    chat_id=chat_id,
    test_type="logistics",
    question_number=1,
    time_limit=120,  # seconds
    bot_token=bot_token
)

# Start persistent timer
job_id = await scheduler.start_question_timer(timer_config)
```

#### Key Features & Benefits

**Redis Persistence**:
- Timers survive bot restarts and crashes
- JobStore in Redis DB 1 (separate from FSM)
- Automatic job recovery on startup
- Graceful shutdown with job cleanup

**User-Isolated Timer Management**:
- Timer keys: `user_{user_id}_{test_type}_q{question_number}`
- Zero conflicts between users and departments  
- Automatic timeout handling with bot notifications
- Progress widgets with 2-second updates

**Integration Pattern**:
```python
# In question getters - compatibility with old system
async def get_logistics_q1_data(dialog_manager: DialogManager = None, **kwargs):
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        if state == LogisticsTestSG.q1:
            timer_key = f"user_{user_id}_logistics_q1"
            await start_timer_background(dialog_manager, timer_key, 120)
    
    return {"question_text": QUESTIONS[1]["text"]}

# In input handlers - automatic timer cleanup
async def on_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    timer_key = f"user_{user_id}_logistics_q1"
    await stop_timer(dialog_manager, timer_key)
    # ... save answer and proceed
```

#### Technical Implementation Details

**Scheduler Configuration** (`config.py`):
```python
@dataclass
class SchedulerConfig:
    enabled: bool = True
    timezone: str = "UTC"
    misfire_grace_time: int = 30  # seconds
    max_instances: int = 3
    coalesce: bool = True

@dataclass  
class RedisConfig:
    jobstore_db: int = 1  # APScheduler jobs database
```

**Main.py Integration**:
```python
# Initialize APScheduler with Redis jobstore
from utils.scheduler_utils import init_scheduler_manager, shutdown_scheduler_manager

redis_config = {
    'host': config.redis.host,
    'port': config.redis.port, 
    'password': config.redis.password,
    'jobstore_db': config.redis.jobstore_db
}
scheduler_manager = await init_scheduler_manager(redis_config)

# Graceful shutdown
await shutdown_scheduler_manager()
```

**Timeout Handling**:
```python
# Automatic timeout notifications via bot
async def _handle_question_timeout(config: TimerConfig):
    bot = Bot(token=config.bot_token)
    await bot.send_message(
        chat_id=config.chat_id,
        text=f"⏰ Время на вопрос {config.question_number} истекло..."
    )
    # Optional: custom timeout callback execution
```

#### Migration from Legacy Timer System

**Backward Compatibility**:
- All existing timer functions work unchanged
- `start_timer_background()`, `stop_timer()`, `get_timer_progress_data()` 
- Automatic migration on startup via `migrate_old_timers_to_scheduler()`

**Critical Differences**:
- **Persistence**: Jobs survive restarts (vs asyncio tasks)
- **Isolation**: User-based job IDs prevent conflicts
- **Monitoring**: APScheduler event listeners for job tracking
- **Error Handling**: Misfire grace periods and job coalescing

#### Dependencies & Configuration

**Required Environment Variables**:
```env
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=UTC
SCHEDULER_MISFIRE_GRACE_TIME=30
SCHEDULER_MAX_INSTANCES=3
REDIS_JOBSTORE_DB=1
```

**Required Imports for Timer Usage**:
```python
from bot.dialogs.unified_testing.enhanced_scheduler_timer_utils import (
    start_timer_background, stop_timer, get_timer_progress_data
)
```

### Legacy Timer System (Deprecated - Do Not Use)
**Old approach** - asyncio-based timers without persistence. **Replaced by APScheduler system above.**

The old `enhanced_timer_utils.py` used asyncio tasks which don't survive bot restarts:

```python
# OLD PATTERN (deprecated) - Do not use
from bot.dialogs.timer_utils import start_timer_background, stop_timer
```

**Migration Status**: All unified tests should use APScheduler. Any remaining asyncio timer code should be migrated.

## Development Workflows

### Database Migrations
```bash
# Create migration after model changes
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Environment Setup
```bash
# Use provided scripts
./start.sh          # Full setup + run (checks Redis, applies migrations)
./restart.sh        # Quick restart
./monitor.sh        # Background monitoring

# Manual database operations
alembic revision --autogenerate -m "description"
alembic upgrade head

# Testing unified system
python3 test_unified_logistics.py     # Test specific department
python3 test_unified_all.py           # Test all unified dialogs
python3 test_unified_system_unit.py   # Unit tests with pytest
```

### Testing Strategy
- **Unified system tests**: `test_unified_*.py` files test the new unified testing architecture
- **Unit tests**: `test_unified_system_unit.py` for isolated component testing with pytest
- **Integration tests**: `test_integration.py` for full bot workflows
- **Feature tests**: Individual files like `test_anketa_update.py`, `test_user_creation.py` for specific features
- **Configuration tests**: `test_unified_logistics.py` validates unified testing configs

### Logging Convention
Use structured logging with dedicated loggers:

```python
# Pattern: Module-specific loggers
logger = logging.getLogger(__name__)

# Centralized error logging
from utils.logging_config import log_error, log_user_action
log_error(e, "Context description")
log_user_action(user_id, "action_type", details)
```

## Critical Dependencies

### External Services
- **PostgreSQL** - Primary data store
- **Redis** - FSM state storage (2-day TTL)
- **Google Sheets API** - Optional export integration

### Key Libraries
- **aiogram 3.x** - Telegram Bot API wrapper
- **aiogram-dialog 2.x** - Dialog framework (NOT compatible with v1.x)
- **SQLAlchemy 2.x** - ORM with async support
- **Alembic** - Database migrations

## Common Gotchas

### Dialog State Management
- Dialog data persists in `dialog_manager.dialog_data`
- Always check `is_editing` mode when handling input
- Use `dialog_manager.start()` for dialog transitions, not direct state switches

### Department Rating System
- All 5 departments must be rated (1-5) before application completion
- Department selection dialog saves to dialog_data, not database directly
- Final save happens in application review step

### Error Handling
- Dialog errors go through `dialog_error_handler.py`
- Use validators in TextInput widgets, not try-catch in handlers
- Always provide user-friendly error messages in Russian

### Google Sheets Integration
- Service can be disabled via `GOOGLE_ENABLE_DRIVE=false`
- Drive integration is optional (folder uploads)
- Always check `google_sheets_service` exists before using