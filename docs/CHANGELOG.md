# Changelog

Все значимые изменения в проекте фиксируются здесь.

---

## [Unreleased]

> Сюда добавляются изменения, которые ещё не вошли в релиз.

---

## 2026-06-04 (продолжение)

### Тесты

**Добавлено:**
- `user-service/tests/` — 20 тестов: репозиторий (XP/leveling, crystals, streak, referrals) + HTTP роутеры
- `quest-service/tests/` — 13 тестов: репозиторий (get_quest, start/complete/fail, hints, get_quest_detail)
- `ai-judge-service/tests/` — 8 тестов: unit-тесты `_compute_weighted_score` + мокнутый Claude в `evaluate_answer` + интеграционный тест роутера
- `pytest.ini` и `requirements-test.txt` для каждого из трёх сервисов
- `.github/workflows/ci.yml` расширен: новый job `test` с PostgreSQL service container, запускается для user/quest/ai-judge после lint

---

## 2026-06-04

### CI/CD + Healthchecks + Error Handling

**Добавлено:**
- `ruff.toml` — линтер ruff с правилами E, F, I (pyflakes + isort)
- `GET /health` во всех 5 FastAPI сервисах — проверяет `SELECT 1` к БД, возвращает `{"status":"ok"}` или 503
- `GET /health` в bot-service — лёгкий aiohttp HTTP-сервер на порту 8080
- Глобальный `Exception` handler в каждом FastAPI сервисе — возвращает `{"detail":"Internal server error"}` вместо traceback
- `RequestValidationError` handler — чистый 422 с деталями ошибки
- Структурированное логирование (`%(asctime)s %(levelname)s %(name)s %(message)s`) в каждом сервисе
- `.github/workflows/ci.yml` — lint (ruff==0.15.15) + docker build для каждого сервиса; build гейтован на lint
- `.github/workflows/cd.yml` — push образов в ghcr.io; запускается только после успешного CI (workflow_run)

**Исправлено:**
- Bot-service: aiohttp runner не закрывался при shutdown (`await runner.cleanup()`)
- Bot-service: `TELEGRAM_BOT_TOKEN` теперь проверяется на старте с понятной ошибкой
- Notification-service: bot session утекал если `start_consumer` падал при старте
- Notification-service worker: исключения в обработчиках теперь пробрасываются, чтобы aio-pika делал nack+requeue
- User-service: achievements endpoint всегда возвращал `[]` вместо реальных данных
- `ruff.toml`: исправлен формат заголовков (native `ruff.toml` vs `pyproject.toml`-style)

---

## 2026-06-03

### Seed Data

**Добавлено:**
- `scripts/seed_quests.py` — 10 квестов по 5 уровням (theory, practice, challenge, boss) по теме AI-инструментов; критерии с весами, подсказки за кристаллы
- `scripts/seed_notifications.py` — 8 шаблонов уведомлений (quest, duel, streak, system)
- `scripts/requirements.txt` — зависимости для seed-скриптов (`asyncpg`)
- `Makefile` — команды `make up`, `make down`, `make seed`

### RabbitMQ Event-Driven Messaging

**Добавлено:**
- `bot-service/app/events.py` — публикация событий в RabbitMQ (topic exchange `quest_bot`)
  - `level.up` — при повышении уровня после квеста
  - `streak.milestone` — при серии 7/30/100 дней
  - `duel.finished` — при завершении дуэли
- `notification-service/app/worker.py` — RabbitMQ консьюмер; шлёт Telegram-сообщения через aiogram Bot
- Воркер запускается в lifespan FastAPI приложения notification-service
- `RABBITMQ_URL` добавлен в docker-compose для bot-service и notification-service

### Telegram Bot (bot-service)

**Добавлено:**
- `bot-service` — новый сервис на aiogram 3 с FSM на Redis
- Хендлеры: `/start` (регистрация, главное меню), `/profile`, `/quests`, `/leaderboard`, `/daily`
- `app/client.py` — aiohttp HTTP-клиенты ко всем внутренним сервисам
- `app/keyboards.py` — inline-клавиатуры (главное меню, список квестов, результат)
- Квест-флоу через FSM: выбор квеста → старт → ответ → оценка AI → XP/streak
- Порог прохождения квеста: score >= 60
- Подсказки стоят кристаллы

### Dockerfiles + Infrastructure

**Добавлено:**
- `Dockerfile` для каждого из 6 сервисов (`python:3.12-slim`, запускает `alembic upgrade head` перед uvicorn)
- `requirements.txt` для каждого сервиса с pinned версиями
- `docker-compose.yml` расширен: все 5 FastAPI сервисов (порты 8001–8005) + bot-service
- `depends_on` с `condition: service_healthy` для всех сервисов
- `.env.example` — шаблон для `ANTHROPIC_API_KEY` и `TELEGRAM_BOT_TOKEN`

### Исправления (инфраструктура)

**Исправлено:**
- `alembic/env.py` во всех сервисах: читает `DATABASE_URL` из переменной окружения, а не из захардкоженного `alembic.ini` (критично для Docker)
- `get_db()` во всех сервисах: транзакция теперь управляется внутри `get_db` (`async with session.begin()`), убран `async with db.begin()` из роутеров (конфликт с SQLAlchemy autobegin)

### Initial Scaffold

**Добавлено:**
- 5 микросервисов: `user-service`, `quest-service`, `ai-judge-service`, `social-service`, `notification-service`
- Каждый сервис: SQLAlchemy async models, Alembic миграции (`0001_initial`), Pydantic schemas, async репозитории, FastAPI роутеры
- `docker-compose.yml` — инфраструктура: 5 PostgreSQL БД, Redis, RabbitMQ
- `ai-judge-service/app/judge.py` — интеграция с Claude API (claude-sonnet-4-6), prompt caching системного промпта, JSON-ответ с оценкой по критериям

---

## Структура сервисов

| Сервис | Порт | БД порт | Описание |
|--------|------|---------|----------|
| user-service | 8001 | 5432 | Пользователи, XP, кристаллы, достижения, рефералы |
| quest-service | 8002 | 5433 | Квесты, прогресс, подсказки, ежедневные задания |
| ai-judge-service | 8003 | 5434 | Оценка ответов через Claude API |
| social-service | 8004 | 5435 | Дуэли, лидерборд, подписки |
| notification-service | 8005 | 5436 | Уведомления, шаблоны, RabbitMQ consumer |
| bot-service | 8080¹ | — | Telegram bot (aiogram 3), FSM на Redis |

¹ Порт 8080 — healthcheck. Бот работает через Telegram long-polling.

---

## Быстрый старт

```bash
cp .env.example .env          # заполнить ANTHROPIC_API_KEY и TELEGRAM_BOT_TOKEN
docker-compose up --build     # поднять все сервисы
pip install asyncpg
python3 scripts/seed_quests.py
python3 scripts/seed_notifications.py
```
