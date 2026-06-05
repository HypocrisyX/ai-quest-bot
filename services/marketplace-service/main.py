import logging
import os
from contextlib import asynccontextmanager

from app.database import engine
from app.router import router
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("marketplace-service")

# Shared service-to-service secret. When set, every request (except open paths)
# must carry X-Internal-Token. Empty token => open mode (local dev).
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
_OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Marketplace Service", lifespan=lifespan)
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
        return {"status": "ok", "service": "marketplace-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "service": "marketplace-service"},
        )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
