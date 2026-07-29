param(
  [string]$TaskName = "VNPTCTO OneBSS Worker",
  [switch]$StartNow,
  [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WorkerScript = Join-Path $Root "scripts\run_onebss_worker_background.ps1"

if (-not (Test-Path $WorkerScript)) {
  throw "Khong tim thay worker script: $WorkerScript"
}

function Add-UserCandidate {
  param(
    [System.Collections.Generic.List[string]]$Candidates,
    [string]$Value
  )
  $text = ([string]$Value).Trim()
  if (-not [string]::IsNullOrWhiteSpace($text) -and -not $Candidates.Contains($text)) {
    $Candidates.Add($text) | Out-Null
  }
}

function Get-InteractiveTaskUserCandidates {
  $candidates = New-Object System.Collections.Generic.List[string]
  try {
    Add-UserCandidate $candidates ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
  } catch {
  }
  try {
    Add-UserCandidate $candidates ((& whoami.exe 2>$null | Select-Object -First 1))
  } catch {
  }
  if (-not [string]::IsNullOrWhiteSpace($env:USERDOMAIN) -and -not [string]::IsNullOrWhiteSpace($env:USERNAME)) {
    Add-UserCandidate $candidates "$env:USERDOMAIN\$env:USERNAME"
  }
  if (-not [string]::IsNullOrWhiteSpace($env:COMPUTERNAME) -and -not [string]::IsNullOrWhiteSpace($env:USERNAME)) {
    Add-UserCandidate $candidates "$env:COMPUTERNAME\$env:USERNAME"
  }
  Add-UserCandidate $candidates $env:USERNAME
  return $candidates
}

function Register-VnptctoInteractiveTask {
  param(
    [string]$Name,
    [object]$Action,
    [object[]]$Trigger,
    [object]$Settings,
    [string]$Description
  )
  $lastError = ""
  foreach ($userId in Get-InteractiveTaskUserCandidates) {
    try {
      $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
      Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings -Principal $principal -Description $Description -Force | Out-Null
      Write-Host "Da tao Scheduled Task voi user: $userId" -ForegroundColor Green
      return
    } catch {
      $lastError = $_.Exception.Message
      Write-Warning "Chua tao duoc Scheduled Task voi user '$userId': $lastError"
    }
  }
  try {
    Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description -Force | Out-Null
    Write-Warning "Da tao Scheduled Task bang principal mac dinh cua Windows."
    return
  } catch {
    $lastError = $_.Exception.Message
  }
  throw "Khong tao duoc Scheduled Task $Name. Loi cuoi: $lastError"
}

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WorkerScript`" -NoPause" `
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

Register-VnptctoInteractiveTask `
  -Name $TaskName `
  -Action $Action `
  -Trigger @($Trigger) `
  -Settings $Settings `
  -Description "Tu dong chay may tram OneBSS cua VNPTCTO khi dang nhap Windows."

Write-Host "Da cai tu dong chay: $TaskName" -ForegroundColor Green
Write-Host "May tram se tu chay lai khi user Windows dang nhap." -ForegroundColor Green
Write-Host "Neu may bi tat hoan toan, task tren web se nam trong hang doi den khi may bat va dang nhap lai."
$WorkerLogRoot = [Environment]::GetEnvironmentVariable("VNPTCTO_WORKSTATION_LOG_DIR", "User")
if ([string]::IsNullOrWhiteSpace($WorkerLogRoot)) {
  $WorkerLogRoot = Join-Path $Root "logs"
}
Write-Host "Log worker: $(Join-Path $WorkerLogRoot "onebss-worker.log")"
Write-Host "Log loi worker: $(Join-Path $WorkerLogRoot "onebss-worker-error.log")"
if ($StartNow) {
  Start-ScheduledTask -TaskName $TaskName
  Write-Host "Da khoi dong worker chay nen. Ban co the dong cua so nay." -ForegroundColor Green
}
if (-not $NoPause) {
  Read-Host "Nhan Enter de dong" | Out-Null
}
