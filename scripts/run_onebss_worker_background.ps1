param(
  [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StartWorkerScript = Join-Path $Root "scripts\start_onebss_worker.ps1"

if (-not (Test-Path -LiteralPath $StartWorkerScript)) {
  throw "Khong tim thay worker script: $StartWorkerScript"
}

$LogRoot = [Environment]::GetEnvironmentVariable("VNPTCTO_WORKSTATION_LOG_DIR", "User")
if ([string]::IsNullOrWhiteSpace($LogRoot)) {
  $LogRoot = Join-Path $Root "logs"
}
$LogRoot = [IO.Path]::GetFullPath($LogRoot)
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null

$script:LogFile = Join-Path $LogRoot "onebss-worker.log"
$script:ErrorLogFile = Join-Path $LogRoot "onebss-worker-error.log"

function Write-WorkerLog {
  param(
    [string]$Message,
    [string]$Path = $script:LogFile
  )
  "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") $Message" | Add-Content -Path $Path -Encoding UTF8
}

function Pause-BeforeExit {
  if (-not $NoPause) {
    Read-Host "Nhan Enter de dong" | Out-Null
  }
}

trap {
  $message = $_.Exception.Message
  Write-WorkerLog "Launcher loi: $message" $script:ErrorLogFile
  Write-WorkerLog "Launcher loi: $message"
  Pause-BeforeExit
  exit 1
}

Set-Location $Root
Write-WorkerLog "Khoi dong OneBSS worker background. Root: $Root"
Write-WorkerLog "Log loi: $script:ErrorLogFile"

$RestartDelaySeconds = 10

while ($true) {
  try {
    $safeWorkerScript = $StartWorkerScript.Replace("'", "''")
    $safeLogFile = $script:LogFile.Replace("'", "''")
    $command = "& '$safeWorkerScript' -NoPause *>> '$safeLogFile'"
    $process = Start-Process `
      -FilePath "powershell.exe" `
      -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command) `
      -WorkingDirectory $Root `
      -WindowStyle Hidden `
      -PassThru
    Write-WorkerLog "Worker process da chay. PID: $($process.Id)"
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
      Write-WorkerLog "Worker dung voi ma loi: $($process.ExitCode)" $script:ErrorLogFile
      Write-WorkerLog "Worker dung voi ma loi: $($process.ExitCode)"
    } else {
      Write-WorkerLog "Worker da dung binh thuong."
    }
  } catch {
    $message = $_.Exception.Message
    Write-WorkerLog "Khong chay duoc worker: $message" $script:ErrorLogFile
    Write-WorkerLog "Khong chay duoc worker: $message"
  }

  Write-WorkerLog "Tu khoi dong lai worker sau $RestartDelaySeconds giay."
  Start-Sleep -Seconds $RestartDelaySeconds
}

Pause-BeforeExit
