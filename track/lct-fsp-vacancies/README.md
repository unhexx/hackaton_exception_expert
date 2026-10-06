# Трек ЛЦТ: агрегатор ИТ-вакансий с профилем ФСП

Документы постановки, требований и устройства прототипа. Код — в [`product/`](../../product/README.md). Стенд поднимается одной командой из корня репозитория:

```text
docker compose -f deploy/fsp/compose.yaml up --build
```

Кабинеты: <http://127.0.0.1:8000>. Тесты — тем же файлом compose, профилем `test`.

| Файл | Что в нём лежит |
|------|-----------------|
| [00-postanovka.md](00-postanovka.md) | Текст заказчика и полный перечень требований ТЗ без исключений |
| [01-requirements.md](01-requirements.md) | Как требования постановки садятся на прототип |
| [02-domain.md](02-domain.md) | Открытые факты о ФСП и ЛЦТ. Не путать с постановкой |
| [03-open-questions.md](03-open-questions.md) | Вопросы модератору и экспертам. Не закрывать молча |
| [04-plan.md](04-plan.md) | Срезы работ на окно 05–11.10.2026 |
| [05-reshenie.md](05-reshenie.md) | Стек и устройство прототипа. Требования не копирует |
| [demo.md](demo.md) | Сквозной сценарий приёмки на стенде |

Роли цикла: [product](roles/product.md), [backend](roles/backend.md), [frontend](roles/frontend.md), [matching](roles/matching.md), [design](roles/design.md). Контракт компетенций: [roles/CONTRACT.md](roles/CONTRACT.md).

Цикл читает `TASK_SPECIFICATION.md` и этот каталог. Шаблон Agentix 3.13.0 остаётся в репозитории как обвязка, не как продукт трека. Прежняя спецификация шаблона: `docs/archive/TASK_SPECIFICATION-agentix-3.13.md`.
