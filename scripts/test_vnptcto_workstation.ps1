param(
  [string]$BaseUrl = "",
  [string]$WorkerId = "",
  [string]$InternalApiUrl = "",
  [string]$PublicApiRoot = "https://api.vnptcto.com",
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

$results = New-Object System.Collections.Generic.List[object]
$results.Add((Test-Http "Web login" "$($BaseUrl.TrimEnd('/'))/login"))

$token = [Environment]::GetEnvironmentVariable("INTERNAL_API_TOKEN", "User")
if (-not [string]::IsNullOrWhiteSpace($token)) {
  try {
    $body = @{
      worker_id = $WorkerId
      status = "health_check"
      roles = @("health_check", "onebss_worker")
      version = "health-check-2026.07.20"
      local_time = (Get-Date).ToString("s")
      message = "Health check tu may tram."
      details = @{ computer = $env:COMPUTERNAME }
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Uri "$($BaseUrl.TrimEnd('/'))/api/workstation/heartbeat" -Method Post -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body $body -TimeoutSec 15 | Out-Null
    $results.Add([pscustomobject]@{ Name = "Heartbeat web"; Ok = $true; Detail = $WorkerId })
  } catch {
    $results.Add([pscustomobject]@{ Name = "Heartbeat web"; Ok = $false; Detail = $_.Exception.Message })
  }
} else {
  $results.Add([pscustomobject]@{ Name = "Heartbeat web"; Ok = $false; Detail = "Chua co INTERNAL_API_TOKEN trong User environment." })
}

foreach ($taskName in @("VNPTCTO OneBSS Worker", "VNPTCTO API Trung Gian", "VNPTCTO API Watchdog", "VNPTCTO Workstation Health Check")) {
  $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  if ($task) {
    $results.Add([pscustomobject]@{ Name = "Task $taskName"; Ok = $true; Detail = $task.State })
  } else {
    $results.Add([pscustomobject]@{ Name = "Task $taskName"; Ok = $false; Detail = "Khong tim thay Scheduled Task." })
  }
}

$results.Add((Test-Http "Local API root" "http://127.0.0.1:8000/"))
$results.Add((Test-Http "Local Oracle" "http://127.0.0.1:8000/test-oracle" 20))
$results.Add((Test-Http "Local Drive" "http://127.0.0.1:8000/test-drive" 20))
$results.Add((Test-Http "Public API root" "$($PublicApiRoot.TrimEnd('/'))/"))

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
