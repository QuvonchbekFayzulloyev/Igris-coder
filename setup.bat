@echo off
setlocal
title IGRIS Setup
cd /d "%~dp0"

echo ================================================
echo   IGRIS - Setup  (one-time install)
echo ================================================
echo.

echo [1/2] Python packages (Igris_brain)...
cd /d "%~dp0Igris_brain"
python -m pip install -r requirements.txt
if errorlevel 1 goto err_py

echo.
echo [2/2] Node packages (Igris_Interface)...
cd /d "%~dp0Igris_Interface"
call npm install
if errorlevel 1 goto err_npm

echo.
echo ================================================
echo   Setup DONE.  Now run:  run.bat
echo ================================================
pause
exit /b 0

:err_py
echo.
echo ERROR: Python / pip failed.
echo Install Python 3.10+ and make sure it is on PATH, then run setup.bat again.
pause
exit /b 1

:err_npm
echo.
echo ERROR: npm install failed.
echo Install Node.js 18+ and make sure npm is on PATH, then run setup.bat again.
pause
exit /b 1
