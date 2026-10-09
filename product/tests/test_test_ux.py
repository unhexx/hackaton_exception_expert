"""HTML сдачи теста: поочерёдный T/F, дорожка шага и панель итога."""

from __future__ import annotations

import re
import sqlite3

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

_HX = {"HX-Request": "true"}
_MARK_NAMES = tuple(f"mark_{q}_{cid}" for q in range(3) for cid in "abc")
_ECHO_NAMES = ("step", *_MARK_NAMES, "answer_0", "answer_1", "answer_2")


def _seeker(client, email: str = "ux@example.com", **extra) -> int:
    register_and_confirm(client, email=email, role="candidate")
    saved = client.put("/api/candidate/profile", json={**_PROFILE, **extra})
    assert saved.status_code == 200, saved.text
    return saved.json()["profile_id"]


def _csrf(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def _hidden(html: str, name: str) -> str:
    match = re.search(rf'name="{re.escape(name)}" value="([^"]*)"', html)
    assert match is not None, name
    return match.group(1)


def _echo(html: str) -> dict[str, str]:
    return {name: _hidden(html, name) for name in _ECHO_NAMES}


def _noscript(html: str) -> str:
    match = re.search(r"<noscript>(.*?)</noscript>", html, flags=re.S | re.I)
    assert match is not None
    return match.group(1)


def _outside_noscript(html: str) -> str:
    return re.sub(r"<noscript>.*?</noscript>", "", html, flags=re.S | re.I)


def _status(client, attempt_id: int) -> str:
    with sqlite3.connect(client.db_path) as db:
        return db.execute("select status from test_attempts where id = ?", (attempt_id,)).fetchone()[0]


def _set_stamp(client, profile_id: int, stamp: str) -> None:
    with sqlite3.connect(client.db_path) as db:
        db.execute("update profiles set grade_changed_at = ? where id = ?", (stamp, profile_id))
        db.commit()


def _answers(template: dict, correct_n: int) -> list[str]:
    chosen = []
    for index, question in enumerate(template["questions"]):
        if index < correct_n:
            chosen.append(question["correct"])
        else:
            chosen.append(next(choice["id"] for choice in question["choices"] if choice["id"] != question["correct"]))
    return chosen


def _submit(client, attempt_id: int, answers: list[str]):
    return client.post(f"/api/candidate/tests/{attempt_id}/submit", json={"answers": answers})


def _key_marks(template: dict) -> dict[str, str]:
    data = {}
    for question_index, question in enumerate(template["questions"]):
        correct = question["correct"]
        for cid in "abc":
            data[f"mark_{question_index}_{cid}"] = "true" if cid == correct else "false"
    return data


def _open_draft(client, email: str):
    _seeker(client, email)
    started = client.post("/api/candidate/tests/start", json={})
    assert started.status_code == 201, started.text
    page = client.get("/candidate/test")
    assert page.status_code == 200
    body = started.json()
    return body, page, load_template(body["template_id"])


def _post_step(client, csrf: str, attempt_id: int, html: str | None = None, **extra):
    data = {"csrf": csrf, "attempt_id": str(attempt_id)}
    if html is not None:
        data.update(_echo(html))
    data.update(extra)
    return client.post("/candidate/test/step", data=data, headers=_HX)


def test_draft_page_keeps_nine_mark_pairs_inside_noscript(client):
    body, page, _template = _open_draft(client, "ux-noscript@example.com")
    noscript = _noscript(page.text)
    outside = _outside_noscript(page.text)
    assert 'id="test-step"' in page.text
    assert "Загрузка шага…" not in page.text
    assert 'name="mark_0_a"' in noscript
    for name in _MARK_NAMES:
        assert f'name="{name}"' in noscript
        assert f'name="{name}"' not in outside
        assert f'name="{name}"' in noscript and 'value="true"' in noscript
        assert 'value="false"' in noscript
    assert 'type="radio"' not in outside
    assert body["questions"][0]["text"] in noscript
    assert "На вопрос нужна ровно одна отметка «истинен»." in page.text


def test_submit_nine_key_marks_scores_100(client):
    body, page, template = _open_draft(client, "ux-marks-ok@example.com")
    sent = client.post(
        "/candidate/test/submit",
        data={
            "csrf": _csrf(page.text),
            "attempt_id": str(body["attempt_id"]),
            **_key_marks(template),
        },
        follow_redirects=False,
    )
    assert sent.status_code == 303
    again = client.get("/candidate/test")
    assert "балл 100" in again.text
    assert _status(client, body["attempt_id"]) == "submitted"


def test_submit_all_false_keeps_draft(client):
    body, page, _template = _open_draft(client, "ux-all-false@example.com")
    sent = client.post(
        "/candidate/test/submit",
        data={
            "csrf": _csrf(page.text),
            "attempt_id": str(body["attempt_id"]),
            **{name: "false" for name in _MARK_NAMES},
        },
        follow_redirects=False,
    )
    assert sent.status_code == 422
    assert "answer_unknown" in sent.text or "Ответ не из вариантов" in sent.text
    assert _status(client, body["attempt_id"]) == "draft"


def test_submit_two_trues_on_first_keeps_draft(client):
    body, page, template = _open_draft(client, "ux-two-true@example.com")
    marks = _key_marks(template)
    marks["mark_0_a"] = "true"
    marks["mark_0_b"] = "true"
    sent = client.post(
        "/candidate/test/submit",
        data={
            "csrf": _csrf(page.text),
            "attempt_id": str(body["attempt_id"]),
            **marks,
        },
        follow_redirects=False,
    )
    assert sent.status_code == 422
    assert "answer_unknown" in sent.text or "Ответ не из вариантов" in sent.text
    assert _status(client, body["attempt_id"]) == "draft"


def test_step_load_without_step_shows_first_stem(client):
    body, page, template = _open_draft(client, "ux-load@example.com")
    frag = _post_step(client, _csrf(page.text), body["attempt_id"])
    assert frag.status_code == 200
    assert "История" not in frag.text
    assert "<h1>Тест грейда</h1>" not in frag.text
    assert "вопрос 1 из 3" in frag.text
    assert ", вариант" not in frag.text
    assert _hidden(frag.text, "step") == "0"
    stem = template["questions"][0]["text"]
    assert stem in frag.text
    for choice in template["questions"][0]["choices"]:
        assert choice["text"] not in frag.text


def test_step_walks_question_one_and_assembles_letter(client):
    body, page, template = _open_draft(client, "ux-walk@example.com")
    csrf = _csrf(page.text)
    attempt_id = body["attempt_id"]
    q1 = template["questions"][0]
    texts = {choice["id"]: choice["text"] for choice in q1["choices"]}
    load = _post_step(client, csrf, attempt_id)
    assert q1["text"] in load.text
    for text in texts.values():
        assert text not in load.text
    opt_a = _post_step(client, csrf, attempt_id, load.text, step="0", advance="1")
    assert "вариант 1 из 3" in opt_a.text
    assert q1["text"] in opt_a.text
    assert texts["a"] in opt_a.text
    assert texts["b"] not in opt_a.text
    assert texts["c"] not in opt_a.text
    assert "Верно" in opt_a.text
    assert "Не верно" in opt_a.text
    assert ">истинен<" not in opt_a.text
    assert ">ложен<" not in opt_a.text
    opt_b = _post_step(client, csrf, attempt_id, opt_a.text, step="1", mark="true")
    assert q1["text"] in opt_b.text
    assert texts["b"] in opt_b.text
    assert texts["a"] not in opt_b.text
    assert texts["c"] not in opt_b.text
    assert "Верно" in opt_b.text
    assert "Не верно" in opt_b.text
    assert ">истинен<" not in opt_b.text
    assert ">ложен<" not in opt_b.text
    opt_c = _post_step(client, csrf, attempt_id, opt_b.text, step="2", mark="false")
    assert q1["text"] in opt_c.text
    assert texts["c"] in opt_c.text
    assert "Верно" in opt_c.text
    assert "Не верно" in opt_c.text
    assert ">истинен<" not in opt_c.text
    assert ">ложен<" not in opt_c.text
    next_stem = _post_step(client, csrf, attempt_id, opt_c.text, step="3", mark="false")
    assert _hidden(next_stem.text, "answer_0") == "a"
    assert _hidden(next_stem.text, "step") == "4"
    assert "вопрос 2 из 3" in next_stem.text
    assert ", вариант" not in next_stem.text
    assert template["questions"][1]["text"] in next_stem.text
    for text in texts.values():
        assert text not in next_stem.text

    phase_c = _post_step(
        client,
        csrf,
        attempt_id,
        step="3",
        mark="true",
        mark_0_a="false",
        mark_0_b="false",
        mark_0_c="",
        mark_1_a="",
        mark_1_b="",
        mark_1_c="",
        mark_2_a="",
        mark_2_b="",
        mark_2_c="",
        answer_0="",
        answer_1="",
        answer_2="",
    )
    assert _hidden(phase_c.text, "answer_0") == "c"
    assert _hidden(phase_c.text, "step") == "4"

    retry = _post_step(
        client,
        csrf,
        attempt_id,
        step="3",
        mark="true",
        mark_0_a="true",
        mark_0_b="false",
        mark_0_c="",
        mark_1_a="",
        mark_1_b="",
        mark_1_c="",
        mark_2_a="",
        mark_2_b="",
        mark_2_c="",
        answer_0="",
        answer_1="",
        answer_2="",
    )
    assert "вопрос 1 из 3" in retry.text
    assert ", вариант" not in retry.text
    assert _hidden(retry.text, "answer_0") == ""
    assert _hidden(retry.text, "step") == "0"
    assert "Нужна ровно одна отметка «истинен»." in retry.text
    assert 'class="hint"' in retry.text


def test_three_trues_repeat_same_question(client):
    body, page, template = _open_draft(client, "ux-repeat@example.com")
    csrf = _csrf(page.text)
    attempt_id = body["attempt_id"]
    q1 = template["questions"][0]
    texts = [choice["text"] for choice in q1["choices"]]
    load = _post_step(client, csrf, attempt_id)
    opt_a = _post_step(client, csrf, attempt_id, load.text, step="0", advance="1")
    assert q1["text"] in opt_a.text
    opt_b = _post_step(client, csrf, attempt_id, opt_a.text, step="1", mark="true")
    assert q1["text"] in opt_b.text
    opt_c = _post_step(client, csrf, attempt_id, opt_b.text, step="2", mark="true")
    assert q1["text"] in opt_c.text
    again = _post_step(client, csrf, attempt_id, opt_c.text, step="3", mark="true")
    assert "вопрос 1 из 3" in again.text
    assert ", вариант" not in again.text
    assert _hidden(again.text, "answer_0") == ""
    assert _hidden(again.text, "step") == "0"
    assert "Нужна ровно одна отметка «истинен»." in again.text
    assert 'class="hint"' in again.text
    shown = sum(1 for text in texts if text in again.text)
    assert shown == 0
    assert q1["text"] in again.text


def test_step_hx_errors_are_fragments(client):
    body, page, _template = _open_draft(client, "ux-csrf@example.com")
    missing = client.post(
        "/candidate/test/step",
        data={"attempt_id": str(body["attempt_id"])},
        headers=_HX,
    )
    assert missing.status_code == 200
    assert "<h1>Тест грейда</h1>" not in missing.text
    assert not missing.text.lstrip().startswith("{")
    assert 'class="error"' in missing.text
    assert "Открыть тест" in missing.text
    foreign = client.post(
        "/candidate/test/step",
        data={"csrf": _csrf(page.text), "attempt_id": "999999"},
        headers=_HX,
    )
    assert foreign.status_code == 200
    assert "<h1>Тест грейда</h1>" not in foreign.text
    assert not foreign.text.lstrip().startswith("{")
    assert 'class="error"' in foreign.text
    assert foreign.status_code != 404


def test_outcome_panel_uses_recorded_pair(client):
    profile_id = _seeker(client, "ux-outcome@example.com")
    started = client.post("/api/candidate/tests/start", json={})
    template = load_template(started.json()["template_id"])
    scored = _submit(client, started.json()["attempt_id"], _answers(template, 3))
    assert scored.json()["outcome"] == "suggest_higher"
    page = client.get("/candidate/test")
    assert "Порог подтверждения 50" in page.text
    assert "Порог предложения выше 80" in page.text
    assert "Ниже заявленного" in page.text
    assert "Подтвердить" in page.text
    assert "Выше" in page.text
    assert 'test-path test-path-current">Выше' in page.text
    assert page.text.count("Начать тест грейда senior") == 1
    assert "Начать тест грейда junior" not in page.text
    _set_stamp(client, profile_id, "2000-01-01T00:00:00Z")
    neighbor = client.post("/api/candidate/tests/start", json={"grade": "senior"})
    assert neighbor.status_code == 201, neighbor.text
    failed = _submit(
        client,
        neighbor.json()["attempt_id"],
        _answers(load_template(neighbor.json()["template_id"]), 1),
    )
    assert failed.json()["outcome"] == "suggest_lower"
    after = client.get("/candidate/test")
    assert "Итог попытки" in after.text
    assert "Грейд попытки: middle." in after.text
    assert 'test-path test-path-current">Выше' in after.text
    assert 'test-path test-path-current">Ниже заявленного' not in after.text
    assert after.text.count("Начать тест грейда senior") == 1
    assert "Начать тест грейда junior" not in after.text
    assert "Записанный грейд этой попыткой не понижен." not in after.text
