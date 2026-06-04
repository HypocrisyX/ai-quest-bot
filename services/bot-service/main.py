import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import web

from app.client import close_session
from app.events import close as close_events
from app.handlers import daily, leaderboard, profile, quests, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("bot-service")


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "bot-service"})


async def run_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Health server running on :8080")
    return runner


async def main() -> None:
    runner = await run_health_server()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")
    bot = Bot(token=token)
    storage = RedisStorage.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    dp = Dispatcher(storage=storage)

    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(quests.router)
    dp.include_router(leaderboard.router)
    dp.include_router(daily.router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_session()
        await close_events()
        await bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
