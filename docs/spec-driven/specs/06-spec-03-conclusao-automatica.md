# SPEC-03 — Conclusão automática da reserva após o horário

| Campo | Valor |
|---|---|
| Fatia | FAT-06 |
| Rastreabilidade | OUT-01 › ACT-04 › STP-04.03 › US-035 |
| Autor / Data | Revisão spec-driven / 2026-08-18 |
| Status | rascunho |
| Versão | 1.0 |

> `[FATO]` O estado `completed` existe no enum e no seed de demo. O README afirma que ele ocorre quando “o horário passou e houve check-in”. `[FATO]` Não há transição automática no código. `[FATO]` O painel de ocupação “agora” já ignora intervalos com fim no passado, então o card não fica vermelho só por status. O defeito observável é outro: reserva com check-in feito continua cancelável e reagendável depois do fim, e nunca aparece como concluída.

## 1. Resultado esperado

- **Comportamento que muda:** depois do fim, a reserva com presença vira histórico concluído; o dono não cancela nem reagenda o passado; o admin filtra “concluídas” de verdade.
- **Resultado de negócio (OUT-01):** o calendário e o histórico não mentem no tempo.
- **Métrica de resultado e linha de base:** número de reservas em check-in feito com fim no passado. Alvo da fatia: 0 após o ciclo de conclusão. Linha de base atual: `[A VALIDAR]` (todas as checked_in antigas no banco de demo/produção).
- **Métrica de guarda:** reserva ainda dentro do horário (início ≤ agora < fim) com check-in **não** vira concluída. Reserva só confirmada **não** vira concluída por esta fatia (quem não veio é no-show da SPEC-01).
- **Prazo de leitura:** 1 semana após o deploy, conferindo o estoque de estados.

## 2. Contexto e usuários

- **Perfis afetados:** [servidor](../01-perfil-usuario.md) (vê Passadas); [admin](../01-perfil-usuario.md) (filtra e confia no status).
- **Cenário de uso:** depois da reunião, na mesa, conferindo histórico; admin no fim do dia olhando o que de fato foi usado.
- **Volume esperado:** o mesmo das reservas do órgão; o job percorre só o que já venceu.

## 3. Escopo

**Está incluído:**

- Transição automática: check-in feito → concluída quando `agora ≥ fim`.
- Atraso máximo de 1 minuto após o fim, no ambiente padrão (mesmo espírito da SPEC-01 para no-show).
- Dono: reserva concluída aparece em Passadas, sem ações de cancelar, reagendar ou check-in.
- Admin: status concluída visível e filtrável; não cancela concluída.
- Disponibilidade: concluída não ocupa horário (já não deveria, por intervalo; a transição torna o status coerente).

**NÃO está incluído (e por quê):**

- Transformar confirmada vencida em concluída — isso seria mentir presença. Confirmada vencida é no-show (SPEC-01 / US-033).
- Check-out explícito na porta.
- Relatório analítico de ocupação histórica.
- Recalcular no-show nesta spec (já é FAT-04).

## 4. Fluxo principal

1. O dono fez check-in e usou a sala.
2. O horário de fim chega.
3. O sistema marca a reserva como concluída.
4. Em Minhas reservas, ela está em Passadas, com indicação de concluída.
5. Cancelar e reagendar não estão disponíveis.

## 5. Fluxos alternativos e de erro

| ID | Situação | Comportamento esperado |
|---|---|---|
| ALT-01 | Fim exatamente agora | Pode concluir (agora ≥ fim) |
| ALT-02 | Reserva concluída no seed/demo | Permanece concluída; job é idempotente |
| ERR-01 | Dono tenta cancelar concluída | Ação não executa; mensagem de que a reserva já encerrou |
| ERR-02 | Dono tenta reagendar concluída | Idem |
| ERR-03 | Admin tenta cancelar concluída | Ação não executa; linha permanece concluída |
| ERR-04 | Falha do ciclo de conclusão | Reserva pode permanecer check-in feito por no máximo 1 minuto após o fim; depois disso é defeito observável (RNF) |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Só reserva em check-in feito transita para concluída. |
| RN-02 | Condição: instante atual ≥ fim da reserva. |
| RN-03 | Concluída não ocupa slot e não admite cancelar, reagendar nem check-in. |
| RN-04 | Confirmada após o início sem presença continua sendo problema da SPEC-01 (no-show), não desta spec. |
| RN-05 | A transição é do sistema, não um botão do usuário. |

## 7. Critérios de aceite

