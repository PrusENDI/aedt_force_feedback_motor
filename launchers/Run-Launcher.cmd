@echo off
setlocal

if "%~1"=="" (
  echo Usage: Run-Launcher.cmd LauncherName.ps1 [args...]
  exit /b 1
)

set "LAUNCHER=%~1"
shift
set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%%LAUNCHER%"

if not exist "%TARGET%" (
  set "TARGET=%SCRIPT_DIR%launchers\%LAUNCHER%"
)

if not exist "%TARGET%" (
  echo Launcher not found: %TARGET%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%TARGET%" %*
exit /b %ERRORLEVEL%
