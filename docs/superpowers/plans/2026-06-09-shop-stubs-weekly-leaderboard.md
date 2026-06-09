# Shop Stubs + Weekly Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 4 functional shop items (streak freeze, hint pack, quest skip, custom title) and add a weekly XP leaderboard tab.

**Architecture:** user-service gets a migration + new repo functions + new endpoints; quest-service gets a skip endpoint; bot-service gets new client methods and updated handlers. The bot orchestrates multi-service flows (e.g. consume skip token, then call quest-service).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, aiogram 3, pytest-asyncio, httpx

---

## File Map

**user-service:**
- Create: `services/user-service/alembic/versions/0003_shop_items.py`
- Modify: `services/user-service/app/models.py` — add 3 columns to `UserStats`
- Modify: `services/user-service/app/schemas.py` — extend `UserStatsOut`; add `SetTitleRequest`
- Modify: `services/user-service/app/repository.py` — `update_streak` freeze; `purchase_item` 4 items; `consume_free_hint`; `consume_skip`; `set_title`; `leaderboard_weekly`
- Modify: `services/user-service/app/router.py` — 4 new endpoints + weekly leaderboard
- Modify: `services/user-service/tests/conftest.py` — add `make_user` helper
- Modify: `services/user-service/tests/test_repository.py` — new test cases
- Modify: `services/user-service/tests/test_router.py` — new endpoint tests

**quest-service:**
- Modify: `services/quest-service/app/repository.py` — `skip_quest` function
- Modify: `services/quest-service/app/router.py` — `POST /quests/{id}/skip`
- Modify: `services/quest-service/tests/test_repository.py` — skip tests

**bot-service:**
- Modify: `services/bot-service/app/client.py` — `_patch` helper; 5 new methods
- Modify: `services/bot-service/app/handlers/shop.py` — header; 4 items; `SettingTitle` FSM
- Modify: `services/bot-service/app/keyboards.py` — `quest_detail` skip button
- Modify: `services/bot-service/app/handlers/quests.py` — free hint check; skip callback
- Modify: `services/bot-service/app/handlers/leaderboard.py` — weekly tab

---

### Task 1: Migration, model, schema (user-service)

**Files:**
- Create: `services/user-service/alembic/versions/0003_shop_items.py`
- Modify: `services/user-service/app/models.py`
- Modify: `services/user-service/app/schemas.py`

- [ ] **Step 1: Create migration file**

Create `services/user-service/alembic/versions/0003_shop_items.py`:

```python
"""add shop columns to user_stats

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_stats", sa.Column("streak_freeze_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_stats", sa.Column("free_hints", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_stats", sa.Column("quest_skips", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("user_stats", "quest_skips")
    op.drop_column("user_stats", "free_hints")
    op.drop_column("user_stats", "streak_freeze_count")
```

- [ ] **Step 2: Add columns to UserStats model**

In `services/user-service/app/models.py`, add these three lines after `xp_boost_quests`:

```python
streak_freeze_count = Column(Integer, nullable=False, server_default="0")
free_hints = Column(Integer, nullable=False, server_default="0")
quest_skips = Column(Integer, nullable=False, server_default="0")
```

- [ ] **Step 3: Extend schemas**

In `services/user-service/app/schemas.py`, add three fields to `UserStatsOut` after `xp_boost_quests: int = 0`:

```python
streak_freeze_count: int = 0
free_hints: int = 0
quest_skips: int = 0
```

After the `PurchaseResponse` class, add:

```python
class SetTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=20)
```

`Field` is already imported in this file.

- [ ] **Step 4: Commit**

```bash
git add services/user-service/alembic/versions/0003_shop_items.py \
        services/user-service/app/models.py \
        services/user-service/app/schemas.py
git commit -m "feat(user-service): migration 0003 — streak_freeze_count, free_hints, quest_skips"
```

---

### Task 2: streak_freeze logic in update_streak (user-service, TDD)

**Files:**
- Modify: `services/user-service/tests/conftest.py`
- Modify: `services/user-service/tests/test_repository.py`
- Modify: `services/user-service/app/repository.py`

- [ ] **Step 1: Add make_user helper to conftest.py**

In `services/user-service/tests/conftest.py`, add at the bottom:

```python
import random
from app.models import User, UserStats


async def make_user(db, **stats_kwargs):
    """Create a user + stats row with sane defaults. Override any field via kwargs."""
    uid = random.randint(10**9, 2 * 10**9)
    user = User(id=uid, first_name="Test", language_code="ru")
    db.add(user)
    defaults = dict(
        level=1, xp=0, xp_to_next=1100, crystals=100,
        elo_rating=1000, streak_days=0, streak_last_at=None,
        total_quests=0, xp_boost_quests=0,
        streak_freeze_count=0, free_hints=0, quest_skips=0,
    )
    defaults.update(stats_kwargs)
    stats = UserStats(user_id=uid, **defaults)
    db.add(stats)
    await db.flush()
    return user, stats
```

