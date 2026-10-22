@echo off
cd /d "%~dp0"
echo EventGuard: foreground read-only monitor. No real agent receiver is connected.
echo Press Ctrl+C or run Stop-EventGuard.cmd from another terminal to stop.
"C:\Python313\python.exe" -B "%~dp0scripts\eventguard.py" monitor
