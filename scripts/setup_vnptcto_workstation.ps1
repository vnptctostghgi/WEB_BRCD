param(
  [string]$InstallRoot = "D:\Tool_Tram_VNPTCTO.COM",
  [string]$BaseUrl = "https://vnptcto.com",
  [string]$WorkerId = "",
  [string]$InternalApiToken = "",
  [string]$InternalApiUrl = "https://api.vnptcto.com/api/du-lieu-web",
  [string]$WorkerDriveUploadApiUrl = "http://127.0.0.1:8000/api/du-lieu-web",
  [string]$ApiRoot = "C:\VNPTCTO",
  [string]$OracleDbDsn = "",
  [string]$OracleDbHost = "",
  [string]$OracleDbPort = "1521",
  [string]$OracleDbService = "",
  [string]$OracleDbSid = "",
  [string]$OracleDbUser = "",
  [string]$OracleDbPass = "",
  [string]$OneBssTaskTimeoutSeconds = "1200",
  [string]$SqlWorkerTimeoutSeconds = "1800",
  [string]$ExportPageSize = "20000",
  [string]$ExportMaxRows = "1000000",
  [string]$ConfigFile = "",
  [switch]$StartNow,
  [switch]$SkipApiMiddleware,
  [switch]$SkipPlaywright,
  [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$SetupScriptPath = $PSCommandPath

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "== $Message" -ForegroundColor Cyan
}

function Pause-BeforeExit {
  if (-not $NoPause) {
    Write-Host "Cua so se tu dong dong sau 10 giay."
    Start-Sleep -Seconds 10
  }
}

function Assert-Administrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Hay chay file nay bang Run as administrator."
  }
}

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

