# Adaptações por domínio

O método é o mesmo; o que muda são os usuários típicos, as restrições inegociáveis, as métricas que importam e os riscos que precisam aparecer cedo na spec. Leia a seção do domínio antes de conduzir a descoberta.

## Índice

1. Institucional, público e jurídico
2. E-commerce e varejo digital
3. SaaS e produtos por assinatura
4. Mercado financeiro e ferramentas de trading
5. Sistemas com IA embutida (qualquer domínio)

## 1. Institucional, público e jurídico

**Papéis distintos que quase nunca coincidem:** quem opera (assessor, analista, servidor), quem decide a adoção (chefia, gestor de área), quem custeia (orçamento/TI) e quem é afetado sem tocar no sistema (parte, cidadão, advogado externo). Requisitos conflitantes entre eles são a regra — traga-os para a spec.

**Restrições que costumam ser inegociáveis:**
- Base legal e política interna sobre tratamento de dados pessoais e sigilo processual.
- Trilha de auditoria completa: quem viu, quem alterou, quando, o quê.
- Acessibilidade como exigência normativa em sistemas públicos.
- Retenção, temporalidade documental e exigências de preservação.
- Integração com sistemas legados que não mudam no ritmo do projeto.
- Ciclos de aprovação e contratação que afetam prazos mais do que a engenharia.

**Métricas úteis:** tempo de ciclo do processo, retrabalho por devolução, taxa de tarefas concluídas sem suporte, redução de trâmites manuais, backlog em fila.

**Riscos a listar cedo:** dependência de um sistema externo instável, mudança normativa durante a construção, resistência de adoção por perda de autonomia percebida, dado de origem inconsistente.

**Espinha dorsal típica:** receber demanda → triar/classificar → instruir → produzir peça/decisão → revisar → tramitar/publicar → acompanhar.

## 2. E-commerce e varejo digital

**Papéis:** comprador (às vezes diferente de quem paga e de quem recebe), operador de loja, atendimento, fornecedor/estoquista.

**Restrições comuns:** limites da plataforma (tema, apps, checkout fechado), políticas de pagamento e antifraude, prazos e custos de frete, dados fiscais, cadastro de produtos como gargalo real, desempenho em rede móvel.

**Métricas:** conversão por etapa do funil, abandono de carrinho, ticket médio, custo de aquisição, taxa de devolução, tempo até primeiro produto relevante, receita por sessão.

**Cuidado que muda o resultado:** a maior parte dos ganhos vem de reduzir atrito em etapas que já existem, não de features novas. Antes de mapear o novo, mapeie o funil atual com dados reais e ponha o mapa em cima dele.

**Riscos:** dependência de app de terceiro para regra de negócio central, sazonalidade concentrando carga, catálogo com dado sujo, mudança de plataforma sem plano de redirecionamento e SEO.

**Espinha dorsal típica:** descobrir produto → avaliar → decidir → pagar → acompanhar entrega → receber → pós-venda/recompra.

## 3. SaaS e produtos por assinatura

**Papéis:** usuário final, administrador da conta, comprador econômico, time de suporte/sucesso.

**Restrições comuns:** multiempresa e isolamento de dados, papéis e permissões, planos e limites de uso, migração de dados na entrada, integrações esperadas, exigências de conformidade dos clientes maiores.

**Métricas:** tempo até o primeiro valor, ativação por conta, uso recorrente por papel, expansão de assentos, churn e seus precursores, volume de suporte por funcionalidade.

**Ponto de atenção:** o onboarding costuma ser a área com maior retorno e a menos especificada. Mapeie-o como jornada própria, com fatias próprias.

**Riscos:** funcionalidade construída para um cliente grande virando dívida do produto, limites de plano definidos sem base de custo, permissões desenhadas tarde e reescritas inteiras depois.

**Espinha dorsal típica:** avaliar → contratar → configurar conta → trazer dados → executar tarefa central → colaborar → medir → renovar/expandir.

## 4. Mercado financeiro e ferramentas de trading

**Papéis:** operador/trader, analista, gestor de risco, desenvolvedor de estratégia. Perfis com fluência alta no domínio e tolerância baixíssima a erro silencioso.

**Restrições que dominam o desenho:**
- **Latência e frescor do dado**: defina explicitamente a idade máxima aceitável do dado exibido e o que acontece quando ela é excedida — dado velho apresentado como atual é falha grave, não detalhe visual.
- **Integridade e reconciliação**: fonte de preço, tratamento de ajustes, fuso e horário de pregão, dados faltantes.
- **Estados de mercado**: pré-abertura, leilão, pregão, after, feriado, circuit breaker. Cada um muda o comportamento correto da tela.
- **Auditoria de decisão**: registro do que foi mostrado no momento da ação.
- **Conformidade**: material informativo x recomendação de investimento têm exigências distintas; deixe claro na spec em qual categoria o produto se enquadra e quais avisos são obrigatórios.

**Métricas de produto** (distintas de resultado de operação): tempo até identificar a situação, erros de operação por engano de interface, cobertura de alerta relevante, tempo de recuperação após queda de conexão.

**Riscos a listar cedo:** dependência de provedor de dados único, backtest com viés de sobrevivência ou look-ahead, exibição de resultado simulado sem distinção clara do real, degradação silenciosa em falha de feed.

**Regra de honestidade:** desempenho passado ou simulado precisa estar rotulado como tal na interface, com premissas visíveis (custos, slippage, período). Isso é requisito de spec, não recomendação de estilo.

**Espinha dorsal típica:** definir hipótese/estratégia → monitorar mercado → identificar oportunidade → dimensionar risco → executar → acompanhar posição → registrar e revisar.

## 5. Sistemas com IA embutida (qualquer domínio)

Quando a fatia inclui modelo de linguagem, geração ou classificação automática, a spec ganha seções extras:

- **Contrato de saída**: formato, campos, o que é obrigatório e o que fazer quando o modelo não devolve o formato.
- **Comportamento sob incerteza**: quando o sistema deve dizer que não sabe, quando escala para humano.
- **Revisão humana**: quem revisa, o que pode ser publicado sem revisão, como o revisor corrige.
- **Rastreabilidade da resposta**: fonte usada, versão do prompt e do modelo, entrada registrada.
- **Critérios de aceite adequados à variabilidade**: em vez de saída literal, verifique propriedades — contém os campos exigidos, cita a fonte, respeita o limite de tamanho, não inventa entidade fora do documento de origem.
- **Métrica de qualidade** com amostragem periódica avaliada por humano, e métrica de guarda para intervenção do revisor.
- **Custo e latência por operação**, com comportamento definido quando o limite é atingido.

O erro clássico é especificar a interface e deixar o comportamento do modelo como "conforme o prompt". O prompt é implementação; o comportamento esperado é spec.
