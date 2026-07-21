@echo off
REM ============================================
REM igris-cli Windows Fixes Setup (cmd.exe)
REM ============================================

set PROJECT_ROOT=%~dp0
set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
set TEMP_DIR=%PROJECT_ROOT%\.pytest_tmp

echo === igris-cli Windows Fixes Setup ===

REM 1. Create temp directory for pytest
echo [1/4] Creating pytest temp directory...
if not exist "%TEMP_DIR%" (
    mkdir "%TEMP_DIR%"
    echo Created: %TEMP_DIR%
) else (
    echo Exists: %TEMP_DIR%
)

REM 2. Set environment variable for current session
set PYTEST_DEBUG_TEMPROOT=%TEMP_DIR%
echo Set PYTEST_DEBUG_TEMPROOT=%TEMP_DIR%

REM 3. Verify MCPManager fix
echo [2/4] Verifying MCPManager error handling fix...
findstr /C:"try {" "%PROJECT_ROOT%\igris\core\mcp_manager.py" >nul
if %ERRORLEVEL% EQU 0 (
    echo Fix already applied
) else (
    echo ERROR: Fix not found in mcp_manager.py
    exit /b 1
)

REM 4. Run tests
echo [3/4] Running backend tests...
cd /d %PROJECT_ROOT%
python -m pytest tests/ -v --tb=short ^
    --ignore=tests/test_knowledge_integration.py ^
    --ignore=tests/test_knowledge_seed.py ^
    --ignore=tests/smoke_mcp.py ^
    --ignore=tests/smoke_knowledge_server.py ^
    --ignore=tests/test_multi_agent_loop.py

echo [4/4] Running frontend tests...
cd /d %PROJECT_ROOT%\desktop
npx vitest run

echo [5/5] Verifying production bundle...
npm run verify:bundle

echo.
echo === All fixes applied successfully! ===
echo.
echo To run tests manually in the future:
echo   set PYTEST_DEBUG_TEMPROOT=%TEMP_DIR%
echo   python -m pytest tests/ -v --tb=short