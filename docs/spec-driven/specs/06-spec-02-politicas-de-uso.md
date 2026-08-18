# SPEC-02 — Políticas de uso por espaço (duração, antecedência, quem reserva)

| Campo | Valor |
|---|---|
| Fatia | FAT-05 |
| Rastreabilidade | OUT-03 › ACT-03 / ACT-06 › STP-03.02 / STP-06.05 › US-024, US-025, US-057 |
| Autor / Data | Revisão spec-driven / 2026-08-18 |
| Status | rascunho |
| Versão | 1.0 |

> `[FATO]` Não existe model nem regra de política no código (PRD story 9 não implementada). Reserva hoje é instantânea para qualquer autenticado, em qualquer duração que o formulário aceite, desde que não haja overlap. `[FATO]` O MP-GO não tem norma publicada; as regras atuais são informais por departamento. Esta spec grava **política operacional do admin**, não um regulamento oficial.

## 1. Resultado esperado

- **Comportamento que muda:** o admin registra duração máxima, antecedência mínima e quem pode reservar cada espaço; o servidor vê a recusa no formulário e corrige, em vez de ligar.
- **Resultado de negócio (OUT-03):** controle operacional sem planilha paralela.
- **Métrica de resultado e linha de base:** proporção de recusas de política resolvidas no próprio fluxo (nova tentativa válida) versus contato com o admin. Linha de base: `[A VALIDAR]` (hoje a recusa de política não existe).
- **Métrica de guarda:** o caso comum elegível continua sem aprovação manual (US-022 permanece). Taxa de abandono da reserva após recusa não pode explodir — se EXP-01 mostrar que a regra informal era “sempre abre exceção”, a política rígida refuta H-03.
- **Prazo de leitura:** 3 semanas após o admin configurar políticas nos espaços reais do piloto.

## 2. Contexto e usuários

- **Perfis afetados:** [administrador](../01-perfil-usuario.md) (configura); [servidor que reserva](../01-perfil-usuario.md) (é barrado ou passa); [chefia](../01-perfil-usuario.md) (decide se a regra informal pode virar configuração).
- **Cenário de uso:** admin no painel, uma vez por espaço, sob pouca pressão; servidor no formulário de reserva/reagendamento, sob pressão de horário.
- **Volume esperado:** `[HIPÓTESE]` 5–30 espaços; poucas mudanças de política por mês; dezenas de reservas/dia passando pela validação.

## 3. Escopo

**Está incluído:**

- Por espaço, três controles opcionais: duração máxima da reserva; antecedência mínima entre o momento da reserva e o início; audiência (qualquer autenticado **ou** apenas staff).
- Aplicação na criação e no reagendamento feitos pelo dono.
- Mensagem específica em português dizendo qual regra falhou e o limite numérico.
- Valores em branco = comportamento atual (sem esse limite).
- Registro de quem alterou a política e quando.

**NÃO está incluído (e por quê):**

- Fluxo de aprovação / sala premium — fora de escopo do mapa até H-03 ser medida; quebraria a reserva instantânea do esqueleto.
- Motor genérico de regras, feriados, “somente procuradores”, listas de usuários nomeados — EXP-01 deve primeiro nomear 2–3 regras reais; esta fatia cobre o mínimo que o PO já descreveu (duração, quem reserva o quê, antecedência operacional).
- Aplicar política retroativa em reservas já confirmadas.
- Política global da instituição (tudo é por espaço, para caber na fragmentação real dos departamentos).
- Reagendamento feito pelo admin (SPEC-04): quando existir, deve reutilizar as mesmas regras — contrato na seção 9.

## 4. Fluxo principal

1. O admin abre o cadastro de um espaço.
2. Informa, se quiser, duração máxima (horas), antecedência mínima (horas) e se só staff reserva.
3. Salva; a interface confirma que a política vale para novas reservas e reagendamentos.
4. Um servidor elegível reserva um horário que respeita os limites — fluxo idêntico ao de hoje, instantâneo.
5. Um servidor que estoura duração ou antecedência, ou não é staff num espaço restrito, vê a recusa e os números da regra, sem criar a reserva.

## 5. Fluxos alternativos e de erro

