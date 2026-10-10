"""Вакансия: вилка до вычета НДФЛ, отклик, почта только после принятия.

ТЗ §2.1 «Просмотр вакансий и отклик», «Публикация вакансий»; ТЗ §2.2 п.1–3.
"""

from __future__ import annotations

from product.tests.conftest import register_and_confirm

_PROFILE = {
    "full_name": "Иван Синтетиков",
    "industry": "it",
    "specialization": "backend",
    "grade": "middle",
    "stack": ["python"],
    "team_role": "разработчик",
    "work_format": "удалённо",
    "experience": "синтетический стаж",
    "soft_skills": ["коммуникация"],
    "publication": True,
}
_CARD = {
    "name": "Синтетика",
    "description": "Платежи",
    "direction": "backend",
    "contact": "telegram: @sintetika",
}


def _login(client, email: str) -> None:
    logged = client.post("/api/auth/login", json={"email": email, "password": "password-ok"})
    assert logged.status_code == 200, logged.text


def _candidate(client, email: str) -> int:
    register_and_confirm(client, email=email, role="candidate")
    saved = client.put("/api/candidate/profile", json=_PROFILE)
    assert saved.status_code == 200, saved.text
    return saved.json()["profile_id"]


def _employer(client, email: str = "boss-vacancy@example.com") -> None:
    register_and_confirm(client, email=email, role="employer")
    saved = client.put("/api/employer/company", json=_CARD)
    assert saved.status_code == 200, saved.text


def _vacancy(**extra) -> dict:
    body = {
        "title": "Backend middle",
        "description": "Платежи, без дежурств",
        "category_id": "backend:middle",
        "company_name": "Синтетика",
        "contact_channel": "telegram: @sintetika",
        "salary_min": 180000,
        "salary_max": 250000,
        "salary_currency": "RUB",
        "task_prompt": "Назовите один заголовок идемпотентного POST.",
    }
    body.update(extra)
    return body


