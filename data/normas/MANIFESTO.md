# Corpus documental — Normas de uso de espaços físicos em instituições públicas

Base documental do assistente de consulta (Trabalho Final — Engenharia de Software para
Modelos de IA).

## Contexto

O MP-GO controla a reserva de salas de forma manual, em planilha, sem norma institucional
publicada. Não há, no portal do MP-GO nem no do TJGO, regulamento público sobre uso e
reserva de espaços — apenas atos normativos de outras matérias e o Regimento Interno.

O corpus reúne, então, regulamentos de instituições públicas brasileiras que **já
normatizaram** o uso de seus espaços. Isso serve a dois propósitos reais:

1. apoiar a redação de uma norma própria, por comparação; e
2. responder dúvidas operacionais recorrentes (quem pode reservar, com quanta
   antecedência, se cabe uso por terceiros, se há cobrança, o que é vedado).

Para o RAG, a heterogeneidade entre instituições é vantagem: permite perguntas
comparativas, que exercitam o retrieval e tornam a exibição das fontes significativa.

## Como baixar

A coleta é automatizada. O manifesto legível por máquina fica em `fontes.json`; o
download é feito por um comando de gerenciamento, no mesmo padrão do `seed_data`:

```bash
docker compose exec web python manage.py baixar_normas
```

O comando é **idempotente** — arquivos já presentes são ignorados. Opções:

| Opção | Efeito |
|---|---|
| `--force` | Baixa novamente o que já existe em disco |
| `--somente 3 5 9` | Baixa apenas os ids informados |

Os arquivos são gravados nesta pasta com o padrão `NN-slug.ext`, e a extensão vem do
`Content-Type` da resposta (`.pdf`, `.html` ou `.txt`).

Ao final o comando lista o que falhou, com a URL, e avisa se o total ficar abaixo dos
**20 documentos** exigidos. Para as falhas, baixe manualmente pelo navegador e salve
seguindo o mesmo padrão de nome — por exemplo, `05-ifba-paulo-afonso-normas-auditorio.pdf`.

Páginas HTML podem ser salvas como PDF pelo navegador (Imprimir → Salvar como PDF) se a
extração do HTML vier suja de menu e rodapé.

A lista traz 22 documentos brasileiros mais 3 complementares, para dar folga sobre o
mínimo.

## Legenda

- **Verificado** — conteúdo baixado e conferido em 26/07/2026
- **A conferir** — URL vinda de busca, ainda não aberta

---

## Documentos principais (Brasil)

### Regulamentos de auditório e salas

| # | Instituição | Documento | Formato | Status | URL |
|---|---|---|---|---|---|
| 01 | UFPA — IFCH | Regulamento nº 1/2025 — Uso do Auditório do IFCH | PDF | Verificado | https://ifch.ufpa.br/images/PDF/2025/Regula_Auditrio.pdf |
| 02 | UFS — BICEN | Normas de Utilização do Auditório da Biblioteca Central | PDF | Verificado | https://bibliotecas.ufs.br/uploads/page_attach/path/14421/NORMAS_UTILIZACAO_AUDITORIO_BICEN-UFS.pdf |
| 03 | IFAL — Maceió | Resolução nº 14/2020 — Regulamento do Auditório Oscar Sátyro | PDF | A conferir | https://www2.ifal.edu.br/campus/maceio/concamp-1/anexo-da-resolucao-n-14-2020-regulamento-de-uso-do-auditorio-oscar-satyro.pdf |
| 04 | UFES — CCE | Regulamento e Orientações do Auditório | PDF | A conferir | https://cce.ufes.br/sites/cce.ufes.br/files/field/anexo/regulamento_orientacoes_auditorio_0.pdf |
| 05 | IFBA — Paulo Afonso | Normas para Utilização do Auditório | PDF | A conferir | https://portal.ifba.edu.br/paulo-afonso/documentos.paf/institucional/manuais-normas-regulamentos/norma-para-utilizacao-do-auditorio.pdf/@@download/file/Norma%20para%20utiliza%C3%A7%C3%A3o%20do%20Audit%C3%B3rio.pdf |
| 06 | UFES — CT | Regras de Utilização do Auditório CT1 e Sala de Reuniões CT4 | HTML | A conferir | https://ct.ufes.br/regras-de-utiliza%C3%A7%C3%A3o-do-audit%C3%B3rio-ct1-e-sala-de-reuni%C3%B5es-ct4 |
| 07 | USP — IFSC | Normas de Utilização do Auditório Prof. Sérgio Mascarenhas | HTML | A conferir | https://www2.ifsc.usp.br/portal-ifsc/normas-de-utilizacao-auditorio-professor-sergio-mascarenhas/ |
| 08 | UNIFAP | Instrução de Uso — Auditório Multiuso | HTML | A conferir | https://www2.unifap.br/auditoriomultiuso/instrucao-de-uso/ |

### Resoluções institucionais sobre espaços físicos

