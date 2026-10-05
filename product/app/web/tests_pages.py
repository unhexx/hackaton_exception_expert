"""Пустая страница теста. Испытание заполнит свой срез."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from product.app.api.deps import db_session
from product.app.web.guards import page_user
from product.app.web.render import ensure_csrf, render

router = APIRouter()


@router.get("/candidate/test")
def test_page(request: Request, db: Session = Depends(db_session)):
    user, denial = page_user(request, db, "candidate")
    if denial is not None:
        return denial
    return render(
        request,
        "candidate/test.html",
        {"csrf": ensure_csrf(request), "user": user},
    )
