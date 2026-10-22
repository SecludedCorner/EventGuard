@echo off
setlocal
where py.exe >nul 2>&1
if errorlevel 1 goto eventguard_path_python
py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
if errorlevel 1 goto eventguard_path_python
py -3.13 -B %*
exit /b %ERRORLEVEL%
:eventguard_path_python
where python.exe >nul 2>&1
if errorlevel 1 goto eventguard_no_python
python.exe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
if errorlevel 1 goto eventguard_no_python
python.exe -B %*
exit /b %ERRORLEVEL%
:eventguard_no_python
echo EventGuard requires an existing Python 3.13. Nothing was installed. 1>&2
exit /b 2
