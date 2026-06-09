"""HTTP endpoint tests for user-service."""
from tests.conftest import make_user


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── POST /users ───────────────────────────────────────────────────────────────

async def test_register_user(client):
    r = await client.post("/users", json={
        "id": 1001, "first_name": "Alice", "username": "alice",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == 1001
    assert data["first_name"] == "Alice"


async def test_register_user_idempotent(client):
    payload = {"id": 1002, "first_name": "Bob", "username": "bob"}
    r1 = await client.post("/users", json=payload)
    r2 = await client.post("/users", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


async def test_register_user_missing_first_name(client):
    r = await client.post("/users", json={"id": 1003})
    assert r.status_code == 422


# ── GET /users/{id} ───────────────────────────────────────────────────────────

async def test_get_user(client):
    await client.post("/users", json={"id": 2001, "first_name": "Carol"})
    r = await client.get("/users/2001")
    assert r.status_code == 200
    assert r.json()["id"] == 2001


async def test_get_user_not_found(client):
    r = await client.get("/users/99999")
    assert r.status_code == 404


# ── GET /users/{id}/profile ───────────────────────────────────────────────────

async def test_get_profile(client):
    await client.post("/users", json={"id": 3001, "first_name": "Dave"})
    r = await client.get("/users/3001/profile")
    assert r.status_code == 200
    data = r.json()
    assert "user" in data
    assert "stats" in data
    assert data["stats"]["level"] == 1
    assert data["stats"]["xp"] == 0
    assert data["stats"]["crystals"] == 0


# ── POST /users/{id}/xp ───────────────────────────────────────────────────────

async def test_add_xp(client):
    await client.post("/users", json={"id": 4001, "first_name": "Eve"})
    r = await client.post("/users/4001/xp", json={
        "user_id": 4001, "delta_xp": 75, "reason": "quest_complete",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["xp_after"] == 75
    assert data["leveled_up"] is False


async def test_add_xp_triggers_levelup(client):
    await client.post("/users", json={"id": 4002, "first_name": "Frank"})
    r = await client.post("/users/4002/xp", json={
        "user_id": 4002, "delta_xp": 1100, "reason": "quest_complete",
    })
    assert r.status_code == 200
    assert r.json()["leveled_up"] is True
    assert r.json()["level_after"] == 2


# ── POST /users/{id}/crystals ─────────────────────────────────────────────────

async def test_add_crystals(client):
    await client.post("/users", json={"id": 5001, "first_name": "Grace"})
    r = await client.post("/users/5001/crystals", json={
        "user_id": 5001, "delta": 50, "reason": "reward",
    })
    assert r.status_code == 200
    assert r.json()["balance_after"] == 50


async def test_spend_crystals_floor_zero(client):
    await client.post("/users", json={"id": 5002, "first_name": "Hank"})
    r = await client.post("/users/5002/crystals", json={
        "user_id": 5002, "delta": -999, "reason": "hint",
    })
    assert r.status_code == 200
    assert r.json()["balance_after"] == 0


# ── POST /users/{id}/streak ───────────────────────────────────────────────────

async def test_update_streak(client):
    await client.post("/users", json={"id": 6001, "first_name": "Ivy"})
    r = await client.post("/users/6001/streak")
    assert r.status_code == 200
    assert r.json()["streak_days"] == 1


# ── consume_free_hint / consume_skip / set_title ──────────────────────────────

async def test_consume_free_hint_endpoint(client, db):
    _, stats = await make_user(db, free_hints=2)
    r = await client.post(f"/users/{stats.user_id}/hints/free/consume")
    assert r.status_code == 200
    assert r.json() == {"used_free": True, "free_hints_left": 1}


async def test_consume_skip_endpoint(client, db):
    _, stats = await make_user(db, quest_skips=1)
    r = await client.post(f"/users/{stats.user_id}/skips/consume")
    assert r.status_code == 200
    assert r.json()["consumed"] is True
    assert r.json()["skips_left"] == 0


async def test_set_title_endpoint(client, db):
    _, stats = await make_user(db)
    r = await client.patch(f"/users/{stats.user_id}/title", json={"title": "Хакер"})
    assert r.status_code == 200
    assert r.json()["class_title"] == "Хакер"


async def test_set_title_too_long_returns_422(client, db):
    _, stats = await make_user(db)
    r = await client.patch(f"/users/{stats.user_id}/title", json={"title": "A" * 21})
    assert r.status_code == 422


async def test_set_title_empty_returns_422(client, db):
    _, stats = await make_user(db)
    r = await client.patch(f"/users/{stats.user_id}/title", json={"title": ""})
    assert r.status_code == 422
