"""Список API-роутеров. После каркаса сюда не добавляют срезы обязательного пути.

ТЗ §3.5 «API: все методы описаны через спецификацию OpenAPI».
"""

from fastapi import APIRouter

from product.app.api import auth, categories, company, offers, profiles, resumes, tests, vacancies, validation

router = APIRouter()
router.include_router(auth.router, prefix="/api")
router.include_router(profiles.router, prefix="/api")
router.include_router(company.router, prefix="/api")
router.include_router(categories.router, prefix="/api")
router.include_router(tests.router, prefix="/api")
router.include_router(offers.router, prefix="/api")
router.include_router(vacancies.router, prefix="/api")
router.include_router(resumes.router, prefix="/api")
router.include_router(validation.router)
