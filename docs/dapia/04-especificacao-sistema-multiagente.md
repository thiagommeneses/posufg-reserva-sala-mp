# Documento de Especificação: Sistema Multiagente (MAS)

**Disciplina:** Desenvolvimento Ágil para Projetos de Inteligência Artificial — UFG
**Squad / Projeto:** Reserva de Espaços (MP-GO) — camada multiagente
**Integrantes:** André Pereira Teles, Thiago Marques Meneses e Marco Antônio dos Santos Silva
**Data:** 31/08/2026

> As seções 1 a 4 estão completas. O *Log de Iteração* e as *Métricas de Sucesso* ficam em
> branco de propósito: o próprio template manda preenchê-los durante os testes, e registrar
> ali um comportamento que ainda não foi observado tornaria o log inútil.

---

## 1. Escopo do Projeto & Fatiamento Ágil (Sprints 1 & 2)

### 1.1 Visão do Produto (Elevator Pitch)

- Nossa solução multiagente serve para ajudar **servidores do MP-GO que precisam de uma sala e o administrador que hoje decide cada exceção por telefone**.
- A resolver o problema de **não existir norma escrita de uso de espaços: a regra é oral, muda de departamento para departamento, e por isso todo caso fora do trivial depende de alguém atender o telefone**.
- Ao contrário de soluções tradicionais monolíticas, nós usamos agentes especialistas para **separar três decisões que hoje se misturam na cabeça de uma pessoa: interpretar o pedido, fundamentar a resposta na norma e alocar o espaço**. Assim toda resposta vem com a fonte citada, e o que a norma não cobre é escalado ao humano em vez de decidido no escuro.

### 1.2 Critérios de Aceitação do MVP (Definition of Done)

**Input do Usuário:** pedido em linguagem natural, digitado pelo servidor autenticado.
Exemplo: *"preciso de uma sala para 12 pessoas com TV, quinta de manhã, por duas horas"*.

**Output Final Esperado:** uma decisão fundamentada, em uma de três formas:

- reserva confirmada, com espaço, horário e justificativa;
- até três alternativas de espaço ou horário, quando o pedido original não couber;
- escalação ao administrador, quando nenhuma norma ou política cobrir o caso.

Em qualquer uma delas, o parecer normativo aparece com o trecho e a fonte que o sustentam —
ou com a declaração explícita de que não há norma aplicável.

**Condições verificáveis ao fim da iteração:**

1. Os dez pedidos do conjunto de teste produzem critérios estruturados corretos (capacidade, equipamentos, data, início e duração).
2. Nenhuma resposta afirma regra sem trecho citado; a ausência de norma é declarada, não preenchida por suposição.
3. Reserva criada pelo agente nunca se sobrepõe a outra ativa — verificado pela restrição de exclusão do banco.
4. Todo caso escalado chega ao administrador com o pedido original, os critérios extraídos e as fontes consultadas.
5. O fluxo roda de ponta a ponta sem intervenção manual entre agentes.
6. Falha de qualquer agente devolve mensagem clara ao usuário e não deixa reserva parcial no banco.

---

## 2. Backlog de Agentes (Personas e Papéis)

### Agente 1 — Intérprete de Solicitação

- **Função (Role):** analista de pedidos de espaço.
- **Objetivo (Goal):** transformar um pedido em texto livre em critérios estruturados e completos — ou identificar exatamente o que falta perguntar.
- **Contexto (Backstory) — rascunho do prompt de sistema:**

> Você é um servidor experiente da administração de espaços do MP-GO. Recebe pedidos escritos
> por colegas apressados, em linguagem informal, e sua única tarefa é convertê-los em critérios
> objetivos: capacidade mínima, equipamentos necessários, data, horário de início e duração.
> Você não decide se o pedido pode ser atendido, não consulta disponibilidade e não sugere
> salas — isso é de outros agentes. Quando faltar informação essencial, não invente: marque o
> campo como ausente e formule uma única pergunta objetiva. Use apenas equipamentos que
> constem no catálogo. Responda sempre no formato estruturado definido, sem texto adicional.

- **Limitações:** não acessa disponibilidade nem base normativa; não conversa com o usuário além de uma pergunta de esclarecimento.

### Agente 2 — Consultor Normativo

- **Função (Role):** parecerista de regras de uso de espaços.
- **Objetivo (Goal):** dizer se o pedido é admissível segundo as políticas cadastradas e a base normativa, sempre citando a fonte — e declarar quando não existe regra aplicável.
- **Contexto (Backstory) — rascunho do prompt de sistema:**

> Você é assessor jurídico de um órgão de controle. Emite parecer sobre pedidos de uso de
> espaços com base em dois insumos: as políticas cadastradas pelo administrador e um corpus de
> regulamentos publicados por outras instituições públicas. Três regras invioláveis. Primeira:
> toda afirmação normativa vem acompanhada do trecho e da instituição de origem. Segunda: o
> MP-GO não possui norma própria sobre uso de espaços — você nunca apresenta regra de outra
> instituição, nem regra do produto, como se fosse norma do MP-GO. Terceira: quando nenhum
> trecho recuperado sustentar a resposta, escreva explicitamente que não há norma aplicável e
> recomende escalar ao administrador. Recusa honesta vale mais do que resposta confiante. Seja
> conciso: parecer em até cinco linhas, seguido das fontes.

- **Limitações:** não reserva nada e não decide alocação; apenas emite parecer.

### Agente 3 — Alocador de Espaço

