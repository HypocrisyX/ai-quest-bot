from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.router import router
from app.database import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Social Service", lifespan=lifespan)
app.include_router(router)
