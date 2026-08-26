# SPEC-01 — Check-in na porta e liberação de no-show sem comando manual

| Campo | Valor |
|---|---|
| Fatia | FAT-04 |
| Rastreabilidade | OUT-01 › ACT-04 › STP-04.01 / STP-04.02 › US-031, US-032, US-034 |
| Autor / Data | Revisão spec-driven / 2026-08-18 |
| Status | rascunho |
| Versão | 1.0 |

> As-is verificado no código: check-in autenticado existe no detalhe da reserva (US-030, POST); a URL de check-in não responde GET; `auto_release_no_shows` existe e só corre se alguém dispara o comando. Janela: 15 minutos antes do início até o fim da reserva. Check-in anônimo está fora de escopo.

## 1. Resultado esperado

- **Comportamento que muda:** na porta, o servidor autenticado entende se pode confirmar presença e confirma; quinze minutos após o início sem check-in, o horário volta a aparecer como livre sem um operador.
- **Resultado de negócio (OUT-01):** ocupação visível corresponde ao uso real.
- **Métrica de resultado e linha de base:** proporção de reservas que recebem check-in dentro da janela. Linha de base: `[A VALIDAR]` (hoje o check-in pela porta não é usável). Alvo da fatia `[HIPÓTESE]`: maioria das reservas presenciais do piloto em uma sala.
- **Métrica de guarda:** check-in de outra pessoa, fora da janela, ou de reserva já encerrada/cancelada/no-show não pode passar a “presente”. Slot de no-show reaparece como livre no máximo 1 minuto após o limiar.
- **Prazo de leitura:** 2 semanas após EXP-02 em uma sala com a URL na porta.

## 2. Contexto e usuários

- **Perfis afetados:** [servidor que reserva](../01-perfil-usuario.md) (usa); [colega na porta](../01-perfil-usuario.md) (é afetado); [administrador](../01-perfil-usuario.md) (vê o no-show no painel).
- **Cenário de uso:** corredor, celular, reunião começando; rede institucional; pressão social de gente atrás. Não é a mesa com o detalhe da reserva aberto.
- **Volume esperado:** `[HIPÓTESE]` dezenas de reservas/dia no órgão, 1 sala de piloto no EXP-02; picos no início da tarde.

## 3. Escopo

**Está incluído:**

- Página de check-in aberta pela URL da reserva (a mesma que um QR impresso apontaria).
- Exibição do estado: pode confirmar / ainda não / já passou / não é sua / já confirmada / cancelada / no-show / concluída.
- Confirmação autenticada na janela de 15 minutos antes do início até o fim.
- Recusa observável nos casos acima, com próximo passo.
- Liberação automática de no-show 15 minutos após o início sem check-in, sem ação de operador, de forma que outro servidor consiga reservar o horário.
- Continuação do check-in pelo detalhe da reserva (US-030), com as mesmas regras.

**NÃO está incluído (e por quê):**

- Gerar ou imprimir a imagem do QR no cadastro da sala — polimento; a URL estável basta para um adesivo operacional.
- Check-in anônimo — quebra auditoria de quem confirmou.
- Notificação lembrando o check-in — fora do PRD; se H-02 cair por esquecimento, volta como fatia própria.
- Sensor, catraca, tablet dedicado na porta.
- Mudar a duração da janela por espaço (fica o valor institucional único de 15 minutos).

## 4. Fluxo principal

1. O servidor chega à porta com a sessão já autenticada (ou autentica e volta para a mesma URL).
2. Abre a URL de check-in daquela reserva (via QR ou link).
3. Vê o nome do espaço, o horário e que está na janela; confirma presença.
4. Vê a confirmação de que a presença foi registrada; o status passa a indicar check-in feito.
5. Se ninguém confirma até 15 minutos após o início, o sistema marca no-show e o horário volta a aparecer livre na disponibilidade e no painel.

## 5. Fluxos alternativos e de erro

