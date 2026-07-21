# AGENTS.md

Instructions for any coding agent (igris itself, Claude Code, Cursor,
Aider, or similar) working in this repository. Humans: see
[README.md](README.md) for the project overview instead -- this file is
terse and operational on purpose. Per-module detail lives next to the
code: `igris/README.md`, `igris/core/README.md`,
`igris/core/providers/README.md`, `igris/mcp_servers/README.md`,
`desktop/src/README.md`, `desktop/src/components/README.md`,
`desktop/src/lib/README.md`, `desktop/README.md`.

## What this project is

A local, Claude-Code-style agent: Python backend (FastAPI + MCP
tool-calling, multi-provider LLM Gateway) with an optional Tauri+React
desktop UI. See the root README's architecture diagram before making
structural changes.

## Build & test commands

```powershell
# Backend
cd igris-cli
pip install -e .
python -m pytest tests\ -v              # 125 tests, must all pass before any change is "done"

# Frontend
cd desktop
npm install
npx tsc -b && npx vitest run && npx vite build   # types, tests, build -- all three, not just one
npm run verify:bundle                             # executes the real production bundle in jsdom -- catches runtime errors static checks can't

# Live smoke tests (no mocking, real subprocess MCP servers)
python tests\smoke_mcp.py
python tests\smoke_knowledge_server.py
```

There is no single "run everything" command by design -- backend and
frontend are separate toolchains (Python/pytest, Node/Vitest) and should
be verified separately even when a change touches both.

## Code style

- **Python**: type hints on public functions, `from __future__ import
  annotations`, async for anything touching the network or a subprocess.
  No bare `except:` -- catch specific exceptions and return an actionable
  error string from MCP tools (see `tool-call-reliability`), never let
  one propagate raw to the transport layer.
- **TypeScript**: strict mode is on (`tsconfig.json`) -- it must stay
  that way. Components take typed props, no `any`. Tailwind utility
  classes only, no inline style objects.
- **Both**: no comments that just restate the line below them; comments
  explain *why*, especially for a non-obvious constraint (Windows-first
  shell defaults, a regex that looks over-specific, a threshold value)
  that would otherwise look arbitrary to the next editor.

## Non-negotiable conventions

- **Windows-first.** Default shell is PowerShell. Never suggest or
  default to WSL. `terminal_server.py`'s `shell="auto"` is the reference
  implementation of this rule.
- **Every provider goes through the Gateway** (`core/gateway.py`).
  Nothing outside `core/providers/` and `gateway.py` itself imports a
  specific provider class.
- **Every MCP tool call must be exception-safe.** A connection failure,
  timeout, or bad argument must come back as `"ERROR: <specific reason>"`
  from the tool function itself, never as an unhandled exception. This
  was a real bug, not a hypothetical -- see `mcp_servers/README.md`.
- **State the change type before making it**: Create (new), Update
  (additive, existing callers unaffected), Modify (existing behavior
  changes -- check fan-in first), Delete/Remove. See `change-type-
  discipline`. A Modify disguised as an Update is the most common
  regression source in this codebase's history.
- **Fix root causes, not symptoms.** No workaround that hides a failing
  test or swallows an exception to make the suite green -- see
  `root-cause-fixing-discipline`.
- **Verify before claiming done.** Run the tests; don't infer they'd
  pass. If something can't be verified in the current environment (no
  browser, no Windows, no live Ollama), say so explicitly rather than
  presenting untested work as tested -- see `autonomous-verification-
  loop`. Current known-unverified gap: the Tauri Rust shell, specifically
  the native window/IPC layer -- confirmed blocked by two independent
  causes (no path to Rust 1.85+ here, and separately no real browser/
  webview obtainable either), not just a toolchain version issue. The
  web app itself (`desktop/`'s React code) IS verified by real execution
  -- see `npm run verify:bundle`. Verify the native shell with `cargo
  tauri dev` on Windows via `rustup` before relying on it.

## Where to look first

New to a task in this repo? Read the module `README.md` next to the code
you're about to touch before editing -- each one states its purpose,
boundary (what must NOT live there), and how it's tested. The project's
own hierarchical knowledge base (`igris/core/knowledge_base.py`,
seeded via `igris seed-knowledge`) contains the same information in a
form igris itself queries automatically during its own reprompt loop --
if you're igris working on igris, that's already happening.
