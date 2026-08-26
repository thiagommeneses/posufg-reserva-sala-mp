# Plano de Fatias — Reserva de Espaços (MP-GO)

Ordem por aprendizado e risco, não por facilidade de construção. FAT-01 a FAT-03 já estão no ar; o plano registra o que já entregou e o que vem agora.

## Visão geral

| Fatia | Resultado entregue | OUT | Aprendizado buscado | Histórias | Status |
|---|---|---|---|---|---|
| FAT-01 | Servidor reserva e o calendário passa a ser a fonte da verdade | OUT-02 | H-01 | US-001, US-002, US-004, US-010 a US-014, US-020 a US-023, US-030, US-040 a US-042 | entregue (US-021 em aberto) |
| FAT-02 | Admin vê ocupação ao vivo e bloqueia manutenção | OUT-03 | Painel substitui a planilha no “agora” | US-003, US-050 a US-055, US-058 | entregue |
| FAT-03 | Consulente pergunta e lê resposta com fonte, ou a recusa honesta | OUT-04 | H-04 | US-060 a US-063 | entregue |
| FAT-04 | Quem chega na porta confirma presença; no-show libera a sala | OUT-01 | H-02 | US-031, US-032, US-033 (pronta), US-034 | próxima |
| FAT-05 | Admin impõe duração e quem reserva o quê | OUT-03 | H-03 | US-024, US-025, US-057 | próxima |
| FAT-06 | Reserva encerrada vira histórico; ocupação para de mentir no tempo | OUT-01 | H-06 | US-035 | próxima |
| FAT-07 | Admin desfaz conflito reagendando terceiros | OUT-03 | H-05 | US-056 | próxima |

## FAT-01 — Servidor reserva e o calendário passa a ser a fonte da verdade

- **Quem consegue fazer o que de novo:** entrar, achar sala por atributo ou frase, ver disponibilidade, reservar na hora, cancelar e reagendar o que é seu, fazer check-in autenticado na página da reserva.
- **Por que esta fatia primeiro:** é o esqueleto ambulante. Sem isso não há o que medir em H-01.
- **Esqueleto ambulante:** sim.
- **Histórias incluídas:** ver tabela. Dívida restante: US-021 (formulário de nova reserva sem sala selecionada).
- **Explicitamente adiado nesta fatia:** QR na porta, políticas, conclusão automática, override de reagendamento admin, assistente.
- **Como mediremos:** tempo até confirmar a reserva; se o servidor ainda liga para o setor (EXP-01). Guarda: taxa de overlap rejeitado visível (o calendário único não pode silenciar conflito).
- **Hipóteses que esta fatia testa:** H-01.
- **Dependências e riscos:** adoção paralela da planilha mata H-01 mesmo com o fluxo perfeito.
- **Specs derivadas:** nenhuma nova — as-is. US-021 pode ser correção pontual sem spec própria.

## FAT-02 — Admin vê ocupação ao vivo e bloqueia manutenção

- **Quem consegue fazer o que de novo:** staff vê o inventário agora, cadastra sala, bloqueia manutenção, cancela reserva de terceiro, gere usuários.
- **Por que nesta ordem:** sem o calendário do servidor, o painel mostraria vazio. Já entregue em paralelo ao esqueleto.
- **Esqueleto ambulante:** não.
- **Como mediremos:** ajustes feitos no painel versus telefone/planilha (OUT-03) — `[A VALIDAR]`.
- **Specs derivadas:** nenhuma nova.

## FAT-03 — Consulente pergunta e lê resposta com fonte

- **Quem consegue fazer o que de novo:** perguntar em português sobre normas de outras instituições, ver fonte e recusa quando o corpus não cobre.
- **Por que não ganha spec nova:** H-04 é risco de confiança, não o pilar Pareto incompleto. EXP-03 roda em paralelo. Evolução só se EXP-03 refutar o comportamento atual.
- **Como mediremos:** EXP-03 (amostragem humana). Guarda já no código: não chama o modelo sem contexto recuperado.
- **Specs derivadas:** nenhuma nesta leva.

## FAT-04 — Quem chega na porta confirma presença; no-show libera a sala

