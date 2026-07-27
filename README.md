# Sistema de Reserva de Espaços

Sistema centralizado para descoberta e reserva de salas e espaços físicos. Resolve o problema da fragmentação de canais (planilhas, e-mails, calendários físicos) e reduz o desperdício de espaço com liberação automática de reservas não utilizadas.

## Pilares

1. **Calendário único e centralizado** — se não está no sistema, não existe.
2. **Liberação automática de no-shows** — sem check-in em 15 minutos, a sala volta a ficar disponível.
3. **Filtros por atributos mínimos** — busca por capacidade e equipamentos (TV, projetor, videoconferência etc.).
4. **Assistência por IA** — busca de salas em linguagem natural e classificação automática de motivos de manutenção, via LLM (Groq).

---

## Como funciona (alto nível)

### Apps principais

| App | Responsabilidade |
|-----|-----------------|
| `accounts` | Autenticação, registro, login/logout |
| `spaces` | Cadastro de espaços e seus atributos (capacidade, localização, equipamentos) |
| `reservations` | Ciclo de vida da reserva: criar, cancelar, reagendar, check-in e auto-release |
| `admin_dashboard` | Interface administrativa customizada (ocupação, gestão de espaços, reservas, manutenção e usuários) |
| `ai_assistant` | Serviços de IA (LLM via Groq): busca de salas em linguagem natural e classificação de motivos de manutenção |

Para ajustar o comportamento conversacional da IA (prompts do sistema, mapeamento de sinônimos como “internet” → “Wi-Fi”, categorias de manutenção e parsing da resposta do LLM), edite `ai_assistant/services.py`. As views (`ai_assistant/views.py` e a busca em `spaces/views.py`) apenas consomem esses serviços.

### API vs Interface Web

- **API REST** (`/api/v1/...`): serve integrações futuras e o QR Code de check-in.
- **Interface Web** (templates + HTMX + DaisyUI): navegação server-side com atualizações parciais de página, sem SPA.

### Estados de uma reserva

| Estado | Quando ocorre |
|--------|--------------|
| `confirmed` | Reserva criada com sucesso (padrão) |
| `checked_in` | Usuário confirmou presença dentro da janela de check-in |
| `cancelled` | Usuário ou admin cancelou a reserva |
| `completed` | Horário da reserva passou e houve check-in |
| `no_show` | Início da reserva passou + 15 minutos sem check-in (auto-release) |

---

## Jornadas

### Usuário final

1. Acessa `/accounts/login/` e entra com usuário e senha (redirecionamento é automático conforme o perfil da conta).
2. Busca espaços em `/spaces/` filtrando por capacidade, localização e equipamentos.
3. Visualiza detalhes do espaço em `/spaces/{id}/` e confere a disponibilidade por data.
4. Seleciona um horário livre e cria a reserva em `/reservations/new/?space={id}`.
5. Gerencia suas reservas em `/reservations/` (cancelar, reagendar).
6. Faz check-in na página `/reservations/{id}/check-in/` (pode ser acessada via QR Code).

### Administrador do espaço

1. Acessa `/accounts/login/` com uma conta com permissão de staff — é redirecionado automaticamente para o painel admin.
2. Acessa o dashboard em `/admin-dashboard/` para ver ocupação em tempo real.
3. Gerencia espaços em `/admin-dashboard/spaces/` (criar, editar, ativar/desativar).
4. Visualiza e cancela reservas em `/admin-dashboard/reservations/`.
5. Cria bloqueios de manutenção em `/admin-dashboard/maintenance/` para impedir reservas em determinados horários.
6. Gerencia usuários em `/admin-dashboard/users/` (criar, editar, remover, promover a admin).

---

## Fluxo por caso de uso

### Login / Registro / Logout

1. Acesse `/accounts/login/` e escolha entrar como **Admin** ou **Usuário**. A escolha é validada: contas sem permissão de staff não conseguem entrar pelo caminho "Admin".
2. Acesse `/accounts/register/` para criar uma conta (sempre como usuário comum).
3. Clique em "Sair" na barra de navegação para encerrar a sessão.

### Listagem e filtro de espaços

1. Acesse `/spaces/`.
2. Preencha capacidade mínima, localização e/ou selecione equipamentos.
3. Clique em **Filtrar**. A lista de espaços atualiza sem recarregar a página.

### Detalhe do espaço e disponibilidade

1. Na listagem, clique em um espaço ou acesse `/spaces/{id}/`.
2. Veja informações do espaço e selecione uma data para ver horários livres/ocupados.
3. Clique em um horário livre para iniciar a reserva.

