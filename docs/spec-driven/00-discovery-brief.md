# Brief de Descoberta — Reserva de Espaços (MP-GO)


| Campo  | Valor                                              |
| ------ | -------------------------------------------------- |
| Autor  | Revisão spec-driven (síntese do produto existente) |
| Data   | 2026-08-18                                         |
| Status | em validação                                       |


> Revisão as-is de um produto já implementado. Não há pesquisa de campo nova nesta revisão. Cada afirmação relevante está marcada `[FATO]`, `[HIPÓTESE]` ou `[A VALIDAR]`. `[FATO]` aqui significa: dito em documento do produto, citado de servidora do MP-GO no README, ou verificado no código.



## 1. Problema e resultado de negócio

- **Problema observado:** `[FATO]` A reserva de salas no MP-GO é controlada de forma manual e fragmentada. O PO descreve três dores que se reforçam: fricção para descobrir se a sala atende (capacidade, equipamentos), reservas fantasma (no-show) e canais que não conversam (planilha, e-mail, telefone, calendário físico). `[FATO]` Uma servidora do MP-GO com atuação na área descreveu o quadro assim: *"As reservas são gerenciadas por vários departamentos distintos e cada um tem uma regra. Geralmente são instruções informais, repassadas pelo telefone sobre o que tem que fazer quando terminar de usar a sala. Mas nenhum documento formal consolidando isso."* (README, §1.1; confirmação verbal única, não amostra).
- **Quem sente, com que frequência:** `[FATO]` Servidores que precisam de sala e quem opera a planilha/telefone em cada departamento. `[HIPÓTESE]` A dor é diária no expediente, com picos em reuniões de gabinete e eventos. `[A VALIDAR]` Frequência real e concentração por unidade — EXP-01.
- **O que fazem hoje sem o produto:** `[FATO]` Planilha por departamento, telefone com instrução oral, ocupação informal de sala vazia (shadow booking descrito pelo PO). `[FATO]` Não existe norma institucional publicada no portal do MP-GO nem regulamento equivalente localizado no TJGO sobre uso de espaços.
- **Resultado de negócio esperado (OUT-01):** A ocupação visível no calendário corresponde ao uso real da sala — quem reserva comparece ou o horário volta a ficar livre.
- **Como esse resultado é medido hoje / linha de base:** `[A VALIDAR]` Não há medição de no-show, tempo até reservar nem taxa de abandono do canal formal. O produto em código já registra status `no_show` e `checked_in`, mas o auto-release só ocorre quando alguém executa `release_no_shows`; o check-in pela porta (QR) não tem página GET. Sem piloto instrumentado, a linha de base é desconhecida.
- **Resultado secundário (OUT-02):** Servidor encontra e reserva o espaço adequado sem aprovação manual e sem ligar para o setor.
- **Resultado secundário (OUT-03):** Administrador de facilities vê ocupação, bloqueia manutenção e resolve conflito sem planilha paralela.
- **Resultado secundário (OUT-04):** Quem precisa redigir ou consultar regra de uso obtém resposta comparativa ancorada em normas de outras instituições públicas, com a fonte visível.



## 2. Proposta de valor

> Para **servidor do MP-GO que precisa de uma sala agora e hoje depende de planilha, telefone ou ocupação informal**, o **Reserva de Espaços** é um **calendário único de autogestão** que **mostra disponibilidade real, reserva na hora e libera no-show**. Diferente da **planilha setorial + ligação**, ele **é a fonte da verdade: se não está no sistema, o horário não está reservado**.

- **Segmento primário:** servidor que reserva sala para reunião no próprio expediente (usa o sistema).
- **Segmentos secundários:** administrador de espaços (usa o painel); chefia/gestor de área (decide adoção, quase não opera); redator de norma / assessoria que consulta o assistente comparativo (OUT-04, camada acadêmica UFG).

Inovação de valor declarada pelo PO (três pilares Pareto): calendário único, auto-release de no-show, filtros por atributos mínimos. `[FATO]` Os dois primeiros e o terceiro existem em parte no código; o auto-release na porta (QR + agendamento confiável) e as políticas de uso ainda não fecham o ciclo.

## 3. Usuários


| Perfil                                      | Papel (usa / decide / é afetado) | Baseado em                                                         | Ficha                      |
| ------------------------------------------- | -------------------------------- | ------------------------------------------------------------------ | -------------------------- |
| Servidor que reserva                        | usa                              | 1 citação de servidora MP-GO + docs do PO `[HIPÓTESE]` no restante | `01-perfil-usuario.md` § A |
| Administrador de espaços                    | usa                              | docs do PO e jornadas do painel `[HIPÓTESE]`                       | `01-perfil-usuario.md` § B |
| Chefia / gestor de área                     | decide adoção                    | domínio institucional `[HIPÓTESE]`                                 | `01-perfil-usuario.md` § C |
| Colega que chega na sala                    | é afetado                        | shadow booking descrito pelo PO `[HIPÓTESE]`                       | `01-perfil-usuario.md` § D |
| Redator de norma / consulente do assistente | usa (secundário)                 | manifesto do corpus `[FATO]` no propósito; perfil `[HIPÓTESE]`     | `01-perfil-usuario.md` § E |


Conflito típico do domínio `[HIPÓTESE]`: o servidor quer reserva instantânea; o administrador quer controle (duração, quem reserva o quê, prioridade). O PO nomeia isso como “conflito de expectativas”. Políticas de uso (PRD story 9) não foram implementadas — o produto hoje privilegia agilidade.

## 4. Alternativas atuais


