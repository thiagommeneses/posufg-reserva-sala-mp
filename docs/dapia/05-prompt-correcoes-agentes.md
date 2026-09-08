# Prompt para o agente do Cursor — correções no pipeline multiagente

> Cole o bloco abaixo inteiro no chat do Cursor, com o repositório aberto.

---

## Contexto

Você é engenheiro sênior no projeto **Reserva de Espaços** (Django 5.2 + PostgreSQL + pgvector),
sistema de reserva de salas do Ministério Público de Goiás. Branch de trabalho:
`develop/aula-dapia`.

O projeto tem uma camada multiagente em `ai_assistant/agents.py`, especificada em
`docs/dapia/04-especificacao-sistema-multiagente.md`. Ela já roda e passou por três rodadas de
benchmark. Sua tarefa é corrigir quatro defeitos que o benchmark expôs, sem regredir o que
funciona.

Antes de alterar qualquer coisa, leia: `ai_assistant/agents.py`, `ai_assistant/services.py`,
`ai_assistant/test_agents.py`, `reservations/availability.py`, `reservations/validators.py` e
`ai_assistant/management/commands/testar_agentes.py`.

---

## Esquema de funcionamento interno

Pipeline **sequencial** (não hierárquico, não grafo). Cada etapa depende só da saída da
anterior. Entrada: pedido em linguagem natural de um servidor autenticado. Saída: reserva
confirmada, até três alternativas, escalação ao administrador, ou pedido de esclarecimento.

```
texto livre
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ AGENTE 1 — Intérprete de Solicitação      interpretar_pedido()   │
│ Ferramenta: services.extract_room_search_filters (Groq, JSON)    │
│ Contexto injetado: availability.contexto_temporal(policy)        │
│   → hoje, dia da semana, abertura/fechamento, horizonte,         │
│     duração mínima e máxima                                      │
│ Saída: min_capacity, max_capacity, attributes[], location,       │
│        date, start_time, duration_minutes, avisos[], faltando[]  │
│ Guardas: atributos saem só do catálogo (DEFAULT_ATTRIBUTES);     │
│   _coerce_date/_coerce_time/_coerce_duration anulam valor fora   │
│   da política e registram o motivo em `avisos`                   │
└──────────────────────────────────────────────────────────────────┘
   │
   ├─ faltando[] não vazio ──► INTERRUPÇÃO 1: DECISAO_ESCLARECIMENTO
   │     pergunta_de_esclarecimento(): se há `avisos`, explica a recusa;
   │     senão, pergunta o campo ausente
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ AGENTE 2 — Consultor Normativo            emitir_parecer()       │
│                                                                  │
│ Metade determinística — _violacoes_de_politica():                │
│   duração < mínimo / > máximo, data no passado, além do          │
│   horizonte, dia sem funcionamento (policy.abre_em)              │
│   → PARECER_INADMISSIVEL, origem "politica", SEM chamar o LLM    │
│                                                                  │
│ Metade comparativa — só se a política passou:                    │
│   Ferramenta: retrieval.search() — busca híbrida (embeddings     │
│   locais + lexical) sobre 722 trechos de 25 regulamentos de      │
│   outras instituições públicas, fundidos por RRF                 │
│   Sem trecho → PARECER_ADMISSIVEL, origem "sem_referencia",      │
│     SEM chamar o LLM (ausência de referência não restringe)      │
│   Com trechos → Groq JSON, recebendo o texto original + os       │
│     critérios + os trechos numerados                             │
│                                                                  │
│ Vocabulário: admissivel | inadmissivel | requer_decisao_humana   │
│ Guardas pós-resposta:                                            │
│   • vocabulário inválido → requer_decisao_humana + aviso         │
│   • recusa sem citação → requer_decisao_humana + aviso           │
│     (citação é exigida para RESTRINGIR, não para permitir)       │
│   • norma de outra instituição nunca vincula o MP-GO             │
└──────────────────────────────────────────────────────────────────┘
   │
   ├─ requer_decisao_humana ──► INTERRUPÇÃO 2: DECISAO_ESCALONAMENTO
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ AGENTE 3 — Alocador de Espaço             alocar()               │
│ Não usa LLM. Ferramentas internas:                               │
│   _espacos_candidatos()  → filtro por capacidade/atributo/local  │
│   validators.active_reservations_overlapping()                   │
│   validators.maintenance_blocks_overlapping()                    │
│   availability.gerar_slots() + marcar_cabimento()                │
│   reservations.services.create_reservation()                     │
│ Decisão:                                                         │
│   admissivel + espaço livre        → DECISAO_RESERVA             │
│   admissivel + ocupado             → DECISAO_ALTERNATIVAS        │
│   inadmissivel                     → alternativas, senão escala  │
│   sem candidato                    → DECISAO_ESCALONAMENTO       │
│ _alternativas(): varre até 7 dias à frente, pulando dias         │
│   fechados, dia externo × espaço interno, no máximo 3 opções     │
└──────────────────────────────────────────────────────────────────┘
```

Instrumentação: cada etapa devolve um `PassoDoAgente` com `duracao_ms` e `tokens`
(`usage_sink` opcional em `_run_json_completion` e `_run_text_completion`). O runner
`manage.py testar_agentes` roda os pedidos de `data/agentes/pedidos-teste.json`, reverte a
transação por padrão e grava `data/agentes/resultado-AAAA-MM-DD.json`.