| ID | Situação | Comportamento esperado |
|---|---|---|
| ALT-01 | Campos de política em branco | Espaço se comporta como hoje: qualquer autenticado, sem teto de duração além do overlap |
| ALT-02 | Reagendamento do dono | As mesmas três regras se aplicam ao novo intervalo |
| ERR-01 | Usuário comum tenta reservar espaço só-staff | Reserva não é criada; mensagem diz que aquele espaço é restrito e a quem pedir |
| ERR-02 | Duração acima do máximo | Reserva não é criada; mensagem informa o máximo em horas daquele espaço |
| ERR-03 | Início mais próximo do que a antecedência mínima | Reserva não é criada; mensagem informa a antecedência exigida |
| ERR-04 | Admin informa duração máxima ≤ 0 ou antecedência < 0 | Formulário não salva; erro de campo |
| ERR-05 | Sem permissão staff no cadastro do espaço | Como hoje: 403 |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Política é por espaço, não por usuário. |
| RN-02 | Duração da reserva = fim − início. Se houver máximo, duração deve ser ≤ máximo. |
| RN-03 | Antecedência = início − instante em que o pedido é feito. Se houver mínimo, antecedência deve ser ≥ mínimo. |
| RN-04 | Audiência “apenas staff”: `is_staff` verdadeiro. Usuário comum é recusado mesmo com horário livre. |
| RN-05 | Reserva instantânea permanece para quem passa nas regras; não há fila de aprovação. |
| RN-06 | Espaço inativo continua irreservável, independentemente da política. |
| RN-07 | Overlap e bloqueio de manutenção continuam sendo recusados como hoje, avaliados depois (ou junto) da política, sempre visíveis. |
| RN-08 | Alteração de política não cancela reservas já confirmadas. |

## 7. Critérios de aceite

```gherkin
AC-057.1 — Admin grava a política
  Dado que sou staff
  Quando defino na Sala Executiva duração máxima de 2 horas, antecedência mínima de 1 hora e audiência “apenas staff”
  Então vejo a confirmação de que a política foi salva
  E outro staff, ao reabrir o cadastro, vê os mesmos valores

AC-024.1 — Duração acima do máximo
  Dado que a Sala Focus tem duração máxima de 2 horas
  E sou usuário comum autenticado
  Quando tento reservar 3 horas contínuas num horário livre
  Então a reserva não é criada
  E vejo que o máximo naquele espaço é 2 horas

AC-024.2 — Antecedência insuficiente
  Dado que a Sala Alfa exige 1 hora de antecedência
  E o início escolhido está a 20 minutos de agora
  Quando confirmo a reserva
  Então a reserva não é criada
  E vejo a antecedência mínima daquele espaço

AC-024.3 — Caso comum segue instantâneo
  Dado que a Sala Beta tem duração máxima de 4 horas e antecedência mínima de 0
  E sou autenticado elegível
  E escolho 1 hora livre amanhã
  Quando confirmo
  Então a reserva é criada na hora
  E o horário passa a aparecer ocupado

AC-025.1 — Espaço só para staff
  Dado que o Auditório Central aceita apenas staff
  Quando um usuário comum tenta reservar um horário livre
  Então a reserva não é criada
  E vejo que o espaço é restrito
  Quando um staff reserva o mesmo horário válido
  Então a reserva é criada

AC-057.2 — Em branco = sem limite extra
  Dado um espaço sem duração, antecedência nem audiência preenchidas
  Quando um usuário comum reserva 6 horas livres com início em 10 minutos
  Então a reserva é criada (sujeita só a overlap e espaço ativo)

AC-024.4 — Reagendamento respeita a política
  Dado que sou dono de uma reserva confirmada
  E o espaço tem duração máxima de 2 horas
  Quando tento reagendar para 4 horas
  Então o horário original permanece
  E vejo o máximo de 2 horas

AC-057.3 — Política inválida no cadastro
  Dado que sou staff
  Quando tento salvar duração máxima 0 horas
  Então o cadastro não é salvo
  E o campo de duração indica o problema
```

## 8. Requisitos não funcionais