- **Quem consegue fazer o que de novo:** na porta, autenticado, vê se pode confirmar e confirma; quinze minutos após o início sem presença, o horário volta a ficar livre sem um operador rodar comando.
- **Por que esta fatia agora:** é o terceiro pilar do Pareto que o PO declarou e o código não fecha (GET de check-in inexistente; `release_no_shows` é manual). Testa H-02, a hipótese de usabilidade mais cara.
- **Esqueleto ambulante:** não — mas é a fatia que completa o resultado OUT-01 do esqueleto.
- **Histórias incluídas:** US-031, US-032, US-034. US-033 (regra dos 15 minutos) já existe no service.
- **Explicitamente adiado nesta fatia:** geração visual do QR no cadastro da sala; check-in anônimo; sensor de presença; notificação lembrando o check-in.
- **Como mediremos:** % de reservas que recebem check-in dentro da janela; tempo até o slot reaparecer como livre após o limiar de no-show. Guarda: check-ins recusados por janela/dono não podem virar presença. Tarefa de guerrilha: EXP-02.
- **Hipóteses que esta fatia testa:** H-02.
- **Dependências e riscos:** autenticação na porta (rede, senha, sessão). Se EXP-02 refutar por login, não “abrir” anônimo — redesenhar o caminho autenticado.
- **Specs derivadas:** [SPEC-01](specs/06-spec-01-checkin-na-porta.md).

## FAT-05 — Admin impõe duração e quem reserva o quê

- **Quem consegue fazer o que de novo:** gravar duração máxima, antecedência e elegibilidade por espaço; o servidor vê a recusa no formulário, não no telefone.
- **Por que depois de FAT-04:** H-03 é o conflito agilidade vs controle. Só vale endurecer regra depois de o calendário ser confiável — senão a política vira mais um motivo para voltar à planilha.
- **Como mediremos:** % de tentativas bloqueadas pela política que não geram contato com o admin (proxy: tickets/ligações — `[A VALIDAR]`). Guarda: reserva instantânea do caso comum (usuário elegível, duração ok) continua sem aprovação.
- **Hipóteses:** H-03 (EXP-01).
- **Dependências:** EXP-01 deve listar as 2–3 regras que o operador já aplica de cabeça; a spec parte delas, não de um motor genérico.
- **Specs derivadas:** [SPEC-02](specs/06-spec-02-politicas-de-uso.md).

## FAT-06 — Reserva encerrada vira histórico

- **Quem consegue fazer o que de novo:** depois do horário, quem fez check-in vê a reserva em Passadas como concluída; o status deixa de sugerir que a sala ainda está em uso; cancelar/reagendar essa reserva deixa de estar disponível.
- **Por que nesta ordem:** o dashboard já filtra ocupação “agora” por intervalo de tempo, então a mentira é mais de estado e de ação indevida do que de card vermelho. Fecha OUT-01 no tempo. Vem depois do check-in na porta porque sem presença real o `completed` não significa “usou”.
- **Como mediremos:** zero reservas `checked_in` com fim no passado após o job de conclusão; zero cancelamentos/reagendamentos de reserva já encerrada. Guarda: reserva ainda dentro do horário não pode ser marcada concluída.
- **Hipóteses:** H-06.
- **Specs derivadas:** [SPEC-03](specs/06-spec-03-conclusao-automatica.md).

## FAT-07 — Admin desfaz conflito reagendando terceiros

- **Quem consegue fazer o que de novo:** staff move o horário de outra pessoa, com os mesmos guards de overlap, e a trilha mostra quem alterou.
- **Por que por último:** é exceção operacional. Cancelar (US-055) já existe. Só investimos em reagendar terceiro se EXP-01 mostrar que “derrubar e mandar refazer” gera telefone de volta.
- **Como mediremos:** conflitos resolvidos por reagendamento vs cancelamento; reclamações de “sumiu minha reserva” após override.
- **Hipóteses:** H-05.
- **Specs derivadas:** [SPEC-04](specs/06-spec-04-admin-resolve-conflito.md).

## Critérios de corte

Se o prazo apertar, sai nesta ordem, decidido agora:

1. FAT-07 inteira — o admin já cancela; piora o conflito, não quebra OUT-01.
2. Elegibilidade por perfil em FAT-05 (US-025) — mantém só duração e antecedência, que o PO cita com mais frequência.
3. Geração/impressão operacional do QR (já fora da spec de produto) — a URL da página basta.
4. Nunca cortar US-032 (recusa clara de check-in) nem US-034 (liberação sem comando manual): sem eles FAT-04 ensina o usuário a não confiar no calendário.
5. Nunca cortar a trilha de quem reagendou terceiro se FAT-07 entrar: override sem auditoria é inaceitável no domínio institucional.

## Registro de mudanças do plano

| Data | Mudança | Motivo (aprendizado) |
|---|---|---|
| 2026-08-18 | Mapa as-is criado; FAT-01–03 marcadas entregues; FAT-04–07 especificadas | Revisão spec-driven do produto existente; sem pesquisa de campo nova |
