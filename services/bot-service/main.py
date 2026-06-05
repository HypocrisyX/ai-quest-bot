import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent
from aiohttp import web
from app.client import close_session
from app.events import close as close_events
from app.handlers import (
    achievements,
    admin,
    daily,
    deeplink,
    duels,
    leaderboard,
    myquests,
    profile,
    quests,
    referral,
    shop,
    start,
)
from app.keyboards import back_to_main

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


async def error_handler(event: ErrorEvent) -> bool:
    logger.exception("Unhandled error in update %s: %s", event.update.update_id, event.exception)
    update = event.update
    text = "⚠️ Что-то пошло не так. Попробуй ещё раз."
    kb = back_to_main()
    try:
        if update.message:
            await update.message.answer(text, reply_markup=kb)
        elif update.callback_query:
            await update.callback_query.answer("⚠️ Ошибка", show_alert=False)
            await update.callback_query.message.answer(text, reply_markup=kb)
    except Exception:
        pass  # don't let the error handler itself crash
    return True  # exception is handled


async def main() -> None:
    runner = await run_health_server()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")
    bot = Bot(token=token)
    storage = RedisStorage.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    dp = Dispatcher(storage=storage)

    # deeplink first: its deep-link /start handler must win over the plain one.
    dp.include_router(deeplink.router)
    dp.include_router(duels.router)
    dp.include_router(referral.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(quests.router)
    dp.include_router(myquests.router)
    dp.include_router(shop.router)
    dp.include_router(achievements.router)
    dp.include_router(admin.router)
    dp.include_router(leaderboard.router)
    dp.include_router(daily.router)
    dp.error.register(error_handler)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_session()
        await close_events()
        await bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
