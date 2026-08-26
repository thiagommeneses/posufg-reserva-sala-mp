# SPEC-__ — [Nome da funcionalidade]

| Campo | Valor |
|---|---|
| Fatia | FAT-__ |
| Rastreabilidade | OUT-__ › ACT-__ › STP-__.__ › US-___ |
| Autor / Data | |
| Status | rascunho / em revisão / aprovada / implementada / obsoleta |
| Versão | 1.0 |

> Toda afirmação não verificada deve estar marcada como `[HIPÓTESE]`. Seção que não se aplica: escreva "não se aplica" e o motivo — não apague.

## 1. Resultado esperado

- **Comportamento que muda:**
- **Resultado de negócio (OUT-__):**
- **Métrica de resultado e linha de base:**
- **Métrica de guarda:**
- **Prazo de leitura:** (em quanto tempo saberemos)

## 2. Contexto e usuários

- **Perfis afetados:** (link para `01-perfil-usuario.md`)
- **Cenário de uso:** quando, onde, sob qual pressão
- **Volume esperado:** usuários simultâneos, operações/dia, tamanho de dados

## 3. Escopo

**Está incluído:**
- 

**NÃO está incluído (e por quê):**
- 

## 4. Fluxo principal

1. 
2. 
3. 

## 5. Fluxos alternativos e de erro

| ID | Situação | Comportamento esperado |
|---|---|---|
| ALT-01 | | |
| ERR-01 | Sem permissão | |
| ERR-02 | Dependência externa indisponível | |
| ERR-03 | Dado inválido/ausente | |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | |

## 7. Critérios de aceite

Formato completo em `07-criterios-aceite.md`.

```gherkin
AC-__.1 — [nome do cenário]
  Dado que [contexto/estado inicial]
  E [condição adicional]
  Quando [ação do usuário]
  Então [efeito observável]
  E [registro/estado resultante]
```

Cobertura obrigatória: caminho feliz, alternativo legítimo, permissão/estado inválido, falha de dependência, limites.

## 8. Requisitos não funcionais

| ID | Categoria | Requisito (com número) |
|---|---|---|
| RNF-01 | Desempenho | |
| RNF-02 | Segurança | |
| RNF-03 | Privacidade | |
| RNF-04 | Acessibilidade | |
| RNF-05 | Auditoria | |

## 9. Dados e contratos

**Entidades e campos**

| Entidade.Campo | Tipo | Obrigatório | Valores válidos | Origem | Visível para |
|---|---|---|---|---|---|

**Estados e transições permitidas**

| De | Para | Condição | Quem pode |
|---|---|---|---|

**Integrações**

| Sistema | Operação | Dados enviados/recebidos | Timeout | Repetição | Idempotência | O que o usuário vê |
|---|---|---|---|---|---|---|

## 10. Telemetria

| Evento | Quando dispara | Propriedades | Serve para medir |
|---|---|---|---|

## 11. Riscos e hipóteses abertas

| ID | Descrição | Impacto se confirmado | Como resolver |
|---|---|---|---|
| H-__ | | | |

## 12. Restrições de implementação (quando a spec alimenta um agente)

- **Stack e versões:**
- **Padrões do repositório / caminhos:**
- **Fora de limites (não tocar):**
- **Comandos de verificação:** teste, lint, build
- **Ordem sugerida de execução:** passos verificáveis

## 13. Definição de pronto

- [ ] Todos os critérios de aceite passam
- [ ] RNFs verificados
- [ ] Telemetria instrumentada e conferida
- [ ] Fluxos de erro testados
- [ ] Acessibilidade verificada
- [ ] Documentação/uso atualizado
- [ ] Métrica de resultado com leitura agendada
