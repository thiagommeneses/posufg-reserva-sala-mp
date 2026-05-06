# PRD — Sistema de Reserva de Salas (Reserva de Espaços)

## Problem Statement

Usuários enfrentam fricção ao descobrir e reservar espaços que atendem suas necessidades (capacidade, equipamentos). Administradores perdem controle sobre ocupação real devido a no-shows, shadow booking e fragmentação de canais (planilhas, e-mails, calendários físicos). O resultado é desperdício de espaço, conflitos de agenda e abandono do processo formal de reserva.

## Solution

Um sistema centralizado de reserva de espaços com três pilares (Pareto 80/20):

1. **Calendário Único e Centralizado** — elimina fragmentação; se não está no sistema, não existe.
2. **Liberação Automática de No-shows (Auto-release)** — se o usuário não fizer check-in em 10-15 minutos, a sala volta a ficar disponível.
3. **Filtros por Atributos Mínimos** — busca por capacidade e equipamentos para resolver fricção de descoberta.

## User Stories

### Usuário Final (Cliente)

1. As a user, I want to search spaces by attributes (capacity, equipment) so that I find the right room for my meeting without trial and error.
2. As a user, I want to see real-time availability of spaces so that I trust the system data and don't need to physically check.
3. As a user, I want to create a reservation instantly (without manual approval) so that the process is frictionless.
4. As a user, I want to cancel or reschedule my reservation autonomously so that I don't depend on an administrator.
5. As a user, I want to check-in to confirm my presence so that the system knows I'm using the space.
6. As a user, I want a web interface to browse spaces, make reservations, and manage my bookings so that I don't need to use raw API calls.
7. As a user, I want to register and login to the system so that my reservations are tied to my identity.

### Administrador do Espaço

8. As an admin, I want to register spaces with their attributes (capacity, equipment, location) so that users can discover them.
9. As an admin, I want to define usage policies (max duration, who can book what) so that I maintain control over space allocation.
10. As an admin, I want to see real-time occupancy of all spaces so that I have visibility over my inventory.
11. As an admin, I want to block time slots for maintenance/cleaning so that operational logistics are respected.
12. As an admin, I want the system to auto-release no-show reservations after 10-15 minutes so that spaces aren't wasted.
13. As an admin, I want a dedicated dashboard interface to manage spaces, view occupancy, and handle reservations so that I have full operational control without using the Django admin directly.
14. As an admin, I want to override or cancel any user's reservation so that I can resolve conflicts and prioritize VIP needs.

## Implementation Decisions

### Apps e Módulos

| App | Responsabilidade |
|-----|-----------------|
| `spaces` | Gestão de espaços e seus atributos (CRUD, busca, filtros) |
| `reservations` | Ciclo de vida da reserva (criar, cancelar, reagendar, check-in, auto-release) |
| `accounts` | Autenticação, login/logout, registro, perfil do usuário |
| `dashboard` | Interface administrativa customizada (ocupação, gestão de espaços, manutenção) |

### Modelos de Domínio

#### `spaces.Space`
- `name` (CharField) — nome do espaço
- `description` (TextField, optional) — descrição
- `capacity` (PositiveIntegerField) — capacidade máxima de pessoas
- `location` (CharField) — localização (andar, bloco)
- `is_active` (BooleanField) — se está disponível para reservas
- `created_at` / `updated_at` (DateTimeField)

#### `spaces.Attribute`
- `name` (CharField, unique) — nome do atributo (ex: "TV", "Ar-condicionado", "Webcam")

#### `spaces.SpaceAttribute` (M2M through)
- `space` (FK → Space)
- `attribute` (FK → Attribute)

#### `reservations.Reservation`
- `space` (FK → Space)
- `user` (FK → User)
- `start_time` (DateTimeField)
- `end_time` (DateTimeField)
- `status` (CharField choices: `confirmed`, `cancelled`, `checked_in`, `completed`, `no_show`)
- `checked_in_at` (DateTimeField, nullable)
- `created_at` / `updated_at` (DateTimeField)
- **Constraint:** sem sobreposição de horários para o mesmo espaço (DB-level)

#### `reservations.MaintenanceBlock`
- `space` (FK → Space)
- `start_time` (DateTimeField)
- `end_time` (DateTimeField)
- `reason` (CharField)
- `created_by` (FK → User)

