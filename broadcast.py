#!/usr/bin/env python3
"""
Разовая рассылка пользователям бота из CSV-файла: альбом из картинок с
подписью, затем отдельное сообщение с кнопкой «Главное меню» (Telegram не
позволяет прикрепить inline-кнопку к альбому).

Использование:
    poetry run python broadcast.py users.csv
    poetry run python broadcast.py users.csv --dry-run
    poetry run python broadcast.py users.csv --rate 15 --yes
    poetry run python broadcast.py users.csv --no-photo   # только текст, без альбома

CSV содержит только telegram_id, по одному на строку (заголовок опционален —
если первая строка не число, она считается заголовком и пропускается).

Текст подписи к альбому — константа MESSAGE_TEXT, текст второго сообщения
с кнопкой — BUTTON_MESSAGE_TEXT. Отправка с альбомом (PHOTO_PATHS) или без
него переключается константой SEND_PHOTO (либо флагом --no-photo для
разового запуска без правки файла) — отредактируйте нужное и запустите
скрипт заново.
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
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from bot.handlers import MAIN_MENU_CALLBACK
from config.config import load_config
from utils.emojis import combo_emojis, emoji

# ============================================================================
# РЕДАКТИРУЕМЫЕ ПАРАМЕТРЫ РАССЫЛКИ
# ============================================================================

# Подпись к альбому (не более 1024 символов — лимит Telegram для caption)
MESSAGE_TEXT = (
    f"{combo_emojis('last_call')}"
    "Напоминаем, что до конца тестирования остался 1 день!\n\n"
    "Если ты еще не прошел(-а) его, советуем не затягивать, а если ты со всем справился(-ась), "
    "скрашиваем твое ожидание небольшим постом, в котором развеиваем мифы о волонтерстве "
    f'{emoji("heart", color="light_blue")}\n\n'
    "Скорее листай карточки, чтобы обо всем узнать и вдохновиться на продуктивную работу "
    f'{emoji("sparkles", color="light_blue")}'
)

# Второе сообщение — отправляется сразу после альбома, несет кнопку меню
BUTTON_MESSAGE_TEXT = (
    "Если ты еще не прошел(-а) тестирование, то можешь его пройти перейдя по кнопке «🏠 Главное меню».\n\n"
    f'Там же можно найти контакты поддержки и статус твоей заявки {emoji("star", color="light_blue")}'
)

# Переключатель: отправлять с альбомом (PHOTO_PATHS) или чистым текстом.
# Можно также временно отключить фото флагом --no-photo, не трогая файл.
SEND_PHOTO = True

# Порядок в списке = порядок карточек в альбоме (в альбоме от 2 до 10 фото)
PHOTO_PATHS = [Path(f"assets/broadcast_pic/{i}.png") for i in range(1, 6)]

# Перед рассылкой альбом один раз отправляется в этот чат: так файлы
# загружаются на сервера Telegram единожды, а всем получателям уходят
# уже по полученным file_id.
FILE_ID_CACHE_CHAT_ID = 257026813

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


async def call_with_retry(chat_id: int, send, max_retries: int = 3) -> tuple[bool, object]:
    """Вызывает send() (корутину отправки), автоматически выжидая при
    flood-control (429). Возвращает (True, результат) или (False, причина)."""
    for attempt in range(1, max_retries + 1):
        try:
            return True, await send()
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


async def upload_photos(bot: Bot) -> list[str]:
    """Загружает PHOTO_PATHS одним альбомом в FILE_ID_CACHE_CHAT_ID и
    возвращает file_id фото в том же порядке."""
    media = [InputMediaPhoto(media=FSInputFile(path)) for path in PHOTO_PATHS]
    ok, result = await call_with_retry(
        FILE_ID_CACHE_CHAT_ID,
        lambda: bot.send_media_group(chat_id=FILE_ID_CACHE_CHAT_ID, media=media),
    )
    if not ok:
        raise RuntimeError(f"Не удалось загрузить фото в чат {FILE_ID_CACHE_CHAT_ID}: {result}")
    return [message.photo[-1].file_id for message in result]


async def send_to_user(bot: Bot, chat_id: int, photos: list[str] | None) -> tuple[bool, str]:
    """Отправляет альбом по file_id с подписью MESSAGE_TEXT (или просто
    текст, если photos is None), затем сообщение с кнопкой. Каждый шаг
    ретраится отдельно, чтобы при flood-control альбом не ушел
    пользователю дважды."""
    if photos is not None:
        media = [
            InputMediaPhoto(media=photo, caption=MESSAGE_TEXT if idx == 0 else None)
            for idx, photo in enumerate(photos)
        ]
        ok, result = await call_with_retry(chat_id, lambda: bot.send_media_group(chat_id=chat_id, media=media))
        if not ok:
            return False, result
    else:
        ok, result = await call_with_retry(chat_id, lambda: bot.send_message(chat_id=chat_id, text=MESSAGE_TEXT))
        if not ok:
            return False, result

    ok, result = await call_with_retry(
        chat_id,
        lambda: bot.send_message(chat_id=chat_id, text=BUTTON_MESSAGE_TEXT, reply_markup=MAIN_MENU_KEYBOARD),
    )
    if not ok:
        return False, f"button_message_failed: {result}"
    return True, ""


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
    missing = [str(path) for path in PHOTO_PATHS if not path.exists()]
    if send_photo and missing:
        raise FileNotFoundError(
            f"Не найдены картинки рассылки: {', '.join(missing)}. Положите их в assets/broadcast_pic/ "
            f"или запустите с --no-photo для отправки только текста."
        )

    telegram_ids = read_telegram_ids(csv_path)
    if not telegram_ids:
        logger.warning("В CSV не найдено ни одного валидного telegram_id, рассылка отменена")
        return

    logger.info("Получателей: %d", len(telegram_ids))
    logger.info("Режим: %s", f"альбом из {len(PHOTO_PATHS)} фото + сообщение с кнопкой" if send_photo else "только текст")
    logger.info("Текст подписи к альбому:\n%s", MESSAGE_TEXT)
    logger.info("Текст сообщения с кнопкой:\n%s", BUTTON_MESSAGE_TEXT)

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

    try:
        file_ids: list[str] | None = None
        if send_photo:
            file_ids = await upload_photos(bot)
            logger.info("Фото загружены в чат %d, file_id: %s", FILE_ID_CACHE_CHAT_ID, file_ids)

        for i, chat_id in enumerate(telegram_ids, start=1):
            ok, info = await send_to_user(bot, chat_id, file_ids)
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
    parser = argparse.ArgumentParser(description="Рассылка альбома и сообщения с кнопкой пользователям из CSV")
    parser.add_argument("csv_file", type=Path, help="Путь к CSV с telegram_id (по одному в строке)")
    parser.add_argument(
        "--rate", type=float, default=DEFAULT_RATE_PER_SEC,
        help=f"Сообщений в секунду (по умолчанию {DEFAULT_RATE_PER_SEC}, лимит Telegram ~{MAX_RATE_PER_SEC}/сек)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Только показать количество получателей, не отправлять")
    parser.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение перед отправкой")
    parser.add_argument(
        "--no-photo", action="store_true",
        help="Отправить только текст, без альбома (переопределяет SEND_PHOTO в скрипте)",
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
