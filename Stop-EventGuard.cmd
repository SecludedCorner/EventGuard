@echo off
cd /d "%~dp0"
"C:\Python313\python.exe" -B "%~dp0scripts\eventguard.py" stop
pause