- [ ] **Step 2: Write failing streak freeze tests**

In `services/user-service/tests/test_repository.py`, add imports at top if missing:

```python
from datetime import date, timedelta
from tests.conftest import make_user
import app.repository as repo
```

Add three test functions:

```python
async def test_streak_freeze_consumed_on_one_day_miss(db):
    _, stats = await make_user(
        db,
        streak_days=5,
        streak_last_at=date.today() - timedelta(days=2),
        streak_freeze_count=1,
    )
    result = await repo.update_streak(db, stats.user_id)
    assert result == 5  # streak preserved, not reset
    await db.refresh(stats)
    assert stats.streak_freeze_count == 0
    assert stats.streak_last_at == date.today()


async def test_streak_freeze_not_consumed_on_two_plus_day_miss(db):
    _, stats = await make_user(
        db,
        streak_days=5,
        streak_last_at=date.today() - timedelta(days=3),
        streak_freeze_count=1,
    )
    result = await repo.update_streak(db, stats.user_id)
    assert result == 1  # streak reset — gap too large
    await db.refresh(stats)
    assert stats.streak_freeze_count == 1  # freeze untouched


async def test_streak_reset_when_no_freeze_available(db):
    _, stats = await make_user(
        db,
        streak_days=5,
        streak_last_at=date.today() - timedelta(days=2),
        streak_freeze_count=0,
    )
    result = await repo.update_streak(db, stats.user_id)
    assert result == 1  # reset — no freeze to save it
```

- [ ] **Step 3: Run tests (expect failures)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py -k "freeze" -v
```

Expected: 3 FAIL.

- [ ] **Step 4: Update update_streak in repository.py**

Add `timedelta` to the datetime import at the top of `services/user-service/app/repository.py`:

```python
from datetime import date, datetime, timedelta, timezone
```

Replace the `update_streak` function:

```python
async def update_streak(session: AsyncSession, user_id: int) -> int:
    stats = await _stats_for_update(session, user_id)
    today = date.today()

    if stats.streak_last_at == today:
        return stats.streak_days

    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    if stats.streak_last_at == yesterday:
        stats.streak_days += 1
    elif stats.streak_last_at == two_days_ago and (stats.streak_freeze_count or 0) > 0:
        stats.streak_freeze_count -= 1
        # streak_days unchanged — freeze preserves it, doesn't advance it
    else:
        stats.streak_days = 1

    stats.streak_last_at = today
    await session.flush()
    return stats.streak_days
```

- [ ] **Step 5: Run tests (expect pass)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py -k "freeze" -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add services/user-service/app/repository.py \
        services/user-service/tests/conftest.py \
        services/user-service/tests/test_repository.py
git commit -m "feat(user-service): streak_freeze logic in update_streak"
```

---

### Task 3: purchase_item for 4 new shop items (user-service, TDD)

**Files:**
- Modify: `services/user-service/app/repository.py`
- Modify: `services/user-service/tests/test_repository.py`

- [ ] **Step 1: Write failing tests**

```python
async def test_purchase_streak_freeze(db):
    _, stats = await make_user(db, crystals=200)
    ok, msg, balance = await repo.purchase_item(db, stats.user_id, "streak_freeze")
    assert ok is True
    assert "Заморозка" in msg
    assert balance == 200 - 80
    await db.refresh(stats)
    assert stats.streak_freeze_count == 1


async def test_purchase_hint_pack(db):
    _, stats = await make_user(db, crystals=200)
    ok, msg, _ = await repo.purchase_item(db, stats.user_id, "hint_pack")
    assert ok is True
    await db.refresh(stats)
    assert stats.free_hints == 3


async def test_purchase_skip_quest(db):
    _, stats = await make_user(db, crystals=200)
    ok, msg, _ = await repo.purchase_item(db, stats.user_id, "skip_quest")
    assert ok is True
    await db.refresh(stats)
    assert stats.quest_skips == 1


async def test_purchase_custom_title_returns_input_signal(db):
    _, stats = await make_user(db, crystals=300)
    ok, msg, balance = await repo.purchase_item(db, stats.user_id, "custom_title")
    assert ok is True
    assert msg == "INPUT:custom_title"
    assert balance == 300 - 200
```

- [ ] **Step 2: Run tests (expect failures)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py \
  -k "purchase_streak or purchase_hint or purchase_skip or purchase_custom" -v
