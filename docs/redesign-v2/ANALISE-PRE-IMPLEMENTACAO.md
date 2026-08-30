# Análise pré-implementação — Redesign V2

**Repositório:** `reserva-sala-mp` · branch `develop/frontend-v2_aula-dapia` (limpo)
**Pacote lido:** `pacote-redesign-reserva-espacos-v2.zip` — 12 documentos, na ordem do README
**Data:** 25/08/2026
**Status:** nenhuma linha de código alterada. Este documento é o entregável da seção 11 do briefing.

---

## Veredito

Não encontrei incompatibilidade que impeça a V2. A stack aguenta tudo que foi pedido sem SPA.

Encontrei **16 divergências** entre o pacote e o código real, das quais **4 alteram o plano de fases** e **3 exigem decisão sua** (listadas no fim). O restante eu resolvo com a alternativa arquiteturalmente mais segura, registrada aqui.

O ponto que mais muda o plano: **a Fase 4 do pacote (policy de disponibilidade) é pré-requisito da Fase 6 (passo 1), não uma fase paralela.** Sem horário de funcionamento configurável, o badge "Disponível hoje" é verdadeiro para praticamente todo espaço em praticamente todo dia — a janela de disponibilidade hoje vai de 00:00 a 24:00. O badge nasceria decorativo, que é exatamente o que o pacote proíbe.

---

## A. Arquitetura encontrada

Django 5.2 server-rendered, sem build de frontend. O projeto tem ~15 linhas de JavaScript escritas à mão.

| Camada | Implementação |
|---|---|
| Framework | Django 5.2 · Python ≥3.12 · dependências via `uv` (`uv.lock`) |
| Apps | `accounts`, `spaces`, `reservations`, `admin_dashboard`, `ai_assistant`, `knowledge`, `core` |
| Web | Django Templates (36 arquivos) + HTMX 2.0.4 **via CDN unpkg** + `django-htmx` |
| CSS | Tailwind v4 via `django-tailwind-cli` 2.8.3 (binário standalone, sem Node) + DaisyUI, tema `mpgo` em `assets/css/source.css` |
| API | DRF + `django-filter` + drf-yasg (`/swagger/`, `/redoc/`) — **sem paginação configurada** |
| Banco | PostgreSQL 16 + `btree_gist` + `pgvector` (imagem `pgvector/pgvector:pg16`) |
| Auth | sessão Django, `auth.User` padrão sem customização (`accounts/models.py` está vazio) |
| IA | Groq `openai/gpt-oss-120b` — busca de salas, classificação de manutenção, RAG de normas |
| Infra | Docker Compose: `db` + `web`, bind mount `.:/app`, comando `manage.py tailwind runserver` |
| Qualidade | pytest **311 funções de teste** em 9 arquivos · ruff · pre-commit · commitizen |

### Onde vive a regra de negócio

`reservations/validators.py` é fonte única, por refatoração deliberada e documentada. Models, serializers DRF, service layer e forms do admin **todos delegam para lá**. Três camadas protegem a sobreposição: validator → `services.create_reservation()` em `transaction.atomic()` → `ExclusionConstraint` PostgreSQL com `tstzrange`.

### Padrão central do frontend

```python
def get_template_names(self):
    if self.request.headers.get("HX-Request") == "true":
        return ["spaces/_space_list_results.html"]   # fragmento
    return [self.template_name]                       # página inteira
```

É o que substitui o re-render do React. Toda tela com filtro segue isso. Qualquer redesign preserva esse padrão ou quebra a interatividade.

### Restrições de processo que condicionam o plano

Duas configurações mudam como as fases precisam ser entregues:

1. **`pyproject.toml`: `addopts = "--cov=. --cov-report=term-missing --cov-fail-under=80"`** — a suíte falha se a cobertura global cair abaixo de 80%. Código novo sem teste **derruba a suíte inteira**, não só a própria linha.
2. **`.pre-commit-config.yaml` roda `pytest` em todo commit** (`always_run: true`). Não existe commit "só de template" que escape do gate.

Consequência: cada fase precisa entregar teste junto. Não é boa prática opcional aqui — é condição para o commit passar.

---

## B. Mapeamento especificação → código

Legenda: 🟢 existe e evolui · 🟡 existe mas muda de contrato · 🔴 não existe, precisa ser criado

