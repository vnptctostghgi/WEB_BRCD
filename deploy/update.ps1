[CmdletBinding()]
param(
    [string]$Branch = "main",
    [string]$HealthUrl = "http://127.0.0.1:8080/api/ping",
    [switch]$EnableTunnel,
    [int]$HealthTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([Parameter(Mandatory)][string]$Command, [string[]]$Arguments = @())
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $repoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available in PATH."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or is not available in PATH."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot ".env"))) {
    throw "Missing .env. Copy .env.server.example to .env and fill the production values first."
}

$dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Cannot read Git status."
}
if ($dirty) {
    throw "The server checkout has local changes. Commit or preserve them before deployment."
}

$previousCommit = (git rev-parse HEAD).Trim()
Invoke-Checked git @("fetch", "origin", "--prune")
Invoke-Checked git @("switch", $Branch)
Invoke-Checked git @("merge", "--ff-only", "origin/$Branch")
$targetCommit = (git rev-parse HEAD).Trim()

Write-Host "Building commit $targetCommit (previous: $previousCommit)..."
Invoke-Checked docker @("compose", "build", "backend")

$composeArgs = @("compose")
if ($EnableTunnel) {
    $composeArgs += @("--profile", "tunnel")
}
$composeArgs += @("up", "-d", "--remove-orphans")
Invoke-Checked docker $composeArgs

$deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
$healthy = $false
do {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10
        if ($response.ok -eq $true -and $response.status -eq "alive") {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 5
    }
} while ((Get-Date) -lt $deadline)

if (-not $healthy) {
    Write-Host "Recent container status:"
    & docker compose ps
    Write-Host "Recent backend logs:"
    & docker compose logs --tail 100 backend
    throw "Deployment did not become healthy. Previous commit: $previousCommit. Target commit: $targetCommit."
}

Write-Host "Deployment healthy: $targetCommit"
Invoke-Checked docker @("compose", "ps")

