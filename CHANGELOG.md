## v0.2.0 (2026-05-06)

### Feat

- configure ralph-workflow feedback loops for lint, format, and test
- configure pytest-cov with 80% minimum coverage threshold
- add Makefile targets for release workflow (release-rc, release, changelog)

## v0.1.0 (2026-05-06)

### Feat

- configure commitizen for semantic versioning and release management
- **sandbox**: add Docker CE CLI and Docker Compose plugin
- add non-interactive createsuperuser-auto Makefile target
- configure pre-commit with conventional commits, ruff, and pytest
- align ruff config with PRD (line-length 100, full rule set) and fix all lint issues
- add Makefile with common development shortcuts
- configure ruff linter and formatter in pyproject.toml
- add Docker environment with docker-compose and PostgreSQL
- configure pytest with Django settings and add smoke test
- create Django project structure with config and core app
- initialize project structure with uv, Django 5.2, and tooling deps
- **sandbox**: add Python 3.12, uv, Node.js 22, Go 1.24 to sandbox image
- add Docker sandbox and --model/--sandbox flags to ralph scripts
