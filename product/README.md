# Агрегатор ИТ-вакансий ФСП

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](pyproject.toml)
[![Docker Compose](https://img.shields.io/badge/stand-Docker_Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](../deploy/fsp/compose.yaml)
[![Тесты](https://img.shields.io/badge/tests-compose_profile_test-0A3069?style=flat-square)](../deploy/fsp/compose.yaml)
[![Шрифт OFL](https://img.shields.io/badge/font-OFL_1.1-lightgrey?style=flat-square)](static/fonts/OFL.txt)

Прототип спецтрека ЛЦТ: работодатель открывает категорию людей с записанным грейдом и профилем достижений Федерации спортивного программирования, затем сам шлёт приглашение с вилкой в рублях.

Кабинеты соискателя и работодателя живут в одном процессе. Боевого реестра ФСП на стенде нет: достижения читаются из JSON в git.

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

Второго способа (venv и pytest на хосте) нет. Свой `PRODUCT_SECRET` можно положить в `deploy/fsp/compose.env` по образцу `compose.env.example`; файл в git не входит.

Прогон валидации — ссылка «Прогон валидации» в подборке работодателя. Один раз после четырёх шагов из [`track/lct-fsp-vacancies/demo.md`](../track/lct-fsp-vacancies/demo.md). Ответ — пять строк этого запуска, не целевые проценты.

## Как устроено

Один процесс uvicorn, один worker, один файл SQLite в режиме WAL.

- Веб: Jinja2 и локальный htmx 2.0.4. Страницы `/auth`, `/candidate`, `/employer`. Ссылок на CDN нет.
- API: FastAPI, JSON под `/api`, сессия — cookie `product_session`.
- Правила категории, теста и разбора резюме — функции в `product/matching`. Сеть им не нужна.
- Мок достижений — `product/fsp_mock`, читает `participants.json` из git.

Категория — специализация и записанный грейд, например `backend:middle`. Отрасль MVP только `it`: она видна в статусе профиля и в `category_id` не входит. Неудачный тест грейд не понижает.

Приглашение работодатель пишет сам: текст, название компании, способ связи компании и вилка в рублях. Способ связи компании соискатель видит сразу. Почта соискателя появляется у работодателя только после `accepted`.

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

Свои вакансии, отклик соискателя и короткое задание работодателя — необязательный хвост и этот стенд не блокируют. Нет модерации чужих досок, нет выгрузки в ATS, нет проверки ИНН и корпоративной почты, нет перевода разряда ФСП в KPI.
