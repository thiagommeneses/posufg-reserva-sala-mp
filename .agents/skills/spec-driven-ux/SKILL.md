---
name: spec-driven-ux
description: Conduz desenvolvimento spec-driven do início ao fim — estratégia de UX e discovery, mapeamento de histórias de usuário, fatiamento em releases e escrita de specs executáveis com critérios de aceite — usando os fundamentos de Jaime Levy (UX Strategy), Jeff Patton (User Story Mapping) e Travis Lowdermilk (Design Centrado no Usuário). Use sempre que o assunto for planejar, descobrir, priorizar ou especificar um produto ou funcionalidade — pedidos como "escreve a spec", "PRD", "story map", "mapa de histórias", "levantamento de requisitos", "backlog", "critérios de aceite", "discovery", "MVP", "roadmap", "vamos planejar o sistema X" ou "como estruturar essa feature" — mesmo que o usuário não cite estratégia de UX nem spec-driven explicitamente. Vale para SaaS, e-commerce, sistemas institucionais/jurídicos e ferramentas de mercado financeiro.
---

# Spec-Driven UX

Método para sair de uma ideia vaga e chegar em specs que um humano ou um agente consegue implementar sem precisar da conversa original — sem pular a parte em que se descobre se a coisa vale a pena ser construída.

## Princípio central

Três ideias sustentam todo o resto:

1. **Resultado acima de entrega** (Patton). O objetivo nunca é "entregar a tela"; é mudar um comportamento do usuário e um número do negócio. Funcionalidade que não move nenhum dos dois é desperdício caro.
2. **Estratégia é validada, não decretada** (Levy). Proposta de valor e segmento de cliente são hipóteses até que evidência de campo diga o contrário. Estratégia de UX vive no encontro entre estratégia de negócio, inovação de valor, pesquisa validada com usuários e execução de design.
3. **O usuário não é você** (Lowdermilk). Suposição sobre usuário é dívida técnica disfarçada de requisito. Envolver usuário cedo, em pequenas doses e com frequência, custa menos do que qualquer refatoração posterior.

A spec é o artefato final, mas o valor está no entendimento compartilhado que a produz. Documento sem conversa vira ficção bem formatada.

## Roteador: por onde entrar

Nem todo pedido começa na fase 1. Identifique o sinal e entre na fase certa — mas verifique se as saídas das fases anteriores existem. Se não existirem, diga isso e proponha uma versão enxuta (30 minutos, não 3 semanas) antes de seguir.

| Sinal do usuário | Entre em | Leia antes |
|---|---|---|
| "tive uma ideia", "vale a pena?", "quem é o público?", concorrência, MVP | Fase 1 — Descoberta | `references/01-estrategia-ux-levy.md`, `references/03-ucd-lowdermilk.md` |
| "quais features?", "como priorizar?", "o que entra no release 1?", backlog bagunçado | Fase 2 — Mapeamento | `references/02-story-mapping-patton.md` |
| "escreve a spec", "PRD", "critérios de aceite", "manda pro dev/agente" | Fase 3 — Especificação | `references/04-specs-e-criterios.md` |
| "já lançamos, e agora?", métricas, teste de usabilidade, feedback | Fase 4 — Validação | `references/03-ucd-lowdermilk.md` |
| Domínio específico (jurídico, e-commerce, SaaS, trading) | qualquer fase | `references/05-contextos-de-dominio.md` |

## Regras invioláveis

Estas seis regras existem porque cada uma corresponde a um jeito conhecido de o processo falhar em silêncio.

1. **Nunca invente evidência.** Não fabrique dados de entrevista, números de mercado, citações de usuário ou resultados de teste. Marque cada afirmação relevante com `[FATO]` (dito pelo usuário ou verificado), `[HIPÓTESE]` (assumido, precisa validar) ou `[A VALIDAR]` (com o experimento que resolveria). Um documento cheio de `[HIPÓTESE]` é honesto e útil; um cheio de invenções é perigoso.
2. **Toda história aponta para um resultado.** Se uma história não rastreia até um `OUT-xx`, ou o resultado está faltando ou a história está sobrando.
3. **Fatia é valor ponta a ponta.** Uma fatia atravessa a narrativa inteira de forma fina (o *walking skeleton* de Patton). Fatiar por camada técnica — "sprint do backend", "sprint das telas" — destrói a capacidade de aprender cedo.
4. **Critério de aceite descreve comportamento observável.** "Dado/Quando/Então" sobre o que o usuário vê e o sistema faz, nunca sobre como o código está organizado.
5. **Pergunte em lotes pequenos.** No máximo 5 perguntas por vez, as de maior impacto primeiro. Se o usuário não souber, registre como hipótese explícita e siga — não trave o fluxo esperando certeza.
6. **Spec pronta é autossuficiente.** Alguém sem acesso a esta conversa deve conseguir implementar. Se precisa perguntar "mas e se...", a spec está incompleta.