def _csrf(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def test_vacancy_rejects_bad_range_and_hides_email_until_accept(client):
    register_and_confirm(client, email="bare-boss@example.com", role="employer")
    missing = client.post("/api/employer/vacancies", json=_vacancy())
    assert missing.status_code == 422
    assert missing.json()["error"] == "company_name"
    _employer(client)
    assert client.post("/api/employer/vacancies", json=_vacancy(salary_max=180000)).json()["error"] == "salary_range"
    assert client.post("/api/employer/vacancies", json=_vacancy(salary_max=10**30)).json()["error"] == "salary_range"
    assert client.post("/api/employer/vacancies", json=_vacancy(salary_min="180000")).json()["error"] == "salary_range"
    assert client.post("/api/employer/vacancies", json=_vacancy(salary_currency="USD")).json()["error"] == "currency"
    assert client.post("/api/employer/vacancies", json=_vacancy(category_id="it:middle")).json()["error"] == "category_id"
    assert client.post("/api/employer/vacancies", json=_vacancy(title="  ")).json()["error"] == "vacancy_title"
    odd = client.post("/api/employer/vacancies", json={**_vacancy(), "vacancy_id": 5})
    assert odd.status_code == 422
    assert odd.json()["error"] == "extra_forbidden"
    created = client.post("/api/employer/vacancies", json=_vacancy())
    assert created.status_code == 201, created.text
    ghost = client.post(f"/api/employer/applications/{10**30}/open")
    assert ghost.status_code == 404
    assert ghost.json()["error"] == "not_found"
    vacancy_id = created.json()["id"]
    assert created.json()["task_prompt"]
    assert "candidate_email" not in created.json()
    _candidate(client, "seeker-vacancy@example.com")
    denied = client.post("/api/employer/vacancies", json=_vacancy())
    assert denied.status_code == 403
    missing_vacancy = client.post(
        f"/api/vacancies/{10**30}/apply",
        json={"message": "Готов обсудить платежи"},
    )
    assert missing_vacancy.status_code == 404
    assert missing_vacancy.json()["error"] == "not_found"
    listed = client.get("/api/vacancies")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == vacancy_id
    assert "seeker-vacancy@example.com" not in listed.text
    empty = client.post(f"/api/vacancies/{vacancy_id}/apply", json={"message": "Готов"})
    assert empty.status_code == 422
    assert empty.json()["error"] == "task_answer"
    applied = client.post(
        f"/api/vacancies/{vacancy_id}/apply",
        json={"message": "Готов обсудить платежи", "task_answer": "Idempotency-Key"},
    )
    assert applied.status_code == 201, applied.text
    assert "candidate_email" not in applied.json()
    application_id = applied.json()["id"]
    again = client.post(
        f"/api/vacancies/{vacancy_id}/apply",
        json={"message": "Ещё раз", "task_answer": "Idempotency-Key"},
    )
    assert again.status_code == 409
    assert again.json()["error"] == "application_open"
    _login(client, "boss-vacancy@example.com")
    hidden = client.get("/api/employer/applications")
    assert hidden.status_code == 200
    assert "candidate_email" not in hidden.json()[0]
    assert "seeker-vacancy@example.com" not in hidden.text
    opened = client.post(f"/api/employer/applications/{application_id}/open")
    assert opened.status_code == 200
    assert opened.json()["status"] == "seen"
    assert "candidate_email" not in opened.json()
    accepted = client.post(f"/api/employer/applications/{application_id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["candidate_email"] == "seeker-vacancy@example.com"
    assert accepted.json()["contact_channel"] == "telegram: @sintetika"
    closed = client.post(f"/api/employer/applications/{application_id}/decline")
    assert closed.status_code == 409
    assert closed.json()["error"] == "application_closed"
    _candidate(client, "other-vacancy@example.com")
    foreign = client.post(f"/api/candidate/applications/{application_id}/decline")
    assert foreign.status_code == 404
    assert foreign.json()["error"] == "not_found"


def test_apply_without_profile_and_without_task(client):
    _employer(client, email="plain-boss@example.com")
    created = client.post("/api/employer/vacancies", json=_vacancy(task_prompt=None))
    assert created.status_code == 422
    body = _vacancy()
    del body["task_prompt"]
    created = client.post("/api/employer/vacancies", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["task_prompt"] == ""
    register_and_confirm(client, email="no-profile@example.com", role="candidate")
    missing = client.post(
        f"/api/vacancies/{created.json()['id']}/apply",
        json={"message": "Без анкеты"},
    )
    assert missing.status_code == 409
    assert missing.json()["error"] == "profile_required"
    _candidate(client, "with-profile@example.com")
    applied = client.post(
        f"/api/vacancies/{created.json()['id']}/apply",
        json={"message": "Без задания"},
    )
    assert applied.status_code == 201, applied.text
    withdrawn = client.post(f"/api/candidate/applications/{applied.json()['id']}/decline")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "declined"
    assert "candidate_email" not in withdrawn.json()


def test_pages_show_gross_fork_and_email_only_after_accept(client):
    register_and_confirm(client, email="page-boss-vac@example.com", role="employer")
    bare = client.get("/employer/vacancies")
    assert bare.status_code == 200
    assert "disabled" in bare.text
    saved = client.put("/api/employer/company", json=_CARD)
    assert saved.status_code == 200, saved.text
    form = client.get("/employer/vacancies")
    assert "Вилка от, руб. (до вычета НДФЛ)" in form.text
    assert "Вилка до, руб. (до вычета НДФЛ)" in form.text
    assert "Суммы до вычета НДФЛ." in form.text
    assert "нетто" not in form.text
    assert "на руки" not in form.text
    sent = client.post(
        "/employer/vacancies",
        data={
            "csrf": _csrf(form.text),
            "title": "Backend middle",
            "description": "Платежи",
            "category_id": "backend:middle",
            "company_name": "Синтетика",
            "contact_channel": "telegram: @sintetika",
            "salary_min": "180000",
            "salary_max": "250000",
            "salary_currency": "RUB",
            "task_prompt": "Один заголовок",
        },
        follow_redirects=False,
    )
    assert sent.status_code == 303
    _candidate(client, "page-seeker-vac@example.com")
    page = client.get("/candidate/vacancies")
    assert "до вычета НДФЛ" in page.text
    assert "нетто" not in page.text
    assert "на руки" not in page.text
    assert "page-seeker-vac@example.com" not in page.text
    assert "Один заголовок" in page.text
    vacancy_id = page.text.split("/candidate/vacancies/")[1].split("/")[0]
    applied = client.post(
        f"/candidate/vacancies/{vacancy_id}/apply",
        data={
            "csrf": _csrf(page.text),
            "message": "Готов",
            "task_answer": "Idempotency-Key",
        },
        follow_redirects=False,
    )
    assert applied.status_code == 303
    mine = client.get("/candidate/vacancies")
    assert "статус sent" in mine.text
    _login(client, "page-boss-vac@example.com")
    board = client.get("/employer/vacancies")
    assert "page-seeker-vac@example.com" not in board.text
    assert "до вычета НДФЛ" in board.text
    application_id = board.text.split("/employer/applications/")[1].split('"')[0]
    opened = client.get(f"/employer/applications/{application_id}", follow_redirects=False)
    assert opened.status_code == 303
    seen = client.get("/employer/vacancies")
    assert "статус seen" in seen.text
    assert "page-seeker-vac@example.com" not in seen.text
    accepted = client.post(
        f"/employer/applications/{application_id}/accept",
        data={"csrf": _csrf(seen.text)},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    after = client.get("/employer/vacancies")
    assert "Почта соискателя: page-seeker-vac@example.com" in after.text


def test_vacancy_form_double_minus_is_rejected_not_crashed(client):
    _employer(client, email="minus-vac-boss@example.com")
    form = client.get("/employer/vacancies")
    bad = client.post(
        "/employer/vacancies",
        data={
            "csrf": _csrf(form.text),
            "title": "Backend middle",
            "description": "Платежи",
            "category_id": "backend:middle",
            "company_name": "Синтетика",
            "contact_channel": "telegram: @sintetika",
            "salary_min": "180000",
            "salary_max": "--250000",
            "salary_currency": "RUB",
        },
    )
    assert bad.status_code == 422
    assert "целыми числами" in bad.text
