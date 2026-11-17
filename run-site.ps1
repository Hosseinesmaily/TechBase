#Requires -Version 5.1
<#
.SYNOPSIS
    Brings the TechBase site up on this machine — no Docker.

.DESCRIPTION
    One command instead of the hand-typed list in the README. The script:

      1. checks the prerequisites (virtualenv, Node, node_modules, .env),
      2. creates a working Docker-less .env when there is none,
      3. applies the migrations and loads the demo data (all idempotent),
      4. opens Django on 127.0.0.1:8000 and Nuxt on localhost:3000, each in its
         own window so the logs stay readable,
      5. waits until both answer, prints the addresses and opens the browser.

    Running it again is safe: the demo seed updates in place and a port that is
    already serving is left alone.

.PARAMETER Stop
    Stop the two servers instead of starting them (kills whatever listens on
    8000 and 3000).

.PARAMETER SkipSeed
    Only migrate; do not write the demo catalog and wiki.

.PARAMETER NoBrowser
    Do not open the browser when the site is ready.

.EXAMPLE
    .\run-site.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\run-site.ps1

.EXAMPLE
    .\run-site.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$SkipSeed,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

# The script sits in the repository root, so its own folder is the root.
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"
$nodeModules = Join-Path $frontendDir "node_modules"
$backendPort = 8000
$frontendPort = 3000

function Write-Step([string]$text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Detail([string]$text) { Write-Host "    $text" -ForegroundColor DarkGray }
function Write-Warn([string]$text) { Write-Host "!!  $text" -ForegroundColor Yellow }
function Write-Fail([string]$text) {
    Write-Host "!!  $text" -ForegroundColor Red
    exit 1
}

function Get-PortOwner([int]$port) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) { return $null }
    return $connection.OwningProcess
}

