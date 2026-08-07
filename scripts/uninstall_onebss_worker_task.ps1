param(
  [string]$InstallRoot = "",
  [string]$ApiRoot = "C:\VNPTCTO",
  [switch]$KeepInstallDir,
  [switch]$NoPause
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "== $Message" -ForegroundColor Cyan
}

function Resolve-InstallRoot {
  if (-not [string]::IsNullOrWhiteSpace($InstallRoot)) {
    return $InstallRoot
  }
  $envRoot = [Environment]::GetEnvironmentVariable("VNPTCTO_WORKSTATION_ROOT", "User")
  if (-not [string]::IsNullOrWhiteSpace($envRoot)) {
    return $envRoot
  }
  $scriptRoot = Split-Path -Parent $PSScriptRoot
  if (-not [string]::IsNullOrWhiteSpace($scriptRoot) -and (Split-Path -Leaf $scriptRoot) -ieq "Tool_Tram_VNPTCTO.COM") {
    return $scriptRoot
  }
  return "D:\Tool_Tram_VNPTCTO.COM"
}

function Normalize-PathText {
  param([string]$Path)
  try {
    return [IO.Path]::GetFullPath($Path).TrimEnd("\")
  } catch {
    return ""
  }
}

function Stop-AndRemoveTask {
  param([string]$TaskName)
  try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
      Write-Host "Khong thay Scheduled Task: $TaskName" -ForegroundColor DarkYellow
      return
    }
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Da go Scheduled Task: $TaskName" -ForegroundColor Green
  } catch {
    Write-Warning "Khong go duoc Scheduled Task ${TaskName}: $($_.Exception.Message)"
  }
}

function Stop-VnptctoProcesses {
  param(
    [string]$Root,
    [string]$ApiDirectory
  )
  $rootText = Normalize-PathText $Root
  $apiText = Normalize-PathText $ApiDirectory
  $currentPid = [int]$PID
  $patterns = @(
    "onebss_workstation_worker.py",
    "start_onebss_worker.ps1",
    "run_onebss_worker_background.ps1",
    "test_vnptcto_workstation.ps1",
    "api-trung-gian",
    "main:app",
    "uvicorn"
  )
  $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    if ([int]$_.ProcessId -eq $currentPid) { return $false }
    $commandLine = [string]$_.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
    $inKnownRoot = $false
    if (-not [string]::IsNullOrWhiteSpace($rootText) -and $commandLine -match [regex]::Escape($rootText)) {
      $inKnownRoot = $true
    }
    if (-not [string]::IsNullOrWhiteSpace($apiText) -and $commandLine -match [regex]::Escape($apiText)) {
      $inKnownRoot = $true
    }
    if (-not $inKnownRoot) { return $false }
    foreach ($pattern in $patterns) {
      if ($commandLine -match [regex]::Escape($pattern)) { return $true }
    }
    return $false
  }
  foreach ($proc in $processes) {
    try {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
      Write-Host "Da dung process PID $($proc.ProcessId)" -ForegroundColor Yellow
    } catch {
      Write-Warning "Khong dung duoc PID $($proc.ProcessId): $($_.Exception.Message)"
    }
  }
}

function Remove-UserEnvironment {
  param([string[]]$Names)
  foreach ($name in $Names) {
    try {
      [Environment]::SetEnvironmentVariable($name, $null, "User")
      Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
      Write-Host "Da xoa bien moi truong User: $name" -ForegroundColor Green
    } catch {
      Write-Warning "Khong xoa duoc bien moi truong ${name}: $($_.Exception.Message)"
    }
  }
}

