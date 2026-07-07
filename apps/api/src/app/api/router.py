from fastapi import APIRouter

from app.api.system import router as system_router
from app.api.configs import router as configs_router


api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(configs_router)
