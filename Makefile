.PHONY: install test contraste lint format css up down build logs shell migrate makemigrations unmigrate createsuperuser createsuperuser-auto pre-commit-install seed seed-flush release-rc release changelog help

COMPOSE := docker compose
WEB_SERVICE := web

install:
	$(COMPOSE) exec $(WEB_SERVICE) uv sync --dev

test:
	$(COMPOSE) exec $(WEB_SERVICE) uv run pytest

lint:
	$(COMPOSE) exec $(WEB_SERVICE) uv run ruff check .

# Guarda de contraste (WCAG 2.1 AA). Sobe um Chromium e mede a cor pintada de
# cada nó de texto das telas principais. Fica fora do `make test` porque é o
# único teste que precisa de navegador; na primeira vez, baixe-o com
# `docker compose exec web uv run playwright install --with-deps chromium`.
contraste:
	$(COMPOSE) exec $(WEB_SERVICE) uv run pytest -m visual --no-cov

format:
	$(COMPOSE) exec $(WEB_SERVICE) uv run ruff format .

# Recompila o bundle do Tailwind. O watcher do `tailwind runserver` depende
# de eventos do sistema de arquivos, que não chegam em projeto sob /mnt/c no
# WSL2 nem em arquivos extraídos com o contêiner já de pé. Quando ele não
# dispara, só as classes novas somem — e a tela fica quase certa, sem erro.
css:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py tailwind build --force

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
	$(COMPOSE) exec $(WEB_SERVICE) uv run pre-commit install --hook-type commit-msg --hook-type pre-commit

seed:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py seed_data

seed-flush:
	$(COMPOSE) exec $(WEB_SERVICE) python manage.py seed_data --flush

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
	@echo "  contraste            - Run the WCAG AA contrast guard (needs Chromium)"
	@echo "  lint                 - Run ruff linter"
	@echo "  format               - Run ruff formatter"
	@echo "  css                  - Rebuild the Tailwind stylesheet (after template changes)"
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
	@echo "  seed                 - Populate database with default demo data (idempotent)"
	@echo "  seed-flush           - Remove seeded data and re-populate fresh"
	@echo "  release-rc           - Create a release candidate tag"
	@echo "  release              - Create a final release tag"
	@echo "  changelog            - Generate CHANGELOG.md"
	@echo "  help                 - Show this help message"