### Dashboard do usuário — 🔴 não existe

| | |
|---|---|
| Hoje | `core/views.py::home_view` faz `redirect("space_list")`. A rota `/` existe e não renderiza nada |
| Afetados | `core/views.py`, `core/urls.py`, `core/tests.py`, `config/settings.py` (`LOGIN_REDIRECT_URL = "/spaces/"`), `accounts/views.py::_redirect_for_user` |
| Novos | `templates/core/dashboard.html`, `templates/components/_upcoming_reservations.html`, `_next_reservation_card.html`, `_useful_information.html` |
| Nota | `_redirect_for_user` manda staff para `/admin-dashboard/` e comum para `/spaces/`. Trocar o destino **depois** que a home existir e tiver teste, como o pacote determina |

### Sidebar — 🟡 existe, muda rótulos e estrutura

| | |
|---|---|
| Hoje | `templates/base_user.html` (w-60, seções "Atalhos"/"Administração") e `templates/base_admin.html` (w-64, 5 itens) |
| Afetados | os dois templates + **`core/tests.py:68-94`**, que asserta os rótulos literais `"Espaços"`, `"Atalhos"`, `"Dashboard"` — todos renomeados pela V2 |
| Nota | O pacote exige "não criar entrada sem rota funcional". A sidebar admin só pode crescer na fase que entrega cada tela — Serviços, Tipos, Políticas, Calendário Geral e Relatórios entram uma a uma |

### Nova Reserva passo 1 — 🟡 existe como `/spaces/`

| | |
|---|---|
| Hoje | `spaces/views.py::SpaceListView` (linhas 78-168) + `templates/spaces/space_list.html` + `_space_list_results.html` |
| Afetados | acima + `spaces/tests.py` (`TestSpaceListView`, `TestSpaceListViewAISearch` — 17 testes), `templates/components/_reservation_steps.html` (3→4 passos) |
| Novos | `templates/spaces/_space_card.html`, `_space_type_tabs.html`, `_quick_controls.html`, `_reservation_summary.html`, `spaces/services/availability.py` (batch) |
| Contrato que muda | contexto passa de `min_capacity`/`max_capacity` para `people` + `date`; `attributes` passa de `.get()` para `.getlist()` |

### Passo 2 — 🟡 existe como `/spaces/{id}/`

| | |
|---|---|
| Hoje | `spaces/views.py::SpaceDetailView` + `templates/spaces/space_detail.html` + `_availability.html`; dados de `reservations/services.py::get_availability_for_date()` |
| Afetados | acima + `spaces/tests.py::TestSpaceDetailView` (8 testes) e `TestSpaceAvailability` (3) |
| Novos | `reservations/services/alternatives.py` (horários próximos + espaços equivalentes) |
| Nota | `get_availability_for_date` devolve intervalos **mesclados**: um dia livre vira **um botão** "00:00–24:00". Para blocos legíveis é preciso fatiar por incremento — e o incremento vem da policy (Fase 4) |

### Passo 3 — 🔴 não existe

| | |
|---|---|
| Hoje | `ReservationCreateView` tem 3 campos (data, início, fim) e cria direto |
| Afetados | `reservations/views.py`, `reservations/models.py`, `reservations/serializers.py`, `templates/reservations/reservation_form.html`, `reservations/tests.py::TestReservationCreateView` (8 testes que postam o payload atual) |
| Novos | app `services` inteiro, `templates/reservations/reservation_details.html`, `_service_option_card.html`, e uma camada de rascunho (ver Divergência 7) |

### Passo 4 — 🔴 não existe

| | |
|---|---|
| Novos | `templates/reservations/reservation_review.html`, GET de revisão + POST final |
| Reaproveita | `services.create_reservation()` já revalida tudo e converte `IntegrityError` em `ValidationError`. A revalidação exigida pelo pacote **já existe** — o que falta é preservar os dados na falha |

### Calendário — 🔴 não existe

| | |
|---|---|
| Hoje | nenhuma visão de calendário em lugar nenhum. O mais próximo é `GET /api/v1/admin/occupancy/?date=` (`reservations/views.py::OccupancyView`), que devolve **todos os status**, inclusive cancelados |
| Novos | `reservations/views.py::CalendarView`, `templates/reservations/calendar_{month,week,day}.html`, serviço de agregação por período |
| Privacidade | `Reservation` não tem campo de visibilidade. O filtro tem de ser no queryset (`.values()` sem `title`/`notes`), nunca no template |

