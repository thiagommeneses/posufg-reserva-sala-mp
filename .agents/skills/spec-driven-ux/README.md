# spec-driven-ux

Skill para desenvolvimento spec-driven guiado por estratégia de UX, mapeamento de histórias e design centrado no usuário — fundamentos de Jaime Levy (*UX Strategy*), Jeff Patton (*User Story Mapping*) e Travis Lowdermilk (*Design Centrado no Usuário*).

Cobre o fluxo inteiro: descoberta e validação de estratégia → mapa de histórias e fatiamento → specs executáveis com critérios de aceite → medição e iteração. Serve para SaaS, e-commerce, sistemas institucionais/jurídicos e ferramentas de mercado financeiro.

## Estrutura

```
spec-driven-ux/
├── SKILL.md          instruções principais (é o que entra em contexto quando a skill dispara)
├── README.md         este arquivo
├── references/       5 arquivos, lidos sob demanda conforme a fase
├── templates/        9 artefatos em branco (00 a 08)
├── examples/         caso completo preenchido, do brief à spec
└── scripts/          storymap.py — validação e renderização do mapa
```

## Instalação

- **Claude.ai / app:** abra o arquivo `.skill` e use **Save skill**.
- **Claude Code:** copie a pasta para `~/.claude/skills/spec-driven-ux/` (uso pessoal) ou `.claude/skills/spec-driven-ux/` dentro do repositório (uso do time), preservando a estrutura.
- A skill dispara sozinha em pedidos de discovery, story map, priorização, PRD, spec ou critérios de aceite. Também pode ser chamada pelo nome.

## Script

Requer PyYAML (`pip install pyyaml`).

```bash
python scripts/storymap.py validar caminho/story-map.yaml
python scripts/storymap.py md      caminho/story-map.yaml -o story-map.md
python scripts/storymap.py html    caminho/story-map.yaml -o story-map.html
```

O validador acusa ID duplicado ou fora de padrão, história sem fatia ou sem resultado, referência a fatia/resultado/hipótese inexistente, passo sem história, fatia vazia e ausência (ou excesso) de esqueleto ambulante. Retorna código 1 quando há erro — dá para usar em pipeline.

## Onde ficam os artefatos que você produzir

Dentro do projeto, não dentro da skill. A skill permanece genérica; o material preenchido vive junto do código:

```
seu-projeto/
└── docs/produto/
    ├── 00-discovery-brief.md
    ├── story-map.yaml
    └── specs/SPEC-01-....md
```
