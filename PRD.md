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

### Desenvolvimento e Demonstração

15. As a developer, I want to populate the database with default data in Portuguese (pt-BR) so that I can develop and demo the system without manual setup.
16. As a developer, I want the seed command to be idempotent so that I can run it multiple times without duplicating data or errors.
17. As a developer, I want a Makefile target to run seeds easily so that onboarding and local setup are frictionless.

### Documentação

18. As a user, I want a simple and intuitive README (in pt-BR) so that I understand what the project does, how it works, and how to use it.
19. As a developer, I want the README to describe user journeys and the flow for each use case so that I can validate behavior and onboard quickly.
20. As a developer, I want the README to document local setup, seed generation, default users (roles), and the main routes so that I can run and test the system end-to-end.

### Correções (UX + Navegação)

21. As a user, I want to be redirected to `/spaces/` after login so that I land on the primary starting page rather than a test route.
22. As a user, I want the "Filtrar" button aligned with the filter fields so that the form looks polished and easy to scan.
23. As a user, I want the spinner inside the "Filtrar" button to be hidden on initial page load (Buscar Espaços) and only appear when I apply filters, disappearing after results load, so that feedback is accurate and not distracting.
24. As an admin, I want the status indicator on `/admin-dashboard/spaces/` to stop loading when no action is being performed so that the page doesn't look broken.
25. As an admin, I want the filter indicator on `/admin-dashboard/reservations/` to stay idle until a user triggers filtering so that it doesn't show infinite loading without interaction.

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

### Seeds de Dados Padrão (pt-BR)

Comando de management `seed_data` para popular o banco com dados de demonstração em português brasileiro. Deve ser **idempotente** (usar `get_or_create` / verificação por chaves naturais) e executável após `migrate`.

| Módulo | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| `core` | `core/management/commands/seed_data.py` | Orquestra a criação de todos os dados padrão |
| `core` | `core/seeds/attributes.py` | Atributos de equipamento em pt-BR |
| `core` | `core/seeds/spaces.py` | Espaços com localização, capacidade e atributos |
| `core` | `core/seeds/users.py` | Usuários admin (staff) e usuários comuns de demo |
| `core` | `core/seeds/reservations.py` | Reservas de exemplo em diferentes status |
| `core` | `core/seeds/maintenance.py` | Bloqueios de manutenção de exemplo |

#### Atributos padrão (pt-BR)

| Nome |
|------|
| Ar-condicionado |
| Projetor |
| TV |
| Webcam |
| Quadro branco |
| Videoconferência |
| Wi-Fi |

#### Espaços padrão (pt-BR)

| Nome | Localização | Capacidade | Atributos |
|------|-------------|------------|-----------|
| Sala de Reunião Alfa | 2º andar, Bloco A | 8 | Ar-condicionado, TV, Videoconferência, Wi-Fi |
| Sala de Reunião Beta | 3º andar, Bloco B | 12 | Ar-condicionado, Projetor, Quadro branco, Wi-Fi |
| Sala Focus | 1º andar, Bloco C | 4 | Ar-condicionado, Webcam, Wi-Fi |
| Auditório Central | Térreo | 50 | Ar-condicionado, Projetor, TV, Videoconferência, Wi-Fi |
| Sala Executiva | 4º andar, Bloco A | 6 | Ar-condicionado, TV, Webcam, Videoconferência, Wi-Fi |

#### Usuários padrão (pt-BR)

| Username | Nome | Perfil | Staff |
|----------|------|--------|-------|
| admin | Administrador | Superusuário | Sim |
| maria.silva | Maria Silva | Usuária comum | Não |
| joao.santos | João Santos | Usuário comum | Não |
| ana.costa | Ana Costa | Usuária comum | Não |

Senhas conhecidas documentadas em `.env.example` (ex.: `SEED_DEFAULT_PASSWORD=reserva123`). Nunca commitar senhas reais.

#### Reservas de exemplo (pt-BR)

Cenários para demonstrar o ciclo de vida:

| Cenário | Usuário | Espaço | Status | Propósito |
|---------|---------|--------|--------|-----------|
| Reunião futura confirmada | maria.silva | Sala de Reunião Alfa | confirmed | Demo de cancelamento/reagendamento |
| Reunião passada concluída | joao.santos | Sala Focus | completed | Histórico em "Minhas Reservas" |
| Reunião de hoje (janela de check-in) | ana.costa | Sala Executiva | confirmed | Demo de check-in e QR Code |
| No-show passado | joao.santos | Sala de Reunião Beta | no_show | Demo de auto-release no dashboard |

Horários relativos a `timezone.now()` (ex.: hoje ±N horas, amanhã, ontem) para permanecerem válidos independentemente da data de execução.

#### Bloqueios de manutenção de exemplo (pt-BR)

| Espaço | Motivo | Período |
|--------|--------|---------|
| Auditório Central | Limpeza pós-evento | Amanhã, 08:00–10:00 |
| Sala de Reunião Beta | Manutenção do ar-condicionado | Próxima semana, dia útil, 14:00–16:00 |