### Fotos — 🔴 não existe nada

| | |
|---|---|
| Hoje | sem campo, sem `MEDIA_ROOT`/`MEDIA_URL`, sem Pillow, sem `django-storages` |
| Afetados | `config/settings.py`, `config/urls.py`, `docker-compose.yml`, `.gitignore`, `.dockerignore`, `spaces/models.py`, `spaces/serializers.py`, `admin_dashboard/forms.py`, `admin_dashboard/views.py`, `templates/admin_dashboard/space_form.html` |
| Armadilha nº 1 | `CreateView`/`UpdateView` precisam receber `request.FILES` e o `<form>` precisa de `enctype="multipart/form-data"`. Sem isso o upload falha em silêncio |

### Tipos de espaço — 🔴 não existe

Nenhum campo de categoria em `Space`. Tabs, filtro por tipo e navegação por categoria dependem de `SpaceType`.

### Serviços — 🔴 não existe

Nada relacionado. `Attribute` é descritivo (TV, Wi-Fi) e não serve: o pacote é explícito — `Projetor` é atributo, `Apoio audiovisual` é serviço.

### Admin — 🟡 existe parcialmente

| Tela V2 | Situação |
|---|---|
| Visão Geral | 🟡 existe (`AdminDashboardView`, 4 KPIs + grade com polling de 30s); falta pendências de serviço e próximos eventos |
| Reservas | 🟢 existe, com filtros e paginação (25/pág) |
| Espaços | 🟢 existe (lista, form, toggle inline via HTMX) |
| Manutenção | 🟢 existe, com classificação por IA |
| Usuários | 🟢 existe |
| Calendário Geral · Tipos · Serviços · Políticas · Relatórios | 🔴 cinco telas novas |

### Relatórios — 🔴 não existe

Ver Divergência 9: duas das métricas pedidas medem coisas que hoje não acontecem.

### Configurações / Políticas — 🔴 não existe

Constantes espalhadas: `CHECK_IN_WINDOW_MINUTES = 15` e `DEFAULT_NO_SHOW_THRESHOLD_MINUTES = 15` em `reservations/services.py`; janela de disponibilidade fixada em `datetime.time.min` → +1 dia.

---

## C. Divergências

### 1. A Busca com IA não extrai data nem horário — 🔴 altera o plano

`ai_assistant/services.py::extract_room_search_filters()` devolve exatamente:

```python
{"min_capacity", "max_capacity", "attributes", "location", "summary"}
```

Sem `date`, sem `start_time`, sem `duration`. O docstring da função usa o exemplo *"sala para 8 pessoas com projetor amanhã de manhã"* — mas o prompt não pede esses campos e a função não os retorna.

O pacote (§11 e Fase 6) diz *"quando o serviço já os fornecer ou quando a extração puder ser adicionada com contrato testado"*. Não fornece. **Decisão registrada:** estender o prompt e o normalizador com `date`, `start_time` e `duration_minutes`, resolvendo datas relativas ("amanhã", "sexta") **no servidor** com o fuso correto — nunca deixando o LLM calcular a data. Fase própria, com testes de contrato mockando o LLM, para não degradar a extração de capacidade que hoje funciona.

### 2. Sem horário de funcionamento, o badge de disponibilidade nasce inútil — 🔴 altera o plano

`get_availability_for_date()` monta o dia como `00:00 → 24:00`. Com um espaço vazio, "tempo livre" = 24h. Com uma reunião de 2h, = 22h. Qualquer limiar de "Poucos horários" calculado sobre isso classifica tudo como "Disponível".

**A Fase 4 do pacote precisa vir antes da Fase 6.** Sem `BookingPolicy` (abertura, fechamento, incremento, duração mínima, limiar), o passo 1 não tem como mostrar status honesto.

### 3. Não existe ambiente de produção — ⚠️ decisão sua

- `Dockerfile`: `CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]`
- `docker-compose.yml`: `command: python manage.py tailwind runserver`
- `config/settings.py`: **sem `STATIC_ROOT`**, sem WhiteNoise, sem nginx
- volume `web`: bind mount `.:/app`