## Fase 1 — Descoberta e estratégia de UX

Objetivo: transformar "quero construir X" em uma aposta declarada, com quem se beneficia, por que ganharia da alternativa atual e o que precisa ser verdade.

Passos, na ordem:

1. **Enquadre o problema e o resultado de negócio.** Quem tem a dor, com que frequência, o que faz hoje sem o produto, e qual número da organização muda se resolvermos. Sem esse número não há como priorizar depois.
2. **Escreva a proposta de valor provisória.** Formato: *para [segmento] que [situação/dor], o [produto] é um [categoria] que [benefício central], diferente de [alternativa atual] porque [inovação de valor]*.
3. **Perfile os usuários** (Lowdermilk). Um perfil por segmento distinto — contexto de uso, objetivos, nível de fluência, restrições, o que hoje frustra. Distinga usuário, comprador e afetado; em contexto institucional eles quase nunca são a mesma pessoa. Template: `templates/01-perfil-usuario.md`.
4. **Analise a concorrência** (Levy). Concorrentes diretos e indiretos, incluindo "planilha + WhatsApp" e "não fazer nada", que costumam ser os campeões reais. Compare em atributos que importam ao usuário, não em lista de features. Template: `templates/02-analise-competitiva.md`.
5. **Levante as hipóteses de risco.** Liste o que precisa ser verdade para a aposta funcionar e ordene por *quanto dói se estiver errado*. Risco de valor (querem?), de usabilidade (conseguem?), de viabilidade (dá pra construir?), de negócio (funciona pra nós?).
6. **Desenhe experimentos baratos** para as duas ou três hipóteses mais caras: entrevista guiada, teste de guerrilha, protótipo de fidelidade mínima, landing de teste. Defina *antes* qual resultado invalida a hipótese. Template: `templates/03-experimento-validacao.md`.

**Portão para a fase 2** — só avance com: segmento primário definido, proposta de valor escrita, pelo menos uma alternativa atual mapeada, hipóteses de risco listadas e resultado de negócio nomeado. Faltando algo, avance mesmo assim se o usuário decidir, mas registre a lacuna em "Riscos e hipóteses abertas" da spec.

Saída: `templates/00-discovery-brief.md` preenchido.

## Fase 2 — Mapeamento de histórias

Objetivo: transformar a aposta em narrativa e a narrativa em fatias priorizadas. Detalhes do método em `references/02-story-mapping-patton.md`.

1. **Conte a história em voz alta, na ordem do tempo.** O que a pessoa faz do começo ao fim para atingir o objetivo — hoje, no mundo real, inclusive as partes fora do sistema.
2. **Monte a espinha dorsal.** Atividades de alto nível (`ACT-xx`) na horizontal, em ordem narrativa. Abaixo de cada uma, os passos (`STP-xx.yy`) que a compõem.
3. **Desça para os detalhes.** Sob cada passo, as histórias (`US-xxx`): variações, exceções, alternativas, regras. Aqui é onde as ideias vão — inclusive as ruins, que ficam visíveis e são descartadas conscientemente.
4. **Fatie horizontalmente por resultado.** Cada fatia é um conjunto de histórias que atravessa a espinha inteira e entrega um resultado inteiro para um grupo de usuários. Nomeie a fatia pelo resultado ("advogado consegue peticionar sem sair do sistema"), não por tamanho.
5. **Nomeie a primeira fatia como esqueleto ambulante:** o caminho mais fino que funciona ponta a ponta e já pode ser observado com usuário real.
6. **Marque o que está fora.** O mapa também serve para tornar visível o que foi deliberadamente adiado — isso evita a renegociação eterna.

Saídas: `templates/04-story-map.yaml` (fonte da verdade, legível por máquina), `templates/05-story-map.md` (visualização) e `templates/08-plano-de-fatias.md`. Rode `scripts/storymap.py` para validar e renderizar.

## Fase 3 — Especificação

Objetivo: para cada fatia priorizada, produzir specs que sustentem implementação direta. Regras de escrita e padrões de critério em `references/04-specs-e-criterios.md`.

Uma spec por história significativa ou por conjunto coeso de histórias de um passo. Estrutura obrigatória em `templates/06-feature-spec.md`:

