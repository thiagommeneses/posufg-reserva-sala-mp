# Perfis de usuário — Reserva de Espaços (MP-GO)

> Quatro papéis distintos. Em contexto institucional eles quase nunca coincidem. Tudo que não veio da citação da servidora do MP-GO ou dos documentos do produto está marcado `[HIPÓTESE]`.

---

# A — Servidor que reserva

| Campo | Valor |
|---|---|
| Papel | usa |
| Baseado em | 1 citação de servidora MP-GO (README §1.1) + jornadas do PO `[HIPÓTESE]` no restante |
| Data | 2026-08-18 |

## Contexto de uso

`[HIPÓTESE]` No expediente, entre uma peça e outra, no computador da mesa ou no celular no corredor. Pressão de tempo: a reunião começa em 20 minutos ou precisa garantir sala para amanhã. Costuma agir sozinho; às vezes pede para o colega “ver se a Alfa está livre”.

## Objetivo real

Garantir um lugar adequado para reunir pessoas (capacidade, TV/projetor, silêncio), no horário combinado, sem gastar a manhã no telefone.

## Fluência

- **No domínio:** média — conhece as salas do próprio bloco, não o inventário inteiro.
- **Com tecnologia:** média — usa e-mail e sistemas internos; não quer aprender um “sistema de facilities”.

## Processo atual

1. Lembra de uma sala que já usou, ou pergunta no departamento quem controla a planilha.
2. Liga ou manda mensagem. `[FATO]` A regra do que fazer “quando terminar de usar a sala” chega por telefone, informal.
3. Se ninguém atende, olha a porta ou ocupa sala vazia.
4. Se a reserva formal existir em planilha de outro setor, só descobre o conflito na hora.

## Frustrações

- Não saber se a sala tem o equipamento que precisa sem ir até lá.
- Horário “reservado” e sala vazia; ou sala ocupada sem registro.
- Cada departamento com uma regra diferente, na cabeça de quem atende.

> `[FATO]` “Geralmente são instruções informais, repassadas pelo telefone.” — servidora do MP-GO.

## Restrições

Rede institucional; conta própria (não compartilhada na hipótese de registro); `[HIPÓTESE]` pode estar em dispositivo móvel na porta da sala na hora do check-in.

## Vocabulário próprio

sala, auditório, reunião, “está livre?”, reserva, “quem controla a Alfa”, check-in (termo do sistema — `[HIPÓTESE]` que não faz parte do vocabulário atual).

## Como o sucesso se parece para essa pessoa

Encontrou a sala certa, o horário está confirmado, chegou e usou. Ninguém do outro setor aparece reivindicando o mesmo espaço.

---

# B — Administrador de espaços

| Campo | Valor |
|---|---|
| Papel | usa |
| Baseado em | `requirements-po.md` e jornadas do painel `[HIPÓTESE]` (sem entrevista) |
| Data | 2026-08-18 |

## Contexto de uso

`[HIPÓTESE]` Mesa com várias abas; telefone tocando quando há conflito; início da manhã para ver o que está ocupado hoje. Desktop. Precisa de visão do inventário inteiro, não de uma sala.

## Objetivo real

Ocupação alta sem briga na porta. Saber o que está acontecendo agora. Conseguir bloquear limpeza/manutenção. Desfazer cedo o horário de quem não veio.

## Fluência

- **No domínio:** alta — conhece capacidade, restrições físicas, salas “nobres”.
- **Com tecnologia:** média — opera planilha com desenvoltura; rejeita ferramenta que aumente trabalho de mediação.

## Processo atual

1. Mantém planilha (ou várias, por departamento).
2. Atende pedido por telefone/e-mail e anota.
3. Quando há sobreposição, escolhe quem fica — muitas vezes por hierarquia informal.
4. Só descobre no-show quando alguém reclama que a sala está vazia ou ocupada indevidamente.

## Frustrações

- Não ver ocupação real.
- Ser o gargalo de todo cancelamento e toda “furada”.
- Não ter regra escrita para recusar pedido abusivo (duração, sala grande para duas pessoas).

## Restrições

Precisa de perfil staff. `[HIPÓTESE]` Não pode depender do Django Admin cru. Auditoria de override importa se a chefia questionar quem derrubou a reserva de quem.

## Vocabulário próprio

