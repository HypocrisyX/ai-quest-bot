PYTHON = python3

.PHONY: up down seed seed-quests seed-notifications logs

up:
	docker-compose up --build -d

down:
	docker-compose down

logs:
	docker-compose logs -f

seed: seed-quests seed-notifications

seed-quests:
	$(PYTHON) scripts/seed_quests.py

seed-notifications:
	$(PYTHON) scripts/seed_notifications.py
