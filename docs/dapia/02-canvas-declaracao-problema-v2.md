# Canvas de Declaração do Problema — v2 (enxuta)

**DAPIA · Sprint 0, Semana 1**
Projeto Reserva de Espaços (MP-GO)
Equipe: André Pereira Teles, Thiago Marques Meneses e Marco Antônio dos Santos Silva

> Versão curta, para entrega. A v1 (`01-canvas-declaracao-problema.md`) fica preservada
> como lastro: é lá que estão as fontes de cada número, as marcações de fato e hipótese e
> o detalhamento dos agentes.

---

## TÍTULO DO PROBLEMA

**Uso de espaços sem norma escrita — cada exceção volta para o telefone.**

---

## CONTEXTO / SITUAÇÃO ATUAL
*quando o problema ocorre?*

Todo dia útil, quando o pedido de sala foge do simples:

- dois pedidos para a mesma sala e horário;
- pedido de auditório;
- exceção de duração ou de antecedência;
- dúvida sobre o que fazer ao desocupar a sala.

E no horário marcado, quando ninguém aparece e a sala segue bloqueada.

O sistema atual já resolve o caso simples. A exceção volta para o telefone.

---

## PROBLEMA PRINCIPAL
*qual é a causa-raiz do problema?*

**O MP-GO não tem norma escrita de uso de espaços.**

A regra existe, mas é oral e muda de departamento para departamento.

> "Cada um tem uma regra. Instruções informais, repassadas pelo telefone. Nenhum documento
> formal consolidando isso." — servidora do MP-GO

Sem critério escrito, toda decisão precisa de um humano no circuito.

---

## IMPACTO QUANTIFICÁVEL
*qual é o impacto mensurável (incluir unidades)?*

- 0 normas do MP-GO sobre uso de espaços. 0 no TJGO.
- 24 instituições públicas já publicaram a sua: 25 documentos, 722 trechos indexados.
- Janela de check-in: 15 minutos.
- Liberação de no-show: só quando alguém roda o comando.

**Sem medição hoje:**

- taxa de no-show (%);
- tempo por reserva no canal informal (min);
- ligações por reserva.

---

## USUÁRIOS AFETADOS
*quem sofre com o problema frequentemente?*

- **Servidor que precisa de sala** — todo dia.
- **Quem controla a planilha e atende o telefone** — carrega a regra sozinho.
- **Administrador de espaços** — decide conflito sem critério escrito.
- **Colega que chega na sala** — encontra ocupada ou vazia e bloqueada.
- **Assessoria** — precisaria redigir a norma e não tem base.

---

## POSSÍVEIS CAUSAS
*de onde vêm as causas do problema?*

- Nenhum ato normativo sobre uso de espaços.
- Gestão separada por departamento.
- Regra passada por telefone, sem registro.
- Planilha, e-mail, telefone e agenda física não conversam.
- Faltar à reserva não tem consequência.
- A liberação automática ainda depende de alguém rodar o comando.

---

## ALTERNATIVAS
*o que fazem hoje para contornar o problema?*

- Planilha do setor e ligação.
- Perguntar a quem controla a sala.
- Olhar a porta e ocupar a sala vazia.
- Agenda de recurso no e-mail.
- Desistir e remarcar depois.
- Usar o sistema no caso simples e o telefone na exceção.

---

## NECESSIDADES / EXPECTATIVAS
*o que é esperado pelos usuários afetados?*

- Saber na hora se pode, sem ligar.
- Que o horário confirmado seja respeitado.
- Administrador com controle, sem virar gargalo.
- Decisão rastreável: quem decidiu, quando e com base em quê.
- Resposta com a fonte citada — ou admitir que não há norma.

---

## IMPACTOS DO PROBLEMA
*como o usuário se sente e quais as consequências?*

**Como se sente**

- Refém do telefone.
- Inseguro sobre o que pode ou não pode.
- Sem confiança no canal formal.

**Consequências**

- Sala bloqueada e vazia.
- Conflito na porta.
- Decisão sem rastro para auditar.
- Regra concentrada em poucas pessoas.

---

## SOLUÇÃO DESEJADA
*qual sistema resolve o problema?*

Camada multiagente sobre o sistema atual. Decide o caso não trivial e escala só o que a
norma não cobre.

- **Presença** — confirma check-in e libera no-show sem comando humano.
- **Conflito** — propõe sala ou horário equivalente.
- **Normativo** — responde com base nos 25 regulamentos indexados e cita a fonte.
- **Política** — grava a regra do administrador e registra a decisão.
- **Orquestrador** — resolve ou escala, com trilha.

Reaproveita o RAG e os serviços de check-in já entregues.

**Meta:** decisão fundamentada em até 3 minutos, sem telefone.
