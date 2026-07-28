# AGENTS.md

## Software Quality

This codebase will outlive you. Every shortcut you take becomes someone else's burden.
Every hack compounds into technical debt that slows the whole team down.

You are not just writing code. You are shaping the future of this project.
The patterns you establish will be copied. The corners you cut will be cut again.

Fight entropy. Leave the codebase better than you found it.

## Feedback Loops

Before committing, run ALL feedback loops defined in `ralph-workflow.config.json`.
Do NOT commit if any feedback loop fails. Fix issues first.

## Task Prioritization

When choosing the next task, prioritize in this order:

1. Architectural decisions and core abstractions
2. Integration points between modules
3. Unknown unknowns and spike work
4. Standard features and implementation
5. Polish, cleanup, and quick wins

Fail fast on risky work. Save easy wins for later.

## Step Size

Keep changes small and focused:

- One logical change per commit
- If a task feels too large, break it into subtasks
- Prefer multiple small commits over one large commit
- Run feedback loops after each change, not at the end

Quality over speed. Small steps compound into big progress.

## Code Conventions

- No `any` types unless absolutely unavoidable (add a comment explaining why)
- Prefer explicit returns on functions
- Use descriptive variable names
- Keep functions small and focused

## Project Workflow Commands

### Setup

Install all dependencies (including dev):
```bash
make install
# or
uv sync --dev
```

### Testing

Run the pytest test suite:
```bash
make test
# or
uv run pytest
```

### Linting

Run the ruff linter:
```bash
make lint
# or
uv run ruff check .
```

Run the ruff formatter:
```bash
make format
# or
uv run ruff format .
```

### Docker

Start the application and database services:
```bash
make up
# or
docker compose up -d
```

Stop all services:
```bash
make down
# or
docker compose down
```

Build Docker images:
```bash
make build
```

### Dependency Changes in Development

When `pyproject.toml` or `uv.lock` changes, the container's virtualenv (`/opt/venv`) must be updated. Because the virtualenv lives outside the mounted project directory (`/app`), it persists across restarts. You do **not** need to rebuild the image.

Instead, sync dependencies directly inside the running container:
```bash
make shell
uv sync --frozen
```
Or in one command:
```bash
docker compose exec web uv sync --frozen
```

**Adding a new dependency: regenerate the lockfile first**

`uv sync --frozen` refuses to run when `uv.lock` is out of date — that is the whole point of `--frozen`. So editing `pyproject.toml` alone is never enough: both the container sync above and `make build` (which runs `uv sync --frozen` at image build time) will fail until the lockfile catches up.

Run this on the host, before anything else:
```bash
uv lock
```

Full sequence after adding a dependency:
```bash
uv lock                    # regenerate uv.lock from pyproject.toml
make build                 # rebuild the image with the new dependency
make up
```

Skipping `uv lock` produces a confusing failure mode: the web container starts, crashes on `ModuleNotFoundError` for the package you just added, and `docker compose exec` then reports `service "web" is not running` — which looks like a Docker problem but is a lockfile problem.

**Container stopped due to missing dependencies**

If the web container fails to start with a `ModuleNotFoundError` (or similar import error), the container is not running and `docker compose exec` will fail. In this case, the virtualenv must be rebuilt inside the image:

```bash
make build
make up
```

This happens when new dependencies are added but the running container was not synced before the Django auto-reloader triggered (e.g., saving a file that imports the missing package).

Only run `make build` if the `Dockerfile` itself or the base image changes.

Follow web service logs:
```bash
make logs
```

Open a bash shell inside the web container:
```bash
make shell
# or
docker compose exec web bash
```

The Django development server runs on port `8000`.

### Database Migrations

Generate new migrations:
```bash
make makemigrations
# or
docker compose exec web python manage.py makemigrations
```

Apply migrations:
```bash
make migrate
# or
docker compose exec web python manage.py migrate
```

Rollback migrations:
```bash
make unmigrate app=<app_name> migration=<migration_name_or_zero>
```

Create a superuser (interactive):
```bash
make createsuperuser
```

Create a superuser (non-interactive):
```bash
make createsuperuser-auto username=<username> email=<email> password=<password>
```

This uses Django's `--noinput` flag with `DJANGO_SUPERUSER_*` environment variables. Useful for CI/CD or when TTY is not available.

### Pre-commit

Install pre-commit and commit-msg hooks:
```bash
make pre-commit-install
```

Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) format:
```
type(scope): description
```

Examples:
```
feat: add user model
fix(core): resolve pagination bug
```

On every commit the hooks will:
1. Validate the commit message format (`conventional-pre-commit`)
2. Run ruff linter and formatter on staged files
3. Run the full pytest suite

### Release and Versioning

This project uses [Semantic Versioning](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/) to automate version bumps.

Release flow:
```
1. Development on main with conventional commits (feat, fix, etc.)
2. make release-rc    → creates tag v1.0.0rc1 → git push origin main --tags
3. make release-rc    → creates tag v1.0.0rc2 → git push origin main --tags
4. make release       → creates tag v1.0.0    → git push origin main --tags
                         (CI triggers production deploy)
```

Create a release candidate (RC):
```bash
make release-rc
# or
docker compose exec web uv run cz bump --prerelease rc
```

Create a final release:
```bash
make release
# or
docker compose exec web uv run cz bump
```

Generate or update the changelog:
```bash
make changelog
# or
docker compose exec web uv run cz changelog
```

After `make release-rc` or `make release`, always push the bump commit and tag to remote:
```bash
git push origin main --tags
```

Tags trigger the CI/CD pipeline for production deploy.

### Code Coverage

Code coverage is enforced with a minimum threshold of 80%. Tests will fail if coverage drops below this level.

Run tests with coverage reporting:
```bash
make test
# or
uv run pytest
```

Coverage runs automatically on every test execution and displays:
- Overall coverage percentage
- Missing lines (`term-missing` report) for easy identification of uncovered code

Files excluded from coverage measurement: migrations, `manage.py`, `config/wsgi.py`, `config/asgi.py`.

### MCP'S improve

#### Grep Vercel
If you are unsure how to do something, use `gh_grep` to search code examples from GitHub.

#### Context7
When you need to search docs, use `context7` tools.