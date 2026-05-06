# ia-clean-code

A Cursor Agent Skill that enforces **Clean Code naming conventions** from
Robert C. Martin's *Clean Code*, Chapter 2 — Meaningful Names.

## What It Does

When the agent writes, modifies, reviews, or refactors code, this skill
ensures that all names (variables, functions, methods, classes, modules)
follow the 16 naming rules from Chapter 2 of Clean Code:

1. Use Intention-Revealing Names
2. Avoid Disinformation
3. Make Meaningful Distinctions
4. Use Pronounceable Names
5. Use Searchable Names
6. Avoid Encodings
7. Avoid Mental Mapping
8. Class Names (nouns)
9. Method Names (verbs)
10. Don't Be Cute
11. Pick One Word per Concept
12. Don't Pun
13. Use Solution Domain Names
14. Use Problem Domain Names
15. Add Meaningful Context
16. Don't Add Gratuitous Context

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Main instructions — condensed rules with short examples |
| `naming-rules.md` | Detailed reference — expanded rules with good/bad Java examples and self-assessment checklist |
| `README.md` | This file |

## Installation

Copy the entire `ia-clean-code/` folder into your project's `.cursor/skills/`
directory:

```bash
cp -r ia-clean-code/ /path/to/your-project/.cursor/skills/ia-clean-code/
```

The agent will automatically discover the skill and apply it during coding
tasks.

## When It Activates

The agent applies this skill whenever it performs:

- Writing new code (variables, functions, classes)
- Modifying or refactoring existing code
- Code review
- Naming decisions of any kind

## Relationship to Other Skills

This skill is **complementary** to behavioral coding skills like
`ai-coding-guidelines` (which covers LLM behavior: think before coding,
simplicity, surgical changes). `ia-clean-code` focuses specifically on
**naming quality and code readability**.

## Source

Robert C. Martin. *Clean Code: A Handbook of Agile Software Craftsmanship*.
Prentice Hall, 2008. Chapter 2: Meaningful Names.

## Future Expansion

This skill currently covers Chapter 2 (Meaningful Names). It can be extended
with additional chapters:

- Chapter 3: Functions
- Chapter 4: Comments
- Chapter 5: Formatting
- Chapter 6: Objects and Data Structures
- Chapter 10: Classes
- Chapter 17: Smells and Heuristics
