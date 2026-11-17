# Starts the local development stack on Windows (no Docker needed).
#
#   .\dev.ps1            database + API + web app
#   .\dev.ps1 -Worker    also start the background worker
#   .\dev.ps1 -Stop      stop the local database
#
# The API, worker and web app each open in their own window; close a window to stop it.

param(
    [switch]$Worker,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host 'backend\.venv is missing. Set up first (see CLAUDE.md, Commands).' -ForegroundColor Red
    exit 1
}

Push-Location $backend
try {
    if ($Stop) {
        & $python scripts\dev_db.py --stop
        exit $LASTEXITCODE
    }
    Write-Host 'Starting local database and applying migrations...' -ForegroundColor Cyan
    & $python scripts\dev_db.py
    if ($LASTEXITCODE -ne 0) { Write-Host 'Database start failed.' -ForegroundColor Red; exit $LASTEXITCODE }
} finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host 'Installing frontend packages...' -ForegroundColor Cyan
    Push-Location $frontend
    try { npm install } finally { Pop-Location }
}

function Start-Window($title, $dir, $command) {
    Start-Process powershell -WorkingDirectory $dir -ArgumentList @(
        '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle = '$title'; $command"
    )
}

Start-Window 'analysisACE API' $backend "& '$python' -m uvicorn app.main:app --reload"
if ($Worker) {
    Start-Window 'analysisACE worker' $backend "& '$python' -m app.jobs.worker"
}
Start-Window 'analysisACE web' $frontend 'npm run dev'

Write-Host ''
Write-Host 'Web app:  http://localhost:3000' -ForegroundColor Green
Write-Host 'API docs: http://localhost:8000/api/v1/docs' -ForegroundColor Green
Write-Host 'Stop the database later with: .\dev.ps1 -Stop'
