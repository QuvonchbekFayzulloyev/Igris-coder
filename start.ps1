#!/usr/bin/env pwsh
<#
.SYNOPSIS
Unified dev launcher for igris-cli — starts the Python backend and (optionally) the frontend.

.DESCRIPTION
Starts uvicorn (FastAPI backend on port 8765) and optionally the Vite dev server
(frontend on port 5173) in a single terminal with cleanup on Ctrl+C.

If -Tauri is set, runs `npx tauri dev` instead (which starts both via Tauri's
beforeDevCommand). Use this for the desktop app.

.NOTES
Run from the igris-cli root directory: .\start.ps1
Requires: Python 3.10+, Node.js 18+, pip install -e . already done.
#>

param(
    [switch]$Tauri = $false,
    [switch]$BackendOnly = $false,
    [switch]$NoBuildCheck = $false
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$desktopDir = "$projectRoot\desktop"
$tempDir = "$projectRoot\.pytest_tmp"
$backendPort = 8765

Write-Host "=== igris-cli Dev Launcher ===" -ForegroundColor Cyan

# ----- Prerequisites -------------------------------------------------------
Write-Host "`n[check] Prerequisites..." -ForegroundColor Yellow

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Python not found on PATH" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Node.js not found on PATH" -ForegroundColor Red
    exit 1
}

# Quick check: is the igris package installed?
$igrisCheck = python -c "import igris; print('ok')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: igris package not installed. Run: pip install -e ." -ForegroundColor Yellow
}

# Create temp dir for pytest (needed by backend on Windows)
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    Write-Host "  Created pytest temp dir: $tempDir" -ForegroundColor Green
}

$env:PYTEST_DEBUG_TEMPROOT = $tempDir

# ----- Frontend build check ------------------------------------------------
if (-not $BackendOnly -and -not $NoBuildCheck -and -not $Tauri) {
    $distDir = "$desktopDir\dist"
    if (-not (Test-Path "$distDir\index.html")) {
        Write-Host "  Frontend not built. Building..." -ForegroundColor Yellow
        Push-Location $desktopDir
        npm run build
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ERROR: Frontend build failed" -ForegroundColor Red
            exit 1
        }
        Pop-Location
        Write-Host "  Frontend built" -ForegroundColor Green
    }
}

# ----- Port check ----------------------------------------------------------
$portCheck = netstat -ano | Select-String ":$backendPort\s"
if ($portCheck) {
    Write-Host "  WARNING: Port $backendPort is already in use." -ForegroundColor Yellow
    Write-Host "  Stop the existing process or change the port." -ForegroundColor Yellow
}

# ----- Start ---------------------------------------------------------------
function Cleanup {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    if ($global:backendJob -and $global:backendJob.State -eq "Running") {
        Stop-Job $global:backendJob -ErrorAction SilentlyContinue
        Remove-Job $global:backendJob -Force -ErrorAction SilentlyContinue
    }
}

if ($Tauri) {
    # ----- Tauri Desktop ---------------------------------------------------
    Write-Host "`n[start] Tauri dev mode..." -ForegroundColor Green
    Push-Location $desktopDir
    try {
        npx tauri dev
    } finally {
        Pop-Location
    }
} elseif ($BackendOnly) {
    # ----- Backend only ----------------------------------------------------
    Write-Host "`n[start] Backend on http://127.0.0.1:$backendPort ..." -ForegroundColor Green
    Write-Host "  Ctrl+C to stop`n" -ForegroundColor Gray
    uvicorn igris.server:app --host 127.0.0.1 --port $backendPort --reload
} else {
    # ----- Backend + Frontend ----------------------------------------------
    Write-Host "`n[start] Backend on http://127.0.0.1:$backendPort ..." -ForegroundColor Green
    Write-Host "[start] Frontend on http://localhost:5173 ..." -ForegroundColor Green
    Write-Host "  Ctrl+C to stop both`n" -ForegroundColor Gray

    $global:backendJob = Start-Job -ScriptBlock {
        param($root, $temp, $port)
        $env:PYTEST_DEBUG_TEMPROOT = $temp
        Set-Location $root
        uvicorn igris.server:app --host 127.0.0.1 --port $port --reload 2>&1
    } -ArgumentList $projectRoot, $tempDir, $backendPort

    Start-Sleep -Seconds 2

    Push-Location $desktopDir
    try {
        npm run dev
    } finally {
        Cleanup
        Pop-Location
    }
}
