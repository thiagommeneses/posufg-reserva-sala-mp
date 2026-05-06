.PHONY: install test lint format up down build logs shell migrate makemigrations unmigrate createsuperuser createsuperuser-auto pre-commit-install release-rc release changelog help

COMPOSE := docker compose
WEB_SERVICE := web

install:
	uv sync --dev

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f $(WEB_SERVICE)

shell:
	$(COMPOSE) exec $(WEB_SERVICE) bash

migrate:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py migrate

makemigrations:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py makemigrations

unmigrate:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py migrate $(app) $(migration)

createsuperuser:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py createsuperuser

createsuperuser-auto:
	$(COMPOSE) exec $(WEB_SERVICE) \
		env DJANGO_SUPERUSER_USERNAME=$(username) \
		DJANGO_SUPERUSER_EMAIL=$(email) \
		DJANGO_SUPERUSER_PASSWORD=$(password) \
		python manage.py createsuperuser --noinput

pre-commit-install:
	uv run pre-commit install --hook-type commit-msg --hook-type pre-commit

release-rc:
	$(COMPOSE) exec $(WEB_SERVICE) uv run cz bump --prerelease rc

release:
	$(COMPOSE) exec $(WEB_SERVICE) uv run cz bump

changelog:
	$(COMPOSE) exec $(WEB_SERVICE) uv run cz changelog

help:
	@echo "Available targets:"
	@echo "  install              - Install dependencies with uv (including dev)"
	@echo "  test                 - Run pytest test suite"
	@echo "  lint                 - Run ruff linter"
	@echo "  format               - Run ruff formatter"
	@echo "  up                   - Start Docker Compose services"
	@echo "  down                 - Stop Docker Compose services"
	@echo "  build                - Build Docker Compose images"
	@echo "  logs                 - Follow web service logs"
	@echo "  shell                - Open bash shell in the web container"
	@echo "  migrate              - Apply Django migrations"
	@echo "  makemigrations       - Generate Django migrations"
	@echo "  unmigrate app=<> migration=<> - Rollback Django migrations"
	@echo "  createsuperuser      - Create a Django superuser (interactive)"
	@echo "  createsuperuser-auto - Create a Django superuser (non-interactive, requires username=, email=, password=)"
	@echo "  pre-commit-install   - Install pre-commit hooks"
	@echo "  release-rc           - Create a release candidate tag"
	@echo "  release              - Create a final release tag"
	@echo "  changelog            - Generate CHANGELOG.md"
	@echo "  help                 - Show this help message"
