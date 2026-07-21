---
name: ide-code-engineering
description: Governs IDE and code engineering tasks: project setup, code generation, refactoring, debugging, testing, CI/CD, code review, architecture patterns.
pipeline_stage: Execution
triggers: [ide, code, project, setup, refactor, debug, test, ci, cd, pipeline, architecture, pattern, generate, scaffold, boilerplate, template, linter, formatter, debugger]
defers_to: []
used_by: [reprompt-loop, skill-loader]
---

## Scope
Applies when the user requests IDE/code engineering work: project
scaffolding, code generation, refactoring, debugging, testing,
CI/CD pipelines, or code architecture guidance.

## Procedure
1. **Understand the goal**: new project, feature, bug fix, refactor, optimization
2. **Select tech stack**: language, framework, build tools, testing framework
3. **Project structure**: follow established patterns for the chosen stack
4. **Code generation**: complete, runnable, with proper error handling
5. **Testing**: unit tests, integration tests, e2e tests
6. **Documentation**: inline comments, README, API docs
7. **CI/CD**: pipeline configuration, deployment scripts

## Project Structures
### Python (FastAPI)
```
project/
  app/
    __init__.py
    main.py
    api/
    core/
    models/
    services/
    utils/
  tests/
  docs/
  pyproject.toml
  README.md
```

### TypeScript (Next.js)
```
project/
  src/
    app/
    components/
    hooks/
    lib/
    types/
    utils/
  public/
  tests/
  package.json
  tsconfig.json
  README.md
```

### Embedded (Arduino/ESP32)
```
project/
  src/
    main.cpp
    config.h
    drivers/
    sensors/
    actuators/
    communication/
  lib/
  test/
  platformio.ini
  README.md
```

## Code Quality Standards
- Functions: max 30 lines, single responsibility
- Files: max 300 lines, single module
- Comments: explain WHY, not WHAT
- Naming: descriptive, no abbreviations except common ones
- Error handling: always catch specific exceptions
- Type hints: mandatory for Python, TypeScript

## Anti-patterns
- Generating code without tests
- Missing error handling
- Hardcoded credentials or magic numbers
- Not following language idioms (PEP 8, ESLint rules)
- Missing type hints in Python/TypeScript
- No README or setup instructions
