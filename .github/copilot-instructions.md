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
**Modern, unified system** for all department testing with zero code duplication:

```python
# Pattern: Configuration-driven test creation
from bot.dialogs.unified_testing import TestQuestion, TestConfig, create_test_dialog

# 1. Define questions
LOGISTICS_QUESTIONS = [
    TestQuestion(
        number=1,
        text="Question text here",
        time_limit=60,
        correct_answer="optional_answer"  # for validation
    ),
    # ... more questions
]

# 2. Create test configuration
LOGISTICS_CONFIG = TestConfig(
    test_type="logistics",
    display_name="Логистика",
    icon="🔧",
    questions=LOGISTICS_QUESTIONS,
    states_group=LogisticsTestSG,
    checkpoint_callback=save_logistics_checkpoint  # optional
)

# 3. Generate dialog (one line!)
logistics_test_dialog = create_test_dialog(LOGISTICS_CONFIG)
```

**Key Features**:
- **User-isolated timers**: `user_{user_id}_{test_type}_q{question}` keys prevent conflicts
- **Progress widgets**: Modern aiogram-dialog Progress with countdown display  
- **Automatic DB saving**: Built-in answer persistence with timeout handling
- **Zero duplication**: Single codebase for all department tests
- **Type safety**: Full dataclass validation and error handling

**Migration Pattern**:
1. Create new `{department}_test_unified.py` using TestConfig pattern
2. Update import in `bot/dialogs/__init__.py` to point to unified version
3. Test thoroughly before removing old version
4. All functionality preserved: timers, checkpoints, state management

**Timer System Architecture**:
- **EnhancedTimerManager**: User-based timer isolation and management
- **TestEngine**: Core business logic for test flow and DB operations
- **DialogGenerator**: Automatic aiogram-dialog creation from config
- **Progress Integration**: Real-time countdown with 2-second updates

### Legacy Timer System (Deprecated)
**Old approach** - still works but avoid for new tests:
**Modern approach** with getter-based timer launching and state checking:

```python
# Pattern: Getter-based timer launching with state validation
from bot.dialogs.timer_utils import start_timer_background, stop_timer, get_timer_progress_data

async def get_department_q1_data(dialog_manager: DialogManager = None, **kwargs):
    logger.debug(f"get_department_q1_data called with dialog_manager: {dialog_manager}")
    
    # Launch timer only if we're in the correct state
    if dialog_manager and hasattr(dialog_manager, 'current_context'):
        state = dialog_manager.current_context().state
        logger.debug(f"Current state: {state}")
        if state == DepartmentTestSG.q1:
            logger.debug("Starting timer for department_q1")
            await start_timer_background(dialog_manager, "department_q1", 120)
    
    return {"question_text": QUESTIONS[1]["text"]}

# Window configuration without on_process_result
Window(
    Format("🏢 <b>Department - Question 1/6</b>\n\n{question_text}\n\n(Time: 120 seconds)"),
    *create_timer_display("department_q1"),
    TextInput(id="q1_input", on_success=on_q1_input),
    state=DepartmentTestSG.q1,
    getter=[get_department_q1_data, get_timer_progress_data("department_q1")],
)

# Debug logging in input handlers
async def on_q1_input(message: Message, widget, dialog_manager: DialogManager, text: str):
    logger.debug(f"on_q1_input called with text: {text}")
    await save_answer_and_proceed(dialog_manager, 1, text)

# Timer cleanup in save functions
async def save_answer_and_proceed(dialog_manager: DialogManager, question_num: int, answer: str):
    logger.debug(f"save_answer_and_proceed called with question_num: {question_num}")
    try:
        timer_key = f"department_q{question_num}"
        await stop_timer(dialog_manager, timer_key)  # New API
        # ... rest of logic
```

**Critical Timer Rules**:
- **State checking prevents duplicate timers**: Always check `dialog_manager.current_context().state` before launching
- **2-second update intervals**: Optimized to avoid Telegram flood control (no more 1s updates)
- **Countdown progress**: Progress goes from 100% → 0% for intuitive countdown display
- **Database session API**: Use `db.get_session()` + manual `session.close()`, not `async with db.session()`
- **No on_process_result**: Timer launching moved to getter functions for better control
- **Comprehensive debug logging**: Track timer launches, state transitions, and function calls

**Migration pattern** from old timer_manager system:
1. Update imports: `timer_manager` → `start_timer_background, stop_timer`
2. Enhance getters with state checking and timer launching
3. Add debug logging to input handlers and save functions
4. Remove old `start_*_timer_q*` functions and `on_process_result` references
5. Update `stop_timer(dialog_manager, timer_key)` calls

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
```

### Testing Strategy
- **Unit tests**: `test_unit/` for isolated logic
- **Integration tests**: `test_integration.py` for full flows
- **Feature tests**: `test_anketa_update.py`, `test_user_creation.py` for specific features

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