### Criar, cancelar e reagendar reserva

1. No formulário `/reservations/new/?space={id}`, escolha data e horário de início/fim.
2. Confirme para criar a reserva. Em caso de conflito, o sistema exibe um alerta.
3. Em `/reservations/{id}/`, clique em **Cancelar** ou **Reagendar** conforme necessário.

### Check-in via página (fluxo QR Code)

1. O QR Code na porta da sala aponta para `/reservations/{id}/check-in/`.
2. O usuário acessa a página e confirma a presença.
3. O status muda para `checked_in` e a sala é considerada ocupada.

### Dashboard e páginas administrativas

1. Acesse `/admin-dashboard/` para visão geral de ocupação.
2. Acesse `/admin-dashboard/spaces/` para gerenciar espaços.
3. Acesse `/admin-dashboard/reservations/` para gerenciar reservas.
4. Acesse `/admin-dashboard/maintenance/` para criar bloqueios de manutenção.
5. Acesse `/admin-dashboard/users/` para gerenciar usuários.

---

## Como executar localmente

### Pré-requisitos

- Docker
- Docker Compose
- Make (opcional, para atalhos)

### Passos

```bash
# 1. Clone o repositório e entre na pasta
# 2. Suba os serviços (Django + PostgreSQL)
make up

# 3. Aplique as migrações
make migrate

# 4. Popule o banco com dados de demonstração
make seed

# 5. Indexe a base de normas para o assistente documental
docker compose exec web python manage.py indexar_normas

# 6. Acesse a aplicação em http://localhost:8000
```

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. Para usar os endpoints de IA (`/api/v1/ai/...`), é necessário definir:

| Variável | Descrição |
|----------|-----------|
| `GROQ_API_KEY` | Chave de API do Groq (gratuita em https://console.groq.com/keys). Sem ela, os endpoints de IA retornam erro 502. |
| `GROQ_MODEL` | Modelo usado nas chamadas (padrão: `llama-3.3-70b-versatile`) |

### Comandos úteis

| Comando | Descrição |
|---------|-----------|
| `make up` | Inicia os containers |
| `make down` | Para os containers |
| `make migrate` | Aplica migrações do banco |
| `make seed` | Cria dados de demonstração (idempotente) |
| `make seed-flush` | Remove dados de demonstração e recria |
| `make test` | Executa a suíte de testes com cobertura |
| `make lint` | Executa o linter (ruff) |
| `make format` | Formata o código (ruff) |
| `make shell` | Abre terminal bash dentro do container web |

---

## Base de normas e indexação

O assistente documental responde perguntas sobre um corpus de regulamentos públicos de
uso de espaços físicos — auditórios, salas de reunião e cessão a terceiros — reunidos de
universidades, institutos federais e órgãos do sistema de Justiça.

Os documentos ficam versionados em `data/normas/`, junto de `fontes.json`, que registra a
procedência de cada um: instituição, título, categoria e URL de origem. Versionar os
arquivos garante que o projeto rode logo após o clone, sem depender de portais externos
que saem do ar — durante a coleta, 4 das 29 fontes falharam e 3 responderam com página de
captcha ou casca de JavaScript. São atos normativos públicos, de livre redistribuição.

### Indexar o corpus

```bash
docker compose exec web python manage.py indexar_normas
```

O comando executa o pipeline em quatro etapas:

1. **Extração** — `pypdf` para PDF, `trafilatura` para HTML. Arquivos que produzem menos
   de 150 palavras são recusados, e não indexados como se fossem válidos.
2. **Segmentação** — divisão em trechos com separadores ajustados para texto normativo
   (`Art.`, `§`, `CAPÍTULO`), de modo que um artigo não seja cortado ao meio.
3. **Embeddings** — vetores gerados localmente pelo `fastembed`, sem chave de API.
4. **Persistência** — trechos gravados com índice HNSW (busca semântica) e `tsvector`
   em português (busca lexical).

É **idempotente**: cada documento guarda o SHA-256 do arquivo que o originou, então rodar
de novo não reprocessa nada. Alterar um arquivo reprocessa apenas ele.

| Opção | Efeito |
|-------|--------|
| `--force` | Reindexa mesmo o que não mudou |
| `--somente 3 5 9` | Indexa apenas os ids informados |

Ao final, o comando relata quantos documentos foram indexados, quais fontes não têm
arquivo em disco e quais falharam, com o motivo.

> **Primeira execução:** o modelo de embedding (~250 MB) é baixado uma vez e guardado no
> volume `fastembed_cache`, preservado entre builds.

### Baixar o corpus novamente

Os arquivos já estão no repositório. Para recoletá-los das fontes originais:

```bash
docker compose exec web python manage.py baixar_normas
```

Aceita as mesmas opções `--force` e `--somente`.

---

## Seeds e credenciais padrão

O comando `make seed` popula o banco com dados de demonstração em português. Ele é **idempotente** — pode ser executado várias vezes sem duplicar registros.

Para recriar os dados do zero:

```bash
make seed-flush
```

### Usuários padrão

| Usuário | Perfil | Staff |
|---------|--------|-------|
| `admin` | Administrador | Sim |
| `maria.silva` | Usuária comum | Não |
| `joao.santos` | Usuário comum | Não |
| `ana.costa` | Usuária comum | Não |

**Senha padrão:** `reserva123` (configurável via variável `SEED_DEFAULT_PASSWORD` no `.env`)

### Dados criados

- **7 atributos de equipamento**: Ar-condicionado, Projetor, TV, Webcam, Quadro branco, Videoconferência, Wi-Fi
- **5 espaços**: Sala de Reunião Alfa, Sala de Reunião Beta, Sala Focus, Auditório Central, Sala Executiva
- **4 reservas de exemplo**: em diferentes status (confirmada, concluída, no-show, com janela de check-in para hoje)
- **2 bloqueios de manutenção**: com motivos em português

---

## Rotas principais

### Interface Web

| Rota | Descrição |
|------|-----------|
| `/accounts/login/` | Login (escolha entre Admin e Usuário) |
| `/accounts/register/` | Registro de conta |
| `/spaces/` | Busca de espaços com filtros |
| `/spaces/{id}/` | Detalhe do espaço e disponibilidade |
| `/reservations/` | Minhas reservas |
| `/reservations/new/` | Nova reserva |
| `/reservations/{id}/` | Detalhe da reserva |
| `/reservations/{id}/check-in/` | Check-in |
| `/admin-dashboard/` | Dashboard de ocupação |
| `/admin-dashboard/spaces/` | Gestão de espaços |
| `/admin-dashboard/reservations/` | Gestão de reservas |
| `/admin-dashboard/maintenance/` | Bloqueios de manutenção |
| `/admin-dashboard/users/` | Gestão de usuários |

### API REST (`/api/v1/`)

Toda a API é versionada sob `/api/v1/`.

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/v1/spaces/` | Listar espaços (com filtros) |
| GET | `/api/v1/spaces/{id}/` | Detalhe do espaço |
| GET | `/api/v1/spaces/{id}/availability/` | Disponibilidade por data |
| GET | `/api/v1/reservations/` | Listar minhas reservas |
| POST | `/api/v1/reservations/` | Criar reserva |
| PATCH | `/api/v1/reservations/{id}/cancel/` | Cancelar reserva |
| PATCH | `/api/v1/reservations/{id}/reschedule/` | Reagendar reserva |
| POST | `/api/v1/reservations/{id}/check-in/` | Fazer check-in |
| GET | `/api/v1/admin/occupancy/` | Dashboard de ocupação (admin) |
| POST | `/api/v1/admin/maintenance-blocks/` | Criar bloqueio de manutenção (admin) |
| POST | `/api/v1/ai/room-search/` | Busca de salas a partir de uma descrição em linguagem natural (ex.: "sala para 8 pessoas com projetor perto da recepção"). O LLM extrai os filtros (capacidade, atributos, localização) e a API retorna os espaços correspondentes. |
| POST | `/api/v1/ai/maintenance-classify/` | Classifica um motivo de manutenção em texto livre em uma categoria fixa (elétrica, hidráulica, limpeza, TI/equipamentos, mobiliário, segurança, outros), com justificativa e nível de confiança. |

Os endpoints de IA exigem autenticação (`IsAuthenticated`), validam a entrada (tamanho mínimo/máximo do texto) e retornam `502` se o provedor de IA falhar. Documentação interativa (Swagger/Redoc) disponível em `/swagger/` e `/redoc/`.

---

## Tecnologias

- **Backend:** Django 5.2, Django REST Framework, PostgreSQL
- **IA:** Groq (LLM) para busca em linguagem natural e classificação de texto
- **Frontend:** Django Templates, HTMX, DaisyUI (sobre Tailwind CSS)
- **Infra:** Docker, Docker Compose
- **Qualidade:** pytest (com cobertura mínima de 80%), ruff, pre-commit, commitizen