- Identificação e rastreabilidade (`OUT` → `ACT` → `STP` → `US` → `AC`)
- Resultado esperado e como será medido
- Usuários afetados e cenário de uso
- Escopo e — igualmente importante — não-escopo
- Fluxo principal e fluxos alternativos/erro
- Regras de negócio numeradas
- Critérios de aceite em Dado/Quando/Então, cobrindo caminho feliz, alternativo, erro e limites
- Requisitos não funcionais que realmente se aplicam (desempenho, segurança, privacidade, acessibilidade, disponibilidade, auditoria)
- Dados e contratos: entidades, campos, validações, integrações
- Telemetria: quais eventos permitem saber se o resultado aconteceu
- Riscos e hipóteses ainda abertas
- Definição de pronto

**Teste de qualidade antes de entregar a spec:** um dev sem contexto consegue começar hoje? Um QA consegue escrever os testes só com os critérios? Dá para saber, em duas semanas, se funcionou? Se alguma resposta for não, falta seção.

## Fase 4 — Validação e iteração

Entregar não encerra o ciclo. Conforme Lowdermilk, a validação com usuário é contínua e barata quando é frequente.

1. Coloque a fatia na frente de 3 a 5 usuários reais com tarefa definida, sem instruções. Observe o que fazem, não o que dizem que fariam.
2. Compare a telemetria com o resultado prometido na spec. Nomeie explicitamente: confirmou, refutou ou foi inconclusivo.
3. Atualize o mapa — histórias mudam de fatia, morrem ou nascem. O mapa é vivo; se ele congela, o processo virou cerimônia.
4. Reescreva as hipóteses que sobreviveram e volte para a fase que o aprendizado exigir.

## Rastreabilidade

Use IDs estáveis desde a fase 1; eles ligam decisão a código a teste a métrica.

```
OUT-01  resultado de negócio/usuário
 └ ACT-02  atividade da espinha dorsal
    └ STP-02.03  passo
       └ US-014  história
          └ AC-014.2  critério de aceite
H-03    hipótese aberta
EXP-02  experimento de validação
```

Nunca renumere um ID já usado — marque como obsoleto e crie outro.

## Antipadrões

- **Mapa que é lista de features.** Se não dá para ler como narrativa temporal, não é um mapa; é backlog em formação de coluna.
- **Persona de fantasia.** Perfil construído a partir de suposição do time, sem uma única conversa. Marque como `[HIPÓTESE]` e trate como risco.
- **Fatia técnica.** "Fatia 1: modelagem de dados." Não entrega resultado, não gera aprendizado.
- **Critério que testa implementação.** "Então o registro é gravado na tabela X" — reescreva pelo efeito observável.
- **Spec sem métrica.** Se ninguém sabe dizer o que muda, ninguém vai poder dizer que deu certo.
- **Discovery pulado porque "o cliente já pediu".** Cliente pede solução; o trabalho é entender o problema por trás e devolver a melhor solução, mesmo que seja a que ele pediu.
- **Documento que ninguém leu junto.** Entendimento compartilhado se constrói em conversa; o documento é o resíduo dela.

## Conteúdo do pacote

```
references/                     detalhes operacionais — leia o da fase antes de produzir o artefato
  01-estrategia-ux-levy.md      fase 1: proposta de valor, concorrência, experimentos
  02-story-mapping-patton.md    fase 2: narrativa, espinha dorsal, fatiamento, esqueleto ambulante
  03-ucd-lowdermilk.md          fases 1 e 4: perfis, pesquisa, testes de usabilidade, iteração
  04-specs-e-criterios.md       fase 3: anatomia da spec, Dado/Quando/Então, RNFs, erros comuns
  05-contextos-de-dominio.md    qualquer fase: jurídico/institucional, e-commerce, SaaS,
                                mercado financeiro, sistemas com IA embutida
templates/                      artefatos em branco, na ordem de uso
  00-discovery-brief.md         01-perfil-usuario.md        02-analise-competitiva.md
  03-experimento-validacao.md   04-story-map.yaml           05-story-map.md
  06-feature-spec.md            07-criterios-aceite.md      08-plano-de-fatias.md
examples/                       um caso institucional completo, do brief à spec — o padrão de
                                qualidade esperado; comece por examples/README.md
scripts/storymap.py             valida o YAML do mapa, checa rastreabilidade, gera Markdown/HTML
```

Leia o reference da fase em que estiver antes de produzir o artefato daquela fase — cada um traz os detalhes operacionais que não cabem aqui. Em dúvida sobre profundidade ("detalho quanto esta spec?", "esta métrica serve?"), compare com o artefato correspondente em `examples/` antes de entregar.

## Uso do script

```bash
python scripts/storymap.py validar mapa.yaml       # erros de estrutura e rastreabilidade
python scripts/storymap.py md mapa.yaml -o mapa.md # tabela de atividades × fatias
python scripts/storymap.py html mapa.yaml -o mapa.html
```

O validador aponta história sem resultado associado, fatia vazia, passo órfão e IDs duplicados — exatamente os defeitos que passam despercebidos na leitura.