| ID | Situação | Comportamento esperado |
|---|---|---|
| ALT-01 | Usuário não autenticado | É levado ao login e, após autenticar, volta à página de check-in da mesma reserva |
| ALT-02 | Já fez check-in | Página informa que a presença já foi registrada; não há segundo botão de confirmar |
| ALT-03 | Check-in pelo detalhe da reserva (fluxo já existente) | Mesmas regras de janela, dono e estados; não há duas lógicas divergentes |
| ERR-01 | Reserva de outra pessoa | Presença não é registrada; mensagem diz que só o dono confirma; tentativa registrada na auditoria |
| ERR-02 | Fora da janela (cedo demais) | Presença não é registrada; mensagem informa a partir de quando será possível (15 minutos antes do início) |
| ERR-03 | Fora da janela (já passou o fim) ou reserva cancelada / no-show / concluída | Presença não é registrada; mensagem explica o estado atual; se for no-show, indica que o horário foi liberado |
| ERR-04 | Reserva inexistente | Página de não encontrado, sem vazar se o identificador existiu para outro usuário |
| ERR-05 | Falha ao persistir o check-in | Mensagem para tentar de novo; estado permanece o anterior; evento de falha registrado |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Só o dono da reserva autentica e confirma presença. |
| RN-02 | A janela vai de 15 minutos antes do início até o instante do fim (inclusive o limite inferior, exclusive depois do fim). Unidade: minutos. Fuso de cálculo: o mesmo já usado pelo sistema (hoje UTC no código — `[FATO]`); horários *exibidos* ao usuário devem estar no fuso de Brasília. |
| RN-03 | Check-in só a partir do estado confirmada. Demais estados não transitam para check-in. |
| RN-04 | Check-in é idempotente na interface: repetir na mesma reserva já com presença mostra sucesso já ocorrido, sem erro agressivo. |
| RN-05 | Se o estado continua confirmada e já se passaram 15 minutos do início, a reserva passa a no-show e deixa de ocupar o horário. |
| RN-06 | A liberação de no-show não exige que um administrador execute comando. O atraso máximo tolerado após o limiar é 1 minuto. |
| RN-07 | Reserva em check-in feito não vira no-show. |

## 7. Critérios de aceite

```gherkin
AC-031.1 — Confirmação na porta dentro da janela
  Dado que sou o dono de uma reserva confirmada para a Sala Focus
  E o horário atual está dentro dos 15 minutos antes do início até o fim
  E estou autenticado
  Quando abro a URL de check-in dessa reserva e confirmo presença
  Então vejo a confirmação de que a presença foi registrada
  E a reserva deixa de oferecer um novo check-in
  E o painel do admin, se a reserva cobre o instante atual, mostra a sala ocupada

AC-031.2 — Chegada sem sessão
  Dado que não estou autenticado
  E a reserva está na janela de check-in
  Quando abro a URL de check-in
  Então sou levado a autenticar
  Quando autentico com a conta dona da reserva
  Então volto à página de check-in da mesma reserva
  E posso confirmar presença

AC-032.1 — Ainda não é hora
  Dado que sou o dono de uma reserva confirmada
  E faltam mais de 15 minutos para o início
  Quando abro a URL de check-in
  Então a presença não pode ser confirmada
  E vejo a partir de quando poderei confirmar

AC-032.2 — Reserva de outra pessoa
  Dado que estou autenticado com uma conta que não é a dona
  Quando abro a URL de check-in de uma reserva alheia
  Então a presença não é registrada
  E vejo que só quem reservou pode confirmar
  E a tentativa fica na trilha de auditoria

AC-032.3 — Estado que não admite check-in
  Dado que a reserva está cancelada, no-show ou concluída
  Quando o dono abre a URL de check-in
  Então a presença não é registrada
  E o estado atual é explicado em português

AC-034.1 — No-show libera o horário
  Dado uma reserva confirmada cujo início foi há 16 minutos
  E ninguém fez check-in
  E nenhum administrador executou comando manual
  Quando outro servidor autenticado consulta a disponibilidade daquele espaço naquela data
  Então o intervalo da reserva aparece como livre
  E a reserva original aparece como no-show para o dono e para o admin

AC-034.2 — Check-in feito não vira no-show
  Dado que a reserva já tem presença registrada
  E já se passaram 16 minutos do início
  Quando o sistema aplica a regra de no-show
  Então a reserva permanece com presença
  E o horário continua ocupado até o fim

AC-031.3 — Limite da janela
  Dado que o relógio está exatamente 15 minutos antes do início
  Quando o dono confirma presença
  Então a presença é registrada
  Dado que o relógio está depois do fim
  Quando o dono tenta confirmar
  Então a presença não é registrada
```

## 8. Requisitos não funcionais

| ID | Categoria | Requisito (com número) |
|---|---|---|
| RNF-01 | Desempenho | Página de check-in responde em até 2 s no p95 em 20 usuários simultâneos |
| RNF-02 | Segurança | Somente o dono autenticado confirma; identificador na URL não autoriza |
| RNF-03 | Privacidade | A página de check-in de reserva alheia não expõe nome do dono nem pauta |
| RNF-04 | Acessibilidade | Confirmação completa por teclado; botão com nome acessível “Confirmar presença”; contraste mínimo 4,5:1; foco visível |
| RNF-05 | Auditoria | Registro de check-in bem-sucedido (usuário, reserva, horário) e de tentativas recusadas (usuário, reserva, motivo), retido no mesmo prazo dos demais registros de reserva |
| RNF-06 | Disponibilidade | Atraso da liberação de no-show ≤ 1 minuto após o limiar, com o ambiente padrão de execução da aplicação (não um passo extra de operação) |

Seção de IA embutida: **não se aplica** — check-in e no-show são regras determinísticas.

## 9. Dados e contratos

**Entidades e campos**

