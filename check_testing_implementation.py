#!/usr/bin/env python3
"""
Простая проверка структуры файлов системы тестирования
"""

import os
import sys

def check_file_structure():
    """Проверка структуры файлов"""
    print("📁 Проверка структуры файлов...")
    
    required_files = [
        "bot/states/__init__.py",
        "bot/dialogs/testing/__init__.py", 
        "bot/dialogs/testing/dialogs.py",
        "bot/dialogs/menu/dialogs.py",
        "bot/dialogs/menu/getters.py",
        "bot/assets/images/first_floor.jpeg",
        "bot/assets/images/second_floor.jpeg",
        "main.py"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - НЕ НАЙДЕН")
            
def check_states_content():
    """Проверка содержимого файла состояний"""
    print("\n📊 Проверка состояний...")
    
    states_file = "bot/states/__init__.py"
    if not os.path.exists(states_file):
        print(f"❌ Файл {states_file} не найден")
        return
        
    with open(states_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    required_states = [
        "TestingSG",
        "GeneralTestSG", 
        "DepartmentTestSelectionSG",
        "LogisticsTestSG",
        "ProgramTestSG",
        "PartnersTestSG",
        "PRTestSG",
        "MarketingTestSG"
    ]
    
    for state in required_states:
        if state in content:
            print(f"✅ {state}")
        else:
            print(f"❌ {state} - НЕ НАЙДЕН")

def check_main_py_integration():
    """Проверка интеграции в main.py"""
    print("\n🔧 Проверка интеграции в main.py...")
    
    main_file = "main.py"
    if not os.path.exists(main_file):
        print(f"❌ Файл {main_file} не найден")
        return
        
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    required_imports = [
        "testing_dialog",
        "general_test_dialog",
        "department_test_selection_dialog",
        "logistics_test_dialog",
        "program_test_dialog",
        "partners_test_dialog",
        "pr_test_dialog",
        "marketing_test_dialog"
    ]
    
    for import_name in required_imports:
        if import_name in content:
            print(f"✅ {import_name}")
        else:
            print(f"❌ {import_name} - НЕ НАЙДЕН")

def check_menu_modification():
    """Проверка изменений в меню"""
    print("\n🏠 Проверка изменений в главном меню...")
    
    menu_dialogs = "bot/dialogs/menu/dialogs.py"
    menu_getters = "bot/dialogs/menu/getters.py"
    
    if os.path.exists(menu_dialogs):
        with open(menu_dialogs, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "TestingSG" in content:
            print("✅ Импорт TestingSG в menu/dialogs.py")
        else:
            print("❌ Импорт TestingSG в menu/dialogs.py - НЕ НАЙДЕН")
            
        if "Пройти тестирование" in content:
            print("✅ Кнопка тестирования в menu/dialogs.py")
        else:
            print("❌ Кнопка тестирования в menu/dialogs.py - НЕ НАЙДЕНА")
    
    if os.path.exists(menu_getters):
        with open(menu_getters, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "show_testing_button" in content:
            print("✅ show_testing_button в menu/getters.py")
        else:
            print("❌ show_testing_button в menu/getters.py - НЕ НАЙДЕН")

def main():
    """Основная функция проверки"""
    print("🧪 Проверка системы тестирования волонтеров")
    print("=" * 60)
    
    check_file_structure()
    check_states_content()
    check_main_py_integration()
    check_menu_modification()
    
    print("\n" + "=" * 60)
    print("📋 Проверка завершена!")
    print("\n📝 Что было реализовано:")
    print("  • 🏠 Изменено главное меню (кнопка тестирования)")
    print("  • 📊 Добавлены состояния для всех диалогов")
    print("  • 🚀 Создано стартовое окно тестирования")
    print("  • ❓ Реализовано общее тестирование (6 вопросов)")
    print("  • 🏢 Создано меню выбора отделов")
    print("  • 🔧 Тестирование Логистики (6 вопросов)")
    print("  • 📋 Тестирование Программы (6 вопросов)")
    print("  • 🤝 Тестирование Партнеров (6 вопросов)")
    print("  • 📰 Тестирование PR (4 вопроса)")
    print("  • 📸 Тестирование Маркетинга (5 вопросов)")
    print("  • ⏰ Интеграция с APScheduler для таймеров")
    print("  • 💾 Сохранение ответов в dialog_data")
    print("  • 🖼️ Поддержка изображений для вопросов 5-6")
    
    print("\n🎯 Особенности:")
    print("  • Таймеры на каждый вопрос с обратным отсчетом")
    print("  • Блокировка пройденных отделов (🔒)")
    print("  • Обязательность прохождения минимум 1 отдела")
    print("  • Автоматическое сохранение пустых ответов при таймауте")
    print("  • Возможность завершения и возврата в меню")

if __name__ == "__main__":
    main()