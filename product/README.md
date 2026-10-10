# Агрегатор ИТ-вакансий ФСП

[![Python 3.12](docs/badges/python.svg)](pyproject.toml)
[![JavaScript](docs/badges/javascript.svg)](app/static/htmx.min.js)
[![HTML](docs/badges/html.svg)](app/templates)
[![CSS](docs/badges/css.svg)](app/static/brand.css)
[![SQL](docs/badges/sql.svg)](app/db)
[![Shell](docs/badges/shell.svg)](../deploy/fsp/entrypoint.sh)
[![FastAPI](docs/badges/fastapi.svg)](pyproject.toml)
[![Docker Compose](docs/badges/docker.svg)](../deploy/fsp/compose.yaml)
[![Тесты](docs/badges/tests.svg)](../deploy/fsp/compose.yaml)
[![Шрифт OFL](docs/badges/ofl.svg)](static/fonts/OFL.txt)

Прототип спецтрека ЛЦТ: работодатель открывает категорию людей с записанным грейдом и профилем достижений Федерации спортивного программирования, затем сам шлёт приглашение с вилкой в рублях.

Авторы: Чистяков Евгений, Иван Курлыков, Леонид Пластуненко, Николай Кузнецов, Игорь Софронов.

Кабинеты соискателя и работодателя живут в одном процессе. Боевого реестра ФСП на стенде нет: JSON из git при старте попадает в SQLite, кабинеты читают таблицы.

## Быстрый старт

На машине заранее стоят только Docker Engine и плагин Compose. Язык, пакеты и база на хост не ставятся. Keycloak в стенд не входит. Копировать `compose.env` не нужно: если `PRODUCT_SECRET` короче 32 символов, точка входа пишет секрет в том `/data/product_secret`.

Из корня репозитория:

```text
docker compose -f deploy/fsp/compose.yaml up --build
```

| Что | Адрес |
| --- | --- |
| Кабинеты | <http://127.0.0.1:8000> |
| OpenAPI, без сети | <http://127.0.0.1:8000/docs> |
| ReDoc, без сети | <http://127.0.0.1:8000/redoc> |

Вторая команда — тесты тем же образом, отдельным контейнером:

```text
docker compose -f deploy/fsp/compose.yaml --profile test run --rm tests
```

Второго способа (venv и pytest на хосте) нет. Бейдж «tests» в шапке — снимок последнего прогона этой команды: зелёный, если все тесты прошли. Файл пишет `pytest_sessionfinish` в `docs/badges`. Свой `PRODUCT_SECRET` можно положить в `deploy/fsp/compose.env` по образцу `compose.env.example`; файл в git не входит. Точка входа и приложение читают один контур: переменная или `PRODUCT_SECRET_FILE`.

Публичного URL нет. Кабинеты после compose — <http://127.0.0.1:8000>. Хост не выдумываем: без Docker смотрите скрины и видео презентации.

Прогон валидации — ссылка «Прогон валидации» в подборке работодателя. Один раз после четырёх шагов из [`track/lct-fsp-vacancies/demo.md`](../track/lct-fsp-vacancies/demo.md). Ответ — пять золотых строк, `grade_separation` и три строки CPU-персон (`sim_competent`, `sim_key_leak`, `sim_adjacent`); целевых процентов нет. Это CPU, без GPU. `category_match` — ожидаемая категория, `outcome_match` — итог теста, `template_stable` — тот же шаблон и те же ответы дали тот же грейд, `relevant_in_top` — отмеченные релевантными в топе, `resume_ok` — PDF без падения. `grade_separation` — сколько пунктов разделяют грейды и сколько пунктов в стемах; порога по этой строке нет. По трём `sim_*` порога тоже нет. Отдельно `python -m product.matching.synth_eval_run` печатает те же девять строк на 1000 синтетических профилей с известным грейдом; GET остаётся золотым набором 38, график — [`docs/synth-eval.svg`](docs/synth-eval.svg).

## Как устроено

Один процесс uvicorn, один worker, один файл SQLite в режиме WAL.

- Веб: Jinja2 и локальный htmx 2.0.4. Страницы `/auth`, `/candidate`, `/employer`. Ссылок на CDN нет.
- API: FastAPI, JSON под `/api`, сессия — cookie `product_session`.
- Правила категории, теста и разбора резюме — функции в `product/matching`. Сеть им не нужна.
- Мок достижений — `product/fsp_mock` кладёт `participants.json` в SQLite при старте.

Каталог теста: 72 шаблона и 216 вопросов, буква c на каждой паре, три вопроса семейств `refusal_contract`, `close_cause`, `offline_check`, пороги 50 и 80, четвёртого шаблона нет. Вариант выбирает `select_template` по `profile_id` и `rule_version`. Ключи в этом документе не публикуются.

Категория — специализация и записанный грейд, например `backend:middle`. Отрасль MVP только `it`: она видна в статусе профиля и в `category_id` не входит. Неудачный тест грейд не понижает.

Приглашение работодатель пишет с карточки подборки: номер профиля подставляется скрытым полем. В форме — текст, название компании, способ связи компании и вилка в рублях. Способ связи компании соискатель видит сразу. Почта соискателя появляется у работодателя только после `accepted`.

## Документы

| Файл | Содержание |
| --- | --- |
| [Сопроводительная записка](docs/zapiska.md) | Архитектура, тест, подбор, валидация, библиотеки |
| [Демо-скрипт](../track/lct-fsp-vacancies/demo.md) | Четыре шага приёмки и один прогон |
| [Требования](../track/lct-fsp-vacancies/01-requirements.md) | Что можно реализовывать |
| [Устройство](../track/lct-fsp-vacancies/05-reshenie.md) | Стек, каталоги, границы |
| [OpenAPI](openapi.json) | Методы, тела, ошибки |

## Лицензии стека

То, что лежит в дереве продукта, не выдуманные бейджи:

| Компонент | Лицензия | Где в дереве |
| --- | --- | --- |
| JetBrains Mono | SIL Open Font License 1.1 | [`static/fonts/OFL.txt`](static/fonts/OFL.txt) |
| htmx 2.0.4 | Zero-Clause BSD | [`app/static/htmx.LICENSE`](app/static/htmx.LICENSE) |
| Swagger UI 5.33.1 | Apache-2.0 | [`app/static/docs/swagger-ui.LICENSE`](app/static/docs/swagger-ui.LICENSE) |
| ReDoc 2.5.4 | MIT | [`app/static/docs/redoc.standalone.js.LICENSE`](app/static/docs/redoc.standalone.js.LICENSE) |

Прямые пакеты Python — в [`pyproject.toml`](pyproject.toml), заморозка образа — в [`requirements.lock`](requirements.lock).

## Что сознательно не входит

Публичного URL нет. Свои вакансии, отклик соискателя и короткое задание работодателя — необязательный хвост и этот стенд не блокируют. Нет живого вебхука ATS, нет проверки ИНН и корпоративной почты, нет перевода разряда ФСП в KPI. Концепция очереди модерации и снимка для ATS — в записке.
