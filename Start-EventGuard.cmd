@echo off
cd /d "%~dp0"
call "%~dp0scripts\run-gui.cmd" --start %*
exit /b %ERRORLEVEL%