function Set-UserEnvironment {
  param([string]$Name, [string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return
  }
  [Environment]::SetEnvironmentVariable($Name, $Value, "User")
  Set-Item -Path "Env:$Name" -Value $Value
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
  Write-Step "Cai Python 3.12 bang winget"
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

function New-PythonVenv {
  param([string]$VenvDir)
  if (Test-Path -LiteralPath (Join-Path $VenvDir "Scripts\python.exe")) {
    return
  }
  $launcher = Ensure-Python
  $venvArgs = @($launcher.Args) + @("-m", "venv", $VenvDir)
  Invoke-External $launcher.File @venvArgs
}

function Same-Path {
  param([string]$Left, [string]$Right)
  try {
    return ([IO.Path]::GetFullPath($Left).TrimEnd("\") -ieq [IO.Path]::GetFullPath($Right).TrimEnd("\"))
  } catch {
    return $false
  }
}

function Source-Root {
  $scriptDir = Split-Path -Parent $SetupScriptPath
  if ((Split-Path -Leaf $scriptDir) -ieq "scripts") {
    return Split-Path -Parent $scriptDir
  }
  return $scriptDir
}

function Import-SetupConfig {
  param([string]$SourceRoot)
  $candidate = $ConfigFile
  if ([string]::IsNullOrWhiteSpace($candidate)) {
    $candidate = Join-Path $SourceRoot "workstation-install-config.ps1"
  }
  if ([string]::IsNullOrWhiteSpace($candidate) -or -not (Test-Path -LiteralPath $candidate)) {
    return @{}
  }
  . $candidate
  $variable = Get-Variable -Name "VNPTCTO_WORKSTATION_CONFIG" -Scope Local -ErrorAction SilentlyContinue
  if (-not $variable -or -not ($variable.Value -is [System.Collections.IDictionary])) {
    Write-Warning "File cau hinh $candidate khong co VNPTCTO_WORKSTATION_CONFIG hop le. Script se dung mac dinh."
    return @{}
  }
  Write-Host "Da nap cau hinh tu $candidate" -ForegroundColor Green
  return $variable.Value
}

function Config-Value {
  param(
    [System.Collections.IDictionary]$Config,
    [string]$Name
  )
  if ($Config.Contains($Name) -and $null -ne $Config[$Name]) {
    return [string]$Config[$Name]
  }
  return ""
}

function Resolve-SetupValue {
  param(
    [System.Collections.IDictionary]$Config,
    [string]$Name,
    [string]$CurrentValue = "",
    [string]$DefaultValue = "",
    [string]$EnvName = ""
  )
  $current = [string]$CurrentValue
  $configured = Config-Value $Config $Name
  if (-not [string]::IsNullOrWhiteSpace($configured) -and ([string]::IsNullOrWhiteSpace($current) -or $current -eq $DefaultValue)) {
    return $configured.Trim()
  }
  if (-not [string]::IsNullOrWhiteSpace($current)) {
    return $current.Trim()
  }
  if (-not [string]::IsNullOrWhiteSpace($EnvName)) {
    $existing = [Environment]::GetEnvironmentVariable($EnvName, "User")
    if (-not [string]::IsNullOrWhiteSpace($existing)) {
      return $existing.Trim()
    }
  }
  return [string]$DefaultValue
}

function Resolve-SetupBool {
  param(
    [System.Collections.IDictionary]$Config,
    [string]$Name,
    [bool]$DefaultValue = $false
  )
  if (-not $Config.Contains($Name) -or $null -eq $Config[$Name]) {
    return $DefaultValue
  }
  $value = $Config[$Name]
  if ($value -is [bool]) {
    return [bool]$value
  }
  $text = ([string]$value).Trim().ToLowerInvariant()
  if ($text -in @("1", "true", "yes", "y", "on")) {
    return $true
  }
  if ($text -in @("0", "false", "no", "n", "off")) {
    return $false
  }
  return $DefaultValue
}

function Copy-WorkspaceFiles {
  param([string]$SourceRoot, [string]$TargetRoot)
  if (Same-Path $SourceRoot $TargetRoot) {
    return
  }
  New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
  foreach ($item in @("app", "docs", "scripts", "requirements.txt", ".env.example", "README.md", "HUONG_DAN_MAY_TRAM_ONEBSS.md", "workstation-install-config.ps1", "SETUP_VNPTCTO_WORKSTATION.bat", "START_ONEBSS_WORKER.bat", "START_ONEBSS_WORKER_BACKGROUND.bat", "INSTALL_ONEBSS_WORKER_AUTOSTART.bat", "UNINSTALL_ONEBSS_WORKER_AUTOSTART.bat")) {
    $source = Join-Path $SourceRoot $item
    if (-not (Test-Path -LiteralPath $source)) {
      continue
    }
    $target = Join-Path $TargetRoot $item
    if (Test-Path -LiteralPath $source -PathType Container) {
      New-Item -ItemType Directory -Path $target -Force | Out-Null
      Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
    } else {
      Copy-Item -LiteralPath $source -Destination $target -Force
    }
  }
}

function DotEnvValue {
  param([string]$Value)
  if ($null -eq $Value) {
    return "''"
  }
  return "'" + ($Value -replace "'", "''") + "'"
}

function Set-DotEnvValue {
  param([string]$Path, [string]$Name, [string]$Value)
  $line = "$Name=$(DotEnvValue $Value)"
  if (-not (Test-Path -LiteralPath $Path)) {
    Set-Content -Path $Path -Value $line -Encoding UTF8
    return
  }
  $content = Get-Content -LiteralPath $Path -Raw
  if ($content -match "(?m)^$([regex]::Escape($Name))=") {
    $content = [regex]::Replace($content, "(?m)^$([regex]::Escape($Name))=.*$", [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $line })
    Set-Content -Path $Path -Value $content -Encoding UTF8
  } else {
    Add-Content -Path $Path -Value $line -Encoding UTF8
  }
}

function Test-DotEnvKey {
  param([string]$Path, [string]$Name)
  if (-not (Test-Path -LiteralPath $Path)) {
    return $false
  }
  $content = Get-Content -LiteralPath $Path -Raw
  return [bool]($content -match "(?m)^$([regex]::Escape($Name))=")
}

function Ensure-WorkstationEnvFile {
  param([string]$Root)
  $envFile = Join-Path $Root ".env"
  if (Test-Path -LiteralPath $envFile) {
    $backup = Join-Path $Root ".env.bak-$(Get-Date -Format yyyyMMdd_HHmmss)"
    Copy-Item -LiteralPath $envFile -Destination $backup -Force
  }
  $secretBytes = New-Object byte[] 48
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($secretBytes)
  } finally {
    $rng.Dispose()
  }
  Set-DotEnvValue $envFile "APP_ENV" "workstation"
  Set-DotEnvValue $envFile "APP_DATABASE_BACKEND" "sqlite"
  Set-DotEnvValue $envFile "APP_DATABASE_PATH" (Join-Path $Root "data\app.db")
  if (-not (Test-DotEnvKey $envFile "SESSION_SECRET")) {
    $sessionSecret = [Convert]::ToBase64String($secretBytes)
    Set-DotEnvValue $envFile "SESSION_SECRET" $sessionSecret
  }
  Set-DotEnvValue $envFile "INTERNAL_API_TOKEN" $InternalApiToken
  Set-DotEnvValue $envFile "INTERNAL_API_URL" $InternalApiUrl
  Set-DotEnvValue $envFile "INTERNAL_API_MOCK_MODE" "false"
  Set-DotEnvValue $envFile "VNPTCTO_BASE_URL" $BaseUrl
  Set-DotEnvValue $envFile "ONEBSS_WORKER_ID" $WorkerId
  Set-DotEnvValue $envFile "ONEBSS_LOGIN_URL" $onebssLoginUrl
  Set-DotEnvValue $envFile "ONEBSS_DOWNLOAD_TIMEOUT_SECONDS" $onebssDownloadTimeoutSeconds
  Set-DotEnvValue $envFile "ONEBSS_TASK_TIMEOUT_SECONDS" $onebssTaskTimeoutSeconds
  Set-DotEnvValue $envFile "SQL_WORKER_TIMEOUT_SECONDS" $sqlWorkerTimeoutSeconds
  Set-DotEnvValue $envFile "EXPORT_PAGE_SIZE" $exportPageSize
  Set-DotEnvValue $envFile "EXPORT_MAX_ROWS" $exportMaxRows
  Set-DotEnvValue $envFile "ONEBSS_USERNAME" $env:ONEBSS_USERNAME
  Set-DotEnvValue $envFile "ONEBSS_PASSWORD" $env:ONEBSS_PASSWORD
  Set-DotEnvValue $envFile "GOOGLE_DRIVE_FOLDER_ID" $googleDriveFolderId
  Set-DotEnvValue $envFile "GOOGLE_DRIVE_OAUTH_CLIENT_ID" $googleDriveOauthClientId
  Set-DotEnvValue $envFile "GOOGLE_DRIVE_OAUTH_CLIENT_SECRET" $googleDriveOauthClientSecret
  Set-DotEnvValue $envFile "GOOGLE_DRIVE_OAUTH_REDIRECT_URI" $googleDriveOauthRedirectUri
  Set-DotEnvValue $envFile "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64" $googleDriveServiceAccountJsonBase64
  Set-DotEnvValue $envFile "DATA_MINING_DOWNLOAD_DIR" (Join-Path $Root "downloads")
}

function Ensure-ApiEnvFile {
  param([string]$ApiDir)
  $apiEnv = Join-Path $ApiDir ".env"
  $oauthTokenFile = Join-Path $ApiDir "drive-oauth-token.json"
  $oauthClientFile = Join-Path $ApiDir "drive-oauth-client.json"
  $driveAuthMode = "oauth"
  if (-not (Test-Path -LiteralPath $apiEnv)) {
    Set-Content -Path $apiEnv -Value @(
      "API_TOKEN=$(DotEnvValue $InternalApiToken)"
      "EXPORT_DIR=$(DotEnvValue (Join-Path $ApiRoot 'exports'))"
      "EXPORT_PAGE_SIZE=$(DotEnvValue $exportPageSize)"
      "EXPORT_MAX_ROWS=$(DotEnvValue $exportMaxRows)"
      "DB_DSN=$(DotEnvValue $oracleDbDsn)"
      "DB_HOST=$(DotEnvValue $oracleDbHost)"
      "DB_PORT=$(DotEnvValue $oracleDbPort)"
      "DB_SERVICE=$(DotEnvValue $oracleDbService)"
      "DB_SID=$(DotEnvValue $oracleDbSid)"
      "DB_USER=$(DotEnvValue $oracleDbUser)"
      "DB_PASS=$(DotEnvValue $oracleDbPass)"
      "GOOGLE_DRIVE_AUTH_MODE=$(DotEnvValue $driveAuthMode)"
      "GOOGLE_DRIVE_OAUTH_CLIENT_FILE=$(DotEnvValue $oauthClientFile)"
      "GOOGLE_DRIVE_OAUTH_TOKEN_FILE=$(DotEnvValue $oauthTokenFile)"
      "GOOGLE_DRIVE_FOLDER_ID=$(DotEnvValue $googleDriveFolderId)"
      "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64=$(DotEnvValue $googleDriveServiceAccountJsonBase64)"
    ) -Encoding UTF8
    Ensure-ApiDriveOauthFiles $ApiDir $oauthClientFile $oauthTokenFile
    return
  }
  Set-DotEnvValue $apiEnv "API_TOKEN" $InternalApiToken
  Set-DotEnvValue $apiEnv "EXPORT_DIR" (Join-Path $ApiRoot "exports")
  Set-DotEnvValue $apiEnv "EXPORT_PAGE_SIZE" $exportPageSize
  Set-DotEnvValue $apiEnv "EXPORT_MAX_ROWS" $exportMaxRows
  Set-DotEnvValue $apiEnv "DB_DSN" $oracleDbDsn
  if (-not [string]::IsNullOrWhiteSpace($oracleDbHost)) { Set-DotEnvValue $apiEnv "DB_HOST" $oracleDbHost }
  if (-not [string]::IsNullOrWhiteSpace($oracleDbPort)) { Set-DotEnvValue $apiEnv "DB_PORT" $oracleDbPort }
  if (-not [string]::IsNullOrWhiteSpace($oracleDbService)) { Set-DotEnvValue $apiEnv "DB_SERVICE" $oracleDbService }
  if (-not [string]::IsNullOrWhiteSpace($oracleDbSid)) { Set-DotEnvValue $apiEnv "DB_SID" $oracleDbSid }
  if (-not [string]::IsNullOrWhiteSpace($oracleDbUser)) { Set-DotEnvValue $apiEnv "DB_USER" $oracleDbUser }
  if (-not [string]::IsNullOrWhiteSpace($oracleDbPass)) { Set-DotEnvValue $apiEnv "DB_PASS" $oracleDbPass }
  Set-DotEnvValue $apiEnv "GOOGLE_DRIVE_FOLDER_ID" $googleDriveFolderId
  Set-DotEnvValue $apiEnv "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64" $googleDriveServiceAccountJsonBase64
  Set-DotEnvValue $apiEnv "GOOGLE_DRIVE_AUTH_MODE" $driveAuthMode
  Set-DotEnvValue $apiEnv "GOOGLE_DRIVE_OAUTH_CLIENT_FILE" $oauthClientFile
  Set-DotEnvValue $apiEnv "GOOGLE_DRIVE_OAUTH_TOKEN_FILE" $oauthTokenFile
  Ensure-ApiDriveOauthFiles $ApiDir $oauthClientFile $oauthTokenFile
}

function Ensure-ApiDriveOauthFiles {
  param(
    [string]$ApiDir,
    [string]$OauthClientFile,
    [string]$OauthTokenFile
  )
  if ([string]::IsNullOrWhiteSpace($googleDriveOauthClientId) -or [string]::IsNullOrWhiteSpace($googleDriveOauthClientSecret)) {
    return
  }
  New-Item -ItemType Directory -Path $ApiDir -Force | Out-Null
  $redirectUri = $googleDriveOauthRedirectUri
  if ([string]::IsNullOrWhiteSpace($redirectUri)) {
    $redirectUri = "http://127.0.0.1:8000/drive-oauth/callback"
  }
  $clientPayload = @{
    installed = @{
      client_id = $googleDriveOauthClientId
      client_secret = $googleDriveOauthClientSecret
      auth_uri = "https://accounts.google.com/o/oauth2/auth"
      token_uri = "https://oauth2.googleapis.com/token"
      redirect_uris = @($redirectUri)
    }
  }
  $clientPayload | ConvertTo-Json -Depth 5 | Set-Content -Path $OauthClientFile -Encoding UTF8
  if ([string]::IsNullOrWhiteSpace($googleDriveOauthRefreshToken)) {
    return
  }
  $tokenPayload = @{
    token = ""
    refresh_token = $googleDriveOauthRefreshToken
    token_uri = "https://oauth2.googleapis.com/token"
    client_id = $googleDriveOauthClientId
    client_secret = $googleDriveOauthClientSecret
    scopes = @("https://www.googleapis.com/auth/drive")
  }
  $tokenPayload | ConvertTo-Json -Depth 5 | Set-Content -Path $OauthTokenFile -Encoding UTF8
}

function Stop-ApiMiddlewareProcesses {
  param([string]$ApiDir)
  foreach ($taskName in @("VNPTCTO API Watchdog", "VNPTCTO API Trung Gian")) {
    try {
      $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
      if ($task) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
      }
    } catch {
    }
  }
  $escapedApiDir = [regex]::Escape($ApiDir)
  $listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
  foreach ($listener in $listeners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
    $commandLine = [string]($proc.CommandLine)
    if ($commandLine -match "main:app|api-trung-gian|$escapedApiDir") {
      Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
  }
  Start-Sleep -Seconds 2
}

function Stop-WorkstationWorkerProcesses {
  param([string]$Root)
  Write-Step "Dung worker may tram cu neu dang chay"
  try {
    $task = Get-ScheduledTask -TaskName "VNPTCTO OneBSS Worker" -ErrorAction SilentlyContinue
    if ($task) {
      Stop-ScheduledTask -TaskName "VNPTCTO OneBSS Worker" -ErrorAction SilentlyContinue
    }
  } catch {
  }
  $escapedRoot = [regex]::Escape(([IO.Path]::GetFullPath($Root)).TrimEnd("\"))
  $patterns = @(
    "onebss_workstation_worker.py",
    "start_onebss_worker.ps1",
    "run_onebss_worker_background.ps1"
  )
  $currentPid = $PID
  $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $commandLine = [string]$_.CommandLine
    if ([int]$_.ProcessId -eq [int]$currentPid) { return $false }
    if ($commandLine -notmatch $escapedRoot) { return $false }
    foreach ($pattern in $patterns) {
      if ($commandLine -match [regex]::Escape($pattern)) { return $true }
    }
    return $false
  }
  foreach ($proc in $processes) {
    try {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
      Write-Host "Da dung worker cu PID $($proc.ProcessId)" -ForegroundColor Yellow
    } catch {
    }
  }
  Start-Sleep -Seconds 2
}

function Get-WorkstationWorkerProcesses {
  param([string]$Root)
  $escapedRoot = [regex]::Escape(([IO.Path]::GetFullPath($Root)).TrimEnd("\"))
  $patterns = @(
    "onebss_workstation_worker.py",
    "start_onebss_worker.ps1",
    "run_onebss_worker_background.ps1"
  )
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $commandLine = [string]$_.CommandLine
    if ([int]$_.ProcessId -eq [int]$PID) { return $false }
    if ($commandLine -notmatch $escapedRoot) { return $false }
    foreach ($pattern in $patterns) {
      if ($commandLine -match [regex]::Escape($pattern)) { return $true }
    }
    return $false
  }
}

function Get-WorkstationWorkerPythonProcesses {
  param([string]$Root)
  @(Get-WorkstationWorkerProcesses $Root) | Where-Object {
    ([string]$_.Name) -match "python" -and ([string]$_.CommandLine) -match [regex]::Escape("onebss_workstation_worker.py")
  }
}

function Wait-WorkstationWorkerStable {
  param(
    [string]$Root,
    [int]$Seconds = 15
  )
  $processes = @(Get-WorkstationWorkerPythonProcesses $Root)
  if ($processes.Count -eq 0) {
    return @()
  }
  Start-Sleep -Seconds $Seconds
  return @(Get-WorkstationWorkerPythonProcesses $Root)
}

function Start-WorkstationWorkerNow {
  param([string]$Root)
  Write-Step "Khoi dong worker may tram nen"
  $running = @(Get-WorkstationWorkerPythonProcesses $Root)
  if ($running.Count -gt 0) {
    $stable = @(Wait-WorkstationWorkerStable $Root 5)
    if ($stable.Count -gt 0) {
      Write-Host "Python worker dang chay on dinh PID: $($stable.ProcessId -join ', ')" -ForegroundColor Green
      return
    }
  }
  try {
    Start-ScheduledTask -TaskName "VNPTCTO OneBSS Worker" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
  } catch {
  }
  $stable = @(Wait-WorkstationWorkerStable $Root 15)
  if ($stable.Count -gt 0) {
    Write-Host "Worker da chay qua Scheduled Task, Python worker PID: $($stable.ProcessId -join ', ')" -ForegroundColor Green
    return
  }
  $workerScript = Join-Path $Root "scripts\start_onebss_worker.ps1"
  if (-not (Test-Path -LiteralPath $workerScript)) {
    Write-Warning "Khong tim thay worker script: $workerScript"
    return
  }
  try {
    $workerArg = "`"$workerScript`""
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $workerArg, "-NoPause") -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 3
    $stable = @(Wait-WorkstationWorkerStable $Root 10)
    if ($stable.Count -gt 0) {
      Write-Host "Worker da chay nen fallback, Python worker PID: $($stable.ProcessId -join ', ')" -ForegroundColor Green
    } else {
      Write-Warning "Da goi khoi dong worker nhung chua thay process. Kiem tra logs\onebss-worker-error.log."
    }
  } catch {
    Write-Warning "Khong khoi dong duoc worker nen: $($_.Exception.Message)"
  }
}

function Install-ApiMiddleware {
  param([string]$Root)
  if ($script:SkipApiMiddlewareResolved) {
    return
  }
  Write-Step "Cai API trung gian Oracle/Drive"
  $apiDir = Join-Path $ApiRoot "api-trung-gian"
  Stop-ApiMiddlewareProcesses $apiDir
  New-Item -ItemType Directory -Path $apiDir -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $ApiRoot "exports") -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $ApiRoot "logs") -Force | Out-Null

  $sourceMain = Join-Path $Root "docs\api_trung_gian_drive_export.py"
  if (Test-Path -LiteralPath $sourceMain) {
    Copy-Item -LiteralPath $sourceMain -Destination (Join-Path $apiDir "main.py") -Force
  }
  Ensure-ApiEnvFile $apiDir

  $apiVenv = Join-Path $apiDir ".venv"
  New-PythonVenv $apiVenv
  $apiPython = Join-Path $apiVenv "Scripts\python.exe"
  Invoke-External $apiPython "-m" "pip" "install" "--upgrade" "pip"
  Invoke-External $apiPython "-m" "pip" "install" "fastapi==0.115.12" "uvicorn[standard]==0.34.2" "oracledb" "python-dotenv" "openpyxl==3.1.5" "google-api-python-client==2.176.0" "google-auth==2.40.3" "google-auth-oauthlib"

  $installTask = Join-Path $Root "docs\install_api_trung_gian_task.ps1"
  if (Test-Path -LiteralPath $installTask) {
    Invoke-External "powershell.exe" "-NoProfile" "-ExecutionPolicy" "Bypass" "-File" $installTask
  }
}

function Add-UserCandidate {
  param(
    [System.Collections.Generic.List[string]]$Candidates,
    [string]$Value
  )
  $text = ([string]$Value).Trim()
  if (-not [string]::IsNullOrWhiteSpace($text) -and -not $Candidates.Contains($text)) {
    $Candidates.Add($text) | Out-Null
  }
}

function Get-InteractiveTaskUserCandidates {
  $candidates = New-Object System.Collections.Generic.List[string]
  try {
    Add-UserCandidate $candidates ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
  } catch {
  }
  try {
    Add-UserCandidate $candidates ((& whoami.exe 2>$null | Select-Object -First 1))
  } catch {
  }
  if (-not [string]::IsNullOrWhiteSpace($env:USERDOMAIN) -and -not [string]::IsNullOrWhiteSpace($env:USERNAME)) {
    Add-UserCandidate $candidates "$env:USERDOMAIN\$env:USERNAME"
  }
  if (-not [string]::IsNullOrWhiteSpace($env:COMPUTERNAME) -and -not [string]::IsNullOrWhiteSpace($env:USERNAME)) {
    Add-UserCandidate $candidates "$env:COMPUTERNAME\$env:USERNAME"
  }
  Add-UserCandidate $candidates $env:USERNAME
  return $candidates
}

function Register-VnptctoInteractiveTask {
  param(
    [string]$Name,
    [object]$Action,
    [object[]]$Trigger,
    [object]$Settings,
    [string]$Description
  )
  $lastError = ""
  foreach ($userId in Get-InteractiveTaskUserCandidates) {
    try {
      $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
      Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings -Principal $principal -Description $Description -Force | Out-Null
      Write-Host "Da tao Scheduled Task voi user: $userId" -ForegroundColor Green
      return
    } catch {
      $lastError = $_.Exception.Message
      Write-Warning "Chua tao duoc Scheduled Task voi user '$userId': $lastError"
    }
  }
  try {
    Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description -Force | Out-Null
    Write-Warning "Da tao Scheduled Task bang principal mac dinh cua Windows."
    return
  } catch {
    $lastError = $_.Exception.Message
  }
  throw "Khong tao duoc Scheduled Task $Name. Loi cuoi: $lastError"
}

function Install-HealthCheckTask {
  param([string]$Root)
  Write-Step "Cai health-check may tram"
  $healthScript = Join-Path $Root "scripts\test_vnptcto_workstation.ps1"
  if (-not (Test-Path -LiteralPath $healthScript)) {
    return
  }
  $taskName = "VNPTCTO Workstation Health Check"
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$healthScript`" -NoPause" -WorkingDirectory $Root
  $startupTrigger = New-ScheduledTaskTrigger -AtLogOn
  $intervalTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew -StartWhenAvailable
  Register-VnptctoInteractiveTask -Name $taskName -Action $action -Trigger @($startupTrigger, $intervalTrigger) -Settings $settings -Description "Kiem tra web, worker, API trung gian VNPTCTO."
}

function Write-SetupErrorLog {
  param([string]$Message)
  try {
    $root = [string]$InstallRoot
    if ([string]::IsNullOrWhiteSpace($root)) {
      $root = "D:\Tool_Tram_VNPTCTO.COM"
    }
    $logDir = Join-Path $root "logs"
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $logFile = Join-Path $logDir "workstation-setup-error.log"
    "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") $Message" | Add-Content -Path $logFile -Encoding UTF8
  } catch {
  }
}

trap {
  Write-Host ""
  Write-Host "Setup may tram VNPTCTO bi loi:" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Write-SetupErrorLog $_.Exception.Message
  Pause-BeforeExit
  exit 1
}

Assert-Administrator
$sourceRoot = Source-Root
$setupConfig = Import-SetupConfig $sourceRoot

$InstallRoot = Resolve-SetupValue $setupConfig "InstallRoot" $InstallRoot "D:\Tool_Tram_VNPTCTO.COM" "VNPTCTO_WORKSTATION_ROOT"
$BaseUrl = Resolve-SetupValue $setupConfig "BaseUrl" $BaseUrl "https://vnptcto.com" "VNPTCTO_BASE_URL"
$InternalApiUrl = Resolve-SetupValue $setupConfig "InternalApiUrl" $InternalApiUrl "https://api.vnptcto.com/api/du-lieu-web" "INTERNAL_API_URL"
$WorkerDriveUploadApiUrl = Resolve-SetupValue $setupConfig "WorkerDriveUploadApiUrl" $WorkerDriveUploadApiUrl "http://127.0.0.1:8000/api/du-lieu-web" "ONEBSS_DRIVE_UPLOAD_API_URL"
$ApiRoot = Resolve-SetupValue $setupConfig "ApiRoot" $ApiRoot "C:\VNPTCTO" ""
$oracleDbDsn = Resolve-SetupValue $setupConfig "OracleDbDsn" $OracleDbDsn "" "DB_DSN"
$oracleDbHost = Resolve-SetupValue $setupConfig "OracleDbHost" $OracleDbHost "" "DB_HOST"
$oracleDbPort = Resolve-SetupValue $setupConfig "OracleDbPort" $OracleDbPort "1521" "DB_PORT"
$oracleDbService = Resolve-SetupValue $setupConfig "OracleDbService" $OracleDbService "" "DB_SERVICE"
$oracleDbSid = Resolve-SetupValue $setupConfig "OracleDbSid" $OracleDbSid "" "DB_SID"
$oracleDbUser = Resolve-SetupValue $setupConfig "OracleDbUser" $OracleDbUser "" "DB_USER"
$oracleDbPass = Resolve-SetupValue $setupConfig "OracleDbPass" $OracleDbPass "" "DB_PASS"
$InternalApiToken = Resolve-SetupValue $setupConfig "InternalApiToken" $InternalApiToken "" "INTERNAL_API_TOKEN"
$WorkerId = Resolve-SetupValue $setupConfig "WorkerId" $WorkerId "" "ONEBSS_WORKER_ID"
$workerIdPrefix = Resolve-SetupValue $setupConfig "WorkerIdPrefix" "" "may-tram" ""
$onebssUsername = Resolve-SetupValue $setupConfig "OneBssUsername" "" "" "ONEBSS_USERNAME"
$onebssPassword = Resolve-SetupValue $setupConfig "OneBssPassword" "" "" "ONEBSS_PASSWORD"
$onebssLoginUrl = Resolve-SetupValue $setupConfig "OneBssLoginUrl" "" "https://onebss.vnpt.vn/" "ONEBSS_LOGIN_URL"
$onebssDownloadTimeoutSeconds = Resolve-SetupValue $setupConfig "OneBssDownloadTimeoutSeconds" "" "180" "ONEBSS_DOWNLOAD_TIMEOUT_SECONDS"
$onebssTaskTimeoutSeconds = Resolve-SetupValue $setupConfig "OneBssTaskTimeoutSeconds" $OneBssTaskTimeoutSeconds "1200" "ONEBSS_TASK_TIMEOUT_SECONDS"
$googleDriveFolderId = Resolve-SetupValue $setupConfig "GoogleDriveFolderId" "" "" "GOOGLE_DRIVE_FOLDER_ID"
$googleDriveOauthClientId = Resolve-SetupValue $setupConfig "GoogleDriveOauthClientId" "" "" "GOOGLE_DRIVE_OAUTH_CLIENT_ID"
$googleDriveOauthClientSecret = Resolve-SetupValue $setupConfig "GoogleDriveOauthClientSecret" "" "" "GOOGLE_DRIVE_OAUTH_CLIENT_SECRET"
$googleDriveOauthRedirectUri = Resolve-SetupValue $setupConfig "GoogleDriveOauthRedirectUri" "" "" "GOOGLE_DRIVE_OAUTH_REDIRECT_URI"
$googleDriveOauthRefreshToken = Resolve-SetupValue $setupConfig "GoogleDriveOauthRefreshToken" "" "" ""
$googleDriveOauthEmail = Resolve-SetupValue $setupConfig "GoogleDriveOauthEmail" "" "" ""
$googleDriveServiceAccountJsonBase64 = Resolve-SetupValue $setupConfig "GoogleDriveServiceAccountJsonBase64" "" "" "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64"
$sqlWorkerTimeoutSeconds = Resolve-SetupValue $setupConfig "SqlWorkerTimeoutSeconds" $SqlWorkerTimeoutSeconds "1800" "SQL_WORKER_TIMEOUT_SECONDS"
$exportPageSize = Resolve-SetupValue $setupConfig "ExportPageSize" $ExportPageSize "20000" "EXPORT_PAGE_SIZE"
$exportMaxRows = Resolve-SetupValue $setupConfig "ExportMaxRows" $ExportMaxRows "1000000" "EXPORT_MAX_ROWS"

$script:SkipApiMiddlewareResolved = [bool]$SkipApiMiddleware
if ($setupConfig.Contains("SkipApiMiddleware")) {
  $script:SkipApiMiddlewareResolved = Resolve-SetupBool $setupConfig "SkipApiMiddleware" $script:SkipApiMiddlewareResolved
}
if ($setupConfig.Contains("InstallApiMiddleware")) {
  $script:SkipApiMiddlewareResolved = -not (Resolve-SetupBool $setupConfig "InstallApiMiddleware" (-not $script:SkipApiMiddlewareResolved))
}
$skipPlaywrightResolved = [bool]$SkipPlaywright
if ($setupConfig.Contains("SkipPlaywright")) {
  $skipPlaywrightResolved = Resolve-SetupBool $setupConfig "SkipPlaywright" $skipPlaywrightResolved
}
$startNowResolved = [bool]$StartNow
if ($setupConfig.Contains("StartNow")) {
  $startNowResolved = Resolve-SetupBool $setupConfig "StartNow" $startNowResolved
}

$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$ApiRoot = [IO.Path]::GetFullPath($ApiRoot)

Write-Step "Chuan bi cau hinh"
if ([string]::IsNullOrWhiteSpace($WorkerId)) {
  $WorkerId = "$workerIdPrefix-$($env:COMPUTERNAME)".ToLower()
}
if ([string]::IsNullOrWhiteSpace($InternalApiToken)) {
  Write-Warning "Goi cai dat chua co INTERNAL_API_TOKEN. May tram se cai xong nhung worker chua the nhan task cho den khi web duoc cau hinh token."
}
if ([string]::IsNullOrWhiteSpace($onebssUsername) -or [string]::IsNullOrWhiteSpace($onebssPassword)) {
  Write-Warning "Goi cai dat chua co tai khoan OneBSS. May tram se cai xong nhung worker OneBSS chua the chay cho den khi web co cau hinh tai khoan."
}
$oracleMissing = @()
if ([string]::IsNullOrWhiteSpace($oracleDbDsn) -and ([string]::IsNullOrWhiteSpace($oracleDbHost) -or ([string]::IsNullOrWhiteSpace($oracleDbService) -and [string]::IsNullOrWhiteSpace($oracleDbSid)))) {
  $oracleMissing += "DB_DSN hoac DB_HOST + DB_SERVICE/DB_SID"
}
if ([string]::IsNullOrWhiteSpace($oracleDbUser)) {
  $oracleMissing += "DB_USER"
}
if ([string]::IsNullOrWhiteSpace($oracleDbPass)) {
  $oracleMissing += "DB_PASS"
}
if ($oracleMissing.Count -gt 0) {
  throw "Goi cai dat thieu cau hinh Oracle: $($oracleMissing -join ', '). Hay cap nhat DB co quan Oracle tren web roi tai lai bo cai moi."
}

Write-Step "Tao thu muc may tram"
foreach ($dir in @($InstallRoot, "$InstallRoot\logs", "$InstallRoot\temp", "$InstallRoot\backups", "$InstallRoot\downloads", "$InstallRoot\exports", "$InstallRoot\data", "$InstallRoot\data\staging", $ApiRoot)) {
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

Stop-WorkstationWorkerProcesses $InstallRoot

Write-Step "Copy source/tool hien tai"
Copy-WorkspaceFiles $sourceRoot $InstallRoot

Write-Step "Cap nhat bien moi truong User"
Set-UserEnvironment "VNPTCTO_BASE_URL" $BaseUrl
Set-UserEnvironment "VNPTCTO_WORKSTATION_ROOT" $InstallRoot
Set-UserEnvironment "VNPTCTO_WORKSTATION_LOG_DIR" (Join-Path $InstallRoot "logs")
Set-UserEnvironment "INTERNAL_API_TOKEN" $InternalApiToken
Set-UserEnvironment "INTERNAL_API_URL" $InternalApiUrl
Set-UserEnvironment "ONEBSS_DRIVE_UPLOAD_API_URL" $WorkerDriveUploadApiUrl
Set-UserEnvironment "ONEBSS_WORKER_ID" $WorkerId
Set-UserEnvironment "ONEBSS_WORKER_POLL_SECONDS" "5"
Set-UserEnvironment "ONEBSS_WORKER_HEARTBEAT_SECONDS" "60"
Set-UserEnvironment "SQL_WORKER_POLL_SECONDS" "10"
Set-UserEnvironment "FTP_WORKER_POLL_SECONDS" "30"
Set-UserEnvironment "SQL_WORKER_TIMEOUT_SECONDS" $sqlWorkerTimeoutSeconds
Set-UserEnvironment "EXPORT_PAGE_SIZE" $exportPageSize
Set-UserEnvironment "EXPORT_MAX_ROWS" $exportMaxRows
Set-UserEnvironment "ONEBSS_USERNAME" $onebssUsername
Set-UserEnvironment "ONEBSS_PASSWORD" $onebssPassword
Set-UserEnvironment "ONEBSS_LOGIN_URL" $onebssLoginUrl
Set-UserEnvironment "ONEBSS_DOWNLOAD_TIMEOUT_SECONDS" $onebssDownloadTimeoutSeconds
Set-UserEnvironment "ONEBSS_TASK_TIMEOUT_SECONDS" $onebssTaskTimeoutSeconds
Set-UserEnvironment "GOOGLE_DRIVE_FOLDER_ID" $googleDriveFolderId
Set-UserEnvironment "GOOGLE_DRIVE_OAUTH_CLIENT_ID" $googleDriveOauthClientId
Set-UserEnvironment "GOOGLE_DRIVE_OAUTH_CLIENT_SECRET" $googleDriveOauthClientSecret
Set-UserEnvironment "GOOGLE_DRIVE_OAUTH_REDIRECT_URI" $googleDriveOauthRedirectUri
Set-UserEnvironment "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64" $googleDriveServiceAccountJsonBase64
Set-UserEnvironment "DATA_MINING_DOWNLOAD_DIR" (Join-Path $InstallRoot "downloads")

Write-Step "Tao/cap nhat file .env"
Ensure-WorkstationEnvFile $InstallRoot

Write-Step "Cai moi truong Python worker"
Ensure-Python | Out-Null
$startWorker = Join-Path $InstallRoot "scripts\start_onebss_worker.ps1"
$workerSetupArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $startWorker, "-SetupOnly", "-NoPause")
if ($skipPlaywrightResolved) {
  $workerSetupArgs += "-SkipPlaywright"
}
Invoke-External "powershell.exe" @workerSetupArgs

Write-Step "Cai Scheduled Task OneBSS worker"
$installWorkerTask = Join-Path $InstallRoot "scripts\install_onebss_worker_task.ps1"
$taskArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $installWorkerTask, "-NoPause")
$canStartWorkerNow = -not [string]::IsNullOrWhiteSpace($InternalApiToken)
if ($startNowResolved -and $canStartWorkerNow) {
  $taskArgs += "-StartNow"
} elseif ($startNowResolved) {
  Write-Warning "Bo qua buoc start worker ngay vi thieu token web. Scheduled Task van da duoc cai de tu chay sau khi cau hinh du."
}
Invoke-External "powershell.exe" @taskArgs

Install-ApiMiddleware $InstallRoot
if ($startNowResolved -and $canStartWorkerNow) {
  Start-WorkstationWorkerNow $InstallRoot
}
Install-HealthCheckTask $InstallRoot

Write-Step "Kiem tra nhanh"
$healthScript = Join-Path $InstallRoot "scripts\test_vnptcto_workstation.ps1"
if (Test-Path -LiteralPath $healthScript) {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $healthScript -NoPause
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Health-check co canh bao. Hay xem log trong $InstallRoot\logs." -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "Da cai xong may tram VNPTCTO." -ForegroundColor Green
Write-Host "Thu muc: $InstallRoot"
Write-Host "Worker ID: $WorkerId"
Write-Host "Web: $BaseUrl"
Write-Host "Cau hinh API trung gian: $ApiRoot\api-trung-gian\.env"
Pause-BeforeExit
