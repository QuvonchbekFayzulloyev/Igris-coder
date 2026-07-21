# igris-cli Windows Fixes

This document summarizes all fixes applied to make igris-cli work correctly on Windows.

## Issues Fixed

### 1. pytest Temp Directory Permission Error
**Problem**: On Windows, pytest couldn't create temp directories in the system temp folder (`C:\Users\user\AppData\Local\Temp\pytest-of-user`), causing 64 test errors with `PermissionError: [WinError 5] Access is denied`.

**Solution**: Set `PYTEST_DEBUG_TEMPROOT` environment variable to a local project directory.

### 2. MCPManager Error Handling
**Problem**: Unhandled exceptions from `session.call_tool()` could propagate and crash the agent loop instead of returning clean ERROR strings.

**Solution**: Added try/except wrapper in `igris/core/mcp_manager.py:110-115` to catch exceptions and return formatted error messages.

## Quick Setup

### Option 1: Complete Setup (Backend + Frontend + Tauri) - Recommended
```powershell
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli
.\setup_all.ps1
```

### Option 2: Backend Only
```powershell
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli
.\setup_fixes.ps1 -RunTests:$false
```

### Option 3: Command Prompt (Complete)
```cmd
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli
setup_all.bat
```

### Option 4: Manual Steps
```powershell
# Backend
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli
pip install -e .

# Frontend
cd desktop
npm install
npm run build
npm run verify:bundle

# Rust/Tauri (optional, for desktop app)
# Install rustup from https://rustup.rs first, then:
cargo install tauri-cli
```

## Running Tests

### Backend Tests (115 tests)
```bash
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli
$env:PYTEST_DEBUG_TEMPROOT = "C:\Users\user\Desktop\ClaudeCoder\igris-cli\.pytest_tmp"
python -m pytest tests/ -v --tb=short `
    --ignore=tests/test_knowledge_integration.py `
    --ignore=tests/test_knowledge_seed.py `
    --ignore=tests/smoke_mcp.py `
    --ignore=tests/smoke_knowledge_server.py `
    --ignore=tests/test_multi_agent_loop.py
```

### Frontend Tests (66 tests)
```bash
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli\desktop
npx vitest run
```

### Production Bundle Verification
```bash
cd C:\Users\user\Desktop\ClaudeCoder\igris-cli\desktop
npm run verify:bundle
```

## Tests Requiring Live Ollama
These tests are excluded by default and require a running Ollama server with `nomic-embed-text` model pulled:
- `test_knowledge_integration.py`
- `test_knowledge_seed.py`
- `test_knowledge_server.py`
- `smoke_mcp.py`
- `smoke_knowledge_server.py`
- `test_multi_agent_loop.py`

Run them separately when Ollama is available:
```bash
ollama pull nomic-embed-text
ollama pull qwen3
python -m pytest tests/test_knowledge_integration.py -v
python -m pytest tests/smoke_mcp.py -v
```

## Files Modified

| File | Change |
|------|--------|
| `igris/core/mcp_manager.py` | Added try/except in `call()` method (lines 110-115) |
| `setup_fixes.ps1` | PowerShell setup script (new) |
| `setup_fixes.bat` | Command Prompt setup script (new) |

## Verification Checklist

- [ ] `PYTEST_DEBUG_TEMPROOT` environment variable set
- [ ] Backend tests pass (115 passed)
- [ ] Frontend tests pass (66 passed)
- [ ] Bundle verification passes (both modes)
- [ ] `mcp_manager.py` has try/except around `session.call_tool()`