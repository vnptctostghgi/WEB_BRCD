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

  & $FilePath @Arguments
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
  "ONEBSS_USERNAME",
  "ONEBSS_PASSWORD",
  "ONEBSS_LOGIN_URL",
  "ONEBSS_DOWNLOAD_TIMEOUT_SECONDS",
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

if ([string]::IsNullOrWhiteSpace($env:INTERNAL_API_TOKEN)) {
  Write-Host "Chua co INTERNAL_API_TOKEN. Hay bao Codex cau hinh token worker." -ForegroundColor Red
  Pause-BeforeExit
  exit 1
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_USERNAME) -or [string]::IsNullOrWhiteSpace($env:ONEBSS_PASSWORD)) {
  Write-Host "Chua co tai khoan OneBSS tren may tram. Hay bao Codex lay cau hinh hoac nhap lai." -ForegroundColor Red
  Pause-BeforeExit
  exit 1
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_ID)) {
  $env:ONEBSS_WORKER_ID = "may-tram-cto-01"
}

if ([string]::IsNullOrWhiteSpace($env:ONEBSS_WORKER_POLL_SECONDS)) {
  $env:ONEBSS_WORKER_POLL_SECONDS = "5"
}

if (-not (Test-Path $VenvPython)) {
  Write-Host "Lan dau chay: dang tao moi truong rieng cho may tram..." -ForegroundColor Cyan
  $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    Invoke-External "py" "-3" "-m" "venv" $VenvDir
  } else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
      throw "Chua tim thay Python. Hay cai Python 3 roi chay lai shortcut."
    }
    Invoke-External "python" "-m" "venv" $VenvDir
  }
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
  Write-Host "Cai dat may tram da san sang. Chua nhan task bao cao nao." -ForegroundColor Green
  Pause-BeforeExit
  exit 0
}

Write-Host "Dang chay may tram OneBSS. Hay de cua so nay mo." -ForegroundColor Green
Write-Host "Trang web: $env:VNPTCTO_BASE_URL"
Write-Host "May tram: $env:ONEBSS_WORKER_ID"
Write-Host ""

Invoke-External $VenvPython (Join-Path $Root "scripts\onebss_workstation_worker.py")

Write-Host ""
Write-Host "Worker da dung." -ForegroundColor Yellow
Pause-BeforeExit
