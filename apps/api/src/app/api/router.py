from fastapi import APIRouter
from app.api.system import router as system_router
from app.api.configs import router as configs_router
from app.api.trade_plans import router as trade_plans_router
from app.api.risk import router as risk_router
from app.api.market import router as market_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(configs_router)
api_router.include_router(trade_plans_router)
api_router.include_router(risk_router)
api_router.include_router(market_router)