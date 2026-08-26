# Canvas de Declaração do Problema

**Disciplina:** Desenvolvimento Ágil para Projetos de Inteligência Artificial (DAPIA)
**Professor:** Prof. Dr. Eliomar Araújo de Lima
**Especialização em Sistemas e Agentes Inteligentes — Universidade Federal de Goiás**
**Equipe:** André Pereira Teles, Thiago Marques Meneses e Marco Antônio dos Santos Silva
**Entregável:** Sprint 0 — Semana 1 (Definição do Desafio e Planejamento)
**Data:** 23/08/2026

---

## Nota de método

Este canvas declara o problema do **Reserva de Espaços**, projeto contínuo da
especialização, no ponto em que ele está hoje. As disciplinas anteriores entregaram o
sistema de reserva e um assistente RAG sobre normas de uso de espaços. O problema
declarado aqui é o que **sobrou depois disso** — e é justamente o que um sistema
multiagente endereça.

Cada afirmação está marcada:

- `[FATO]` — verificado no código, medido no corpus indexado, ou dito por servidora do MP-GO.
- `[HIPÓTESE]` — inferência plausível do domínio, ainda não confirmada.
- `[A VALIDAR]` — número que precisa de medição em campo; experimento já definido.

Nenhum número deste canvas foi estimado sem origem declarada. Onde não há linha de base,
o canvas diz que não há — a ausência de medição é, ela mesma, parte do problema.

---

## TÍTULO DO PROBLEMA

**No MP-GO, toda decisão não trivial sobre uso de espaços depende de uma regra informal
que vive na cabeça de quem atende o telefone.**

---

## CONTEXTO / SITUAÇÃO ATUAL
*Quando o problema ocorre?*

Todo dia útil, no expediente, sempre que o pedido de sala **sai do caso simples**:

- duas solicitações legítimas para o mesmo espaço e horário;
- pedido de auditório ou espaço de maior porte;
- exceção de duração ou de antecedência;
- dúvida sobre o que fazer ao desocupar a sala. `[FATO]`

E ocorre também **depois** da reserva feita: no horário marcado, quando ninguém aparece e
o slot continua bloqueado.

O sistema Reserva de Espaços, entregue nas disciplinas anteriores, já resolve o caso
simples — descobrir por capacidade e equipamento, ver disponibilidade e reservar na hora,
sem telefone. `[FATO]` O caso **não trivial** continua saindo do sistema e voltando para o
telefone.

---

## PROBLEMA PRINCIPAL
*Qual é a causa-raiz do problema?*

**O MP-GO nunca consolidou uma norma de uso de espaços.** `[FATO]`

A regra existe — mas oral, fragmentada por departamento e não registrada:

> "As reservas são gerenciadas por vários departamentos distintos e cada um tem uma regra.
> Geralmente são instruções informais, repassadas pelo telefone sobre o que tem que fazer
> quando terminar de usar a sala. Mas nenhum documento formal consolidando isso."
> — servidora do MP-GO com atuação na área `[FATO]`

Sem critério escrito e verificável, **todo julgamento precisa de um humano no circuito**:
quem tem prioridade, o que é exceção aceitável, o que se exige ao desocupar.

Daí a causa-raiz ser mais funda do que "falta um sistema": software que apenas *registra*
reservas automatiza o registro, não o julgamento. Por isso a lacuna sobreviveu à
informatização — foi exatamente o que observamos ao entregar o produto e ver o telefone
continuar tocando para os casos de exceção.

---

## IMPACTO QUANTIFICÁVEL
*Qual é o impacto mensurável (incluir unidades)?*

**Medido** `[FATO]`