O critério de aceite *"mídia funciona em produção"* (07-QA) não tem alvo. Não vou inventar uma topologia de deploy. Ver Decisão 1 no fim.

### 4. A referência visual contradiz o mapa de telas aprovado

A imagem mostra, na sidebar do **usuário**: `Espaços` com sub-itens (Salas de Reunião, Auditório, Espaços Compartilhados, **Equipamentos**), `Painel Administrativo`, `Relatórios`, `Configurações`.

O documento `10-MAPA-DE-TELAS-E-MENUS.md` e `01-DECISOES §6` dizem o oposto: *"Evitar menu separado `Espaços` se ele apenas duplicar Nova Reserva"*, e colocam Relatórios/Configurações **só no admin**. E `Equipamentos` não é reservável — `Attribute` é atributo do espaço, não entidade.

**Pela hierarquia de fontes do briefing, o pacote vence a imagem.** Sigo o mapa de telas para a estrutura e a imagem para a linguagem visual (densidade, proporções, cards, foto, painel lateral).

### 5. A imagem tem quatro elementos sem dado real por trás

O pacote proíbe dado fake, contador fictício e link morto. A imagem contém:

| Elemento na imagem | Situação |
|---|---|
| Sino de notificações com badge **"3"** | não existe sistema de notificações. Nem modelo, nem `EMAIL_BACKEND` |
| **"Ana Maria · Departamento Jurídico"** | `User` não tem nome completo preenchido nem departamento. Só `username` |
| Botão **"Solicitar outro espaço"** | não existe fluxo de solicitação |
| Bloco **"Precisa de ajuda? · Falar com suporte"** | não existe canal de suporte cadastrado |

**Decisão registrada:** não reproduzo nenhum dos quatro como enfeite. O sino sai; o card do usuário mostra `username` + perfil derivado de `is_staff`; "Solicitar outro espaço" sai até existir fluxo; o bloco de ajuda vira link real para `/ajuda/` e `/assistente/`. Se quiser nome e departamento de verdade, é um modelo `Profile` — listado em D como opcional.

### 6. Testes acoplados a markup vão quebrar — e isso é esperado

Não é "teste frágil", é contrato explícito. A lista completa:

| Arquivo:linha | Asserção |
|---|---|
| `spaces/tests.py:559` | `'class="form-control justify-end"'` |
| `spaces/tests.py:568-569` | `id="loading-indicator"` + `htmx-indicator` |
| `spaces/tests.py:581` | contagem de `hx-indicator="#loading-indicator"` = nº de checkboxes + 1 |
| `admin_dashboard/tests.py:333,346` | `'class="spinner htmx-indicator'` |
| `admin_dashboard/tests.py:558` | `id="filter-indicator"` |
| `core/tests.py:79-80,93-94` | `drawer`, `sidebar-link` |
| `core/tests.py:71-81` | rótulos `"Espaços"`, `"Atalhos"` |
| `core/tests.py:88-94` | rótulo `"Dashboard"` |

**Vou atualizar essas asserções, nunca removê-las.** A intenção de cada uma (o spinner não pode ficar visível em carga inicial; todo checkbox dispara o mesmo indicador) continua valendo e continua testada.

### 7. Não existe estado entre etapas — o pacote não decide, eu decido

O fluxo atual é stateless: passo 1 → 2 é navegação por URL, e o POST cria a reserva de uma vez. A V2 exige quatro etapas, *"manter escolhas ao voltar"* e *"em conflito de última hora, não perder dados preenchidos"*. Isso requer rascunho.

Três opções: querystring (frágil, vaza dados em log), sessão Django (simples, some ao trocar de dispositivo), modelo `ReservationDraft` (robusto, exige expiração e limpeza).

**Decisão registrada: sessão Django**, chaveada por um `draft_id` na URL. É reversível, não cria migration, não exige rotina de limpeza e resolve os dois requisitos. Se depois surgir necessidade de soft-hold de slot (backlog §6 do pacote), aí sim vira modelo.

### 8. `attendee_count` obrigatório colide com dados existentes

O pacote pede `attendee_count = PositiveSmallIntegerField()` (não-nulo) e validação `<= space.capacity`. As reservas já gravadas não têm o dado.

**Decisão registrada:** `null=True, blank=True` no modelo; obrigatório **apenas no formulário do passo 3**; validação de capacidade só quando preenchido. A API mantém o campo opcional, senão quebra cliente existente. Relatório de subutilização ignora os nulos e diz quantos ignorou.

