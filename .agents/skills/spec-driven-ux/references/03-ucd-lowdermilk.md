# Design centrado no usuário — fundamentos operacionais

Base conceitual: Travis Lowdermilk, *User-Centered Design: A Developer's Guide to Building User-Friendly Applications*. Síntese operacional para as fases 1 e 4.

## Índice

1. A premissa
2. Perfis de usuário
3. Métodos de pesquisa e quando usar cada um
4. Teste de usabilidade prático
5. Princípios de design que viram requisito
6. Acessibilidade como requisito, não como caridade
7. Iteração e medição
8. Erros de quem desenvolve

## 1. A premissa

Quem constrói o software é a pessoa menos capaz de julgar se ele é usável, porque conhece o modelo interno. O usuário só tem a interface e as próprias suposições. Esse descompasso não se resolve com boa intenção nem com mais explicação na tela — só com observação.

Duas consequências práticas:

- **Preferência sua não é requisito.** Toda vez que aparecer "acho que o usuário vai preferir", converta em `[HIPÓTESE]` com um jeito barato de verificar.
- **Design não é a camada de tinta no fim.** Decisões de fluxo, vocabulário e modelo mental são tomadas cedo e ficam caras depois.

Em contexto de agente/IA isso é ainda mais forte: é fácil gerar uma tela plausível e difícil perceber que ela resolve o problema errado com elegância.

## 2. Perfis de usuário

Um perfil útil é curto, baseado em evidência e capaz de resolver discussões de escopo. Componentes mínimos:

- **Papel e contexto**: onde e quando usa, em que dispositivo, sob qual pressão de tempo.
- **Objetivo real**: o que a pessoa quer alcançar, que geralmente não é "usar o sistema".
- **Fluência**: com a tarefa (domínio) e com tecnologia — são independentes. Especialista em direito com baixa fluência digital é um perfil comum e mal atendido.
- **Frustrações atuais** com o processo existente, com citação curta quando houver.
- **Restrições**: rede, permissões, política institucional, acessibilidade, dispositivo compartilhado.
- **Como o sucesso se parece** para essa pessoa.

Separe três papéis que costumam ser confundidos: quem **usa**, quem **decide/compra** e quem é **afetado** pelo resultado sem tocar no sistema (o cidadão, o cliente final, a contraparte). Requisitos conflitantes entre eles devem aparecer na spec, não ser resolvidos em silêncio.

Marque cada perfil como baseado em pesquisa ou em suposição. Perfil suposto é ponto de partida legítimo — desde que rotulado.

## 3. Métodos de pesquisa e quando usar cada um

| Método | Bom para | Custo | Cuidado |
|---|---|---|---|
| Entrevista de descoberta | Entender contexto e processo real | Baixo | Não pergunte sobre o futuro hipotético |
| Observação/shadowing | Ver o processo que ninguém descreve corretamente | Médio | Presença altera comportamento; observe mais de uma vez |
| Teste de usabilidade com tarefa | Descobrir onde o fluxo quebra | Baixo | Dar tarefa, não instrução |
| Questionário | Confirmar frequência de algo já conhecido | Baixo | Ruim para descobrir o desconhecido |
| Análise de dados de uso | Onde as pessoas param | Baixo | Diz o quê, nunca o porquê |
| Análise de chamados/suporte | Dor recorrente já documentada | Muito baixo | Enviesado para quem reclama |

Comece pelo mais barato que responde à pergunta. Duas entrevistas bem-feitas valem mais que uma pesquisa de 200 respostas mal formulada.

## 4. Teste de usabilidade prático

Cinco participantes por perfil revelam a maior parte dos problemas graves. Roteiro:

1. **Escolha 3 a 5 tarefas** que representem o resultado prometido na spec. Escreva a tarefa em linguagem do usuário: "descubra se o pedido 4471 já foi enviado", não "use a tela de consulta de pedidos".
2. **Defina antes o critério de sucesso**: conclui sem ajuda, em até X, sem tomar o caminho errado.
3. **Peça para pensar em voz alta.** O silêncio prolongado é dado — anote onde acontece.
4. **Não ajude, não explique, não defenda.** Diante de pergunta, devolva: "o que você acha que aconteceria?".
5. **Registre**: onde hesitou, o vocabulário que usou (diferente do seu), onde desistiu, o que procurou e não achou.
6. **Classifique os achados** por gravidade: impede a tarefa / atrasa muito / incomoda. Só o primeiro grupo bloqueia release.

Vocabulário divergente é o achado mais subestimado: se a pessoa procura "protocolar" e o sistema diz "submeter", é defeito de produto, não de usuário.

## 5. Princípios de design que viram requisito

Converta princípio em critério de aceite verificável, senão vira decoração:

- **Visibilidade do estado**: toda ação com efeito tem feedback em até 1 segundo; ação longa mostra progresso.
- **Linguagem do usuário**: rótulos usam o vocabulário do domínio, verificado em pesquisa.
- **Prevenção antes de mensagem de erro**: restringir entrada inválida vale mais que explicar o erro depois.
- **Erro recuperável**: mensagem diz o que aconteceu, por que e qual o próximo passo — sem código interno como única informação.
- **Consistência**: mesmo conceito, mesmo nome e mesmo lugar em todo o produto.
- **Carga cognitiva mínima**: reconhecer é mais fácil que lembrar; padrões sensatos reduzem decisão.
- **Saída sempre disponível**: cancelar, voltar e desfazer em qualquer fluxo de múltiplas etapas.

## 6. Acessibilidade como requisito

Trate como requisito não funcional obrigatório desde a primeira fatia — retrofit custa muito mais:

- Contraste suficiente e informação nunca transmitida só por cor.
- Operável por teclado, com foco visível e ordem lógica.
- Rótulos programáticos em campos e botões; imagem com texto alternativo.
- Alvos de toque adequados e tolerância a imprecisão.
- Tempo suficiente ou ajustável em operações com limite.

Em sistemas públicos e institucionais isso costuma ser também exigência legal — verifique em `references/05-contextos-de-dominio.md`.

## 7. Iteração e medição

Ciclo curto: hipótese → menor mudança que a testa → observação com usuário → decisão registrada.

Para cada fatia entregue, defina antes:

- **Métrica de resultado**: mudou o que se queria mudar? (conclusão de tarefa, tempo até resultado, retrabalho, adoção)
- **Métrica de guarda**: algo piorou junto? (erros, chamados de suporte, abandono em etapa anterior)

Registre a decisão de cada ciclo — manter, ajustar ou reverter — junto ao ID da história. Isso evita a rediscussão anual da mesma escolha sem ninguém lembrar o motivo.

## 8. Erros de quem desenvolve

- Testar com colegas de time e concluir que está fácil.
- Adicionar opção de configuração para não decidir; toda opção transfere trabalho ao usuário.
- Explicar em tooltip aquilo que deveria ser óbvio no fluxo.
- Confundir "o usuário reclamou" com "o usuário sabe a solução" — ouça o problema, projete a solução.
- Tratar acessibilidade e mensagens de erro como polimento de fim de projeto.
- Escrever a interface no vocabulário do banco de dados.
