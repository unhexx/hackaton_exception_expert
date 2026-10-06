# .agent/PLAN.md

**Инициатива:** трек ЛЦТ, агрегатор ИТ-вакансий с профилем ФСП  
**Обновлено:** 2026-10-06  
**Маркер:** FSP-TOP5-ADVANTAGE-LOOP закрыт записью ТОП-5. Следующие прогоны — отдельные срезы ниже, не этот планировщик.

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

Не драться с FSP-QUALITY-RELEASE-LOOP (`01a110f2-01d7-7913-90e6-eb38f964e4f0`): золотой набор, теги, выгрузка на Bitbucket — только у него.

1. **Параллельно, сразу**
   - **T1 Тексты заданий.** Только `product/matching/templates/*.json` (+ опционально `vacancies/samples.json`). Не менять `template_id`, id вопросов, id вариантов, `correct`, пороги. Не трогать `golden/`.
   - **T2 Ранг потребности.** `product/matching/need.py`, `product/app/services/categories.py`, `product/tests/test_category.py`. Пустая потребность → прежний `rank_key`. `cases.json` не переписывать здесь.
   - **T4 Стенд и записка.** `track/lct-fsp-vacancies/03-open-questions.md` (Q9), `product/docs/zapiska.md` (схема антифрода/ATS, не отказ), подпись строк валидации в кабинете работодателя без смены `PlainTextResponse` пяти строк. Хост — вне git-секретов.
2. **Затем T3 Кабинеты.** Шаблоны и `brand.css`. Зависит от T2, чтобы карточка показала новый `list_reason`. Кнопка «Пригласить» с подстановкой id. Не править matching.
3. **T5 FSP-8**, только если T1–T4 закрыты примерно к 09.10. Файлы как в 05-reshenie FSP-8. Том sqlite удалить и поднять compose заново. `openapi.json` — перегенерация уже на `main`, не в ветке. `main.py` и `grade.py` не трогать. Адаптив — хвост `brand.css` после T3.
4. **Питч** не в этом цикле. Файл `product/docs/prezentaciya.pptx` трогать после 18.10, если команда в ТОП-10.

`product/openapi.json` параллельный срез не коммитит. `product/matching/golden/` и бейдж тестов — quality-release. Коммит локальный как Евгений Чистяков `<echistyakov@aq.ru>`. GitHub origin не пушить. Bitbucket — только у quality-release.

## Не пересоздавать

FSP-DEV-CYCLE-LOOP, FSP-DOCS-BADGES-LOOP, FSP-PITCH-DECK-LOOP, FSP-SCORE-RESEARCH-LOOP, FSP-DATA-STRATEGY-LOOP, FSP-QUALITY-RELEASE-LOOP, этот FSP-TOP5-ADVANTAGE-LOOP.
