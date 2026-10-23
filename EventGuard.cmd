@echo off
cd /d "%~dp0"
call "%~dp0scripts\run-gui.cmd" %*
exit /b %ERRORLEVEL%
