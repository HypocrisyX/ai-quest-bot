# Changelog

Все значимые изменения в проекте фиксируются здесь.

---

## [Unreleased]

### Тесты: починка набора + покрытие social/marketplace

**Исправлено (важное):**
- Тестовый conftest во **всех 5 сервисах** был сломан: session-scoped engine конфликтовал с function-scoped event-loop'ом pytest-asyncio 0.24 → `InterfaceError: another operation is in progress`. CI test-job, вероятно, был красный. Переписано на per-test engine + `NullPool` (живёт в петле теста), транзакция откатывается после каждого теста
- Дрейф модель↔миграция в `LeaderboardEntry`: unique-constraint `uq_leaderboard_user_period` и индекс были только в миграции, не в модели → `create_all` (тесты) их не создавал, `on_conflict` падал. Добавлены в `__table_args__` (тест поймал)

**Добавлено:**
- Тесты social-service (14): дуэли (создание, резолв победитель/ничья, self/not-found/already-played, TTL-истечение), лидерборд (upsert + порядок + апдейт), follows
- social-service и marketplace-service добавлены в CI test-матрицу
- CI test-step выставляет `DATABASE_URL` (на тестовую БД, чтобы `/health` проходил) и `INTERNAL_TOKEN=""` (open-режим для тест-клиента)

**Прогон локально:** user 55 · quest 22 · ai-judge 10 · social 14 · marketplace 13 = **114 тестов зелёные**.

### Дуэли: срок жизни 24 часа

**Добавлено:**
- `pending`-дуэль истекает через **24 часа** (`DUEL_TTL`). Истёкшую нельзя принять — `accept_and_resolve` отклоняет (409 «Эта дуэль истекла»), проверка пересчитывает возраст при каждой попытке
- Бот показывает «⏳ Эта дуэль истекла (срок — 24 часа)» в инвайте и при нажатии «Принять»; при создании пишет «Дуэль ждёт соперника 24 часа»
- Lazy-enforcement без cron: строка остаётся `pending`, но принять её уже нельзя

**Проверено:** свежая дуэль принимается (200); состаренная на 25ч → 409.

### Маркетплейс: лимит листингов + предупреждение про ссылки

**Добавлено:**
- Лимит **10 активных листингов** на продавца (`MAX_LISTINGS_PER_SELLER`). Превышение → 409. Бот делает пред-проверку до начала формы (не даёт заполнить всё впустую) и enforce'ит сервис
- Предупреждение покупателю при выдаче товара с внешней ссылкой: «⚠️ Внешняя ссылка от продавца. Переходи на свой риск»
- Дисклеймер в меню маркетплейса: товары создают пользователи, покупай на свой риск, о нарушениях — «Пожаловаться»
- Тест на подсчёт активных листингов (снятые не считаются)

**Проверено:** 10 листингов ок, 11-й → 409; после снятия одного снова можно создать.

### Безопасность: блокировка строк против гонки баланса

**Добавлено:**
- `SELECT ... FOR UPDATE` (`_stats_for_update`) во всех функциях, мутирующих `user_stats`: `add_crystals`, `add_xp`, `update_streak`, `purchase_item` (магазин), `marketplace_settle`, `apply_duel_result`, `check_and_grant_achievements`
- Многострочные операции (settle, дуэль) лочат обе строки в порядке возрастания id (`_lock_two`) — без deadlock'ов
- Читающие функции (профиль, лидерборд, `user_rank`) остались без блокировок
- Закрывает двойную трату / уход баланса в минус / потерянные обновления при параллельных запросах

**Проверено вживую:** 5 параллельных `settle` (баланс 100, цена 100) → прошёл ровно 1, баланс 0 (не отрицательный), продавец +90 один раз; 10 параллельных `add_xp(+50)` → ровно 500 (без потерянных обновлений).

### Безопасность: серверная валидация экономики

