param(
  [string]$BaseUrl = "",
  [string]$WorkerId = "",
  [string]$InternalApiUrl = "",
  [string]$PublicApiRoot = "",
  [switch]$NoPause
)

$ErrorActionPreference = "Continue"

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
  $BaseUrl = [Environment]::GetEnvironmentVariable("VNPTCTO_BASE_URL", "User")
}
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
  $BaseUrl = "https://vnptcto.com"
}
if ([string]::IsNullOrWhiteSpace($WorkerId)) {
  $WorkerId = [Environment]::GetEnvironmentVariable("ONEBSS_WORKER_ID", "User")
}
if ([string]::IsNullOrWhiteSpace($WorkerId)) {
  $WorkerId = "may-tram-$($env:COMPUTERNAME)".ToLower()
}
if ([string]::IsNullOrWhiteSpace($InternalApiUrl)) {
  $InternalApiUrl = [Environment]::GetEnvironmentVariable("INTERNAL_API_URL", "User")
}
if ([string]::IsNullOrWhiteSpace($InternalApiUrl)) {
  $InternalApiUrl = "http://127.0.0.1:8000/api/du-lieu-web"
}

$LogRoot = [Environment]::GetEnvironmentVariable("VNPTCTO_WORKSTATION_LOG_DIR", "User")
if ([string]::IsNullOrWhiteSpace($LogRoot)) {
  $LogRoot = Join-Path $PSScriptRoot "..\logs"
}
$LogRoot = [IO.Path]::GetFullPath($LogRoot)
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$LogFile = Join-Path $LogRoot "workstation-health.log"

function Write-HealthLog {
  param([string]$Message)
  "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") $Message" | Add-Content -Path $LogFile -Encoding UTF8
}

function Test-Http {
  param(
    [string]$Name,
    [string]$Url,
    [int]$TimeoutSec = 15
  )
  try {
    Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec | Out-Null
    [pscustomobject]@{ Name = $Name; Ok = $true; Detail = $Url }
  } catch {
    [pscustomobject]@{ Name = $Name; Ok = $false; Detail = $_.Exception.Message }
  }
}