| ID | Categoria | Requisito (com número) |
|---|---|---|
| RNF-01 | Desempenho | Validação da política na reserva em até 200 ms além do custo atual de overlap, p95 |
| RNF-02 | Segurança | Só staff altera política; usuário comum não envia esses campos com efeito |
| RNF-03 | Privacidade | Mensagem de espaço restrito não lista quem são os staffs |
| RNF-04 | Acessibilidade | Campos de política com rótulo, erro associado ao campo, formulário de reserva anuncia a recusa de forma textual (não só cor) |
| RNF-05 | Auditoria | Cada mudança de política registra ator, espaço, valores anteriores e novos, horário |

IA embutida: **não se aplica**.

## 9. Dados e contratos

**Entidades e campos**

| Entidade.Campo | Tipo | Obrigatório | Valores válidos | Origem | Visível para |
|---|---|---|---|---|---|
| Espaco.duracaoMaximaHoras | número decimal | não | > 0, até 24 | admin | admin no cadastro; usuário só via mensagem de recusa / ajuda |
| Espaco.antecedenciaMinimaHoras | número decimal | não | ≥ 0, até 720 | admin | idem |
| Espaco.audienciaReserva | enum | sim (default todos) | todos_autenticados, apenas_staff | admin | idem |
| Politica.alteradoPor | usuário | sim na alteração | staff | sistema | staff / auditoria |
| Politica.alteradoEm | data-hora | sim na alteração | — | sistema | staff / auditoria |

**Estados e transições permitidas**

não se aplica — política não é máquina de estados da reserva. A reserva continua nascendo confirmada quando passa.

**Integrações**

não se aplica — sem sistema externo.

Contrato com SPEC-04: o reagendamento de terceiro deve chamar a mesma validação de política; se SPEC-04 entrar antes, duplicar a regra é defeito.

## 10. Telemetria

| Evento | Quando dispara | Propriedades | Serve para medir |
|---|---|---|---|
| politica_salva | admin grava política | espaço, campos alterados | adoção da fatia |
| reserva_recusada_politica | criação ou reagendamento barrado | espaço, motivo (duracao / antecedencia / audiencia) | OUT-03; H-03 |
| reserva_criada | sucesso | espaço, passou_politica sim/não | denominador; guarda da instantaneidade |

## 11. Riscos e hipóteses abertas

| ID | Descrição | Impacto se confirmado | Como resolver |
|---|---|---|---|
| H-03 | Sem norma formal, o admin não ousa gravar regra — ou grava e o servidor volta ao telefone pedindo exceção | política vira teatro ou trava H-01 | EXP-01 antes ou em paralelo; se refutar, não construir motor de aprovação nesta fatia |
| R-01 | Unidades (horas vs minutos) confundem | recusas incompreensíveis | UI em horas, com exemplo (“reunião de no máximo 2 horas”) |
| R-02 | Fragmentação real (cada departamento uma regra) pede política por departamento, não por espaço | admin duplica regra em 10 salas | aceitável nesta fatia; agrupamento é fatia futura |

## 12. Restrições de implementação (quando a spec alimenta um agente)

- **Stack:** Django; campos no espaço (`spaces` app) e validação no mesmo caminho de `validate_reservation_slot` / `create_reservation` / `reschedule_reservation`.
- **Padrões / caminhos:** `spaces/models.py`, `admin_dashboard` formulário de espaço, `reservations/services.py` e `reservations/validators.py`. Mensagens ao usuário em pt-BR (hoje há validators em inglês na API — novas mensagens desta fatia nascem em português na UI).
- **Fora de limites:** não criar app de “workflow”; não alterar US-022 para exigir aprovação; não aplicar nas reservas já existentes.
- **Comandos de verificação:** `make test`, `make lint`; testes de criação/reagendamento com cada recusa e com ALT-01.
- **Ordem sugerida:** (1) campos e formulário admin; (2) validação na criação; (3) validação no reagendamento do dono; (4) mensagens; (5) auditoria; (6) telemetria.

## 13. Definição de pronto

- [ ] AC-057.1 a AC-057.3, AC-024.1 a AC-024.4, AC-025.1 passando
- [ ] RNF-01 a RNF-05 verificados
- [ ] Telemetria conferida
- [ ] ERR-01 a ERR-05 exercitados
- [ ] Acessibilidade dos erros de formulário
- [ ] EXP-01 registrado como entrada: as 2–3 regras do operador cabem nestes três controles, ou o mapa ganha história nova (sem esticar esta spec em silêncio)
- [ ] Leitura da métrica agendada para 3 semanas após configuração no piloto
