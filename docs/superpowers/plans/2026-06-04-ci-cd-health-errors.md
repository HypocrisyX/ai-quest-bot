# CI/CD + Healthchecks + Error Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить `/health` эндпоинты с проверкой БД, глобальные exception handlers со структурированным логированием, и GitHub Actions CI/CD (lint + docker build + push to ghcr.io).

**Architecture:** Каждый FastAPI-сервис получает `/health` эндпоинт (проверяет `SELECT 1` через engine), глобальный handler для Exception и RequestValidationError в `main.py`. CI запускает ruff и `docker build` для каждого сервиса при пуше. CD пушит образы в ghcr.io при мерже в main.

**Tech Stack:** FastAPI, SQLAlchemy asyncpg, GitHub Actions, ruff, ghcr.io (GitHub Container Registry)

---

## File Map

**Создать:**
- `ruff.toml` — конфиг линтера
- `.github/workflows/ci.yml` — lint + docker build при push/PR
- `.github/workflows/cd.yml` — build + push to ghcr.io при push в main

**Изменить:**
- `services/user-service/main.py`
- `services/quest-service/main.py`
- `services/ai-judge-service/main.py`
- `services/social-service/main.py`
- `services/notification-service/main.py`
- `services/bot-service/main.py`

---

### Task 1: ruff config + /health в user-service

**Files:**
- Create: `ruff.toml`
- Modify: `services/user-service/main.py`

- [ ] **Step 1: Создать `ruff.toml`**

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = ["E501"]
```

- [ ] **Step 2: Обновить `services/user-service/main.py`**

```python
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("user-service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="User Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "user-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "service": "user-service"})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 3: Проверить что сервис стартует без ошибок**

```bash
docker-compose up -d --build user-service
docker logs ai-quest-bot-user-service-1 2>&1 | tail -5
# Ожидается: Application startup complete.
```

- [ ] **Step 4: Проверить /health**

```bash
curl http://localhost:8001/health
# Ожидается: {"status":"ok","service":"user-service"}
```

- [ ] **Step 5: Commit**

```bash
git add ruff.toml services/user-service/main.py
git commit -m "feat: add /health and error handlers to user-service"
```

---

### Task 2: /health + error handling в quest, ai-judge, social, notification

**Files:**
- Modify: `services/quest-service/main.py`
- Modify: `services/ai-judge-service/main.py`
- Modify: `services/social-service/main.py`
- Modify: `services/notification-service/main.py`

- [ ] **Step 1: Обновить `services/quest-service/main.py`**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("quest-service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Quest Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "quest-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "service": "quest-service"})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 2: Обновить `services/ai-judge-service/main.py`**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ai-judge-service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="AI Judge Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "ai-judge-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "service": "ai-judge-service"})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 3: Обновить `services/social-service/main.py`**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("social-service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Social Service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "social-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "service": "social-service"})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 4: Обновить `services/notification-service/main.py`**

```python
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.router import router
from app.worker import start_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("notification-service")


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


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "notification-service"}
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "service": "notification-service"})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 5: Пересобрать и проверить все 4 сервиса**

```bash
docker-compose up -d --build quest-service ai-judge-service social-service notification-service
sleep 5
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
# Все должны вернуть {"status":"ok","service":"..."}
```

- [ ] **Step 6: Commit**

```bash
git add services/quest-service/main.py services/ai-judge-service/main.py \
        services/social-service/main.py services/notification-service/main.py
git commit -m "feat: add /health and error handlers to remaining FastAPI services"
```

---

### Task 3: /health в bot-service

**Files:**
- Modify: `services/bot-service/main.py`

- [ ] **Step 1: Обновить `services/bot-service/main.py`**

```python
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


async def run_health_server() -> None:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Health server running on :8080")


async def main() -> None:
    await run_health_server()

    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
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


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Добавить порт healthcheck в docker-compose.yml для bot-service**

В секции `bot-service` добавить:
```yaml
  bot-service:
    build: ./services/bot-service
    ports:
      - "8080:8080"
    environment:
      ...
```

- [ ] **Step 3: Пересобрать и проверить**

```bash
docker-compose up -d --build bot-service
sleep 5
curl http://localhost:8080/health
# Ожидается: {"status":"ok","service":"bot-service"}
```

- [ ] **Step 4: Commit**

```bash
git add services/bot-service/main.py docker-compose.yml
git commit -m "feat: add /health HTTP server to bot-service on port 8080"
```

---

### Task 4: GitHub Actions CI (lint + build)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Создать `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check services/

  build:
    name: Docker Build — ${{ matrix.service }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        service:
          - user-service
          - quest-service
          - ai-judge-service
          - social-service
          - notification-service
          - bot-service
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: |
          docker build \
            -t ghcr.io/${{ github.repository_owner }}/${{ matrix.service }}:ci \
            ./services/${{ matrix.service }}
```

- [ ] **Step 2: Убедиться что ruff не ломается локально**

```bash
pip install ruff
ruff check services/
# Ожидается: All checks passed! или список предупреждений без exit code 1
```

- [ ] **Step 3: Commit и проверить Actions**

```bash
git add .github/workflows/ci.yml ruff.toml
git commit -m "ci: add lint and docker build checks on push/PR"
git push
# Открыть https://github.com/HypocrisyX/ai-quest-bot/actions
# Ожидается: workflow запустился и прошёл
```

---

### Task 5: GitHub Actions CD (push to ghcr.io)

**Files:**
- Create: `.github/workflows/cd.yml`

- [ ] **Step 1: Создать `.github/workflows/cd.yml`**

```yaml
name: CD

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ghcr.io/${{ github.repository_owner }}

jobs:
  push:
    name: Push — ${{ matrix.service }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    strategy:
      fail-fast: false
      matrix:
        service:
          - user-service
          - quest-service
          - ai-judge-service
          - social-service
          - notification-service
          - bot-service
    steps:
      - uses: actions/checkout@v4

      - name: Log in to ghcr.io
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./services/${{ matrix.service }}
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/${{ matrix.service }}:latest
            ghcr.io/${{ github.repository_owner }}/${{ matrix.service }}:${{ github.sha }}
```

- [ ] **Step 2: Commit и проверить CD**

```bash
git add .github/workflows/cd.yml
git commit -m "ci: add CD workflow — push images to ghcr.io on main"
git push
# Открыть https://github.com/HypocrisyX/ai-quest-bot/actions
# Ожидается: CD workflow запустился, образы появились в
# https://github.com/HypocrisyX?tab=packages
```

---

## Итог

После всех задач:
- `curl http://localhost:800{1..5}/health` → `{"status":"ok"}`
- `curl http://localhost:8080/health` → `{"status":"ok"}` (bot-service)
- 500 ошибки возвращают `{"detail":"Internal server error"}`, не traceback
- GitHub Actions: каждый PR проверяется lint + docker build
- Push в main → образы обновляются в ghcr.io автоматически
