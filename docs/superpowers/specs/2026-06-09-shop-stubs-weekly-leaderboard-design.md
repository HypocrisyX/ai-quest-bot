# Shop Stubs + Weekly Leaderboard — Design Spec

**Date:** 2026-06-09  
**Status:** Approved

---

## Scope

Two independent features:

1. **Shop stubs → real items**: implement all 4 placeholder shop items
   (`streak_freeze`, `hint_pack`, `skip_quest`, `custom_title`)
2. **Weekly leaderboard**: new "Неделя" tab showing XP delta for the current week

---

## Part 1: Shop Items

### Database migration — `0003_shop_items` (user-service)

One migration adds three columns to `user_stats`:

```sql
ALTER TABLE user_stats ADD COLUMN streak_freeze_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_stats ADD COLUMN free_hints          INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_stats ADD COLUMN quest_skips         INTEGER NOT NULL DEFAULT 0;
```

`custom_title` reuses the existing `class_title` column (String 32) — no migration needed.

---

### 🧊 streak_freeze (80 💎)

**Effect:** preserves the streak when a user misses exactly one day.

**repository.py — `update_streak` change:**
```
gap = today - streak_last_at
if gap == 2 days AND streak_freeze_count > 0:
    streak_freeze_count -= 1
    streak_last_at = today  # bridge the gap, streak unchanged
elif gap == 1 day:
    streak_days += 1
    streak_last_at = today
else:
    streak_days = 1
    streak_last_at = today
```

**purchase_item:** `streak_freeze_count += 1`, message: "🧊 Заморозка добавлена! Сохранит серию при пропуске дня."

**Bot `shop.py` header:** show `streak_freeze_count` like boost count.

---

### 💡 hint_pack (60 💎) — grants 3 free hints

**Effect:** next 3 hint uses cost 0 crystals.

**New endpoint** in user-service:
```
POST /users/{user_id}/hints/free/consume
Response: {"used_free": bool, "free_hints_left": int}
```
Atomically: if `free_hints > 0` → decrement, return `used_free=true`; else return `used_free=false`.

**purchase_item:** `free_hints += 3`, message: "💡 3 бесплатные подсказки добавлены!"

**Bot `quests.py` — `cb_hint` change:**
```python
consume = await client.consume_free_hint(user_id)
if not consume["used_free"]:
    await client.spend_crystals(user_id, cost, "hint")
```

**Bot `client.py`:** add `consume_free_hint(user_id)` → `POST /users/{id}/hints/free/consume`.

**`UserStatsOut` schema:** add `free_hints: int = 0`.

---

### ⏭ skip_quest (120 💎) — grants 1 skip token

**Effect:** marks a quest as completed (score=0, xp=0), unlocking the next one.

**New endpoint** in quest-service:
```
POST /quests/{quest_id}/skip?user_id={user_id}
Response: {"skipped": true}
```
Logic: just calls `complete_quest(user_id, quest_id, score=0, xp=0)`. Token consumption happens in user-service *before* this call (bot orchestrates the two steps).

**New endpoint** in user-service:
```
POST /users/{user_id}/skips/consume
Response: {"consumed": bool, "skips_left": int}
```

**purchase_item:** `quest_skips += 1`, message: "⏭ Пропуск квеста добавлен!"

**Bot `keyboards.py` — `quest_detail`:** add "⏭ Пропустить" button when `quest_skips > 0` (pass `skips` param to keyboard builder).

**Bot `quests.py`:** new callback `quest:skip:{quest_id}` — calls `client.skip_quest(user_id, quest_id)`, shows confirm message, refreshes category list.

**`UserStatsOut` schema:** add `quest_skips: int = 0`.

---

### 🏷 custom_title (200 💎) — custom profile title

**Effect:** user sets any text (1–20 chars) as their `class_title`.

**New endpoint** in user-service:
```
PATCH /users/{user_id}/title
Body: {"title": "..."}   # 1–20 chars, stripped; validated via Pydantic Field
Response: {"class_title": "..."}
```

**purchase_item:** returns special message prefix `"INPUT:custom_title"`. Bot detects this prefix and enters FSM instead of showing an alert.

**Bot `shop.py` — `cb_shop_buy` change:** if `result["message"].startswith("INPUT:")`, enter FSM `SettingTitle.awaiting_title`.

