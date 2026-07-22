---
name: mini-cycles
description: Always decompose every task into focused sequential mini work cycles instead of one big loop. Each cycle has a specific goal and tool subset. Verify between cycles.
---

# Mini Work Cycles

Every task is decomposed into focused mini work cycles. No single cycle does everything.

## Standard templates per intent

### code_task
1. plan (read/glob/grep) — Plan architecture and structure
2. scaffold (all tools) — Create project files and config
3. backend (all tools) — Implement backend logic
4. frontend (all tools) — Implement frontend UI
5. test (bash/terminal) — Write and run tests
6. review (read/glob/grep) — Review and fix issues

### bug_fix
1. observe (read) — Reproduce and gather context
2. diagnose (read) — Find root cause
3. patch (code) — Implement fix
4. verify (test) — Verify fix works

### research
1. collect (read) — Gather information
2. analyze (plan) — Analyze collected data
3. summarize (write) — Summarize findings

### command
1. prepare (read) — Understand command and context
2. execute (code) — Run command
3. verify (test) — Check result

## Rules

- Stay in one cycle at a time. Do not do future work.
- Each cycle uses only its allowed tool subset.
- Between cycles, briefly verify output before proceeding.
- If a cycle fails, report and ask before continuing.
