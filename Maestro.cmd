@echo off
rem Maestro launcher — double-click to start the dashboard.
cd /d "%~dp0"
python app.py %*
if errorlevel 1 (
  echo.
  echo Maestro exited with an error. Make sure Python 3.10+ is installed and on PATH.
  pause
)
