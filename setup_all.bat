@echo off
REM ============================================
REM igris-cli + Tauri Desktop Full Setup (cmd.exe)
REM ============================================

set PROJECT_ROOT=%~dp0
set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%
set DESKTOP_DIR=%PROJECT_ROOT%\desktop
set TEMP_DIR=%PROJECT_ROOT%\.pytest_tmp

echo === igris-cli + Tauri Desktop Full Setup ===

REM Create pytest temp directory
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"
set PYTEST_DEBUG_TEMPROOT=%TEMP_DIR%

REM 1. Python Backend
echo [1/5] Installing Python backend...
cd /d %PROJECT_ROOT%
pip install -e .
echo Python package installed

REM 2. Frontend Dependencies
echo [2/5] Installing Node.js frontend dependencies...
cd /d %DESKTOP_DIR%
npm install
echo npm install complete

REM 3. Build Frontend
echo [3/5] Building frontend...
npm run build
echo Build complete

REM 4. Verify Production Bundle
echo [4/5] Verifying production bundle...
npm run verify:bundle
echo Bundle verification PASSED

REM 5. Rust/Tauri Setup
echo [5/5] Setting up Rust + Tauri CLI...
where rustup >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing rustup...
    powershell -Command "$wc = New-Object System.Net.WebClient; $wc.DownloadFile('https://win.rustup.rs/x86_64', '$env:TEMP\rustup-init.exe'); Start-Process -Wait -FilePath '$env:TEMP\rustup-init.exe' -ArgumentList '-y --default-toolchain stable'"
    set PATH=%PATH%;%USERPROFILE%\.cargo\bin
) else (
    echo rustup already installed
)

where tauri >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing Tauri CLI...
    cargo install tauri-cli
) else (
    echo Tauri CLI already installed
)

echo.
echo === Setup Complete! ===
echo.
echo Next steps:
echo   1. Start backend:  uvicorn igris.server:app --port 8765 --reload
echo   2. Start frontend: cd desktop; npm run dev
echo   OR run together:  cd desktop; npx tauri dev
echo.
echo Run tests: set PYTEST_DEBUG_TEMPROOT=%TEMP_DIR% && python -m pytest tests/ -v --tb=short
echo Frontend tests: cd desktop; npx vitest run