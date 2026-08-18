# Análise Competitiva — Reserva de espaços em órgão público

> Atributos da matriz são os que o usuário valoriza no problema (confiança, tempo, esforço, controle), não checklist de features. Notas 1–5 são `[HIPÓTESE]` — nenhum concorrente foi usado de ponta a ponta nesta revisão.

## 1. Panorama

| Concorrente | Tipo | Segmento atendido | Proposta de valor declarada | Modelo de receita | Como o usuário chega |
|---|---|---|---|---|---|
| Planilha setorial + telefone | improviso (campeão atual) `[FATO]` | cada departamento do MP-GO | “a gente controla aqui” | custo de tempo de quem atende | já está no e-mail / ramal |
| Ocupar sala vazia (shadow booking) | improviso `[FATO]` descrito pelo PO | quem está no corredor | instantâneo, zero rito | conflito social | olhar a porta |
| Google Agenda / calendário de recurso | indireta `[HIPÓTESE]` | equipes que “donam” uma sala | convite já no e-mail | incluso no workspace | hábito de marcar reunião |
| Microsoft Bookings / Outlook room | indireta `[HIPÓTESE]` | órgãos em ecossistema Microsoft | sala no mesmo convite da reunião | licença institucional | TI já padronizou |
| Sistemas comerciais (Robin, Deskbee, etc.) | direta `[HIPÓTESE]` | empresas e alguns órgãos | app + sensor + analytics | assinatura | RFP / vendedor |
| Não fazer nada (remarcar na hora) | improviso | qualquer um no pico | evita o rito | reunião perdida | desistência |
| Reserva de Espaços (nós) | — | servidor MP-GO + admin de facilities | calendário único, autogestão, auto-release, filtros | custo interno / acadêmico | login institucional do próprio sistema |

## 2. Matriz por atributos que o usuário valoriza

Escala 1 (ruim) a 5 (excelente). `[HIPÓTESE]` em todas as notas. “Nós” descreve o produto **como está no código hoje**, não o alvo das próximas fatias.

| Atributo | Nós (hoje) | Planilha + telefone | Agenda setorial | Shadow booking | Comercial típico |
|---|---|---|---|---|---|
| Tempo até a primeira reserva | 4 | 2 | 4 | 5 | 3 (onboarding) |
| Confiança de que o horário está mesmo livre | 3 | 2 | 3 | 1 | 4 |
| Combate a no-show | 2 | 1 | 1 | 1 | 4 (sensor/QR) |
| Descoberta por capacidade/equipamento | 4 | 1 | 2 | 1 | 4 |
| Esforço do admin para manter o canal | 3 | 2 | 3 | 5 (zero, até o conflito) | 3 |
| Controle (política, override, auditoria) | 2 | 3 (informal, na cabeça) | 2 | 1 | 4 |
| Adoção sem treinar ninguém | 3 | 5 | 4 | 5 | 2 |
| Custo total percebido | 4 | 3 (tempo escondido) | 4 | 5 | 1 |

Leitura: o produto já compete em descoberta e reserva instantânea. É medíocre exatamente onde o PO colocou o terceiro pilar — presença real na porta — e onde o admin ainda não tem política. Shadow booking ganha em velocidade e perde em confiança; é o concorrente que o check-in na porta precisa vencer.

## 3. Uso direto do produto concorrente

| Concorrente | Fluxo testado | Onde travou | Observação |
|---|---|---|---|
| Planilha + telefone | não observado nesta revisão | — | `[A VALIDAR]` EXP-01 deve pedir a última vez que a pessoa reservou, com o canal real |
| Google Agenda recurso | não testado nesta revisão | — | `[A VALIDAR]` se a instituição já usa, H-01 fica mais cara |
| Comercial (Robin etc.) | não testado | — | não vale competir em sensor de presença nesta leva (PRD: hardware fora de escopo) |

## 4. Reclamações públicas recorrentes

| Fonte | Tema | Frequência percebida |
|---|---|---|
| Documentos do próprio produto (PO, README) | fragmentação, no-show, “cada departamento uma regra” | `[FATO]` como discurso interno; não é review de loja |
| Mercado de room booking (memória de categoria, não coleta) | check-in ignorado; sala “ocupada” no app e vazia no mundo; permissões rígidas demais | `[HIPÓTESE]` |

Não há coleta sistemática de reclamações de usuários do MP-GO além da citação única no README.

## 5. Conclusões

- **Padrão de categoria que ninguém questiona:** ter *algum* calendário. O que falta não é “mais uma tela de agenda”, é fazer o calendário ser mais confiável do que olhar a porta.
- **Atributo em que todos os improvisos são medíocres (oportunidade):** confiança no dado + liberação de no-show. É o OUT-01. O código já tem status e comando; a última milha (QR na porta + agendamento do release + conclusão automática) é onde a categoria informal não entra.
- **Onde não vale competir nesta leva:** sensores, pagamento, SSO/OAuth, SPA, analytics de IA (PRD Out of Scope). Também não vale o assistente RAG se apresentar como norma do MP-GO.
- **Implicação para a proposta de valor:** a frase de valor (“se não está no sistema, não existe”) só se sustenta depois de FAT-04 e FAT-06. Hoje um `checked_in` que já passou do horário continua ocupando o slot, e um GET em `/reservations/{id}/check-in/` não entrega a página que o QR promete.
