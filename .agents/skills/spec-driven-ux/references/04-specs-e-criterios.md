# Specs e critérios de aceite — fundamentos operacionais

Guia da fase 3: transformar fatias do mapa em documentos que sustentam implementação por humano ou agente.

## Índice

1. O que uma spec é e o que não é
2. Anatomia da spec
3. Regras de negócio
4. Critérios de aceite
5. Requisitos não funcionais
6. Dados, contratos e integrações
7. Telemetria
8. Specs para agentes de código
9. Revisão antes de entregar
10. Exemplos de reescrita

## 1. O que uma spec é e o que não é

**É** o contrato de comportamento: o que o sistema faz, para quem, sob quais regras, e como saberemos que funcionou.

**Não é** desenho de implementação. Nomes de classes, estrutura de pastas e escolha de biblioteca pertencem à decisão técnica, não à spec — a menos que sejam restrição imposta de fora (sistema legado, política institucional, contrato).

Spec-driven funciona quando a spec é a fonte da verdade e o código é a consequência. Quando o código diverge, corrige-se a spec deliberadamente, com registro — não por omissão.

## 2. Anatomia da spec

Seções obrigatórias, na ordem (template pronto em `templates/06-feature-spec.md`):

1. **Cabeçalho e rastreabilidade** — ID da spec, fatia, `OUT`/`ACT`/`STP`/`US` associados, autor, data, status.
2. **Resultado esperado** — que comportamento muda e qual métrica reflete isso.
3. **Contexto e usuários** — perfis afetados, cenário de uso, volume esperado.
4. **Escopo** e **não-escopo** — o segundo evita metade das discussões de entrega.
5. **Fluxo principal** — passo a passo do caminho feliz.
6. **Fluxos alternativos e de erro** — o que acontece quando falta permissão, dado, rede, ou o usuário desiste no meio.
7. **Regras de negócio** numeradas (`RN-xx`).
8. **Critérios de aceite** (`AC-xx.y`).
9. **Requisitos não funcionais** aplicáveis.
10. **Dados e contratos** — entidades, campos, validações, integrações.
11. **Telemetria** — eventos e como se lê o resultado.
12. **Riscos e hipóteses abertas** (`H-xx`) — o que ainda não sabemos e como isso pode afetar.
13. **Definição de pronto**.

Seção que não se aplica: escreva "não se aplica" com o motivo em uma linha. Seção apagada some junto com a decisão de tê-la ignorado.

## 3. Regras de negócio

Uma regra por item, numerada, testável, sem ambiguidade e sem embutir interface.

Bom: `RN-03: Pedido acima de R$ 5.000 exige aprovação de gestor antes do faturamento.`

Ruim: `RN-03: Pedidos grandes precisam de aprovação.` (o que é grande? aprovação de quem? antes do quê?)

Onde houver limite numérico, informe unidade, arredondamento e fuso quando temporal. "Prazo de 5 dias" precisa dizer: corridos ou úteis, contados a partir de qual evento, em qual fuso.

## 4. Critérios de aceite

Formato Dado/Quando/Então, um comportamento por critério:

```gherkin
AC-014.1 — Emissão dentro do limite
  Dado que sou assessor com perfil "redator"
  E o processo 4471 está com status "apto"
  Quando solicito a emissão da minuta
  Então o sistema gera o documento em até 5 segundos
  E registra o evento "minuta_emitida" com o ID do processo
```

Cobertura mínima por história — se faltar alguma linha, provavelmente falta pensamento:

- Caminho feliz.
- Pelo menos um caminho alternativo legítimo.
- Falha de permissão ou de estado inválido.
- Falha de dependência externa (integração indisponível, timeout).
- Limites: valor mínimo/máximo, vazio, tamanho, concorrência.

Regras de escrita:

- Sujeito é o usuário ou o sistema, nunca "o desenvolvedor".
- Verifique efeito observável: o que aparece, o que muda de estado, o que é registrado.
- Nada de "e/ou" e "etc." — cada ramo vira um critério.
- Se um critério só pode ser verificado lendo o banco, questione: existe efeito visível equivalente? Se realmente não existe (rotina de retaguarda), explicite o meio de verificação.

## 5. Requisitos não funcionais

