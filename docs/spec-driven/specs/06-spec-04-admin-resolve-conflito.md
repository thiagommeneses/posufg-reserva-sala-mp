# SPEC-04 — Admin resolve conflito reagendando reserva de terceiro

| Campo | Valor |
|---|---|
| Fatia | FAT-07 |
| Rastreabilidade | OUT-03 › ACT-06 › STP-06.04 › US-056 |
| Autor / Data | Revisão spec-driven / 2026-08-18 |
| Status | rascunho |
| Versão | 1.0 |

> `[FATO]` Staff já cancela qualquer reserva (`admin_cancel_reservation`). `[FATO]` Reagendar existe só para o dono (`reschedule_reservation` exige ownership). `[FATO]` Não há trilha de “quem alterou a reserva de quem” além de timestamps genéricos. Esta fatia é exceção operacional: só entra se o cancelamento puro gerar telefone de volta (H-05).

## 1. Resultado esperado

- **Comportamento que muda:** o admin move o horário de outra pessoa em vez de só apagar o compromisso; fica visível quem moveu.
- **Resultado de negócio (OUT-03):** conflito resolvido sem planilha e sem mandar o servidor criar tudo de novo.
- **Métrica de resultado e linha de base:** conflitos tratados por reagendamento admin vs. cancelamento admin. Linha de base: 100% cancelamento `[FATO]` (é a única ferramenta). Alvo `[HIPÓTESE]`: parte dos conflitos do piloto sai de “derrubar”.
- **Métrica de guarda:** overlap continua impossível; usuário comum não reagenda reserva alheia; toda movimentação tem ator staff identificável.
- **Prazo de leitura:** 3 semanas de painel em uso real (ou EXP-01 se mostrar que H-05 é fraca — aí esta spec não entra).

## 2. Contexto e usuários

- **Perfis afetados:** [administrador](../01-perfil-usuario.md) (usa); [servidor dono](../01-perfil-usuario.md) (é afetado — a reunião anda); [chefia](../01-perfil-usuario.md) (pode perguntar quem mandou).
- **Cenário de uso:** telefone tocando, duas reuniões no mesmo espaço, hierarquia informal. Desktop, agora.
- **Volume esperado:** `[HIPÓTESE]` poucos overrides/semana; cada um é politicamente caro.

## 3. Escopo

**Está incluído:**

- Staff escolhe uma reserva confirmada ou com check-in feito (ainda no horário) e informa novo início e fim no mesmo espaço.
- Mesmos guards de overlap, manutenção, espaço e — se SPEC-02 estiver em produção — política de duração/antecedência.
- O dono permanece o mesmo; só o horário muda.
- Depois do sucesso, o dono vê o novo horário em Minhas reservas; o intervalo antigo fica livre.
- Trilha: quem (staff), quando, horário anterior, horário novo, reserva.

**NÃO está incluído (e por quê):**

- Trocar o espaço da reserva (muda o significado de “mesmo compromisso”; pode vir depois).
- Trocar o dono.
- Notificar o dono por e-mail — fora do PRD; a UI do dono passa a mostrar o novo horário quando ele abrir.
- Fila de aprovação do override.
- Reagendar cancelada, no-show ou concluída.

## 4. Fluxo principal

1. O admin localiza a reserva no painel.
2. Escolhe reagendar, informa data e horário novos no mesmo espaço.
3. O sistema valida overlap, manutenção e política (se houver).
4. Confirma; o admin vê a linha atualizada.
5. O horário antigo aparece livre; o novo, ocupado pelo mesmo dono.

## 5. Fluxos alternativos e de erro

| ID | Situação | Comportamento esperado |
|---|---|---|
| ALT-01 | Novo horário idêntico ao atual | Mensagem de que nada mudou; sem novo evento de auditoria de movimentação |
| ERR-01 | Usuário comum tenta a ação | 403 / ação inexistente na UI dele |
| ERR-02 | Novo horário sobrepõe outra reserva ou manutenção | Reserva original intacta; mensagem de conflito, como no reagendamento do dono |
| ERR-03 | Reserva cancelada, no-show ou concluída | Ação indisponível; estado explicado |
| ERR-04 | Política de duração/antecedência (SPEC-02) violada | Reserva original intacta; mensagem com o limite |
| ERR-05 | Staff tenta reagendar a própria reserva por este fluxo | Permitido (é staff); equivalente a mover qualquer uma, com trilha |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Só staff executa reagendamento de terceiro. |
| RN-02 | Espaço não muda. Dono não muda. |
| RN-03 | Estados de origem: confirmada ou check-in feito com fim ainda no futuro. Check-in feito reagendada volta a confirmada no novo horário `[HIPÓTESE]` alinhada ao as-is do dono (`reschedule_reservation` zera para confirmada) — o dono precisará de novo check-in na janela nova. |
| RN-04 | Intervalo novo passa pelas mesmas validações de slot que uma reserva nova, excluindo a própria reserva. |
| RN-05 | Cancelar continua existindo (US-055); reagendar não substitui derrubar quando o compromisso deve sumir. |
| RN-06 | Toda movimentação efetiva registra ator staff, valores antes/depois. |

## 7. Critérios de aceite

