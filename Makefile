PYTHON = python3
PROD_FILE = -f docker-compose.prod.yml

# ── Dev ───────────────────────────────────────────────────────────────────────

.PHONY: up down logs seed seed-quests seed-notifications

up:
	docker-compose up --build -d

down:
	docker-compose down

logs:
	docker-compose logs -f

seed: seed-quests seed-notifications seed-achievements

seed-quests:
	$(PYTHON) scripts/seed_quests.py

seed-notifications:
	$(PYTHON) scripts/seed_notifications.py

seed-achievements:
	$(PYTHON) scripts/seed_achievements.py

# ── Prod ──────────────────────────────────────────────────────────────────────

.PHONY: prod-up prod-down prod-logs prod-build

prod-up:
	docker-compose $(PROD_FILE) up -d

prod-down:
	docker-compose $(PROD_FILE) down

prod-logs:
	docker-compose $(PROD_FILE) logs -f

prod-build:
	docker-compose $(PROD_FILE) build

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: test test-user test-quest test-judge

test: test-user test-quest test-judge

test-user:
	cd services/user-service && pytest -v

test-quest:
	cd services/quest-service && pytest -v

test-judge:
	cd services/ai-judge-service && pytest -v
