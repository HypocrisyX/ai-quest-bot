import json
import logging
import os

import aio_pika
from aiogram import Bot

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME = "quest_bot"
QUEUE_NAME = "notifications"

_LEVEL_TITLES = {
    1: "Новичок", 2: "Ученик", 3: "Практик", 4: "Знаток", 5: "Эксперт",
    10: "Мастер", 20: "Гроссмейстер", 50: "Легенда",
}


def _level_title(level: int) -> str:
    for lvl in sorted(_LEVEL_TITLES.keys(), reverse=True):
        if level >= lvl:
            return _LEVEL_TITLES[lvl]
    return "Новичок"


async def _on_level_up(bot: Bot, payload: dict) -> None:
    user_id = payload["user_id"]
    level_after = payload["level_after"]
    title = _level_title(level_after)
    await bot.send_message(
        user_id,
        f"🎉 <b>Поздравляем!</b>\n\n"
        f"Ты достиг уровня <b>{level_after}</b> — <i>{title}</i>!\n"
        f"Открываются новые квесты 🚀",
        parse_mode="HTML",
    )


async def _on_streak_milestone(bot: Bot, payload: dict) -> None:
    user_id = payload["user_id"]
    streak = payload["streak_days"]
    emojis = {7: "🔥", 30: "💫", 100: "🏆"}
    emoji = emojis.get(streak, "🔥")
    await bot.send_message(
        user_id,
        f"{emoji} <b>Серия {streak} дней!</b>\n\n"
        f"Ты занимаешься уже <b>{streak}</b> дней подряд. "
        f"Продолжай в том же духе!",
        parse_mode="HTML",
    )


async def _on_duel_finished(bot: Bot, payload: dict) -> None:
    challenger_id = payload["challenger_id"]
    opponent_id = payload["opponent_id"]
    winner_id = payload.get("winner_id")
    c_score = payload["challenger_score"]
    o_score = payload["opponent_score"]

    async def _notify(user_id: int, my_score: int, their_score: int) -> None:
        if winner_id is None:
            result = "🤝 Ничья!"
        elif winner_id == user_id:
            result = "🏆 Ты победил!"
        else:
            result = "😔 Ты проиграл."

        await bot.send_message(
            user_id,
            f"⚔️ <b>Дуэль завершена</b>\n\n"
            f"{result}\n"
            f"Счёт: <b>{my_score}</b> vs {their_score}",
            parse_mode="HTML",
        )

    await _notify(challenger_id, c_score, o_score)
    await _notify(opponent_id, o_score, c_score)


_HANDLERS = {
    "level.up": _on_level_up,
    "streak.milestone": _on_streak_milestone,
    "duel.finished": _on_duel_finished,
}


async def _process(message: aio_pika.IncomingMessage, bot: Bot) -> None:
    async with message.process(requeue=True):
        routing_key = message.routing_key
        payload = json.loads(message.body)
        handler = _HANDLERS.get(routing_key)
        if handler:
            try:
                await handler(bot, payload)
            except Exception:
                logger.exception("Failed to handle event %s: %s", routing_key, payload)
                raise


async def start_consumer(bot: Bot) -> aio_pika.RobustConnection:
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)

    for pattern in ("level.#", "streak.#", "duel.#"):
        await queue.bind(exchange, routing_key=pattern)

    await queue.consume(lambda msg: _process(msg, bot))
    logger.info("Notification worker started, listening on queue '%s'", QUEUE_NAME)
    return connection
