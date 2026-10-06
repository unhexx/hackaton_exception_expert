# .agent/PLAN.md

**Инициатива:** трек ЛЦТ, агрегатор ИТ-вакансий с профилем ФСП  
**Обновлено:** 2026-10-06  
**Маркер:** FSP-T123-DEV-LOOP. Активные срезы этого прогона — T1, T2, T3. T4 и T5 не брать. FSP-TOP5-ADVANTAGE-LOOP закрыт записью ТОП-5.

## Фаза

Контракт и стек зафиксированы. Обязательные FSP-1…FSP-7 и обязательная часть FSP-6 на `main` закрыты. Окно кода 05–11.10.2026. Стоп-код 11.10.2026, 23:59 МСК. Экспертиза 12–18.10. ТОП-10 — 18.10.2026. Очный финал 30.10.2026 в Москве.

Требования: `track/lct-fsp-vacancies/`. Решение, по которому пишется код: `track/lct-fsp-vacancies/05-reshenie.md`. Стек в этом плане не переоткрывается: Python 3.12, Jinja2 + локальный htmx, FastAPI, один SQLite WAL. Запуск только `docker compose -f deploy/fsp/compose.yaml up --build`. Кабинеты 127.0.0.1:8000. Порты 8100/8110 не занимать. `product/matching/` остаётся чистым.

Публичный ТОП-5 без внутренних ролей — в `track/lct-fsp-vacancies/04-plan.md`, раздел «Пять доработок до стоп-кода».

## Срезы каркаса

| ID | Статус |
|----|--------|
| FSP-1 Каркас кабинетов | DONE |
| FSP-2 Мок достижений | DONE |
| FSP-3 Категория v1 | DONE |
| FSP-7 Тест грейда | DONE |
| FSP-4 Разбор резюме | DONE |
| FSP-5 Предложение | DONE |
| FSP-6 Стенд и записка | DONE |
| FSP-8 Дополнительный функционал | OPTIONAL, не открыт; см. T5 |

## ТОП-5 до стоп-кода (ожидаемый вклад в оценку)

Для отбора 12–18.10 питч 10% не входит. Веса: подбор 35, тест 25, UI 10, техника 7, полнота 6, доп. 7.

| # | Доработка | Тип | Вес | Владелец файлов |
|---|-----------|-----|-----|-----------------|
| 1 | Содержательные задания теста | полировка FSP-7 | 25% | matching: только `product/matching/templates/*.json` и при нужде `vacancies/samples.json` |
| 2 | Соответствие потребности в выдаче | полировка FSP-3 | 35% | matching `need.py`; backend `app/services/categories.py`, `tests/test_category.py` |
| 3 | Приглашение с карточки подборки | полировка FSP-5 / кабинеты | 10%+35% демо | frontend: `app/templates/**`, `brand.css`, `app/web/{shortlist,offers_pages}.py` |
| 4 | Публичный стенд и концепция антифрода | полировка FSP-6, Q9 | 6%+7% + концепт 7% | product: `zapiska.md`, `03-open-questions.md`, README при URL |
| 5 | Свои вакансии и отклик | reopen FSP-8 | 7% | backend+frontend по списку FSP-8 в 05-reshenie.md |

Не открывать и не рекомендовать в этом окне: React, Postgres, Keycloak, живой ATS/webhook, ИНН/ЕГРЮЛ, мастер оффера, слоты созвона, разряд→KPI, ESCO/O*NET, NDCG/каппа, зашитый Precision@3.

## Порядок прогонов (непересекающиеся владельцы)

Этот прогон закрывает T1, T2 и T3. Золотой набор `product/matching/golden/` не расширять, ключи ответов не менять. Теги `v1.0.0` не двигать.

1. **T1 Тексты заданий — сделано.** Только `product/matching/templates/*.json` (+ опционально `vacancies/samples.json`). Не менять `template_id`, id вопросов, id вариантов, `correct`, пороги. Не трогать `golden/`.
2. **T2 Ранг потребности — сделано.** `product/matching/need.py`, `product/app/services/categories.py`, `product/tests/test_category.py`, сортировка в `golden_run.py` тем же предикатом. Пустая потребность → прежний `rank_key`. `cases.json` не переписывать здесь.
3. **T3 Кабинеты — сделано.** `app/templates/**`, `brand.css`, `app/web/{shortlist,offers_pages,candidate}.py`, `tests/test_offers.py`. Кнопка «Пригласить» с подстановкой id. Не править matching, кроме уже сделанного T2.
4. **T4 Стенд и записка — не этот прогон.**
5. **T5 FSP-8 — не этот прогон.** Только если T1–T4 закрыты примерно к 09.10.

`product/openapi.json` этот срез не коммитит, если схема не менялась. GitHub origin `unhexx/agentic_loop_template` не пушить. Коммиты этого прогона — `exception.expert <jenyach@exception.expert>`, после `main` — выгрузка на spectrack-10-26.

## Не пересоздавать

FSP-DEV-CYCLE-LOOP, FSP-DOCS-BADGES-LOOP, FSP-PITCH-DECK-LOOP, FSP-SCORE-RESEARCH-LOOP, FSP-DATA-STRATEGY-LOOP, FSP-QUALITY-RELEASE-LOOP, этот FSP-TOP5-ADVANTAGE-LOOP.
