import os
from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI

from app.database import engine
from app.router import router
from app.worker import start_consumer


@asynccontextmanager
async def lifespan(_: FastAPI):
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    connection = await start_consumer(bot)
    yield
    await connection.close()
    await bot.session.close()
    await engine.dispose()


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.include_router(router)