```

Expected: 4 FAIL — items still `available=False`.

- [ ] **Step 3: Update SHOP_ITEMS and purchase_item in repository.py**

Replace `SHOP_ITEMS` list:

```python
SHOP_ITEMS = [
    {
        "key": "xp_boost",
        "title": "⚡️ Буст XP ×2",
        "description": f"Двойной XP за следующие {XP_BOOST_QUESTS} квеста",
        "cost": 50,
        "available": True,
    },
    {
        "key": "streak_freeze",
        "title": "🧊 Заморозка серии",
        "description": "Сохранит серию если пропустишь один день",
        "cost": 80,
        "available": True,
    },
    {
        "key": "hint_pack",
        "title": "💡 Набор подсказок",
        "description": "3 бесплатные подсказки для квестов",
        "cost": 60,
        "available": True,
    },
    {
        "key": "skip_quest",
        "title": "⏭ Пропуск квеста",
        "description": "Пропустить сложный квест (засчитывается без награды)",
        "cost": 120,
        "available": True,
    },
    {
        "key": "custom_title",
        "title": "🏷 Свой титул",
        "description": "Кастомный титул в профиле (1–20 символов)",
        "cost": 200,
        "available": True,
    },
]
```

In `purchase_item`, replace the `if item_key == "xp_boost": ... else: msg = "Покупка совершена"` block:

```python
    if item_key == "xp_boost":
        stats.xp_boost_quests = (stats.xp_boost_quests or 0) + XP_BOOST_QUESTS
        msg = f"⚡️ Буст активирован! ×2 XP на следующие {XP_BOOST_QUESTS} квеста"
    elif item_key == "streak_freeze":
        stats.streak_freeze_count = (stats.streak_freeze_count or 0) + 1
        msg = "🧊 Заморозка добавлена! Сохранит серию при пропуске одного дня."
    elif item_key == "hint_pack":
        stats.free_hints = (stats.free_hints or 0) + 3
        msg = "💡 3 бесплатные подсказки добавлены!"
    elif item_key == "skip_quest":
        stats.quest_skips = (stats.quest_skips or 0) + 1
        msg = "⏭ Пропуск квеста добавлен!"
    elif item_key == "custom_title":
        msg = "INPUT:custom_title"
    else:
        msg = "Покупка совершена"
```

- [ ] **Step 4: Run tests (expect pass)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py -k "purchase" -v
```

Expected: all purchase tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/user-service/app/repository.py \
        services/user-service/tests/test_repository.py
git commit -m "feat(user-service): activate streak_freeze, hint_pack, skip_quest, custom_title in shop"
```

---

### Task 4: consume_free_hint, consume_skip, set_title (user-service, TDD)

**Files:**
- Modify: `services/user-service/app/repository.py`
- Modify: `services/user-service/app/router.py`
- Modify: `services/user-service/tests/test_repository.py`
- Modify: `services/user-service/tests/test_router.py`

- [ ] **Step 1: Write failing repository tests**

```python
async def test_consume_free_hint_decrements(db):
    _, stats = await make_user(db, free_hints=3)
    result = await repo.consume_free_hint(db, stats.user_id)
    assert result == {"used_free": True, "free_hints_left": 2}
    await db.refresh(stats)
    assert stats.free_hints == 2


async def test_consume_free_hint_when_none(db):
    _, stats = await make_user(db, free_hints=0)
    result = await repo.consume_free_hint(db, stats.user_id)
    assert result == {"used_free": False, "free_hints_left": 0}


async def test_consume_skip_decrements(db):
    _, stats = await make_user(db, quest_skips=2)
    result = await repo.consume_skip(db, stats.user_id)
    assert result == {"consumed": True, "skips_left": 1}
    await db.refresh(stats)
    assert stats.quest_skips == 1


async def test_consume_skip_when_none(db):
    _, stats = await make_user(db, quest_skips=0)
    result = await repo.consume_skip(db, stats.user_id)
    assert result == {"consumed": False, "skips_left": 0}


async def test_set_title_updates_class_title(db):
    _, stats = await make_user(db)
    title = await repo.set_title(db, stats.user_id, "AI Мастер")
    assert title == "AI Мастер"
    await db.refresh(stats)
    assert stats.class_title == "AI Мастер"


async def test_set_title_strips_whitespace(db):
    _, stats = await make_user(db)
    title = await repo.set_title(db, stats.user_id, "  Guru  ")
    assert title == "Guru"
```

- [ ] **Step 2: Run tests (expect failures)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py \
  -k "consume_free or consume_skip or set_title" -v
```

Expected: 6 FAIL — functions not defined.

- [ ] **Step 3: Add repo functions**

In `services/user-service/app/repository.py`, add after `list_shop_items`:

