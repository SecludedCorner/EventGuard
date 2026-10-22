@echo off
cd /d "%~dp0"
echo EventGuard: foreground read-only monitoring; no model required.
echo Press Ctrl+C or use Stop-EventGuard.cmd from another terminal.
call "%~dp0scripts\run-python.cmd" "%~dp0scripts\eventguard.py" --format text monitor %*
exit /b %ERRORLEVEL%
