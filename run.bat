@echo off
setlocal
title IGRIS
cd /d "%~dp0"

rem ================================================================
rem   IGRIS - entry point
rem   ===================
rem   Double-click -> one-click start: Ollama + backend + web + DESKTOP
rem                    run FULLY HIDDEN (no terminals stay open), then the
rem                    desktop app window opens automatically.
rem                    (If the desktop app is not built yet, the browser
rem                    opens as fallback: http://localhost:1420)
rem
rem   run.bat stop   -> stop all IGRIS services (backend, web, ollama)
rem   run.bat menu   -> interactive menu (web / desktop / server only)
rem   run.bat build  -> build the desktop app once (self-contained exe)
rem ================================================================

rem ---- locate python (python or py -3) ----
rem BU PYCMD topda, goto'lardan OLDIN o'rnatiladi — aks holda `run.bat menu`
rem rejimida %PYCMD% bo'sh qolib, backend server.py ni topa olmas edi.
set "PYCMD=python"
where python >nul 2>&1
if errorlevel 1 set "PYCMD=py -3"

rem ---- logs folders (Igris_brain/logs for backend+ollama, root logs for vite) ----
rem Bular ham goto'lardan oldin yaratiladi — menu rejimida ham mavjud bo'ladi.
if not exist "%~dp0logs" mkdir "%~dp0logs"
if not exist "%~dp0Igris_brain\logs" mkdir "%~dp0Igris_brain\logs"

if /i "%~1"=="stop" goto stop_all
if /i "%~1"=="menu" goto menu
if /i "%~1"=="build" goto build_desktop

echo ================================================
echo   IGRIS - quick start (all services hidden)
echo ================================================
echo.

call :start_ollama
call :start_server
call :start_watchdog
call :start_web
rem ---- desktop oynasi ochilishidan oldin backend tayyor bo'lishini kutamiz ----
rem (wait_backend desktop_launch ichida ham chaqiriladi - bu yerda takror emas)
call :open_desktop

echo.
echo IGRIS is running in the background - no terminals needed.
echo   Desktop : native app window
echo   Web UI  : http://localhost:1420   (browser fallback)
echo   API     : http://127.0.0.1:8765
echo   Logs    : %~dp0logs\  (backend+ollama: %~dp0Igris_brain\logs\)
echo.
echo To stop everything:  double-click  stop.bat   (or  run.bat stop)
echo.
exit /b 0

rem ================================================================
rem   Interactive menu (power users - visible windows)
rem ================================================================
:menu
echo ================================================
echo   IGRIS - Run
echo ================================================
echo.
echo   1 - Desktop     (hidden services + desktop app window)
echo   2 - Web UI      (hidden services + browser)
echo   3 - Server only (API on http://127.0.0.1:8765)
echo.
set /p CHOICE="Your choice (1-3): "

if "%CHOICE%"=="1" (
    call :start_ollama
    call :start_server
    call :start_watchdog
    call :start_web
    rem tanlangan rejim ochilishidan oldin xizmatlar tayyor bo'lishini kutamiz
    rem (wait_backend desktop_launch ichida bajariladi - takror kutish yo'q)
    call :open_desktop
)
if "%CHOICE%"=="2" (
    call :start_ollama
    call :start_server
    call :start_watchdog
    call :start_web
    call :wait_backend
    call :open_browser
)
if "%CHOICE%"=="3" (
    call :start_ollama
    call :start_server
    call :start_watchdog
    call :wait_backend
)
echo.
echo Done. API: http://127.0.0.1:8765
echo Desktop not built? Run:  run.bat build   (one-time, 2-5 min)
pause
exit /b 0

rem ================================================================
rem   Stop all services (ports 1420, 8765, 11434)
rem ================================================================
:stop_all
echo Stopping IGRIS services (ports 1420, 8765, 11434)...
echo NOTE: bu portdagi barcha jarayonlar to'xtatiladi - Ollama'ni
 echo       alohida ishlatayotgan bo'lsangiz, u ham yopiladi.
rem ---- watchdog ham to'xtatiladi: stop fayl + pid + commandline ----
rem (watchdog hech qanday portni egallamaydi, shuning uchun commandline
rem  orqali topiladi; stop fayl esa uni xavfsiz tarzda chiqishga majbur qiladi)
if exist "%~dp0Igris_brain\logs\watchdog.stop" del /q "%~dp0Igris_brain\logs\watchdog.stop" >nul 2>&1
echo stop > "%~dp0Igris_brain\logs\watchdog.stop"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 1420,8765,11434 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
echo Done.
pause
exit /b 0

rem ================================================================
rem   Service starters (hidden via _hidden.vbs)
rem ================================================================

:start_ollama
echo [ollama] checking port 11434...
curl -s --max-time 2 http://127.0.0.1:11434/api/tags >nul 2>&1
if not errorlevel 1 (
    echo [ollama] already running
    exit /b 0
)
where ollama >nul 2>&1
if errorlevel 1 (
    echo [ollama] 'ollama' not found - server runs with --no-llm fallback
    exit /b 0
)
echo [ollama] starting (hidden)...
wscript.exe "%~dp0_hidden.vbs" "cmd /c ollama serve >> ""%~dp0Igris_brain\logs\ollama.log"" 2>&1"
exit /b 0

:start_server
echo [server] checking port 8765...
curl -s --max-time 2 http://127.0.0.1:8765/api/status >nul 2>&1
if not errorlevel 1 (
    echo [server] already running
    exit /b 0
)
echo [server] starting (hidden)...
wscript.exe "%~dp0_hidden.vbs" "cmd /c cd /d ""%~dp0Igris_brain"" && %PYCMD% server.py >> ""%~dp0Igris_brain\logs\server.log"" 2>&1"
exit /b 0

:start_watchdog
rem ---- Watchdog: backend qulab tushsa uni avtomatik qayta ishga tushiradi ----
rem ("birdan offline bo'lib qolish" oldini oladi). Alohida jarayon sifatida
rem yashirin ishlaydi; log: Igris_brain\logs\watchdog.log
rem Eslatma: watchdog.py o'zi ham bitta nusxa chekloviga ega (fayl qulfi) —
rem agar allaqachon ishlayotgan bo'lsa, yangisi o'z-o'zidan chiqib ketadi.
set "WD_PID="
if exist "%~dp0Igris_brain\logs\watchdog.pid" set /p WD_PID=<"%~dp0Igris_brain\logs\watchdog.pid"
if defined WD_PID (
    tasklist /FI "PID eq %WD_PID%" 2>nul | findstr /i /c:"%WD_PID%" >nul
    if not errorlevel 1 (
        echo [watchdog] already running (pid %WD_PID%)
        exit /b 0
    )
)
echo [watchdog] starting (hidden)...
wscript.exe "%~dp0_hidden.vbs" "cmd /c cd /d ""%~dp0Igris_brain"" && %PYCMD% watchdog.py >> ""%~dp0Igris_brain\logs\watchdog.log"" 2>&1"
exit /b 0

:start_web
echo [web] checking port 1420...
curl -s --max-time 2 http://localhost:1420/ >nul 2>&1
if not errorlevel 1 (
    echo [web] already running
    exit /b 0
)
echo [web] starting vite (hidden)...
wscript.exe "%~dp0_hidden.vbs" "cmd /c cd /d ""%~dp0Igris_Interface"" && npm run dev >> ""%~dp0logs\vite.log"" 2>&1"
exit /b 0

rem ================================================================
rem   Readiness waits — tanlangan rejim ochilishidan oldin xizmat
rem   haqiqatan ishga tushganini tekshiramiz (bo'sh sahifa / offline
rem   oyna ochilmasin).
rem ================================================================

:wait_backend
rem ---- backend (8765) javob bera boshlashini kutamiz (max ~45s) ----
set /a N=0
:wait_backend_loop
set /a N+=1
if %N% gtr 45 (
    echo [server] WARNING: backend javob bermayapti - Igris_brain\logs\server.log ni tekshiring
    exit /b 1
)
curl -s --max-time 1 http://127.0.0.1:8765/api/status >nul 2>&1
if not errorlevel 1 (
    echo [server] backend ready - http://127.0.0.1:8765
    exit /b 0
)
rem sleep ~1s (PATH'dan mustaqil — `timeout` ba'zi muhitda GNU bilan almashishi mumkin)
ping -n 2 127.0.0.1 >nul
goto wait_backend_loop

:wait_web
rem ---- web UI (1420) javob bera boshlashini kutamiz (max ~30s) ----
set /a M=0
:wait_web_loop
set /a M+=1
if %M% gtr 30 (
    echo [web] WARNING: web UI javob bermayapti - logs\vite.log ni tekshiring
    exit /b 1
)
curl -s --max-time 1 http://localhost:1420/ >nul 2>&1
if not errorlevel 1 (
    echo [web] web UI ready - http://localhost:1420
    exit /b 0
)
ping -n 2 127.0.0.1 >nul
goto wait_web_loop

:open_desktop
rem ---- prefer a release (self-contained) build, else the dev debug exe ----
set "DESKTOP_EXE=%~dp0Igris_Interface\src-tauri\target\release\igris-agent-console.exe"
set "DESKTOP_IS_RELEASE=0"
if exist "%DESKTOP_EXE%" (
    set "DESKTOP_IS_RELEASE=1"
) else (
    set "DESKTOP_EXE=%~dp0Igris_Interface\src-tauri\target\debug\igris-agent-console.exe"
)
if not exist "%DESKTOP_EXE%" (
    echo [desktop] app not built yet - opening browser instead.
    echo [desktop] To build once:  run.bat build - bir martalik, 2-5 daqiqa
    call :open_browser
    exit /b 0
)
rem ---- the DEBUG build loads its UI from vite (:1420); the RELEASE build
rem      is self-contained and does NOT need vite - launch it right away ----
if "%DESKTOP_IS_RELEASE%"=="1" goto desktop_launch

echo [desktop] waiting for UI to come up (dev build needs vite)...
set /a N=0
:waitloop
set /a N+=1
if %N% gtr 40 (
    echo [desktop] UI not ready yet - check logs\vite.log
    call :open_browser
    exit /b 0
)
curl -s --max-time 1 http://localhost:1420/ >nul 2>&1
if not errorlevel 1 goto desktop_launch
ping -n 2 127.0.0.1 >nul
goto waitloop

:desktop_launch
rem ---- backend tayyor bo'lishini kutamiz (desktop app shunga ulanadi) ----
call :wait_backend
rem ---- if a desktop window is already open, don't stack a second one ----
rem findstr ishlatiladi (find o'rniga) — ba'zi muhitda PATH'dagi GNU find
rem Windows find'ni soya qilib, "/i" xato berishi mumkin.
tasklist /FI "IMAGENAME eq igris-agent-console.exe" 2>nul | findstr /i /c:"igris-agent-console.exe" >nul
if not errorlevel 1 (
    echo [desktop] already running - window is open.
    exit /b 0
)
echo [desktop] opening native app window...
rem AVVALGI XATO: _hidden.vbs (window style 0 = yashirin) ishlatilgan edi —
rem desktop oynasi hech qachon ko'rinmas edi. Endi start bilan ODDIY (ko'rinadigan)
rem rejimda ochiladi.
start "" "%DESKTOP_EXE%"
exit /b 0

:open_browser
rem ---- brauzer ochilishidan oldin web UI tayyor bo'lishini kutamiz ----
call :wait_web
echo [web] opening browser...
start "" "http://localhost:1420"
exit /b 0

:build_desktop
echo ================================================
echo   Building IGRIS Desktop app (one-time, 2-5 min)
echo   A visible terminal is needed for the build log.
echo ================================================
cd /d "%~dp0Igris_Interface"
call npm run tauri build -- --no-bundle
if errorlevel 1 (
    echo.
    echo [desktop] build failed - see the output above.
    echo Tip: make sure Rust is installed:  rustup default stable
    pause
    exit /b 1
)
echo.
echo [desktop] build complete! Now just double-click run.bat -
echo           the desktop app window will open automatically.
pause
exit /b 0
