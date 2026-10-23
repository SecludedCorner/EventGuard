@echo off
cd /d "%~dp0"
if not "%~1"=="" goto eventguard_cli
call "%~dp0scripts\run-gui.cmd" %*
exit /b %ERRORLEVEL%
:eventguard_cli
call "%~dp0scripts\run-python.cmd" "%~dp0scripts\eventguard.py" %*
exit /b %ERRORLEVEL%
