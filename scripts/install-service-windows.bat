@echo off
REM Install Maestro as a Windows service using NSSM (https://nssm.cc)
REM Usage: install-service-windows.bat [path\to\nssm.exe]
setlocal

set NSSM=%1
if "%NSSM%"=="" set NSSM=nssm

where %NSSM% >nul 2>&1
if errorlevel 1 (
  echo NSSM not found. Download it from https://nssm.cc and pass its path:
  echo   install-service-windows.bat C:\tools\nssm.exe
  exit /b 1
)

set ROOT=%~dp0..
for %%i in ("%ROOT%") do set ROOT=%%~fi

%NSSM% install Maestro python "%ROOT%\app.py"
%NSSM% set Maestro AppDirectory "%ROOT%"
%NSSM% set Maestro AppEnvironmentExtra MAESTRO_OPEN_BROWSER=false
%NSSM% set Maestro Description "Maestro Automotive Test Automation Framework"
%NSSM% set Maestro Start SERVICE_AUTO_START
%NSSM% start Maestro

echo Maestro service installed and started (http://localhost:8000)
endlocal
