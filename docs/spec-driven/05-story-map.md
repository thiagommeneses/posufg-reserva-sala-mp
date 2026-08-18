# Story Map — Reserva de Espaços (MP-GO)

Versão 1.0 · atualizado em 2026-08-18

## Resultados

| ID | Resultado | Métrica |
|---|---|---|
| OUT-01 | A ocupação visível no calendário corresponde ao uso real da sala | Taxa de reservas que terminam em check-in ou no-show liberado, versus confirmed/checked_in que já passaram do horário (linha de base: [A VALIDAR] — não medida) |
| OUT-02 | Servidor encontra e reserva o espaço adequado sem aprovação e sem telefone | Tempo entre abrir a listagem e confirmar a reserva; % de reservas sem contato com o setor (linha de base: [A VALIDAR]) |
| OUT-03 | Admin opera inventário, manutenção e conflito sem planilha paralela | Número de ajustes feitos no painel versus fora do sistema (telefone/planilha) (linha de base: [A VALIDAR]) |
| OUT-04 | Consulente obtém resposta comparativa ancorada em norma de outra instituição, sem parecer norma do MP-GO | % de respostas com fonte visível e recusa quando não há contexto (linha de base do código: recusa já implementada; qualidade percebida [A VALIDAR] EXP-03) |

## Espinha dorsal

| ACT-01 Entrar no sistema | ACT-02 Descobrir o espaço | ACT-03 Reservar | ACT-04 Usar o espaço | ACT-05 Gerir a própria reserva | ACT-06 Operar o inventário | ACT-07 Consultar normas |
|---|---|---|---|---|---|---|
| STP-01.01 Identificar-se | STP-02.01 Buscar por necessidade, não por nome | STP-03.01 Escolher o horário | STP-04.01 Confirmar presença | STP-05.01 Ver o que é meu | STP-06.01 Ver o que está acontecendo agora | STP-07.01 Perguntar em linguagem natural |
| STP-01.02 Encontrar o ponto de partida | STP-02.02 Ver se o horário está livre de verdade | STP-03.02 Confirmar na hora | STP-04.02 Liberar quem não veio | STP-05.02 Desistir ou mudar sozinho | STP-06.02 Manter o cadastro das salas | STP-07.02 Conferir a origem |
|  |  |  | STP-04.03 Encerrar o uso no horário |  | STP-06.03 Bloquear para manutenção |  |
|  |  |  |  |  | STP-06.04 Resolver conflito |  |
|  |  |  |  |  | STP-06.05 Definir as regras do jogo |  |
|  |  |  |  |  | STP-06.06 Controlar quem acessa |  |

## Fatias

### FAT-01 — Servidor reserva e o calendário passa a ser a fonte da verdade *(esqueleto ambulante)*

- Resultado: OUT-02
- Aprendizado buscado: H-01 — o canal formal substitui planilha e telefone no caso comum

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-01 | STP-01.01 | US-001 Criar conta de servidor comum | pronta |
| ACT-01 | STP-01.01 | US-002 Entrar com usuário e senha | pronta |
| ACT-01 | STP-01.02 | US-004 Listagem de espaços como tela inicial | pronta |
| ACT-02 | STP-02.01 | US-010 Filtrar por capacidade, localização e equipamentos | pronta |
| ACT-02 | STP-02.01 | US-011 Buscar a sala em linguagem natural | pronta |
| ACT-02 | STP-02.01 | US-012 Esconder espaços inativos da busca | pronta |
| ACT-02 | STP-02.02 | US-013 Grade de horários por data | pronta |
| ACT-02 | STP-02.02 | US-014 Distinguir reserva de bloqueio de manutenção | pronta |
| ACT-03 | STP-03.01 | US-020 Partir do slot livre para a confirmação | pronta |
| ACT-03 | STP-03.01 | US-021 Escolher o espaço quando a nova reserva abre sem sala | descoberta |
| ACT-03 | STP-03.02 | US-022 Reserva instantânea sem aprovação | pronta |
| ACT-03 | STP-03.02 | US-023 Recusar overlap com outra reserva ou manutenção | pronta |
| ACT-04 | STP-04.01 | US-030 Check-in pelo detalhe da reserva já autenticado | pronta |
| ACT-05 | STP-05.01 | US-040 Abas de ativas, passadas e canceladas | pronta |
| ACT-05 | STP-05.02 | US-041 Cancelar a própria reserva | pronta |
| ACT-05 | STP-05.02 | US-042 Reagendar a própria reserva sem overlap | pronta |

### FAT-02 — Admin vê ocupação ao vivo e bloqueia manutenção