```gherkin
AC-056.1 — Move o horário e libera o antigo
  Dado que sou staff
  E Maria tem reserva confirmada na Sala Alfa das 10:00 às 11:00
  E das 14:00 às 15:00 está livre
  Quando reagendo essa reserva para 14:00–15:00 no mesmo espaço
  Então o intervalo 10:00–11:00 aparece livre para outro servidor
  E 14:00–15:00 aparece ocupado por Maria
  E Maria, autenticada, vê 14:00–15:00 em Minhas reservas

AC-056.2 — Overlap recusado
  Dado que João já ocupa 14:00–15:00 na mesma sala
  Quando tento reagendar a reserva de Maria para 14:00–15:00
  Então o horário de Maria permanece 10:00–11:00
  E vejo que aquele horário não está livre

AC-056.3 — Comum não move alheio
  Dado que estou autenticado como usuário comum
  Quando tento reagendar a reserva de outra pessoa
  Então a ação não é executada
  E o horário permanece

AC-056.4 — Encerrada não se move
  Dado uma reserva concluída ou no-show
  Quando sou staff e abro as ações no painel
  Então reagendar não está disponível para essa reserva

AC-056.5 — Trilha do override
  Dado o sucesso de AC-056.1
  Quando a chefia consulta quem alterou aquela reserva
  Então vê o staff, o horário da ação, 10:00–11:00 como valor anterior e 14:00–15:00 como novo

AC-056.6 — Check-in anterior não vale no novo horário
  Dado uma reserva com presença já registrada ainda dentro do horário original
  Quando o admin reagenda para um horário futuro
  Então o estado volta a exigir check-in no novo horário
  E a presença antiga não conta como presença no novo intervalo
```

## 8. Requisitos não funcionais

| ID | Categoria | Requisito (com número) |
|---|---|---|
| RNF-01 | Desempenho | Reagendar no painel conclui em até 2 s no p95 |
| RNF-02 | Segurança | Autorização staff no servidor, não só ocultar o botão |
| RNF-03 | Privacidade | Admin vê o necessário para o conflito (dono, espaço, horário); não cria novo dado pessoal |
| RNF-04 | Acessibilidade | Formulário de reagendamento admin usável por teclado; erros em texto |
| RNF-05 | Auditoria | Registro imutável o suficiente para responder “quem moveu, de onde para onde, quando” por no mínimo o prazo de retenção das reservas |

IA embutida: **não se aplica**.

## 9. Dados e contratos

**Entidades e campos**

| Entidade.Campo | Tipo | Obrigatório | Valores válidos | Origem | Visível para |
|---|---|---|---|---|---|
| Reserva.inicio / Reserva.fim | data-hora | sim | fim > início, sem overlap | staff neste fluxo | dono e staff |
| Reserva.estado | enum | sim | após mover: confirmada (RN-03) | sistema | dono e staff |
| Reserva.dono | usuário | sim | inalterado | original | staff |
| Override.ator | usuário staff | sim | staff | sessão | staff / auditoria |
| Override.antesInicio / antesFim | data-hora | sim | snapshot | sistema | staff / auditoria |
| Override.depoisInicio / depoisFim | data-hora | sim | snapshot | sistema | staff / auditoria |
| Override.em | data-hora | sim | — | sistema | staff / auditoria |

**Estados e transições permitidas (esta fatia)**

| De | Para | Condição | Quem pode |
|---|---|---|---|
| confirmada | confirmada (novos horários) | slot válido | staff |
| check-in feito | confirmada (novos horários) | slot válido, fim original ainda futuro | staff |

**Integrações:** não se aplica.

Reutilizar a validação de `reschedule_reservation` sem a restrição de dono, **ou** um service de admin que chama as mesmas validações de slot. Duplicar a regra de overlap é defeito.

## 10. Telemetria

| Evento | Quando dispara | Propriedades | Serve para medir |
|---|---|---|---|
| admin_reagendou | sucesso | reserva, ator, duracao_deslocamento_minutos | OUT-03; H-05 |
| admin_reagendamento_recusado | overlap/política/estado | motivo | guarda |
| admin_cancelou | já existe implicitamente no as-is — emitir se ainda não houver | reserva, ator | denominador conflito = reagendou / (reagendou + cancelou) |

## 11. Riscos e hipóteses abertas

| ID | Descrição | Impacto se confirmado | Como resolver |
|---|---|---|---|
| H-05 | Cancelar e mandar refazer já basta, ou o admin não ousa mover compromisso alheio | fatia não move métrica | EXP-01; critério de corte do plano: FAT-07 sai primeiro se o prazo apertar |
| R-01 | Dono não é avisado (e-mail fora de escopo) e aparece na sala antiga | conflito social na porta | texto visível em Minhas reservas; considerar notificação numa fatia futura se EXP-02/01 mostrarem o dano |
| R-02 | Zerar check-in no reagendar (RN-03) surpreende o admin | “mas ele já tinha dado presença” | copy na confirmação do painel: o novo horário exige novo check-in |

## 12. Restrições de implementação (quando a spec alimenta um agente)

- **Stack:** Django + HTMX no `admin_dashboard`, no padrão de `AdminReservationCancelView`.
- **Padrões / caminhos:** `admin_dashboard/views.py`, `templates/admin_dashboard/`, `reservations/services.py` (`reschedule_reservation` hoje recusa não-dono). Não usar Django Admin como UI desta fatia.
- **Fora de limites:** não abrir reagendamento alheio para usuário comum; não enviar e-mail; não mudar de espaço nesta spec.
- **Comandos de verificação:** testes de overlap, 403 para comum, trilha, reset de check-in; `make test`; `make lint`.
- **Ordem sugerida:** (1) service admin reusando validação de slot; (2) UI no painel; (3) trilha; (4) interação com estados da SPEC-03; (5) política da SPEC-02 se já estiver no ar; (6) telemetria.

## 13. Definição de pronto

- [ ] AC-056.1 a AC-056.6 passando
- [ ] RNF-01 a RNF-05 verificados
- [ ] Telemetria conferida
- [ ] ERR-01 a ERR-05 exercitados
- [ ] Acessibilidade do formulário admin
- [ ] Copy de confirmação cobre o reset de check-in (R-02)
- [ ] H-05 relida em 3 semanas: se ninguém usar reagendar, a história volta no mapa, não ganha escopo extra
