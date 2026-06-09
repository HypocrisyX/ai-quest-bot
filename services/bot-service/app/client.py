import os
from datetime import date
from typing import Any, Optional

import aiohttp

USER_SVC = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
QUEST_SVC = os.getenv("QUEST_SERVICE_URL", "http://quest-service:8000")
JUDGE_SVC = os.getenv("JUDGE_SERVICE_URL", "http://ai-judge-service:8000")
SOCIAL_SVC = os.getenv("SOCIAL_SERVICE_URL", "http://social-service:8000")
MARKET_SVC = os.getenv("MARKETPLACE_SERVICE_URL", "http://marketplace-service:8000")

_session: Optional[aiohttp.ClientSession] = None

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
_JUDGE_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=5)  # Claude API can be slow


def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        headers = {}
        token = os.getenv("INTERNAL_TOKEN", "")
        if token:
            headers["X-Internal-Token"] = token  # service-to-service auth
        _session = aiohttp.ClientSession(timeout=_DEFAULT_TIMEOUT, headers=headers)
    return _session


async def close_session() -> None:
    if _session and not _session.closed:
        await _session.close()


async def _post(url: str, body: dict, params: Optional[dict] = None) -> dict:
    async with get_session().post(url, json=body, params=params) as r:
        r.raise_for_status()
        return await r.json()


async def _patch(url: str, body: dict) -> dict:
    async with get_session().patch(url, json=body) as r:
        r.raise_for_status()
        return await r.json()


async def _get(url: str, params: Optional[dict] = None) -> Any:
    async with get_session().get(url, params=params) as r:
        r.raise_for_status()
        return await r.json()


# ── User Service ──────────────────────────────────────────────────────────────

async def register_user(
    telegram_id: int,
    username: Optional[str],
    first_name: str,
    language_code: str = "ru",
) -> dict:
    return await _post(f"{USER_SVC}/users", {
        "id": telegram_id,
        "username": username,
        "first_name": first_name,
        "language_code": language_code,
    })


async def get_profile(user_id: int) -> dict:
    return await _get(f"{USER_SVC}/users/{user_id}/profile")


async def get_user(user_id: int) -> Optional[dict]:
    try:
        return await _get(f"{USER_SVC}/users/{user_id}")
    except aiohttp.ClientResponseError:
        return None


async def complete_referral(referrer_id: int, referee_id: int) -> dict:
    return await _post(f"{USER_SVC}/referrals", {
        "referrer_id": referrer_id,
        "referee_id": referee_id,
    })


async def get_referral_stats(user_id: int) -> dict:
    return await _get(f"{USER_SVC}/users/{user_id}/referrals/stats")


# ── Admin ─────────────────────────────────────────────────────────────────────

async def admin_user_stats() -> dict:
    return await _get(f"{USER_SVC}/admin/stats")


async def admin_users(limit: int = 10, offset: int = 0) -> dict:
    return await _get(f"{USER_SVC}/admin/users", params={"limit": limit, "offset": offset})


async def admin_quest_stats() -> dict:
    return await _get(f"{QUEST_SVC}/admin/stats")


async def admin_quests() -> list[dict]:
    return await _get(f"{QUEST_SVC}/admin/quests")


async def admin_duel_stats() -> dict:
    return await _get(f"{SOCIAL_SVC}/admin/stats")


async def get_achievements(user_id: int) -> list[dict]:
    return await _get(f"{USER_SVC}/users/{user_id}/achievements")


async def check_achievements(user_id: int) -> list[dict]:
    return await _post(f"{USER_SVC}/users/{user_id}/achievements/check", {})


async def add_xp(user_id: int, delta_xp: int, reason: str) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/xp", {
        "user_id": user_id,
        "delta_xp": delta_xp,
        "reason": reason,
    })


async def update_streak(user_id: int) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/streak", {})


async def add_crystals(user_id: int, amount: int, reason: str) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/crystals", {
        "user_id": user_id,
        "delta": amount,
        "reason": reason,
    })


async def spend_crystals(user_id: int, amount: int, reason: str) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/crystals", {
        "user_id": user_id,
        "delta": -amount,
        "reason": reason,
    })


