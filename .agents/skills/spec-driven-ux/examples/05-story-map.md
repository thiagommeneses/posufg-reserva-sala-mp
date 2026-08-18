# Story Map — Painel de Triagem de Manifestações

Versão 0.3 · atualizado em 2026-08-14

## Resultados

| ID | Resultado | Métrica |
|---|---|---|
| OUT-01 | Assessor distribui a manifestação no mesmo dia da chegada | Tempo entre protocolo e distribuição (linha de base: 2,3 dias úteis) |
| OUT-02 | Manifestação chega à área certa na primeira distribuição | % de redistribuição por classificação errada (linha de base: 18%) |
| OUT-03 | Coordenação enxerga o estado da fila sem pedir relatório | Nº de solicitações manuais de status por semana (linha de base: 9) |

## Espinha dorsal

| ACT-01 Assumir a fila do dia | ACT-02 Entender a manifestação | ACT-03 Decidir o encaminhamento | ACT-04 Registrar e acompanhar |
|---|---|---|---|
| STP-01.01 Ver o que chegou e o que é meu | STP-02.01 Ler o essencial já extraído | STP-03.01 Classificar o assunto | STP-04.01 Confirmar a distribuição no sistema oficial |
| STP-01.02 Retomar o que ficou pendente ontem | STP-02.02 Consultar o documento quando necessário | STP-03.02 Escolher a área ou pessoa responsável | STP-04.02 Acompanhar a fila do time |
|  | STP-02.03 Ver se já houve manifestação parecida |  |  |

## Fatias

### FAT-01 — Assessor tria e distribui uma manifestação comum sem abrir o PDF *(esqueleto ambulante)*

- Resultado: OUT-01
- Aprendizado buscado: Verificar se os campos extraídos bastam para decidir (H-01, H-02)

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-01 | STP-01.01 | US-001 Fila do dia ordenada por prazo | pronta |
| ACT-02 | STP-02.01 | US-010 Resumo estruturado com assunto, requerente, órgão e prazo | pronta |
| ACT-02 | STP-02.01 | US-011 Cada campo aponta o trecho de origem no documento | pronta |
| ACT-03 | STP-03.01 | US-020 Sugestão de classificação com nível de confiança visível | pronta |
| ACT-03 | STP-03.01 | US-021 Correção da classificação em um passo | pronta |
| ACT-03 | STP-03.02 | US-022 Destino sugerido a partir da classificação | pronta |
| ACT-04 | STP-04.01 | US-030 Registro no sistema legado com confirmação visível | pronta |
| ACT-04 | STP-04.01 | US-031 Comportamento definido quando o sistema legado está fora | pronta |

### FAT-02 — Assessor lida com os casos que fogem do comum sem sair do painel

- Resultado: OUT-02
- Aprendizado buscado: Medir se a redistribuição cai quando há contexto e histórico

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-01 | STP-01.01 | US-002 Reserva de item para evitar triagem duplicada | descoberta |
| ACT-01 | STP-01.02 | US-003 Separação entre novos e retomados | descoberta |
| ACT-02 | STP-02.02 | US-012 Documento original ao lado, sem trocar de tela | descoberta |
| ACT-02 | STP-02.03 | US-013 Histórico do mesmo requerente ou assunto | descoberta |
| ACT-03 | STP-03.02 | US-023 Encaminhamento com justificativa obrigatória quando contraria a sugestão | descoberta |

### FAT-03 — Coordenação acompanha a fila e redistribui carga

- Resultado: OUT-03
- Aprendizado buscado: Confirmar que a visão de fila substitui os pedidos manuais de status

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-04 | STP-04.02 | US-040 Painel de fila por área com prazos em risco | descoberta |
| ACT-04 | STP-04.02 | US-041 Redistribuição de itens entre assessores | descoberta |

## Hipóteses abertas

| ID | Hipótese | Risco | Experimento |
|---|---|---|---|
| H-01 | O assessor confia na extração automática o bastante para decidir sem abrir o documento | alto | EXP-01 |
| H-02 | Assunto, requerente, órgão e prazo bastam para o caso comum | alto | EXP-01 |
| H-03 | A classificação automática acerta acima do patamar aceitável para ser exibida como sugestão | medio | EXP-02 |

## Deliberadamente fora de escopo

- Responder a manifestação dentro do painel (segue no sistema legado)
- Fluxo específico das unidades regionais
- Ranking de produtividade individual por assessor
- Ingestão de manifestações por e-mail
