# PRD — Django Project Setup with uv, pytest, Docker, and Developer Tooling

## Problem Statement

Desenvolvedores precisam de uma forma padronizada de inicializar um projeto Django com tooling moderno (uv, pytest, ruff), ambiente containerizado (Docker + docker-compose) e guardrails de qualidade (pre-commit, conventional commits) sem configurar cada ferramenta manualmente. Também precisam de atalhos documentados para tarefas frequentes (testes, lint, migrations, subir/derrubar ambiente).

## Solution

Criar um template de projeto Django que inclui:
- Inicialização do projeto com uv
- Estrutura da aplicação Django (projeto `config` + app `core`)
- Configuração de pytest com pytest-django
- Linter ruff configurado para Django
- Ambiente Docker com docker-compose (app + PostgreSQL)
- Makefile com atalhos para comandos frequentes
- Pre-commit com conventional commits, ruff e pytest
- AGENTS.md documentando os comandos principais do workflow

## User Stories

1. As a developer, I want to initialize a Django project with uv so that I can manage dependencies efficiently
2. As a developer, I want pytest configured so that I can write and run tests easily
3. As a developer, I want a linter configured so that I can maintain code quality standards
4. As a developer, I want a basic Django project structure so that I can start building features immediately
5. As a developer, I want to start the whole stack with a single command so that I have a reproducible environment
6. As a developer, I want to access the application container shell so that I can run Django management commands
7. As a developer, I want simplified commands (via Makefile) for tests, lint, docker and migrations so that I don't need to memorize long commands
8. As a developer, I want my commits to follow conventional commits and pass lint/tests automatically via pre-commit so that the codebase stays consistent
9. As a developer, I want an AGENTS.md centralizing all essential commands so that onboarding is fast

## Implementation Decisions

### Modules and files to create
- `pyproject.toml` — uv config, dependencies, and tooling config (pytest and ruff centralized here)
- `config/` — Django project (settings, urls, wsgi, asgi)
- `core/` — example Django app
- `Dockerfile` — application image (Python 3.12 + uv)
- `docker-compose.yml` — service orchestration (web + PostgreSQL db)
- `.pre-commit-config.yaml` — pre-commit hooks
- `Makefile` — shortcuts for common commands
- `AGENTS.md` — workflow command documentation

### Technical decisions
- Python 3.12 as target version
- uv for package and virtualenv management
- Django 5.2.x LTS
- pytest + pytest-django for tests (configured in `[tool.pytest.ini_options]` inside `pyproject.toml`)
- ruff for lint and format (configured in `[tool.ruff]` inside `pyproject.toml`)
- PostgreSQL as database in docker-compose (service `db` with named volume `postgres_data`)
- Volumes in docker-compose for hot-reload during development
- Django project package named `config`, example app named `core`
- Pre-commit with hooks:
  - `conventional-pre-commit` (validates commit messages)
  - `ruff` (lint + format)
  - Local hook running `uv run pytest` with `pass_filenames: false` and `always_run: true` (runs full suite)
- Makefile targets: `install`, `test`, `lint`, `format`, `up`, `down`, `build`, `logs`, `shell`, `migrate`, `makemigrations`, `unmigrate`, `createsuperuser`, `pre-commit-install`, `help`

### Commands documented in AGENTS.md
- Run tests: `make test` (or `uv run pytest`)
- Run lint: `make lint` (or `uv run ruff check .`)
- Start application: `make up` (or `docker compose up -d`)
- Stop application: `make down` (or `docker compose down`)
- Access container: `make shell` (or `docker compose exec web bash`)
- Generate migration: `make makemigrations` (or `docker compose exec web python manage.py makemigrations`)
- Apply migration: `make migrate`
- Rollback migration: `make unmigrate app=<app_name> migration=<migration_name_or_zero>`

## Testing Decisions

- Tests must verify external behavior, not implementation details
- Verify that the Django project can be created and started
- ruff must pass across all generated code
- Test suite must be runnable and pass initially
- Verify that uv installs all dependencies correctly
- Verify that `docker compose up` starts services and the app responds
- Verify that `docker compose exec web bash` accesses the container
- Verify that pre-commit rejects commits that do not follow conventional commits
- Verify that pre-commit runs ruff and pytest before the commit completes
- Verify that all Makefile targets work as expected

## Out of Scope

- Production deployment configurations
- Advanced Django features (custom auth, advanced admin, etc.)
- CI/CD pipelines
- Domain migrations beyond Django initial ones
- Cache (Redis) or task queue (Celery) configuration
- Observability (structured logs, metrics, tracing)

## Further Notes

- Target Python version: 3.12
- All configuration files live at the project root
- Django project package: `config`
- Initial Django app: `core`
- Makefile assumes docker compose v2 is available
- Pre-commit is installed locally only (not enforced in CI at this stage)
