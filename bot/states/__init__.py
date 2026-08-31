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


