---
name: llm-wiki-lint
description: >-
  Validate Wiki integrity before commits.
  USE WHEN: checking wiki health; before committing changes;
  running CI checks on knowledge base.
---

# LLM Wiki Lint Skill

## Steps

1. `python scripts/wiki_tool.py doctor`
2. `python scripts/wiki_tool.py build`
3. `python scripts/wiki_tool.py lint`
4. `python scripts/wiki_tool.py source-lint`
5. `python scripts/audit_public.py`
6. Fix any failures before proceeding

## Expected Output

All checks should pass with 0 errors. Warnings are acceptable.
