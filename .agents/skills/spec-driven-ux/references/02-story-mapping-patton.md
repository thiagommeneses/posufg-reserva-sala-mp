# Mapeamento de histórias de usuário — fundamentos operacionais

Base conceitual: Jeff Patton, *User Story Mapping: Discover the Whole Story, Build the Right Product*. Síntese operacional para conduzir a fase 2.

## Índice

1. Por que mapa e não lista
2. Anatomia do mapa
3. Como construir, passo a passo
4. Fatiamento por resultado
5. Esqueleto ambulante
6. Escrita das histórias
7. Descoberta contínua dentro da entrega
8. Sinais de que o mapa está errado

## 1. Por que mapa e não lista

Backlog é uma lista plana: perde a ordem narrativa, o contexto e a noção de completude. Fica impossível olhar e perguntar "falta alguma coisa para a pessoa conseguir terminar o que veio fazer?".

O mapa recupera duas dimensões:

- **Horizontal**: o tempo. A sequência do que a pessoa faz, do começo ao fim.
- **Vertical**: a necessidade. Do essencial ao opcional, dentro de cada momento.

A consequência prática: dá para cortar escopo por linhas horizontais mantendo a história inteira funcionando, em vez de amputar o final da jornada.

O produto do mapeamento não é o mapa — é o entendimento compartilhado entre quem decide, quem projeta e quem constrói. O mapa é o que sobra da conversa e permite retomá-la.

## 2. Anatomia do mapa

```
OUT-01 resultado buscado
┌──────────────┬──────────────┬──────────────┐
│ ACT-01       │ ACT-02       │ ACT-03       │  espinha dorsal (atividades, ordem narrativa)
├──────────────┼──────────────┼──────────────┤
│ STP-01.01    │ STP-02.01    │ STP-03.01    │  passos que compõem cada atividade
│ STP-01.02    │ STP-02.02    │              │
└──────────────┴──────────────┴──────────────┘
  US-001         US-010         US-020         ─── fatia 1: esqueleto ambulante
  US-002         US-011                        ─── fatia 2: torna utilizável no dia a dia
  US-003                        US-021         ─── fatia 3: escala e casos de exceção
```

- **Atividade (`ACT`)**: bloco de alto nível que agrupa passos com um objetivo comum. Nomeie com verbo no infinitivo + objeto: "instruir processo", "montar carrinho", "configurar alerta".
- **Passo (`STP`)**: unidade da narrativa que a pessoa executa. Também verbo + objeto, mais específico.
- **História (`US`)**: variação, detalhe, regra ou alternativa dentro de um passo. É aqui que o escopo realmente vive.
- **Fatia**: corte horizontal que atravessa a espinha e entrega um resultado inteiro.

## 3. Como construir, passo a passo

1. **Defina o resultado e o usuário.** Sem isso, o mapa vira mapa de sistema, não de pessoa.
2. **Narre em voz alta**, do início ao fim, no presente e no mundo real. Inclua o que acontece fora do software — telefone, papel, conversa com colega. É lá que costumam estar as oportunidades.
3. **Escreva um passo por cartão**, na ordem em que acontecem. Não organize enquanto escreve; escreva primeiro, ordene depois.
4. **Agrupe em atividades** quando a linha ficar longa demais para ler de uma vez.
5. **Confira a completude** perguntando: o que pode dar errado aqui? o que essa pessoa faz quando o caso é excepcional? quem mais participa deste passo?
6. **Detalhe verticalmente**, colocando as histórias sob cada passo, do essencial para o opcional.
7. **Marque o fora de escopo** explicitamente, sem apagar. O que está visível e descartado não volta a cada reunião.

Quando trabalhar sozinho ou com o usuário em uma conversa de chat, faça o mesmo processo por escrito: primeiro a narrativa em prosa, depois a decomposição. Pular a narrativa produz mapas que são só a estrutura do banco de dados travestida.

## 4. Fatiamento por resultado

Cada fatia responde: **quem consegue fazer o quê de novo, e que resultado isso gera?**

Critérios de uma boa fatia:

- Atravessa a espinha dorsal inteira, mesmo que de forma rudimentar em vários pontos.
- Entrega valor observável para um grupo real de usuários.
- Permite medir algo — se não gera evento mensurável, não gera aprendizado.
- Cabe em um ciclo curto de entrega.

Ordene as fatias por aprendizado e risco, não por facilidade. A fatia que responde a hipótese mais cara vem antes da fatia mais confortável de construir.

Nomeie fatias pelo resultado: "assessor emite a minuta sem sair do sistema", não "release 1" ou "MVP".

## 5. Esqueleto ambulante

A primeira fatia é o caminho mais fino que funciona de ponta a ponta: entrada de dados feia, sem otimização, um único caso feliz — mas atravessando todos os componentes reais e podendo ser observada com um usuário de verdade.

Ela existe para responder três perguntas de uma vez: o fluxo faz sentido para o usuário? a arquitetura se sustenta? conseguimos medir o resultado?

Erro comum: confundir esqueleto ambulante com protótipo. O esqueleto é software real, integrado, só que mínimo. Se não pode ser usado por alguém de fora do time, ainda não anda.

## 6. Escrita das histórias

O formato "Como [papel], quero [ação], para [benefício]" serve para lembrar de conversar, não para ser preenchido mecanicamente. Uma história é um lembrete de conversa mais os detalhes que a conversa produziu.

Boas práticas:

- O "para" precisa conter benefício real, não repetição da ação. "Para poder exportar" não é benefício; "para enviar ao cartório sem redigitar" é.
- História grande demais para uma fatia deve ser dividida por regra de negócio, tipo de dado ou caso de uso — nunca por camada técnica.
- Anexe à história as perguntas em aberto. Elas viram itens de descoberta.
- Uma história que ninguém consegue explicar por que existe é candidata a ser removida do mapa.

## 7. Descoberta contínua dentro da entrega

Entrega e descoberta correm juntas. Enquanto uma fatia é construída, a próxima está sendo investigada e a anterior está sendo medida. O mapa é o lugar onde os três estados se encontram: marque cada história com `descoberta`, `pronta`, `em entrega` ou `medindo`.

Depois de cada fatia entregue, revisite o mapa com o que foi aprendido. Histórias mudam de fatia, morrem ou nascem. Mapa que não muda depois do contato com o usuário é sinal de que ninguém olhou os dados.

## 8. Sinais de que o mapa está errado

- Não dá para ler a espinha dorsal em voz alta como uma frase que faz sentido.
- Os cartões da espinha são nomes de telas ou de módulos do sistema.
- Todas as histórias estão na primeira fatia.
- As fatias se chamam "fase 1, fase 2, fase 3" e não dizem o que a pessoa consegue fazer.
- Existe uma fatia chamada "infraestrutura", "modelagem" ou "cadastros".
- Ninguém além de quem construiu o mapa consegue explicá-lo.
