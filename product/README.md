# Агрегатор ИТ-вакансий ФСП

Стенд рассчитан на машину, где заранее стоят только Docker Engine и плагин Compose. Язык, пакеты и база на хост не ставятся. Keycloak не входит в стенд.

Один раз скопируйте `deploy/fsp/compose.env.example` в `deploy/fsp/compose.env` и запишите туда `PRODUCT_SECRET` не короче 32 символов. Файл с секретом в git не входит. Это подготовка, не второй способ запуска.

Команда стенда:

```text
docker compose -f deploy/fsp/compose.yaml up --build
```

Кабинеты открываются в браузере на `http://127.0.0.1:8000`. Описание API без сети: `http://127.0.0.1:8000/docs`. Прогон валидации — ссылка «Прогон валидации» в подборке работодателя, один раз после четырёх шагов сценария из `track/lct-fsp-vacancies/demo.md`.

Проверка тестов тем же compose:

```text
docker compose -f deploy/fsp/compose.yaml --profile test run --rm tests
```
