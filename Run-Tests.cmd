@echo off
cd /d "%~dp0"
call "%~dp0scripts\run-python.cmd" "%~dp0scripts\verify.py"  %*
exit /b %ERRORLEVEL%
