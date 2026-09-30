# Wiki Tool Command Reference

## Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `doctor` | Health check: folders, Python version, catalog, manifest | `python scripts/wiki_tool.py doctor` |
| `build` | Generate catalog.jsonl, index.md, per-folder indexes | `python scripts/wiki_tool.py build` |
| `lint` | Validate frontmatter, tags, source links | `python scripts/wiki_tool.py lint` |
| `source-scan` | List Raw sources, update manifest | `python scripts/wiki_tool.py source-scan` |
| `source-scan --update --accept-covered` | Mark covered sources | `python scripts/wiki_tool.py source-scan --update` |
| `source-lint` | Validate source frontmatter and coverage | `python scripts/wiki_tool.py source-lint` |
| `source-delta` | Show uncovered Raw sources | `python scripts/wiki_tool.py source-delta` |
| `source-coverage` | Coverage report | `python scripts/wiki_tool.py source-coverage` |
| `search-catalog --query "text"` | Full-text search compiled notes | `python scripts/wiki_tool.py search-catalog --query "python"` |
| `log --title "x" --details "y"` | Append to Wiki/log.md | `python scripts/wiki_tool.py log --title "Added note" --details "..."` |

## Options

| Flag | Description |
|------|-------------|
| `--root <path>` | Wiki root directory (default: current dir) |
| `--verbose` | Show detailed output |
| `--fix` | Auto-fix issues where possible |
| `--dry-run` | Show what would change without writing |
