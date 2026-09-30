@echo off
setlocal
title IGRIS Setup
cd /d "%~dp0"

echo ================================================
echo   IGRIS - Setup  (bir martalik o'rnatish)
echo ================================================
echo.

rem ================================================================
rem   [0/5] Muhit tekshiruvi — Python va Node o'rnatilganini
rem   tekshiramiz (to'rt bosqich davomida erta xabar beramiz).
rem ================================================================
echo [0/5] Muhit tekshiruvi...
set "PYCMD=python"
where python >nul 2>&1
if errorlevel 1 set "PYCMD=py -3"
where %PYCMD% >nul 2>&1
if errorlevel 1 goto err_py
where npm >nul 2>&1
if errorlevel 1 goto err_npm
echo        Python: %PYCMD%  OK
echo        npm:    OK
echo.

rem ================================================================
rem   [1/5] Python paketlari (Igris_brain/requirements.txt)
rem ================================================================
echo [1/5] Python paketlari (Igris_brain)...
cd /d "%~dp0Igris_brain"
%PYCMD% -m pip install -r requirements.txt
if errorlevel 1 goto err_py
echo.

rem ================================================================
rem   [2/5] Node paketlari (Igris_Interface)
rem ================================================================
echo [2/5] Node paketlari (Igris_Interface)...
cd /d "%~dp0Igris_Interface"
call npm install
if errorlevel 1 goto err_npm
echo.

rem ================================================================
rem   [3/5] Eskirgan runtime fayllarini tozalash
rem   Server "server/logs" ichiga launch-info yozgan bo'lsa (eski
rem   xulq), watchdog uni o'qiy olmasdi. Hozir hamma fayl kanonik
rem   Igris_brain/logs da; eskilarni o'chirib qo'yamiz.
rem ================================================================
echo [3/5] Eskirgan runtime fayllarini tozalash...
if exist "%~dp0Igris_brain\server\logs\server_launch.json" del /q "%~dp0Igris_brain\server\logs\server_launch.json" >nul 2>&1
if exist "%~dp0Igris_brain\server\logs\watchdog.json" del /q "%~dp0Igris_brain\server\logs\watchdog.json" >nul 2>&1
del /q "%~dp0Igris_brain\logs\restart_*.ok" >nul 2>&1
echo        OK
echo.

rem ================================================================
rem   [4/5] Ollama (ixtiyoriy, LLM uchun)
rem   O'rnatilmasa backend --no-llm fallback bilan ishlayveradi
rem   (deterministik brick-engine to'liq ishlaydi, chat LLM'siz).
rem ================================================================
echo [4/5] Ollama tekshiruvi (ixtiyoriy)...
where ollama >nul 2>&1
if errorlevel 1 (
    echo        OGohlantirish: ollama topilmadi - LLM fallback'siz ishlaydi.
    echo        O'rnatish: https://ollama.com/download
    echo        Keyin modelni yuklab oling:  ollama pull qwen3:8b
) else (
    echo        ollama: OK  (model yuklab olish:  ollama pull qwen3:8b^)
)
echo.

rem ================================================================
rem   [5/5] Desktop app (ixtiyoriy, Rust kerak)
rem   Qurilmasa run.bat avtomatik brauzer fallback ochadi
rem   (http://localhost:1420) - IGRIS baribir ishlaydi.
rem ================================================================
echo [5/5] Desktop app (ixtiyoriy)...
if exist "%~dp0Igris_Interface\src-tauri\target\release\igris-agent-console.exe" (
    echo        Desktop exe mavjud - qayta qurish shart emas.
    echo        GUI yangilanishi kerak bo'lsa:  run.bat build
) else (
    echo        Desktop exe topilmadi.
    echo        Qurish:  run.bat build   (bir martalik, 2-5 daqiqa, Rust kerak)
    echo        Qurmagan holda ham ishlaydi: run.bat brauzerda ochadi.
)
echo.

echo ================================================
echo   Setup TUGADI.
echo ================================================
echo.
echo   Ishga tushirish:   run.bat
echo      - Ollama + backend + web UI yashirin (oynasiz) ishga tushadi,
echo        desktop oynasi yoki brauzer avtomatik ochiladi.
echo      - Watchdog (Igris_brain\monitor\watchdog.py) ham avtomatik
echo        ishga tushadi: backend qulasa ~16 sekundda o'zi tiklaydi.
echo.
echo   Boshqa rejimlar:
echo      run.bat menu   - interaktiv menyu (desktop / web / server)
echo      run.bat build  - desktop appni qurish (GUI yangilanishi)
echo      run.bat stop   - barcha xizmatlarni to'xtatish (yoki stop.bat)
echo.
echo   Qo'llanma: README.md va IGRIS_RUN_COMMANDS.txt
echo.
pause
exit /b 0

:err_py
echo.
echo XATO: Python / pip muvaffaqiyatsiz tugadi.
echo Python 3.10+ o'rnating va PATH'da ekanligini tekshiring, keyin setup.bat ni qayta ishga tushiring.
pause
exit /b 1

:err_npm
echo.
echo XATO: npm install muvaffaqiyatsiz tugadi.
echo Node.js 18+ o'rnating va npm PATH'da ekanligini tekshiring, keyin setup.bat ni qayta ishga tushiring.
pause
exit /b 1
