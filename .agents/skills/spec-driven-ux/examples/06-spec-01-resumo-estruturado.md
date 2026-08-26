# SPEC-01 — Resumo estruturado da manifestação com origem rastreável

| Campo | Valor |
|---|---|
| Fatia | FAT-01 (esqueleto ambulante) |
| Rastreabilidade | OUT-01 › ACT-02 › STP-02.01 › US-010, US-011 |
| Autor / Data | Equipe de produto / 2026-08-14 |
| Status | aprovada |
| Versão | 1.1 |

> **Exemplo didático** (caso institucional fictício), escrito no nível de detalhe que a fase 3 exige — inclusive as seções de IA embutida, já que a extração é feita por modelo.

## 1. Resultado esperado

- **Comportamento que muda:** o assessor decide o encaminhamento do caso comum lendo o resumo, sem abrir o PDF.
- **Resultado de negócio (OUT-01):** distribuição no mesmo dia da chegada.
- **Métrica de resultado:** proporção de triagens concluídas sem abertura do documento original. Linha de base: 0%. Alvo da fatia: 60% dos casos.
- **Métrica de guarda:** taxa de redistribuição por classificação errada não pode subir acima da linha de base (18%).
- **Prazo de leitura:** 3 semanas após o piloto com 8 assessores.

## 2. Contexto e usuários

- **Perfis afetados:** assessor de triagem (usa); coordenador (lê o efeito nas métricas).
- **Cenário de uso:** manhã, lote concentrado, sob pressão de prazo, em desktop de duas telas.
- **Volume esperado:** 120 a 300 manifestações/dia; picos de 500 no início do mês; 8 usuários simultâneos.

## 3. Escopo

**Está incluído:**
- Extração e exibição de assunto, requerente, órgão de origem, prazo legal e pedido principal.
- Indicação do trecho de origem de cada campo, com salto para o ponto correspondente do documento.
- Sinalização explícita quando um campo não pôde ser extraído.

**NÃO está incluído (e por quê):**
- Sugestão de classificação — está em SPEC-02, para permitir medir separadamente o efeito do resumo e o da sugestão.
- Edição do texto extraído — a correção acontece na classificação, não no resumo; evita divergência com o documento oficial.
- Documentos manuscritos ou digitalizados sem camada de texto — tratados como "não extraível" nesta fatia.

## 4. Fluxo principal

1. O assessor abre um item da fila.
2. O sistema exibe o resumo estruturado com os cinco campos.
3. Cada campo mostra um indicador de origem clicável.
4. Ao acionar o indicador, o documento abre no painel lateral posicionado no trecho correspondente, com o trecho destacado.
5. O assessor segue para a classificação (SPEC-02) ou devolve o item à fila.

## 5. Fluxos alternativos e de erro

| ID | Situação | Comportamento esperado |
|---|---|---|
| ALT-01 | Campo não extraível (ausente no documento) | Campo exibido como "não localizado no documento", com atalho para abrir o PDF na íntegra |
| ALT-02 | Documento sem camada de texto | Resumo não é exibido; item marcado como "requer leitura integral" e mantido na fila |
| ALT-03 | Manifestação com restrição de sigilo | Resumo exibido apenas a perfil autorizado; demais veem apenas metadados e o motivo da restrição |
| ERR-01 | Usuário sem permissão de triagem | Item não abre; mensagem indica a quem solicitar acesso |
| ERR-02 | Serviço de extração indisponível ou acima do tempo limite | Item abre direto no documento original, com aviso de que o resumo está indisponível; evento registrado; item não é bloqueado |
| ERR-03 | Extração retorna formato inválido | Tratada como ERR-02; a saída malformada é registrada para diagnóstico, sem ser exibida ao usuário |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | O resumo é derivado exclusivamente do documento protocolado; nenhuma informação de outra fonte é apresentada como campo extraído. |
| RN-02 | Prazo legal é exibido em dias úteis contados a partir da data de protocolo, no fuso de Brasília. |
| RN-03 | Campo com origem não localizável no documento não é exibido, mesmo que o modelo o tenha produzido. |
| RN-04 | Toda visualização de resumo de manifestação restrita é registrada na trilha de auditoria com usuário, item e horário. |
| RN-05 | O resumo nunca substitui o documento como peça oficial; a distribuição registra o documento, não o resumo. |

