## Unreleased

### Feat

- **ai**: max_capacity e reescrita de follow-ups no chat
- **knowledge**: adicionar historico de conversas e avaliacao automatica
- **knowledge**: adiciona página web de consulta às normas
- **ai**: adiciona endpoint document-qa com RAG e testes
- **knowledge**: indexa normas e habilita Q&A documental com RAG

### Fix

- **ai**: mensagens amigáveis com detalhe no console
- **ai**: mapeamento de sinônimos e prompts de busca

### Refactor

- **reservations**: centralizar regras de conflito em validators
- **reservations**: centralizar regras de conflito em validators

## v0.3.0 (2026-05-27)

### Feat

- **admin_dashboard**: implement admin maintenance block management pages
- **admin_dashboard**: implement admin reservation management pages
- **admin_dashboard**: implement admin space management pages
- add Makefile seed targets and document seed workflow
- **admin_dashboard**: implement admin dashboard with real-time occupancy overview
- **core**: create seed_data management command with modular seed infrastructure
- **reservations**: implement user-facing reservation list, detail, cancel, reschedule and check-in views
- **reservations**: implement user-facing reservation creation page
- **spaces**: implement user-facing space detail and availability page
- **spaces**: implement user-facing space search page with HTMX filtering
- **reservations**: implement user reservation listing with filtering
- **reservations**: implement admin occupancy overview endpoint
- **reservations**: implement admin maintenance blocks API
- **reservations**: implement auto-release of no-show reservations
- **reservations**: implement check-in mechanism
- **reservations**: implement self-service cancellation and rescheduling
- **reservations**: implement reservation creation with conflict validation
- **spaces**: implement real-time availability check for spaces
- **spaces**: implement Space API with attribute-based filtering
- **reservations**: create reservations app with Reservation and MaintenanceBlock models
- **spaces**: create spaces app with Space, Attribute, and SpaceAttribute models
- create accounts app with authentication views
- install HTMX, DaisyUI, and configure template infrastructure
- install Django REST Framework and configure API base
- add git-commit skill with container-based workflow
- add context7 skill and update PRD for space reservation system
- add skill-creator for creating and evaluating agent skills
- add release-generator skill for automated commitizen releases

### Fix

- **spaces**: hide filter spinner on initial load and wire checkbox indicator
- **admin_dashboard**: hide filter indicator on initial reservation list load
- **admin_dashboard**: stop infinite loading spinner in spaces status column
- **spaces**: show filter spinner only on explicit submit and hide on load
- **spaces**: align filter button vertically with input fields
- **accounts**: redirect login and register to /spaces/ instead of htmx-test
- **test**: remove duplicate user creation in admin cancel test

### Refactor

- **git-commit**: simplify exec commands removing unnecessary cd /app

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
