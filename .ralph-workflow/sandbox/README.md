# Ralph Workflow Sandbox

Roda o `opencode` dentro de um container Docker isolado. Isso limita o que o
agente pode tocar no host (vê apenas o diretório do projeto + credenciais do
opencode) e garante um ambiente reproducível.

## Pré-requisitos

- Docker Engine 20.10+ ou Docker Desktop (não é necessário `docker sandbox`)
- Imagem construída via `./.ralph-workflow/sandbox/build.sh`
- Credenciais do opencode já configuradas no host em
  `~/.local/share/opencode/` (gere com `opencode auth login` uma vez)

## Build

```bash
./.ralph-workflow/sandbox/build.sh
# rebuild forçado:
./.ralph-workflow/sandbox/build.sh --no-cache
```

A imagem padrão é `ralph-workflow-sandbox:latest`. Sobrescreva com
`RALPH_SANDBOX_IMAGE` e `RALPH_SANDBOX_TAG`.

## Uso

Wrapper genérico (pode rodar qualquer comando dentro do sandbox):

```bash
./.ralph-workflow/sandbox/run.sh opencode run --help
./.ralph-workflow/sandbox/run.sh bash      # shell interativo
```

Os scripts do Ralph já usam o sandbox por padrão:

```bash
./.ralph-workflow/ralph-once.sh                  # 1 iteração (sandbox)
./.ralph-workflow/afk-ralph.sh 10                # até 10 iterações (sandbox)
```

Para rodar direto no host (sem container) — útil em CI ou debug — use a flag
`--no-sandbox` ou a env var `RALPH_NO_SANDBOX=1`:

```bash
./.ralph-workflow/ralph-once.sh --no-sandbox
./.ralph-workflow/afk-ralph.sh --no-sandbox 10
RALPH_NO_SANDBOX=1 ./.ralph-workflow/ralph-once.sh
```

A flag `--sandbox` também existe como opção explícita (é o default):

```bash
./.ralph-workflow/afk-ralph.sh --sandbox 10
```

Flag na CLI sempre vence sobre a env var.

## O que o sandbox monta

| Host                              | Container                              | Modo |
| --------------------------------- | -------------------------------------- | ---- |
| `<projeto>`                       | `/workspace`                           | rw   |
| `~/.local/share/opencode`         | `/home/ralph/.local/share/opencode`    | rw   |
| `~/.cache/opencode` (se existir)  | `/home/ralph/.cache/opencode`          | rw   |
| `~/.gitconfig` (se existir)       | `/home/ralph/.gitconfig`               | ro   |

## O que o sandbox bloqueia

- Acesso ao `$HOME` do host fora das pastas listadas acima
- Privilégios adicionais (`--security-opt no-new-privileges`)
- Todas as capabilities exceto `CHOWN`, `SETUID`, `SETGID`, `DAC_OVERRIDE`
  (necessárias para operações básicas de arquivos)

O container tem rede aberta para alcançar os provedores LLM configurados.