```gherkin
AC-035.1 — Vira histórico depois do fim
  Dado que sou dono de uma reserva com presença registrada
  E o fim já passou
  E nenhum operador agiu
  Quando abro Minhas reservas na aba Passadas
  Então vejo essa reserva como concluída
  E não vejo ações de cancelar, reagendar ou check-in

AC-035.2 — Ainda no horário permanece em uso
  Dado que a reserva tem presença registrada
  E o instante atual está entre o início e o fim
  Quando consulto a reserva
  Então o estado não é concluída
  E o painel, se o intervalo cobre agora, mostra a sala ocupada

AC-035.3 — Confirmada não vira concluída
  Dado uma reserva confirmada cujo fim já passou
  E não houve check-in
  Quando o ciclo de conclusão corre
  Então essa reserva não aparece como concluída

AC-035.4 — Admin não cancela o passado concluído
  Dado que sou staff
  E a reserva está concluída
  Quando tento cancelá-la no painel
  Então o estado permanece concluída
  E vejo que reservas encerradas não se cancelam

AC-035.5 — Slot livre após o fim
  Dado uma reserva concluída das 10:00 às 11:00
  Quando outro servidor consulta a disponibilidade desse espaço no mesmo dia
  Então o intervalo 10:00–11:00 não aparece como ocupado por reserva ativa
  E um horário livre depois das 11:00 pode ser reservado
```

## 8. Requisitos não funcionais

| ID | Categoria | Requisito (com número) |
|---|---|---|
| RNF-01 | Desempenho | Ciclo de conclusão processa o lote do dia em até 5 s para até 10 mil reservas vencidas |
| RNF-02 | Segurança | Nenhum usuário comum força a transição; só o sistema |
| RNF-03 | Privacidade | não se aplica além do já visível ao dono e ao staff |
| RNF-04 | Acessibilidade | Status “Concluída” em texto, não só cor; mesmo padrão dos demais badges |
| RNF-05 | Auditoria | Transição registra horário em que virou concluída (campo de atualização já existente basta se o evento de telemetria existir) |
| RNF-06 | Disponibilidade | Atraso máximo 1 minuto após o fim, no ambiente padrão de execução |

IA embutida: **não se aplica**.

## 9. Dados e contratos

**Entidades e campos**

| Entidade.Campo | Tipo | Obrigatório | Valores válidos | Origem | Visível para |
|---|---|---|---|---|---|
| Reserva.estado | enum | sim | inclui concluída | sistema | dono e staff |
| Reserva.fim | data-hora | sim | — | dono / admin | dono e staff |
| Reserva.presencaEm | data-hora | sim para esta transição | preenchido | check-in | dono e staff |

**Estados e transições permitidas (esta fatia)**

| De | Para | Condição | Quem pode |
|---|---|---|---|
| check-in feito | concluída | agora ≥ fim | sistema |

Confirmada → no-show permanece na SPEC-01. Concluída não retorna para check-in feito.

**Integrações:** não se aplica.

Os status que ocupam horário continuam só confirmada e check-in feito (já é o as-is de `ACTIVE_RESERVATION_STATUSES`).

## 10. Telemetria

| Evento | Quando dispara | Propriedades | Serve para medir |
|---|---|---|---|
| reserva_concluida | transição | reserva, atraso_apos_fim_segundos | OUT-01; RNF-06 |
| acao_rejeitada_reserva_encerrada | cancelar/reagendar/check-in recusado | reserva, acao, perfil | guarda de ERR-01–03 |
| estoque_checkin_vencido | medição periódica | quantidade de check-in feito com fim no passado | métrica de resultado |

## 11. Riscos e hipóteses abertas

| ID | Descrição | Impacto se confirmado | Como resolver |
|---|---|---|---|
| H-06 | Status “check-in feito” eterno faz o time tratar o enum como irrelevante | OUT-01 não se lê; admin filtra errado | esta fatia |
| R-01 | Job de no-show e job de conclusão competem no mesmo instante | confirmada no limiar poderia ser classificada errado | ordem: no-show só de confirmada; conclusão só de check-in feito — conjuntos disjuntos |
| R-02 | Labels em inglês (“Completed”) na UI | usuário não reconhece o estado | textos de status desta fatia em pt-BR |

## 12. Restrições de implementação (quando a spec alimenta um agente)

- **Stack:** reutilizar o padrão do `release_no_shows` (management command + disparo no ambiente padrão). Preferir um único ciclo periódico que aplique no-show e conclusão na ordem RN da R-01.
- **Padrões / caminhos:** `reservations/enums.py`, `reservations/services.py`, `ReservationListView` (abas), `ReservationDetailView` (`can_cancel` / `can_reschedule` / `can_check_in` hoje incluem check-in feito sem olhar o fim), `admin_cancel_reservation`.
- **Fora de limites:** não usar `completed` para quem não fez check-in; não mudar a regra de ocupação “agora” além de garantir que concluída está fora.
- **Comandos de verificação:** testes do job idempotente; testes das abas Ativas/Passadas; testes de detalhe sem botões; `make test` e `make lint`.
- **Ordem sugerida:** (1) transição no service; (2) esconder ações no detalhe e no admin; (3) disparo no ambiente padrão; (4) labels pt-BR; (5) telemetria.

## 13. Definição de pronto

- [ ] AC-035.1 a AC-035.5 passando
- [ ] RNF-01 a RNF-06 verificados
- [ ] Telemetria conferida
- [ ] ERR-01 a ERR-04 exercitados
- [ ] README da máquina de estados deixa de documentar conclusão que o código não faz — passa a coincidir
- [ ] Leitura do estoque `estoque_checkin_vencido` em 1 semana (alvo 0)