```python
async def consume_free_hint(session: AsyncSession, user_id: int) -> dict:
    stats = await _stats_for_update(session, user_id)
    if stats is None or (stats.free_hints or 0) <= 0:
        return {"used_free": False, "free_hints_left": 0}
    stats.free_hints -= 1
    await session.flush()
    return {"used_free": True, "free_hints_left": stats.free_hints}


async def consume_skip(session: AsyncSession, user_id: int) -> dict:
    stats = await _stats_for_update(session, user_id)
    if stats is None or (stats.quest_skips or 0) <= 0:
        return {"consumed": False, "skips_left": 0}
    stats.quest_skips -= 1
    await session.flush()
    return {"consumed": True, "skips_left": stats.quest_skips}


async def set_title(session: AsyncSession, user_id: int, title: str) -> str:
    stats = await _stats_for_update(session, user_id)
    if stats is None:
        raise ValueError("User not found")
    stats.class_title = title.strip()
    await session.flush()
    return stats.class_title
```

- [ ] **Step 4: Run repo tests (expect pass)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py \
  -k "consume_free or consume_skip or set_title" -v
```

Expected: 6 PASS.

- [ ] **Step 5: Add router endpoints**

In `services/user-service/app/router.py`, add `SetTitleRequest` to the schema imports block.

Add three endpoints after the `purchase` endpoint:

```python
@router.post("/users/{user_id}/hints/free/consume")
async def consume_free_hint(user_id: int, db: DB):
    return await repo.consume_free_hint(db, user_id)


@router.post("/users/{user_id}/skips/consume")
async def consume_skip(user_id: int, db: DB):
    return await repo.consume_skip(db, user_id)


@router.patch("/users/{user_id}/title")
async def set_title(user_id: int, data: SetTitleRequest, db: DB):
    title = await repo.set_title(db, user_id, data.title)
    return {"class_title": title}
```

- [ ] **Step 6: Write router tests**

In `services/user-service/tests/test_router.py`, add import:

```python
from tests.conftest import make_user
```

Add test functions:

```python
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
```

- [ ] **Step 7: Run all new tests**

```bash
cd services/user-service && python -m pytest tests/ -k "consume or set_title" -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add services/user-service/app/repository.py \
        services/user-service/app/router.py \
        services/user-service/tests/test_repository.py \
        services/user-service/tests/test_router.py
git commit -m "feat(user-service): consume_free_hint, consume_skip, set_title endpoints"
```

---

### Task 5: Weekly leaderboard (user-service, TDD)

**Files:**
- Modify: `services/user-service/app/repository.py`
- Modify: `services/user-service/app/router.py`
- Modify: `services/user-service/tests/test_repository.py`

- [ ] **Step 1: Write failing tests**

```python
async def test_weekly_leaderboard_aggregates_xp(db):
    from app.models import XpHistory
    from datetime import datetime, timezone

    u1, _ = await make_user(db)
    u2, _ = await make_user(db)
    now = datetime.now(timezone.utc)
    db.add(XpHistory(user_id=u1.id, delta_xp=200, reason="quest_complete", level_after=1, created_at=now))
    db.add(XpHistory(user_id=u1.id, delta_xp=100, reason="quest_complete", level_after=1, created_at=now))
    db.add(XpHistory(user_id=u2.id, delta_xp=350, reason="quest_complete", level_after=1, created_at=now))
    await db.flush()

    today = date.today()
    iso = today.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    result = await repo.leaderboard_weekly(db, week)

    assert result["week"] == week
    assert len(result["entries"]) == 2
    assert result["entries"][0]["user_id"] == u2.id  # 350 > 300
    assert result["entries"][0]["xp_gained"] == 350
    assert result["entries"][1]["xp_gained"] == 300


async def test_weekly_leaderboard_excludes_last_week(db):
    from app.models import XpHistory
    from datetime import datetime, timezone

    u1, _ = await make_user(db)
    last_week = datetime.now(timezone.utc) - timedelta(days=8)
    db.add(XpHistory(user_id=u1.id, delta_xp=500, reason="quest_complete", level_after=1, created_at=last_week))
    await db.flush()

    today = date.today()
    iso = today.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    result = await repo.leaderboard_weekly(db, week)
    assert result["entries"] == []


async def test_weekly_leaderboard_me_rank(db):
    from app.models import XpHistory
    from datetime import datetime, timezone

    u1, _ = await make_user(db)
    u2, _ = await make_user(db)
    now = datetime.now(timezone.utc)
    db.add(XpHistory(user_id=u1.id, delta_xp=100, reason="quest_complete", level_after=1, created_at=now))
    db.add(XpHistory(user_id=u2.id, delta_xp=200, reason="quest_complete", level_after=1, created_at=now))
    await db.flush()

    today = date.today()
    iso = today.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    result = await repo.leaderboard_weekly(db, week, user_id=u1.id)
    assert result["me"]["rank"] == 2
    assert result["me"]["xp_gained"] == 100
```

- [ ] **Step 2: Run tests (expect failures)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py -k "weekly" -v
```

Expected: 3 FAIL — `leaderboard_weekly` not defined.

- [ ] **Step 3: Add leaderboard_weekly to repository.py**

Add `re` to imports at top:
```python
import re
```

Verify `XpHistory` is in the `from .models import (...)` block. If not, add it.