function Remove-SafeDirectory {
  param(
    [string]$Path,
    [string[]]$AllowedRoots
  )
  $target = Normalize-PathText $Path
  if ([string]::IsNullOrWhiteSpace($target) -or -not (Test-Path -LiteralPath $target)) {
    Write-Host "Khong thay thu muc: $Path" -ForegroundColor DarkYellow
    return
  }
  $allowed = $false
  foreach ($allowedRoot in $AllowedRoots) {
    $allowedText = Normalize-PathText $allowedRoot
    if ([string]::IsNullOrWhiteSpace($allowedText)) {
      continue
    }
    if ($target -ieq $allowedText -or $target.StartsWith("$allowedText\", [System.StringComparison]::OrdinalIgnoreCase)) {
      $allowed = $true
      break
    }
  }
  if (-not $allowed) {
    Write-Warning "Bo qua xoa thu muc khong nam trong vung an toan: $target"
    return
  }
  Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
  Write-Host "Da xoa thu muc: $target" -ForegroundColor Green
}

$resolvedInstallRoot = Normalize-PathText (Resolve-InstallRoot)
$resolvedApiRoot = Normalize-PathText $ApiRoot
$apiDir = Normalize-PathText (Join-Path $resolvedApiRoot "api-trung-gian")

Write-Host "Go cai dat may tram VNPTCTO" -ForegroundColor Cyan
Write-Host "Thu muc worker: $resolvedInstallRoot"
Write-Host "Thu muc API: $resolvedApiRoot"

Write-Step "Dung va go Scheduled Task"
foreach ($taskName in @(
  "VNPTCTO OneBSS Worker",
  "VNPTCTO Workstation Health Check",
  "VNPTCTO API Trung Gian",
  "VNPTCTO API Watchdog"
)) {
  Stop-AndRemoveTask $taskName
}

Write-Step "Dung process VNPTCTO dang chay"
Stop-VnptctoProcesses -Root $resolvedInstallRoot -ApiDirectory $apiDir

Write-Step "Xoa bien moi truong do bo cai dat"
Remove-UserEnvironment @(
  "VNPTCTO_BASE_URL",
  "VNPTCTO_WORKSTATION_ROOT",
  "VNPTCTO_WORKSTATION_LOG_DIR",
  "INTERNAL_API_TOKEN",
  "INTERNAL_API_URL",
  "ONEBSS_DRIVE_UPLOAD_API_URL",
  "ONEBSS_WORKER_ID",
  "ONEBSS_WORKER_POLL_SECONDS",
  "ONEBSS_WORKER_HEARTBEAT_SECONDS",
  "SQL_WORKER_POLL_SECONDS",
  "FTP_WORKER_POLL_SECONDS",
  "SQL_WORKER_TIMEOUT_SECONDS",
  "EXPORT_PAGE_SIZE",
  "EXPORT_MAX_ROWS",
  "ONEBSS_USERNAME",
  "ONEBSS_PASSWORD",
  "ONEBSS_LOGIN_URL",
  "ONEBSS_DOWNLOAD_TIMEOUT_SECONDS",
  "ONEBSS_TASK_TIMEOUT_SECONDS",
  "ONEBSS_WORKER_OTP_WAIT_SECONDS",
  "ONEBSS_WORKER_DISABLE_TASK_GUARD",
  "ONEBSS_WORKER_ENABLE_TASK_GUARD",
  "GOOGLE_DRIVE_FOLDER_ID",
  "GOOGLE_DRIVE_OAUTH_CLIENT_ID",
  "GOOGLE_DRIVE_OAUTH_CLIENT_SECRET",
  "GOOGLE_DRIVE_OAUTH_REDIRECT_URI",
  "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64",
  "DATA_MINING_DOWNLOAD_DIR"
)

if ($KeepInstallDir) {
  Write-Step "Giu lai thu muc cai dat"
  Write-Host "Da giu lai: $resolvedInstallRoot" -ForegroundColor Yellow
  Write-Host "Da giu lai: $resolvedApiRoot" -ForegroundColor Yellow
} else {
  Write-Step "Xoa thu muc cai dat"
  try {
    Set-Location -LiteralPath $env:TEMP
  } catch {
  }
  Remove-SafeDirectory -Path $resolvedInstallRoot -AllowedRoots @("D:\Tool_Tram_VNPTCTO.COM", "$env:USERPROFILE\Tool_Tram_VNPTCTO.COM")
  Remove-SafeDirectory -Path $resolvedApiRoot -AllowedRoots @("C:\VNPTCTO")
}

Write-Host ""
Write-Host "Da go cai dat may tram VNPTCTO. Neu muon cai lai, hay tai bo cai moi tren web va chay SETUP_VNPTCTO_WORKSTATION.bat bang Run as administrator." -ForegroundColor Green

if (-not $NoPause) {
  Read-Host "Nhan Enter de dong" | Out-Null
}
