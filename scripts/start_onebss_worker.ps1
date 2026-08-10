param(
  [switch]$SetupOnly,
  [switch]$SkipPlaywright,
  [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$VenvDir = Join-Path $Root ".venv-onebss-worker"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$RequirementsFile = Join-Path $Root "requirements.txt"
$SetupMarker = Join-Path $VenvDir ".setup-complete"

function Invoke-External {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $FilePath @Arguments 2>&1 | ForEach-Object {
      if ($_ -is [System.Management.Automation.ErrorRecord]) {
        Write-Output ([string]$_.Exception.Message)
      } else {
        Write-Output ([string]$_)
      }
    }
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Lenh that bai ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
  }
}

function Pause-BeforeExit {
  param([string]$Message = "Nhan Enter de dong")

  if (-not $NoPause) {
    Read-Host $Message | Out-Null
  }
}

function Test-PythonLauncher {
  param(
    [Parameter(Mandatory = $true)][string]$File,
    [string[]]$Args = @()
  )
  $testArgs = @($Args) + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)")
  try {
    & $File @testArgs *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

function Python-FileLauncher {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
    return $null
  }
  if (Test-PythonLauncher $Path) {
    return @{ File = $Path; Args = @() }
  }
  return $null
}

function Find-PythonFileCandidate {
  $pathCandidates = @()
  try {
    $pathCandidates += & where.exe python 2>$null | ForEach-Object { ([string]$_).Trim() }
    $pathCandidates += & where.exe python3 2>$null | ForEach-Object { ([string]$_).Trim() }
  } catch {
  }
  foreach ($candidate in $pathCandidates | Where-Object { $_ } | Select-Object -Unique) {
    $launcher = Python-FileLauncher $candidate
    if ($launcher) {
      return $launcher
    }
  }
  $roots = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python"),
    (Join-Path $env:ProgramFiles "Python312"),
    (Join-Path ${env:ProgramFiles(x86)} "Python312")
  )
  foreach ($root in $roots) {
    if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root)) {
      continue
    }
    $candidates = @()
    if (Test-Path -LiteralPath (Join-Path $root "python.exe")) {
      $candidates += (Join-Path $root "python.exe")
    }
    $candidates += Get-ChildItem -Path $root -Filter python.exe -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    foreach ($candidate in $candidates | Select-Object -Unique) {
      $launcher = Python-FileLauncher $candidate
      if ($launcher) {
        return $launcher
      }
    }
  }
  return $null
}

function Find-PythonLauncher {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py -and (Test-PythonLauncher "py" @("-3"))) {
    return @{ File = "py"; Args = @("-3") }
  }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python -and (Test-PythonLauncher "python")) {
    return @{ File = "python"; Args = @() }
  }
  $fileCandidate = Find-PythonFileCandidate
  if ($fileCandidate) {
    return $fileCandidate
  }
  return $null
}

function Ensure-Python {
  $launcher = Find-PythonLauncher
  if ($launcher) {
    return $launcher
  }
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "Chua tim thay Python va cung khong co winget de tu cai. Hay cai Python 3.12 roi chay lai."
  }
  Write-Host "Chua co Python that. Dang tu cai Python 3.12 bang winget..." -ForegroundColor Cyan
  Invoke-External $winget.Source "install" "-e" "--id" "Python.Python.3.12" "--silent" "--accept-package-agreements" "--accept-source-agreements"
  $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machinePath;$userPath"
  $launcher = Find-PythonLauncher
  if (-not $launcher) {
    throw "Da chay winget nhung van chua thay Python that. Hay tat App execution aliases cho python.exe/python3.exe hoac mo lai PowerShell roi chay lai."
  }
  return $launcher
}

trap {
  Write-Host ""
  Write-Host "May tram OneBSS bi loi:" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Pause-BeforeExit
  exit 1
}

$env:VNPTCTO_BASE_URL = [Environment]::GetEnvironmentVariable("VNPTCTO_BASE_URL", "User")
if ([string]::IsNullOrWhiteSpace($env:VNPTCTO_BASE_URL)) {
  $env:VNPTCTO_BASE_URL = "https://vnptcto.com"
}

