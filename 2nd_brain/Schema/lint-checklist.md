# Lint Checklist

Run before committing Wiki changes:

## 1. Frontmatter Validation
- [ ] All required fields present
- [ ] Created date is valid ISO
- [ ] Tags follow naming conventions
- [ ] sources list points to existing Raw files

## 2. Content Validation
- [ ] Every claim has a `[[source]]` link
- [ ] No orphan notes (notes with no links to them)
- [ ] No broken wiki-links
- [ ] Code blocks have language tags
- [ ] No TODO/FIXME left uncommented

## 3. Structure Validation
- [ ] Note is in correct Wiki/ subdirectory
- [ ] Note title matches filename
- [ ] No duplicate notes (check catalog.jsonl)
- [ ] Cross-links are bidirectional

## 4. Coverage Validation
- [ ] All Raw sources have at least one compiled note
- [ ] source-manifest.jsonl is up to date
- [ ] catalog.jsonl reflects current state