| # | Instituição | Documento | Formato | Status | URL |
|---|---|---|---|---|---|
| 09 | UFFS | Resolução nº 177/CONSC RE/2025 — Auditórios e salas de videoconferência | HTML | A conferir | http://www.uffs.edu.br/atos-normativos/resolucao/coscre/2025-0177 |
| 10 | UFPI | Legislação PREX — Resolução CAD nº 192/2026 (uso de espaços e taxas) | HTML | A conferir | https://ufpi.br/legislacao-prex |
| 11 | UFMS — PROADI | Gestão de Espaços Físicos — normas de cessão e valores | HTML | A conferir | https://proadi.ufms.br/proadi/gestaodesespacosfisicos/ |
| 12 | IFC — Concórdia | Resolução nº 16/2017 — Espaços passíveis de autorização para cessão | HTML | A conferir | https://concampus.concordia.ifc.edu.br/espacos-fisicos-e-bens-passiveis-de-autorizacao-para-cessao-de-acordo-com-a-resolucao-n16-2017/ |
| 13 | IFBA — Santo Antônio | Portaria nº 01/2017 — Regulamento para cessão de espaço físico | HTML | A conferir | https://portal.ifba.edu.br/santoantonio/menu-a-direita/regulamento-para-cessao-de-espaco-fisico |
| 14 | IFMG — Santa Luzia | Regulamento de Uso dos Espaços | HTML | A conferir | https://www.ifmg.edu.br/santaluzia/dap/regulamento-de-acesso-ao-campus |

### Procedimentos operacionais de reserva

| # | Instituição | Documento | Formato | Status | URL |
|---|---|---|---|---|---|
| 15 | UFU — PREFE | Reserva de Espaço Físico | HTML | A conferir | https://prefe.ufu.br/assunto/reserva-de-espaco-fisico |
| 16 | UFU — PREFE | Reserva de Auditório | HTML | A conferir | https://prefe.ufu.br/servicos/logistica-prefeitura-universitaria/reserva-de-auditorio |
| 17 | UFU — PREFE | Espaços Físicos — catálogo e condições | HTML | A conferir | https://prefe.ufu.br/espacos-fisicos |
| 18 | UFG — Letras | Reserva de Salas e Espaços | HTML | A conferir | https://letras.ufg.br/p/22472-reserva-de-salas-e-espacos |
| 19 | UFRGS — FCE | Agendamento de Espaços Físicos | HTML | A conferir | https://www.ufrgs.br/fce/agendamento/ |

### Contexto jurídico e institucional local

| # | Instituição | Documento | Formato | Status | URL |
|---|---|---|---|---|---|
| 20 | TCU | Ocupação por terceiros de espaço físico em bens imóveis de órgãos públicos | PDF | A conferir | https://revista.tcu.gov.br/ojs/index.php/RTCU/article/download/468/519/0 |
| 21 | CNMP | Gestão de recursos físicos — imóveis, manutenção e cessão | HTML | A conferir | https://www.cnmp.mp.br/portal/institucional/731-institucional/comissoes-institucional/comissao-de-controle-administrativo-e-financeiro/ordenador-de-despesas/gestao-de-recursos-fisicos/4049-imoveis-manutencao-alugueis-e-acessibilidade |
| 22 | TJGO | Regimento Interno (abril/2024) | PDF | A conferir | https://docs.tjgo.jus.br/publicacoes/regimento_Interno/regimentoInterno_042024.pdf |

---

## Complementares (opcionais)

Instituições públicas portuguesas. Ampliam a base além de 20 e permitem perguntas
comparativas internacionais. Usar apenas se algum link brasileiro cair.

| # | Instituição | Documento | Formato | URL |
|---|---|---|---|---|
| 23 | Universidade NOVA de Lisboa | Regulamento de Utilização dos Auditórios, Sala do Senado e Átrio | PDF | https://www.unl.pt/wp-content/uploads/2024/07/regulamento_auditorios_2016_0.pdf |
| 24 | INFARMED | Regulamento de utilização do auditório e salas de reunião | PDF | https://www.infarmed.pt/documents/15786/1604161/Regulamento.pdf/ea2ef4f2-4b49-4f70-8e88-ba1a36505370?version=1.3 |
| 25 | Universidade de Lisboa — FMD | Regulamento do Auditório Prof. Simões dos Santos | HTML | https://auditorio.fmd.ulisboa.pt/?page_id=68 |

---

## Perguntas de validação sugeridas

Guardem estas para testar o retrieval e alimentar a seção de resultados do relatório.
Todas exigem recuperar trechos de documentos diferentes:

1. Com quanta antecedência devo solicitar a reserva de um auditório?
2. Quais instituições cobram taxa pelo uso do espaço e quais não cobram?
3. Uma empresa privada pode usar o auditório para um evento comercial?
4. É permitido consumir alimentos e bebidas dentro do auditório?
5. Que penalidades se aplica a quem descumpre o regulamento?
6. Quem decide quando dois setores pedem a mesma data?
7. Eventos político-partidários podem ocorrer nesses espaços?
8. Qual o horário de funcionamento típico dos auditórios?
9. Que informações o formulário de solicitação precisa conter?
10. Quem responde por danos ao equipamento durante o evento?

As perguntas 2, 3 e 7 são as mais valiosas para a demonstração: a resposta correta exige
sintetizar regras divergentes entre instituições, o que evidencia o RAG funcionando e
torna a exibição das fontes indispensável.
