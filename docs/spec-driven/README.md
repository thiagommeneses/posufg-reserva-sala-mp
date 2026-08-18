# Spec-driven UX — Reserva de Espaços (MP-GO)

Revisão as-is do produto já implementado (reservas, painel admin, assistente RAG), mais specs das fatias que ainda não fecham o resultado. Método: skill spec-driven-ux (Levy, Patton, Lowdermilk).

Esta pasta **não substitui** [`PRD.md`](../../PRD.md) nem [`prd.json`](../../prd.json) do Ralph Loop. O PRD lista o que construir; estes artefatos ligam resultado → narrativa → fatia → critério observável.

Nenhuma entrevista nova foi feita nesta revisão. Afirmações estão marcadas `[FATO]`, `[HIPÓTESE]` ou `[A VALIDAR]`.

## Como ler

| Ordem | Artefato | Fase | O que responde |
|---|---|---|---|
| 1 | [00-discovery-brief.md](00-discovery-brief.md) | 1 | Problema, proposta de valor, OUT-01 a OUT-04, hipóteses |
| 2 | [01-perfil-usuario.md](01-perfil-usuario.md) | 1 | Quem usa, quem decide, quem é afetado |
| 3 | [02-analise-competitiva.md](02-analise-competitiva.md) | 1 | Planilha, telefone, shadow booking, onde competir |
| 4 | [03-experimento-validacao.md](03-experimento-validacao.md) | 1 / 4 | EXP-01 a EXP-03 (ainda não executados) |
| 5 | [04-story-map.yaml](04-story-map.yaml) | 2 | Fonte da verdade do mapa (IDs estáveis) |
| 6 | [05-story-map.md](05-story-map.md) | 2 | Visualização gerada — não editar à mão |
| 7 | [08-plano-de-fatias.md](08-plano-de-fatias.md) | 2 | O que já foi entregue e a ordem do que falta |
| 8 | [specs/](specs/) | 3 | Specs das fatias próximas |

Validar e regenerar o mapa:

```bash
python .agents/skills/spec-driven-ux/scripts/storymap.py validar docs/spec-driven/04-story-map.yaml
python .agents/skills/spec-driven-ux/scripts/storymap.py md docs/spec-driven/04-story-map.yaml -o docs/spec-driven/05-story-map.md
```

## Fatias

| Fatia | Resultado | Status | Spec |
|---|---|---|---|
| FAT-01 | Servidor reserva; calendário como fonte da verdade | entregue (esqueleto ambulante; US-021 em aberto) | — |
| FAT-02 | Admin vê ocupação e bloqueia manutenção | entregue | — |
| FAT-03 | Consulta normativa com fonte (ou recusa) | entregue | EXP-03 em paralelo |
| FAT-04 | Check-in na porta; no-show libera a sala | próxima | [SPEC-01](specs/06-spec-01-checkin-na-porta.md) |
| FAT-05 | Políticas de duração, antecedência e audiência | próxima | [SPEC-02](specs/06-spec-02-politicas-de-uso.md) |
| FAT-06 | Conclusão automática após o horário | próxima | [SPEC-03](specs/06-spec-03-conclusao-automatica.md) |
| FAT-07 | Admin reagenda reserva de terceiro | próxima | [SPEC-04](specs/06-spec-04-admin-resolve-conflito.md) |

Ordem de aprendizado: FAT-04 → FAT-05 → FAT-06 → FAT-07. Se o prazo apertar, FAT-07 sai primeiro (ver critérios de corte no plano de fatias).

## IDs

```
OUT-01  ocupação visível = uso real
OUT-02  achar e reservar sem telefone
OUT-03  admin opera sem planilha paralela
OUT-04  resposta normativa ancorada (não é norma do MP-GO)
```

Não renumerar ID já usado. Obsoleto se marca; o próximo número é novo.
