"""Aiogram Dialog definition for Stage 2 volunteer selection."""

from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window, StartMode
from aiogram_dialog.widgets.input import MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Row, Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from bot.states import MenuSG, Stage2SG
from .getters import get_stage2_main_data
from .handlers import (
    on_proceed_to_test,
    on_proceed_to_timer_warning,
    on_start_general_yes,
    on_start_general_no,
    on_stage2_dialog_close,
    on_q1_entered,
    on_q2_entered,
    on_q3_entered,
    on_video_proceed,
    on_wrong_content_type,
    on_vq1,
    on_vq2,
    on_vq3,
    on_vq4,
    on_vq5,
    on_start_media_proceed,
    on_media_equipment_yes,
    on_media_equipment_no,
    on_media_experience_entered,
    on_media_portfolio_entered,
)

_ALREADY_DONE_TEXT = (
    "✅ <b>Ты уже прошёл(-ла) второй этап отбора!</b>\n\n"
    "Спасибо за ответы — мы проверим их и сообщим результаты с <b>4 по 7 октября 2026</b>.\n\n"
    "По всем общим вопросам обращайся к Карине (@karrrishenka) и Даше (@drkirna).\n"
    "Если есть технические вопросы по боту, пиши Артему (@zobko)."
)

_NO_STAGE1_TEXT = (
    "⚠️ <b>Второй этап недоступен</b>\n\n"
    "Заявка первого этапа не найдена. Пожалуйста, сначала заполни анкету первого этапа или обратись к организаторам: @drkirna."
)

