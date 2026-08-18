# Estratégia de UX — fundamentos operacionais

Base conceitual: Jaime Levy, *UX Strategy: Product Strategy Techniques for Devising Innovative Digital Solutions*. Este arquivo é uma síntese operacional para conduzir a fase 1, não um resumo do livro.

## Índice

1. Os quatro pilares
2. Proposta de valor e segmento de cliente
3. Pesquisa validada com usuários
4. Análise competitiva
5. Inovação de valor
6. Experimentos e MVP
7. Perguntas de condução
8. Saídas esperadas

## 1. Os quatro pilares

Estratégia de UX é o ponto onde quatro coisas se encontram. Se qualquer uma falta, o produto tende a falhar de um jeito previsível:

| Pilar | Pergunta que responde | Falha típica quando ausente |
|---|---|---|
| Estratégia de negócio | Como ganhamos e sustentamos vantagem? | Produto bonito que não se paga |
| Inovação de valor | Por que alguém trocaria o que usa hoje por isto? | Clone de concorrente, disputa por preço |
| Pesquisa validada com usuários | Quem é, e isso é problema real dele? | Solução para problema imaginário |
| Design de experiência | A execução é boa o bastante para converter? | Boa ideia que ninguém consegue usar |

Ao conduzir a fase 1, verifique explicitamente os quatro. É comum um time forte em dois deles achar que os outros dois "já estão resolvidos".

## 2. Proposta de valor e segmento de cliente

A proposta de valor é uma hipótese com duas metades acopladas: **quem** e **o quê**. Mudar uma muda a outra.

Formato de trabalho:

> Para **[segmento específico]** que **[situação/dor recorrente]**, o **[produto]** é um **[categoria]** que **[benefício principal]**. Diferente de **[alternativa atual]**, ele **[diferença que importa ao usuário]**.

Regras práticas:

- Segmento específico significa comportamento observável, não demografia. "Analista que fecha relatório mensal em planilha na virada do mês" é útil; "profissionais de 25 a 45 anos" não é.
- Se a proposta serve para todo mundo, ela não serve para o primeiro release. Escolha o segmento de maior dor e menor custo de acesso — é onde a validação acontece rápido.
- A alternativa atual sempre existe. Quando parece não existir, ela é "conviver com o problema", que é um concorrente forte e gratuito.

## 3. Pesquisa validada com usuários

Validada significa: você falou com pessoas do segmento e o que elas disseram e fizeram mudou (ou confirmou) algo em concreto.

Roteiro mínimo de entrevista de descoberta (30 minutos, 5 a 8 pessoas por segmento):

1. Peça para narrar a última vez que enfrentaram a situação. Passado concreto, nunca hipótese futura.
2. Investigue o processo real: ferramentas, atalhos, planilhas paralelas, quem mais participa.
3. Identifique o momento de maior atrito e quanto custa (tempo, retrabalho, risco, dinheiro).
4. Pergunte o que já tentaram e por que abandonaram — mostra disposição real de mudar.
5. Termine em pedido de indicação de mais alguém do mesmo perfil.

Cuidados que mudam o resultado:

- Não apresente sua solução no início. Isso contamina toda a entrevista.
- "Você usaria?" e "quanto pagaria?" produzem gentileza, não dados. Prefira "o que você usa hoje?" e "quanto isso te custou no mês passado?".
- Sinal de validação forte é a pessoa já ter gastado tempo, dinheiro ou gambiarra tentando resolver por conta própria.
- Anote verbatim curto e diferencie do que você interpretou. Interpretação vira `[HIPÓTESE]`.

## 4. Análise competitiva

O objetivo não é catalogar features, é entender como o valor é entregue hoje e onde há espaço.

Passos:

1. Liste concorrentes **diretos** (mesma solução, mesmo problema), **indiretos** (solução diferente, mesmo problema) e **substitutos improvisados** (planilha, WhatsApp, e-mail, estagiário, papel).
2. Para cada um: proposta de valor declarada, segmento atendido, modelo de receita, como o usuário chega até ele, ponto forte e ponto fraco percebido pelo usuário — não por você.
3. Use o produto de verdade quando possível. Faça o fluxo principal do começo ao fim e registre onde travou.
4. Leia avaliações e reclamações públicas: elas apontam o que o mercado tolera mal.
5. Monte a matriz comparativa por **atributos que o usuário valoriza** (tempo até resultado, esforço de configuração, confiança, custo), não por checklist de funcionalidades.

Leitura da matriz: procure atributo em que todos são igualmente medíocres — costuma ser onde está a oportunidade, porque virou padrão de categoria que ninguém questiona.

## 5. Inovação de valor

Inovação de valor acontece quando você aumenta algo que a categoria trata como caro e elimina algo que ela trata como obrigatório. Três movimentos para testar em conjunto:

- **Eliminar**: o que a categoria faz por hábito e o usuário não valoriza?
- **Reduzir drasticamente**: onde há excesso que só serve para comparação de feature?
- **Elevar / criar**: qual atributo, se fosse dez vezes melhor, mudaria a escolha do usuário?

Escreva a resposta em uma frase testável. Se a resposta for "somos mais fáceis de usar", ainda não há inovação de valor — há intenção.

## 6. Experimentos e MVP

MVP aqui significa o menor artefato que gera aprendizado válido, não a versão 1.0 encolhida.

Escolha o formato pelo risco que precisa atacar:

| Risco dominante | Experimento adequado | Sinal de validação |
|---|---|---|
| Valor (querem?) | Landing com chamada clara, entrevista com protótipo, pré-venda | Ação custosa: cadastro qualificado, agendamento, pagamento |
| Usabilidade (conseguem?) | Protótipo clicável com tarefa, teste de guerrilha | Conclui a tarefa sem ajuda, no tempo esperado |
| Viabilidade (dá pra fazer?) | Spike técnico, protótipo de integração | Caminho técnico com custo conhecido |
| Negócio (compensa?) | Modelo de unidade econômica, teste de preço | Margem plausível com custo de aquisição real |

Regras:

- Defina o critério de falha **antes** de rodar. Sem isso, todo resultado vira confirmação.
- Um experimento por hipótese. Experimento que testa três coisas não conclui nenhuma.
- Prefira o mais barato que ainda responde. Fidelidade alta cedo compra confiança falsa.
- Registre o resultado mesmo quando refuta — especialmente quando refuta. Template: `templates/03-experimento-validacao.md`.

## 7. Perguntas de condução

Quando faltar informação, priorize nesta ordem (as primeiras destravam as demais):

1. Que resultado de negócio muda se isso funcionar, e como ele é medido hoje?
2. Quem exatamente sente a dor, e com que frequência?
3. O que essas pessoas fazem hoje para resolver?
4. Quem decide a adoção e quem paga — são a mesma pessoa que usa?
5. Qual restrição inegociável existe (prazo, orçamento, regulação, sistema legado)?

Sem resposta, registre como hipótese com ID `H-xx` e siga.

## 8. Saídas esperadas

Ao final da fase 1: `templates/00-discovery-brief.md` preenchido, um `templates/01-perfil-usuario.md` por segmento, `templates/02-analise-competitiva.md` e os experimentos definidos ou executados. Toda afirmação marcada como `[FATO]`, `[HIPÓTESE]` ou `[A VALIDAR]`.
