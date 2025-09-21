#!/usr/bin/env python3
"""
Экспорт ответов пользователей (этап 2: общие вопросы + отделы) в CSV.

Колонки (в порядке):
- Тег ТГ (@username)
- ФИО
- Курс
- Живет в мд (да/нет; если пусто в БД, выводим "нет")
- ВУЗ (одна колонка: "ВШМ" | "СПбГУ" | значение из поля university)
- Общие 1..6 (ответы на общие вопросы)
- Логистика 1..6
- Маркетинг 1..5
- PR 1..4
- Программа 1..6
- Партнеры 1..6

Запуск:
    python3 export_answers_csv.py [--out exports/answers_YYYYMMDD_HHMM.csv]

Примечание: скрипт использует настройки подключения к БД из config/config.py.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.config import load_config
from database.db import Database
from database.models import (
    User, Application, Stage2Answer,
    DepartmentTestResult, DepartmentTestAnswer,
)
from sqlalchemy import select, func


# Порядок отделов как в меню выбора отделов (см. bot/dialogs/departments.py):
DEPARTMENTS_ORDER = [
    ("logistics", "Логистика", 6),
    ("marketing", "Маркетинг", 5),
    ("pr", "PR", 4),
    ("program", "Программа", 6),
    ("partners", "Партнеры", 6),
]


def course_display(course: Optional[str]) -> str:
    """Возвращаем курс как есть (без сложного маппинга), если потребуется - можно расширить."""
    return course or ""


def dorm_display(dormitory: Optional[bool]) -> str:
    """Да/нет для общежития, по умолчанию нет."""
    return "да" if dormitory is True else "нет"


def university_display(is_from_vsm: Optional[bool], is_from_spbu: Optional[bool], university: Optional[str]) -> str:
    if is_from_vsm:
        return "ВШМ"
    if is_from_spbu:
        return "СПбГУ"
    return (university or "").strip()


def build_headers() -> List[str]:
    headers = [
        "Тег ТГ",
        "ФИО",
        "Курс",
        "Живет в мд",
        "ВУЗ",
    ]
    # Общие вопросы 1..6
    headers.extend([f"Общие {i}" for i in range(1, 7)])
    # Отделы
    for _, dept_name, count in DEPARTMENTS_ORDER:
        headers.extend([f"{dept_name} {i}" for i in range(1, count + 1)])
    return headers


async def fetch_latest_application(session, user_id: int) -> Optional[Application]:
    """Получить последнюю по времени заявку пользователя."""
    result = await session.execute(
        select(Application).where(Application.user_id == user_id).order_by(Application.created_at.desc()).limit(1)
    )
    return result.scalars().first()


async def fetch_stage2(session, user_id: int) -> Optional[Stage2Answer]:
    result = await session.execute(
        select(Stage2Answer).where(Stage2Answer.user_id == user_id)
    )
    return result.scalars().first()


async def fetch_department_answers(session, user_id: int) -> Dict[str, Dict[int, str]]:
    """Вернуть ответы по отделам: { department: {question_number: answer_text} }"""
    dept_answers: Dict[str, Dict[int, str]] = {}

    # Берем все результаты тестов пользователя
    tr_result = await session.execute(
        select(DepartmentTestResult.id, DepartmentTestResult.department)
        .where(DepartmentTestResult.user_id == user_id)
    )
    test_rows = tr_result.all()
    if not test_rows:
        return dept_answers

    test_ids = [row.id for row in test_rows]
    id_to_dept = {row.id: row.department for row in test_rows}

    # Загружаем ответы одним запросом
    ans_result = await session.execute(
        select(
            DepartmentTestAnswer.test_result_id,
            DepartmentTestAnswer.question_number,
            DepartmentTestAnswer.answer_text,
        )
        .where(DepartmentTestAnswer.test_result_id.in_(test_ids))
        .order_by(DepartmentTestAnswer.test_result_id, DepartmentTestAnswer.question_number)
    )

    for test_result_id, qn, answer_text in ans_result.all():
        dept = id_to_dept.get(test_result_id)
        if not dept:
            continue
        dept_answers.setdefault(dept, {})[qn] = answer_text or ""

    return dept_answers


async def export_to_csv(out_path: Path) -> Path:
    config = load_config()
    db = Database(config)
    session = await db.get_session()
    try:
        # Готовим заголовки и файл
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = build_headers()

        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=",")
            writer.writerow(headers)

            # Получаем всех пользователей, у кого есть заявки (основной кейс)
            users_result = await session.execute(
                select(User.id, User.telegram_id, User.telegram_username)
                .join(Application, Application.user_id == User.id)
                .group_by(User.id, User.telegram_id, User.telegram_username)
                .order_by(User.id)
            )

            for user_id, tg_id, tg_username in users_result.all():
                # Базовые сущности
                application = await fetch_latest_application(session, user_id)
                stage2 = await fetch_stage2(session, user_id)
                dept_ans = await fetch_department_answers(session, user_id)

                # Первая часть строк
                tag = f"@{tg_username}" if tg_username else ""
                full_name = application.full_name if application else ""
                course = course_display(application.course if application else None)
                dorm = dorm_display(application.dormitory if application else None)
                univ = university_display(
                    application.is_from_vsm if application else None,
                    application.is_from_spbu if application else None,
                    application.university if application else None,
                )

                row: List[str] = [tag, full_name, course, dorm, univ]

                # Общие вопросы 1..6: сначала пробуем взять из единой системы (department='general'),
                # затем fallback на старую таблицу Stage2Answer
                general_from_unified = dept_ans.get("general") if dept_ans else None
                if general_from_unified:
                    row.extend([general_from_unified.get(i, "") for i in range(1, 7)])
                elif stage2:
                    row.extend([
                        stage2.general_q1_answer or "",
                        stage2.general_q2_answer or "",
                        stage2.general_q3_answer or "",
                        stage2.general_q4_answer or "",
                        stage2.general_q5_answer or "",
                        stage2.general_q6_answer or "",
                    ])
                else:
                    row.extend([""] * 6)

                # Отделы по заданному порядку, заполняем по номеру вопроса
                for dept_code, _dept_name, q_count in DEPARTMENTS_ORDER:
                    answers_map = dept_ans.get(dept_code, {})
                    for qn in range(1, q_count + 1):
                        row.append(answers_map.get(qn, ""))

                writer.writerow(row)

    finally:
        await session.close()
        await db.close()

    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Экспорт ответов этапа 2 и отделов в CSV")
    parser.add_argument(
        "--out",
        dest="out",
        default=None,
        help="Путь к выходному CSV (по умолчанию exports/answers_YYYYMMDD_HHMM.csv)",
    )
    return parser.parse_args()


async def amain():
    args = parse_args()
    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = Path("exports") / f"answers_{ts}.csv"

    result_path = await export_to_csv(out_path)
    print(f"CSV выгрузка создана: {result_path}")


if __name__ == "__main__":
    asyncio.run(amain())