ocupação, bloqueio, manutenção, no-show, conflito, “derrubar reserva”, inventário, VIP / prioridade (PO menciona priorizar VIP — `[HIPÓTESE]` se isso é prática real).

## Como o sucesso se parece para essa pessoa

Olha o painel e confia. Bloqueia um horário de limpeza. Resolve um conflito sem planilha. Não passa o dia no telefone confirmando presença.

---

# C — Chefia / gestor de área

| Campo | Valor |
|---|---|
| Papel | decide (adoção e, no limite, orçamento/TI) |
| Baseado em | padrão de domínio institucional `[HIPÓTESE]` |
| Data | 2026-08-18 |

## Contexto de uso

Quase não opera o sistema. Vê o produto em demonstração ou quando um conflito chega na mesa.

## Objetivo real

Menos reclamação, menos desperdício de espaço, rastreabilidade se houver questionamento interno. Não quer virar dono de outra ferramenta.

## Fluência

- **No domínio:** alta em prioridade política das salas.
- **Com tecnologia:** variável.

## Processo atual

Recebe escalonamento (“a sala da reunião com o procurador estava ocupada”). Manda o setor “organizar isso”.

## Frustrações

Ferramenta que a equipe não usa; métrica que não consegue mostrar; risco reputacional de dado errado.

## Restrições

Ciclo de aprovação; identidade visual institucional; acessibilidade em sistema público; não apresentar o assistente RAG como “norma do MP-GO”.

## Vocabulário próprio

norma, circular, responsabilidade, auditoria, “isso está oficial?”.

## Como o sucesso se parece para essa pessoa

O setor para de ligar para a chefia por causa de sala. Se perguntarem quem autorizou o override, há registro.

---

# D — Colega que chega na sala (afetado)

| Campo | Valor |
|---|---|
| Papel | é afetado (pode não ter conta nem abrir o sistema) |
| Baseado em | shadow booking descrito pelo PO `[HIPÓTESE]` |
| Data | 2026-08-18 |

## Contexto de uso

Na porta, com gente atrás, reunião marcada. Não vai “entrar no sistema” para entender o conflito.

## Objetivo real

Usar a sala no horário combinado, ou saber rápido que precisa ir para outra.

## Fluência

Irrelevante para o software se o desenho não o inclui. O QR na porta é o único ponto de contato possível com o produto.

## Processo atual

Olha a porta, entra se estiver vazia, discute se alguém aparecer.

## Frustrações

Sala reservada e vazia; sala “livre” e ocupada; não saber para quem reclamar.

## Restrições

Sem login na hora, a menos que o check-in na porta peça autenticação — o que é exatamente o risco de H-02.

## Vocabulário próprio

“está ocupada?”, “de quem é a reserva?”.

## Como o sucesso se parece para essa pessoa

A porta e o calendário contam a mesma história. Se a reserva caducou, a sala está de fato disponível.

---

# E — Redator de norma / consulente do assistente

| Campo | Valor |
|---|---|
| Papel | usa (segmento secundário, OUT-04) |
| Baseado em | `data/normas/MANIFESTO.md` e README §1 `[FATO]` no propósito; persona `[HIPÓTESE]` |
| Data | 2026-08-18 |

## Contexto de uso

Escritório, desktop, tarefa pontual: “como outras instituições resolvem antecedência / uso por terceiros / vedações?”. Não é o fluxo diário de reservar sala.

## Objetivo real

Insumo comparativo para redigir norma própria ou responder dúvida operacional recorrente, com trecho e instituição de origem.

## Fluência

- **No domínio:** alta em texto normativo.
- **Com tecnologia:** média.

## Processo atual

Busca no Google por regulamentos de auditório; abre PDFs; copia trechos. `[FATO]` O MP-GO não tem documento formal para consultar.

## Frustrações

Resposta de modelo sem fonte; misturar instituições como se fossem a mesma regra; parecer que o assistente “fala em nome do MP-GO”.

## Restrições

A resposta deve recusar-se a inventar quando o corpus não cobre. O corpus é de outras instituições, não do MP-GO.

## Vocabulário próprio

regulamento, resolução, antecedência, cessão, vedação, penalidade, fonte.

## Como o sucesso se parece para essa pessoa

Pergunta em português, lê uma resposta curta, expande o excerto, abre o original. Sabe que aquilo é de outra instituição.