function Get-WorkerProcesses {
  $root = [Environment]::GetEnvironmentVariable("VNPTCTO_WORKSTATION_ROOT", "User")
  if ([string]::IsNullOrWhiteSpace($root)) {
    $root = Join-Path $PSScriptRoot ".."
  }
  $escapedRoot = [regex]::Escape(([IO.Path]::GetFullPath($root)).TrimEnd("\"))
  $patterns = @(
    "onebss_workstation_worker.py",
    "start_onebss_worker.ps1",
    "run_onebss_worker_background.ps1"
  )
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $commandLine = [string]$_.CommandLine
    if ($commandLine -notmatch $escapedRoot) { return $false }
    foreach ($pattern in $patterns) {
      if ($commandLine -match [regex]::Escape($pattern)) { return $true }
    }
    return $false
  }
}

function Get-WorkerPythonProcesses {
  @(Get-WorkerProcesses) | Where-Object {
    ([string]$_.Name) -match "python" -and ([string]$_.CommandLine) -match [regex]::Escape("onebss_workstation_worker.py")
  }
}

function Get-WorkerPythonInstances {
  $processes = @(Get-WorkerPythonProcesses)
  if ($processes.Count -le 1) {
    return $processes
  }
  $processIds = @{}
  foreach ($process in $processes) {
    $processIds[[int]$process.ProcessId] = $true
  }
  @($processes | Where-Object { -not $processIds.ContainsKey([int]$_.ParentProcessId) })
}

function Get-WorkerWrapperProcesses {
  @(Get-WorkerProcesses) | Where-Object {
    ([string]$_.CommandLine) -match [regex]::Escape("run_onebss_worker_background.ps1")
  }
}

function Wait-WorkerProcessesStable {
  param([int]$Seconds = 15)
  $processes = @(Get-WorkerPythonInstances)
  if ($processes.Count -eq 0) {
    return @()
  }
  Start-Sleep -Seconds $Seconds
  return @(Get-WorkerPythonInstances)
}

function Test-OneBssWorkerTaskUsesBackgroundWorker {
  $task = Get-ScheduledTask -TaskName "VNPTCTO OneBSS Worker" -ErrorAction SilentlyContinue
  if (-not $task) {
    return $false
  }
  foreach ($action in @($task.Actions)) {
    $arguments = [string]$action.Arguments
    if ($arguments -match [regex]::Escape("run_onebss_worker_background.ps1")) {
      return $true
    }
  }
  return $false
}

function Start-WorkerIfMissing {
  $processes = @(Get-WorkerPythonInstances)
  if ($processes.Count -gt 0) {
    $stableProcesses = @(Wait-WorkerProcessesStable 5)
    $wrappers = @(Get-WorkerWrapperProcesses)
    if ($wrappers.Count -gt 1) {
      return [pscustomobject]@{ Ok = $false; Detail = "Dang co nhieu worker chay trung. Wrapper PID: $($wrappers.ProcessId -join ', '); Python PID: $($stableProcesses.ProcessId -join ', ')" }
    }
    if ($stableProcesses.Count -gt 0) {
      return [pscustomobject]@{ Ok = $true; Detail = "Python worker dang chay PID: $($stableProcesses.ProcessId -join ', ')" }
    }
  }
  if (Test-OneBssWorkerTaskUsesBackgroundWorker) {
    try {
      Start-ScheduledTask -TaskName "VNPTCTO OneBSS Worker" -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 5
    } catch {
    }
    $stableProcesses = @(Wait-WorkerProcessesStable 20)
    $wrappers = @(Get-WorkerWrapperProcesses)
    if ($wrappers.Count -gt 1) {
      return [pscustomobject]@{ Ok = $false; Detail = "Da start Scheduled Task nhung co nhieu worker chay trung. Wrapper PID: $($wrappers.ProcessId -join ', '); Python PID: $($stableProcesses.ProcessId -join ', ')" }
    }
    if ($stableProcesses.Count -gt 0) {
      return [pscustomobject]@{ Ok = $true; Detail = "Da start Scheduled Task, Python worker PID: $($stableProcesses.ProcessId -join ', ')" }
    }
  }
  $root = [Environment]::GetEnvironmentVariable("VNPTCTO_WORKSTATION_ROOT", "User")
  if ([string]::IsNullOrWhiteSpace($root)) {
    $root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
  }
  $workerScript = Join-Path $root "scripts\run_onebss_worker_background.ps1"
  if (-not (Test-Path -LiteralPath $workerScript)) {
    return [pscustomobject]@{ Ok = $false; Detail = "Khong tim thay worker script: $workerScript" }
  }
  try {
    $workerArg = "`"$workerScript`""
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $workerArg, "-NoPause") -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 3
  } catch {
    return [pscustomobject]@{ Ok = $false; Detail = $_.Exception.Message }
  }
  $stableProcesses = @(Wait-WorkerProcessesStable 20)
  $wrappers = @(Get-WorkerWrapperProcesses)
  if ($wrappers.Count -gt 1) {
    return [pscustomobject]@{ Ok = $false; Detail = "Da start worker fallback nhung co nhieu worker chay trung. Wrapper PID: $($wrappers.ProcessId -join ', '); Python PID: $($stableProcesses.ProcessId -join ', ')" }
  }
  if ($stableProcesses.Count -gt 0) {
    return [pscustomobject]@{ Ok = $true; Detail = "Da start worker fallback, Python worker PID: $($stableProcesses.ProcessId -join ', ')" }
  }
  return [pscustomobject]@{ Ok = $false; Detail = "Da goi start worker nhung chua thay process. Xem onebss-worker-error.log." }
}

$results = New-Object System.Collections.Generic.List[object]
$results.Add((Test-Http "Web login" "$($BaseUrl.TrimEnd('/'))/login"))

$workerStart = Start-WorkerIfMissing
$results.Add([pscustomobject]@{ Name = "Worker process"; Ok = $workerStart.Ok; Detail = $workerStart.Detail })

$token = [Environment]::GetEnvironmentVariable("INTERNAL_API_TOKEN", "User")
if (-not [string]::IsNullOrWhiteSpace($token)) {
  try {
    $heartbeatRoles = @("health_check")
    if ($workerStart.Ok) {
      $heartbeatRoles = @("health_check", "onebss_worker", "sql_report_worker", "sql_export_worker", "ftp_report_worker", "excel_export", "drive_upload")
    }
    $body = @{
      worker_id = $WorkerId
      status = "health_check"
      roles = $heartbeatRoles
      version = "health-check-2026.08.03-failover"
      local_time = (Get-Date).ToString("s")
      message = "Health check tu may tram."
      details = @{
        computer = $env:COMPUTERNAME
        worker_process = $workerStart.Detail
      }
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Uri "$($BaseUrl.TrimEnd('/'))/api/workstation/heartbeat" -Method Post -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body $body -TimeoutSec 15 | Out-Null
    $results.Add([pscustomobject]@{ Name = "Heartbeat web"; Ok = $true; Detail = $WorkerId })
  } catch {
    $results.Add([pscustomobject]@{ Name = "Heartbeat web"; Ok = $false; Detail = $_.Exception.Message })
  }
} else {
  $results.Add([pscustomobject]@{ Name = "Heartbeat web"; Ok = $false; Detail = "Chua co INTERNAL_API_TOKEN trong User environment." })
}

$optionalTaskNames = @("VNPTCTO API Trung Gian", "VNPTCTO API Watchdog")
foreach ($taskName in @("VNPTCTO OneBSS Worker", "VNPTCTO API Trung Gian", "VNPTCTO API Watchdog", "VNPTCTO Workstation Health Check")) {
  $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  if ($task) {
    $results.Add([pscustomobject]@{ Name = "Task $taskName"; Ok = $true; Detail = $task.State })
  } else {
    $optionalTask = $optionalTaskNames -contains $taskName
    $detail = if ($optionalTask) { "Khong tim thay Scheduled Task; khong bat buoc neu Local API dang OK." } else { "Khong tim thay Scheduled Task." }
    $results.Add([pscustomobject]@{ Name = "Task $taskName"; Ok = $optionalTask; Detail = $detail })
  }
}

$results.Add((Test-Http "Local API root" "http://127.0.0.1:8000/"))
$results.Add((Test-Http "Local API config" "http://127.0.0.1:8000/config-status"))
$results.Add((Test-Http "Local Oracle" "http://127.0.0.1:8000/test-oracle" 20))
$results.Add((Test-Http "Local Drive" "http://127.0.0.1:8000/test-drive" 20))
$cloudflared = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($cloudflared -and -not [string]::IsNullOrWhiteSpace($PublicApiRoot)) {
  $results.Add((Test-Http "Public API root" "$($PublicApiRoot.TrimEnd('/'))/"))
} else {
  $results.Add([pscustomobject]@{ Name = "Public API root"; Ok = $true; Detail = "Bo qua vi chua cai cloudflared; khong bat buoc cho worker outbound." })
}

$failed = $results | Where-Object { -not $_.Ok }
$results | Format-Table -AutoSize
Write-HealthLog (($results | ConvertTo-Json -Compress) -replace "`r?`n", "")

if ($failed) {
  Write-Host ""
  Write-Host "Co hang muc can cau hinh/kiem tra lai. Xem log: $LogFile" -ForegroundColor Yellow
  if (-not $NoPause) { Read-Host "Nhan Enter de dong" | Out-Null }
  exit 1
}

Write-Host ""
Write-Host "Health check may tram OK. Log: $LogFile" -ForegroundColor Green
if (-not $NoPause) { Read-Host "Nhan Enter de dong" | Out-Null }