| Indicador | Valor | Unidade |
|---|---|---|
| Normas do MP-GO sobre uso de espaços localizadas no portal institucional | 0 | documentos |
| Normas equivalentes localizadas no TJGO | 0 | documentos |
| Instituições que já publicaram regulamento e serviram de corpus comparativo | 24 | instituições |
| Base normativa externa indexada | 25 docs / 722 trechos / 75.474 | documentos / trechos / palavras |
| Janela de check-in implementada no sistema | 15 | minutos |
| Tempo até o horário de um no-show voltar a ficar livre | indeterminado — a liberação só ocorre quando um operador executa o comando manualmente | — |

**Sem linha de base** `[A VALIDAR]` — nenhum destes é medido hoje pela instituição:

| Indicador | Unidade | Experimento |
|---|---|---|
| Taxa de no-show | % das reservas | EXP-02 |
| Tempo até concluir uma reserva pelo canal informal | minutos | EXP-01 |
| Contatos telefônicos por reserva | ligações / reserva | EXP-01 |
| Departamentos com regra própria distinta | departamentos | EXP-01 |

A ausência de medição é achado, não omissão: sem norma escrita, não há indicador definido
para acompanhar, e portanto não há como afirmar que o processo piorou ou melhorou.

---

## USUÁRIOS AFETADOS
*Quem sofre com o problema frequentemente?*

| Perfil | Como sofre | Frequência |
|---|---|---|
| Servidor que precisa de sala | não sabe se pode, nem se o horário será respeitado | diária `[HIPÓTESE]` |
| Operador que controla a planilha e atende o telefone | **é ele quem carrega a regra**; vira gargalo e ponto único de falha | diária `[FATO]` |
| Administrador de espaços (facilities) | decide conflito e exceção sem critério escrito para se apoiar | semanal `[HIPÓTESE]` |
| Colega que chega na sala | encontra a sala ocupada por quem não reservou, ou vazia e bloqueada | eventual `[FATO]` |
| Quem precisa redigir a norma / assessoria | não tem base comparativa nem histórico de decisões | pontual `[FATO]` |

---

## POSSÍVEIS CAUSAS
*De onde vêm as causas que colaboram para a definição do problema?*

1. **Ausência de ato normativo institucional** sobre uso e reserva de espaços. `[FATO]`
2. **Gestão distribuída por departamento**, sem coordenação nem padrão comum. `[FATO]`
3. **Transmissão oral da regra**, por telefone, sem registro nem versão. `[FATO]`
4. **Canais paralelos que não conversam**: planilha, e-mail, telefone, agenda física. `[FATO]`
5. **Ausência de verificação de presença física**: reservar não custa nada e faltar não tem consequência. `[FATO]`
6. **A automação existente ainda depende de operador**: a liberação de no-show é um comando que alguém precisa executar. `[FATO]`
7. **Conflito de expectativas** entre agilidade (servidor quer reserva instantânea) e controle (admin quer regra). `[HIPÓTESE]`

---

## ALTERNATIVAS
*O que os usuários afetados fazem hoje para contornar o problema?*

| Alternativa | Por que usam | Onde falha |
|---|---|---|
| Planilha setorial + ligação | é o processo atual `[FATO]` | dado divergente; regra na cabeça de quem atende |
| Perguntar a quem "controla" a sala | resposta rápida de quem sabe | conhecimento não transferível |
| Olhar a porta / ocupar sala vazia (*shadow booking*) | instantâneo, zero rito `[FATO]` | conflito quando o titular chega; destrói a confiança no canal formal |
| Agenda de recurso no e-mail | já está na ferramenta do dia a dia `[HIPÓTESE]` | não filtra equipamento, não combate no-show, não é fonte única |
| Desistir e remarcar presencialmente | evita o rito | reunião não acontece; deslocamento perdido |
| **Reserva de Espaços (nosso sistema)** | resolve o caso simples `[FATO]` | **a exceção volta ao telefone** |

---

## NECESSIDADES / EXPECTATIVAS
*Inquietações e o que é esperado pelos usuários afetados*

