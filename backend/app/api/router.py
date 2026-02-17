from fastapi import APIRouter

from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.expenses import router as expenses_router
from app.api.settings import router as settings_router
from app.api.taxonomy import router as taxonomy_router

api_router = APIRouter()
api_router.include_router(analysis_router)
api_router.include_router(auth_router)
api_router.include_router(expenses_router)
api_router.include_router(settings_router)
api_router.include_router(taxonomy_router)
