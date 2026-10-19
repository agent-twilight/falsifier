@echo off
REM Starts the website on your own machine.
REM
REM Double-click this file, then open http://127.0.0.1:8000 in a browser.
REM Leave the black window open while you use the site. Close it to stop.
REM
REM --reload means the site picks up code changes without restarting.

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

echo.
echo   The Falsifier is starting.
echo   Open this in your browser:  http://127.0.0.1:8000
echo   Close this window to stop it.
echo.

".venv\Scripts\python.exe" -m uvicorn web.main:app --host 127.0.0.1 --port 8000 --reload