- **Servidor:** saber na hora se pode reservar daquele jeito, sem ligar — e que o horário confirmado seja de fato respeitado.
- **Operador / administrador:** parar de ser o repositório vivo da regra; manter controle (duração, antecedência, elegibilidade) sem virar gargalo de cada exceção.
- **Instituição:** critério verificável e **rastreável** — quem decidiu o quê, quando e com base em quê. Órgão de controle não pode operar decisão sem trilha.
- **Todos:** que a resposta **cite a fonte** quando ela existir e **admita** quando a norma não cobre o caso, em vez de inventar regra.

---

## IMPACTOS DO PROBLEMA
*Como o usuário se sente e quais as consequências diretas?*

**Como se sente**

- Refém do telefone e da disponibilidade de quem atende.
- Inseguro sobre "posso ou não posso" — a resposta muda conforme o departamento.
- Descrente do canal formal, o que empurra de volta para a planilha e o *shadow booking*.

**Consequências diretas**

- Sala bloqueada e vazia: desperdício de recurso público. `[FATO]`
- Conflito na porta entre dois ocupantes que se julgam legítimos. `[FATO]`
- Decisão sem rastro: não há como auditar por que uma reserva foi priorizada ou cancelada. `[FATO]`
- Conhecimento operacional concentrado em poucas pessoas — risco de continuidade quando saem de férias ou mudam de setor. `[HIPÓTESE]`
- Reforço do ciclo: quanto menos o canal formal é usado, menos confiável fica o dado nele. `[HIPÓTESE]`

---

## SOLUÇÃO DESEJADA
*Qual sistema ou componente é esperado para resolver o problema?*

Uma **camada multiagente sobre o Reserva de Espaços** que decida os casos não triviais e
escale ao humano apenas o que a regra não cobre — invertendo o padrão atual, em que o
humano decide tudo e o sistema só registra.

| Agente | Responsabilidade | Padrão agêntico |
|---|---|---|
| **Presença** | Acompanha a janela de 15 min, confirma o check-in na porta e libera o no-show sem comando humano | ferramentas |
| **Conflito** | Ao detectar sobreposição, propõe espaço ou horário equivalente em vez de simplesmente cancelar | planejamento |
| **Normativo** | Responde "posso reservar assim?" consultando o corpus de 25 regulamentos já indexado, citando a fonte e recusando quando não há base | reflexão |
| **Política** | Converte a regra oral do administrador em política verificável e registra a decisão para auditoria | ferramentas |
| **Orquestrador** | Decide o que resolve sozinho e o que escala, mantendo trilha da decisão | multiagentes |

**Reaproveitamento:** os agentes Normativo e Presença assentam sobre o que já existe — o
pipeline RAG (busca híbrida com *Reciprocal Rank Fusion* sobre 722 trechos) e os *services*
de check-in e liberação. A disciplina anterior entregou as ferramentas; esta entrega o
**julgamento** que as aciona.

**Frase testável:** *o servidor obtém uma decisão fundamentada sobre um caso de exceção em
menos de 3 minutos, sem telefone, com a fonte normativa visível ou com a escalação
explícita de que a norma não cobre o caso.*

**Guarda de projeto:** o sistema **não** pode apresentar regra do produto como se fosse
norma oficial do MP-GO. Onde não há norma, a resposta correta é dizer que não há e
escalar — recusa honesta vale mais do que resposta confiante, ainda mais em órgão de
controle.

---

## Referências internas

- `README.md` §1.1 a §1.3 — origem do problema, citação da servidora, composição do corpus.
- `docs/spec-driven/00-discovery-brief.md` — hipóteses H-01 a H-06 e restrições.
- `docs/spec-driven/03-experimento-validacao.md` — EXP-01 e EXP-02.
- `docs/spec-driven/08-plano-de-fatias.md` — FAT-04 a FAT-07, as lacunas que motivam a camada agêntica.
- `PRD.md` — três pilares Pareto e estados de reserva.
