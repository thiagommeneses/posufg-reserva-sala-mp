# Experimentos de validação — Reserva de Espaços (MP-GO)

Nenhum experimento abaixo foi executado nesta revisão. Critérios de confirmação/refutação ficam definidos *antes* de rodar. Resultados brutos permanecem vazios de propósito.

---

# Experimento — EXP-01

| Campo | Valor |
|---|---|
| Hipótese testada | H-01, H-03 |
| Tipo de risco | valor / negócio |
| Responsável | a definir (produto + contato no MP-GO) |
| Período | não iniciado |

## Hipótese

> Acreditamos que **servidores já gastam tempo em planilha/telefone e trocariam isso por um calendário único se ele for a fonte da verdade**, e que **o admin aceita gravar política operacional mesmo sem norma formal**. Se for verdade, esperamos observar **relato da última reserva pelo canal informal + disposição concreta de abandonar a planilha *se* o horário no sistema for respeitado**, e o admin nomear 2–3 regras que hoje aplica de cabeça (duração, antecedência, quem não reserva auditório).

## Método

Entrevista guiada de 30 minutos, 5 pessoas: 4 do perfil A (servidor que reserva) e 1 do perfil B (quem opera a planilha), recrutadas por indicação da servidora já citada — sem apresentar a solução no início.

Roteiro mínimo (Lowdermilk / Levy):

1. Conte a última vez que precisou de uma sala. O que fez, minuto a minuto.
2. Quais ferramentas, ramais, planilhas, pessoas.
3. O momento de maior atrito e o que custou (tempo, reunião perdida, constrangimento).
4. O que já tentaram e por que voltaram ao jeito antigo.
5. Só no fim: mostrar o fluxo atual de `/spaces/` → reserva (protótipo vivo, não mock). Observar se perguntam “e se eu não for?” e “quem manda na Alfa?”.

Não perguntar “você usaria?”.

## Critérios definidos ANTES de rodar

- **Confirma se:** pelo menos 4 de 5 descrevem canal informal na última reserva real; pelo menos 3 relatam conflito ou sala vazia reservada nos últimos 60 dias; o operador da planilha enuncia regras que hoje não estão no sistema.
- **Refuta se:** a última reserva da maioria já é outro sistema único (Agenda/Bookings) que eles consideram suficiente; ou ninguém relata custo real — só “seria legal ter”.
- **Inconclusivo se:** amostra só de um departamento, ou entrevistas contaminadas por demonstração no início.

## Execução

Não executado.

## Resultados brutos

—

## Conclusão

- [ ] Confirmou  - [ ] Refutou  - [ ] Inconclusivo

**Interpretação:** pendente.

**Decisão tomada:** pendente.

**Impacto no mapa e nas specs:** H-01, H-03, FAT-01 (adoção), FAT-05 (políticas), SPEC-02.

---

# Experimento — EXP-02

| Campo | Valor |
|---|---|
| Hipótese testada | H-02 |
| Tipo de risco | usabilidade |
| Responsável | a definir |
| Período | não iniciado — exige FAT-04 em homologação ou QR de teste em 1 sala |

## Hipótese

> Acreditamos que **na hora H o servidor consegue confirmar presença em até 15 minutos, na porta, com o celular, autenticado**. Se for verdade, esperamos observar **check-in concluído sem ajuda do aplicador, dentro da janela, na primeira tentativa**.

## Método

Teste de guerrilha na porta de **uma** sala real (ou maquete da porta no corredor), com 5 servidores do perfil A que tenham uma reserva de teste naquele horário. Tarefa: “Sua reunião é nesta sala. Faça o que você faria ao chegar.” Sem instrução sobre QR, login ou janela.

Observar (não perguntar primeiro): o que olham, se sacam o celular, se abandonam, se pedem ajuda, tempo até o status mudar.

Depois, 5 minutos de conversa: o que acharam que o código era; se fariam isso todo dia.

## Critérios definidos ANTES de rodar

- **Confirma se:** pelo menos 4 de 5 concluem o check-in sozinhos em até 2 minutos após apontar o celular para o QR; nenhum descreve o login como bloqueio intransponível no contexto institucional (já autenticado ou consegue autenticar na hora).
- **Refuta se:** 3 ou mais abandonam, pedem para o aplicador, ou dizem que fariam check-in “depois na mesa” — o que na prática não acontece. Ou a autenticação na porta mata o fluxo.
- **Inconclusivo se:** rede Wi-Fi do corredor cai, QR mal impresso, ou participantes são da equipe de desenvolvimento.

## Execução

Não executado. Bloqueado até existir GET de check-in (SPEC-01).

## Resultados brutos

—

## Conclusão

- [ ] Confirmou  - [ ] Refutou  - [ ] Inconclusivo

**Interpretação:** pendente.

**Decisão tomada:** pendente. Se refutar por autenticação na porta, a spec precisa de caminho autenticado prévio (link na reserva / sessão já aberta), não de QR anônimo — anônimo está fora de escopo por auditoria.

**Impacto no mapa e nas specs:** H-02, FAT-04, SPEC-01.

---

# Experimento — EXP-03

| Campo | Valor |
|---|---|
| Hipótese testada | H-04 |
| Tipo de risco | valor / IA |
| Responsável | a definir (já existe conjunto em `data/avaliacao/`) |
| Período | amostragem periódica; não iniciado como rotina de produto |

## Hipótese

> Acreditamos que **uma resposta sem trecho de fonte, ou que misture instituições como se fossem regra do MP-GO, destrói confiança mais do que a ausência do assistente**. Se for verdade, esperamos observar **rejeição explícita da resposta “órfã” por quem redige norma, e aceitação da recusa honesta quando o corpus não cobre**.

## Método

Amostragem humana de 20 perguntas: 10 do conjunto `data/avaliacao/perguntas.json` e 10 inventadas por um redator (perfil E), incluindo pelo menos 3 que o corpus não cobre (“qual a norma do MP-GO para antecedência?”).

Para cada resposta, o avaliador marca: (a) todas as afirmações têm fonte visível; (b) nenhuma instituição é apresentada como se fosse o MP-GO; (c) quando não há contexto, o sistema recusou em vez de inventar.

Já existe avaliação LLM-as-judge em `data/avaliacao/`; este experimento é **humano**, porque H-04 é confiança, não BLEU.

## Critérios definidos ANTES de rodar

- **Confirma se:** 100% das perguntas sem contexto recuperado resultam em recusa visível; 0 respostas apresentam o texto como norma do MP-GO; o redator declara que usaria as respostas *com fonte* como insumo de minuta.
- **Refuta se:** o avaliador encontra afirmação sem âncora em mais de 2 de 20; ou o sistema responde “a norma do MP-GO é…” a partir de outra instituição.
- **Inconclusivo se:** o índice documental está desatualizado ou a chave Groq falha no lote.

## Execução

Não executado nesta revisão. `[FATO]` o código da UI já evita chamar o LLM quando a recuperação vem vazia (`used_context: false`) — isso é implementação da guarda, não validação de H-04 com usuário.

## Resultados brutos

—

## Conclusão

- [ ] Confirmou  - [ ] Refutou  - [ ] Inconclusivo

**Interpretação:** pendente.

**Decisão tomada:** pendente. Nenhuma spec nova do assistente nesta leva; o experimento alimenta se FAT-03 precisa evoluir.

**Impacto no mapa e nas specs:** H-04, FAT-03 (já entregue), brief OUT-04.
