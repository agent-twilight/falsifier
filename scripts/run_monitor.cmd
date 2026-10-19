@echo off
REM Daily monitoring run, for Windows Task Scheduler.
REM
REM Re-checks every cited source (free), and on Mondays also hunts for
REM developments that did not exist before (costs Tavily credits).
REM Writes one line per run to logs\monitor.log, which is the record of
REM the agent having run unattended.

cd /d "%~dp0.."
if not exist logs mkdir logs

set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m falsifier.monitor >> "logs\monitor.log" 2>&1
