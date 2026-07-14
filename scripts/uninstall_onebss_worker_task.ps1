param(
  [string]$TaskName = "VNPTCTO OneBSS Worker"
)

$ErrorActionPreference = "Stop"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Da go tu dong chay: $TaskName" -ForegroundColor Green
} else {
  Write-Host "Khong thay task tu dong chay: $TaskName" -ForegroundColor Yellow
}

Read-Host "Nhan Enter de dong" | Out-Null
