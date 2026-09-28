# Контракт ролей трека

Компетенции заказчика не подменяют роли цикла. Handoff по-прежнему валидируется схемой `schemas/handoff.schema.json`: `role` и `handoff_to` только `Orchestrator`, `Coder`, `Tester`, `Debugger`, `Reviewer`, `None`.

Компетенция пишется в дополнительное поле `track_role`. Схема дополнительные поля разрешает.

| track_role | Кто это | role в handoff | Куда сдаёт работу |
|------------|---------|----------------|-------------------|
| `product` | Product/project manager | `Orchestrator` | `Coder` или `Reviewer` |
| `backend` | Backend-developer | `Coder` | `Tester` |
| `frontend` | Frontend-developer | `Coder` | `Tester` |
| `matching` | Data Scientist / ML-engineer | `Coder` | `Tester` |
| `design` | UX/UI, опционально | `Coder` | `frontend` через `handoff_to=Coder` и `track_role` следующего шага в `context_delta` |

`Tester`, `Debugger`, `Reviewer` остаются общими. Они не становятся отдельными компетенциями заказчика. Reviewer проверяет демо-скрипт из требований, а не только тесты.

## Общие правила для всех пяти

- Источник поведения продукта — `01-requirements.md`. Текст постановки не пересказывать в коде и в ответах.
- Вопрос из `03-open-questions.md` не закрывать в коде. Если без ответа блокер, handoff `status=BLOCKED` и элемент в `clarification_questions`.
- Комментарии, сообщения коммитов и документы продукта — обычный русский, как у разработчика в этом репозитории.
- Чужие файлы не править. Владение путями объявляется в `owned_paths` handoff.
- Секреты и живые персональные данные в коммиты не попадают.
- Конец хода — один JSON handoff. После `}` текста нет.

## Поле handoff, общее для трека

```json
{
  "track_role": "backend",
  "owned_paths": ["services/fsp/"],
  "next_input_files": [
    "track/lct-fsp-vacancies/01-requirements.md",
    "track/lct-fsp-vacancies/roles/frontend.md"
  ]
}
```

`summary` — что стало истинным после хода, одной-двумя фразами. Не список намерений.
