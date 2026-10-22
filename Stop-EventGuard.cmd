@echo off
cd /d "%~dp0"
call "%~dp0scripts\run-python.cmd" "%~dp0scripts\eventguard.py" stop %*
exit /b %ERRORLEVEL%