async def get_shop(user_id: int) -> list[dict]:
    return await _get(f"{USER_SVC}/users/{user_id}/shop")


async def purchase_item(user_id: int, item_key: str) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/shop/purchase", {
        "user_id": user_id,
        "item_key": item_key,
    })


async def consume_free_hint(user_id: int) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/hints/free/consume", {})


async def consume_skip(user_id: int) -> dict:
    return await _post(f"{USER_SVC}/users/{user_id}/skips/consume", {})


async def set_title(user_id: int, title: str) -> dict:
    return await _patch(f"{USER_SVC}/users/{user_id}/title", {"title": title})


async def get_weekly_leaderboard(user_id: int | None = None) -> dict:
    params: dict = {}
    if user_id is not None:
        params["user_id"] = user_id
    return await _get(f"{USER_SVC}/leaderboard/weekly", params=params)


# ── Quest Service ─────────────────────────────────────────────────────────────

async def get_categories(user_id: int) -> list[dict]:
    return await _get(f"{QUEST_SVC}/categories", params={"user_id": user_id})


async def get_quests(category: str, user_id: int) -> list[dict]:
    return await _get(f"{QUEST_SVC}/quests", params={"category": category, "user_id": user_id})


async def get_completed_quests(user_id: int, limit: int = 50) -> list[dict]:
    return await _get(f"{QUEST_SVC}/me/completed", params={"user_id": user_id, "limit": limit})


async def get_quest_detail(quest_id: int) -> dict:
    return await _get(f"{QUEST_SVC}/quests/{quest_id}")


async def start_quest(user_id: int, quest_id: int) -> dict:
    return await _post(f"{QUEST_SVC}/quests/{quest_id}/start", {
        "user_id": user_id,
        "quest_id": quest_id,
    })


async def complete_quest(user_id: int, quest_id: int, score: int, xp_earned: int) -> dict:
    return await _post(f"{QUEST_SVC}/quests/{quest_id}/complete", {
        "user_id": user_id,
        "quest_id": quest_id,
        "score": score,
        "xp_earned": xp_earned,
    })


async def fail_quest(user_id: int, quest_id: int) -> dict:
    return await _post(f"{QUEST_SVC}/quests/{quest_id}/fail", {
        "user_id": user_id,
        "quest_id": quest_id,
    })


async def skip_quest(user_id: int, quest_id: int) -> dict:
    return await _post(
        f"{QUEST_SVC}/quests/{quest_id}/skip", {},
        params={"user_id": user_id},
    )


async def get_progress(user_id: int, quest_id: int) -> Optional[dict]:
    try:
        return await _get(f"{QUEST_SVC}/quests/{quest_id}/progress/{user_id}")
    except aiohttp.ClientResponseError:
        return None


async def get_daily(user_level: int) -> Optional[dict]:
    try:
        return await _get(f"{QUEST_SVC}/daily", params={
            "user_level": user_level,
            "for_date": date.today().isoformat(),
        })
    except aiohttp.ClientResponseError:
        return None


async def complete_daily(daily_id: int, user_id: int) -> dict:
    return await _post(
        f"{QUEST_SVC}/daily/{daily_id}/complete",
        {},
        # user_id passed as query param
    )


async def use_hint(hint_id: int, user_id: int) -> dict:
    return await _post(f"{QUEST_SVC}/hints/{hint_id}/use", {
        "user_id": user_id,
        "hint_id": hint_id,
    })


# ── AI Judge Service ──────────────────────────────────────────────────────────

async def evaluate(
    user_id: int,
    quest: dict,
    attempt_num: int,
    user_input: str,
) -> dict:
    async with get_session().post(
        f"{JUDGE_SVC}/evaluate",
        json={
            "user_id": user_id,
            "quest_id": quest["id"],
            "attempt_num": attempt_num,
            "user_input": user_input,
            "quest_title": quest["title"],
            "quest_instructions": quest["instructions"],
            "criteria": quest.get("criteria", []),
        },
        timeout=_JUDGE_TIMEOUT,
    ) as r:
        r.raise_for_status()
        return await r.json()


# ── Social Service ────────────────────────────────────────────────────────────

