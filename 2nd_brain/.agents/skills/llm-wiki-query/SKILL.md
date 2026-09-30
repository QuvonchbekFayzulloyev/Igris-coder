---
name: llm-wiki-query
description: >-
  Query the compiled Wiki before generating answers.
  USE WHEN: answering technical questions; when user asks about
  engineering, data analysis, OS operations; when uncertain about
  best practices.
---

# LLM Wiki Query Skill

## When to Use

- Before answering technical questions
- When user asks about engineering, data analysis, OS operations
- When uncertain about best practices

## Steps

1. Parse user question for keywords
2. Run `python scripts/wiki_tool.py search-catalog --query "<keywords>"`
3. Open top-3 relevant Wiki notes
4. If insufficient, open linked Raw sources
5. Cite Wiki note + Raw source in answer
6. Prefer compiled Wiki over broad Raw context

## Answer Format

```
Based on [[Wiki-Note-Name]] (source: Raw/Sources/...):

<answer>

References:
- [[Wiki-Note-1]]
- [[Wiki-Note-2]]
```