| Entidade.Campo | Tipo | Obrigatório | Valores válidos | Origem | Visível para |
|---|---|---|---|---|---|
| Reserva.id | identificador | sim | existente | sistema | dono; staff vê na gestão |
| Reserva.estado | enum | sim | confirmada, check-in feito, cancelada, concluída, no-show | sistema | dono e staff |
| Reserva.inicio / Reserva.fim | data-hora | sim | fim > início | dono na criação | dono e staff |
| Reserva.presencaEm | data-hora | não | dentro da janela | sistema no check-in | dono e staff |
| CheckIn.janelaMinutos | inteiro | sim | 15 | configuração institucional | todos (texto na UI) |
| NoShow.limiarMinutos | inteiro | sim | 15 | configuração institucional | staff (explicação no painel) |

**Estados e transições permitidas (esta fatia)**

| De | Para | Condição | Quem pode |
|---|---|---|---|
| confirmada | check-in feito | dono autenticado, dentro da janela | dono |
| confirmada | no-show | 15 min após o início, sem presença | sistema |
| check-in feito | no-show | — | ninguém |

Transição não listada nesta tabela permanece como no as-is (cancelar, reagendar).

**Integrações**

| Sistema | Operação | Dados | Timeout | Repetição | Idempotência | O que o usuário vê |
|---|---|---|---|---|---|---|
| não se aplica | — | sem serviço externo no check-in | — | — | POST de check-in repetido não duplica presença | ALT-02 |

## 10. Telemetria

| Evento | Quando dispara | Propriedades | Serve para medir |
|---|---|---|---|
| checkin_pagina_aberta | GET da URL de check-in | reserva, autenticado sim/não, estado | denominador do funil na porta |
| checkin_confirmado | presença registrada | reserva, origem (porta / detalhe), atraso_minutos_relativo_ao_inicio | OUT-01; H-02 |
| checkin_recusado | tentativa inválida | reserva, motivo (janela / dono / estado) | guarda |
| noshow_liberado | transição para no-show | reserva, atraso_apos_limiar_segundos | US-034; guarda de 1 minuto |
| slot_livre_apos_noshow | primeira consulta de disponibilidade que já não ocupa aquele intervalo | espaço, intervalo | OUT-01 observável |

## 11. Riscos e hipóteses abertas

| ID | Descrição | Impacto se confirmado | Como resolver |
|---|---|---|---|
| H-02 | Na porta o servidor não autentica ou não aceita o rito | pilar no-show pune quem usou a sala e não fechou o ciclo | EXP-02; não abrir anônimo |
| R-01 | Relógio do servidor em UTC vs. expectativa em Brasília | janela “errada” na cabeça do usuário | exibir horário de Brasília; testes de limite com relógio controlado |
| R-02 | URL na porta com id de reserva fixo: o adesivo fica obsoleto a cada reunião | QR “da sala” não pode ser um id de reserva | `[HIPÓTESE]` operacional: o adesivo aponta para a reserva do dia via processo do admin, ou a próxima fatia cria URL por espaço. **Esta spec exige URL por reserva**, como o PRD já descreveu; QR genérico por sala fica explícito fora. |

## 12. Restrições de implementação (quando a spec alimenta um agente)

- **Stack e versões:** Django templates + HTMX; reutilizar `check_in_reservation` e `auto_release_no_shows` em `reservations/services.py` (`CHECK_IN_WINDOW_MINUTES = 15`, `DEFAULT_NO_SHOW_THRESHOLD_MINUTES = 15`).
- **Padrões / caminhos:** `ReservationCheckInView` hoje só implementa POST em `reservations/views.py`; rota `reservations/<int:pk>/check-in/` em `config/urls.py`. Painel: `admin_dashboard/views.py`. Testes em `reservations/tests.py`.
- **Fora de limites:** não introduzir check-in sem login; não adicionar Celery só por preferência se o agendamento puder viver no compose/`make up` de forma observável; não gerar PNG de QR nesta fatia.
- **Comandos de verificação:** `make test` (ou `uv run pytest`); `make lint`; cobertura ≥ 80%.
- **Ordem sugerida:** (1) GET da página com estados e mensagens; (2) POST já existente alinhado às mesmas mensagens em pt-BR; (3) auditoria das recusas; (4) liberação de no-show disparada pelo ambiente padrão, com teste de que 16 minutos depois o slot está livre sem chamar o comando na mão; (5) telemetria; (6) EXP-02.

## 13. Definição de pronto

- [ ] AC-031.1 a AC-031.3, AC-032.1 a AC-032.3, AC-034.1 e AC-034.2 passando
- [ ] RNF-01 a RNF-06 verificados
- [ ] Eventos de telemetria conferidos em homologação
- [ ] ERR-01 a ERR-05 exercitados
- [ ] Acessibilidade da página de check-in por teclado
- [ ] README de jornadas deixa de prometer página GET que não existe
- [ ] EXP-02 pode ser executado em uma porta real com a URL
- [ ] Leitura da métrica de resultado agendada para 2 semanas após o piloto