function Wait-ForUrl([string]$url, [int]$timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch {
            # Not up yet — keep waiting.
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

if ($Stop) {
    Write-Step "Stopping the TechBase servers"
    foreach ($port in @($frontendPort, $backendPort)) {
        $owner = Get-PortOwner $port
        if ($null -eq $owner) {
            Write-Detail "nothing is listening on $port"
            continue
        }
        $process = Get-Process -Id $owner -ErrorAction SilentlyContinue
        $name = "the process"
        if ($null -ne $process) { $name = $process.ProcessName }
        Write-Detail "stopping $name (pid $owner) on port $port"
        taskkill /PID $owner /T /F | Out-Null
    }
    Write-Host ""
    Write-Host "The site is down." -ForegroundColor Green
    exit 0
}

# --- 1. The tools ------------------------------------------------------------
Write-Step "Checking the tools"

if (-not (Test-Path $python)) {
    Write-Host ""
    Write-Host "!!  The Python virtual environment is missing:" -ForegroundColor Red
    Write-Host "      $python" -ForegroundColor Red
    Write-Host ""
    Write-Host "    Create it once, from the repository root:" -ForegroundColor Yellow
    Write-Host "      python -m venv .venv" -ForegroundColor Yellow
    Write-Host "      .\.venv\Scripts\python.exe -m pip install -r backend\requirements\dev.txt" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
$pythonVersion = (& $python --version) 2>&1
Write-Detail "python   $pythonVersion"

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $npmCommand) {
    Write-Fail "npm was not found. Install Node.js 20 or newer (https://nodejs.org) and run this again."
}
$npmVersion = (& npm.cmd --version) 2>&1
Write-Detail "npm      $npmVersion"

if (-not (Test-Path $nodeModules)) {
    Write-Step "The frontend dependencies are missing - installing them (one time)"
    Push-Location $frontendDir
    try {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) { Write-Fail "npm install failed; see the output above." }
    } finally {
        Pop-Location
    }
}

# --- 2. The configuration ----------------------------------------------------
Write-Step "Checking the configuration (.env)"
if (Test-Path $envFile) {
    Write-Detail ".env is in place"
} else {
    if (-not (Test-Path $envExample)) { Write-Fail "Neither .env nor .env.example exists." }
    # .env.example describes the Docker stack. Without Docker the database is
    # SQLite and Redis/Meilisearch are absent, so those values are rewritten; a
    # copied file must not point at services that are not running.
    $content = [System.IO.File]::ReadAllText($envExample)
    $content = [regex]::Replace($content, "(?m)^DB_ENGINE=.*$", "DB_ENGINE=sqlite")
    $content = [regex]::Replace($content, "(?m)^# SQLITE_PATH=.*$", "SQLITE_PATH=db.sqlite3")
    $content = [regex]::Replace($content, "(?m)^SQLITE_PATH=.*$", "SQLITE_PATH=db.sqlite3")
    $content = [regex]::Replace($content, "(?m)^REDIS_URL=.*$", "REDIS_URL=")
    $content = [regex]::Replace($content, "(?m)^MEILI_HOST=.*$", "MEILI_HOST=")
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($envFile, $content, $utf8)
    Write-Detail "no .env found - created one for a Docker-less run (SQLite, no Redis/Meilisearch)"
}

# --- 3. Database and demo data ----------------------------------------------
Write-Step "Applying the migrations"
$superuserCount = "?"
Push-Location $backendDir
try {
    & $python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { Write-Fail "The migrations failed; see the output above." }

    if ($SkipSeed) {
        Write-Detail "demo data skipped (-SkipSeed)"
    } else {
        Write-Step "Loading the demo data (idempotent - safe to run again)"
        & $python manage.py seed_demo
        & $python manage.py seed_wiki
        & $python manage.py index_content
        Write-Detail "catalog, wiki articles and the assistant index are up to date"
    }

    # No credential is written in this file on purpose (docs/SECURITY.md). The
    # summary only says whether an account exists.
    try {
        $countQuery = "from django.contrib.auth import get_user_model as g; print(g().objects.filter(is_superuser=True).count())"
        $countOutput = & $python manage.py shell -c $countQuery 2>$null
        $superuserCount = ($countOutput | Select-Object -Last 1)
    } catch {
        $superuserCount = "?"
    }
} finally {
    Pop-Location
}
# --- 4. The two servers ------------------------------------------------------
Write-Step "Starting the servers"

$backendOwner = Get-PortOwner $backendPort
if ($null -ne $backendOwner) {
    Write-Detail "port $backendPort already answers (pid $backendOwner) - leaving it alone"
} else {
    $backendArguments = @(
        "-NoExit",
        "-Command",
        "& '$python' manage.py runserver 127.0.0.1:$backendPort"
    )
    Start-Process -FilePath "powershell.exe" -ArgumentList $backendArguments -WorkingDirectory $backendDir
    Write-Detail "backend  started in its own window (Django, port $backendPort)"
}

$frontendOwner = Get-PortOwner $frontendPort
if ($null -ne $frontendOwner) {
    Write-Detail "port $frontendPort already answers (pid $frontendOwner) - leaving it alone"
} else {
    $frontendArguments = @("-NoExit", "-Command", "npm.cmd run dev")
    Start-Process -FilePath "powershell.exe" -ArgumentList $frontendArguments -WorkingDirectory $frontendDir
    Write-Detail "frontend started in its own window (Nuxt, port $frontendPort)"
}

# --- 5. Ready ----------------------------------------------------------------
Write-Step "Waiting for the backend"
$backendReady = Wait-ForUrl "http://127.0.0.1:$backendPort/api/v1/health/" 90
if (-not $backendReady) { Write-Warn "the backend is not answering yet - look at its window" }

Write-Step "Waiting for the frontend (the first start takes about 30 seconds)"
$frontendReady = Wait-ForUrl "http://localhost:$frontendPort/" 180
if (-not $frontendReady) { Write-Warn "the frontend is not answering yet - look at its window" }

Write-Host ""
if ($backendReady -and $frontendReady) {
    Write-Host "The site is up." -ForegroundColor Green
} else {
    Write-Host "The site is still starting; the two windows show the progress." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  site        http://localhost:$frontendPort"
Write-Host "  api         http://127.0.0.1:$backendPort/api/v1/"
Write-Host "  api docs    http://127.0.0.1:$backendPort/api/docs/"
Write-Host "  admin       http://127.0.0.1:$backendPort/admin/"
Write-Host "  wiki (cms)  http://127.0.0.1:$backendPort/cms/"
Write-Host ""

if ("$superuserCount" -eq "0") {
    Write-Host "  No manager account exists yet. Create one with:" -ForegroundColor Yellow
    Write-Host "    cd backend; ..\.venv\Scripts\python.exe manage.py createsuperuser" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "  Stop with:  .\run-site.ps1 -Stop   (or close the two server windows)"
Write-Host ""

if (-not $NoBrowser -and $frontendReady) {
    Start-Process "http://localhost:$frontendPort"
}