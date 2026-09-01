@echo off
rem IGRIS - stop all background services (backend, web UI, ollama).
rem Kills whatever listens on ports 1420 / 8765 / 11434.
call "%~dp0run.bat" stop
