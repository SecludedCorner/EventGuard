@echo off
cd /d "%~dp0"
echo EventGuard: background read-only monitoring; no model required.
echo Use Status-EventGuard.cmd to inspect, or Stop-EventGuard.cmd to disable it durably.
call "%~dp0scripts\run-python.cmd" "%~dp0scripts\eventguard.py" --format text background start %*
exit /b %ERRORLEVEL%
