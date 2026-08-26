# Critérios de Aceite — US-___ / SPEC-__

> Um comportamento por critério. Sujeito é o usuário ou o sistema. Verifique efeito observável, nunca implementação.

## Caminho feliz

```gherkin
AC-___.1 — [nome]
  Dado que [perfil e estado inicial]
  Quando [ação]
  Então [efeito visível]
  E [estado/registro resultante]
```

## Caminho alternativo legítimo

```gherkin
AC-___.2 — [nome]
  Dado que [variação de contexto]
  Quando [ação]
  Então [efeito esperado para essa variação]
```

## Permissão e estado inválido

```gherkin
AC-___.3 — Sem permissão
  Dado que sou [perfil sem direito]
  Quando tento [ação]
  Então a ação não é executada
  E vejo [mensagem que diz o que fazer]
```

## Falha de dependência

```gherkin
AC-___.4 — Serviço externo indisponível
  Dado que [integração] não responde em [timeout]
  Quando [ação]
  Então [comportamento degradado definido]
  E o usuário vê [mensagem com próximo passo]
  E o evento [nome] é registrado
```

## Limites

```gherkin
AC-___.5 — [valor mínimo / máximo / vazio / concorrência]
  Dado que [condição de limite]
  Quando [ação]
  Então [comportamento definido no limite]
```

## Critérios com IA generativa (quando aplicável)

Verifique propriedades, não texto literal:

```gherkin
AC-___.6 — Saída estruturada e ancorada
  Dado um documento de origem [tipo]
  Quando solicito [operação]
  Então a resposta contém os campos [lista]
  E cada afirmação referencia trecho do documento de origem
  E nenhuma entidade fora do documento é introduzida
  E a operação conclui em até [tempo] com custo até [limite]
```

## Checklist de qualidade

- [ ] Nenhum critério cita tabela, classe, endpoint interno ou nome de arquivo
- [ ] Nenhum "e/ou", "etc.", "deve ser rápido", "amigável"
- [ ] Cada critério é verificável por observação ou por comando
- [ ] Todos os limites numéricos têm unidade
- [ ] Um QA sem contexto escreveria os testes só com isto
