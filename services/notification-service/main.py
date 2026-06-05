import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot
from app.database import engine
from app.router import router
from app.worker import start_consumer
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("notification-service")

# Shared service-to-service secret. When set, every request (except open paths)
# must carry X-Internal-Token. Empty token => open mode (local dev).
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
_OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    try:
        connection = await start_consumer(bot)
    except Exception:
        await bot.session.close()
        raise
    yield
    await connection.close()
    await bot.session.close()
    await engine.dispose()


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def internal_auth(request: Request, call_next):
    if INTERNAL_TOKEN and request.url.path not in _OPEN_PATHS:
        if request.headers.get("X-Internal-Token") != INTERNAL_TOKEN:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "notification-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "service": "notification-service"},
        )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