Inclua apenas os que se aplicam, sempre com número. RNF sem número é desejo.

| Categoria | Formato mínimo |
|---|---|
| Desempenho | percentil, operação e carga: "p95 até 800 ms em consulta com 10 mil registros" |
| Disponibilidade | janela, degradação aceitável e comportamento em falha |
| Segurança | autenticação, autorização por perfil, proteção de dados sensíveis, trilha |
| Privacidade | dados pessoais tratados, base legal, retenção, anonimização |
| Auditoria | o que é registrado, por quanto tempo, quem consulta |
| Acessibilidade | nível-alvo e verificações obrigatórias |
| Compatibilidade | navegadores, dispositivos, resoluções, versões de integração |
| Observabilidade | logs, alertas, o que dispara ação |
| Localização | idioma, formatos de data, moeda, fuso |

## 6. Dados, contratos e integrações

Para cada entidade tocada: campos, tipo, obrigatoriedade, valores válidos, valor padrão, origem e quem pode ver.

Para cada integração: endpoint ou canal, autenticação, campos enviados e recebidos, comportamento em timeout, política de repetição, idempotência e o que o usuário vê enquanto isso.

Estados: liste os estados possíveis e as transições permitidas. Transição não listada é transição proibida — diga isso explicitamente.

## 7. Telemetria

Sem instrumentação, a fase 4 não acontece. Para cada spec, defina:

- **Eventos** com nome estável, momento do disparo e propriedades.
- **Métrica de resultado** ligada ao `OUT` e a leitura que confirma sucesso.
- **Métrica de guarda** que detecta piora colateral.
- **Recorte** por perfil de usuário quando os perfis tiverem expectativas diferentes.

## 8. Specs para agentes de código

Quando a spec vai alimentar um agente de implementação, acrescente:

- **Restrições técnicas herdadas**: linguagem, framework, versões, padrões do repositório, caminhos de arquivo.
- **Ordem de execução sugerida** em passos verificáveis, cada um com como testar.
- **Fora de limites**: arquivos e módulos que não devem ser tocados.
- **Critérios verificáveis por comando**: teste que roda, saída esperada, comando de lint/build.
- **Ambiguidade zero em nomes**: se o campo é `dataEmissao`, diga; agente inventa nome plausível e cria divergência silenciosa.

Um agente não pergunta como um dev sênior pergunta — ele preenche a lacuna com algo verossímil. Toda lacuna que você deixar volta como decisão que ninguém tomou.

## 9. Revisão antes de entregar

Passe esta lista antes de considerar a spec pronta:

- [ ] Cada história rastreia até um `OUT`.
- [ ] Existe métrica que diz se o resultado aconteceu.
- [ ] Não-escopo escrito.
- [ ] Todo critério é observável e independente de implementação.
- [ ] Falhas de dependência e permissão cobertas.
- [ ] RNFs aplicáveis com número.
- [ ] Hipóteses abertas listadas, não escondidas.
- [ ] Um dev sem contexto começaria hoje sem perguntar nada essencial.
- [ ] Um QA escreveria os testes só com esta spec.
- [ ] Nenhuma afirmação inventada; tudo marcado `[FATO]`/`[HIPÓTESE]`/`[A VALIDAR]`.

## 10. Exemplos de reescrita

**Critério que testa implementação**

Antes: `Então o registro é inserido na tabela minutas com status 2.`
Depois: `Então a minuta aparece na lista do usuário com o status "Emitida" e fica disponível para download.`

**História sem benefício**

Antes: `Como usuário, quero exportar em CSV, para poder exportar em CSV.`
Depois: `Como analista de conciliação, quero exportar o extrato em CSV, para conferir no meu modelo de planilha sem redigitar os lançamentos.`

**Regra ambígua**

Antes: `O sistema deve ser rápido.`
Depois: `RNF-01: A busca responde em até 1,5 s no percentil 95, com base de 500 mil documentos e 50 usuários simultâneos.`

**Fatia técnica virando fatia de resultado**

Antes: `Fatia 1 — modelagem de dados e autenticação.`
Depois: `Fatia 1 — o assessor faz login e consulta um processo real pelo número, vendo dados corretos; demais fluxos indisponíveis.`
