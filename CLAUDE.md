# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Telegram bot (Russian-language, `aiogram` 3.x + `aiogram-dialog`) that runs the volunteer selection process for the "Менеджмент Будущего" (MB) 2026 conference. Two selection stages:

- **Stage 1** — a form (`bot/dialogs/application.py`): full name, email, phone, faculty, course, availability, role, motivation, experience. Saved to Postgres and exported to Google Sheets.
- **Stage 2** — a timed test (`bot/dialogs/stage2/`): 3 written questions + up to 5 video-circle ("video note") answers for general volunteers, or 3 questions for photo/video media volunteers. Governed by a background timer service.

Everything is in Russian, including user-facing strings, log messages, and code comments — keep new user-facing text and comments consistent with that.

## Commands

```bash
poetry install                       # install dependencies
poetry run python main.py            # run the bot (long polling)
./start.sh                           # same, plus .env check, Redis check/start, alembic upgrade
poetry run alembic revision --autogenerate -m "description"   # new migration
poetry run alembic upgrade head      # apply migrations
```

There is no test suite and no linter/formatter configured in this repo.

Requires Postgres and Redis running locally (see `.env.example` for connection vars; `DB_*`, `REDIS_*`, `BOT_TOKEN`, `ADMIN_IDS`, optional `GOOGLE_*`, `STAGE2_PREVIEW`).

Production deploy is via `restart.sh` (`git pull` + `systemctl restart mb_vol_select_bot`, a systemd service — not Docker). `update.sh`/`monitor.sh` reference a `docker-compose.prod.yml` that does not exist in this repo; treat them as stale/unused rather than the real deployment path.

## Architecture

**Entry point** `main.py` wires everything together: loads `Config`, connects Redis (FSM storage) and Postgres, creates the `Bot`/`Dispatcher`, registers a `config_middleware` closure that injects `config`, `db`, `bot`, `google_sheets_service` into every handler's data dict, registers `router` + all dialog routers, calls `setup_dialogs(dp)` and hands the resulting `BgManagerFactory` to `services/stage2_timer.py` (needed so background timers can push dialog transitions from outside a request context), and registers `dialog_error_handler`.

**Config** (`config/config.py`) merges two sources into one `Config` dataclass: environment variables (`.env`, secrets/connection info) and `config/selection_config.json` (stage deadlines, support contacts, departments — non-secret, editable without a deploy). Note: there is also a stale top-level `selection_config.json` in the repo root — the live one loaded at runtime is `config/selection_config.json`. `config.stage2_preview` (env `STAGE2_PREVIEW`) hides Stage 2 from non-admins in the main menu while still allowing admins to see/test it (`bot/dialogs/menu.py`).

**FSM states** (`bot/states/__init__.py`) define one `StatesGroup` per dialog: `StartSG`, `MenuSG`, `ApplicationSG`, `ViewUserSG` (admin user inspector), `Stage2SG`, `Stage2ReviewSG` (admin review of Stage 2 submissions). Each dialog module under `bot/dialogs/` follows the aiogram-dialog convention of windows + getters (data providers) + handlers (button/input callbacks), assembled into a `Dialog(...)` router exported from `bot/dialogs/__init__.py` and included in `main.py`.

**Database** (`database/`): `models.py` defines `User`, `Application` (Stage 1), `Stage2Application` (Stage 2, one row per user, `role_type` = `general`|`media`, video answers stored as Telegram `file_id` strings, `is_completed`/`reviewed` flags). `db.py` wraps an async SQLAlchemy engine/sessionmaker; `Database.create_tables()` uses `Base.metadata.create_all` at startup (migrations under `alembic/` are the source of truth for schema changes — keep both in sync). `repositories.py` holds `UserRepository`, `ApplicationRepository`, `Stage2Repository` — all DB access goes through these, not raw queries in dialogs/handlers. `ApplicationRepository` also pushes new submissions to Google Sheets when the service is configured.

**Stage 2 timer** (`services/stage2_timer.py`) is a module-level, in-memory (not persisted) timer scheduler keyed by `user_id`, using `asyncio.TimerHandle`s stored in a global dict. Two modes, switchable at runtime by admins:
- `basic`: one countdown for the whole stage, with proportional warning notifications, then a grace period, then forced completion.
- `ind` (default): a separate countdown per question (written questions get no grace period; video questions get a grace period to allow upload time), auto-advancing the user's dialog window via `_NEXT_QUESTION_MAP` when time runs out.

Because timers fire in the background outside any request, expiry callbacks build their own `Database`/`Config`/`BgManagerFactory`-based session to update the DB and push the user to the next dialog state — this is the one place in the codebase that talks to Postgres and aiogram-dialog outside the normal handler/getter flow. State (`_timer_mode`, durations, active timers) resets on process restart.

**Admin commands** (`bot/handlers.py`, gated by `check_is_admin` against `config.admin_ids`): `/sub_status`, `/view_user`, `/stage2_review` (`/vol_review`), `/basic_timer_duration`, `/timer_type`, `/ind_timer_duration`, `/delete_application`. These are the primary tools for testing/tuning Stage 2 timing without redeploying (e.g. `/basic_timer_duration 60`, `/timer_type ind`). `/delete_application <user> <1|2|all>` resets a user's Stage 1 and/or Stage 2 data for re-testing the flow end-to-end.

**Logging** (`utils/logging_config.py`): rotating file handlers under `logs/` (`bot.log`, `database.log`, `errors.log`, `user_actions.log`) plus console output; helpers `log_error`, `log_db_operation`, `log_user_action`, `log_user_debug` are used throughout instead of calling `logging` directly — prefer them for consistency with existing log parsing/monitoring.

**Emojis** (`utils/emojis.py`): user-facing text uses custom Telegram premium emoji (`<tg-emoji>` tags via the `emoji()`/`num_emoji()` helpers), not plain Unicode — use these helpers rather than hardcoding emoji characters in new dialog text.

**Google Sheets** (`utils/google_services.py`, wired in `main.py` via `setup_google_sheets_service`): optional integration, only active when `GOOGLE_CREDENTIALS_PATH` + `GOOGLE_SPREADSHEET_ID` are set; the bot must keep working with it disabled (`google_sheets_service` can be `None` everywhere it's used).

**Archive** (`archive/`): frozen code from the 2025 campaign, kept for reference only — not imported or run by the current bot.
