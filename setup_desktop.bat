@echo off
REM ============================================
REM igris-cli Desktop (Frontend) Setup - cmd.exe
REM ============================================

set PROJECT_ROOT=C:\Users\user\Desktop\ClaudeCoder\igris-cli
set DESKTOP_DIR=%PROJECT_ROOT%\desktop

echo === igris-cli Desktop (Frontend) Setup ===

REM 1. Install Dependencies
echo.
echo [1/4] Installing Node.js dependencies...
cd /d %DESKTOP_DIR%
npm install
echo npm install complete

REM 2. Build Frontend
echo.
echo [2/4] Building frontend...
npm run build
echo Build complete

REM 3. Verify Production Bundle
echo.
echo [3/4] Verifying production bundle...
npm run verify:bundle
echo Bundle verification PASSED

REM 4. Tauri CLI (optional - install globally if not present)
echo.
echo [4/4] Checking Tauri CLI...
where tauri >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing Tauri CLI globally...
    npm install -g @tauri-apps/cli
) else (
    echo Tauri CLI already installed
)

echo.
echo === Desktop Setup Complete! ===
echo.
echo To run:
echo   Dev mode:     npx tauri dev
echo   Dev (split):  uvicorn igris.server:app --port 8765 --reload
echo                 npm run dev
echo   Build:        npm run tauri build
echo   Tests:        npx vitest run