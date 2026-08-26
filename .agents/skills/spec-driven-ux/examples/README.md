# Exemplo completo — Painel de Triagem de Manifestações

Caso institucional **fictício**, usado para mostrar o padrão de qualidade esperado em cada fase. Leia na ordem:

| Ordem | Arquivo | O que demonstra |
|---|---|---|
| 1 | `00-discovery-brief.md` | Fase 1 — problema com linha de base numérica, proposta de valor, alternativas atuais (inclusive improvisos), hipóteses ordenadas por risco e uso das marcações `[FATO]`/`[HIPÓTESE]` |
| 2 | `04-story-map.yaml` | Fase 2 — espinha dorsal narrativa, histórias ligadas a resultados e hipóteses, fatias nomeadas pelo resultado, esqueleto ambulante e fora de escopo explícito |
| 3 | `05-story-map.md` | Saída de `scripts/storymap.py md` sobre o YAML acima |
| 4 | `08-plano-de-fatias.md` | Ordem das fatias por aprendizado, critérios de corte decididos antecipadamente e registro de mudanças |
| 5 | `06-spec-01-resumo-estruturado.md` | Fase 3 — spec completa, com critérios de aceite para falha e limites, RNFs numerados, contratos, telemetria e as seções extras exigidas quando há IA embutida |

Três coisas que valem atenção ao comparar com o seu caso:

- **Toda métrica tem linha de base.** "Reduzir o tempo de triagem" sem o "2,3 dias úteis" não permite dizer se funcionou.
- **O não-escopo é tão específico quanto o escopo**, e vem com o motivo — é o que evita a renegociação a cada reunião.
- **Os critérios de aceite cobrem a falha**, não só o caminho feliz. Na prática é onde o produto ganha ou perde a confiança do usuário.

Para reproduzir a validação e a renderização:

```bash
python scripts/storymap.py validar examples/04-story-map.yaml
python scripts/storymap.py md examples/04-story-map.yaml -o examples/05-story-map.md
python scripts/storymap.py html examples/04-story-map.yaml -o /tmp/mapa.html
```