- Resultado: OUT-03
- Aprendizado buscado: O painel substitui a planilha para ver o agora e impedir reserva em horário de limpeza

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-01 | STP-01.01 | US-003 Staff cai no painel após o login | pronta |
| ACT-06 | STP-06.01 | US-050 Painel de ocupação ao vivo | pronta |
| ACT-06 | STP-06.02 | US-051 Cadastrar e editar espaço com atributos | pronta |
| ACT-06 | STP-06.02 | US-052 Ativar ou desativar espaço sem apagar o histórico | pronta |
| ACT-06 | STP-06.03 | US-053 Criar bloqueio de limpeza ou conserto | pronta |
| ACT-06 | STP-06.03 | US-054 Sugerir categoria do motivo via IA | pronta |
| ACT-06 | STP-06.04 | US-055 Cancelar reserva de qualquer pessoa | pronta |
| ACT-06 | STP-06.06 | US-058 Criar, editar, promover e remover usuários | pronta |

### FAT-03 — Servidor consulta norma comparativa com citação de fonte

- Resultado: OUT-04
- Aprendizado buscado: H-04 — resposta sem fonte é pior do que não ter assistente

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-07 | STP-07.01 | US-060 Perguntar e receber resposta com fontes | pronta |
| ACT-07 | STP-07.01 | US-061 Recusar quando não há trecho recuperado | pronta |
| ACT-07 | STP-07.01 | US-062 Continuar a conversa com o histórico recente | pronta |
| ACT-07 | STP-07.02 | US-063 Expandir o excerto e abrir o documento original | pronta |

### FAT-04 — Quem chega na porta confirma presença e o no-show libera a sala

- Resultado: OUT-01
- Aprendizado buscado: H-02 — check-in na hora H acontece; o terceiro pilar Pareto deixa de ser incompleto

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-04 | STP-04.01 | US-031 Check-in pela URL da porta com página que explica o estado | descoberta |
| ACT-04 | STP-04.01 | US-032 Recusar check-in fora da janela ou de outra pessoa | descoberta |
| ACT-04 | STP-04.02 | US-033 No-show 15 minutos após o início sem check-in | pronta |
| ACT-04 | STP-04.02 | US-034 Liberação de no-show sem depender de alguém rodar o comando | descoberta |

### FAT-05 — Admin impõe duração e quem reserva o quê sem planilha paralela

- Resultado: OUT-03
- Aprendizado buscado: H-03 — política operacional funciona mesmo sem norma formal consolidada

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-03 | STP-03.02 | US-024 Respeitar duração máxima e antecedência | descoberta |
| ACT-03 | STP-03.02 | US-025 Só quem pode reservar aquele espaço consegue confirmar | descoberta |
| ACT-06 | STP-06.05 | US-057 Configurar duração, antecedência e quem reserva o quê | descoberta |

### FAT-06 — Reserva encerrada vira histórico e o calendário para de mentir depois do horário

- Resultado: OUT-01
- Aprendizado buscado: H-06 — checked_in após o fim do horário não pode continuar ocupando o slot

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-04 | STP-04.03 | US-035 Reserva com presença vira histórico depois do fim | descoberta |

### FAT-07 — Admin desfaz conflito reagendando terceiros, não só cancelando

- Resultado: OUT-03
- Aprendizado buscado: H-05 — cancelar e mandar refazer aumenta telefone; reagendar com trilha resolve

| Atividade | Passo | História | Estado |
|---|---|---|---|
| ACT-06 | STP-06.04 | US-056 Reagendar reserva de terceiro com trilha | descoberta |

## Hipóteses abertas

| ID | Hipótese | Risco | Experimento |
|---|---|---|---|
| H-01 | Servidores abandonam planilha e telefone e passam a tratar o calendário como fonte da verdade | alto | EXP-01 |
| H-02 | Na hora H o servidor consegue e aceita fazer check-in na porta, na janela de 15 minutos | alto | EXP-02 |
| H-03 | É possível gravar política operacional (duração, antecedência, elegibilidade) sem norma formal consolidada | alto | EXP-01 |
| H-04 | Resposta do assistente sem fonte visível, ou apresentada como norma do MP-GO, destrói mais confiança do que não ter assistente | medio | EXP-03 |
| H-05 | Admin precisa reagendar reserva de terceiro, não só cancelar, para resolver conflito sem gerar outro telefone | medio | - |
| H-06 | Reserva com check-in que já passou do horário, se continuar ativa, faz o calendário mentir | medio | - |

## Deliberadamente fora de escopo

- Pagamento in-app (PO: só faria sentido em modelo público pago)
- Notificações por e-mail ou push (PRD; pode voltar depois de FAT-04, senão o check-in depende de a pessoa lembrar sozinha)
- Autenticação social / OAuth
- Multi-tenancy (várias organizações no mesmo deploy)
- Integração com Google Calendar, Outlook ou ERP
- Hardware de presença (catraca, sensor) — QR impresso é o teto desta leva
- Frontend SPA separado
- Check-in anônimo na porta (quebra auditoria de quem confirmou)
- Assistente falando em nome do MP-GO ou gerando minuta oficial
- Políticas de aprovação manual para sala premium (adiado até H-03 ser medida; hoje a reserva é instantânea)
- Dark mode e geração visual do QR no cadastro da sala (polimento, não resultado)
