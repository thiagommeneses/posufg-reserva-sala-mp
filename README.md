# Assistente de Consulta a Normas de Uso de Espaços

**Relatório Técnico — Trabalho Prático Final (Opção 2)**
Engenharia de Software para Modelos de IA
Especialização em Sistemas e Agentes Inteligentes — Universidade Federal de Goiás

**Equipe:** Thiago Marques Meneses e André Pereira Teles

**Repositório:** https://github.com/thiagommeneses/posufg-reserva-sala-mp

---

## Sumário

1. [Descrição do contexto dos documentos](#1-descrição-do-contexto-dos-documentos)
2. [Processo de preparação dos dados](#2-processo-de-preparação-dos-dados)
3. [Embeddings utilizados](#3-embeddings-utilizados)
4. [LLM utilizado](#4-llm-utilizado)
5. [Arquitetura da solução](#5-arquitetura-da-solução)
6. [Resultados](#6-resultados)
7. [Funcionalidades complementares](#7-funcionalidades-complementares)
8. [Limitações e trabalhos futuros](#8-limitações-e-trabalhos-futuros)

---

## 1. Descrição do contexto dos documentos

### 1.1 O problema

Este trabalho evolui o **Sistema de Reserva de Espaços**, projeto contínuo do curso,
desenvolvido a partir de um cenário real do Ministério Público de Goiás, onde a reserva
de salas é controlada manualmente em planilha.

Ao levantar a base documental, encontramos um dado que redirecionou o trabalho: **não
existe norma do MP-GO regulamentando o uso e a reserva de espaços físicos.** O portal
institucional publica Atos PGJ e resoluções do CSMP sobre outras matérias, mas nada sobre
salas e auditórios. A mesma busca no TJGO retornou apenas o Regimento Interno, sem
portaria específica.

A busca pública, sozinha, sustentaria apenas a afirmação mais fraca de que a norma não
está publicada. Para diferenciar ausência de evidência e evidência de ausência,
consultamos uma servidora do MP-GO com atuação na área. A resposta confirmou o quadro:

> "As reservas são gerenciadas por vários departamentos distintos e cada um tem uma regra.
> Geralmente são instruções informais, repassadas pelo telefone sobre o que tem que fazer
> quando terminar de usar a sala. Mas nenhum documento formal consolidando isso."

O achado é mais forte do que a ausência de um documento. O que existe é **regulação
informal e fragmentada**: cada departamento opera sua própria regra, transmitida
oralmente, sem registro. Isso significa que não há critério verificável para decidir quem
pode reservar, com que antecedência ou sob quais condições — e que o conhecimento
operacional depende de quem atende o telefone e controla a planilha de reservas.

É exatamente a lacuna que motiva este trabalho.

### 1.2 Por que um corpus multi-institucional

Diante disso, o corpus foi montado com regulamentos de instituições públicas que **já
normatizaram** o uso de seus espaços. A base serve a dois propósitos concretos:

1. **Apoiar a redação de uma norma própria**, permitindo comparar como diferentes órgãos
   resolveram as mesmas questões. Onde hoje há instrução informal por telefone, um
   regulamento escrito precisa decidir prazos, responsabilidades e vedações — e outras
   instituições públicas já enfrentaram essas mesmas decisões.
2. **Responder dúvidas operacionais recorrentes** — quem pode reservar, prazos, uso por
   terceiros, cobrança, vedações e penalidades.

Para a tarefa de RAG, a heterogeneidade é uma vantagem metodológica, não um defeito. Um
corpus de uma só instituição responderia por consulta simples ao documento. Um corpus
multi-institucional exige que o sistema **recupere e confronte trechos de fontes
distintas**, que é onde a recuperação semântica precisa demonstrar valor.

### 1.3 Composição do corpus

| Métrica | Valor |
|---|---|
| Fontes catalogadas | 27 |
| Documentos indexados | 25 |
| Instituições distintas | 24 |
| Palavras totais | 75.474 |
| Trechos indexados | 722 |
| Média de palavras por documento | 3.018 |
| Menor / maior documento | 150 / 28.653 palavras |
| Formatos | 22 PDF, 3 HTML |

**Distribuição por categoria:**

| Categoria | Documentos | Exemplos |
|---|---|---|
| Regulamento de auditório | 11 | UFPA/IFCH, UFS/BICEN, IFAL, IFBA, USP/IFSC, UFBA/IMS |
| Resolução institucional | 6 | UFFS 177/2025, UFPI CAD 192/2026, IFC 16/2017 |
| Procedimento de reserva | 2 | UFU/PREFE |
| Contexto jurídico | 3 | TCU, CNMP, TJGO |
| Complementar internacional | 3 | UNL, INFARMED, U. Lisboa/FMD |

O bloco de **contexto jurídico** merece nota. O Regimento Interno do TJGO tem baixa
densidade temática — 28.653 palavras com poucas menções diretas ao assunto —, mas contém
regras reais e específicas: o art. 55 atribui ao desembargador titular a competência de
definir escalas de uso do próprio gabinete, e há previsão de cedência das instalações da
EJUG para eventos externos. Em um índice segmentado isso não é problema: os trechos
relevantes são recuperáveis e os demais simplesmente nunca correspondem a consulta
alguma.

A procedência de cada documento está registrada em
[`data/normas/fontes.json`](data/normas/fontes.json) — instituição, título, categoria e
URL de origem —, o que torna toda afirmação do sistema rastreável até a fonte primária.

---

## 2. Processo de preparação dos dados

O pipeline tem quatro etapas, todas automatizadas em comandos de gerenciamento do Django.

### 2.1 Coleta

Comando: `python manage.py baixar_normas`

Lê o manifesto `fontes.json` e baixa cada documento, nomeando no padrão `NN-slug.ext` com
a extensão definida pelo `Content-Type` da resposta. É idempotente.

**Resultado da coleta e o que ela ensinou:**

| Desfecho | Quantidade |
|---|---|
| Baixados automaticamente | 21 |
| Falharam no download | 4 |
| Baixaram com HTTP 200 mas sem conteúdo útil | 3 |

As 4 falhas foram de infraestrutura: três por cadeia de certificados SSL incompleta
(servidores que omitem o certificado intermediário, algo que navegadores contornam via
*AIA fetching* mas o `urllib` não) e uma por HTTP 503.

A terceira linha é a mais relevante metodologicamente. Três arquivos foram baixados com
**status 200 e tamanho plausível**, mas continham uma página de captcha (Radware) ou
apenas o esqueleto de navegação de páginas renderizadas por JavaScript. Um pipeline que
confiasse no código de status os teria indexado como documentos válidos, ocupando espaço
no índice e nunca correspondendo a consulta alguma.

Esse achado motivou a decisão de projeto descrita a seguir.

### 2.2 Extração

Módulo: [`knowledge/extraction.py`](knowledge/extraction.py)

- **PDF** — `pypdf`
- **HTML** — `trafilatura`, com fallback
- **Validação** — arquivos que produzem menos de **150 palavras** são **recusados**, não
  indexados

O limiar de 150 palavras é a resposta direta ao problema da coleta: em vez de confiar no
transporte, o pipeline valida o **conteúdo**. A mensagem de erro é específica por formato
— em PDF aponta para ausência de camada de texto (documento digitalizado), em HTML para
captcha ou casca de JavaScript.

**O caso do trafilatura.** A biblioteca é feita para separar conteúdo principal de
boilerplate e cumpre bem esse papel na maioria das páginas. Em três portais institucionais
do corpus, porém, o conteúdo está em tabelas e listas aninhadas que seu detector
classificou como navegação: retornou 68, 60 e 18 palavras em páginas que continham 881,
607 e 153.

A solução foi tratá-lo como **primeira estratégia, não única**. Quando o resultado fica
abaixo do limiar, o pipeline recorre à remoção direta de tags, descartando apenas blocos
que comprovadamente não contêm norma (`script`, `style`, `nav`, `footer`, `header`,
`form`, `aside`). O texto sai mais ruidoso, mas as regras sobrevivem. Após a correção, os
26 documentos com arquivo em disco extraem sem falha.

### 2.3 Segmentação

Módulo: [`knowledge/chunking.py`](knowledge/chunking.py)

`RecursiveCharacterTextSplitter` com 1.000 caracteres por trecho e 200 de sobreposição,
mas com os **separadores ajustados para texto normativo**:

```python
["\nArt. ", "\nArtigo ", "\nCAPÍTULO ", "\nSeção ", "\n§", "\nParágrafo ",
 "\n\n", "\n", ". ", " ", ""]
```

A ordem importa. Os separadores padrão da biblioteca são pensados para prosa e quebram em
parágrafo e frase. Norma jurídica tem estrutura própria: a unidade de sentido é o artigo.
Um trecho cortado no meio de um artigo responde pela metade, e um trecho que funde dois
artigos não relacionados produz um embedding difuso, que não representa bem nenhum dos
dois.

Os 26 documentos produziram **734 trechos**, média de 28 por documento.

### 2.4 Indexação

Comando: `python manage.py indexar_normas`

Cada trecho é gravado com **dois vetores**:

- `embedding` — vetor denso de 384 dimensões, com índice HNSW (`vector_cosine_ops`)
- `search_vector` — `tsvector` do PostgreSQL com dicionário português, com índice GIN

A ingestão é **idempotente por SHA-256**: cada documento guarda o hash do arquivo que o
originou. Uma segunda execução não reprocessa nada; alterar um arquivo reprocessa apenas
ele. Isso atende ao requisito de reprocessamento incremental e torna barato reindexar após
ajustes no chunking.

---

## 3. Embeddings utilizados

| Item | Escolha |
|---|---|
| Biblioteca | `fastembed` (ONNX Runtime) |
| Modelo | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensionalidade | 384 |
| Métrica | Distância de cosseno |
| Índice | HNSW (`m=16`, `ef_construction=64`) |
| Execução | Local, no container |

**Por que um modelo multilíngue.** O corpus é integralmente em português, incluindo
terminologia jurídica e administrativa. Modelos treinados só em inglês — como o
`bge-small-en`, padrão do fastembed — degradam sensivelmente nesse cenário.

**Por que execução local.** O Groq, provedor do LLM usado neste trabalho, **não oferece
API de embeddings**. As alternativas seriam depender de OpenAI ou Gemini, o que
adicionaria uma segunda chave de API e um custo por requisição. O `fastembed` executa o
modelo em ONNX dentro do próprio container, sem chave e sem chamada de rede em tempo de
consulta. Para um trabalho acadêmico, isso significa que quem for avaliar reproduz o
ambiente com `make up`, sem precisar de credenciais próprias.

O custo é o primeiro uso: **252 MB** de pesos baixados uma vez, preservados no volume
`fastembed_cache` entre reconstruções da imagem.

**Uma armadilha documentada no código.** `VectorField(dimensions=384)` fixa a
dimensionalidade no schema. Trocar por um modelo de 768 ou 1024 dimensões exige nova
migration. O módulo de embeddings valida a dimensão do vetor antes de gravar e, em caso de
divergência, emite mensagem explicando exatamente isso — em vez de deixar o erro
manifestar-se como falha opaca do banco.

---

## 4. LLM utilizado

| Item | Escolha |
|---|---|
| Provedor | Groq |
| Modelo | `llama-3.3-70b-versatile` |
| Temperatura | 0.1 |

A temperatura baixa é deliberada: a tarefa é reproduzir fielmente o que está nos trechos
recuperados, não gerar texto criativo.

### 4.1 Projeto do prompt

O prompt de sistema estabelece seis regras, das quais três são específicas deste corpus:

> **Regra 1.** Responder exclusivamente com base nos trechos numerados fornecidos.
>
> **Regra 2.** Ao afirmar uma regra, dizer de qual instituição ela é.
>
> **Regra 3.** Quando os trechos divergirem, apresentar as diferenças em vez de escolher
> uma versão.
>
> **Regra 4.** Se os trechos não permitirem responder, dizer isso claramente.
>
> **Regra 5.** Citar os trechos usados pelo número, no formato `[1]`, `[2]`.
>
> **Regra 6.** Responder em português do Brasil.

As regras 2 e 3 existem por causa da natureza multi-institucional da base. Afirmar "é
necessário solicitar com 30 dias de antecedência" sem dizer de quem é a regra é enganoso,
porque outra instituição do mesmo corpus exige 7. A regra 3 impede que o modelo resolva a
divergência escolhendo arbitrariamente uma das versões.

### 4.2 Decisão: não chamar o LLM sem contexto

Quando a recuperação retorna vazia, **o modelo não é invocado**. O sistema devolve uma
mensagem explícita e o campo `used_context: false`.

Essa decisão é o núcleo da diferença entre um sistema RAG e um chatbot genérico. Um LLM
consultado sem contexto responde a partir do que memorizou no treinamento — que é
exatamente o comportamento que esta aplicação existe para evitar. A resposta seria
plausível, fluente e sem qualquer garantia de correspondência com as normas indexadas.

---

## 5. Arquitetura da solução

A solução evolui um sistema Django existente, preservando suas convenções e fronteiras.

```
knowledge/                     app da base de conhecimento
├── models.py                  Document, DocumentChunk (embedding + search_vector)
├── manifest.py                leitura de fontes.json — fonte única de verdade
├── extraction.py              PDF (pypdf) e HTML (trafilatura + fallback)
├── chunking.py                segmentação com separadores normativos
├── embedding.py               fastembed, modelo carregado uma vez
├── services.py                pipeline de ingestão, idempotente por hash
├── retrieval.py               busca híbrida com Reciprocal Rank Fusion
├── views.py                   página web de consulta
└── management/commands/
    └── indexar_normas.py

ai_assistant/                  fronteira com o provedor de LLM
├── services.py                answer_from_documents + os dois serviços anteriores
├── serializers.py
└── views.py                   POST /api/v1/ai/document-qa/

core/management/commands/
└── baixar_normas.py           coleta a partir do manifesto
```

**Separação de responsabilidades.** Todo contato com o LLM permanece confinado em
`ai_assistant`, que era a fronteira já estabelecida no trabalho da disciplina anterior. O
app `knowledge` cuida do corpus e da recuperação; a página web o consome exatamente como
`spaces/views.py` já consumia o serviço de busca em linguagem natural. Nenhuma camada nova
foi criada onde uma existente servia.

**Duas interfaces sobre o mesmo serviço:**

| Interface | Endereço |
|---|---|
| Web (HTMX) | `/assistente/` |
| API REST | `POST /api/v1/ai/document-qa/` |

### 5.1 Recuperação híbrida

Módulo: [`knowledge/retrieval.py`](knowledge/retrieval.py)

Duas estratégias, combinadas:

- **Semântica** — distância de cosseno sobre os embeddings, via índice HNSW. Encontra
  passagens que significam o mesmo que a pergunta ainda que não compartilhem vocabulário.
- **Lexical** — busca textual do PostgreSQL sobre `search_vector`, com dicionário
  português. Ancora em termos exatos que o embedding tende a diluir: número de artigo,
  nome de instituição, valor monetário.

As duas produzem escores em **escalas incomparáveis** — distância de cosseno varia de 0 a
2, `SearchRank` é outra grandeza. Normalizá-las exigiria calibração arbitrária. Por isso a
fusão usa **Reciprocal Rank Fusion**, que descarta os valores e combina apenas as
posições:

```
score(d) = Σ  1 / (k + posição(d, ranking))
```

com `k = 60`, conforme o artigo original de Cormack et al. (2009). Um trecho bem
posicionado nas duas listas supera um que lidera apenas uma.

---

## 6. Resultados

### 6.1 Consulta comparativa entre instituições

Pergunta submetida a `POST /api/v1/ai/document-qa/`:

> *Quais instituições cobram taxa pelo uso do auditório e quanto?*

Resposta obtida:

> De acordo com os trechos fornecidos, apenas a UFBA — IMS Campus Anísio Teixeira cobra
> taxa pelo uso do auditório, conforme descrito em [1]. As taxas são:
>
> - R$ 1.200,00 por dia de utilização do auditório do pavilhão administrativo;
> - R$ 500,00 por dia de utilização do auditório do pavilhão de aulas.
>
> Já a UFS — BICEN, conforme [5], não cobra taxas para eventos promovidos no auditório.
> Não há informações sobre taxas de utilização nas outras instituições mencionadas nos
> trechos [2], [3] e [4].

Esse resultado exercita todas as decisões de projeto descritas acima:

1. **A recuperação híbrida foi necessária.** O trecho da UFBA contém a palavra "taxa"
   literalmente; o da UFS afirma "não haverá cobranças de taxas". Ambos foram recuperados,
   de documentos distintos.
2. **A regra de atribuição funcionou.** Cada valor está associado à instituição de origem.
3. **A regra de divergência funcionou.** O sistema apresentou o polo que cobra e o que não
   cobra, sem escolher um.
4. **A regra de honestidade funcionou.** Declarou explicitamente que os trechos [2], [3] e
   [4] não continham informação sobre taxas, em vez de preencher a lacuna.

### 6.2 Qualidade da base

| Indicador | Resultado |
|---|---|
| Documentos com arquivo em disco | 25 de 27 fontes |
| Taxa de extração bem-sucedida | 25 de 25 (100%) |
| Arquivos rejeitados pela validação | 0 após correção da extração |

### 6.3 Avaliação automática e os limites do instrumento

A execução de `avaliar_respostas` sobre as 14 perguntas do conjunto — 13 avaliadas, uma
perdida por falha transitória de rede — produziu:

| Critério | Média |
|---|---|
| Fundamentação | 5,0 |
| Completude | 5,0 |
| Citação | 5,0 |
| **Média geral** | **5,0** |

Nota máxima em tudo é um resultado que exige investigação, não comemoração. A primeira
hipótese foi de que o conjunto era fácil demais, e por isso ele foi ampliado com **quatro
perguntas adversariais**. As notas não se moveram. A inspeção manual das respostas
mostrou por quê.

**As respostas adversariais estão de fato corretas.** Dois exemplos:

À pergunta capciosa *"Todas as instituições exigem 30 dias de antecedência, correto?"*, o
sistema **recusou a premissa** e enumerou as divergências: dois dias úteis no IFBA Paulo
Afonso, 48 horas a uma semana no IFMG, 7 a 60 dias no IFAL para público interno, 30 a 60
para externo. Concordar teria sido o comportamento fácil e errado.

Na pergunta de precisão numérica, o sistema reproduziu os dois números exatos (172
lugares, mínimo de 30%) e **detectou uma inconsistência interna da própria fonte**: "30%
de 172 é aproximadamente 51,6, mas o trecho especifica 50 participantes como o mínimo".
Preferiu o texto literal ao seu próprio cálculo — que é o comportamento correto para um
sistema que deve reportar a norma, não interpretá-la.

Ou seja: parte da nota máxima reflete desempenho real. Ainda assim, o instrumento tem
**duas limitações que a nota esconde**.

**Primeira: falta de resolução.** Uma métrica que atribui 5,0 a tudo não distingue um
sistema excelente de um apenas bom, nem detecta degradação. Se o `chunk_size` fosse
alterado ou o prompt piorado, a nota provavelmente continuaria em 5,0 — e uma métrica que
não detecta regressão não cumpre a função para a qual existe.

**Segunda, e mais séria: a avaliação é cega a falhas de recuperação.** O juiz pontua a
resposta contra os trechos recuperados. Se a recuperação trouxer os trechos errados, uma
resposta perfeitamente fiel a esses trechos errados recebe nota máxima.

A pergunta 11 demonstra isso concretamente. Perguntada sobre multa por cancelamento na
UFPA, a recuperação devolveu trechos da UNL, da FATEC, da Universidade de Lisboa, do IFC
e da UFBA — **nenhum da UFPA**. O sistema respondeu, com fidelidade ao que recebeu, que
"não há informações sobre a UFPA". O juiz deu 5,0, corretamente segundo seu próprio
critério.

Mas **a UFPA está no corpus**: é a fonte 01, um regulamento de auditório com 1.209
palavras. A afirmação da resposta é verdadeira sobre o contexto recuperado e falsa sobre
a base. A conclusão final acabou correta por acidente — verificamos que o documento da
UFPA realmente não menciona cancelamento nem multa —, mas o caminho até ela passou por
uma falha de recuperação que a métrica não tem como enxergar.

Isso não é defeito de implementação: é consequência do **desenho** da avaliação. Medir
recuperação exigiria anotar, para cada pergunta, quais trechos do corpus são relevantes —
e comparar com os efetivamente devolvidos, por métricas como *recall@k*. Com 722 trechos
e sem anotação disponível, essa medição ficou fora do escopo.

Registramos a análise porque apresentar "média 5,0" como evidência de qualidade seria uma
leitura ingênua do próprio instrumento de medida.

### 6.4 Qualidade do código

| Indicador | Resultado |
|---|---|
| Testes automatizados | 359 |
| Cobertura | 93,6% (mínimo exigido pelo projeto: 80%) |
| Linter | `ruff` sem apontamentos |

Do total, 88 testes cobrem especificamente o trabalho desta disciplina: pipeline de
ingestão, poda do índice, recuperação, serviço RAG, endpoint da API, interface web,
histórico de conversas e avaliação automática.

---

## 7. Funcionalidades complementares

| Funcionalidade | Situação |
|---|---|
| Busca híbrida (vetorial + lexical) | Implementada — seção 5.1 |
| Histórico de conversas | Implementado — seção 7.1 |
| Avaliação automática de respostas | Implementada — seção 7.2 |
| Utilização de Docker | Implementada — `docker-compose.yml` |
| Reprocessamento incremental de documentos | Implementado — seção 7.3 |

### 7.1 Histórico de conversas

Model `ConversationTurn`, com persistência por usuário e exibição na página de consulta.

Além de registrar, os **três turnos mais recentes voltam ao prompt** como preâmbulo. Sem
isso, uma pergunta de acompanhamento como *"e na UFBA?"* é literalmente irrespondível: o
sujeito da pergunta está no turno anterior. O preâmbulo é explicitamente marcado como
destinado apenas a resolver referências implícitas, para não competir com os trechos
recuperados como fonte de conteúdo.

**Decisão de modelagem:** as fontes são gravadas **desnormalizadas**, em um campo JSON,
em vez de chave estrangeira para `DocumentChunk`. Os trechos são apagados e reconstruídos
a cada reindexação — uma FK obrigaria a escolher entre bloquear a reindexação ou apagar
silenciosamente a procedência das respostas passadas. Copiar o trecho preserva o registro
histórico do que foi efetivamente mostrado ao usuário naquele momento.

### 7.2 Avaliação automática de respostas

Comando: `python manage.py avaliar_respostas`

Módulo: [`ai_assistant/evaluation.py`](ai_assistant/evaluation.py)

Um segundo modelo (LLM-as-a-judge) pontua cada resposta de 0 a 5 em três critérios:

| Critério | O que mede |
|---|---|
| **Fundamentação** | Toda afirmação é sustentada pelos trechos recuperados? |
| **Completude** | A resposta aproveita a informação relevante disponível? |
| **Citação** | Os trechos são citados por número e atribuídos à instituição correta? |

**A escolha do referencial importa.** O juiz avalia a resposta contra **os trechos que
foram recuperados**, não contra o mundo. Essa é a propriedade que interessa aqui: o
sistema deve reportar o que o corpus diz, então uma resposta é correta quando é fiel ao
corpus — mesmo que o corpus esteja incompleto. O prompt do juiz é explícito: uma
afirmação verdadeira no mundo real, mas não sustentada pelos trechos, é falha de
fundamentação.

O conjunto de referência está em
[`data/avaliacao/perguntas.json`](data/avaliacao/perguntas.json): nove perguntas sobre o
domínio, sendo três comparativas entre instituições, uma de **controle negativo** sobre
assunto ausente do corpus, e quatro **adversariais** acrescentadas depois de a primeira
execução revelar saturação do indicador — ver seção 6.3. Para o controle negativo, a
resposta correta é declarar que não há informação, e o prompt do juiz instrui a premiar
esse comportamento em vez de puni-lo.

```bash
docker compose exec web python manage.py avaliar_respostas
docker compose exec web python manage.py avaliar_respostas --salvar relatorio.json
```

A execução usada na seção 6.3 está versionada em
[`data/avaliacao/resultado-2026-07-27.json`](data/avaliacao/resultado-2026-07-27.json),
com as respostas geradas, os trechos recuperados e a justificativa do juiz para cada
pergunta.

As notas do juiz são normalizadas para a escala 0–5 antes de entrar na média. O juiz é
ele próprio um LLM e pode devolver um valor fora da escala ou em formato inesperado; sem
essa proteção, um veredito malformado contaminaria o agregado.

### 7.3 Reprocessamento incremental

Cada documento guarda o SHA-256 do arquivo que o originou. Uma nova execução de
`indexar_normas` compara os hashes e só reprocessa o que mudou — reindexar 25 documentos
por causa de um único arquivo alterado seria desperdício de tempo e de chamadas ao modelo
de embedding.

O caminho inverso também é tratado: documentos cuja fonte **saiu do manifesto** são
removidos do índice. Sem essa poda, aposentar uma fonte deixaria seus trechos no índice
para sempre, ainda concorrendo na recuperação — uma divergência silenciosa entre o que o
manifesto declara e o que o assistente de fato pesquisa. A poda só ocorre em execução
completa: durante uma execução parcial (`--somente`), a ausência de uma fonte no filtro é
esperada e não significa nada sobre o corpus.

---

## 8. Limitações e trabalhos futuros

**Duas fontes sem arquivo.** As fontes 18 (UFG/Letras) e 19 (UFRGS/FCE) permanecem sem
documento em disco: a primeira é uma página que apenas orienta o envio de e-mail, sem
norma; a segunda respondeu HTTP 503 durante a coleta.

**Documentos digitalizados.** Alguns PDFs institucionais são imagens sem camada de texto.
São corretamente rejeitados pela validação, mas recuperá-los exigiria OCR — decisão
adiada por custo de dependências frente ao prazo.

**A avaliação não mede recuperação.** Como detalhado na seção 6.3, o juiz pontua a
resposta contra os trechos recuperados, de modo que uma falha de recuperação é invisível
para a métrica. Corrigir isso exige anotar quais trechos do corpus são relevantes para
cada pergunta e medir *recall@k* — trabalho de anotação que não coube no prazo. É a
limitação mais importante deste trabalho.

**O juiz e o gerador são o mesmo modelo.** A avaliação usa o mesmo
`llama-3.3-70b-versatile` que produz as respostas. A literatura documenta viés de
autopreferência nesse arranjo: modelos avaliam melhor textos com seu próprio estilo. Uma
avaliação mais rigorosa usaria um juiz de outra família, ou anotação humana em uma amostra
para calibrar as notas automáticas.

**Prompt do juiz não calibrado.** Os critérios são descritos em linguagem natural, sem
âncoras que definam o que separa uma nota 3 de uma nota 5. Rubricas com exemplos por
faixa de nota provavelmente produziriam maior dispersão e, portanto, mais poder
discriminativo.

**Dependência da versão do fastembed.** A biblioteca alterou a estratégia de *pooling* do
modelo (de CLS para *mean pooling*). Embeddings gerados por versões diferentes não são
comparáveis entre si, de modo que atualizar a dependência exige reindexar o corpus com
`indexar_normas --force`.

---
-----------------------
---

# Documentação do Sistema

Sistema centralizado para descoberta e reserva de salas e espaços físicos. Resolve o problema da fragmentação de canais (planilhas, e-mails, calendários físicos) e reduz o desperdício de espaço com liberação automática de reservas não utilizadas.

## Pilares

1. **Calendário único e centralizado** — se não está no sistema, não existe.
2. **Liberação automática de no-shows** — sem check-in em 15 minutos, a sala volta a ficar disponível.
3. **Filtros por atributos mínimos** — busca por capacidade e equipamentos (TV, projetor, videoconferência etc.).
4. **Assistência por IA** — busca de salas em linguagem natural e classificação automática de motivos de manutenção, via LLM (Groq).

---

## Como funciona (alto nível)

### Apps principais

| App | Responsabilidade |
|-----|-----------------|
| `accounts` | Autenticação, registro, login/logout |
| `spaces` | Cadastro de espaços e seus atributos (capacidade, localização, equipamentos) |
| `reservations` | Ciclo de vida da reserva: criar, cancelar, reagendar, check-in e auto-release |
| `admin_dashboard` | Interface administrativa customizada (ocupação, gestão de espaços, reservas, manutenção e usuários) |
| `ai_assistant` | Serviços de IA (LLM via Groq): busca de salas em linguagem natural e classificação de motivos de manutenção |

Para ajustar o comportamento conversacional da IA (prompts do sistema, mapeamento de sinônimos como “internet” → “Wi-Fi”, categorias de manutenção e parsing da resposta do LLM), edite `ai_assistant/services.py`. As views (`ai_assistant/views.py` e a busca em `spaces/views.py`) apenas consomem esses serviços.

### API vs Interface Web

- **API REST** (`/api/v1/...`): serve integrações futuras e o QR Code de check-in.
- **Interface Web** (templates + HTMX + DaisyUI): navegação server-side com atualizações parciais de página, sem SPA.

### Estados de uma reserva

| Estado | Quando ocorre |
|--------|--------------|
| `confirmed` | Reserva criada com sucesso (padrão) |
| `checked_in` | Usuário confirmou presença dentro da janela de check-in |
| `cancelled` | Usuário ou admin cancelou a reserva |
| `completed` | Horário da reserva passou e houve check-in |
| `no_show` | Início da reserva passou + 15 minutos sem check-in (auto-release) |

---

## Jornadas

### Usuário final

1. Acessa `/accounts/login/` e entra com usuário e senha (redirecionamento é automático conforme o perfil da conta).
2. Busca espaços em `/spaces/` filtrando por capacidade, localização e equipamentos.
3. Visualiza detalhes do espaço em `/spaces/{id}/` e confere a disponibilidade por data.
4. Seleciona um horário livre e cria a reserva em `/reservations/new/?space={id}`.
5. Gerencia suas reservas em `/reservations/` (cancelar, reagendar).
6. Faz check-in na página `/reservations/{id}/check-in/` (pode ser acessada via QR Code).

### Administrador do espaço

1. Acessa `/accounts/login/` com uma conta com permissão de staff — é redirecionado automaticamente para o painel admin.
2. Acessa o dashboard em `/admin-dashboard/` para ver ocupação em tempo real.
3. Gerencia espaços em `/admin-dashboard/spaces/` (criar, editar, ativar/desativar).
4. Visualiza e cancela reservas em `/admin-dashboard/reservations/`.
5. Cria bloqueios de manutenção em `/admin-dashboard/maintenance/` para impedir reservas em determinados horários.
6. Gerencia usuários em `/admin-dashboard/users/` (criar, editar, remover, promover a admin).

---

## Fluxo por caso de uso

### Login / Registro / Logout

1. Acesse `/accounts/login/` e escolha entrar como **Admin** ou **Usuário**. A escolha é validada: contas sem permissão de staff não conseguem entrar pelo caminho "Admin".
2. Acesse `/accounts/register/` para criar uma conta (sempre como usuário comum).
3. Clique em "Sair" na barra de navegação para encerrar a sessão.

### Listagem e filtro de espaços

1. Acesse `/spaces/`.
2. Preencha capacidade mínima, localização e/ou selecione equipamentos.
3. Clique em **Filtrar**. A lista de espaços atualiza sem recarregar a página.

### Detalhe do espaço e disponibilidade

1. Na listagem, clique em um espaço ou acesse `/spaces/{id}/`.
2. Veja informações do espaço e selecione uma data para ver horários livres/ocupados.
3. Clique em um horário livre para iniciar a reserva.

### Criar, cancelar e reagendar reserva

1. No formulário `/reservations/new/?space={id}`, escolha data e horário de início/fim.
2. Confirme para criar a reserva. Em caso de conflito, o sistema exibe um alerta.
3. Em `/reservations/{id}/`, clique em **Cancelar** ou **Reagendar** conforme necessário.

### Check-in via página (fluxo QR Code)

1. O QR Code na porta da sala aponta para `/reservations/{id}/check-in/`.
2. O usuário acessa a página e confirma a presença.
3. O status muda para `checked_in` e a sala é considerada ocupada.

### Dashboard e páginas administrativas

1. Acesse `/admin-dashboard/` para visão geral de ocupação.
2. Acesse `/admin-dashboard/spaces/` para gerenciar espaços.
3. Acesse `/admin-dashboard/reservations/` para gerenciar reservas.
4. Acesse `/admin-dashboard/maintenance/` para criar bloqueios de manutenção.
5. Acesse `/admin-dashboard/users/` para gerenciar usuários.

---

## Como executar localmente

### Pré-requisitos

- Docker
- Docker Compose
- Make (opcional, para atalhos)

### Passos

```bash
# 1. Clone o repositório e entre na pasta
# 2. Suba os serviços (Django + PostgreSQL)
make up

# 3. Aplique as migrações
make migrate

# 4. Popule o banco com dados de demonstração
make seed

# 5. Indexe a base de normas para o assistente documental
docker compose exec web python manage.py indexar_normas

# 6. Acesse a aplicação em http://localhost:8000
```

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. Para usar os endpoints de IA (`/api/v1/ai/...`), é necessário definir:

| Variável | Descrição |
|----------|-----------|
| `GROQ_API_KEY` | Chave de API do Groq (gratuita em https://console.groq.com/keys). Sem ela, os endpoints de IA retornam erro 502. |
| `GROQ_MODEL` | Modelo usado nas chamadas (padrão: `llama-3.3-70b-versatile`) |

### Comandos úteis

| Comando | Descrição |
|---------|-----------|
| `make up` | Inicia os containers |
| `make down` | Para os containers |
| `make migrate` | Aplica migrações do banco |
| `make seed` | Cria dados de demonstração (idempotente) |
| `make seed-flush` | Remove dados de demonstração e recria |
| `make test` | Executa a suíte de testes com cobertura |
| `make lint` | Executa o linter (ruff) |
| `make format` | Formata o código (ruff) |
| `make shell` | Abre terminal bash dentro do container web |

---

## Base de normas e indexação

O assistente documental responde perguntas sobre um corpus de regulamentos públicos de
uso de espaços físicos — auditórios, salas de reunião e cessão a terceiros — reunidos de
universidades, institutos federais e órgãos do sistema de Justiça.

Os documentos ficam versionados em `data/normas/`, junto de `fontes.json`, que registra a
procedência de cada um: instituição, título, categoria e URL de origem. Versionar os
arquivos garante que o projeto rode logo após o clone, sem depender de portais externos
que saem do ar — durante a coleta, 4 das 29 fontes falharam e 3 responderam com página de
captcha ou casca de JavaScript. São atos normativos públicos, de livre redistribuição.

### Indexar o corpus

```bash
docker compose exec web python manage.py indexar_normas
```

O comando executa o pipeline em quatro etapas:

1. **Extração** — `pypdf` para PDF, `trafilatura` para HTML. Arquivos que produzem menos
   de 150 palavras são recusados, e não indexados como se fossem válidos.
2. **Segmentação** — divisão em trechos com separadores ajustados para texto normativo
   (`Art.`, `§`, `CAPÍTULO`), de modo que um artigo não seja cortado ao meio.
3. **Embeddings** — vetores gerados localmente pelo `fastembed`, sem chave de API.
4. **Persistência** — trechos gravados com índice HNSW (busca semântica) e `tsvector`
   em português (busca lexical).

É **idempotente**: cada documento guarda o SHA-256 do arquivo que o originou, então rodar
de novo não reprocessa nada. Alterar um arquivo reprocessa apenas ele.

| Opção | Efeito |
|-------|--------|
| `--force` | Reindexa mesmo o que não mudou |
| `--somente 3 5 9` | Indexa apenas os ids informados |

Ao final, o comando relata quantos documentos foram indexados, quais fontes não têm
arquivo em disco e quais falharam, com o motivo.

> **Primeira execução:** o modelo de embedding (~250 MB) é baixado uma vez e guardado no
> volume `fastembed_cache`, preservado entre builds.

### Baixar o corpus novamente

Os arquivos já estão no repositório. Para recoletá-los das fontes originais:

```bash
docker compose exec web python manage.py baixar_normas
```

Aceita as mesmas opções `--force` e `--somente`.

---

## Seeds e credenciais padrão

O comando `make seed` popula o banco com dados de demonstração em português. Ele é **idempotente** — pode ser executado várias vezes sem duplicar registros.

Para recriar os dados do zero:

```bash
make seed-flush
```

### Usuários padrão

| Usuário | Perfil | Staff |
|---------|--------|-------|
| `admin` | Administrador | Sim |
| `maria.silva` | Usuária comum | Não |
| `joao.santos` | Usuário comum | Não |
| `ana.costa` | Usuária comum | Não |

**Senha padrão:** `reserva123` (configurável via variável `SEED_DEFAULT_PASSWORD` no `.env`)

### Dados criados

- **7 atributos de equipamento**: Ar-condicionado, Projetor, TV, Webcam, Quadro branco, Videoconferência, Wi-Fi
- **5 espaços**: Sala de Reunião Alfa, Sala de Reunião Beta, Sala Focus, Auditório Central, Sala Executiva
- **4 reservas de exemplo**: em diferentes status (confirmada, concluída, no-show, com janela de check-in para hoje)
- **2 bloqueios de manutenção**: com motivos em português

---

## Rotas principais

### Interface Web

| Rota | Descrição |
|------|-----------|
| `/accounts/login/` | Login (escolha entre Admin e Usuário) |
| `/accounts/register/` | Registro de conta |
| `/spaces/` | Busca de espaços com filtros |
| `/spaces/{id}/` | Detalhe do espaço e disponibilidade |
| `/reservations/` | Minhas reservas |
| `/reservations/new/` | Nova reserva |
| `/reservations/{id}/` | Detalhe da reserva |
| `/reservations/{id}/check-in/` | Check-in |
| `/admin-dashboard/` | Dashboard de ocupação |
| `/admin-dashboard/spaces/` | Gestão de espaços |
| `/admin-dashboard/reservations/` | Gestão de reservas |
| `/admin-dashboard/maintenance/` | Bloqueios de manutenção |
| `/admin-dashboard/users/` | Gestão de usuários |
| `/assistente/` | Consulta às normas em linguagem natural, com exibição das fontes |

### API REST (`/api/v1/`)

Toda a API é versionada sob `/api/v1/`.

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/v1/spaces/` | Listar espaços (com filtros) |
| GET | `/api/v1/spaces/{id}/` | Detalhe do espaço |
| GET | `/api/v1/spaces/{id}/availability/` | Disponibilidade por data |
| GET | `/api/v1/reservations/` | Listar minhas reservas |
| POST | `/api/v1/reservations/` | Criar reserva |
| PATCH | `/api/v1/reservations/{id}/cancel/` | Cancelar reserva |
| PATCH | `/api/v1/reservations/{id}/reschedule/` | Reagendar reserva |
| POST | `/api/v1/reservations/{id}/check-in/` | Fazer check-in |
| GET | `/api/v1/admin/occupancy/` | Dashboard de ocupação (admin) |
| POST | `/api/v1/admin/maintenance-blocks/` | Criar bloqueio de manutenção (admin) |
| POST | `/api/v1/ai/room-search/` | Busca de salas a partir de uma descrição em linguagem natural (ex.: "sala para 8 pessoas com projetor perto da recepção"). O LLM extrai os filtros (capacidade, atributos, localização) e a API retorna os espaços correspondentes. |
| POST | `/api/v1/ai/maintenance-classify/` | Classifica um motivo de manutenção em texto livre em uma categoria fixa (elétrica, hidráulica, limpeza, TI/equipamentos, mobiliário, segurança, outros), com justificativa e nível de confiança. |
| POST | `/api/v1/ai/document-qa/` | Responde perguntas em linguagem natural sobre o corpus de normas (RAG). Recupera trechos por busca híbrida, gera resposta ancorada neles e devolve as fontes utilizadas. Aceita `top_k` e `hybrid`. |

Os endpoints de IA exigem autenticação (`IsAuthenticated`), validam a entrada (tamanho mínimo/máximo do texto) e retornam `502` se o provedor de IA falhar. Documentação interativa (Swagger/Redoc) disponível em `/swagger/` e `/redoc/`.

---

## Tecnologias

- **Backend:** Django 5.2, Django REST Framework, PostgreSQL 16
- **Banco vetorial:** pgvector (índice HNSW, distância de cosseno)
- **LLM:** Groq (`llama-3.3-70b-versatile`) para busca em linguagem natural, classificação de texto e consulta documental (RAG)
- **Embeddings:** fastembed (ONNX) com `paraphrase-multilingual-MiniLM-L12-v2`, executado localmente
- **Processamento de documentos:** pypdf, trafilatura, langchain-text-splitters
- **Frontend:** Django Templates, HTMX, DaisyUI (sobre Tailwind CSS)
- **Infra:** Docker, Docker Compose
- **Qualidade:** pytest (com cobertura mínima de 80%), ruff, pre-commit, commitizen
