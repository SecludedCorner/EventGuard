@echo off
setlocal
where pyw.exe >nul 2>&1
if errorlevel 1 goto eventguard_console
py -3.13 -B -c "import sys,tkinter; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
if errorlevel 1 goto eventguard_missing
start "" pyw.exe -3.13 -B "%~dp0eventguard_gui.py" %*
exit /b 0
:eventguard_console
call "%~dp0run-python.cmd" "%~dp0eventguard_gui.py" %*
exit /b %ERRORLEVEL%
:eventguard_missing
echo EventGuard requires existing Python 3.13 with tkinter. Nothing was installed. 1>&2
pause
exit /b 2
