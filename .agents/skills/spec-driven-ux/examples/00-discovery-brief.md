# Brief de Descoberta — Painel de Triagem de Manifestações

| Campo | Valor |
|---|---|
| Autor | Equipe de produto |
| Data | 2026-08-10 |
| Status | em validação |

> **Exemplo didático.** Caso institucional fictício, usado para mostrar o nível de detalhe esperado e o uso das marcações `[FATO]` / `[HIPÓTESE]` / `[A VALIDAR]`. Os números são ilustrativos.

## 1. Problema e resultado de negócio

- **Problema observado:** `[FATO]` As manifestações que chegam pelo canal externo são triadas manualmente: o assessor abre cada documento, identifica o assunto, classifica e distribui. Em entrevistas (n=6), todos descreveram o mesmo processo de leitura integral do PDF antes de qualquer decisão.
- **Quem sente, com que frequência:** `[FATO]` Assessores de triagem, diariamente, em lote concentrado no início da manhã.
- **O que fazem hoje sem o produto:** `[FATO]` Planilha compartilhada para controlar o que já foi triado, mais o sistema legado para registrar a distribuição. Dois assessores mantêm anotações paralelas em caderno porque a planilha "trava quando três pessoas abrem junto".
- **Resultado de negócio esperado (OUT-01):** Reduzir o tempo entre a chegada da manifestação e a distribuição ao responsável.
- **Linha de base:** `[FATO]` Média de 2,3 dias úteis entre protocolo e distribuição, medida sobre 400 registros do último trimestre.
- **Resultado secundário (OUT-02):** Reduzir a redistribuição por classificação errada. Linha de base: `[FATO]` 18% das manifestações mudam de área após a primeira distribuição.

## 2. Proposta de valor

> Para **assessores de triagem** que **recebem um volume diário de manifestações não classificadas e decidem o encaminhamento lendo cada documento por inteiro**, o **Painel de Triagem** é um **espaço de trabalho de fila** que **apresenta o essencial de cada manifestação já extraído e sugere a classificação, mantendo a decisão com o assessor**. Diferente de **ler o PDF no sistema legado**, ele **elimina a leitura integral no caso comum e registra a decisão em um clique**.

- **Segmento primário:** assessores de triagem da unidade central.
- **Segmentos secundários (fora do primeiro release):** coordenadores que acompanham a fila; unidades regionais com fluxo distinto.

## 3. Usuários

| Perfil | Papel | Baseado em | Ficha |
|---|---|---|---|
| Assessor de triagem | usa | pesquisa (n=6 entrevistas + 2 observações) | `01-perfil-usuario.md` |
| Coordenador da unidade | decide adoção | pesquisa (n=2) | — |
| Cidadão que protocolou | é afetado | `[HIPÓTESE]` sem contato direto ainda | — |

Conflito registrado: `[FATO]` o coordenador pediu ranking de produtividade por assessor; os assessores relataram que métrica individual os levaria a "escolher os fáceis primeiro". Decisão adiada para depois da primeira fatia, registrada como risco de adoção.

## 4. Alternativas atuais

| Alternativa | Tipo | Por que usam | Onde falha |
|---|---|---|---|
| Sistema legado + leitura do PDF | direta | é o registro oficial | exige leitura integral; sem visão de fila |
| Planilha compartilhada | improviso | mostra o que já foi feito | conflito de edição, dado duplicado |
| Caderno pessoal | improviso | confiável para a pessoa | invisível para o time |
| Não fazer nada (acumular) | improviso | absorve pico de volume | gera o atraso que queremos atacar |

## 5. Inovação de valor

- **Eliminar:** leitura integral do documento no caso comum.
- **Reduzir:** número de telas entre ver a manifestação e distribuí-la (hoje 4).
- **Elevar/criar:** confiança na sugestão automática — ela precisa mostrar de onde tirou a conclusão, não só o resultado.
- **Frase testável:** o assessor decide o encaminhamento do caso comum em menos de 40 segundos, sem abrir o PDF, e sem aumentar a taxa de redistribuição.

## 6. Hipóteses de risco

| ID | Hipótese | Tipo | Dor se errada | Experimento |
|---|---|---|---|---|
| H-01 | O assessor confia na extração automática o bastante para decidir sem abrir o documento | valor | alta — produto vira uma tela a mais | EXP-01 |
| H-02 | Os campos extraídos (assunto, órgão, prazo, requerente) bastam para o caso comum | usabilidade | alta — retrabalho de escopo | EXP-01 |
| H-03 | A classificação automática acerta acima do patamar aceitável para sugestão | viabilidade | média — vira triagem manual assistida | EXP-02 |
| H-04 | O volume diário cabe em uma fila única sem partição por área | negócio | baixa — ajuste de configuração | — |

## 7. Restrições inegociáveis

- **Normativas:** trilha de auditoria de quem visualizou e quem classificou; sigilo de manifestações restritas; acessibilidade exigida em sistema público.
- **Técnicas:** o sistema legado é a fonte da verdade da distribuição — o painel registra nele, não substitui.
- **Organizacionais:** mudança de fluxo precisa de aval da coordenação antes do piloto.

## 8. Decisão

- [x] Validar H-01 e H-02 antes de seguir para o mapeamento completo
- [ ] Seguir para mapeamento (fase 2)
- [ ] Descartar / repensar a aposta

**Justificativa:** H-01 e H-02 sustentam a proposta inteira e custam uma semana para testar com protótipo estático sobre 20 manifestações reais. Construir a fila antes de saber se o assessor dispensa o PDF seria apostar o release inteiro na parte não verificada.