- **Função (Role):** negociador de disponibilidade.
- **Objetivo (Goal):** dados os critérios e o parecer, confirmar a reserva, propor até três alternativas ou escalar ao administrador — registrando a decisão e o motivo.
- **Contexto (Backstory) — rascunho do prompt de sistema:**

> Você é o responsável pela alocação de espaços. Recebe critérios estruturados e um parecer
> normativo, e executa exatamente uma entre três ações: reservar, propor alternativas ou
> escalar. Nunca reserve quando o parecer for desfavorável. Nunca decida sozinho quando o
> parecer disser que não há norma aplicável — nesse caso escale ao administrador com todo o
> contexto. Ao propor alternativas, ofereça no máximo três, respeitando capacidade e
> equipamentos pedidos, ordenadas da mais próxima do pedido original para a mais distante.
> Registre toda ação com o motivo. Não invente disponibilidade: use apenas o que a ferramenta
> de consulta retornar.

- **Limitações:** não interpreta texto livre e não emite parecer normativo.

---

## 3. Mapeamento de Tarefas (Tasks) e Ferramentas (Tools)

### 3.1 Fluxo de tarefas sequenciais

1. **Tarefa 1 (Intérprete de Solicitação):** recebe o pedido em linguagem natural e gera os critérios estruturados — ou uma pergunta de esclarecimento.
2. **Tarefa 2 (Consultor Normativo):** recebe os critérios, consulta políticas e corpus, e gera o parecer — admissível, inadmissível ou sem norma aplicável — com as fontes.
3. **Tarefa 3 (Alocador de Espaço):** recebe critérios e parecer, consulta disponibilidade e entrega o resultado final — reserva confirmada, até três alternativas, ou escalação registrada.

Duas interrupções previstas: se a Tarefa 1 devolver pergunta de esclarecimento, o fluxo para e
retorna ao usuário; se a Tarefa 2 concluir que não há norma aplicável, a Tarefa 3 executa
apenas a escalação.

### 3.2 Caixa de ferramentas

- **Agente 1:** leitura do catálogo de atributos dos espaços (capacidades e equipamentos válidos). Somente leitura.
- **Agente 2:** busca híbrida na base normativa — semântica por embeddings combinada com busca lexical, sobre os 722 trechos indexados; leitura das políticas de uso cadastradas por espaço.
- **Agente 3:** consulta de disponibilidade e criação de reserva pelos serviços já existentes do sistema; registro da decisão na trilha de auditoria.

Os embeddings são gerados localmente; apenas a geração de texto depende de API externa.

---

## 4. Arquitetura de Orquestração

- **[X] Sequencial (Pipeline)** — linear, o output de um agente alimenta o próximo.
- [ ] Hierárquica (Manager) — um agente gerente dita o fluxo e valida entregas.
- [ ] Grafo / Rede (Stateful) — fluxo cíclico, agentes decidem o próximo passo por estado.

**Justificativa da escolha**

O fluxo do MVP é determinístico: interpretar, fundamentar, alocar. Cada etapa depende apenas
da saída da anterior e a ordem nunca muda — um agente gerente não teria decisão a tomar,
apenas repassaria tarefas em sequência fixa, gastando chamadas de modelo para nada.

Um grafo com estado resolveria casos que ainda não sabemos se existem, e cobraria por isso
desde a primeira iteração: condição de parada, persistência de estado e depuração muito mais
difícil quando algo der errado.

Escolher o pipeline agora é a decisão ágil — é a topologia mais simples que entrega o resultado
esperado, e o log de iteração é exatamente o instrumento que dirá se ela basta. Migraremos
para hierárquica se aparecer necessidade de replanejamento (por exemplo, o parecer exigir novo
levantamento de critérios), e para grafo se surgir negociação cíclica entre alocação e parecer.
Enquanto isso não for observado em teste, complexidade adicional é custo sem retorno.

---

## Log de Iteração & Feedback (Retrospectiva do Sistema)

A preencher durante a fase de testes e depuração.

| Rodada / Teste | Comportamento esperado | Comportamento real (erro observado) | Ajuste efetuado (prompt / tool / fluxo) |
|---|---|---|---|
| #01 | | | |
| #02 | | | |
| #03 | | | |
| #04 | | | |

## Métricas de Sucesso do Projeto

A medir na execução do sistema.

- Tempo médio de execução (latency): ________ segundos
- Custo / eficiência (tokens estimados): ( ) Baixo ( ) Médio ( ) Alto
- Aderência ao objetivo da atividade (nota de 1 a 5 do grupo para o output final): ________

---

## Por que estes três agentes

O Canvas de Declaração do Problema propôs cinco agentes: Presença, Conflito, Normativo,
Política e Orquestrador. O template limita o MVP a três, e a escolha seguiu um critério: o
documento pede um **Input do Usuário** e um **Output Final**, ou seja, um fluxo disparado por
uma pessoa.

- **Presença** ficou de fora porque não é disparado por usuário — roda em segundo plano, por agendamento. Entra na iteração seguinte.
- **Política** foi absorvido pelo Consultor Normativo: no MVP, política cadastrada e norma externa são dois insumos do mesmo parecer.
- **Conflito** foi absorvido pelo Alocador, que já propõe alternativas quando o pedido não cabe.
- **Orquestrador** não vira agente porque a topologia escolhida é sequencial: gastar um dos três slots com um gerente que só repassa tarefas em ordem fixa seria desperdício.
