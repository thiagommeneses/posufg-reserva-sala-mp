# Plano de Fatias — Painel de Triagem de Manifestações

> **Exemplo didático.** Ordem definida por aprendizado e risco, não por facilidade de construção.

## Visão geral

| Fatia | Resultado entregue | OUT | Aprendizado buscado | Histórias | Status |
|---|---|---|---|---|---|
| FAT-01 | Assessor tria e distribui um caso comum sem abrir o PDF | OUT-01, OUT-02 | H-01, H-02, H-03 | US-001, US-010, US-011, US-020, US-021, US-022, US-030, US-031 | em entrega |
| FAT-02 | Assessor resolve os casos atípicos sem sair do painel | OUT-02 | Contexto e histórico reduzem redistribuição? | US-002, US-003, US-012, US-013, US-023 | planejada |
| FAT-03 | Coordenação acompanha a fila e remaneja carga | OUT-03 | A visão de fila elimina os pedidos manuais de status? | US-040, US-041 | planejada |

## FAT-01 — Assessor tria e distribui um caso comum sem abrir o PDF

- **Quem consegue fazer o que de novo:** o assessor de triagem conclui, do início ao fim, a triagem de uma manifestação comum — vê a fila, lê o resumo, confirma a classificação e registra a distribuição no sistema oficial.
- **Por que esta fatia primeiro:** ela testa H-01 e H-02, que sustentam a proposta de valor inteira. Se o assessor abrir o PDF de qualquer jeito, nenhuma das outras fatias faz diferença.
- **Esqueleto ambulante:** sim — atravessa fila, leitura, decisão e registro no legado, com apenas um caminho feliz em cada ponto.
- **Explicitamente adiado nesta fatia:** casos atípicos, sigilo além do bloqueio simples, reserva de item, histórico, visão de coordenação.
- **Como mediremos:** resultado — % de triagens sem `documento_aberto`; guarda — taxa de redistribuição e tempo médio por item.
- **Hipóteses que testa:** H-01, H-02, H-03.
- **Dependências e riscos:** disponibilidade da API de distribuição do legado; proporção real de documentos sem camada de texto.
- **Specs derivadas:** SPEC-01 (resumo estruturado), SPEC-02 (sugestão de classificação), SPEC-03 (registro no legado).

## FAT-02 — Casos atípicos

- **Quem consegue fazer o que de novo:** resolver, dentro do painel, os itens que hoje forçam a volta ao sistema legado — documento ao lado, histórico do requerente, retomada de pendências e justificativa de discordância.
- **Por que depois:** só faz sentido dimensionar o atípico depois de saber a frequência real dele, medida na FAT-01.
- **Como mediremos:** taxa de redistribuição (OUT-02) e proporção de itens devolvidos à fila.
- **Specs derivadas:** a definir após a leitura da FAT-01.

## FAT-03 — Visão de coordenação

- **Quem consegue fazer o que de novo:** coordenador vê a fila por área, identifica prazos em risco e remaneja itens.
- **Por que por último:** depende de volume real fluindo pelo painel; sem as fatias anteriores, o painel mostraria uma fila vazia.
- **Risco de adoção registrado:** a coordenação pediu métrica individual por assessor; os assessores sinalizaram efeito perverso. Decisão a tomar com dados da FAT-01, não agora.

## Critérios de corte

Se o prazo apertar, sai nesta ordem, decidido agora:

1. US-021 (correção em um passo) vira correção em formulário comum — piora a experiência, não bloqueia o resultado.
2. US-001 (ordenação por prazo) vira ordem de chegada — perde priorização, mantém o fluxo.
3. Nunca cortar US-031 (comportamento com o legado fora do ar): sem ele o assessor perde trabalho silenciosamente.

## Registro de mudanças do plano

| Data | Mudança | Motivo (aprendizado) |
|---|---|---|
| 2026-08-12 | US-013 (histórico) movida de FAT-01 para FAT-02 | Observação mostrou que o histórico é consultado em minoria dos casos |
| 2026-08-14 | US-031 promovida a item não cortável | Falha do legado ocorreu duas vezes durante a observação |
