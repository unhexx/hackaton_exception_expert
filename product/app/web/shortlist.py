"""Подборка работодателя. Новый фильтр не стирает уже показанный блок.

ТЗ §2.1 «Работа с подборкой… обоснование попадания», «фильтрация и уточнение запроса без потери ранее полученной подборки».
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.services.categories import employer_candidates, parse_has_fsp
from product.app.services.errors import ApiError, hint as catalog_hint
from product.app.web.guards import page_user
from product.app.web.render import ensure_csrf, render
from product.matching.rules import load_rules

router = APIRouter()


@router.get("/employer/shortlist")
def shortlist_page(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "employer")
    if denial is not None:
        return denial
    rules = load_rules()
    params = request.query_params
    category_id = params.get("category_id") or ""
    partial = request.headers.get("hx-request") == "true"
    ctx = {
        "csrf": ensure_csrf(request),
        "user": user,
        "rules": rules,
        "title": "",
        "cards": [],
        "error": "",
        "hint": "",
        "show_block": False,
    }
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
            ctx["title"] = f"Подборка {category_id}"
            ctx["cards"] = cards
            if not cards:
                ctx["hint"] = catalog_hint("hint_shortlist_empty")
        except ApiError as exc:
            ctx["title"] = "Подборка"
            ctx["error"] = exc.message
        ctx["show_block"] = True
        if partial:
            return render(request, "employer/_shortlist_block.html", ctx)
    return render(request, "employer/shortlist.html", ctx)