stage2_dialog = Dialog(

    # ── 1. MAIN / Guard ───────────────────────────────────────────────────────
    Window(
        Const(
            "👋 <b>Второй этап отбора волонтеров МБ 2026</b>\n\n"
            "Поздравляем с прохождением первого этапа! Впереди тебя ждут специальные задания отбора.",
            when="can_start"
        ),
        Const(_ALREADY_DONE_TEXT, when="already_completed"),
        Const(_NO_STAGE1_TEXT, when="no_stage1"),
        Button(
            Const("🚀 Начать 2-й этап"),
            id="btn_stage2_start",
            on_click=on_proceed_to_test,
            when="can_start",
        ),
        Start(
            Const("⬅️ В главное меню"),
            id="btn_stage2_back_menu",
            state=MenuSG.main,
            mode=StartMode.RESET_STACK,
        ),
        state=Stage2SG.MAIN,
        getter=get_stage2_main_data,
    ),

    # ── 2. INTRO GENERAL ──────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Задания второго этапа (Общий функционал)</b>\n\n"
            "Привет! Мы очень рады, что ты откликнулся(-сь) на волонтерство МБ’26!\n\n"
            "Внимательно прочитай инструкцию перед выполнением, так как тестирование непрерывное:\n"
            "• Тестирование состоит из <b>3 развернутых письменных вопросов</b> и <b>5 вопросов видеоинтервью</b>.\n"
            "• На выполнение всего этапа действует <b>общий таймер: 35 минут</b>.\n"
            "• Видеоинтервью записывается в формате <b>видео-кружочков</b> в Telegram (длительность до 1 мин).\n\n"
            "🚫 Мы не приветствуем использование ИИ и чтение с экрана. В случае использования посторонних материалов мы не учтем твой ответ ☹. Нам важно увидеть искренность и честность.\n\n"
            "Желаем удачи!"
        ),
        Button(
            Const("Далее ▶️"),
            id="btn_general_to_timer",
            on_click=on_proceed_to_timer_warning,
        ),
        SwitchTo(
            Const("⬅️ Назад"),
            id="btn_general_intro_back",
            state=Stage2SG.MAIN,
        ),
        state=Stage2SG.intro_general,
    ),

    # ── 3. TIMER WARNING ──────────────────────────────────────────────────────
    Window(
        Const(
            "⏱ <b>Внимание! Таймер тестирования</b>\n\n"
            "На выполнение всех заданий отводится <b>35 минут</b> с момента нажатия кнопки «Да, начать».\n\n"
            "Убедись, что у тебя есть достаточно свободного времени, стабильный интернет и возможность записать видео.\n\n"
            "Готов(-а) начать прямо сейчас?"
        ),
        Row(
            Button(Const("✅ Да, начать"), id="btn_timer_yes", on_click=on_start_general_yes),
            Button(Const("❌ Нет, позже"), id="btn_timer_no", on_click=on_start_general_no),
        ),
        state=Stage2SG.timer_warning,
    ),

    # ── 4. Q1 GENERAL ─────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Вопрос 1/3 (письменный)</b>\n\n"
            "Что ты знаешь о Конференции «Менеджмент Будущего»? "
            "(ответ должен содержать тему, даты проведения, треки Конференции и другую известную тебе информацию)."
        ),
        TextInput(id="stage2_q1_input", on_success=on_q1_entered),
        state=Stage2SG.q1_about_mb,
    ),

    # ── 5. Q2 GENERAL ─────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Вопрос 2/3 (письменный)</b>\n\n"
            "Почему ты хочешь стать волонтером именно на Менеджменте Будущего? "
            "Что Конференция может дать тебе?"
        ),
        TextInput(id="stage2_q2_input", on_success=on_q2_entered),
        state=Stage2SG.q2_motivation,
    ),

    # ── 6. Q3 GENERAL ─────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Вопрос 3/3 (письменный)</b>\n\n"
            "Как ты думаешь, что делает мероприятие действительно хорошо организованным?"
        ),
        TextInput(id="stage2_q3_input", on_success=on_q3_entered),
        state=Stage2SG.q3_well_organized,
    ),

    # ── 7. VIDEO INTRO ────────────────────────────────────────────────────────
    Window(
        Const(
            "🎉 <b>Супер! Ты ответил(-а) на все письменные вопросы.</b>\n\n"
            "Предлагаем перейти к части <b>видеоинтервью</b>.\n\n"
            "Тебе предстоит записать <b>5 видео-кружочков</b> (видеосообщений) длительностью до 1 минуты каждый.\n\n"
            "💡 <i>Совет: говори свободно и искренне, не читай заготовленный текст.</i>"
        ),
        Button(Const("🎥 Начать видеоинтервью"), id="btn_video_proceed", on_click=on_video_proceed),
        state=Stage2SG.video_intro,
    ),

    # ── 8. VQ1 ────────────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Видео-интервью 1/5</b>\n\n"
            "Расскажи о ситуации, когда ты сам(-а) заметил(-а) проблему и решил(-а) ее без поручения.\n\n"
            "🎥 Запиши и отправь <b>видео-кружок</b> (до 1 минуты)"
        ),
        MessageInput(on_vq1, content_types=[ContentType.VIDEO_NOTE]),
        MessageInput(on_wrong_content_type, content_types=[ContentType.ANY]),
        state=Stage2SG.vq1,
    ),

    # ── 9. VQ2 ────────────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Видео-интервью 2/5</b>\n\n"
            "Была ли у тебя ситуация, при которой тебе пришлось пожертвовать личным комфортом ради достижения командной цели/результата? Опиши такую ситуацию.\n\n"
            "🎥 Запиши и отправь <b>видео-кружок</b> (до 1 минуты)"
        ),
        MessageInput(on_vq2, content_types=[ContentType.VIDEO_NOTE]),
        MessageInput(on_wrong_content_type, content_types=[ContentType.ANY]),
        state=Stage2SG.vq2,
    ),

    # ── 10. VQ3 ───────────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Видео-интервью 3/5</b>\n\n"
            "Представь, что ты волонтер на конференции. До начала важной сессии 15 минут. Твой руководитель просит тебя проверить готовность зала, одновременно участник просит помочь найти нужную аудиторию, а спикер пишет, что ему срочно нужна помощь. Что ты будешь делать? Объясни свои действия по порядку.\n\n"
            "🎥 Запиши и отправь <b>видео-кружок</b> (до 1 минуты)"
        ),
        MessageInput(on_vq3, content_types=[ContentType.VIDEO_NOTE]),
        MessageInput(on_wrong_content_type, content_types=[ContentType.ANY]),
        state=Stage2SG.vq3,
    ),

    # ── 11. VQ4 ───────────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Видео-интервью 4/5</b>\n\n"
            "Что ты будешь делать, если тебе кажется, что руководитель принял неправильное решение?\n\n"
            "🎥 Запиши и отправь <b>видео-кружок</b> (до 1 минуты)"
        ),
        MessageInput(on_vq4, content_types=[ContentType.VIDEO_NOTE]),
        MessageInput(on_wrong_content_type, content_types=[ContentType.ANY]),
        state=Stage2SG.vq4,
    ),

    # ── 12. VQ5 ───────────────────────────────────────────────────────────────
    Window(
        Const(
            "<b>Видео-интервью 5/5</b>\n\n"
            "Расскажи о случае, когда тебе пришлось работать с человеком, который тебе не нравился. Как ты решал(-а) эту проблему?\n\n"
            "🎥 Запиши и отправь <b>видео-кружок</b> (до 1 минуты)"
        ),
        MessageInput(on_vq5, content_types=[ContentType.VIDEO_NOTE]),
        MessageInput(on_wrong_content_type, content_types=[ContentType.ANY]),
        state=Stage2SG.vq5,
    ),

    # ── 13. INTRO MEDIA ───────────────────────────────────────────────────────
    Window(
        Format(
            "📸 <b>Второй этап отбора (Медиа: {role_title})</b>\n\n"
            "Привет! Мы очень рады, что ты откликнулся(-сь) на волонтерство МБ’26!\n\n"
            "Мы возвращаемся с заданиями второго этапа отбора. Тебе предстоит ответить на 3 вопроса о твоем оборудовании и опыте съемок.\n\n"
            "Мы вернемся с результатами с <b>4 по 7 октября 2026</b>."
        ),
        Button(
            Const("Перейти к вопросам ▶️"),
            id="btn_media_proceed",
            on_click=on_start_media_proceed,
        ),
        Start(
            Const("⬅️ В главное меню"),
            id="btn_media_back_menu",
            state=MenuSG.main,
            mode=StartMode.RESET_STACK,
        ),
        state=Stage2SG.intro_media,
        getter=get_stage2_main_data,
    ),

    # ── 14. MEDIA Q1 (EQUIPMENT) ──────────────────────────────────────────────
    Window(
        Const("<b>Вопрос 1/3 (Медиа)</b>\n\nЕсть ли у тебя свое профессиональное оборудование?"),
        Row(
            Button(Const("Да"), id="btn_media_eq_yes", on_click=on_media_equipment_yes),
            Button(Const("Нет"), id="btn_media_eq_no", on_click=on_media_equipment_no),
        ),
        state=Stage2SG.media_q1_equipment,
    ),

    # ── 15. MEDIA Q2 (EXPERIENCE) ─────────────────────────────────────────────
    Window(
        Const(
            "<b>Вопрос 2/3 (Медиа)</b>\n\n"
            "Есть ли у тебя опыт фотографирования/видеосъемки профессиональных мероприятий (Конференций, Форумов)? "
            "Опиши подробно свой опыт."
        ),
        TextInput(id="media_exp_input", on_success=on_media_experience_entered),
        state=Stage2SG.media_q2_experience,
    ),

    # ── 16. MEDIA Q3 (PORTFOLIO) ──────────────────────────────────────────────
    Window(
        Const(
            "<b>Вопрос 3/3 (Медиа)</b>\n\n"
            "Если у тебя есть портфолио, прикрепи ссылку, пожалуйста (Google Диск, Яндекс.Диск, Behance и т.п.).\n\n"
            "<i>⚠️ Убедись, что доступ к файлам по ссылке открыт.</i>"
        ),
        TextInput(id="media_port_input", on_success=on_media_portfolio_entered),
        state=Stage2SG.media_q3_portfolio,
    ),

    # ── 17. SUCCESS ───────────────────────────────────────────────────────────
    Window(
        Const(
            "✅ <b>Спасибо за твои ответы!</b>\n\n"
            "Ты успешно завершил(-а) второй этап отбора волонтеров Конференции «Менеджмент Будущего 2026».\n\n"
            "📅 Мы вернемся с результатами с <b>4 по 7 октября 2026</b>.\n\n"
            "По всем общим вопросам обращайся к Карине (@karrrishenka) и Даше (@drkirna).\n"
            "Если не работает бот, пиши Артему (@zobko).\n\n"
            "Следи за новостями в нашем Telegram-канале: @managementfuture"
        ),
        Start(
            Const("🏠 Личный кабинет"),
            id="btn_stage2_to_menu",
            state=MenuSG.main,
            mode=StartMode.RESET_STACK,
        ),
        state=Stage2SG.success,
    ),

    on_close=on_stage2_dialog_close,
)