## 7. Critérios de aceite

```gherkin
AC-010.1 — Resumo do caso comum
  Dado que sou assessor com perfil "triagem"
  E o item 2026-4471 tem documento com camada de texto
  Quando abro o item
  Então vejo assunto, requerente, órgão de origem, prazo legal e pedido principal
  E cada campo apresenta um indicador de origem
  E o resumo aparece em até 3 segundos no percentil 95

AC-011.1 — Salto para o trecho de origem
  Dado que estou vendo o resumo do item 2026-4471
  Quando aciono o indicador de origem do campo "prazo legal"
  Então o documento abre no painel lateral na página do trecho
  E o trecho correspondente aparece destacado

AC-010.2 — Campo não localizado
  Dado que o documento do item 2026-4490 não menciona órgão de origem
  Quando abro o item
  Então o campo "órgão de origem" é exibido como "não localizado no documento"
  E nenhum valor inferido é apresentado nesse campo

AC-010.3 — Documento sem camada de texto
  Dado que o documento do item 2026-4501 é imagem sem texto reconhecível
  Quando abro o item
  Então vejo a marcação "requer leitura integral"
  E o documento original é aberto diretamente
  E o item permanece na fila

AC-010.4 — Restrição de sigilo
  Dado que o item 2026-4510 está marcado como restrito
  E meu perfil não tem autorização para conteúdo restrito
  Quando abro o item
  Então não vejo o resumo nem o conteúdo do documento
  E vejo o motivo da restrição e a quem solicitar acesso
  E a tentativa de acesso é registrada na trilha de auditoria

AC-010.5 — Serviço de extração indisponível
  Dado que o serviço de extração não responde em até 8 segundos
  Quando abro um item
  Então o documento original é aberto sem resumo
  E vejo o aviso de que o resumo está indisponível
  E o evento "resumo_indisponivel" é registrado com o ID do item
  E consigo concluir a triagem normalmente

AC-010.6 — Ancoragem no documento de origem
  Dado qualquer resumo exibido
  Quando comparo cada campo com o documento
  Então todo valor apresentado corresponde a trecho existente no documento
  E nenhuma entidade ausente do documento é introduzida
```

## 8. Requisitos não funcionais

| ID | Categoria | Requisito |
|---|---|---|
| RNF-01 | Desempenho | Resumo renderizado em até 3 s no p95, com 8 usuários simultâneos e documentos de até 40 páginas |
| RNF-02 | Desempenho | Extração assíncrona iniciada na chegada do item; tempo limite de 8 s na exibição |
| RNF-03 | Segurança | Acesso ao conteúdo condicionado ao perfil; itens restritos exigem autorização específica |
| RNF-04 | Privacidade | Dados pessoais do requerente não saem do ambiente institucional; retenção do resumo igual à do item |
| RNF-05 | Auditoria | Registro de visualização (usuário, item, horário, perfil) retido por 5 anos e consultável pela corregedoria |
| RNF-06 | Acessibilidade | Navegação completa por teclado, foco visível, contraste mínimo 4.5:1, campos com rótulo programático |
| RNF-07 | Observabilidade | Alerta quando a taxa de "resumo_indisponivel" ultrapassar 5% em 15 minutos |
| RNF-08 | Custo | Custo médio de extração por item registrado; alerta acima do teto definido pela coordenação |

## 9. Dados e contratos

**Entidades e campos**

