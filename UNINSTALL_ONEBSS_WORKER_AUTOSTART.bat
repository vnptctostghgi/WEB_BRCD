@echo off
setlocal

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Dang mo lai bang quyen Administrator...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "VNPTCTO_UNINSTALL_ROOT=%~dp0"
cd /d "%TEMP%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%VNPTCTO_UNINSTALL_ROOT%scripts\uninstall_onebss_worker_task.ps1" -NoPause
