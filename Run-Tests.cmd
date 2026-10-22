@echo off
cd /d "%~dp0"
"C:\Python313\python.exe" -B "%~dp0scripts\verify.py"
set "eventguard_result=%ERRORLEVEL%"
echo Verification exit: %eventguard_result%
pause
exit /b %eventguard_result%
