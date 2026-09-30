---
name: llm-wiki-maintain
description: >-
  Periodic maintenance of the knowledge base.
  USE WHEN: scheduled maintenance; wiki cleanup; updating outdated notes.
---

# LLM Wiki Maintain Skill

## Steps

1. Review `Wiki/Logs/` for outdated entries
2. Check `Schema/source-manifest.jsonl` for uncovered sources
3. Rebuild `Wiki/catalog.jsonl` and indexes
4. Archive obsolete notes to `Wiki/Archive/`
5. Update cross-links between notes

## Schedule

- **Weekly**: Run lint + build
- **Monthly**: Full maintenance cycle
- **On demand**: When adding new domain knowledge
