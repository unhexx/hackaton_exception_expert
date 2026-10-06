"""Приглашение: вилка RUB, контакт компании сразу, почта только после принятия."""

from __future__ import annotations

from product.matching.grade import load_template
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


def _answers(template: dict, correct_n: int) -> list[str]:
    chosen = []
    for index, question in enumerate(template["questions"]):
        if index < correct_n:
            chosen.append(question["correct"])
        else:
            chosen.append(next(item["id"] for item in question["choices"] if item["id"] != question["correct"]))
    return chosen


def _candidate(client, email: str, **extra) -> int:
    register_and_confirm(client, email=email, role="candidate")
    saved = client.put("/api/candidate/profile", json={**_PROFILE, **extra})
    assert saved.status_code == 200, saved.text
    return saved.json()["profile_id"]


def _scored(client, email: str, **extra) -> int:
    profile_id = _candidate(client, email, **extra)
    started = client.post("/api/candidate/tests/start", json={})
    assert started.status_code == 201, started.text
    template = load_template(started.json()["template_id"])
    submitted = client.post(
        f"/api/candidate/tests/{started.json()['attempt_id']}/submit",
        json={"answers": _answers(template, 2)},
    )
    assert submitted.status_code == 200, submitted.text
    return profile_id


def _employer(client, email: str = "boss-offer@example.com", contact: str | None = None) -> None:
    register_and_confirm(client, email=email, role="employer")
    card = dict(_CARD)
    if contact is not None:
        card["contact"] = contact
    saved = client.put("/api/employer/company", json=card)
    assert saved.status_code == 200, saved.text


def _offer(profile_id: int, **extra) -> dict:
    body = {
        "profile_id": profile_id,
        "category_id": "backend:middle",
        "company_name": "Синтетика",
        "message": "Ищем backend middle в команду платежей",
        "salary_min": 180000,
        "salary_max": 250000,
        "salary_currency": "RUB",
        "contact_channel": "telegram: @sintetika",
    }
    body.update(extra)
    return body


