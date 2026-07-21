---
name: windows-first-guard
description: Enforces the project's Windows-first, never-WSL-by-default convention across shell commands, path handling, and setup instructions.
pipeline_stage: Implementation
triggers: [command, code_task, shell, terminal, powershell, wsl]
defers_to: []
used_by: [reprompt-loop, specification-expander]
---

## Scope
Applies whenever a task involves running a command, writing setup
instructions, or generating shell scripts.

## Procedure
1. Default to PowerShell (`pwsh` if present, else `powershell.exe`) for
   any command execution or example command shown to the user.
2. Never invoke or suggest WSL unless the user explicitly names it or
   the target explicitly requires a Linux-only toolchain.
3. Use Windows-style paths in examples (backslashes or raw strings) when
   writing instructions meant to be typed by the user; Python code itself
   should still use `pathlib` for portability rather than hardcoded
   separators.
4. When a package or tool is Linux-only with no native Windows build,
   say so explicitly instead of silently reaching for WSL as a workaround.

## Anti-patterns
- Defaulting example commands to bash/WSL "because it's more common".
- Mixing forward-slash and backslash path examples in the same set of
  instructions.
- Silently assuming a Linux dev environment when the project's stated
  environment is Windows-first.
