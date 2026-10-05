"""Подборка работодателя. Новый фильтр не стирает уже показанный блок."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, select_autoescape
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.services.categories import employer_candidates, parse_has_fsp
from product.app.services.errors import ApiError
from product.app.web.guards import page_user
from product.app.web.render import ensure_csrf, render
from product.matching.rules import load_rules

router = APIRouter()

_env = Environment(autoescape=select_autoescape(enabled_extensions=("html",)))
_BLOCK = _env.from_string(
    """<section class="kept">
  <h2>{{ title }}</h2>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  {% if cards %}
  <ul>
    {% for card in cards %}
    <li>
      <p>{{ card.full_name }}. Отрасль: {{ card.industry }}. Категория: {{ card.category_id }}.</p>
      <p>{{ card.explanation }}</p>
      <p>{{ card.list_reason }}</p>
      <p>Балл {{ card.test_score }}, порядок {{ card.rank_key }}. Роль в компании: {{ card.team_role }}. Формат: {{ card.work_format }}.</p>
      <p>Стек: {{ card.stack | join(', ') }}.</p>
      {% if card.achievements %}
      <ul>
        {% for row in card.achievements %}
        <li>{{ row.discipline }}, роль на старте: {{ row.role_in_team }}, результат: {{ row.place }}</li>
        {% endfor %}
      </ul>
      {% if card.fsp_rank %}<p>Разряд источника: {{ card.fsp_rank }}</p>{% endif %}
      {% else %}
      <p>Достижений ФСП нет.</p>
      {% endif %}
    </li>
    {% endfor %}
  </ul>
  {% elif not error %}
  <p>В этой категории никого нет.</p>
  {% endif %}
</section>"""
)


def _block(title: str, cards: list[dict] | None = None, error: str = "") -> HTMLResponse:
    html = _BLOCK.render(title=title, cards=cards or [], error=error)
    return HTMLResponse(html)


@router.get("/employer/shortlist")
def shortlist_page(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "employer")
    if denial is not None:
        return denial
    rules = load_rules()
    params = request.query_params
    category_id = params.get("category_id") or ""
    partial = request.headers.get("hx-request") == "true"
    block = ""
    if category_id or partial:
        try:
            cards = employer_candidates(
                db,
                category_id=category_id,
                stack=params.getlist("stack"),
                team_role=params.get("team_role") or "",
                work_format=params.get("work_format") or "",
                has_fsp=parse_has_fsp(params.get("has_fsp")),
                q=params.get("q") or "",
            )
            title = f"Подборка {category_id}"
            if partial:
                return _block(title, cards)
            block = _BLOCK.render(title=title, cards=cards, error="")
        except ApiError as exc:
            if partial:
                return _block("Подборка", error=exc.message)
            block = _BLOCK.render(title="Подборка", cards=[], error=exc.message)
    return render(
        request,
        "employer/shortlist.html",
        {
            "csrf": ensure_csrf(request),
            "user": user,
            "rules": rules,
            "kept": block,
        },
    )
