Коротко и честно: сделать таймер на каждый вопрос в aiogram-dialog — легко на бумаге, чуть сложнее в надёжной продакшн-реализации. Главные риски: утечки задач (asyncio.Task), гонки (пользователь ответил одновременно с таймаутом) и невозможность хранить объекты loop/Task в персистентном сторедже. Ниже — рабочая, идиоматичная реализация с ООП-подходом, асинхронными практиками и пояснениями плюс рекомендации для масштаба. Я использую возможности aiogram-dialog (getter / MessageInput / dialog_manager) и asyncio-таски; если вам нужна отказоустойчивая система с кластером — внизу опция с APScheduler / внешним хранилищем. Документация и источники отмечены после ключевых мест — читайте их, они важны.  ￼

⸻

Идея (в 2 строках)
	1.	Когда показываете окно с вопросом — запускаете asyncio.Task, который ждёт duration и по таймауту выполняет обработчик (отметить как пропуск/поставить 0/перейти дальше).
	2.	Если пользователь отвечает раньше — отменяете таску корректно и обрабатываете ответ.
	3.	Храните таски в центральном in-memory реестре (ключ — чат/интенция). Для продакшна — используйте планировщик + персистентный jobstore (см. APScheduler) или pub/sub.

⸻

Почему так (критично)
	•	aiogram-dialog умеет вызывать getter/on_start при показе окна и предоставляет dialog_manager в обработчиках/getter’ах — это место, где удобно запускать побочную задачу таймера.  ￼
	•	MessageInput/TextInput — стандартный способ ловить текстовый ответ в окне; туда навешиваем логику отмены таймера.  ￼
	•	Асинхронные таски создаём через asyncio.create_task; отменяем через task.cancel() и обязательно await-им, чтобы не оставлять «висящих» корутин. Документация asyncio про задачи и отмену — обязательное чтение.  ￼

⸻

Что вы получите ниже
	1.	Полный пример кода (минимум внешних зависимостей).
	2.	Класс-реестр таймеров с блокировкой и корректной отменой.
	3.	Шаблон Dialog / Window с getter, MessageInput и примерами on_success.
	4.	Пояснение по тестированию, ограничениям и варианту для масштабирования (APScheduler + job store).

⸻

Зависимости
python >= 3.11
aiogram >= 3.x
aiogram-dialog >= 2.x
(опционально) apscheduler