#### Interface do comando

```bash
python manage.py seed_data          # popula dados padrão (idempotente)
python manage.py seed_data --flush  # remove dados seedados e recria (opcional)
make seed                           # atalho via Makefile
```

#### Decisões técnicas dos seeds

- Módulos em `core/seeds/` isolados por domínio — testáveis unitariamente
- Chaves naturais para idempotência: `Attribute.name`, `Space.name`, `User.username`
- Reservas identificadas por tupla `(user, space, start_time)` para evitar duplicatas
- Flag `--flush` remove apenas registros criados pelo seed (identificados pelas chaves naturais acima), nunca dados customizados do usuário
- Textos de interface (motivos, descrições) sempre em pt-BR
- Ordem de execução: atributos → espaços → usuários → reservas → bloqueios de manutenção (respeita FKs)

### Documentação (README)

Criar um `README.md` em português (pt-BR), objetivo e fácil de seguir, cobrindo:

- **Visão geral do projeto**: qual problema resolve e quais são os pilares (calendário único, auto-release, filtros por atributos).
- **Como funciona (alto nível)**:
  - Apps principais (`accounts`, `spaces`, `reservations`, `dashboard`)
  - Diferença entre **API** (`/api/...`) e **UI** (templates/HTMX)
  - Estados de reserva (confirmed/cancelled/checked_in/completed/no_show) e quando ocorrem
- **Jornadas do usuário** (passo a passo):
  - Usuário final: buscar espaço → ver detalhes → reservar → (opcional) check-in → cancelar/reagendar → ver histórico
  - Administrador: gerir espaços → gerir reservas → criar bloqueios de manutenção → observar ocupação
- **Fluxo por caso de uso** (um fluxo por tópico, com passos e rotas):
  - Login/registro/logout
  - Listagem e filtro de espaços
  - Detalhe do espaço e disponibilidade
  - Criar reserva, cancelar, reagendar
  - Check-in via página (fluxo QR Code)
  - Admin dashboard e páginas de manutenção
- **Como executar localmente**:
  - Pré-requisitos (Docker + Docker Compose)
  - Comandos essenciais (`make up`, `make migrate`, `make seed`, `make test`, `make lint`, `make format`)
- **Seeds e credenciais padrão**:
  - Como gerar seeds e como rodar novamente (idempotente / `--flush`)
  - Usuários padrão e papéis (admin staff vs usuário comum) + senha default via `SEED_DEFAULT_PASSWORD`
- **Rotas principais**:
  - UI: `/accounts/login/`, `/accounts/register/`, `/spaces/`, `/reservations/`, `/admin-dashboard/...`
  - API: `/api/spaces/`, `/api/reservations/`, `/api/admin/...`

### Correções (Navegação + HTMX)

- **Redirect pós-login**: rota padrão deve ser `/spaces/` (não `/htmx-test/`).
- **Form de filtros em `/spaces/` (Buscar Espaços)**:
  - Botão "Filtrar" alinhado verticalmente com os campos (capacidade mínima e localização).
  - Spinner inline dentro do botão "Filtrar" (`#loading-indicator` com classe `htmx-indicator`) deve estar **oculto no load inicial** da página.
  - Spinner deve aparecer **apenas** durante requisições HTMX disparadas pelo usuário (clique em "Filtrar" ou alteração de checkboxes de equipamentos) e ser removido ao término do swap.
  - Bug conhecido: spinner DaisyUI (`loading loading-spinner`) permanece visível infinitamente no botão mesmo sem ação do usuário — corrigir wiring CSS/HTMX do indicador.
- **Admin dashboard**:
  - Em `/admin-dashboard/spaces/`, o status (coluna "Status") não deve ficar com spinner infinito sem ação do usuário.
  - Em `/admin-dashboard/reservations/`, o elemento `#filter-indicator` não deve carregar infinitamente no load inicial (apenas durante ações de filtro/atualização disparadas pelo usuário).

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
  - Comando `seed_data` é idempotente (segunda execução não duplica registros)
  - Seeds criam atributos, espaços e usuários com textos em pt-BR
  - Reservas de exemplo cobrem múltiplos status (confirmed, completed, no_show)
  - Redirect pós-login aponta para `/spaces/`
  - Página `/spaces/` (Buscar Espaços): spinner dentro do botão "Filtrar" oculto no load inicial e visível apenas durante filtro ativo
  - Página `/admin-dashboard/spaces/` não exibe spinner infinito na coluna status no load inicial
  - Página `/admin-dashboard/reservations/` não exibe `#filter-indicator` carregando infinitamente sem ação do usuário
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
- Executar `make migrate && make seed` após subir o ambiente Docker pela primeira vez para ter dados de demo prontos
- Credenciais de demo: `admin` / `reserva123` (staff) e `maria.silva` / `reserva123` (usuário comum) — configuráveis via variáveis de ambiente