### 9. Duas métricas de relatório medem algo que não acontece

- **`completed`**: o status existe e é usado nos filtros de "Minhas Reservas", mas **nenhuma rotina o define**. Uma reserva com check-in fica `checked_in` para sempre. Existe spec parada em `docs/spec-driven/specs/06-spec-03-conclusao-automatica.md`.
- **`no_show`**: só é atribuído por `python manage.py release_no_shows`, e **não há scheduler no projeto**. Sem cron externo, nunca roda.

Relatório de ocupação e de no-show sobre isso mede o vazio. **Decisão registrada:** a fase de relatórios não começa antes de fechar as duas lacunas, ou os relatórios afetados não são publicados.

### 10. O card precisa de atributos priorizados; `Attribute` só tem `name`

A anatomia do card pede "2–4 atributos prioritários". Com 7 atributos e nenhum campo de ordenação, a escolha seria arbitrária. `is_featured` + `sort_order` em `Attribute` estão listados como *opcionais* na Fase 3 do pacote — na prática são necessários para o card não mentir sobre prioridade.

### 11. Multi-atributo está quebrado hoje — dois bugs, não um

`spaces/views.py:111` usa `request.GET.get("attributes")`, mas o template emite **vários** `name="attributes"`. `.get()` devolve só o último → marcar TV + Projetor filtra apenas por Projetor.

E `space_list.html:107` faz `{% if attr.name in selected_attributes %}` contra a **string crua**, o que casa por substring.

A API (`SpaceFilterSet.filter_attributes`) usa separação por vírgula e está correta. **Web e API divergem no formato.** Ao corrigir com `getlist`, manter a vírgula aceita na API para não quebrar cliente.

### 12. Self-host de fonte e HTMX muda o CSS versionado

`static/css/tailwind.css` (142 KB) está **commitado**. O `@import` do Google Fonts está dentro de `assets/css/source.css`, processado pelo Tailwind CLI. Trocar por `@font-face` local exige baixar os `.woff2`, colocá-los em `static/fonts/` e **regenerar e commitar** o CSS. Esquecer o regenerate quebra a tipografia em qualquer ambiente que não rode `tailwind build`.

### 13. O grid de horários não é fatiado

`_availability.html` renderiza **um botão por intervalo livre mesclado**. Um dia inteiro livre = um botão "00:00 – 24:00". A imagem e o pacote pressupõem blocos de horário. O fatiamento tem de ser feito no backend, com o incremento vindo da policy.

### 14. Timezone: o "dia" da disponibilidade é montado em UTC

`get_availability_for_date()` faz `datetime.combine(date, time.min).replace(tzinfo=datetime.UTC)`. Ao mudar `TIME_ZONE` para `America/Sao_Paulo`, isso precisa virar limite **local** — senão uma reserva das 22:00 BRT cai no dia UTC seguinte e some do grid do dia certo.

Boa notícia: os 311 testes usam `timezone.now()` (137×) e `timezone.make_aware()` (20×), ambos sensíveis a `TIME_ZONE`. Estão escritos corretamente e vão acompanhar a mudança. Falta teste de borda para 22:00–23:00.

### 15. `OccupancyView` devolve reservas canceladas

Diferente de `/spaces/{id}/availability/`, que filtra por `ACTIVE_RESERVATION_STATUSES`. Se o Calendário Geral reusar `OccupancyView`, mostra sala ocupada por reserva cancelada.

### 16. A API não tem paginação

`REST_FRAMEWORK` não define `DEFAULT_PAGINATION_CLASS`. `/spaces/` e `/reservations/` devolvem array puro. Não é bloqueante agora; vira problema se o Calendário Geral consumir a API para períodos longos.

---

## D. Migrations previstas

Todas pequenas, isoladas por fase e reversíveis. Nenhuma altera as constraints existentes.