**Добавлено:**
- marketplace `ListingCreate`: цена 10–10000, title 1–128, payload_text 1–8000, лимиты длины описания/файла/ссылки (Pydantic `Field` → 422)
- marketplace `PurchaseRequest`: price/seller_earned ≥ 0
- user-service `MarketplaceSettleRequest`: price > 0; в repo `marketplace_settle` защита `invalid_price` на случай внутреннего вызова
- Раньше эти проверки были только в боте — теперь дублируются в сервисах (defense-in-depth: даже багнутый/обойдённый вызов не создаст листинг с ценой 0 или settle с отрицательной суммой)
- Тесты: отклонение цены вне диапазона, пустого title/payload; settle с invalid_price

**Проверено:** цена 0/999999, пустой title/payload → 422; settle с 0/−50 → 422; валидный листинг → 201.

### Безопасность: межсервисный токен

**Добавлено:**
- Аутентификация между сервисами через заголовок `X-Internal-Token`. Все 6 FastAPI-сервисов проверяют его middleware'ом; запросы без/с неверным токеном → 401
- `/health` (и `/docs`, `/openapi.json`, `/redoc`) остаются открытыми — Docker healthcheck'и не ломаются
- «Мягкий» режим: если `INTERNAL_TOKEN` пустой — проверка выключена (удобно для чисто локального запуска)
- Бот носит токен сам (в `aiohttp` сессии) — тестирование через Telegram не меняется
- `INTERNAL_TOKEN` в dev-compose (дефолт `dev-internal-token`), prod-compose (**обязателен**, `${INTERNAL_TOKEN:?}`) и `.env.example`
- Закрывает класс атак «любой может начислить себе кристаллы / слить пользователей» через прямой вызов сервисов или публичный nginx `/api/*`

**Проверено:** health открыт, защищённые эндпоинты всех 6 сервисов отдают 401 без токена и 200 с верным.

### Маркетплейс (тестовая версия)

**Добавлено:**
- Новый сервис `marketplace-service` (своя БД, порт 8006) — листинги и покупки
- Раздел «🏪 Маркетплейс» в боте, открывается **только после прохождения всех квестов** (`GET /me/training-complete` в quest-service)
- Продавец выставляет товар (FSM): название → описание → цена (10–10000 💎) → текст-товар → опц. файл/ссылка
- Покупатель: каталог с пагинацией → купить за кристаллы → товар выдаётся (текст + файл + ссылка). Цифровой товар продаётся без лимита
- Экономика: оплата кристаллами, продавец получает `цена × 90%`, комиссия **10%** — приложению (`POST /marketplace/settle` в user-service). Звёзды добавятся отдельным слоем позже
- «📦 Мои товары» (продажи/доход, снятие своих), «🎒 Мои покупки» (повторная выдача)
- Защиты: нельзя купить свой товар, нет двойного списания, проверка баланса
- Модерация: кнопка «Пожаловаться» (уведомляет админов) + раздел «🏪 Маркетплейс» в `/admin` (снятие любого товара)
- Тесты: marketplace repo (создание, идемпотентность покупки, статистика), settle (комиссия/недостаток/self), training-progress
- CI/CD матрицы, prod-compose и nginx дополнены новым сервисом

### Критерии, порог 70, картинки и бонусные квесты

**Добавлено:**
- Критерии оценки для всех 20 новых квестов (order_index 11–30) — теперь у всех 30 квестов есть критерии для AI-судьи. У квестов-картинок критерии учитывают, что AI не видит изображение (проверяют факт отправки + промпты + описание)
- **Приём изображений**: для квестов-картинок бот принимает фото (сохраняет `file_id`) или ссылку; текстовые квесты — как раньше. Подсказка при неверном типе ответа
- **Бонусные («золотые») квесты**: при старте с шансом 20% квест становится бонусным (⭐). За результат 90+ — сверху +20 💎 и +50 XP. Решается в FSM, без изменений в БД
- Рефакторинг: единый `_process_answer` для текстовых и фото-ответов

**Изменено:**
- Проходной балл квеста: 60 → **70**

### Рефералка