### API Endpoints (DRF)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/spaces/` | Listar espaços (com filtros: capacity, attributes) |
| GET | `/api/spaces/{id}/` | Detalhe do espaço |
| POST | `/api/spaces/` | Criar espaço (admin) |
| PUT/PATCH | `/api/spaces/{id}/` | Atualizar espaço (admin) |
| GET | `/api/spaces/{id}/availability/` | Disponibilidade do espaço (por data) |
| GET | `/api/reservations/` | Listar reservas do usuário |
| POST | `/api/reservations/` | Criar reserva |
| PATCH | `/api/reservations/{id}/cancel/` | Cancelar reserva |
| PATCH | `/api/reservations/{id}/reschedule/` | Reagendar reserva |
| POST | `/api/reservations/{id}/check-in/` | Fazer check-in |
| GET | `/api/admin/occupancy/` | Dashboard de ocupação (admin) |
| POST | `/api/admin/maintenance-blocks/` | Criar bloqueio de manutenção (admin) |

### Páginas da Área do Usuário (`/reservas/`)

| Rota | Página | Descrição |
|------|--------|-----------|
| `/accounts/login/` | Login | Formulário de autenticação |
| `/accounts/register/` | Registro | Formulário de criação de conta |
| `/accounts/logout/` | Logout | Encerra sessão |
| `/spaces/` | Busca de Espaços | Lista com filtros (capacidade, atributos, localização) |
| `/spaces/{id}/` | Detalhe do Espaço | Info + calendário de disponibilidade + botão reservar |
| `/reservations/` | Minhas Reservas | Lista de reservas do usuário (ativas, passadas, canceladas) |
| `/reservations/new/?space={id}` | Nova Reserva | Formulário de seleção de horário |
| `/reservations/{id}/` | Detalhe da Reserva | Status, ações (cancelar, reagendar, check-in) |
| `/reservations/{id}/check-in/` | Check-in | Confirmação de presença (acessível via QR Code) |

### Páginas da Área Administrativa (`/admin-dashboard/`)

| Rota | Página | Descrição |
|------|--------|-----------|
| `/admin-dashboard/` | Dashboard | Visão geral de ocupação em tempo real |
| `/admin-dashboard/spaces/` | Gestão de Espaços | CRUD de espaços e atributos |
| `/admin-dashboard/spaces/{id}/` | Editar Espaço | Formulário de edição com atributos |
| `/admin-dashboard/reservations/` | Gestão de Reservas | Lista de todas as reservas com ações (cancelar, override) |
| `/admin-dashboard/maintenance/` | Bloqueios de Manutenção | Lista + criar bloqueios de manutenção |
| `/admin-dashboard/maintenance/new/` | Novo Bloqueio | Formulário de criação de bloqueio |

### Decisões Técnicas

- **Django REST Framework** — para APIs RESTful
- **django-filter** — para filtros compostos na busca de espaços
- **Django Templates + HTMX + DaisyUI** — interfaces server-side modernas com interatividade sem SPA
- **Tailwind CSS + DaisyUI** — component library para UI moderna e consistente (botões, cards, modais, badges, tabelas, formulários)
- **HTMX** — para atualizações parciais de página (ex: calendário de disponibilidade, ações inline, filtros dinâmicos)
- **Service layer** — lógica de negócio isolada em `services.py` (não nos views)
- **Estado da reserva** — máquina de estados simples (sem lib externa)
- **Auto-release** — management command executável via cron/scheduler (sem Celery no MVP)
- **Check-in** — via endpoint API e via página web (QR Code na porta aponta para a página de check-in)
- **Permissões** — DRF permissions (IsAuthenticated + custom IsAdmin para endpoints de gestão)
- **Permissões (views)** — LoginRequiredMixin para área de usuário, StaffRequiredMixin para área admin
- **Validação de conflito** — constraint de exclusão no PostgreSQL (`ExclusionConstraint` com `btree_gist`)
- **Timezone** — todos os horários em UTC, conversão no frontend
- **Template inheritance** — base layout compartilhado com navegação contextual (usuário vs admin)

### Stack Frontend (DaisyUI + HTMX)

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| Tailwind CSS | 3.x (via CDN ou django-tailwind) | Utility-first CSS framework |
| DaisyUI | 4.x (via CDN) | Componentes pré-estilizados sobre Tailwind |
| HTMX | 2.x (via CDN) | Interatividade server-side (partial swaps, polling) |

#### Componentes DaisyUI utilizados

| Componente | Onde é usado |
|------------|-------------|
| `navbar` | Navegação principal (user e admin) |
| `card` | Cards de espaços na busca, cards de resumo no dashboard |
| `badge` | Status da reserva (confirmed, checked_in, no_show, cancelled) |
| `btn` | Botões de ação (reservar, cancelar, check-in) |
| `modal` | Confirmação de cancelamento, detalhes rápidos |
| `table` | Listagem de reservas, gestão admin |
| `form-control` / `input` / `select` | Formulários de reserva, filtros, login/registro |
| `alert` | Feedback de sucesso/erro (Django messages) |
| `stats` | Cards de métricas no dashboard admin |
| `calendar` / `timeline` | Visualização de disponibilidade |
| `drawer` | Menu lateral no admin dashboard |
| `tabs` | Abas de reservas (ativas, passadas, canceladas) |
| `loading` / `skeleton` | Indicadores de carregamento HTMX |
| `toast` | Notificações inline (combinado com Django messages) |
| `dropdown` | Ações rápidas em linhas de tabela |
| `theme-controller` | Suporte a dark/light mode |