| Alternativa                             | Tipo               | Por que as pessoas usam                                                                 | Onde falha                                                                                |
| --------------------------------------- | ------------------ | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Planilha setorial + telefone            | improviso / direta | `[FATO]` é o processo atual no MP-GO; cada departamento tem a sua regra                 | dado divergente; conhecimento na cabeça de quem atende; sem norma verificável             |
| Google Agenda / calendário de sala      | indireta           | `[HIPÓTESE]` já está no e-mail institucional; baixo atrito para quem “dona” a sala      | não filtra por equipamento; não combate no-show; não é calendário único da instituição    |
| Ocupar sala vazia (shadow booking)      | improviso          | `[FATO]` descrito pelo PO como prática que gera conflito quando o dono da reserva chega | quebra confiança no canal formal                                                          |
| Não reservar / remarcar presencialmente | improviso          | evita o rito                                                                            | desperdício de deslocamento; reunião não acontece                                         |
| Sistemas comerciais de room booking     | direta             | `[HIPÓTESE]` conhecidos de outros órgãos                                                | custo, contratação, identidade visual e SSO institucional; não resolvem norma inexistente |


Detalhamento em `02-analise-competitiva.md`.

## 5. Inovação de valor

- **Eliminar:** a necessidade de ligar para saber se a sala está livre; aprovação manual no caso comum (90% segundo o PO — `[HIPÓTESE]` sem medição).
- **Reduzir:** tempo de descoberta (capacidade/equipamento); horários bloqueados por quem não aparece.
- **Elevar/criar:** confiança de que o calendário reflete o mundo físico; rastreio de quem reservou, cancelou e fez check-in; consulta normativa com fonte citada (camada RAG).
- **Frase testável:** um servidor encontra sala adequada e confirma a reserva em menos de 3 minutos, sem telefone; a sala cujo ocupante não fez check-in em 15 minutos volta a aparecer como livre para o próximo.



## 6. Hipóteses de risco


| ID   | Hipótese                                                                                                                                        | Tipo        | Dor se estiver errada                                                                          | Experimento |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------- | ----------- |
| H-01 | Servidores abandonam planilha/telefone e passam a tratar o calendário como fonte da verdade                                                     | valor       | alta — o produto vira canal a mais                                                             | EXP-01      |
| H-02 | Na hora H, o servidor consegue e aceita fazer check-in (na porta ou no celular) com a janela de 15 minutos                                      | usabilidade | alta — auto-release pune quem usou a sala e não fechou o ciclo; ocupação continua mentirosa    | EXP-02      |
| H-03 | É possível definir políticas de uso (duração, antecedência, quem reserva o quê) sem norma formal consolidada, só com regra operacional do admin | negócio     | alta — ou o admin não consegue controlar, ou o servidor volta ao telefone para “pedir exceção” | EXP-01      |
| H-04 | Resposta do assistente sem trecho de fonte visível é pior para a confiança do que não ter assistente                                            | valor / IA  | média — alucinação institucional em órgão de controle                                          | EXP-03      |
| H-05 | Admin precisa reagendar reserva de terceiro (não só cancelar) para resolver conflito sem destruir o compromisso                                 | usabilidade | média — cancelar e pedir para a pessoa refazer aumenta atrito e telefone                       | —           |
| H-06 | Reserva com check-in que já passou do horário, se continuar “ativa”, faz o calendário mentir e o dashboard perder credibilidade                 | valor       | média — OUT-01 não se sustenta no tempo                                                        | —           |


Ordenação por dor: H-01 e H-02 sustentam os pilares Pareto. H-03 é o conflito agilidade vs controle. H-04 é a aposta da camada acadêmica, não do núcleo de reserva.

## 7. Restrições inegociáveis

- **Prazo:** `[FATO]` produto acadêmico/institucional já em evolução contínua; esta revisão não implementa código.
- **Orçamento:** `[HIPÓTESE]` sem linha orçamentária de produto comercial; infra atual é Docker + Groq para LLM.
- **Regulatórias/normativas:** `[FATO]` sistema público — acessibilidade e tratamento de dados pessoais importam; `[FATO]` não há norma própria de espaços no MP-GO, então a regra de negócio do produto não pode se apresentar como regulamento oficial. Trilha de quem alterou reserva de terceiro é exigência de domínio institucional `[HIPÓTESE]` a confirmar com a área.
- **Técnicas/legado:** `[FATO]` Django templates + HTMX; PostgreSQL com exclusion constraint; check-in e auto-release já têm services; Groq é dependência externa do assistente e da busca NL.
- **Organizacionais:** `[FATO]` vários departamentos, cada um com regra informal; adoção exige que o calendário único substitua (não conviva com) a planilha — senão H-01 cai.



## 8. Decisão

- [x] Seguir para mapeamento (fase 2)
- [ ] Validar hipóteses H-01 e H-02 em campo antes de mapear
- [ ] Descartar / repensar a aposta

**Justificativa:** o esqueleto ambulante já está no ar (FAT-01 a FAT-03). Mapear as-is e especificar as fatias que fecham os pilares (check-in na porta, políticas, conclusão automática, conflito admin) é o próximo passo de produto. H-01 e H-02 continuam abertas: os experimentos EXP-01 e EXP-02 devem rodar em paralelo à implementação das specs, não depois de construir o restante. Lacuna registrada: sem linha de base numérica e com n=1 de contato no MP-GO.

**Portão da fase 1:** segmento primário definido; proposta de valor escrita; alternativas atuais mapeadas (incluindo improvisos); hipóteses de risco listadas; resultados OUT-01 a OUT-04 nomeados. Métricas sem linha de base ficam `[A VALIDAR]`.