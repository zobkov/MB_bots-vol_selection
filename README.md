# Telegram Bot для отбора волонтеров МБ 2026

Бот для проведения отбора волонтеров Конференции «Менеджмент Будущего» с использованием aiogram 3.x и aiogram-dialog.

## Технологический стек

- **Python 3.11+**
- **Poetry** - управление зависимостями и виртуальным окружением
- **aiogram 3.x** - основной фреймворк для Telegram бота
- **aiogram-dialog** - система диалогов для интерфейса
- **PostgreSQL** - основная база данных
- **Redis** - хранилище состояний FSM
- **SQLAlchemy 2.0** (asyncio) - ORM для работы с базой данных
- **Google Sheets API (gspread)** - выгрузка анкет кандидатов

## Структура проекта

```
MB_bots-vol_selection/
├── config/
│   ├── config.py              # Конфигурация приложения
│   ├── selection_config.json  # Настройки этапов отбора
│   └── google_credentials.json.example
├── bot/
│   ├── dialogs/              # Диалоги бота
│   │   ├── start.py         # Стартовое окно
│   │   └── application.py   # Анкета отбора (10 вопросов + обзор)
│   ├── states/              # Состояния FSM (aiogram_dialog)
│   ├── keyboards/           # Командное меню бота
│   └── handlers.py          # Обработчики команд
├── database/
│   ├── models.py            # Модели базы данных (User, Application)
│   ├── db.py               # Подключение к БД и создание таблиц
│   └── repositories.py     # Репозитории (UserRepository, ApplicationRepository)
├── utils/
│   ├── google_services.py   # Интеграция с Google Sheets
│   └── logging_config.py    # Настройка логирования
├── archive/
│   └── 2025/                # Архив кампании 2025 года
├── pyproject.toml           # Конфигурация Poetry и зависимости
├── poetry.lock              # Зафиксированные версии пакетов
├── main.py                 # Точка входа
└── start.sh                # Скрипт быстрого запуска
```

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd MB_bots-vol_selection
```

### 2. Установка зависимостей через Poetry

```bash
poetry install
```

### 3. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните переменные в `.env`:

```env
# Bot Token (получить у @BotFather)
BOT_TOKEN=your_bot_token_here

# Database PostgreSQL
DB_USER=vol_selection_user
DB_PASS=vol_selection_pass
DB_NAME=vol_selection_db
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Google Sheets (опционально)
GOOGLE_CREDENTIALS_PATH=config/google_credentials.json
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
```

### 4. Настройка базы данных и Redis

Запустите PostgreSQL и Redis (например, через Docker):

```bash
# PostgreSQL
docker run -d --name vol_selection_postgres -e POSTGRES_USER=vol_selection_user -e POSTGRES_PASSWORD=vol_selection_pass -e POSTGRES_DB=vol_selection_db -p 5432:5432 postgres:15

# Redis
docker run -d --name vol_selection_redis -p 6379:6379 redis:7
```

### 5. Запуск бота

```bash
poetry run python main.py
# или
./start.sh
```

## Функциональность

### Команды бота

- `/start` - главное приветствие и переход к заполнению анкеты
- `/apply` - прямой переход к первому вопросу анкеты

### Анкета отбора (10 вопросов)

1. **ФИО** (текст, проверка на ввод имени и фамилии)
2. **Почта st** (текст, корпоративный email СПбГУ)
3. **Номер телефона** (текст или отправка контакта кнопкой)
4. **Факультет / направление** (текст)
5. **Курс** (кнопки 1-4 бакалавриат, 1-2 магистратура, Другое)
6. **Готовность по дням** (кнопки 2 дня / 3 дня)
7. **0-й день (21 октября)** (кнопки Да / Нет)
8. **Желаемая роль** (кнопки: общий функционал, фотограф, видеограф)
9. **Мотивация** (текст)
10. **Опыт волонтерства** (текст)
11. **Экран проверки и точечного редактирования**
12. **Сохранение в PostgreSQL и выгрузка в Google Sheets**

2. **Главное меню** - информация о текущем этапе, статус заявки, кнопки для заполнения анкеты и поддержки
3. **Анкета (1-й этап)** - пошаговое заполнение анкеты:
   - ФИО
   - Курс обучения (1-4 бакалавриат, 1-2 магистратура)
   - Проживание в общежитии
   - Корпоративная почта (@spbu.ru или @student.spbu.ru)
   - Контактный телефон
   - Личные качества
   - Оценка интереса к отделам (1-5)
   - Мотивация
   - Обзор и подтверждение

### Структура базы данных

#### Таблица `users`
- `telegram_id` - ID пользователя в Telegram
- `telegram_username` - username в Telegram
- `is_alive` - активность пользователя
- `is_blocked` - заблокирован ли пользователь
- `stage1_submitted` - статус подачи заявки ('submitted'/'not_submitted')

#### Таблица `applications` 
- Данные анкеты пользователя
- Оценки интереса к отделам (1-5)
- Связь с пользователем через `user_id`

## Конфигурация этапов

Настройки этапов отбора находятся в `config/selection_config.json`:

```json
{
  "selection_stages": {
    "stage1": {
      "name": "Первый этап - Анкета",
      "deadline": "21.09.2025 23:59",
      "results_date": "22.09.2025 12:00"
    },
    "stage2": {
      "name": "Второй этап - Тестовое задание", 
      "start_date": "22.09.2025 12:00"
    }
  },
  "departments": {
    "logistics": "Логистика",
    "marketing": "Маркетинг", 
    "pr": "PR",
    "program": "Программа",
    "partners": "Партнеры"
  },
  "support_contacts": {
    "main": "@support_user1",
    "technical": "@support_user2"
  }
}
```

## Логирование

Бот использует стандартное логирование Python. Уровень логирования можно настроить в `main.py`.

## Разработка

### Создание новых миграций

```bash
alembic revision --autogenerate -m "описание изменений"
alembic upgrade head
```

### Работа с диалогами

Диалоги построены на основе aiogram-dialog. Каждый диалог состоит из:
- Состояний (states) - определяют окна диалога
- Окон (windows) - содержат интерфейс и логику
- Геттеров (getters) - предоставляют данные для отображения
- Обработчиков (handlers) - обрабатывают действия пользователя

### Добавление новых функций

1. Определите новые состояния в `bot/states/`
2. Создайте диалог в `bot/dialogs/`
3. Зарегистрируйте диалог в `main.py`
4. При необходимости обновите модели БД и создайте миграцию

## Поддержка

При возникновении вопросов обращайтесь к документации:
- [aiogram](https://docs.aiogram.dev/)
- [aiogram-dialog](https://aiogram-dialog.readthedocs.io/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