| # | Migration | Conteúdo | Reversível |
|---|---|---|---|
| M1 | `spaces/0003_space_cover_image` | `cover_image = ImageField(null=True, blank=True, upload_to=...)` | ✅ |
| M2 | `spaces/0004_spacetype` | modelo `SpaceType` (name, slug, icon_name, sort_order, is_active) + `Space.space_type = FK(null=True)` | ✅ |
| M3 | `spaces/0005_spacetype_seed` | **data migration** idempotente: 6 tipos iniciais. `reverse_code` remove só os criados | ✅ |
| M4 | `spaces/0006_attribute_display` | `Attribute.is_featured`, `sort_order`, `icon_name` (defaults seguros) | ✅ |
| M5 | `reservations/0002_reservation_details` | `title = CharField(max_length=160, blank=True, default="")`, `attendee_count = PositiveSmallIntegerField(null=True, blank=True)`, `notes = TextField(blank=True, default="")` | ✅ |
| M6 | `services/0001_initial` | app novo: `ServiceType` + `ServiceType.available_in = M2M("spaces.Space", related_name="available_services")` + `ReservationServiceRequest` | ✅ |
| M7 | `services/0002_servicetype_seed` | **data migration**: catálogo inicial de 7 serviços | ✅ |
| M8 | `policies/0001_initial` | `BookingPolicy` global (abertura, fechamento, incremento, duração mín/máx, horizonte, limiar de "poucos horários") + `get_solo()` | ✅ |
| M9 | `reservations/0003_calendar_visibility` | `calendar_visibility` com default `occupied_only` — **só se** a Decisão 3 for pelo calendário geral | ✅ |

**Sem migration de `space_type` obrigatório.** O pacote determina backfill revisado pelo admin, não inferência por nome. Entrego um comando `sugerir_tipos_de_espaco --dry-run` que propõe, um admin confirma, e a obrigatoriedade do campo fica para depois — se fizer sentido.

**Não previsto, mas listado como opcional:** modelo `Profile` (OneToOne com `User`) para nome completo e departamento. Só entra se a Decisão 2 pedir.

---

## E. Riscos

Ordenados por probabilidade × impacto.

### 🔴 Alto

**1. O gate de cobertura derruba a suíte inteira.**
`--cov-fail-under=80` sobre `--cov=.` e pre-commit rodando pytest em todo commit. Um app `services` novo, com models e views sem teste, arrasta o total para baixo e **nenhum commit passa** — nem os não relacionados.
*Mitigação:* teste na mesma fase do código, sempre. Medir a cobertura antes de abrir cada fase e reportar depois.

**2. N+1 na disponibilidade dos cards.**
`get_availability_for_date()` faz 2 queries por espaço. Chamada em loop no grid: 2N por render — e o grid re-renderiza a cada filtro, cada tab, cada checkbox via HTMX.
*Mitigação:* serviço batch com 2 queries totais (reservas do dia + manutenções do dia), agrupadas por `space_id` em Python. Teste com `django_assert_num_queries` fixando o teto.

**3. Concorrência aumenta com quatro etapas.**
Hoje a janela entre escolher o horário e gravar é de segundos. Com passos 3 e 4 vira minutos. Dois usuários no mesmo slot deixa de ser hipótese.
*Mitigação:* a `ExclusionConstraint` já garante integridade — o risco é de **experiência**. O passo 4 precisa capturar o `ValidationError`, preservar o rascunho na sessão e oferecer alternativas. Teste de concorrência explícito.

### 🟡 Médio

**4. Renomear um `id` de alvo HTMX quebra em silêncio.**
`#space-results`, `#availability-content`, `#reservation-actions`, `#occupancy-grid`, `#reservation-table-container`, `#answer`. A suíte cobre `loading-indicator` e `filter-indicator`; os demais não têm rede de proteção.
*Mitigação:* adicionar asserção de presença dos alvos antes de mexer nos templates.

**5. Mexer no prompt da IA degrada o que funciona.**
O system prompt de busca já é longo e ensina distinção sutil entre piso e teto de capacidade. Acrescentar data/hora pode piorar a extração de capacidade.
*Mitigação:* testes de contrato com o LLM mockado, cobrindo os casos que hoje funcionam, **antes** de tocar no prompt. Fase isolada e reversível.

**6. Mídia sem destino de produção.**
Bind mount `.:/app` resolve dev. Sem `STATIC_ROOT`, sem WhiteNoise e com `runserver`, nada serve `/media/` fora do `DEBUG`.
*Mitigação:* depende da Decisão 1.