---

## Dados do benchmark

Modelo: `openai/gpt-oss-120b` (Groq). Três rodadas em 07/09/2026.

| Rodada | Pedidos | Conferem | Latência média | Mediana | Tokens/pedido |
|---|---|---|---|---|---|
| #01 | 10 | 2 | 3.574 ms | 1.777 ms | 1.298 |
| #02 | 10 | 2 | 11.666 ms | 10.083 ms | 2.506 |
| #03 | 4 | 4 | 7.485 ms | 3.230 ms | 2.715 |

Rodada #03, por agente: Intérprete 1.473 ms e 1.297 tokens; Consultor 6.012 ms e 1.418 tokens;
Alocador 0 ms e 0 tokens. **A latência está contaminada por HTTP 429 do plano gratuito**, com
esperas de 7 a 19 s. Sem o pedido que esperou 19 s, a média da #03 cai para 2,6 s.

Achados já corrigidos (não refaça):

1. Base normativa não indexada → Consultor emitia parecer vazio. Resolvido com `indexar_normas`.
2. Valor recusado pela validação virava "campo ausente" e o sistema perguntava o que a pessoa já
   tinha respondido. Resolvido: `pergunta_de_esclarecimento` usa `avisos`.
3. Alternativa procurada só no dia pedido → pedido para domingo escalava. Resolvido:
   `_alternativas` varre 7 dias.
4. Agente 2 escalava 100% dos pedidos ("normas de outras instituições não vinculam o MP-GO") e,
   num caso, fez o oposto e barrou pedido legítimo aplicando prazo de 10 dias úteis da UFFS.
   Resolvido: papel comparativo, política interna decide, citação exigida só para restringir.

---

## O que corrigir

### 1. Resolução de data relativa é instável (prioridade alta)

Na rodada #02 o pedido *"Sala para 6 pessoas no próximo domingo às 10h por 1 hora"* foi resolvido
como **08/09 (terça-feira)**. Na #01 e na #03, corretamente como domingo. O erro é silencioso: a
data resultante é válida, então nada acusa.

Implemente validação do dia da semana em `ai_assistant/services.py`: quando o pedido mencionar
explicitamente um dia da semana ("domingo", "segunda", "terça"…), confira se a data devolvida cai
nesse dia. Se não cair, corrija para a próxima ocorrência do dia mencionado e registre em
`avisos`. Não invente dia quando o pedido não mencionar nenhum.

Critério de aceite: teste em `ai_assistant/test_busca_temporal.py` que force o modelo a devolver
uma data em dia divergente e verifique a correção mais o aviso.

### 2. Atributo fora do catálogo é descartado em silêncio

*"Sala para 8 pessoas com esteira ergométrica"* reservou normalmente — correto, porque
`normalize_room_search_attributes` descarta o que não está no catálogo. Mas ninguém avisa que o
requisito foi ignorado, e a pessoa recebe uma sala que não atende ao que pediu.

Faça `normalize_room_search_attributes` devolver também os termos descartados, e o pipeline
incluí-los na mensagem final ("o equipamento X não consta no catálogo e não foi considerado").

Critério de aceite: teste verificando que o termo descartado aparece na mensagem devolvida.

### 3. O caminho de conflito nunca foi exercitado em rodada real

`DECISAO_ALTERNATIVAS` por sala ocupada só tem cobertura em teste unitário com mock. Nenhum
pedido do benchmark chegou lá com LLM real.

Acrescente a `data/agentes/pedidos-teste.json` um par de pedidos encadeados: o primeiro reserva
um horário, o segundo pede o mesmo espaço e horário. Rode com `--persistir` para que o primeiro
exista quando o segundo chegar, e documente isso no `--help` do comando.

Critério de aceite: rodar `testar_agentes --somente P12 P13 --persistir` e obter
`reserva_confirmada` seguido de `alternativas`.

### 4. Separar espera de trabalho na medição

A métrica de latência hoje mistura processamento com fila de rate limit, o que a torna inútil
para comparar rodadas.

Instrumente o tempo gasto em retry de HTTP 429 e reporte `duracao_ms` e `espera_ms` separados,
por passo e no resumo.

Critério de aceite: o resumo do runner passa a mostrar latência líquida e tempo de espera.

---

## Restrições

- Evolua o código existente; não crie módulo paralelo nem reescreva o pipeline.
- Reuse `reservations.availability`, `reservations.validators` e `reservations.services` — a regra
  de conflito tem uma única fonte de verdade e não deve ser duplicada.
- Mantenha as guardas do Agente 2. Em especial: norma de outra instituição nunca vincula o MP-GO,
  e restringir exige citação.
- `ruff check` e `ruff format` limpos. Docstrings no padrão Google, em inglês; comentários e
  mensagens ao usuário em português.
- Todo teste novo roda sem chamar a API do Groq nem a base vetorial.
- `make test` verde ao final. Os 23 testes de `ai_assistant/test_agents.py` devem continuar
  passando.
- Ao terminar, atualize a tabela do Log de Iteração em
  `docs/dapia/Relatorio-de-benchmarking-Especificacao-MAS.docx` com a rodada #04.
