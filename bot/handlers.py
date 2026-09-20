from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from bot.states import StartSG, ApplicationSG, MenuSG, ViewUserSG, Stage2SG, Stage2ReviewSG
from config.config import Config
from database.repositories import UserRepository
from database.db import Database
from services.stage2_timer import get_stage2_duration_sec, set_stage2_duration_sec, format_duration, cancel_user_timer
from utils.logging_config import log_user_action

router = Router()


def check_is_admin(user_id: int, config: Config | None) -> bool:
    """Check if user_id is in config.admin_ids"""
    if not config or not config.admin_ids:
        return False
    return user_id in config.admin_ids


@router.message(Command("start", "menu"))
async def cmd_start_or_menu(message: Message, dialog_manager: DialogManager):
    """Единый обработчик команд /start и /menu с проверкой статуса заявки"""
    # Сбрасываем таймер этапа 2 при выходе в меню /start
    cancel_user_timer(message.from_user.id)

    db: Database = dialog_manager.middleware_data.get("db")
    is_submitted = False
    
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            from database.repositories import ApplicationRepository
            app_repo = ApplicationRepository(session)
            db_user = await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
            )
            latest_app = await app_repo.get_latest_application_by_user_id(db_user.id)
            is_submitted = (db_user.status == "submitted") or (latest_app is not None)
            if latest_app and db_user.status != "submitted":
                await user_repo.update_status(db_user.telegram_id, "submitted")
        finally:
            await session.close()
    
    if is_submitted:
        await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)
    else:
        await dialog_manager.start(StartSG.welcome, mode=StartMode.RESET_STACK)


@router.message(Command("apply"))
async def cmd_apply(message: Message, dialog_manager: DialogManager):
    """Прямой запуск анкеты по команде /apply"""
    cancel_user_timer(message.from_user.id)
    db: Database = dialog_manager.middleware_data.get("db")
    
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
            )
        finally:
            await session.close()
    
    await dialog_manager.start(ApplicationSG.full_name, mode=StartMode.RESET_STACK)


@router.message(Command("stage2"))
async def cmd_stage2(message: Message, dialog_manager: DialogManager):
    """Прямой запуск 2-го этапа по команде /stage2"""
    db: Database = dialog_manager.middleware_data.get("db")
    if db:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            await user_repo.get_or_create_user(
                telegram_id=message.from_user.id,
                telegram_username=message.from_user.username
            )
        finally:
            await session.close()

    await dialog_manager.start(Stage2SG.MAIN, mode=StartMode.RESET_STACK)


# ============================================================================
# АДМИНИСТРАТИВНЫЕ КОМАНДЫ (проверка прав)
# ============================================================================

@router.message(Command("sub_status"))
async def cmd_sub_status(message: Message, command: CommandObject, dialog_manager: DialogManager):
    """
    Команда дебага для изменения статуса пользователя:
    /sub_status [user_id|telegram_username] 1/0
    1 — 'submitted', 0 или 2 — 'registered'
    """
    config: Config | None = dialog_manager.middleware_data.get("config")
    if not check_is_admin(message.from_user.id, config):
        await message.answer("⛔️ <b>Доступ запрещен.</b> У вас нет прав администратора.")
        return

    args = command.args.split() if command.args else []
    if len(args) < 2:
        await message.answer(
            "❌ <b>Использование:</b> <code>/sub_status [user_id|telegram_username] [1/0]</code>\n\n"
            "• <code>1</code> — 'submitted' (заявка подана)\n"
            "• <code>0</code> или <code>2</code> — 'registered' (зарегистрирован, заявка не подана)\n\n"
            "<i>Пример:</i> <code>/sub_status 123456789 1</code> или <code>/sub_status @username 0</code>"
        )
        return

    target_query = args[0]
    status_flag = args[1].lower()

    if status_flag in ("1", "submitted"):
        new_status = "submitted"
    elif status_flag in ("0", "2", "registered"):
        new_status = "registered"
    else:
        await message.answer("❌ Неверный статус. Используйте <code>1</code> (submitted) или <code>0</code> (registered).")
        return

    db: Database = dialog_manager.middleware_data.get("db")
    if not db:
        await message.answer("❌ База данных недоступна.")
        return

    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        user = await user_repo.find_user(target_query)
        if not user:
            await message.answer(f"❌ Пользователь <code>{target_query}</code> не найден в базе данных.")
            return

        old_status = user.status
        await user_repo.update_status(user.telegram_id, new_status)

        username = message.from_user.username or f"{message.from_user.first_name or ''}".strip()
        log_user_action(
            message.from_user.id,
            username,
            "ADMIN_CHANGE_STATUS",
            f"Target: {user.telegram_id} (@{user.telegram_username}), Old: {old_status}, New: {new_status}"
        )

        user_display = f"@{user.telegram_username}" if user.telegram_username else f"ID: <code>{user.telegram_id}</code>"
        await message.answer(
            f"✅ Статус пользователя <b>{user_display}</b> (Telegram ID: <code>{user.telegram_id}</code>, DB ID: <code>{user.id}</code>) "
            f"успешно изменен:\n"
            f"<code>{old_status}</code> ➔ <b>{new_status}</b>"
        )
    finally:
        await session.close()


