param(
  [string]$TaskName = "VNPTCTO OneBSS Worker",
  [switch]$StartNow
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WorkerScript = Join-Path $Root "scripts\start_onebss_worker.ps1"

if (-not (Test-Path $WorkerScript)) {
  throw "Khong tim thay worker script: $WorkerScript"
}

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$WorkerScript`" -NoPause" `
  -WorkingDirectory $Root

$Trigger = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Days 365) `
  -MultipleInstances IgnoreNew `
  -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -StartWhenAvailable

$Principal = New-ScheduledTaskPrincipal `
  -UserId $env:USERNAME `
  -LogonType Interactive `
  -RunLevel LeastPrivilege

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Principal $Principal `
  -Description "Tu dong chay may tram OneBSS cua VNPTCTO khi dang nhap Windows." `
  -Force | Out-Null

Write-Host "Da cai tu dong chay: $TaskName" -ForegroundColor Green
Write-Host "May tram se tu chay lai khi user Windows dang nhap." -ForegroundColor Green
Write-Host "Neu may bi tat hoan toan, task tren web se nam trong hang doi den khi may bat va dang nhap lai."
if ($StartNow) {
  Start-ScheduledTask -TaskName $TaskName
  Write-Host "Da khoi dong worker chay nen. Ban co the dong cua so nay." -ForegroundColor Green
}
Read-Host "Nhan Enter de dong" | Out-Null
