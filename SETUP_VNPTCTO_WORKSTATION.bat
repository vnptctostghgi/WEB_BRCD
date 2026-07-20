@echo off
setlocal

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Dang mo lai bang quyen Administrator...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_vnptcto_workstation.ps1" -StartNow
pause
