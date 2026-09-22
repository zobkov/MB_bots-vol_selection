#!/usr/bin/env python3
"""
Разовая рассылка сообщения с картинкой пользователям бота из CSV-файла.

Использование:
    poetry run python broadcast.py users.csv
    poetry run python broadcast.py users.csv --dry-run
    poetry run python broadcast.py users.csv --rate 15 --yes
    poetry run python broadcast.py users.csv --no-photo   # только текст

CSV содержит только telegram_id, по одному на строку (заголовок опционален —
если первая строка не число, она считается заголовком и пропускается).

Текст сообщения задан константой MESSAGE_TEXT. Отправка с картинкой
(PHOTO_PATH) или без нее переключается константой SEND_PHOTO (либо флагом
--no-photo для разового запуска без правки файла) — отредактируйте нужное
и запустите скрипт заново.
"""

import argparse
import asyncio
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers import MAIN_MENU_CALLBACK
from config.config import load_config
from utils.emojis import combo_emojis, emoji

# ============================================================================
# РЕДАКТИРУЕМЫЕ ПАРАМЕТРЫ РАССЫЛКИ
# ============================================================================

MESSAGE_TEXT = (
    f'{combo_emojis("announcement_light_purple")} <b>Мы возвращаемся с прекрасной новостью!</b>\n\n'
    "Первый этап отбора завершен, и мы готовы приступить к следующему. Тебе предстоит "
    "выполнить тестовое задание и ответить на несколько вопросов в формате «кружков».\n\n"
    f' {emoji("exclamation", color="orange")}  Внимательно прочитай инструкцию перед выполнением '
    "задания. Ты можешь выполнить его до 27 сентября 23:59 включительно.\n\n"
    f'<b>Советуем не откладывать на последний день и желаем удачи!</b> {emoji("sparkles", color="light_purple")}\n\n'
    "По всем вопросам пиши в чат поддержки @mbconf_support\n"
    "Если у тебя есть технические трудности с прохождением тестирования пиши напрямую Артёму @zobko"
)

# Переключатель: отправлять с картинкой (PHOTO_PATH) или чистым текстом.
# Можно также временно отключить фото флагом --no-photo, не трогая файл.
SEND_PHOTO = True

PHOTO_PATH = Path("assets/broadcast_pic/1.png")

# Кнопка "Главное меню" — callback_data обрабатывается в bot/handlers.py
# (cb_go_to_main_menu), поэтому кнопка работает, только пока бот запущен.
MAIN_MENU_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data=MAIN_MENU_CALLBACK)]]
)

# Telegram Bot API: не более ~30 сообщений/сек в разные чаты, иначе бот
# начинает получать 429 Too Many Requests. Берем значение с запасом ниже
# официального лимита.
DEFAULT_RATE_PER_SEC = 20
MAX_RATE_PER_SEC = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("broadcast")


def read_telegram_ids(csv_path: Path) -> list[int]:
    """Читает уникальные telegram_id из CSV — один id в первой колонке каждой
    строки. Заголовок не обязателен: если первая строка не число, она
    считается заголовком и пропускается."""
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = [row for row in csv.reader(f) if row and row[0].strip()]

    if not rows:
        raise ValueError("CSV файл пуст")

    start_idx = 0
    if not rows[0][0].strip().lstrip("-").isdigit():
        start_idx = 1  # первая строка — заголовок, пропускаем

    seen: set[int] = set()
    ids: list[int] = []
    for row_num, row in enumerate(rows[start_idx:], start=start_idx + 1):
        raw = row[0].strip()
        if not raw.lstrip("-").isdigit():
            logger.warning("Строка %d: некорректный telegram_id %r, пропущена", row_num, raw)
            continue
        tid = int(raw)
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
    return ids