async def get_leaderboard(metric: str = "xp", user_id: int | None = None) -> dict:
    params = {"metric": metric, "limit": 10}
    if user_id is not None:
        params["user_id"] = user_id
    return await _get(f"{USER_SVC}/leaderboard", params=params)


async def create_duel(challenger_id: int, quest_id: int, score: int, answer: str) -> dict:
    return await _post(f"{SOCIAL_SVC}/duels", {
        "challenger_id": challenger_id,
        "quest_id": quest_id,
        "challenger_score": score,
        "challenger_answer": answer,
    })


async def get_duel_by_code(code: str) -> Optional[dict]:
    try:
        return await _get(f"{SOCIAL_SVC}/duels/code/{code}")
    except aiohttp.ClientResponseError:
        return None


async def accept_duel(code: str, opponent_id: int, score: int, answer: str) -> dict:
    """Returns the resolution. Raises ClientResponseError(409) on conflict."""
    async with get_session().post(
        f"{SOCIAL_SVC}/duels/{code}/accept",
        json={"opponent_id": opponent_id, "opponent_score": score, "opponent_answer": answer},
    ) as r:
        r.raise_for_status()
        return await r.json()


async def apply_duel_result(challenger_id: int, opponent_id: int, winner_id: Optional[int]) -> dict:
    return await _post(f"{USER_SVC}/duels/apply", {
        "challenger_id": challenger_id,
        "opponent_id": opponent_id,
        "winner_id": winner_id,
    })


# ── Marketplace ───────────────────────────────────────────────────────────────

async def training_complete(user_id: int) -> dict:
    return await _get(f"{QUEST_SVC}/me/training-complete", params={"user_id": user_id})


async def marketplace_settle(buyer_id: int, seller_id: int, price: int) -> dict:
    return await _post(f"{USER_SVC}/marketplace/settle", {
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "price": price,
    })


async def create_listing(
    seller_id: int, title: str, description: str, price: int,
    payload_text: str, payload_file_id: Optional[str], payload_url: Optional[str],
) -> dict:
    return await _post(f"{MARKET_SVC}/listings", {
        "seller_id": seller_id,
        "title": title,
        "description": description,
        "price": price,
        "payload_text": payload_text,
        "payload_file_id": payload_file_id,
        "payload_url": payload_url,
    })


async def list_listings(user_id: int, limit: int = 10, offset: int = 0) -> dict:
    return await _get(f"{MARKET_SVC}/listings", params={
        "limit": limit, "offset": offset, "exclude_seller": user_id,
    })


async def get_listing(listing_id: int) -> Optional[dict]:
    try:
        return await _get(f"{MARKET_SVC}/listings/{listing_id}")
    except aiohttp.ClientResponseError:
        return None


async def get_listing_payload(listing_id: int) -> dict:
    return await _get(f"{MARKET_SVC}/listings/{listing_id}/payload")


async def has_purchased(buyer_id: int, listing_id: int) -> bool:
    data = await _get(f"{MARKET_SVC}/buyers/{buyer_id}/purchased/{listing_id}")
    return data.get("purchased", False)


async def record_purchase(listing_id: int, buyer_id: int, price: int, seller_earned: int) -> dict:
    return await _post(f"{MARKET_SVC}/purchases", {
        "listing_id": listing_id,
        "buyer_id": buyer_id,
        "price": price,
        "seller_earned": seller_earned,
    })


async def get_seller_listings(seller_id: int) -> list[dict]:
    return await _get(f"{MARKET_SVC}/sellers/{seller_id}/listings")


async def get_seller_stats(seller_id: int) -> dict:
    return await _get(f"{MARKET_SVC}/sellers/{seller_id}/stats")


async def get_buyer_purchases(buyer_id: int) -> list[dict]:
    return await _get(f"{MARKET_SVC}/buyers/{buyer_id}/purchases")


async def remove_listing(listing_id: int) -> dict:
    async with get_session().delete(f"{MARKET_SVC}/listings/{listing_id}") as r:
        r.raise_for_status()
        return await r.json()


async def admin_listings(limit: int = 20) -> list[dict]:
    return await _get(f"{MARKET_SVC}/admin/listings", params={"limit": limit})
