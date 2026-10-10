"""Синтетические кандидаты с известным «истинным» грейдом.

ТЗ §2: «готовых датасетов нет — команда работает на собственных данных,
синтетических… и предлагает собственную процедуру оценки». На Q&A: жюри
проверит тест на своём закрытом наборе синтетических профилей. Здесь — наш
открытый набор того же рода.

Файлы ``data/candidates.csv`` и ``data/candidates.json`` содержат одно и то же
и рассчитаны на ручной перенос в другую версию кода: плоские поля, UTF-8,
без ссылок на внутренние таблицы проекта.

Поля кандидата:

    candidate_id    sim-0001 … sim-0500 — стабильный ключ
    display_name    вымышленное имя (явно синтетическое)
    email           sim-0001@example.com — домен для примеров, писем не будет
    industry        it (как в правилах v1 проекта)
    specialization  backend | frontend | mobile | data | security | devops
    true_grade      ИСТИННЫЙ грейд — эталон для проверки, тесту не сообщается
    theta           истинный уровень на шкале scale.py (внутри интервала true_grade)
    declared_grade  грейд, на который кандидат заявился сам (ТЗ: «самостоятельный
                    выбор предполагаемого грейда»): 60% честно, 25% на ступень выше,
                    15% на ступень ниже
    team_role, work_format, stack — поля анкеты проекта (для импорта в кабинет)
    fsp_external_id пусто: история ФСП в этом наборе не используется

В CSV список ``stack`` записан через «;».
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from product.validation_sim.scale import GRADES, band

SCHEMA_VERSION = 1
DATA_DIR = Path(__file__).resolve().parent / "data"
CSV_PATH = DATA_DIR / "candidates.csv"
JSON_PATH = DATA_DIR / "candidates.json"

FIELDS = (
    "candidate_id", "display_name", "email", "industry", "specialization",
    "true_grade", "theta", "declared_grade", "team_role", "work_format", "stack",
    "fsp_external_id",
)

SPECIALIZATIONS = ("backend", "frontend", "mobile", "data", "security", "devops")

# Доля истинных грейдов: начинающих больше, лидов меньше — как на рынке.
GRADE_SHARE = {"junior": 0.35, "middle": 0.30, "senior": 0.22, "lead": 0.13}

# Типичный стек по специализации (значения из rules/v1.json проекта).
STACK_BY_SPEC = {
    "backend": ["python", "java", "go", "sql", "docker"],
    "frontend": ["javascript", "typescript"],
    "mobile": ["kotlin", "swift"],
    "data": ["python", "sql"],
    "security": ["linux", "python", "go"],
    "devops": ["linux", "docker", "go", "python"],
}
WORK_FORMATS = ("офис", "удалённо", "гибрид")


def _declared(rng: random.Random, true_grade: str) -> str:
    """Грейд, который кандидат выбирает сам. Часть переоценивает себя, часть — недооценивает."""
    index = GRADES.index(true_grade)
    roll = rng.random()
    if roll < 0.25 and index < len(GRADES) - 1:
        return GRADES[index + 1]
    if roll < 0.40 and index > 0:
        return GRADES[index - 1]
    return true_grade


def generate(n: int = 500, seed: int = 2026) -> list[dict]:
    """n кандидатов, детерминированно по seed."""
    rng = random.Random(seed)
    grades = list(GRADE_SHARE)
    weights = list(GRADE_SHARE.values())
    rows = []
    for i in range(1, n + 1):
        spec = SPECIALIZATIONS[(i - 1) % len(SPECIALIZATIONS)]  # поровну по специализациям
        true_grade = rng.choices(grades, weights)[0]
        lo, hi = band(true_grade)
        theta = round(rng.uniform(lo, hi), 3)
        if true_grade == "lead" or (true_grade == "senior" and rng.random() < 0.3):
            role = "тимлид"
        elif spec == "data" and rng.random() < 0.5:
            role = "аналитик"
        else:
            role = "разработчик"
        pool = STACK_BY_SPEC[spec]
        stack = sorted(rng.sample(pool, k=min(len(pool), rng.randint(1, 3))))
        rows.append(
            {
                "candidate_id": f"sim-{i:04d}",
                "display_name": f"Синтетический кандидат {i:04d}",
                "email": f"sim-{i:04d}@example.com",
                "industry": "it",
                "specialization": spec,
                "true_grade": true_grade,
                "theta": theta,
                "declared_grade": _declared(rng, true_grade),
                "team_role": role,
                "work_format": rng.choice(WORK_FORMATS),
                "stack": stack,
                "fsp_external_id": "",
            }
        )
    return rows


def save(rows: list[dict], seed: int, csv_path: Path = CSV_PATH, json_path: Path = JSON_PATH) -> None:
    """Пишет оба формата. JSON — с метаданными, CSV — плоская таблица для Excel."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "count": len(rows),
        "note": "Синтетические профили для валидации теста. true_grade и theta — эталон, не показывать в продукте.",
        "fields": list(FIELDS),
        "candidates": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    # utf-8-sig: Excel на Windows сразу видит кириллицу
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "stack": ";".join(row["stack"])})


def load(path: Path = JSON_PATH) -> list[dict]:
    """Читает JSON или CSV (по расширению) и приводит типы."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["candidates"]
    else:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            row["stack"] = [item for item in row["stack"].split(";") if item]
    for row in rows:
        row["theta"] = float(row["theta"])
        if row["true_grade"] not in GRADES or row["declared_grade"] not in GRADES:
            raise ValueError(f"{row['candidate_id']}: неизвестный грейд")
    return rows
