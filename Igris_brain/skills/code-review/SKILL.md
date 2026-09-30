---
name: code-review
description: >-
  Systematic code review skill for quality assurance. USE WHEN:
  reviewing code changes, pull requests, or existing code for bugs,
  security issues, performance problems, or style violations.
  Trigger on 'code review', 'tekshirib chiq', 'kodni ko\'rib chiq',
  'review PR', 'audit code'.
---

# Code Review Skill

## Review Checklist

### 1. Correctness
- [ ] Does the code do what it claims?
- [ ] Are edge cases handled?
- [ ] Are error conditions handled?
- [ ] Are return types correct?

### 2. Security
- [ ] Input validation present?
- [ ] SQL injection prevented?
- [ ] XSS vulnerabilities?
- [ ] Secrets not hardcoded?
- [ ] Authentication/authorization checked?

### 3. Performance
- [ ] N+1 queries avoided?
- [ ] Appropriate data structures used?
- [ ] Unnecessary loops/computations?
- [ ] Memory leaks possible?
- [ ] Caching opportunities missed?

### 4. Maintainability
- [ ] Functions are focused (single responsibility)?
- [ ] Variables/functions well-named?
- [ ] Complex logic commented?
- [ ] Tests present and sufficient?
- [ ] DRY (Don't Repeat Yourself)?

### 5. Style
- [ ] Follows project conventions?
- [ ] Consistent formatting?
- [ ] No dead code?
- [ ] No magic numbers?

## Review Output Format

```markdown
## Code Review: [file/path]

### Summary
- **Files reviewed**: X
- **Issues found**: Y (Z critical)
- **Verdict**: Approve / Request Changes / Comment

### Issues

#### 🔴 Critical
1. **[file:line]** — Description
   ```python
   # problematic code
   ```
   **Fix**: How to fix it

#### 🟡 Warning
1. **[file:line]** — Description

#### 💡 Suggestion
1. **[file:line]** — Description

### Positive Notes
- Good: What's done well
```

## Auto-Review Commands

```bash
# Python
python -m py_compile file.py
python -m flake8 file.py
python -m mypy file.py
python -m bandit file.py  # Security

# JavaScript/TypeScript
npm run lint
npx tsc --noEmit

# General
git diff --check  # Whitespace
```
