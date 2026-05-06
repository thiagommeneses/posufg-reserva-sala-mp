---
name: git-commit
description: >
  Use this skill whenever creating a git commit in this project. This skill ensures commits are
  executed inside the Docker container (where pre-commit hooks run correctly), uses the project's
  .gitconfig for consistent author/committer identity, and verifies the environment is up before
  committing. Use when the user says "commit", "commite", "faça um commit", "salve as alterações",
  or any variation of requesting a git commit.
---

# Git Commit Skill

This project runs pre-commit hooks (ruff lint, ruff format, pytest) that depend on the Docker
container environment. Commits must be executed inside the `web` container to ensure hooks pass
correctly.

## Why this matters

The host machine may not have pre-commit installed or the correct Python environment configured.
The container has the full toolchain (uv, ruff, pytest, pre-commit) available. The project's
`.gitconfig` is mounted at `/root/.gitconfig` inside the container, ensuring the same
author/committer identity as the host.

## Commit Workflow

Follow these steps in order every time you need to create a commit:

### 1. Ensure the Docker environment is running

Check if containers are up. If not, start them:

```bash
docker compose ps --status running --format "{{.Name}}" | grep -q web || docker compose up -d
```

Wait for the db to be healthy before proceeding:

```bash
docker compose exec -T web echo 'Container ready'
```

If this fails, run `docker compose up -d` and wait for services to be healthy.

### 2. Stage changes on the host

Stage files normally from the host (the volume mount shares the git state):

```bash
git add <files>
```

### 3. Commit inside the container

Execute the commit inside the web container. The `.gitconfig` mounted at `/root/.gitconfig`
provides author identity and safe.directory configuration:

```bash
docker compose exec -T web git commit -m "<message>"
```

The commit message must follow Conventional Commits format:
```
type(scope): description
```

Examples:
- `feat: add user authentication`
- `fix(api): resolve pagination offset error`
- `refactor(spaces): extract availability logic to service layer`
- `test: add integration tests for reservation lifecycle`
- `docs: update API endpoint documentation`
- `chore: update dependencies`

### 4. Handle pre-commit hook failures

The pre-commit hooks run automatically on commit and handle linting, formatting, and testing.
There is no need to run feedback loops separately — the hooks already cover:

1. **ruff --fix** — auto-fixes lint issues in staged Python files
2. **ruff-format** — auto-formats staged Python files
3. **pytest** — runs the full test suite (fails commit if tests fail or coverage < 80%)
4. **conventional-pre-commit** — validates commit message format

If a hook fails:
- **ruff auto-fixed files**: re-stage the modified files (`git add .`) and commit again
- **pytest failure**: fix the failing test or code, re-stage, and commit again
- **Invalid commit message**: use the correct Conventional Commits format and commit again

### 5. Verify success

After the commit, verify it was created correctly:

```bash
docker compose exec -T web git log --oneline -1
```

## Infrastructure Details

### Project .gitconfig (`.gitconfig` at project root)

This file is mounted read-only at `/root/.gitconfig` inside the container via docker-compose.yml:

```ini
[user]
    name = André Teles
    email = andre.telestp@gmail.com

[safe]
    directory = /app
```

The `safe.directory` entry is required because the `/app` volume is owned by the host user
(uid 1000) but the container runs as root. Without it, git refuses to operate on the repository.

### Docker Compose volume mount

```yaml
volumes:
  - .:/app
  - ./.gitconfig:/root/.gitconfig:ro
```

### Pre-commit hooks that run on commit

1. **conventional-pre-commit** (commit-msg stage) — validates message format
2. **ruff** — lints and auto-fixes staged Python files
3. **ruff-format** — formats staged Python files
4. **pytest** — runs the full test suite

All hooks run inside the container environment where uv and all dev dependencies are available.
There is no need to run these tools manually before committing — the hooks are the enforcement
mechanism and will catch any issues.

## Troubleshooting

### "Container not running"

```bash
docker compose up -d
# Wait for db health check
docker compose exec -T db pg_isready -U postgres
```

### "pre-commit not found" (on host)

This error means you accidentally tried to commit from the host. Always commit inside the
container using `docker compose exec -T web git commit -m "..."`.


### "dubious ownership" error

The `.gitconfig` already includes `safe.directory = /app`. If you still see this error, the
`.gitconfig` mount may not be active. Restart the container: `docker compose down && docker compose up -d`.

### Pre-commit hook fails

Fix the issue in the source code, re-stage the files, and try the commit again. Common failures:
- **ruff check**: lint errors in Python code (often auto-fixed — just re-stage)
- **ruff format**: formatting issues (auto-fixed — just re-stage)
- **pytest**: test failures or coverage below 80%
- **conventional-pre-commit**: invalid commit message format

## Quick Reference

```bash
# Full commit workflow (copy-paste ready)
docker compose ps --status running --format "{{.Name}}" | grep -q web || docker compose up -d
git add <files>
docker compose exec -T web git commit -m "type(scope): description"
```
