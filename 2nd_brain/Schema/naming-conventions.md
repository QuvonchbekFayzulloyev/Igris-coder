# Naming Conventions

## Files

- **Wiki notes**: `Topic-Name.md` (Title-Case, hyphens, no spaces)
- **Raw sources**: `source-name.md` (lowercase, hyphens)
- **Templates**: `template-name.md` (lowercase, hyphens)
- **Logs**: `YYYY-MM-DD-title.md`

## Directories

- **Wiki/**: `Topics/`, `Concepts/`, `Entities/`, `Projects/`, `Logs/`
- **Raw/**: `Sources/<domain>/`, `Files/`
- **Schema/**: flat files, no subdirectories

## Tags

- Lowercase, hyphen-separated
- Category tags: `source`, `topic`, `concept`, `entity`, `project`, `log`
- Domain tags: `engineering`, `data-analytics`, `windows`, `linux`, `code`, `math`
- Status tags: `draft`, `active`, `archived`

## Wiki Links

- Use double brackets: `[[Topic-Name]]`
- Aliases: `[[Topic-Name|Display Text]]`
- Every claim must link to its source in Raw
