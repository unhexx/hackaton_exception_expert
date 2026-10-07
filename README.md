# Агрегатор ИТ-вакансий с профилем ФСП

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](product/pyproject.toml)
[![JavaScript](https://img.shields.io/badge/javascript-htmx_2.0.4-F7DF1E?style=flat-square&logo=javascript&logoColor=black)](product/app/static/htmx.min.js)
[![HTML](https://img.shields.io/badge/html-Jinja2-E34F26?style=flat-square&logo=html5&logoColor=white)](product/app/templates)
[![CSS](https://img.shields.io/badge/css-brand-1572B6?style=flat-square&logo=css3&logoColor=white)](product/app/static/brand.css)
[![SQL](https://img.shields.io/badge/sql-SQLite_WAL-003B57?style=flat-square&logo=sqlite&logoColor=white)](product/app/db)
[![Shell](https://img.shields.io/badge/shell-POSIX-4EAA25?style=flat-square&logo=gnubash&logoColor=white)](deploy/fsp/entrypoint.sh)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](product/pyproject.toml)
[![Docker Compose](https://img.shields.io/badge/stand-Docker_Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](deploy/fsp/compose.yaml)
[![Тесты](product/docs/badges/tests.svg)](deploy/fsp/compose.yaml)
[![Шрифт OFL](https://img.shields.io/badge/font-OFL_1.1-lightgrey?style=flat-square)](product/static/fonts/OFL.txt)

Спецтрек ЛЦТ, Федерация спортивного программирования.

Авторы: Чистяков Евгений, Иван Курлыков, Леонид Пластуненко, Николай Кузнецов, Игорь Софронов.

Прототип: кабинеты соискателя и работодателя, категория из специализации и грейда, тест грейда, разбор текстового PDF, приглашение с вилкой в рублях и контактом компании, вакансия работодателя с откликом и одним коротким заданием. Боевого реестра ФСП на стенде нет.

## Быстрый старт

На машине заранее стоят только Docker Engine и плагин Compose. Язык, пакеты и база на хост не ставятся. Полный `up` поднимает и локальный Keycloak. Почта остаётся входом, связь ID — кнопка в кабинете. Переключение на issuer заказчика — [`deploy/fsp/keycloak.md`](deploy/fsp/keycloak.md). Копировать `compose.env` не нужно: если `PRODUCT_SECRET` короче 32 символов, точка входа пишет секрет в том `/data/product_secret`.

```text
docker compose -f deploy/fsp/compose.yaml up --build
```

| Что | Адрес |
| --- | --- |
| Кабинеты | <http://127.0.0.1:8000> |
| Консоль Keycloak | <http://127.0.0.1:8080> |
| OpenAPI, без сети | <http://127.0.0.1:8000/docs> |
| ReDoc, без сети | <http://127.0.0.1:8000/redoc> |

```text
docker compose -f deploy/fsp/compose.yaml --profile test run --rm tests
```

Бейдж «tests» в шапке пишет этот прогон: зелёный, если все тесты прошли.

Подробности — в [`product/README.md`](product/README.md).
