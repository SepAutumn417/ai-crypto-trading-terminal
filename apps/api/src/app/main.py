from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.router import api_router
from app.config import settings
from app.exceptions import AppException
from app.response import ApiResponse
from app.services.execution_service import close_exchange


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_exchange()


app = FastAPI(title="AI Personal Trading Terminal L4", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": exc.code, "message": str(exc.detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.err(
            detail.get("code", exc.code),
            detail.get("message", str(exc.detail)),
            detail.get("details"),
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ApiResponse.err(
            "VALIDATION_ERROR",
            "请求参数验证失败",
            {"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=ApiResponse.err("INVALID_INPUT", str(exc)).model_dump(),
    )


@app.exception_handler(LookupError)
async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ApiResponse.err("NOT_FOUND", str(exc)).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logging.getLogger(__name__).exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ApiResponse.err("INTERNAL_ERROR", "服务器内部错误").model_dump(),
    )


@app.get("/api/health")
async def health():
    return JSONResponse(content=ApiResponse.ok({"status": "ok"}).model_dump())