def _csrf(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def test_offer_hides_email_until_accepted_and_keeps_company_contact(client):
    profile_id = _scored(client, "seeker-offer@example.com")
    _employer(client)
    denied = client.get("/api/candidate/offers")
    assert denied.status_code == 403
    assert denied.json()["error"] == "forbidden"
    created = client.post("/api/employer/offers", json=_offer(profile_id))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "sent"
    assert body["contact_channel"] == "telegram: @sintetika"
    assert body["salary_currency"] == "RUB"
    assert body["salary_max"] > body["salary_min"]
    assert "candidate_email" not in body
    assert "vacancy_id" not in body
    assert "seeker-offer@example.com" not in created.text
    again = client.post("/api/employer/offers", json=_offer(profile_id))
    assert again.status_code == 409
    assert again.json()["error"] == "offer_open"
    _login(client, "seeker-offer@example.com")
    listed = client.get("/api/candidate/offers")
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "sent"
    assert listed.json()[0]["contact_channel"] == "telegram: @sintetika"
    assert "candidate_email" not in listed.json()[0]
    peeked = client.get(f"/api/candidate/offers/{body['id']}")
    assert peeked.status_code == 200, peeked.text
    assert peeked.json()["status"] == "sent"
    opened = client.post(f"/api/candidate/offers/{body['id']}/open")
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "seen"
    assert "candidate_email" not in opened.json()
    _login(client, "boss-offer@example.com")
    waiting = client.get("/api/employer/offers").json()
    assert waiting[0]["status"] == "seen"
    assert waiting[0]["contact_channel"] == "telegram: @sintetika"
    assert "candidate_email" not in waiting[0]
    _login(client, "seeker-offer@example.com")
    accepted = client.post(f"/api/candidate/offers/{body['id']}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert "candidate_email" not in accepted.json()
    closed = client.post(f"/api/candidate/offers/{body['id']}/decline")
    assert closed.status_code == 409
    assert closed.json()["error"] == "offer_closed"
    _login(client, "boss-offer@example.com")
    shown = client.get("/api/employer/offers").json()
    assert shown[0]["candidate_email"] == "seeker-offer@example.com"
    assert shown[0]["contact_channel"] == "telegram: @sintetika"
    assert shown[0]["contact_channel"] != shown[0]["candidate_email"]


def test_offer_rejects_incomplete_range_and_foreign_profile(client):
    hidden = _scored(client, "hidden-offer@example.com", publication=False)
    plain = _candidate(client, "plain-offer@example.com")
    visible = _scored(client, "visible-offer@example.com")
    register_and_confirm(client, email="empty-co@example.com", role="employer")
    missing_card = client.post("/api/employer/offers", json=_offer(visible))
    assert missing_card.status_code == 422
    assert missing_card.json()["error"] == "company_name"
    _employer(client, email="boss-rules@example.com")
    assert client.post("/api/employer/offers", json=_offer(visible, message="  ")).json()["error"] == "offer_incomplete"
    assert client.post("/api/employer/offers", json=_offer(visible, salary_max=180000)).json()["error"] == "salary_range"
    assert client.post("/api/employer/offers", json=_offer(visible, salary_min="180000")).json()["error"] == "salary_range"
    assert client.post("/api/employer/offers", json=_offer(visible, salary_currency="USD")).json()["error"] == "currency"
    assert client.post("/api/employer/offers", json=_offer(visible, company_name="Другая")).json()["error"] == "company_name"
    mailed = client.post(
        "/api/employer/offers",
        json=_offer(visible, contact_channel="visible-offer@example.com"),
    )
    assert mailed.status_code == 422
    assert mailed.json()["error"] == "contact_channel"
    odd = client.post("/api/employer/offers", json=_offer(visible, category_id="it:middle"))
    assert odd.status_code == 422
    assert odd.json()["error"] == "category_id"
    foreign = client.post("/api/employer/offers", json=_offer(999999))
    assert foreign.status_code == 404
    assert foreign.json()["error"] == "profile_not_in_category"
    unpublished = client.post("/api/employer/offers", json=_offer(hidden))
    assert unpublished.status_code == 404
    assert unpublished.json()["error"] == "profile_not_in_category"
    untested = client.post("/api/employer/offers", json=_offer(plain))
    assert untested.status_code == 404
    other = client.post("/api/employer/offers", json=_offer(visible, category_id="frontend:middle"))
    assert other.status_code == 404
    assert other.json()["error"] == "profile_not_in_category"
    extra = client.post("/api/employer/offers", json={**_offer(visible), "vacancy_id": 5})
    assert extra.status_code == 422
    assert extra.json()["error"] == "extra_forbidden"
    _login(client, "visible-offer@example.com")
    assert client.post("/api/employer/offers", json=_offer(visible)).status_code == 403
    created = None
    _login(client, "boss-rules@example.com")
    created = client.post(
        "/api/employer/offers",
        json=_offer(visible, message="<script>alert(1)</script>"),
    )
    assert created.status_code == 201, created.text
    offer_id = created.json()["id"]
    _login(client, "visible-offer@example.com")
    direct = client.post(f"/api/candidate/offers/{offer_id}/decline")
    assert direct.status_code == 200
    assert direct.json()["status"] == "declined"
    _login(client, "boss-rules@example.com")
    fresh = client.post("/api/employer/offers", json=_offer(visible))
    assert fresh.status_code == 201, fresh.text
    _scored(client, "other-offer@example.com")
    assert client.get(f"/api/candidate/offers/{fresh.json()['id']}").status_code == 404
    _login(client, "boss-rules@example.com")
    assert client.post(f"/api/candidate/offers/{fresh.json()['id']}/accept").status_code == 403


def test_pages_show_contact_and_email_only_after_accept(client):
    profile_id = _scored(client, "page-seeker@example.com")
    register_and_confirm(client, email="page-boss@example.com", role="employer")
    bare = client.get("/employer/offers")
    assert bare.status_code == 200
    assert "disabled" in bare.text
    assert "Отправить приглашение" in bare.text
    saved = client.put("/api/employer/company", json=_CARD)
    assert saved.status_code == 200, saved.text
    form = client.get(
        "/employer/offers",
        params={"profile_id": str(profile_id), "category_id": "backend:middle"},
    )
    assert "telegram: @sintetika" in form.text
    assert "disabled" not in form.text
    assert "page-seeker@example.com" not in form.text
    assert f'type="hidden" value="{profile_id}"' in form.text
    sent = client.post(
        "/employer/offers",
        data={
            "csrf": _csrf(form.text),
            "profile_id": str(profile_id),
            "category_id": "backend:middle",
            "company_name": "Синтетика",
            "contact_channel": "telegram: @sintetika",
            "message": "<script>alert(1)</script>",
            "salary_min": "180000",
            "salary_max": "250000",
            "salary_currency": "RUB",
        },
        follow_redirects=False,
    )
    assert sent.status_code == 303
    listed = client.get("/employer/offers")
    assert "Способ связи компании: telegram: @sintetika" in listed.text
    assert "page-seeker@example.com" not in listed.text
    assert "<script>alert(1)</script>" not in listed.text
    assert "&lt;script&gt;" in listed.text
    _login(client, "page-seeker@example.com")
    page = client.get("/candidate/offers")
    assert "telegram: @sintetika" in page.text
    assert "page-seeker@example.com" not in page.text
    assert "Принять" in page.text
    offer_id = page.text.split("/candidate/offers/")[1].split('"')[0]
    prefetch = client.get(
        f"/candidate/offers/{offer_id}",
        headers={"sec-fetch-site": "cross-site"},
    )
    assert prefetch.status_code == 200
    assert "Статус: sent" in prefetch.text
    opened = client.get(f"/candidate/offers/{offer_id}")
    assert "Статус: seen" in opened.text
    accepted = client.post(
        f"/candidate/offers/{offer_id}/accept",
        data={"csrf": _csrf(opened.text)},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    _login(client, "page-boss@example.com")
    after = client.get("/employer/offers")
    assert "Почта соискателя: page-seeker@example.com" in after.text
    assert "Способ связи компании: telegram: @sintetika" in after.text


def test_shortlist_card_invites_with_profile_id(client):
    profile_id = _scored(client, "card-seeker@example.com")
    _employer(client, email="card-boss@example.com")
    listed = client.get("/employer/shortlist", params={"category_id": "backend:middle"})
    assert listed.status_code == 200
    assert f"Номер профиля: {profile_id}" in listed.text
    assert f"/employer/offers?profile_id={profile_id}&amp;category_id=backend:middle" in listed.text
    assert "Пригласить" in listed.text
    form = client.get(
        "/employer/offers",
        params={"profile_id": str(profile_id), "category_id": "backend:middle"},
    )
    assert form.status_code == 200
    assert f'id="profile_id" name="profile_id" type="hidden" value="{profile_id}"' in form.text
    assert 'id="category_id" name="category_id" type="hidden" value="backend:middle"' in form.text
    assert 'name="profile_id" type="number"' not in form.text
    bare = client.get("/employer/offers")
    assert 'name="profile_id"' not in bare.text
    assert "на карточке подборки" in bare.text
    _login(client, "card-seeker@example.com")
    cabinet = client.get("/candidate")
    assert cabinet.status_code == 200
    assert "История опроса" in cabinet.text
    assert "backend" in cabinet.text
    assert "middle" in cabinet.text
    assert "История теста" in cabinet.text
    assert "Публиковать профиль в подборке работодателя" in cabinet.text
    assert "Публиковать профиль и согласие на обработку" not in cabinet.text
