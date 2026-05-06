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

Create a superuser:
```bash
make createsuperuser
```

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
