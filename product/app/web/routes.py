"""Сборка страниц. main подключает этот роутер одной строкой.

ТЗ §3.5 «Архитектура»: веб-приложение для обеих ролей.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from product.app.api.deps import db_session, load_session_user
from product.app.web import auth_pages, candidate, employer, fsp_link, offers_pages, shortlist, tests_pages, vacancies_pages

router = APIRouter()
router.include_router(auth_pages.router, include_in_schema=False)
router.include_router(fsp_link.router, include_in_schema=False)
router.include_router(candidate.router, include_in_schema=False)
router.include_router(employer.router, include_in_schema=False)
router.include_router(shortlist.router, include_in_schema=False)
router.include_router(tests_pages.router, include_in_schema=False)
router.include_router(offers_pages.router, include_in_schema=False)
router.include_router(vacancies_pages.router, include_in_schema=False)


@router.get("/", include_in_schema=False)
def home(request: Request, db: Session = Depends(db_session)):
    user = load_session_user(request, db)
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    target = "/candidate" if user.role == "candidate" else "/employer"
    return RedirectResponse(target, status_code=303)
