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

$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "powershell.exe"
$processInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartWorkerScript`" -NoPause"
$processInfo.WorkingDirectory = $Root
$processInfo.UseShellExecute = $false
$processInfo.CreateNoWindow = $true
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $processInfo

$outputHandler = [System.Diagnostics.DataReceivedEventHandler]{
  param($sender, $eventArgs)
  if ($null -ne $eventArgs.Data -and $eventArgs.Data.Length -gt 0) {
    "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") $($eventArgs.Data)" | Add-Content -Path $script:LogFile -Encoding UTF8
  }
}

$errorHandler = [System.Diagnostics.DataReceivedEventHandler]{
  param($sender, $eventArgs)
  if ($null -ne $eventArgs.Data -and $eventArgs.Data.Length -gt 0) {
    "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") $($eventArgs.Data)" | Add-Content -Path $script:LogFile -Encoding UTF8
    "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") $($eventArgs.Data)" | Add-Content -Path $script:ErrorLogFile -Encoding UTF8
  }
}

$process.add_OutputDataReceived($outputHandler)
$process.add_ErrorDataReceived($errorHandler)

try {
  $process.Start() | Out-Null
  $process.BeginOutputReadLine()
  $process.BeginErrorReadLine()
  Write-WorkerLog "Worker process da chay. PID: $($process.Id)"
  $process.WaitForExit()
  if ($process.ExitCode -ne 0) {
    Write-WorkerLog "Worker dung voi ma loi: $($process.ExitCode)" $script:ErrorLogFile
    Write-WorkerLog "Worker dung voi ma loi: $($process.ExitCode)"
    exit $process.ExitCode
  }
  Write-WorkerLog "Worker da dung binh thuong."
} finally {
  $process.remove_OutputDataReceived($outputHandler)
  $process.remove_ErrorDataReceived($errorHandler)
  $process.Dispose()
}

Pause-BeforeExit
