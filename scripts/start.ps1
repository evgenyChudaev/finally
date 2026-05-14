# FinAlly - start script (Windows PowerShell 5.1+).
#
# Usage:
#   .\scripts\start.ps1            # build only if image missing, then run
#   .\scripts\start.ps1 -Build     # force rebuild
#
# Verify the running container:
#   curl.exe -fsS http://localhost:8000/api/health
#   # expected: {"status":"ok"}
#
# Idempotent: safe to run multiple times.

[CmdletBinding()]
param(
    [switch]$Build,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

# Resolve repo root (parent of the scripts/ directory) so the script
# works from any cwd.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $RepoRoot

$Image = 'finally:latest'
$Name  = 'finally'

if (-not (Test-Path (Join-Path $RepoRoot '.env'))) {
    Write-Error "ERROR: .env not found in $RepoRoot.`n       Copy .env.example to .env and add your OPENROUTER_API_KEY."
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: docker is not installed or not on PATH."
    exit 1
}

# Decide whether to build.
$ImageExists = $false
try {
    docker image inspect $Image 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ImageExists = $true }
} catch {
    $ImageExists = $false
}

if ($Build -or -not $ImageExists) {
    Write-Host ">> Building $Image ..."
    docker build -t $Image .
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker build failed"
        exit $LASTEXITCODE
    }
} else {
    Write-Host ">> Image $Image already exists; skipping build (pass -Build to force)."
}

# Ensure bind-mount directory exists.
$DbDir = Join-Path $RepoRoot 'db'
if (-not (Test-Path $DbDir)) {
    New-Item -ItemType Directory -Path $DbDir | Out-Null
}

# Tear down any existing container with the same name (idempotent).
$existing = docker ps -a --format '{{.Names}}' 2>$null | Where-Object { $_ -eq $Name }
if ($existing) {
    Write-Host ">> Removing existing $Name container ..."
    docker rm -f $Name | Out-Null
}

Write-Host ">> Starting $Name on port $Port ..."
docker run -d `
    --name $Name `
    -p "${Port}:8000" `
    --env-file .env `
    -v "${RepoRoot}/db:/app/db" `
    --restart unless-stopped `
    $Image | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Error "docker run failed"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "App available at http://localhost:$Port"
Write-Host "Logs:  docker logs -f $Name"
Write-Host "Stop:  .\scripts\stop.ps1"
Write-Host ""
Write-Host "Verify with:  curl.exe -fsS http://localhost:$Port/api/health"