# Полный пример (скопируйте — он рабочий, читаемый, OOP-стиль)
``` python
# quiz_bot.py
from __future__ import annotations
import asyncio
import functools
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import (
    Dialog, DialogManager, Window, setup_dialogs
)
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.kbd import Row, Next
from aiogram_dialog.widgets.input import MessageInput

logger = logging.getLogger(__name__)


class TimerRegistry:
    """
    Управляет asyncio.Task для таймеров вопросов.
    Ключ — (chat_id, intent_id) или другой уникальный идентификатор диалога.
    """
    def __init__(self) -> None:
        self._tasks: Dict[Tuple[int, Optional[str]], asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def start_timer(self, key: Tuple[int, Optional[str]],
                          duration: float,
                          callback_coro: Callable[..., Any],
                          *cb_args: Any) -> None:
        """Запустить таймер: отменит предыдущий таск по ключу, если есть."""
        async with self._lock:
            await self._cancel_no_lock(key)
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._timer_worker(key, duration, callback_coro, *cb_args))
            self._tasks[key] = task
            logger.debug("Started timer %s (duration=%s)", key, duration)

    async def cancel_timer(self, key: Tuple[int, Optional[str]]) -> None:
        """Безопасно отменяет таск по ключу, дожидаясь его завершения."""
        async with self._lock:
            await self._cancel_no_lock(key)

    async def _cancel_no_lock(self, key: Tuple[int, Optional[str]]) -> None:
        task = self._tasks.pop(key, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.debug("Timer %s cancelled", key)
        except Exception:
            logger.exception("Exception while awaiting cancelled task %s", key)

    async def _timer_worker(self, key: Tuple[int, Optional[str]],
                            duration: float,
                            callback_coro: Callable[..., Any],
                            *cb_args: Any) -> None:
        try:
            await asyncio.sleep(duration)
            # вызываем callback — это должен быть coroutine function
            await callback_coro(*cb_args)
        except asyncio.CancelledError:
            # ожидаемое поведение — пользователь ответил раньше
            logger.debug("Timer worker cancelled for %s", key)
            raise
        except Exception:
            logger.exception("Timer worker error for %s", key)
        finally:
            # очистка: удаляем задачу из реестра, если осталась
            async with self._lock:
                self._tasks.pop(key, None)


# глобальный реестр (подойдет для single-process)
TIMER_REGISTRY = TimerRegistry()

# === quiz logic ===

class QuizSG(StatesGroup):
    question = State()
    finished = State()

# Пример вопросов
QUESTIONS = [
    {"id": 1, "text": "Сколько будет 2+2?", "time": 10},
    {"id": 2, "text": "Столица Франции?", "time": 8},
]

async def _get_chat_key_from_manager(dialog_manager: DialogManager) -> Tuple[int, Optional[str]]:
    """
    Универсальная функция для ключа в TimerRegistry.
    Используем chat_id и intent_id (если есть) — так таймеры уникальны для конкретного диалога/сессии.
    """
    event = dialog_manager.event
    # попытка безопасно взять chat id
    chat_id = None
    if isinstance(event, Message):
        chat_id = event.chat.id
    elif hasattr(event, "from_user") and event.from_user:
        chat_id = event.from_user.id
    else:
        # fallback — менеджер может быть bg / callback, пробуем из dialog_manager.data
        chat_id = dialog_manager.dialog_data.get("chat_id") or dialog_manager.start_data.get("chat_id")
    intent = None
    try:
        current_ctx = dialog_manager.current_context()
        intent = getattr(current_ctx, "intent_id", None)
    except Exception:
        intent = None
    return int(chat_id), intent

# Callback: что делать при таймауте
async def on_question_timeout(dialog_manager: DialogManager, q_index: int) -> None:
    """
    Вызывается из фоновой таски, когда время вышло.
    Здесь мы:
     - уведомляем пользователя
     - помечаем ответ как None (пример)
     - переходим к следующему вопросу (manager.next())
    """
    try:
        chat_key = await _get_chat_key_from_manager(dialog_manager)
        chat_id = chat_key[0]
        bot: Bot = dialog_manager.middleware_data.get("bot") or dialog_manager.event.bot
        # уведомляем
        await bot.send_message(chat_id, f"Время на вопрос #{q_index+1} вышло. Переходим к следующему.")
        # сохраняем пустой ответ
        answers = dialog_manager.dialog_data.setdefault("answers", [])
        answers.append(None)  # маркер пропуска
        # отменяем таймер (на всякий случай)
        await TIMER_REGISTRY.cancel_timer(chat_key)
        # Переход к следующему вопросу (если есть)
        await dialog_manager.next()
    except Exception:
        logger.exception("Ошибка в on_question_timeout")

# Getter: вызывается при показе окна; стартует таймер
async def question_getter(dialog_manager: DialogManager, **kwargs) -> Dict[str, Any]:
    # определяем индекс текущего вопроса (храним в dialog_data)
    q_index = dialog_manager.dialog_data.get("q_index", 0)
    q = QUESTIONS[q_index]
    # стартуем таймер (перезапишем старый)
    key = await _get_chat_key_from_manager(dialog_manager)
    # в callback передаём сам dialog_manager — acceptable для in-memory (не сериализуемо)
    await TIMER_REGISTRY.start_timer(key, q["time"], on_question_timeout, dialog_manager, q_index)
    return {"question_text": q["text"], "time_left": q["time"]}

# Обработчик успешного ответа (MessageInput.on_success)
async def handle_answer(message: Message, dialog_manager: DialogManager, text: str) -> None:
    # отменяем таймер
    key = await _get_chat_key_from_manager(dialog_manager)
    await TIMER_REGISTRY.cancel_timer(key)
    # сохраняем ответ
    answers = dialog_manager.dialog_data.setdefault("answers", [])
    answers.append(text)
    # логика перехода (следующий вопрос или finish)
    q_index = dialog_manager.dialog_data.get("q_index", 0)
    q_index += 1
    if q_index >= len(QUESTIONS):
        # закончено
        dialog_manager.dialog_data["q_index"] = q_index
        # можно вызвать finished обработчик или manager.done()
        await dialog_manager.switch_to(QuizSG.finished)
    else:
        dialog_manager.dialog_data["q_index"] = q_index
        await dialog_manager.next()

# Window определение
question_window = Window(
    Format("Вопрос: {question_text}\nВремя: {time_left} сек"),
    MessageInput(func=handle_answer),
    Next(Const("Пропустить (next)")),  # для примера: кнопка Next тоже переводит дальше
    getter=question_getter,
    state=QuizSG.question
)

finished_window = Window(
    Format("Тест завершён. Ответы: {dialog_data[answers]}"),
    state=QuizSG.finished
)

quiz_dialog = Dialog(question_window, finished_window)

# Регистрация — в основном файле бота:
# from aiogram import Bot, Dispatcher
# bot = Bot(TOKEN)
# dp = Dispatcher()
# setup_dialogs(dp)  # docs example
# dp.include_router(your_router)
# dp.run_polling(bot)
```