**Добавлено:**
- Реферальная программа по ссылке `t.me/bot?start=ref_<id>`: пригласивший и приглашённый **оба** получают +100 💎
- Бонус начисляется только когда по ссылке приходит **новый** пользователь (защита от фарма существующими)
- `/ref` (и кнопка «🤝 Друзья») — личная ссылка + статистика (приглашено / заработано)
- user-service: `repository.complete_referral()` (грант обоим, идемпотентно, защита от self) + `referral_stats()`, `POST /referrals` теперь начисляет награды, `GET /users/{id}/referrals/stats`, константа `REFERRAL_BONUS=100`
- bot: единый диспетчер deep-link `handlers/deeplink.py` (дуэли + рефералы), общий util `app/links.py` (deep-link с кешем username), `handlers/referral.py`
- Рефакторинг: deep-link дуэлей вынесен в `duels.show_duel_invite`, дублирующий код ссылок убран
- Тесты: грант обоим, self-реферал, идемпотентность без двойного начисления, подсчёт статистики

### Живой лидерборд

**Добавлено:**
- Лидерборд теперь реальный — считается на лету из user-service (раньше читал пустую таблицу `leaderboard_entries` в social-service)
- Два рейтинга с переключателем: 🏆 По XP (уровень + XP) и ⚔️ По ELO (дуэли); топ-10
- Показывает твоё место («Ты на N-м месте»)
- user-service: `repository.leaderboard(metric, limit)` + `user_rank(user_id, metric)`, эндпоинт `GET /leaderboard?metric=xp|elo&user_id=`
- bot: `client.get_leaderboard(metric, user_id)` переключён на user-service, хендлер с инлайн-переключателем
- Тесты: ранжирование по уровню+XP, по ELO, своё место, отсутствующий юзер
- Недельные срезы пока не делаем (нужен трекинг дельт по периодам — позже)

### Админ-панель в боте

**Добавлено:**
- `/admin` — панель только для админов (доступ по `ADMIN_IDS`, comma-separated Telegram ID). Не-админ получает свой ID, чтобы себя добавить
- 📊 Сводка: всего участников, активных сегодня, квестов/прохождений, дуэлей
- 👥 Участники: пагинированный список (имя, уровень, XP, кристаллы, ELO, квесты, даты регистрации/активности)
- ⚔️ Квесты: все квесты по мирам со счётчиком прохождений
- Admin-эндпоинты: user-service `GET /admin/stats`, `GET /admin/users`; quest-service `GET /admin/stats`, `GET /admin/quests`; social-service `GET /admin/stats`
- `ADMIN_IDS` добавлен в docker-compose и `.env.example`

### Дуэли (квест-формат, инвайт по ссылке)

**Добавлено:**
- Дуэль 1-на-1 по ссылке: челленджер выбирает квест, отвечает первым, получает ссылку `t.me/bot?start=duel_<код>`; друг открывает ссылку, принимает вызов, отвечает на тот же квест → резолв
- Тестовый режим (AI off): оба ответа = 100 баллов → **ничья**. Структура готова к AI-оценке (ответы обоих сохраняются в БД для будущего пересчёта)
- Награды: ELO по формуле Эло (K=32, zero-sum, пол 100), кристаллы — победа +15 / ничья +5 обоим / проигрыш +0
- social-service: миграция `0002` (код-инвайт, nullable opponent, тексты ответов), `create_duel`/`get_duel_by_code`/`accept_and_resolve`, эндпоинты `POST /duels`, `GET /duels/code/{code}`, `POST /duels/{code}/accept`
- user-service: `apply_duel_result()` — пересчёт ELO + кристаллы (владеет рейтингами), эндпоинт `POST /duels/apply`, формула `_elo_delta`
- bot-service: `handlers/duels.py` — FSM создания/принятия, deep-link `/start duel_<код>` (приоритетнее обычного start), результат показывается обоим (оппоненту inline, челленджеру — сообщением). Кнопка «⚔️ Дуэль» в меню
- Защиты: нельзя принять свой вызов, нельзя сыграть дважды
- Тесты: ничья без смены ELO, zero-sum победа (+16/−16), победитель растёт/проигравший падает, пол ELO

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