Add after `user_rank`:

```python
def _parse_week(week_str: str) -> tuple[datetime, datetime]:
    """Parse 'YYYY-Www' → (monday_utc, next_monday_utc)."""
    m = re.match(r"^(\d{4})-W(\d{2})$", week_str)
    if not m:
        raise ValueError(f"Invalid week format: {week_str!r}. Expected YYYY-Www")
    year, week = int(m.group(1)), int(m.group(2))
    monday = date.fromisocalendar(year, week, 1)
    next_monday = monday + timedelta(days=7)
    return (
        datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc),
        datetime(next_monday.year, next_monday.month, next_monday.day, tzinfo=timezone.utc),
    )


async def leaderboard_weekly(
    session: AsyncSession,
    week_str: str,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> dict:
    """Top users by XP gained in the given ISO week. week_str: '2026-W23'."""
    start, end = _parse_week(week_str)

    xp_sub = (
        select(XpHistory.user_id, func.sum(XpHistory.delta_xp).label("xp_gained"))
        .where(XpHistory.created_at >= start, XpHistory.created_at < end)
        .group_by(XpHistory.user_id)
        .subquery()
    )
    result = await session.execute(
        select(User.id, User.username, User.first_name, xp_sub.c.xp_gained)
        .join(xp_sub, xp_sub.c.user_id == User.id)
        .order_by(xp_sub.c.xp_gained.desc())
        .limit(limit)
    )
    entries = [
        {
            "rank": i,
            "user_id": uid,
            "name": _display_name(username, first_name),
            "xp_gained": xp_gained,
        }
        for i, (uid, username, first_name, xp_gained) in enumerate(result, start=1)
    ]

    me = None
    if user_id is not None:
        user_xp = await session.scalar(
            select(func.sum(XpHistory.delta_xp)).where(
                XpHistory.user_id == user_id,
                XpHistory.created_at >= start,
                XpHistory.created_at < end,
            )
        ) or 0
        higher_sub = (
            select(XpHistory.user_id, func.sum(XpHistory.delta_xp).label("total"))
            .where(XpHistory.created_at >= start, XpHistory.created_at < end)
            .group_by(XpHistory.user_id)
            .subquery()
        )
        higher_count = await session.scalar(
            select(func.count()).select_from(higher_sub).where(higher_sub.c.total > user_xp)
        ) or 0
        me = {"rank": higher_count + 1, "xp_gained": user_xp}

    return {"week": week_str, "entries": entries, "me": me}
```

- [ ] **Step 4: Run tests (expect pass)**

```bash
cd services/user-service && python -m pytest tests/test_repository.py -k "weekly" -v
```

Expected: 3 PASS.

- [ ] **Step 5: Add router endpoint**

In `services/user-service/app/router.py`, add `date` and `Optional` to imports if not present:

```python
from datetime import date
from typing import Annotated, Optional
```

Add after `get_leaderboard`:

```python
@router.get("/leaderboard/weekly")
async def get_weekly_leaderboard(
    db: DB,
    week: Optional[str] = None,
    user_id: int | None = None,
):
    if week is None:
        today = date.today()
        iso = today.isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"
    return await repo.leaderboard_weekly(db, week, user_id)
```

- [ ] **Step 6: Run full user-service suite**

```bash
cd services/user-service && python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add services/user-service/app/repository.py \
        services/user-service/app/router.py \
        services/user-service/tests/test_repository.py
git commit -m "feat(user-service): weekly XP leaderboard endpoint"
```

---

### Task 6: quest-service — skip_quest endpoint (TDD)

**Files:**
- Modify: `services/quest-service/app/repository.py`
- Modify: `services/quest-service/app/router.py`
- Modify: `services/quest-service/tests/test_repository.py`

- [ ] **Step 1: Write failing tests**

In `services/quest-service/tests/test_repository.py`, add:

```python
async def test_skip_quest_marks_completed_score_zero(db):
    from app.models import Quest, UserQuestProgress
    from sqlalchemy import select

    q = Quest(
        level_min=1, type="practice", category="text",
        title="Skip me", instructions="x", xp_reward=50, order_index=99,
    )
    db.add(q)
    await db.flush()

    user_id = 55001
    result = await repo.skip_quest(db, user_id, q.id)
    assert result is True

    prog = (await db.execute(
        select(UserQuestProgress).where(
            UserQuestProgress.user_id == user_id,
            UserQuestProgress.quest_id == q.id,
        )
    )).scalar_one_or_none()
    assert prog is not None
    assert prog.status == "completed"
    assert prog.best_score == 0
    assert prog.xp_earned == 0


async def test_skip_quest_idempotent(db):
    from app.models import Quest

    q = Quest(
        level_min=1, type="practice", category="text",
        title="Already done", instructions="x", xp_reward=50, order_index=100,
    )
    db.add(q)
    await db.flush()

    user_id = 55002
    await repo.skip_quest(db, user_id, q.id)
    result = await repo.skip_quest(db, user_id, q.id)
    assert result is True  # no error on second call


async def test_skip_quest_returns_false_for_missing_quest(db):
    result = await repo.skip_quest(db, 999, 99999)
    assert result is False
```

