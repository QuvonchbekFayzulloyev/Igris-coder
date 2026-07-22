---
name: pipeline-verify
description: Use when verifying changes — always run the appropriate verification pipeline (pytest, desktop tests, bundle) before claiming done. Never assume tests pass without running them.
---

# Verification Pipeline

Always verify before claiming done. Run the appropriate checks:

## Backend (igris-cli)
```powershell
python -m pytest tests\ -v --tb=short
```

Expect: 64 passed, 80 pre-existing Windows PermissionErrors on `tmp_path`-dependent tests.

## Frontend (desktop)
```powershell
cd desktop
npm run typecheck
npm run test
npm run build
```

## Full CI
```powershell
# backend
python -m pytest tests\ -v --tb=short
# frontend (if changed)
cd desktop
npx tsc -b && npx vitest run && npx vite build
npm run verify:bundle
```

## Smoke tests (live MCP)
```powershell
python tests\smoke_mcp.py
python tests\smoke_knowledge_server.py
```

## Rules
- Run tests; don't infer they'd pass.
- If tests fail, diagnose and fix before proceeding.
- Pre-existing PermissionErrors (80 total) are acceptable — they're Windows `tmp_path`-related.
- New failures = regression = must fix.
