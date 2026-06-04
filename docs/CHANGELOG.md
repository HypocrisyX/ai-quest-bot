# Changelog

Все значимые изменения в проекте фиксируются здесь.

---

## [Unreleased]

### Достижения

**Добавлено:**
- 8 достижений с авто-выдачей: первый квест, 5/10/25 квестов, 2/3 уровень, серия 3/7 дней
- Условия разблокировки в коде (`repository.ACHIEVEMENT_RULES`), отображение и награды — в БД (`achievements`)
- `repository.check_and_grant_achievements()` — проверяет правила по `user_stats`, выдаёт новые, начисляет награды (XP + кристаллы)
- Эндпоинты: `POST /users/{id}/achievements/check` (выдать новые), исправлен `GET /users/{id}/achievements` (теперь возвращает детали + дату)
- Схемы `EarnedAchievementOut`, `GrantedAchievementOut`
- `scripts/seed_achievements.py` (идемпотентный), добавлен в `make seed`
- В боте: проверка после каждого пройденного квеста — новые достижения показываются прямо в результате (`🏅 Достижение: ...`); команда `/achievements` и кнопка в меню (заработанные ✅ / закрытые 🔒)
- Тесты: выдача first_quest с наградой, идемпотентность, блокировка до выполнения условия, достижение по уровню

### Магазин и «Мои квесты»

**Добавлено — Магазин (`/shop`):**
- `⚡️ Буст XP ×2` — рабочий товар: за 50 💎 даёт ×2 XP на следующие 3 квеста (счётчик `user_stats.xp_boost_quests`, применяется в `add_xp` при `quest_complete`, расходуется по 1 за квест)
- 4 заглушки (заморозка серии, набор подсказок, пропуск квеста, свой титул) — помечены «скоро», пока недоступны
- user-service: миграция `0002` (`xp_boost_quests`), `repository.purchase_item()` + `list_shop_items()`, эндпоинты `GET /users/{id}/shop` и `POST /users/{id}/shop/purchase`
- Схемы `ShopItemOut`, `PurchaseRequest/Response`; буст виден в профиле и шапке магазина
- Тесты: покупка буста, недостаток кристаллов, недоступный товар, удвоение XP, буст не применяется к не-квестам

**Добавлено — Мои квесты (`/myquests`):**
- Сводка прогресса: всего пройдено N/total, разбивка по мирам, последние 10 пройденных квестов со счётом
- quest-service: `repository.get_completed_quests()`, эндпоинт `GET /me/completed`, схема `CompletedQuestOut`
- В главное меню добавлены кнопки «📜 Мои квесты» и «🛒 Магазин»

### Категории-«миры» с последовательным открытием

**Добавлено:**
- Меню квестов теперь показывает категории-миры: 📝 Текстовые промпты · 🖼 Генерация изображений · 🎬 Генерация видео
- Миры открываются по очереди как локации в RPG: следующий доступен только когда пройдены ВСЕ квесты предыдущего
- Колонка `quests.category` (`text`/`image`/`video`), миграция `0003`
- `repository.get_categories_with_status()` — статус мира: `unlocked` / `completed` / `locked` / `soon` (открыт, но квестов ещё нет)
- `GET /categories?user_id=` — список миров со статусами
- Схема `CategoryOut`; в боте — `category_menu` с иконками 🔒/✅/🔜 и счётчиком (N/total)
- Хендлеры: `cat:<key>` (открыть мир), `cat:locked`/`cat:soon` (алерты)
- Тесты на разблокировку миров (image закрыт пока text не пройден; video → soon после image)

**Изменено:**
- `GET /quests` теперь фильтрует по `category` вместо `level`; внутри мира — прежний последовательный порядок
- Кнопка «Назад» в списке квестов ведёт к категориям, а не в главное меню
- 25 текстовых квестов → мир `text`, 5 квестов генерации → мир `image`

### Последовательное открытие квестов

**Добавлено:**
- Квесты открываются по порядку: следующий доступен только после прохождения предыдущего (по `order_index`)
- `repository.get_quests_with_status()` — статус каждого квеста: `completed` / `unlocked` / `locked`
- Схема `QuestListItemOut` (QuestOut + `status`)
- В боте: ✅ пройденные, 🔒 закрытые (нажатие → «Сначала пройди предыдущий квест»), активный с обычной иконкой
- Тесты на последовательную логику (первый открыт, открытие после прохождения, все пройдены)

**Изменено:**
- `GET /quests` теперь требует `user_id` и возвращает квесты со статусами
- `client.get_quests(level, user_id)` — добавлен `user_id`

### Тестовый режим AI-проверки

**Добавлено:**
- Флаг `AI_JUDGE_ENABLED` в bot-service: при `false` ответы на квесты одобряются автоматически (score 100) без вызова ai-judge — экономит токены на тестах. Сейчас выключен в `docker-compose.yml`, вернуть AI-проверку = установить `true`

### Контент: +20 квестов

**Добавлено:**
- 15 новых квестов по промптингу на уровень 1 (теперь 18 квестов на уровне)
- 5 квестов по генерации изображений на уровень 2 (первая генерация, стили, negative prompts, параметры, итерации)
- Миграция `0002_widen_ai_tool` — `quests.ai_tool` расширен с 32 до 64 символов (длинные списки инструментов)

**Изменено:**
- Формула XP: уровень 1→2 теперь требует 1100 XP (≈15 из 18 квестов), чтобы квесты генерации изображений на уровне 2 открывались только после прохождения большинства уровня 1. `xp_to_next` по умолчанию = 1100
- `scripts/seed_quests.py` теперь **идемпотентный**: квесты матчатся по `title`, существующие обновляются (id и прогресс пользователей сохраняются), новые добавляются. Критерии пересинхронизируются, подсказки вставляются только если их нет (избегаем FK-конфликта с `user_hints_used`). Скрипт можно запускать повторно без дубликатов

---

## 2026-06-04 (продолжение — Nginx + Production)

### Nginx + Production docker-compose

**Добавлено:**
- `nginx/nginx.conf` — reverse proxy перед всеми 5 FastAPI сервисами:
  - `/health` — собственный Nginx healthcheck
  - `/health/<service>` — прокси к `/health` каждого сервиса
  - `/api/users/`, `/api/quests/`, `/api/judge/`, `/api/social/`, `/api/notify/` — маршрутизация с отрезанием префикса
  - keepalive к upstream-ам, таймауты, логирование
- `nginx/Dockerfile` — `nginx:1.27-alpine` с вшитым конфигом
- `docker-compose.prod.yml` — production-сборка:
  - Нет открытых портов БД, Redis, RabbitMQ на хост
  - Нет RabbitMQ management UI (порт 15672)
  - Нет прямых портов FastAPI-сервисов — только nginx на 80
  - `restart: unless-stopped` на всех контейнерах
  - Лимиты памяти: 512m на большинство сервисов, 1g на ai-judge, 256m на bot, 128m на nginx
  - Ротация логов: 10m × 3 файла через `x-logging` YAML-якорь
  - Redis с `maxmemory 128mb` + LRU eviction
  - `POSTGRES_PASSWORD`, `RABBITMQ_USER`, `RABBITMQ_PASS` как отдельные env-переменные
  - Healthcheck у nginx через wget
- `.env.example` дополнен prod-переменными (`POSTGRES_PASSWORD`, `RABBITMQ_*`)
- `Makefile` расширен: `make prod-up`, `make prod-down`, `make prod-build`, `make prod-logs`, `make test`

## 2026-06-04 (продолжение — тесты)

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