| Entidade.Campo | Tipo | Obrigatório | Valores válidos | Origem | Visível para |
|---|---|---|---|---|---|
| Resumo.assunto | texto (≤200) | não | livre | extração | perfil triagem |
| Resumo.requerente | texto (≤120) | não | livre | extração | perfil triagem |
| Resumo.orgaoOrigem | texto (≤120) | não | livre | extração | perfil triagem |
| Resumo.prazoLegal | data | não | data válida ≥ protocolo | extração | perfil triagem |
| Resumo.pedidoPrincipal | texto (≤500) | não | livre | extração | perfil triagem |
| Resumo.ancoras[] | lista | sim | campo, página, trecho | extração | perfil triagem |
| Resumo.status | enum | sim | completo, parcial, indisponivel, nao_extraivel | sistema | perfil triagem |

**Estados e transições permitidas**

| De | Para | Condição | Quem pode |
|---|---|---|---|
| pendente | em_extracao | item recebido | sistema |
| em_extracao | completo / parcial | extração concluída | sistema |
| em_extracao | indisponivel | tempo limite ou erro | sistema |
| pendente | nao_extraivel | documento sem camada de texto | sistema |

Transição não listada é proibida.

**Integrações**

| Sistema | Operação | Dados | Timeout | Repetição | Idempotência | O que o usuário vê |
|---|---|---|---|---|---|---|
| Serviço de extração | extrair(documento) | PDF → campos + âncoras | 8 s | 2 tentativas com espera crescente | chave = hash do documento | indicador de carregamento; após o limite, ERR-02 |
| Repositório documental | obter(documento) | ID → binário | 5 s | 1 tentativa | leitura | erro com opção de tentar de novo |

## 10. Telemetria

| Evento | Quando dispara | Propriedades | Serve para medir |
|---|---|---|---|
| item_aberto | abertura do item | item, perfil, status do resumo | denominador das taxas |
| documento_aberto | abertura do PDF | item, origem (âncora / manual) | métrica de resultado: triagem sem abrir documento |
| ancora_acionada | clique no indicador | item, campo | confiança no resumo (H-01) |
| resumo_indisponivel | falha ou tempo limite | item, motivo | guarda operacional (RNF-07) |
| triagem_concluida | distribuição registrada | item, duração, abriu_documento | resultado OUT-01 |

## 11. Riscos e hipóteses abertas

| ID | Descrição | Impacto se confirmado | Como resolver |
|---|---|---|---|
| H-01 | Assessor pode não confiar no resumo e abrir o PDF de qualquer forma | métrica de resultado não se move | medir `documento_aberto` por item; entrevistar quem sempre abre |
| H-02 | Cinco campos podem não bastar em subgrupos de assunto | retrabalho de escopo | recortar a métrica por tipo de assunto no piloto |
| R-01 | Documentos digitalizados podem ser mais frequentes que o estimado | cobertura menor que o alvo | medir proporção de `nao_extraivel` na primeira semana |

## 12. Restrições de implementação

- **Stack e versões:** conforme o padrão do repositório do painel; sem novas dependências de front sem aval.
- **Fora de limites:** módulo de distribuição do sistema legado — o painel apenas consome a API existente.
- **Comandos de verificação:** suíte de testes do módulo de triagem; verificação de acessibilidade automatizada na pipeline.
- **Ordem sugerida:** (1) contrato e status do resumo com dados simulados; (2) exibição e âncoras; (3) integração real com extração; (4) sigilo e auditoria; (5) telemetria; (6) tratamento de indisponibilidade.
- **Nomes fixos:** os campos da seção 9 são os nomes de contrato — não renomear.

## 13. Definição de pronto

- [ ] AC-010.1 a AC-010.6 e AC-011.1 passando
- [ ] RNF-01 a RNF-08 verificados
- [ ] Eventos de telemetria conferidos em ambiente de homologação
- [ ] Fluxos ERR-01 a ERR-03 testados com falha induzida
- [ ] Acessibilidade verificada por teclado e por leitor de tela
- [ ] Trilha de auditoria validada com a área responsável
- [ ] Leitura da métrica de resultado agendada para 3 semanas após o piloto