**7. Timezone e o dia da disponibilidade.**
Detalhado na Divergência 14. Risco de reserva noturna sumir do grid.
*Mitigação:* teste de borda 22:00–23:00 BRT escrito **antes** da troca de `TIME_ZONE`.

**8. Compatibilidade da API.**
Adicionar campos ao `SpaceSerializer` é aditivo e seguro. Tornar `attendee_count` obrigatório no `ReservationSerializer` quebraria qualquer cliente.
*Mitigação:* campos novos sempre opcionais na API; obrigatoriedade só no form web.

**9. CSS versionado fora de sincronia.**
`static/css/tailwind.css` está commitado e é o que o dev vê. Mudança em `source.css` sem regenerar = visual quebrado para quem não roda o build.
*Mitigação:* regenerar e commitar em toda fase que tocar o tema; conferir no checklist da fase.

### 🟢 Baixo, mas a registrar

**10. Backfill de tipo por heurística.** Se `space_type` virar obrigatório antes da revisão humana, as tabs mentem. Por isso M2 é nullable e não há migration de obrigatoriedade.

**11. Vazamento de privacidade no calendário.** `title` e `notes` são novos e sensíveis. Se o filtro ficar no template, um `{% include %}` distraído vaza.
*Mitigação:* o queryset do calendário de terceiros usa `.values("space_id", "start_time", "end_time")` — os campos sensíveis **não chegam ao contexto**. Teste que asserta ausência no HTML.

**12. Relatórios sobre dados que não existem.** Divergência 9.

**13. `docker compose down -v` e a mídia.** O bind mount sobrevive, mas `media/` precisa entrar em `.gitignore` e `.dockerignore` — senão vai para a imagem e para o repositório.

---

## F. Plano incremental para este repositório

As 16 fases do pacote reorganizadas pelas dependências reais do código. Cada fase é um commit ou uma sequência curta, com teste próprio, e é revertível sozinha.

**Mudança relevante frente ao pacote:** a policy de disponibilidade (Fase 4 lá) sobe para antes do passo 1, porque o badge depende dela.

