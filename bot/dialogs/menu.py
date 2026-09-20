import logging
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from bot.states import MenuSG, ApplicationSG, Stage2SG
from config.config import Config
from database.db import Database
from database.repositories import UserRepository, ApplicationRepository, Stage2Repository
from utils.emojis import emoji

logger = logging.getLogger(__name__)


async def get_menu_data(dialog_manager: DialogManager, **kwargs):
    """Геттер данных для главного меню"""
    db: Database = dialog_manager.middleware_data.get("db")
    config: Config = dialog_manager.middleware_data.get("config")
    user = dialog_manager.event.from_user

    is_submitted = False
    is_stage2_completed = False

    if db and user:
        session = await db.get_session()
        try:
            user_repo = UserRepository(session)
            app_repo = ApplicationRepository(session)
            stage2_repo = Stage2Repository(session)

            db_user = await user_repo.get_or_create_user(
                telegram_id=user.id,
                telegram_username=user.username
            )

            # Проверяем статус в users или реальное наличие анкеты в таблице applications
            latest_app = await app_repo.get_latest_application_by_user_id(db_user.id)
            is_submitted = (db_user.status == "submitted") or (latest_app is not None)

            # Если анкета есть в БД, синхронизируем статус пользователя
            if latest_app and db_user.status != "submitted":
                await user_repo.update_status(db_user.telegram_id, "submitted")

            if is_submitted:
                stage2_app = await stage2_repo.get_by_user_id(db_user.id)
                if stage2_app:
                    if stage2_app.is_completed:
                        is_stage2_completed = True
                    elif stage2_app.role_type == "general":
                        is_stage2_completed = bool(
                            stage2_app.vq1_file_id
                            and stage2_app.vq2_file_id
                            and stage2_app.vq3_file_id
                            and stage2_app.vq4_file_id
                            and stage2_app.vq5_file_id
                        )
                    else:
                        is_stage2_completed = bool(stage2_app.media_portfolio or stage2_app.media_experience)
        finally:
            await session.close()

    is_admin = bool(config and user and user.id in config.admin_ids)
    stage2_preview = bool(config and config.stage2_preview)

    logger.info(
        "[MENU_GETTER] user=%s id=%s is_submitted=%s is_stage2_completed=%s can_start_stage2=%s is_admin=%s stage2_preview=%s",
        user.id if user else None,
        db_user.id if 'db_user' in locals() else None,
        is_submitted,
        is_stage2_completed,
        is_submitted and not is_stage2_completed,
        is_admin,
        stage2_preview,
    )

    # Не-админы в режиме превью видят старое меню без 2-го этапа
    if stage2_preview and not is_admin:
        stage1_status_text = "<b>Заявка подана</b>" if is_submitted else "<b>Заявка не подана</b>"
        menu_text = (
            f'{emoji("🌍")} <b>Личный кабинет кандидата в команду волонтеров МБ</b>\n\n'
            f'{emoji("arrow_right")}  Сбор заявок открыт до <b>21 сентября 23:59</b>\n\n'
            f'📝 Статус заявки: {stage1_status_text}'
        )
        return {
            "menu_text": menu_text,
            "is_submitted": is_submitted,
            "not_submitted": not is_submitted,
            "can_start_stage2": False,
            "stage2_completed": False,
        }

    stage1_status_text = f"<b>{emoji('✅')}  Заявка подана</b>" if is_submitted else f"<b>{emoji('❌')} Заявка не подана</b>"

    if is_stage2_completed:
        stage2_status_text = f"<b>{emoji('✅', 'orange')}  Пройден</b>"
    elif is_submitted:
        stage2_status_text = f"<b>{emoji('fire', 'orange')}  Доступен для прохождения</b>"
    else:
        stage2_status_text = f"<b>{emoji('cross', 'orange')} Недоступен</b>"

    menu_text = (
        f'{emoji("🌍")} <b>Личный кабинет кандидата в команду волонтеров МБ 2026</b>\n\n'
        f'<b>1-й этап (Анкета):</b> {stage1_status_text}\n'
        f'<b>2-й этап (Тестирование):</b> {stage2_status_text}\n\n'
        f'{emoji("🕐")} Результаты отбора будут объявлены <b>4–7 октября 2026</b>.'
    )

    return {
        "menu_text": menu_text,
        "is_submitted": is_submitted,
        "not_submitted": not is_submitted,
        "can_start_stage2": is_submitted and not is_stage2_completed,
        "stage2_completed": is_stage2_completed,
    }


menu_dialog = Dialog(
    Window(
        Format("{menu_text}"),
        Start(
            Const("📝 Заполнить анкету (1-й этап)"),
            id="start_app_from_menu",
            state=ApplicationSG.full_name,
            when="not_submitted"
        ),
        Start(
            Const("➡️ 2-й этап"),
            id="start_stage2_from_menu",
            state=Stage2SG.MAIN,
            when="can_start_stage2"
        ),
        SwitchTo(
            Const("📞 Поддержка"),
            id="to_support",
            state=MenuSG.support
        ),
        state=MenuSG.main,
        getter=get_menu_data,
    ),
    Window(
        Const(
            "📞 <b>Контакты для связи:</b>\n\n"
            f"{emoji("arrow_right")}  По всем вопросам обращайся в наш чат поддержки: @mbconf_support.\n\n"
            f"{emoji("arrow_right")}  Технические вопросы: Артем (@zobko)\n\n"
            f"{emoji("arrow_right")}  Официальный канал: @managementfuture"
        ),
        SwitchTo(
            Const("🔙 Назад"),
            id="back_to_menu",
            state=MenuSG.main
        ),
        state=MenuSG.support,
    ),
)

