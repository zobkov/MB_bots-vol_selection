from aiogram.filters.state import StatesGroup, State


class StartSG(StatesGroup):
    """Стартовый диалог"""
    welcome = State()


class MenuSG(StatesGroup):
    """Главное меню"""
    main = State()
    support = State()


class ApplicationSG(StatesGroup):
    """Анкета отбора волонтеров 2026"""
    full_name = State()            # 1. ФИО
    email_st = State()             # 2. Почта st
    phone = State()                # 3. Телефон
    faculty = State()              # 4. Факультет / направление
    course = State()               # 5. Курс обучения
    days_count = State()           # 6. Количество дней (2 или 3 дня)
    day_zero = State()             # 7. 0 день Конференции (21 октября)
    role = State()                 # 8. Роль на площадке
    motivation = State()           # 9. Почему ты - идеальный волонтер
    experience = State()           # 10. Опыт волонтерства
    overview = State()             # Экран проверки
    edit_menu = State()            # Меню редактирования
    submitted = State()            # Экран успешной отправки


class ViewUserSG(StatesGroup):
    """Просмотр профиля и анкеты пользователя для администраторов/дебага"""
    user_info = State()            # Общая информация о пользователе
    app_details = State()          # Постраничный просмотр анкеты волонтера


class Stage2SG(StatesGroup):
    """Второй этап отбора волонтеров МБ 2026"""
    # Шлюз / выбор ветки
    MAIN = State()

    # Ветка: Волонтеры общего функционала
    intro_general = State()        # Инструкция и правила
    timer_warning = State()        # Предупреждение о таймере (35 минут) + кнопка готовности
    q1_about_mb = State()          # Вопрос 1: Что ты знаешь о Конференции
    q2_motivation = State()        # Вопрос 2: Почему хочешь стать волонтером именно на МБ
    q3_well_organized = State()    # Вопрос 3: Что делает мероприятие хорошо организованным
    video_intro = State()          # Экран-переход к видеоинтервью
    vq1 = State()                  # Видео-вопрос 1 (самостоятельное решение проблемы)
    vq2 = State()                  # Видео-вопрос 2 (жертва личным комфортом ради цели)
    vq3 = State()                  # Видео-вопрос 3 (кейс с приоритезацией задач)
    vq4 = State()                  # Видео-вопрос 4 (сомнения в решении руководителя)
    vq5 = State()                  # Видео-вопрос 5 (работа в команде со сложным человеком)

    # Ветка: Фотографы и видеографы
    intro_media = State()          # Инструкция для медиа-направления
    media_q1_equipment = State()   # Вопрос 1: Свое оборудование (Да/Нет)
    media_q2_experience = State()  # Вопрос 2: Опыт профессиональной съемки
    media_q3_portfolio = State()   # Вопрос 3: Ссылка на портфолио

    # Финал
    success = State()              # Экран успешного завершения


class Stage2ReviewSG(StatesGroup):
    """Оценка и просмотр заявок 2-го этапа для администраторов"""
    PAGE_SELECT = State()          # Сетка выбора номеров страниц
    PAGE = State()                 # Список из 10 заявок на выбранной странице
    APP_DETAIL = State()           # Полная анкета кандидата (с пагинацией длинного текста)
    VIDEO = State()                # Просмотр видео-кружков кандидата



