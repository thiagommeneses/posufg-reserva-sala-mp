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
10. As a developer, I want to create release candidates (RC) so that I can validate changes before a final release
11. As a developer, I want to create a final release with semantic versioning so that production deploys are triggered automatically via tags
12. As a developer, I want an auto-generated CHANGELOG so that stakeholders can track what changed between versions
13. As a developer, I want code coverage enforcement (minimum 80%) so that the test suite maintains meaningful coverage as the project grows

## Implementation Decisions

### Modules and files to create/modify
- `pyproject.toml` — uv config, dependencies, tooling config (pytest, ruff, commitizen, coverage centralized here)
- `config/` — Django project (settings, urls, wsgi, asgi)
- `core/` — example Django app
- `Dockerfile` — application image (Python 3.12 + uv)
- `docker-compose.yml` — service orchestration (web + PostgreSQL db)
- `.pre-commit-config.yaml` — pre-commit hooks
- `Makefile` — shortcuts for common commands (including release-rc, release, changelog)
- `AGENTS.md` — workflow command documentation
- `CHANGELOG.md` — auto-generated changelog (managed by commitizen)

### Technical decisions
- Python 3.12 as target version
- uv for package and virtualenv management
- Django 5.2.x LTS
- pytest + pytest-django for tests (configured in `[tool.pytest.ini_options]` inside `pyproject.toml`)
- pytest-cov for code coverage measurement with minimum threshold of 80% (`--cov-fail-under=80`)
- ruff for lint and format (configured in `[tool.ruff]` inside `pyproject.toml`)
  - `line-length = 100`
  - `select = ["E", "F", "W", "I", "N", "UP", "C90", "D", "S", "ASYNC", "PERF", "T20", "RET", "PT"]`
- PostgreSQL as database in docker-compose (service `db` with named volume `postgres_data`)
- Volumes in docker-compose for hot-reload during development
- Django project package named `config`, example app named `core`
- Pre-commit with hooks:
  - `conventional-pre-commit` (validates commit messages)
  - `ruff` (lint + format)
  - Local hook running `uv run pytest` with `pass_filenames: false` and `always_run: true` (runs full suite)
- Makefile targets: `install`, `test`, `lint`, `format`, `up`, `down`, `build`, `logs`, `shell`, `migrate`, `makemigrations`, `unmigrate`, `createsuperuser`, `createsuperuser-auto`, `pre-commit-install`, `release-rc`, `release`, `changelog`, `help`

### Release and Versioning
- Semantic Versioning with unified versioning — all packages share the same version
- commitizen for release management (configured in `[tool.commitizen]` inside `pyproject.toml`)
- commitizen reads Conventional Commits history (`feat`, `fix`, `refactor`, etc.) to determine the next version number
- On bump, commitizen automatically updates the `version` field in all `pyproject.toml` files via `version_files`
- `CHANGELOG.md` is auto-generated on each bump
- Git tags are created in the format `vX.Y.Z` (e.g., `v1.0.0`, `v1.0.0rc1`)
- Tags trigger production deploy via CI (GitLab CI / GitHub Actions)

### Code Coverage
- pytest-cov integrated with pytest for coverage measurement
- Configured in `[tool.pytest.ini_options]` with `addopts = --cov=. --cov-report=term-missing --cov-fail-under=80`
- Minimum coverage threshold: 80% — tests fail if coverage drops below this
- Coverage report shows missing lines (`term-missing`) for easy identification of uncovered code
- `.coveragerc` or `[tool.coverage]` in `pyproject.toml` to exclude migrations, config, and manage.py from coverage

### Release Flow
```
1. Development on main with conventional commits (feat, fix, etc.)
2. make release-rc    → creates tag v1.0.0rc1 → git push origin main --tags
3. make release-rc    → creates tag v1.0.0rc2 → git push origin main --tags
4. make release       → creates tag v1.0.0    → git push origin main --tags
                        (CI triggers production deploy)
```

### Commands documented in AGENTS.md
- Run tests: `make test` (or `uv run pytest`)
- Run tests with coverage: `make test` (pytest-cov is integrated — coverage runs automatically)
- Run lint: `make lint` (or `uv run ruff check .`)
- Start application: `make up` (or `docker compose up -d`)
- Stop application: `make down` (or `docker compose down`)
- Access container: `make shell` (or `docker compose exec web bash`)
- Generate migration: `make makemigrations` (or `docker compose exec web python manage.py makemigrations`)
- Apply migration: `make migrate`
- Rollback migration: `make unmigrate app=<app_name> migration=<migration_name_or_zero>`
- Create superuser: `make createsuperuser` (interactive) and `make createsuperuser-auto username=<username> email=<email> password=<password>` (non-interactive)
- Release candidate: `make release-rc` (or `docker compose exec web uv run cz bump --prerelease rc`)
- Final release: `make release` (or `docker compose exec web uv run cz bump`)
- Generate changelog: `make changelog` (or `docker compose exec web uv run cz changelog`)

## Testing Decisions

- Tests must verify external behavior, not implementation details
- Verify that the Django project can be created and started
- ruff must pass across all generated code
- Test suite must be runnable and pass initially
- Code coverage must meet or exceed 80% threshold — tests fail otherwise
- Verify that uv installs all dependencies correctly
- Verify that `docker compose up` starts services and the app responds
- Verify that `docker compose exec web bash` accesses the container
- Verify that pre-commit rejects commits that do not follow conventional commits
- Verify that pre-commit runs ruff and pytest before the commit completes
- Verify that all Makefile targets work as expected
- Verify that `make release-rc` creates a valid release candidate tag
- Verify that `make release` creates a valid release tag
- Verify that `make changelog` generates/updates CHANGELOG.md
- Verify that commitizen rejects a bump when there are no new conventional commits

## Out of Scope

- Production deployment configurations (infrastructure, Kubernetes, etc.)
- Advanced Django features (custom auth, advanced admin, etc.)
- CI/CD pipeline definition files (GitHub Actions / GitLab CI YAML) — only the tag-based trigger contract is defined
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
- After `make release-rc` or `make release`, always run `git push origin main --tags` to push the bump commit and tag to remote
- The tag triggers the CI pipeline for production deploy
- commitizen is added to dev dependencies (`commitizen` package)
- pytest-cov is added to dev dependencies (`pytest-cov` package)
- Coverage excludes: migrations, manage.py, config/wsgi.py, config/asgi.py
