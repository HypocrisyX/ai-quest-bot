import json
import os
from typing import Optional

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME = "quest_bot"

_connection: Optional[aio_pika.RobustConnection] = None
_exchange: Optional[aio_pika.Exchange] = None


async def _get_exchange() -> aio_pika.Exchange:
    global _connection, _exchange
    if _exchange is None:
        _connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await _connection.channel()
        _exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
    return _exchange


async def publish(routing_key: str, payload: dict) -> None:
    exchange = await _get_exchange()
    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload, ensure_ascii=False).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )


async def close() -> None:
    if _connection:
        await _connection.close()


# ── Typed helpers ─────────────────────────────────────────────────────────────

async def publish_level_up(user_id: int, level_before: int, level_after: int) -> None:
    await publish("level.up", {
        "user_id": user_id,
        "level_before": level_before,
        "level_after": level_after,
    })


async def publish_streak_milestone(user_id: int, streak_days: int) -> None:
    await publish("streak.milestone", {
        "user_id": user_id,
        "streak_days": streak_days,
    })


async def publish_duel_finished(
    duel_id: int,
    challenger_id: int,
    opponent_id: int,
    winner_id: Optional[int],
    challenger_score: int,
    opponent_score: int,
) -> None:
    await publish("duel.finished", {
        "duel_id": duel_id,
        "challenger_id": challenger_id,
        "opponent_id": opponent_id,
        "winner_id": winner_id,
        "challenger_score": challenger_score,
        "opponent_score": opponent_score,
    })