async def send_with_retry(bot: Bot, chat_id: int, photo, max_retries: int = 3) -> tuple[bool, str]:
    """Отправляет фото с подписью (или просто текст, если photo is None),
    автоматически выжидая при flood-control (429)."""
    for attempt in range(1, max_retries + 1):
        try:
            if photo is not None:
                message = await bot.send_photo(
                    chat_id=chat_id, photo=photo, caption=MESSAGE_TEXT, reply_markup=MAIN_MENU_KEYBOARD
                )
                return True, message.photo[-1].file_id
            else:
                await bot.send_message(chat_id=chat_id, text=MESSAGE_TEXT, reply_markup=MAIN_MENU_KEYBOARD)
                return True, ""
        except TelegramRetryAfter as e:
            logger.warning(
                "Flood control для %d: жду %d сек. (попытка %d/%d)",
                chat_id, e.retry_after, attempt, max_retries,
            )
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            logger.info("Пользователь %d заблокировал бота", chat_id)
            return False, "blocked"
        except TelegramBadRequest as e:
            logger.warning("Bad request для %d: %s", chat_id, e)
            return False, f"bad_request: {e}"
        except Exception as e:
            logger.error("Неожиданная ошибка для %d: %s", chat_id, e)
            return False, f"error: {e}"
    return False, "flood_control_exhausted"


def write_report(results: list[tuple[int, str]]) -> Path:
    reports_dir = Path("logs")
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"broadcast_report_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["telegram_id", "status"])
        writer.writerows(results)
    logger.info("Отчет сохранен: %s", report_path)
    return report_path


async def broadcast(csv_path: Path, rate_per_sec: float, dry_run: bool, skip_confirm: bool, send_photo: bool) -> None:
    if send_photo and not PHOTO_PATH.exists():
        raise FileNotFoundError(
            f"Не найдена картинка рассылки: {PHOTO_PATH}. Положите файл 1.png в assets/broadcast_pic/ "
            f"или запустите с --no-photo для отправки только текста."
        )

    telegram_ids = read_telegram_ids(csv_path)
    if not telegram_ids:
        logger.warning("В CSV не найдено ни одного валидного telegram_id, рассылка отменена")
        return

    logger.info("Получателей: %d", len(telegram_ids))
    logger.info("Режим: %s", "с картинкой" if send_photo else "только текст")
    logger.info("Текст сообщения:\n%s", MESSAGE_TEXT)

    if dry_run:
        logger.info("Режим dry-run: сообщения не отправляются")
        return

    if not skip_confirm:
        answer = input(f"Отправить сообщение {len(telegram_ids)} пользователям? [y/N]: ").strip().lower()
        if answer != "y":
            logger.info("Отменено пользователем")
            return

    config = load_config()
    bot = Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    delay = 1.0 / rate_per_sec
    results: list[tuple[int, str]] = []
    file_id: str | None = None

    try:
        for i, chat_id in enumerate(telegram_ids, start=1):
            photo = None
            if send_photo:
                # Первая отправка загружает файл и возвращает file_id, дальше
                # переиспользуем его — так быстрее и не грузит файл заново.
                photo = file_id if file_id else FSInputFile(PHOTO_PATH)
            ok, info = await send_with_retry(bot, chat_id, photo)
            if ok and send_photo and file_id is None:
                file_id = info
            results.append((chat_id, "sent" if ok else info))
            logger.info("[%d/%d] %d -> %s", i, len(telegram_ids), chat_id, "OK" if ok else info)

            if i < len(telegram_ids):
                await asyncio.sleep(delay)
    finally:
        await bot.session.close()

    write_report(results)

    sent = sum(1 for _, status in results if status == "sent")
    logger.info("Готово: успешно %d/%d", sent, len(results))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Рассылка сообщения с картинкой пользователям из CSV")
    parser.add_argument("csv_file", type=Path, help="Путь к CSV с telegram_id (по одному в строке)")
    parser.add_argument(
        "--rate", type=float, default=DEFAULT_RATE_PER_SEC,
        help=f"Сообщений в секунду (по умолчанию {DEFAULT_RATE_PER_SEC}, лимит Telegram ~{MAX_RATE_PER_SEC}/сек)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Только показать количество получателей, не отправлять")
    parser.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение перед отправкой")
    parser.add_argument(
        "--no-photo", action="store_true",
        help="Отправить только текст, без картинки (переопределяет SEND_PHOTO в скрипте)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not (0 < args.rate <= MAX_RATE_PER_SEC):
        logger.error("--rate должен быть в диапазоне (0, %d], чтобы не превышать лимиты Telegram", MAX_RATE_PER_SEC)
        sys.exit(1)

    if not args.csv_file.exists():
        logger.error("Файл не найден: %s", args.csv_file)
        sys.exit(1)

    send_photo = SEND_PHOTO and not args.no_photo
    asyncio.run(broadcast(args.csv_file, args.rate, args.dry_run, args.yes, send_photo))


if __name__ == "__main__":
    main()