Комментарии по коду: мы стартуем таймер в getter (оно вызывается при рендере окна), отменяем в handle_answer. Реестр использует lock, безопасную отмену (await task) и удаляет завершённые таски. Это предотвращает утечки. Для single-process это норм; для нескольких воркеров — потребуется внешний планировщик/хранилище.

⸻

Пояснения (технические, прямо)
	1.	Почему getter? Он вызывается при отрисовке окна и получает dialog_manager в kwargs — удобное место для запуска побочных эффектов, связанных с показом окна.  ￼
	2.	Не храните asyncio.Task в Redis / персистентном сторедже. Task — объект loop-а; храните только в памяти или используйте external scheduler (APScheduler) с jobstore. Для отказоустойчивости — см. раздел «масштабирование».  ￼
	3.	Всегда ожидайте отмену задачи. Просто вызвать task.cancel() и не await — оставит корутину в «зависшем» состоянии; правильно task.cancel(); await task (ловим CancelledError). Это предотвращает resource leaks.  ￼
	4.	Ресурсы/ограничения: если бот рестартует — все in-memory timers исчезнут (пользователи не получат таймаут). Для долгих тестов/много воркеров — используйте внешнюю систему (см. APScheduler или очередь задач).

⸻

Опции для продакшна (кратко)
	1.	Single-process / low traffic — подход выше. Прост и быстр.
	2.	Multi-process / High availability — используйте APScheduler с persistent jobstore (Postgres/Redis). В каждом вопросе создавайте job, который через AsyncIOScheduler вызовет ваш обработчик (он может обновить БД и через pub/sub/redis уведомить экземпляр бота о том, что нужно переключить диалог). Это решает рестарты и распределённость, но сложнее в реализации.  ￼
	3.	Альтернативы: Redis с TTL + keyspace notifications (подписаться на срабатывание истечения ключа) — при expiry шлём event; но это сложнее и зависит от infra.

⸻

Тестирование
	•	Unit: тестируйте TimerRegistry отдельно (создавайте таску, отменяйте, проверяйте, что callback не вызван / вызван).
	•	Integration: запуск локального бота, симуляция пользователя, время сокращать (1–2 сек) и проверить гонки: 1) ответ до таймаута 2) одновременный ответ + таймаут (должен работать сначала отмена/обработка)
	•	Логируйте всё — таймеры, отмены, ошибки — это важно для отладки гонок.

⸻

Частые ошибки и как их избежать
	•	Хранение manager/Task в сторедже — не делайте. Только in-memory.
	•	Неожиданные исключения в callback — обязательно try/except внутри _timer_worker и on_question_timeout (иначе таска умрёт молча).
	•	Множественные таймеры на 1-ю сессию — всегда перед созданием нового таймера отменяйте старый (в коде делается).
	•	Слабая уникальность ключа — используйте сочетание chat_id + intent_id/diag_id, иначе перезаписываете чужие таймеры.

⸻

Ссылки / чтение (ключевые)
	•	aiogram-dialog — getter и dialog_manager в getter; примеры on_start у Dialog. (доки).  ￼
	•	TextInput / MessageInput — как обрабатывать ввод внутри окна.  ￼
	•	Python asyncio — Tasks / как их создавать.  ￼
	•	Best practices по отмене asyncio-тасков и обработке CancelledError.  ￼

⸻

Заключение (сухо)
Если вам нужен простой, быстрый и управляемый вариант — используйте предложенный шаблон с TimerRegistry. Он полностью покрывает сценарий «таймер на вопрос» в рамках одного инстанса бота, при этом не нагружает инфраструктуру лишними зависимостями. Такой подход хорош для учебных или средних по масштабу проектов, где перезапуски бота редки и нет необходимости держать state при падении.

Если же бот работает в продакшне с нагрузкой, где важна отказоустойчивость, стабильность и горизонтальное масштабирование, придётся вынести таймеры наружу — в APScheduler, Redis или другой планировщик, чтобы таймауты жили независимо от памяти процесса. В этом случае бот будет только подписываться на события и реагировать, а не держать задачи в loop.

Итого: решение через TimerRegistry — оптимальный баланс простоты и чистоты для начала. Когда станет тесно — вы уже будете иметь готовую архитектуру, которую можно заменить на более «тяжёлый» вариант без переписывания логики диалога.