#### Padrões HTMX utilizados

| Padrão | Onde é usado |
|--------|-------------|
| `hx-get` + `hx-target` | Filtros de busca de espaços (atualiza lista sem reload) |
| `hx-get` + `hx-trigger="change"` | Seleção de data no calendário de disponibilidade |
| `hx-post` + `hx-swap="outerHTML"` | Ações de cancelamento/check-in inline |
| `hx-trigger="every 30s"` | Auto-refresh do dashboard de ocupação admin |
| `hx-indicator` | Spinner/loading durante requisições |
| `hx-confirm` | Confirmação antes de ações destrutivas (cancelar reserva) |
| `hx-push-url` | Manter URL sincronizada com filtros aplicados |

### Interfaces entre Módulos

- `reservations` importa `spaces.Space` para FK
- `reservations.services.check_availability(space, start, end)` → bool
- `reservations.services.auto_release_no_shows(threshold_minutes=15)` → int (count)
- `spaces` não importa nada de `reservations` (dependência unidirecional)
- `dashboard` importa services de `spaces` e `reservations` (somente leitura + ações admin)
- `accounts` é independente (apenas Django auth padrão com views customizadas)
- Views de template (área do usuário) reutilizam os mesmos services que a API

## Testing Decisions

- Testar comportamento externo via API (integration tests com APITestCase)
- Testar lógica de negócio isolada em services (unit tests)
- Testar views de template com Django TestClient (status codes, redirects, contexto)
- Cenários críticos:
  - Conflito de horário (duas reservas no mesmo slot) deve ser rejeitado
  - Auto-release libera reserva sem check-in após threshold
  - Cancelamento muda status e libera slot
  - Filtro por atributos retorna apenas espaços compatíveis
  - Disponibilidade reflete reservas existentes e bloqueios de manutenção
  - Área do usuário requer login (redirect para login se não autenticado)
  - Área admin requer staff (403 para usuários não-staff)
  - Páginas renderizam corretamente com dados (template assertions)
- Coverage mínimo: 80% (já configurado no projeto)

## Out of Scope

- Pagamento in-app
- Dashboards complexos de IA/analytics
- Integrações com ERPs ou calendários externos (Google Calendar, Outlook)
- Hardware proprietário (catracas, sensores de presença)
- Notificações push/email (pode ser adicionado depois)
- Autenticação social (OAuth) — usar Django auth padrão
- Multi-tenancy (múltiplas organizações)
- Frontend SPA separado (React, Vue, etc.) — usar Django templates + HTMX + DaisyUI
- Design system customizado — DaisyUI já fornece componentes suficientes
- Build pipeline de CSS (Tailwind CLI / PostCSS) — usar CDN no MVP para simplicidade

## Further Notes

- O check-in pode ser feito via QR Code impresso na porta da sala que redireciona para a página `/reservations/{id}/check-in/`
- O auto-release roda como management command: `python manage.py release_no_shows` (agendável via cron)
- A constraint de exclusão no PostgreSQL requer a extensão `btree_gist` (habilitada via migration)
- Prioridade de implementação segue a hierarquia do PO: disponibilidade real-time > autogestão > check-in > pagamento (fora de escopo)
- O modelo permite evolução futura: adicionar políticas de uso (max duração, aprovação para salas premium) sem reescrever o core
- Templates usam herança: `base.html` → `base_user.html` (área do usuário) e `base.html` → `base_admin.html` (área admin)
- `base.html` inclui Tailwind CSS (CDN), DaisyUI (CDN plugin), e HTMX (CDN) no `<head>`
- DaisyUI themes: `light` para área do usuário, `dark` disponível via `theme-controller`
- HTMX permite atualizar calendário de disponibilidade e listas sem reload completo de página
- Componentes DaisyUI garantem UI consistente e moderna sem necessidade de CSS customizado
- A área do usuário e a API REST coexistem — a API serve integrações futuras e o QR Code de check-in pode usar qualquer uma
- Django admin padrão (`/admin/`) continua disponível como fallback para superusers, mas o dashboard customizado (`/admin-dashboard/`) é a interface primária para administradores de espaço
- Caso o projeto evolua além do MVP, migrar de CDN para Tailwind CLI (build local) para purging e performance
