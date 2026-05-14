# FinAlly - stop script (Windows PowerShell 5.1+).
#
# Stops and removes the "finally" container. Idempotent: returns 0 even
# if nothing was running. The bind-mounted .\db directory is preserved.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Name = 'finally'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: docker is not installed or not on PATH."
    exit 1
}

$existing = docker ps -a --format '{{.Names}}' 2>$null | Where-Object { $_ -eq $Name }
if ($existing) {
    Write-Host ">> Stopping $Name ..."
    docker stop $Name 2>$null | Out-Null
    docker rm $Name 2>$null | Out-Null
    Write-Host ">> Done. (Database in .\db preserved.)"
} else {
    Write-Host ">> No $Name container running. Nothing to do."
}