- [ ] **Step 2: Run tests (expect failures)**

```bash
cd services/quest-service && python -m pytest tests/test_repository.py -k "skip" -v
```

Expected: 3 FAIL — `skip_quest` not defined.

- [ ] **Step 3: Add skip_quest to repository.py**

In `services/quest-service/app/repository.py`, add after `fail_quest`:

```python
async def skip_quest(session: AsyncSession, user_id: int, quest_id: int) -> bool:
    """Mark quest completed with score=0, xp=0. Returns False if quest not found."""
    quest = await get_quest(session, quest_id)
    if not quest:
        return False

    progress = await get_user_progress(session, user_id, quest_id)
    if progress and progress.status == "completed":
        return True  # idempotent

    if not progress:
        progress = UserQuestProgress(user_id=user_id, quest_id=quest_id, attempts=0)
        session.add(progress)
        await session.flush()

    await complete_quest(session, user_id, quest_id, score=0, xp_earned=0)
    return True
```

`UserQuestProgress` is already imported in this file.

- [ ] **Step 4: Run tests (expect pass)**

```bash
cd services/quest-service && python -m pytest tests/test_repository.py -k "skip" -v
```

Expected: 3 PASS.

- [ ] **Step 5: Add router endpoint**

In `services/quest-service/app/router.py`, add after the `fail_quest` endpoint:

```python
@router.post("/quests/{quest_id}/skip")
async def skip_quest(quest_id: int, user_id: int, db: DB):
    """Mark quest completed (score=0, xp=0). Bot must consume the skip token first."""
    skipped = await repo.skip_quest(db, user_id, quest_id)
    if not skipped:
        raise HTTPException(404, "Quest not found")
    return {"skipped": True}
```

- [ ] **Step 6: Run full quest-service suite**

```bash
cd services/quest-service && python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add services/quest-service/app/repository.py \
        services/quest-service/app/router.py \
        services/quest-service/tests/test_repository.py
git commit -m "feat(quest-service): skip_quest endpoint"
```

---

### Task 7: bot-service — client.py new methods

**Files:**
- Modify: `services/bot-service/app/client.py`

- [ ] **Step 1: Add params support to _post and add _patch**

Replace `_post`:

```python
async def _post(url: str, body: dict, params: Optional[dict] = None) -> dict:
    async with get_session().post(url, json=body, params=params) as r:
        r.raise_for_status()
        return await r.json()
```

After `_get`, add:

```python
async def _patch(url: str, body: dict) -> dict:
    async with get_session().patch(url, json=body) as r:
        r.raise_for_status()
        return await r.json()
```

- [ ] **Step 2: Add 4 user-service methods**

After `purchase_item` in the `# ── User Service ──` section:

```python
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
```

- [ ] **Step 3: Add quest-service skip method**

After `fail_quest` in the `# ── Quest Service ──` section:

```python
async def skip_quest(user_id: int, quest_id: int) -> dict:
    return await _post(
        f"{QUEST_SVC}/quests/{quest_id}/skip", {},
        params={"user_id": user_id},
    )
```

- [ ] **Step 4: Commit**

```bash
git add services/bot-service/app/client.py
git commit -m "feat(bot): client — _patch, consume_free_hint, consume_skip, skip_quest, set_title, weekly lb"
```

---

### Task 8: bot-service — shop.py (4 items + custom_title FSM)

**Files:**
- Modify: `services/bot-service/app/handlers/shop.py`

- [ ] **Step 1: Update imports**

Ensure these imports are at the top of `services/bot-service/app/handlers/shop.py`:

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main, shop_menu
```

Add FSM class after imports:

```python
class SettingTitle(StatesGroup):
    awaiting_title = State()
```

- [ ] **Step 2: Update _shop_header and _render_shop**

Replace `_shop_header`:

```python
def _shop_header(
    crystals: int,
    boost: int,
    freezes: int = 0,
    hints: int = 0,
    skips: int = 0,
) -> str:
    lines = [
        "🛒 <b>Магазин</b>",
        f"💎 Баланс: <b>{crystals}</b> кристаллов",
    ]
    if boost > 0:
        lines.append(f"⚡️ Активен буст ×2: ещё <b>{boost}</b> квест(а)")
    if freezes > 0:
        lines.append(f"🧊 Заморозок серии: <b>{freezes}</b>")
    if hints > 0:
        lines.append(f"💡 Бесплатных подсказок: <b>{hints}</b>")
    if skips > 0:
        lines.append(f"⏭ Пропусков квестов: <b>{skips}</b>")
    lines.append("\nВыбери товар:")
    return "\n".join(lines)
