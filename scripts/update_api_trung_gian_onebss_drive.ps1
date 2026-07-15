param(
  [string]$ApiDir = "C:\VNPTCTO\api-trung-gian"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Source = Join-Path $Root "docs\api_trung_gian_drive_export.py"
$TargetDir = $ApiDir
$Target = Join-Path $TargetDir "main.py"

function Pause-BeforeExit {
  Read-Host "Nhan Enter de dong" | Out-Null
}

trap {
  Write-Host ""
  Write-Host "Cap nhat API trung gian bi loi:" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Pause-BeforeExit
  exit 1
}

if (-not (Test-Path $Source)) {
  throw "Khong tim thay file nguon: $Source"
}

if (-not (Test-Path $TargetDir)) {
  throw "Khong tim thay thu muc API trung gian: $TargetDir"
}

if (-not (Test-Path $Target)) {
  throw "Khong tim thay main.py hien tai: $Target"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $TargetDir "main.py.bak-$stamp"
Copy-Item -LiteralPath $Target -Destination $Backup -Force
Copy-Item -LiteralPath $Source -Destination $Target -Force

Write-Host "Da backup main.py cu:" -ForegroundColor Green
Write-Host $Backup
Write-Host "Da cap nhat API trung gian de ho tro action upload_file_to_drive." -ForegroundColor Green

$taskName = "VNPTCTO API Trung Gian"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
  Write-Host "Dang restart Scheduled Task: $taskName" -ForegroundColor Cyan
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
  Start-ScheduledTask -TaskName $taskName
  Write-Host "Da restart task API trung gian." -ForegroundColor Green
} else {
  Write-Host "Khong thay Scheduled Task '$taskName'. Hay restart API trung gian theo cach dang dung hien tai." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Kiem tra sau khi cap nhat:" -ForegroundColor Cyan
Write-Host "Invoke-RestMethod https://api.vnptcto.com/test-drive"
Write-Host "Invoke-RestMethod https://api.vnptcto.com/test-oracle"
Pause-BeforeExit
