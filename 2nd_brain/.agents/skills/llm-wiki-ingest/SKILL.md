---
name: llm-wiki-ingest
description: >-
  Ingest new source material into the LLM Wiki system.
  USE WHEN: user provides a new document, URL, or code snippet;
  auto-ingest from Web AI tab; adding knowledge to the 2nd Brain.
---

# LLM Wiki Ingest Skill

## When to Use

- User provides a new document, URL, or code snippet
- Auto-ingest from Web AI tab
- Adding knowledge to the 2nd Brain

## Steps

1. Place cleaned Markdown in `Raw/Sources/<domain>/`
2. Run `python scripts/wiki_tool.py source-scan --update`
3. Search `Wiki/catalog.jsonl` for related topics
4. Compile focused Wiki notes in `Wiki/Topics/`, `Wiki/Concepts/`, etc.
5. Link every claim to Raw source in `sources` frontmatter
6. Run `python scripts/wiki_tool.py build && python scripts/wiki_tool.py lint`
7. Update `Wiki/Logs/` with ingest summary

## Quality Checklist

- [ ] Source note has all required frontmatter fields
- [ ] At least one Wiki note compiled from source
- [ ] All claims linked to source
- [ ] No broken wiki-links
- [ ] catalog.jsonl updated