foreach ($name in @(
  "INTERNAL_API_TOKEN",
  "INTERNAL_API_URL",
  "ONEBSS_DRIVE_UPLOAD_API_URL",
  "ONEBSS_DRIVE_UPLOAD_TIMEOUT_SECONDS",
  "ONEBSS_WORKER_ID",
  "ONEBSS_WORKER_POLL_SECONDS",
  "ONEBSS_WORKER_HEARTBEAT_SECONDS",
  "SQL_WORKER_POLL_SECONDS",
  "FTP_WORKER_POLL_SECONDS",
  "VNPTCTO_WORKER_MAX_CONCURRENT_TASKS",
  "ONEBSS_WORKER_MAX_CONCURRENT_TASKS",
  "ONEBSS_WORKER_MAX_ONEBSS_TASKS",
  "SQL_WORKER_MAX_CONCURRENT_TASKS",
  "FTP_WORKER_MAX_CONCURRENT_TASKS",
  "ONEBSS_USERNAME",
  "ONEBSS_PASSWORD",
  "ONEBSS_LOGIN_URL",
  "ONEBSS_DOWNLOAD_TIMEOUT_SECONDS",
  "ONEBSS_GRID_TIMEOUT_SECONDS",
  "ONEBSS_PROCESSING_TIMEOUT_RETRY_ATTEMPTS",
  "ONEBSS_PROCESSING_TIMEOUT_RETRY_DELAY_SECONDS",
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
)) {
  $value = [Environment]::GetEnvironmentVariable($name, "User")
  if (-not [string]::IsNullOrWhiteSpace($value)) {
    Set-Item -Path "Env:$name" -Value $value
  }
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_DISABLE_TASK_GUARD)) {
  $env:ONEBSS_WORKER_DISABLE_TASK_GUARD = "1"
}
if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_OTP_WAIT_SECONDS)) {
  $env:ONEBSS_WORKER_OTP_WAIT_SECONDS = "180"
}
if ([string]::IsNullOrWhiteSpace($env:VNPTCTO_WORKER_MAX_CONCURRENT_TASKS)) {
  if (-not [string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_MAX_CONCURRENT_TASKS)) {
    $env:VNPTCTO_WORKER_MAX_CONCURRENT_TASKS = $env:ONEBSS_WORKER_MAX_CONCURRENT_TASKS
  } else {
    $env:VNPTCTO_WORKER_MAX_CONCURRENT_TASKS = "4"
  }
}
if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_MAX_CONCURRENT_TASKS)) {
  $env:ONEBSS_WORKER_MAX_CONCURRENT_TASKS = $env:VNPTCTO_WORKER_MAX_CONCURRENT_TASKS
}
if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_MAX_ONEBSS_TASKS)) {
  $env:ONEBSS_WORKER_MAX_ONEBSS_TASKS = "2"
}
if ([string]::IsNullOrWhiteSpace($env:SQL_WORKER_MAX_CONCURRENT_TASKS)) {
  $env:SQL_WORKER_MAX_CONCURRENT_TASKS = "2"
}
if ([string]::IsNullOrWhiteSpace($env:FTP_WORKER_MAX_CONCURRENT_TASKS)) {
  $env:FTP_WORKER_MAX_CONCURRENT_TASKS = "2"
}

$missingRuntimeConfig = New-Object System.Collections.Generic.List[string]
if ([string]::IsNullOrWhiteSpace($env:INTERNAL_API_TOKEN)) {
  $missingRuntimeConfig.Add("INTERNAL_API_TOKEN") | Out-Null
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_USERNAME) -or [string]::IsNullOrWhiteSpace($env:ONEBSS_PASSWORD)) {
  $missingRuntimeConfig.Add("ONEBSS_USERNAME/ONEBSS_PASSWORD") | Out-Null
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_ID)) {
  $env:ONEBSS_WORKER_ID = "may-tram-cto-01"
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_POLL_SECONDS)) {
  $env:ONEBSS_WORKER_POLL_SECONDS = "5"
}

if (-not (Test-Path $VenvPython)) {
  Write-Host "Lan dau chay: dang tao moi truong rieng cho may tram..." -ForegroundColor Cyan
  $launcher = Ensure-Python
  $venvArgs = @($launcher.Args) + @("-m", "venv", $VenvDir)
  Invoke-External $launcher.File @venvArgs
}

if (-not (Test-Path $VenvPython)) {
  throw "Khong tao duoc moi truong rieng cho may tram: $VenvPython"
}

$needsSetup = -not (Test-Path $SetupMarker)
if (-not $needsSetup -and (Test-Path $RequirementsFile)) {
  $needsSetup = (Get-Item $RequirementsFile).LastWriteTimeUtc -gt (Get-Item $SetupMarker).LastWriteTimeUtc
}

if ($needsSetup) {
  Write-Host "Dang cai thu vien rieng cho may tram. Viec nay chi lau o lan dau..." -ForegroundColor Cyan
  Invoke-External $VenvPython "-m" "pip" "install" "--upgrade" "pip"
  Invoke-External $VenvPython "-m" "pip" "install" "-r" $RequirementsFile
  if (-not $SkipPlaywright) {
    Invoke-External $VenvPython "-m" "playwright" "install" "chromium"
  }
  Set-Content -Path $SetupMarker -Value (Get-Date).ToString("o")
}

if ($SetupOnly) {
  if ($missingRuntimeConfig.Count -gt 0) {
    Write-Warning "Cai moi truong xong, nhung worker chua the chay vi thieu: $($missingRuntimeConfig -join ', '). Hay cap nhat cau hinh tren web roi tai lai bo cai."
  }
  Write-Host "Cai dat may tram da san sang. Chua nhan task bao cao nao." -ForegroundColor Green
  Pause-BeforeExit
  exit 0
}

if ($missingRuntimeConfig.Count -gt 0) {
  Write-Host "Chua du cau hinh de chay worker: $($missingRuntimeConfig -join ', ')." -ForegroundColor Red
  Write-Host "Hay cap nhat cau hinh tren web, tai lai bo cai va chay SETUP_VNPTCTO_WORKSTATION.bat." -ForegroundColor Yellow
  Pause-BeforeExit
  exit 1
}

Write-Host "Dang chay may tram OneBSS. Hay de cua so nay mo." -ForegroundColor Green
Write-Host "Trang web: $env:VNPTCTO_BASE_URL"
Write-Host "May tram: $env:ONEBSS_WORKER_ID"
Write-Host "Da luong: tong $env:VNPTCTO_WORKER_MAX_CONCURRENT_TASKS task, OneBSS $env:ONEBSS_WORKER_MAX_ONEBSS_TASKS, SQL $env:SQL_WORKER_MAX_CONCURRENT_TASKS, FTP $env:FTP_WORKER_MAX_CONCURRENT_TASKS"
Write-Host ""

Invoke-External $VenvPython (Join-Path $Root "scripts\onebss_workstation_worker.py")

Write-Host ""
Write-Host "Worker da dung." -ForegroundColor Yellow
Pause-BeforeExit
