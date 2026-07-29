@echo off
setlocal

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Dang mo lai bang quyen Administrator...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_vnptcto_workstation.ps1" -StartNow -NoPause
set "SETUP_EXIT=%errorlevel%"
if not "%SETUP_EXIT%"=="0" (
  exit /b %SETUP_EXIT%
)
exit /b 0
