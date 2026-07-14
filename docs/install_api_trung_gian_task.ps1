# Run this file in an Administrator PowerShell window on the workstation.
# It creates:
# - VNPTCTO API Trung Gian: starts the local FastAPI middleware at boot.
# - VNPTCTO API Watchdog: checks API/cloudflared every 5 minutes and restarts them if needed.

$ErrorActionPreference = "Stop"

$ApiRoot = "C:\VNPTCTO"
$ApiDir = Join-Path $ApiRoot "api-trung-gian"
$LogDir = Join-Path $ApiRoot "logs"
$StartBat = Join-Path $ApiRoot "start-api-trung-gian.bat"
$WatchdogPs1 = Join-Path $ApiRoot "watch-api-trung-gian.ps1"
$TaskName = "VNPTCTO API Trung Gian"
$WatchdogTaskName = "VNPTCTO API Watchdog"
$LocalHealthUrl = "http://127.0.0.1:8000/"
$PublicHealthUrl = "https://api.vnptcto.com/"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Hay mo PowerShell bang Run as administrator roi chay lai script nay."
    }
}

function Find-PythonExe {
    $candidates = @()

    try {
        $pyOutput = & py -0p 2>$null
        foreach ($line in $pyOutput) {
            if ($line -match "([A-Za-z]:\\.*python\.exe)$") {
                $candidates += $Matches[1].Trim()
            }
        }
    } catch {
    }

    try {
        $whereOutput = & where.exe python 2>$null
        foreach ($line in $whereOutput) {
            $candidates += $line.Trim()
        }
    } catch {
    }

    $python = $candidates |
        Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
        Select-Object -First 1

    if (-not $python) {
        throw "Khong tim thay python.exe. Hay cai Python tren may tram truoc."
    }

    return $python
}

Assert-Administrator

if (-not (Test-Path -LiteralPath $ApiDir)) {
    throw "Khong tim thay thu muc $ApiDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $ApiDir "main.py"))) {
    throw "Khong tim thay $ApiDir\main.py"
}

if (-not (Test-Path -LiteralPath (Join-Path $ApiDir ".env"))) {
    throw "Khong tim thay $ApiDir\.env"
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$PythonExe = Find-PythonExe

$startBatContent = @"
@echo off
cd /d "$ApiDir"
if not exist "$LogDir" mkdir "$LogDir"
"$PythonExe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips="*" >> "$LogDir\api-trung-gian.log" 2>&1
"@
Set-Content -Path $StartBat -Value $startBatContent -Encoding ASCII

$watchdogContent = @"
`$ErrorActionPreference = "SilentlyContinue"
`$TaskName = "$TaskName"
`$LogDir = "$LogDir"
`$LogFile = Join-Path `$LogDir "api-watchdog.log"
`$LocalHealthUrl = "$LocalHealthUrl"
`$PublicHealthUrl = "$PublicHealthUrl"

function Write-WatchLog([string]`$Message) {
    if (-not (Test-Path -LiteralPath `$LogDir)) {
        New-Item -ItemType Directory -Path `$LogDir -Force | Out-Null
    }
    "`$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") `$Message" | Add-Content -Path `$LogFile -Encoding UTF8
}

`$cloudflared = Get-Service cloudflared -ErrorAction SilentlyContinue
if (`$cloudflared) {
    Set-Service cloudflared -StartupType Automatic
    if (`$cloudflared.Status -ne "Running") {
        Start-Service cloudflared
        Write-WatchLog "Started cloudflared service."
    }
}

`$localOk = `$false
try {
    Invoke-RestMethod `$LocalHealthUrl -TimeoutSec 8 | Out-Null
    `$localOk = `$true
} catch {
    `$localOk = `$false
}

if (-not `$localOk) {
    `$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    foreach (`$listener in `$listeners) {
        `$proc = Get-CimInstance Win32_Process -Filter "ProcessId=`$(`$listener.OwningProcess)" -ErrorAction SilentlyContinue
        if (`$proc.CommandLine -match "uvicorn|main:app|api-trung-gian") {
            Stop-Process -Id `$listener.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-WatchLog "Stopped stale API process `$(`$listener.OwningProcess)."
        }
    }
    Start-ScheduledTask -TaskName `$TaskName
    Write-WatchLog "Started API scheduled task."
    Start-Sleep -Seconds 10
}

try {
    Invoke-RestMethod `$PublicHealthUrl -TimeoutSec 12 | Out-Null
} catch {
    `$cloudflared = Get-Service cloudflared -ErrorAction SilentlyContinue
    if (`$cloudflared) {
        Restart-Service cloudflared -Force
        Write-WatchLog "Restarted cloudflared because public health check failed."
    }
}
"@
Set-Content -Path $WatchdogPs1 -Value $watchdogContent -Encoding ASCII

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$StartBat`"" `
    -WorkingDirectory $ApiDir

$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

$watchdogAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$WatchdogPs1`""

$watchdogStartupTrigger = New-ScheduledTaskTrigger -AtStartup
$watchdogIntervalTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

Register-ScheduledTask `
    -TaskName $WatchdogTaskName `
    -Action $watchdogAction `
    -Trigger @($watchdogStartupTrigger, $watchdogIntervalTrigger) `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

$cfService = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($cfService) {
    Set-Service cloudflared -StartupType Automatic
    try {
        sc.exe failure cloudflared reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
    } catch {
    }
    if ($cfService.Status -ne "Running") {
        Start-Service cloudflared
    }
} else {
    Write-Warning "Khong tim thay service cloudflared. Hay cai Cloudflare Tunnel service rieng."
}

Start-ScheduledTask -TaskName $TaskName
Start-ScheduledTask -TaskName $WatchdogTaskName
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "Da tao task tu dong."
Write-Host "Python: $PythonExe"
Write-Host "Start script: $StartBat"
Write-Host "Watchdog script: $WatchdogPs1"
Write-Host "Log API: $LogDir\api-trung-gian.log"
Write-Host "Log watchdog: $LogDir\api-watchdog.log"
Write-Host ""

Get-ScheduledTask -TaskName $TaskName, $WatchdogTaskName | Select-Object TaskName, State

Write-Host ""
Write-Host "Kiem tra nhanh:"
try {
    Invoke-RestMethod "http://127.0.0.1:8000/test-oracle" -TimeoutSec 20
} catch {
    Write-Warning "Local API chua OK: $($_.Exception.Message)"
}
try {
    Invoke-RestMethod "https://api.vnptcto.com/test-oracle" -TimeoutSec 20
} catch {
    Write-Warning "Public tunnel chua OK: $($_.Exception.Message)"
}