@router.message(Command("view_user"))
async def cmd_view_user(message: Message, command: CommandObject, dialog_manager: DialogManager):
    """
    Команда дебага для просмотра информации и анкеты пользователя:
    /view_user [user_id|telegram_username]
    """
    config: Config | None = dialog_manager.middleware_data.get("config")
    if not check_is_admin(message.from_user.id, config):
        await message.answer("⛔️ <b>Доступ запрещен.</b> У вас нет прав администратора.")
        return

    args = command.args.split() if command.args else []
    if len(args) < 1:
        await message.answer(
            "❌ <b>Использование:</b> <code>/view_user [user_id|telegram_username]</code>\n\n"
            "<i>Пример:</i> <code>/view_user 123456789</code> или <code>/view_user @username</code>"
        )
        return

    target_query = args[0]
    db: Database = dialog_manager.middleware_data.get("db")
    if not db:
        await message.answer("❌ База данных недоступна.")
        return

    session = await db.get_session()
    try:
        user_repo = UserRepository(session)
        user = await user_repo.find_user(target_query)
        if not user:
            await message.answer(f"❌ Пользователь <code>{target_query}</code> не найден в базе данных.")
            return

        username = message.from_user.username or f"{message.from_user.first_name or ''}".strip()
        log_user_action(
            message.from_user.id,
            username,
            "ADMIN_VIEW_USER",
            f"Viewed user {user.telegram_id} (@{user.telegram_username})"
        )

        await dialog_manager.start(
            ViewUserSG.user_info,
            data={"target_user_id": user.id, "app_page": 0},
            mode=StartMode.RESET_STACK
        )
    finally:
        await session.close()


@router.message(Command("stage2_review", "vol_review"))
async def cmd_stage2_review(message: Message, dialog_manager: DialogManager):
    """
    Команда для администраторов:
    /stage2_review или /vol_review — открывает постраничный просмотр заявок 2-го этапа.
    """
    config: Config | None = dialog_manager.middleware_data.get("config")
    if not check_is_admin(message.from_user.id, config):
        await message.answer("⛔️ <b>Доступ запрещен.</b> У вас нет прав администратора.")
        return

    username = message.from_user.username or f"{message.from_user.first_name or ''}".strip()
    log_user_action(
        message.from_user.id,
        username,
        "ADMIN_STAGE2_REVIEW",
        f"Admin opened Stage 2 review"
    )

    await dialog_manager.start(Stage2ReviewSG.PAGE_SELECT, mode=StartMode.RESET_STACK)


@router.message(Command("basic_timer_duration"))
async def cmd_basic_timer_duration(message: Message, command: CommandObject, dialog_manager: DialogManager):
    """
    Команда тестирования и настройки общего таймера 2-го этапа:
    /basic_timer_duration [sec]
    """
    config: Config | None = dialog_manager.middleware_data.get("config")
    if not check_is_admin(message.from_user.id, config):
        await message.answer("⛔️ <b>Доступ запрещен.</b> У вас нет прав администратора.")
        return

    current_sec = get_stage2_duration_sec()
    args = command.args.strip() if command.args else ""

    if not args:
        half_sec = current_sec // 2
        last_sec = int(current_sec * 0.8)
        await message.answer(
            f"⏱ <b>Текущая длительность таймера 2-го этапа:</b>\n"
            f"<b>{current_sec} сек.</b> ({format_duration(current_sec)})\n\n"
            f"🔔 <b>Тайминги оповещений:</b>\n"
            f"• ⏳ 50% времени: через {half_sec} сек. (останется {format_duration(current_sec - half_sec)})\n"
            f"• ⚠️ 20% времени (осталось): через {last_sec} сек. (останется {format_duration(current_sec - last_sec)})\n"
            f"• ⏰ Окончание времени: через {current_sec} сек.\n\n"
            f"<b>Как изменить:</b> <code>/basic_timer_duration [секунды]</code>\n"
            f"<i>Пример для теста:</i> <code>/basic_timer_duration 60</code>\n"
            f"<i>По умолчанию:</i> <code>/basic_timer_duration 2100</code> (35 минут)"
        )
        return

    if not args.isdigit() or int(args) < 5:
        await message.answer(
            "❌ Пожалуйста, укажите целое число секунд (минимум 5 секунд).\n"
            "<i>Пример:</i> <code>/basic_timer_duration 60</code>"
        )
        return

    new_sec = int(args)
    set_stage2_duration_sec(new_sec)

    username = message.from_user.username or f"{message.from_user.first_name or ''}".strip()
    log_user_action(
        message.from_user.id,
        username,
        "ADMIN_SET_TIMER",
        f"Timer duration set to {new_sec}s"
    )

    half_sec = new_sec // 2
    last_sec = int(new_sec * 0.8)
    await message.answer(
        f"✅ <b>Длительность таймера 2-го этапа успешно установлена!</b>\n\n"
        f"⏱ <b>Новое время:</b> {new_sec} сек. ({format_duration(new_sec)})\n\n"
        f"🔔 <b>Оповещения будут приходить пропорционально:</b>\n"
        f"1. ⏳ 50% времени — через <b>{half_sec} сек.</b>\n"
        f"2. ⚠️ 20% осталось — через <b>{last_sec} сек.</b>\n"
        f"3. ⏰ 100% времени (таймаут) — через <b>{new_sec} сек.</b>"
    )




