@echo off
cd /d "%~dp0"
call "%~dp0scripts\run-python.cmd" "%~dp0scripts\eventguard.py" --format text stop %*
exit /b %ERRORLEVEL%
