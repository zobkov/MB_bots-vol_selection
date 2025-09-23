from aiogram.types import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, Group, Cancel, Radio, Column, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput, MessageInput

from bot.states import ApplicationSG
from .handlers import (
    on_full_name_input, on_course_selected, on_vsm_selected, on_spbu_selected,
    on_university_input, on_dormitory_selected, on_email_input, on_phone_input,
    on_contact_received, on_qualities_input, on_motivation_input, on_submit_application,
    on_edit_full_name, on_edit_course, on_edit_vsm, on_edit_spbu, on_edit_university,
    on_edit_dormitory, on_edit_email, on_edit_phone, on_edit_qualities,
    on_edit_motivation, on_edit_departments, on_departments_result,
    email_check, phone_check
)
from .getters import (
    get_course_options, get_yes_no_options, get_dormitory_options,
    get_overview_data, get_edit_menu_data
)


application_dialog = Dialog(
    # Окно 1: ФИО
    Window(
        Const("👤 Введи свою Фамилию, Имя и Отчество:\n\nНапример: Иванов Иван Иванович"),
        TextInput(
            id="full_name_input",
            on_success=on_full_name_input,
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.full_name,
    ),
    
    # Окно 2: Курс обучения
    Window(
        Const("🎓 Укажи свой курс обучения:"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="course_radio",
                item_id_getter=lambda item: item["id"],
                items="courses",
                on_click=on_course_selected
            ),
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.course,
        getter=get_course_options,
    ),
    
    # Окно 3: Вопрос про ВШМ
    Window(
        Const("🏛️ Ты из ВШМ?"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="vsm_radio",
                item_id_getter=lambda item: item["id"],
                items="options",
                on_click=on_vsm_selected
            ),
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.is_from_vsm,
        getter=get_yes_no_options,
    ),
    
    # Окно 4: Вопрос про СПбГУ
    Window(
        Const("🎓 Ты из СПбГУ?"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="spbu_radio",
                item_id_getter=lambda item: item["id"],
                items="options",
                on_click=on_spbu_selected
            ),
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.is_from_spbu,
        getter=get_yes_no_options,
    ),
    
    # Окно 5: ВУЗ
    Window(
        Const("🏫 Из какого ты ВУЗа? Укажи название уч. заведения и факультет:"),
        TextInput(
            id="university_input",
            on_success=on_university_input,
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.university,
    ),
    
    # Окно 6: Общежитие (показывается только если НЕ из ВШМ)
    Window(
        Const("🏠 Живешь ли ты в общежитии в Михайловской даче?"),
        Column(
            Radio(
                Format("🔘 {item[text]}"),
                Format("⚪ {item[text]}"),
                id="dormitory_radio",
                item_id_getter=lambda item: item["id"],
                items="dormitory_options",
                on_click=on_dormitory_selected
            ),
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.dormitory,
        getter=get_dormitory_options,
    ),
    
    # Окно 7: Email
    Window(
        Const("📧 Укажи свой email адрес (Если из СПбГУ, то укажи, пожалуйста, почту st):"),
        TextInput(
            id="email_input",
            on_success=on_email_input,
            type_factory=email_check,
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.email,
    ),
    
    # Окно 8: Телефон
    Window(
        Const("📱 Введи твой номер телефона:"),
        TextInput(
            id="phone_input",
            on_success=on_phone_input,
            type_factory=phone_check,
        ),
        MessageInput(
            func=on_contact_received,
            content_types=[ContentType.CONTACT],
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.phone,
    ),
    
    # Окно 9: Личные качества
    Window(
        Const("🌸 Расскажи развёрнуто о своих личностных качествах и умениях, "
              "которые пригодились бы в волонтёрской работе:"),
        TextInput(
            id="qualities_input",
            on_success=on_qualities_input,
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.personal_qualities,
    ),
    
    # Окно 10: Мотивация
    Window(
        Const("🌟 Объясни подробно, почему тебе бы хотелось попробовать себя в роли волонтёра МБ:"),
        TextInput(
            id="motivation_input",
            on_success=on_motivation_input,
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.motivation,
    ),
    
    # Окно 11: Обзор ответов
    Window(
        Format("{overview_text}"),
        Group(
            Button(Const("✅ Подтвердить и отправить"), id="submit", on_click=on_submit_application),
            Button(Const("✏️ Изменить"), id="edit", on_click=lambda c, b, m: m.switch_to(ApplicationSG.edit_menu)),
            width=1,
        ),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.overview,
        getter=get_overview_data,
    ),
    
    # Окно 12: Меню изменения заявки
    Window(
        Const("✏️ Что хочешь изменить?"),
        Group(
            Button(Const("👤 ФИО"), id="edit_full_name", on_click=on_edit_full_name),
            Button(Const("🎓 Курс"), id="edit_course", on_click=on_edit_course),
            Button(Const("🏛️ Из ВШМ"), id="edit_vsm", on_click=on_edit_vsm),
            Button(Const("🎓 Из СПбГУ"), id="edit_spbu", on_click=on_edit_spbu),
            Button(Const("🏫 ВУЗ"), id="edit_university", on_click=on_edit_university),
            Button(Const("🏠 Общежитие"), id="edit_dormitory", on_click=on_edit_dormitory),
            Button(Const("📧 Email"), id="edit_email", on_click=on_edit_email),
            Button(Const("📱 Телефон"), id="edit_phone", on_click=on_edit_phone),
            Button(Const("🌸 Личные качества"), id="edit_qualities", on_click=on_edit_qualities),
            Button(Const("🌟 Мотивация"), id="edit_motivation", on_click=on_edit_motivation),
            Button(Const("📊 Оценки отделов"), id="edit_departments", on_click=on_edit_departments),
            width=2,
        ),
        SwitchTo(Const("🔙 Назад к обзору"), id="back_to_overview", state=ApplicationSG.overview),
        Cancel(Const("❌ Отмена")),
        state=ApplicationSG.edit_menu,
        getter=get_edit_menu_data,
    ),
    
    on_process_result=on_departments_result,
)