| # | Fase | Depende de | Migration | Entrega verificável |
|---|---|---|---|---|
| **0** | **Estabilização** — timezone `America/Sao_Paulo` + dia local na disponibilidade; mensagens dos validators em pt-BR (preservando os `code`); `getlist` para atributos + `selected_attributes` como lista; HTMX self-hosted; fontes locais; logo otimizado | — | — | suíte verde, cobertura ≥ baseline, teste de borda 22:00 |
| **1** | **Fundação visual + stepper 4/4** — tokens derivados (`--brand-primary-subtle`, `-hover`, `-ring`, `--surface-elevated`, `--border-subtle`), refino de `.surface`/`.sidebar-link`, stepper de 4 etapas, sidebars com os rótulos novos | 0 | — | `core/tests.py` atualizado, CSS regenerado, sem link morto |
| **2** | **Foto de capa** — `cover_image`, Pillow, validação real de conteúdo, resize/WebP, EXIF removido, nome UUID, limpeza do arquivo antigo, `enctype` no form, `request.FILES` nas views, fallback institucional, serializer | 1 | M1 | upload ponta a ponta + card com placeholder estável |
| **3** | **Tipos de espaço** — `SpaceType` administrável, FK nullable, catálogo inicial, comando de sugestão em `--dry-run`, CRUD admin, filtro e serializer | 1 | M2, M3 | tabs alimentadas pelo banco |
| **4** | **Policy + disponibilidade batch** — `BookingPolicy`, fatiamento por incremento, serviço batch de resumo, `AvailabilityBadge` com data explícita | 0 | M8 | `django_assert_num_queries` fixando o teto; status nunca derivado de `is_active` |
| **5** | **Atributos priorizados** — `is_featured`/`sort_order`/`icon_name`, seleção dos 2–4 do card | 1 | M4 | card mostra prioridade real |
| **6** | **Dashboard do usuário + navegação** — `/inicio/`, próxima reserva, próximas reservas, check-in contextual, Reservar novamente, Informações Úteis; troca do redirect pós-login **no fim da fase** | 1, 4 | — | zero número fictício; ações contextuais conforme regra |
| **7** | **Passo 1** — tabs, Data (default hoje), **Pessoas** substituindo min/max, filtros avançados em chips, grid fotográfico, resumo sticky, seleção acessível | 2, 3, 4, 5 | — | `TestSpaceListView` atualizado; ranking prefere o menor espaço que comporta |
| **8** | **IA com data e horário** — estender contrato de `extract_room_search_filters` com `date`/`start_time`/`duration_minutes`; datas relativas resolvidas no servidor | 4, 7 | — | testes de contrato com LLM mockado, incluindo os casos atuais |
| **9** | **Passo 2** — redesenho de data/horário, blocos legíveis, manutenção visualmente distinta de reserva, alternativas quando indisponível | 4, 7 | — | `TestSpaceDetailView` atualizado |
| **10** | **Domínio dos detalhes + rascunho em sessão** — `title`, `attendee_count`, `notes`; validação de capacidade; rascunho por `draft_id` | 9 | M5 | voltar uma etapa preserva o preenchido |
| **11** | **Catálogo de serviços** — app `services`, `ServiceType`, M2M por espaço, `ReservationServiceRequest` com status operacional | 3 | M6, M7 | admin gere catálogo; nenhum boolean por serviço |
| **12** | **Passo 3** — Detalhes e serviços com progressive disclosure; só serviços aplicáveis ao espaço; campo extra só após seleção | 10, 11 | — | acessibilidade não coleta dado sensível |
| **13** | **Passo 4** — revisão com blocos `Alterar`, POST final revalidando tudo, recuperação de conflito sem perder dados | 12 | — | teste de concorrência explícito |
| **14** | **Fechar `completed` e agendar `no-show`** — rotina de conclusão automática (spec já escrita) + scheduler documentado | 0 | — | pré-requisito honesto para a fase 16 |
| **15** | **Calendário do usuário** — mês/semana/dia, próprias com detalhe, terceiros como `Ocupado` via queryset | 6, 10 | M9 (opcional) | teste que asserta ausência de `title`/`notes` no HTML |
| **16** | **Admin V2** — Visão Geral com pendências de serviço, Calendário Geral, Tipos, Serviços, Políticas | 11, 15 | — | cada item de menu com rota funcional |
| **17** | **Relatórios** — ocupação, picos, cancelamento/no-show, serviços, manutenção, subutilização; CSV primeiro | 14, 16 | — | nenhuma métrica sobre dado inexistente |
| **18** | **Ajuda** — perguntas frequentes ligadas às regras reais do código, atalho para Consultar Normas | 6 | — | sem contato fictício |
| **19** | **QA final** — 7 resoluções, teclado, HTMX, privacidade, concorrência, timezone; checklist do `07-QA` inteiro | todas | — | checklist assinado item a item |

### Marcos naturais para parar e avaliar

- **Fim da 4** — a base existe (visual, foto, tipo, policy) e o produto ainda é o de hoje. Reversível por inteiro.
- **Fim da 9** — a jornada de descoberta e escolha está nova; a criação de reserva ainda é a antiga, de um passo.
- **Fim da 13** — as quatro etapas estão completas. É a entrega que justifica o nome "V2".
- **Fim da 19** — pacote completo.

### Como cada fase é reportada

Arquivos alterados · decisões · migrations · resultado de `make test` · resultado de `make lint` · cobertura antes/depois · divergências novas · o que vem em seguida. Sem avançar antes disso.

---

## Decisões que preciso de você

Só estas três. O resto está resolvido acima.

**1. Onde isto roda em produção?**
Muda o que eu construo na Fase 2. Se existe (ou vai existir) deploy real, configuro `STATIC_ROOT` + WhiteNoise + volume nomeado para mídia. Se é ambiente acadêmico/demo, mantenho o bind mount, documento a limitação e não invento infraestrutura.

**2. Nome completo e departamento do usuário — entram na V2?**
A referência visual mostra "Ana Maria · Departamento Jurídico". Hoje só existe `username`. É um modelo `Profile` novo (OneToOne), mais formulário de registro e backfill. Sem isso, o card da sidebar mostra o `username`.

**3. Calendário Geral do admin entra agora?**
É a fase mais cara depois do fluxo de 4 etapas e a única que exige decisão de privacidade com efeito em migration (M9). Se for adiada, a Fase 15 entrega só o calendário do usuário e M9 não é criada.

E uma confirmação de escopo: são **20 fases**. Quer que eu vá até o marco da Fase 13 (as quatro etapas completas) e reavaliemos, ou seguir direto até o fim?
