# Frontmatter Schema

Every Wiki note MUST have this frontmatter:

```yaml
---
Title: "Note Title"
Author: "IGRIS Knowledge Base"
Reference: "internal" | "<url>"
ContentType: ["markdown"]
Created: YYYY-MM-DD
Processed: true | false
tags: ["source", "<domain>"]
sources:
  - "Raw/Sources/<domain>/<filename>"
---
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| Title | string | Human-readable title |
| Author | string | Source author or "IGRIS Knowledge Base" |
| Reference | string | "internal" or URL |
| ContentType | list | Always ["markdown"] for notes |
| Created | date | ISO date (YYYY-MM-DD) |
| Processed | bool | false=raw, true=compiled to Wiki |
| tags | list | Must start with category tag |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| sources | list | Paths to Raw source files |
| aliases | list | Alternative names for the note |
| status | string | draft / active / archived |
| version | string | Semantic version |
