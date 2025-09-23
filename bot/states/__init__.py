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


# Система тестирования
class TestingSG(StatesGroup):
    """Стартовое окно тестирования"""
    intro = State()


class GeneralTestSG(StatesGroup):
    """Общее тестирование"""
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    completed = State()


class DepartmentTestSelectionSG(StatesGroup):
    """Выбор отделов для тестирования"""
    selection = State()


class LogisticsTestSG(StatesGroup):
    """Тестирование отдела Логистика"""
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    completed = State()


class ProgramTestSG(StatesGroup):
    """Тестирование отдела Программа"""
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    completed = State()


class PartnersTestSG(StatesGroup):
    """Тестирование отдела Партнеры"""
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    completed = State()


class PRTestSG(StatesGroup):
    """Тестирование отдела PR"""
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    completed = State()


class MarketingTestSG(StatesGroup):
    """Тестирование отдела Маркетинг"""
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    completed = State()
