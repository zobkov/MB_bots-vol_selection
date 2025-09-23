from aiogram.filters.state import StatesGroup, State


class StartSG(StatesGroup):
    """Стартовый диалог"""
    start = State()


class MenuSG(StatesGroup):
    """Главное меню"""
    main = State()
    support = State()


class ApplicationSG(StatesGroup):
    """Анкета - первый этап"""
    full_name = State()
    course = State()
    is_from_vsm = State()
    is_from_spbu = State()
    university = State()
    dormitory = State()
    email = State()
    phone = State()
    personal_qualities = State()
    motivation = State()
    overview = State()
    edit_menu = State()


class DepartmentSelectionSG(StatesGroup):
    """Выбор отделов"""
    logistics = State()
    marketing = State()
    pr = State()
    program = State()
    partners = State()
    overview = State()