**New FSM `SettingTitle`** in `shop.py`:
- State `awaiting_title` (text): validate 1–20 chars, call `client.set_title(user_id, text)`, confirm "🏷 Титул установлен: {text}", exit FSM.
- Non-text messages (photo, sticker, etc.): answer "Пришли текст (1–20 символов)", stay in state.
- Cancel (/cancel or /start): clear FSM with note "Титул не задан. Кристаллы не возвращаются."

**Bot `client.py`:** add `set_title(user_id, title)` → `PATCH /users/{id}/title`.

---

### Common: `purchase_item` for new items

Mark all 4 items `available=True` in `SHOP_ITEMS`. Add handlers in `purchase_item`:

```python
elif item_key == "streak_freeze":
    stats.streak_freeze_count = (stats.streak_freeze_count or 0) + 1
    msg = "🧊 Заморозка добавлена! Сохранит серию при пропуске дня."
elif item_key == "hint_pack":
    stats.free_hints = (stats.free_hints or 0) + 3
    msg = "💡 3 бесплатные подсказки добавлены!"
elif item_key == "skip_quest":
    stats.quest_skips = (stats.quest_skips or 0) + 1
    msg = "⏭ Пропуск квеста добавлен!"
elif item_key == "custom_title":
    msg = "INPUT:custom_title"
```

---

## Part 2: Weekly Leaderboard

### New endpoint in user-service

```
GET /leaderboard/weekly?week=2026-W23&user_id=123
```

**Logic:**
1. Parse `week` (ISO format `YYYY-Www`) → Monday (start) and following Monday (end).
2. Query `xp_history`: `SELECT user_id, SUM(delta_xp) AS xp_gained FROM xp_history WHERE created_at >= start AND created_at < end GROUP BY user_id`.
3. Join with `users` table for display names.
4. Sort `xp_gained DESC`, assign rank 1-based, return top-10.
5. If `user_id` provided, also compute their rank + delta.

**Default:** `week` defaults to current ISO week if omitted.

**Response:**
```json
{
  "week": "2026-W23",
  "entries": [
    {"rank": 1, "user_id": 123, "name": "@alice", "xp_gained": 350},
    ...
  ],
  "me": {"rank": 5, "xp_gained": 120}
}
```

### Bot changes

**`leaderboard.py`:**
- Add `"🗓 Неделя"` button to `_toggle_kb()` — 3 buttons arranged 2+1.
- New render branch for `metric == "weekly"`: shows `xp_gained` per entry.
- `_show()`: if `metric == "weekly"`, call `client.get_weekly_leaderboard(user_id)`.

**`client.py`:** add `get_weekly_leaderboard(user_id)` → `GET /leaderboard/weekly?user_id={id}`.

---

## Data flow summary

```
Weekly Leaderboard:
Bot → GET /leaderboard/weekly (user-service)
    → SELECT SUM(delta_xp) FROM xp_history GROUP BY user_id for current week
    → return ranked list

Skip Quest:
Bot → POST /users/{id}/skips/consume (user-service) → {consumed, skips_left}
if consumed: Bot → POST /quests/{id}/skip?user_id= (quest-service)
    → complete_quest(score=0, xp=0) → {skipped: true}

Free Hint:
Bot → POST /users/{id}/hints/free/consume (user-service) → {used_free, free_hints_left}
if not used_free: Bot → POST /users/{id}/crystals (spend cost)
Bot → POST /quests/hints/{hint_id}/use (quest-service)
```

---

## Tests

| Service | New tests |
|---------|-----------|
| user-service | `streak_freeze` on missed day; no freeze consumed on 2+ day gap; `hint_pack` consume decrements; consume when 0 returns `used_free=false`; skip consume; `set_title` validates len 1/20/21; weekly leaderboard aggregates XP correctly |
| quest-service | skip marks quest completed score=0 xp=0; returns 409 when no skips left (consume fails) |

---

## Build order

1. Migration `0003_shop_items` + model + schema (user-service)
2. New user-service endpoints: `consume_free_hint`, `consume_skip`, `set_title`, `weekly_leaderboard`
3. Quest-service `skip` endpoint
4. Bot: `shop.py` (4 items + FSM), `quests.py` (hint + skip), `keyboards.py` (skip button), `leaderboard.py` (weekly tab), `client.py` (new methods)
5. Tests
