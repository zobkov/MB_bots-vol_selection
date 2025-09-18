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
Uses **Repository pattern** instead of direct ORM:

```python
# Always use repositories, not direct SQLAlchemy
user_repo = UserRepository(db)
app_repo = ApplicationRepository(db)

# Pattern: Create/update through repositories
await user_repo.create_user(telegram_id, username)
await app_repo.save_application(user_id, application_data)
```

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