```

Replace `_render_shop`:

```python
async def _render_shop(user_id: int):
    profile = await client.get_profile(user_id)
    stats = profile["stats"]
    crystals = stats["crystals"]
    boost = stats.get("xp_boost_quests", 0)
    freezes = stats.get("streak_freeze_count", 0)
    hints = stats.get("free_hints", 0)
    skips = stats.get("quest_skips", 0)
    items = await client.get_shop(user_id)
    return _shop_header(crystals, boost, freezes, hints, skips), shop_menu(items)
```

- [ ] **Step 3: Update cb_shop_buy to detect INPUT signal**

Replace `cb_shop_buy`:

```python
@router.callback_query(F.data.startswith("shop:buy:"))
async def cb_shop_buy(call: CallbackQuery, state: FSMContext):
    item_key = call.data.split(":")[2]
    result = await client.purchase_item(call.from_user.id, item_key)
    if result.get("ok") and result.get("message", "").startswith("INPUT:"):
        await state.set_state(SettingTitle.awaiting_title)
        await call.message.edit_text(
            "🏷 <b>Введи свой титул</b> (1–20 символов):",
            parse_mode="HTML",
            reply_markup=back_to_main(),
        )
        await call.answer()
        return
    await call.answer(result["message"], show_alert=True)
    text, kb = await _render_shop(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
```

- [ ] **Step 4: Add FSM handlers**

Add after `cb_shop_buy`:

```python
@router.message(SettingTitle.awaiting_title, F.text)
async def handle_title_input(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 1 or len(title) > 20:
        await message.answer("⚠️ Титул должен быть от 1 до 20 символов. Попробуй ещё раз:")
        return
    await client.set_title(message.from_user.id, title)
    await state.clear()
    await message.answer(
        f"🏷 Титул установлен: <b>{title}</b>",
        parse_mode="HTML",
    )


@router.message(SettingTitle.awaiting_title)
async def handle_title_non_text(message: Message):
    await message.answer("Пришли текст (1–20 символов).")
```

- [ ] **Step 5: Commit**

```bash
git add services/bot-service/app/handlers/shop.py
git commit -m "feat(bot): shop — 4 items active, custom_title FSM"
```

---

### Task 9: bot-service — keyboards.py + quests.py (skip button + free hint)

**Files:**
- Modify: `services/bot-service/app/keyboards.py`
- Modify: `services/bot-service/app/handlers/quests.py`

- [ ] **Step 1: Add quest_skips param to quest_detail keyboard**

In `services/bot-service/app/keyboards.py`, replace `quest_detail`:

```python
def quest_detail(quest_id: int, has_hints: bool = False, quest_skips: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="▶️ Начать", callback_data=f"quest:start:{quest_id}")
    if has_hints:
        kb.button(text="💡 Подсказка", callback_data=f"quest:hint:{quest_id}")
    if quest_skips > 0:
        kb.button(text=f"⏭ Пропустить ({quest_skips})", callback_data=f"quest:skip:{quest_id}")
    kb.button(text="◀️ К списку", callback_data="menu:quests")
    kb.adjust(1)
    return kb.as_markup()
```

- [ ] **Step 2: Update cb_quest_detail to pass quest_skips**

In `services/bot-service/app/handlers/quests.py`, add `import asyncio` at the top if not already present.

Replace `cb_quest_detail`:

```python
@router.callback_query(F.data.startswith("quest:detail:"))
async def cb_quest_detail(call: CallbackQuery):
    quest_id = int(call.data.split(":")[2])
    quest, profile = await asyncio.gather(
        client.get_quest_detail(quest_id),
        client.get_profile(call.from_user.id),
    )
    quest_skips = profile["stats"].get("quest_skips", 0)
    has_hints = bool(quest.get("hints"))
    await call.message.edit_text(
        _quest_card(quest),
        reply_markup=quest_detail(quest_id, has_hints, quest_skips),
        parse_mode="HTML",
    )
    await call.answer()
```

- [ ] **Step 3: Update cb_hint to try free hint first**

Replace `cb_hint`:

```python
@router.callback_query(F.data.startswith("quest:hint:"))
async def cb_hint(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    quest = data.get("quest") or await client.get_quest_detail(int(call.data.split(":")[2]))
    hints = quest.get("hints", [])
    if not hints:
        await call.answer("Подсказок нет", show_alert=True)
        return

    first_hint = hints[0]
    cost = first_hint.get("cost", 5)

    consume = await client.consume_free_hint(call.from_user.id)
    if not consume["used_free"]:
        try:
            await client.spend_crystals(call.from_user.id, cost, "hint")
        except Exception:
            await call.answer(f"💎 Недостаточно кристаллов (нужно {cost} 💎)", show_alert=True)
            return

    hint_detail = await client.use_hint(first_hint["id"], call.from_user.id)
    free_note = " (бесплатно 💡)" if consume["used_free"] else ""
    await call.answer(f"💡 {hint_detail['text']}{free_note}", show_alert=True)
```

- [ ] **Step 4: Add cb_quest_skip handler**

Add after `cb_hint`:

```python
@router.callback_query(F.data.startswith("quest:skip:"))
async def cb_quest_skip(call: CallbackQuery):
    quest_id = int(call.data.split(":")[2])
    user_id = call.from_user.id

    consume = await client.consume_skip(user_id)
    if not consume["consumed"]:
        await call.answer("⏭ Нет токенов пропуска. Купи в магазине!", show_alert=True)
        return

    await client.skip_quest(user_id, quest_id)
    await call.answer("⏭ Квест пропущен!", show_alert=True)
    await _show_categories(call.message, user_id, edit=True)
```

- [ ] **Step 5: Commit**

```bash
git add services/bot-service/app/keyboards.py \
        services/bot-service/app/handlers/quests.py
git commit -m "feat(bot): skip button in quest detail, free hint check, skip callback"
```

---

### Task 10: bot-service — leaderboard.py (weekly tab)

**Files:**
- Modify: `services/bot-service/app/handlers/leaderboard.py`

- [ ] **Step 1: Replace _toggle_kb with 3-button version**

Replace `_toggle_kb`:

```python
def _toggle_kb(metric: str):
    kb = InlineKeyboardBuilder()
    xp_label = "🏆 По XP" + (" ✓" if metric == "xp" else "")
    elo_label = "⚔️ По ELO" + (" ✓" if metric == "elo" else "")
    week_label = "🗓 Неделя" + (" ✓" if metric == "weekly" else "")
    kb.button(text=xp_label, callback_data="lb:xp")
    kb.button(text=elo_label, callback_data="lb:elo")
    kb.button(text=week_label, callback_data="lb:weekly")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(2, 1, 1)
    return kb.as_markup()
```

- [ ] **Step 2: Replace _render to handle weekly metric**

Replace `_render`:

```python
def _render(data: dict) -> str:
    metric = data["metric"]
    entries = data.get("entries", [])
    if not entries:
        if metric == "weekly":
            return "🗓 За эту неделю ещё никто не набрал XP. Начни первым!"
        return "🏆 Таблица лидеров пуста. Будь первым — проходи квесты!"

    if metric == "weekly":
        title = f"🗓 <b>Топ за неделю {data.get('week', '')}</b>"
        lines = [title, ""]
        for e in entries:
            medal = MEDALS.get(e["rank"], f"<b>{e['rank']}.</b>")
            lines.append(f"{medal} {e['name']} — +{e['xp_gained']} XP")
    else:
        title = "🏆 <b>Топ по XP</b>" if metric == "xp" else "⚔️ <b>Топ по ELO</b>"
        lines = [title, ""]
        for e in entries:
            medal = MEDALS.get(e["rank"], f"<b>{e['rank']}.</b>")
            if metric == "xp":
                value = f"ур.{e['level']} · {e['xp']}xp"
            else:
                value = f"{e['elo_rating']} ELO"
            lines.append(f"{medal} {e['name']} — {value}")

    me = data.get("me")
    if me:
        if metric == "weekly":
            lines.append(f"\n<i>Ты на {me['rank']}-м месте (+{me['xp_gained']} XP)</i>")
        else:
            lines.append(f"\n<i>Ты на {me['rank']}-м месте</i>")
    return "\n".join(lines)
```

- [ ] **Step 3: Update _show to branch on weekly**

Replace `_show`:

```python
async def _show(message: Message, user_id: int, metric: str, edit: bool):
    if metric == "weekly":
        data = await client.get_weekly_leaderboard(user_id)
        data["metric"] = "weekly"
    else:
        data = await client.get_leaderboard(metric, user_id)
    text = _render(data)
    kb = _toggle_kb(metric)
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
```

- [ ] **Step 4: Commit**

```bash
git add services/bot-service/app/handlers/leaderboard.py
git commit -m "feat(bot): weekly XP leaderboard tab"
```

---

## Self-Review Checklist

- **Spec coverage:** All 4 shop items implemented; weekly leaderboard implemented; bot handlers updated; tests written for each feature
- **Placeholder scan:** None — all steps contain complete code
- **Type consistency:**
  - `make_user` defined once in `conftest.py`, imported in both test files
  - `leaderboard_weekly` returns `{"week", "entries", "me"}` — matches `_render` in bot
  - `consume_free_hint` returns `{"used_free", "free_hints_left"}` — matches bot handler
  - `consume_skip` returns `{"consumed", "skips_left"}` — matches bot handler
  - `quest_detail(quest_id, has_hints, quest_skips)` signature consistent across keyboards.py and quests.py
