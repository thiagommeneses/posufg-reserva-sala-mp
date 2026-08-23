# Canvas de Declaração do Problema — v3 (dia zero)

**DAPIA · Sprint 0, Semana 1**
Projeto Reserva de Espaços (MP-GO)
Equipe: André Pereira Teles, Thiago Marques Meneses e Marco Antônio dos Santos Silva

> Versão escrita como se nenhuma linha de código existisse ainda. Declara o problema
> original: reserva de sala inteiramente manual, por telefone e planilha.
>
> As versões anteriores continuam no diretório: a v1 traz a procedência de cada número e
> a v2 é a mesma declaração em formato enxuto, ambas partindo do sistema já entregue.

---

## TÍTULO DO PROBLEMA

**Reservar sala depende de telefone e planilha — e de a pessoa certa atender.**

---

## CONTEXTO / SITUAÇÃO ATUAL
*quando o problema ocorre?*

Todo dia útil, sempre que alguém precisa de uma sala:

- descobre as salas perguntando a colegas ou indo até a porta;
- liga para o departamento para saber se está livre;
- liga de novo para efetivar a reserva;
- só descobre o conflito na hora da reunião.

Não existe sistema. O controle é planilha por departamento, e-mail e agenda de papel.

---

## PROBLEMA PRINCIPAL
*qual é a causa-raiz do problema?*

**Não existe registro único de disponibilidade.**

Por isso toda consulta e toda reserva passam por uma pessoa no telefone.

A disponibilidade está na planilha de um setor e na cabeça de quem atende. Ninguém sabe,
de fora, o que está de fato ocupado.

---

## IMPACTO QUANTIFICÁVEL
*qual é o impacto mensurável (incluir unidades)?*

- 2 ligações por reserva: uma para confirmar, outra para reservar.
- 4 canais paralelos em uso: planilha, e-mail, telefone e agenda de papel.
- 1 planilha por departamento, sem padrão comum.
- 0 normas escritas sobre uso de espaços no MP-GO.

**Sem medição hoje:**

- tempo até conseguir a reserva (min);
- taxa de no-show (%);
- salas vazias em horário bloqueado (h/semana).

---

## USUÁRIOS AFETADOS
*quem sofre com o problema frequentemente?*

- **Servidor que precisa de sala** — todo dia.
- **Quem atende o telefone e controla a planilha** — interrompido a cada pedido.
- **Chefia e administração** — não enxerga a ocupação real.
- **Colega que chega na sala** — encontra ocupada ou vazia e bloqueada.
- **Quem organiza evento ou audiência** — depende de confirmação verbal.

---

## POSSÍVEIS CAUSAS
*de onde vêm as causas do problema?*

- Não existe sistema: o controle é planilha, e-mail e papel.
- Nenhuma norma escrita de uso de espaços; cada departamento criou a sua.
- Disponibilidade e regra passam por telefone, sem registro.
- O inventário das salas não é público: ninguém sabe capacidade nem equipamento.
- Faltar à reserva não tem consequência.
- Cancelar depende de avisar alguém — e muitos não avisam.

---

## ALTERNATIVAS
*o que fazem hoje para contornar o problema?*

- Ligar para o departamento e pedir a sala.
- Perguntar a colegas qual sala costuma estar livre.
- Ir até a porta e olhar.
- Ocupar sala vazia sem avisar.
- Reservar por garantia e cancelar depois — ou não cancelar.
- Fazer a reunião em outro lugar ou remarcar.

---

## NECESSIDADES / EXPECTATIVAS
*o que é esperado pelos usuários afetados?*

- Ver a disponibilidade sem ligar para ninguém.
- Reservar sozinho, na hora.
- Encontrar sala por capacidade e equipamento.
- Cancelar e remarcar sem depender de terceiros.
- Administração enxergando a ocupação real.
- Regra igual para todos os departamentos.

---

## IMPACTOS DO PROBLEMA
*como o usuário se sente e quais as consequências?*

**Como se sente**

- Perde tempo e depende da boa vontade de quem atende.
- Inseguro: não tem confirmação escrita.
- Frustrado ao chegar e achar a sala ocupada.

**Consequências**

- Sala bloqueada e vazia.
- Conflito na porta; reunião atrasada ou remarcada.
- Quem atende o telefone, interrompido o dia todo.
- Sem histórico para planejar o uso dos espaços.

---

## SOLUÇÃO DESEJADA
*qual sistema resolve o problema?*

Sistema web de reserva com calendário único. Depois, uma camada inteligente sobre ele.

**MVP: acabar com o telefone**

- Calendário único: se não está no sistema, não está reservado.
- Busca por capacidade e equipamento.
- Reserva, cancelamento e remarcação pelo próprio usuário, sem aprovação.
- Check-in; sem check-in em 15 min, a sala volta a ficar livre.
- Painel de ocupação e bloqueio de manutenção.

**Evolução: camada de IA**

- Assistente que tira dúvidas de uso citando normas de outras instituições.
- Agentes que resolvem conflito e exceção, e escalam o resto.

---

## Origem das afirmações

| Afirmação | Fonte |
|---|---|
| Fricção de descoberta, no-show, fragmentação, shadow booking | `requirements-po.md` §1 |
| Conflito de expectativas (agilidade × controle) | `requirements-po.md`, abertura |
| Três pilares Pareto do MVP | `requirements-po.md` §4 e `PRD.md` |
| Janela de check-in de 15 minutos | `PRD.md`; `reservations/services.py` |
| Ausência de norma escrita no MP-GO | `README.md` §1.1 (busca no portal + servidora do MP-GO) |
| Ligar para confirmar e ligar para reservar | relato do PO |
