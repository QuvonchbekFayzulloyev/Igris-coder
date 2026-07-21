#!/usr/bin/env pwsh
<#
.SYNOPSIS
Complete setup for igris-cli + Tauri Desktop App on Windows.

.DESCRIPTION
This script sets up everything needed to run igris-cli with the Tauri+React desktop UI:
1. Python backend (pip install -e .)
2. Node.js frontend dependencies (npm install)
3. Frontend build & verification
4. Rust/Tauri CLI installation (optional)
5. Development commands

.NOTES
Run from igris-cli root directory: .\setup_all.ps1
Requires: Python 3.10+, Node.js 18+, Rust (via rustup)
#>

param(
    [switch]$InstallRust = $true,
    [switch]$BuildFrontend = $true,
    [switch]$VerifyBundle = $true,
    [switch]$SkipPython = $false
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$desktopDir = "$projectRoot\desktop"
$tempDir = "$projectRoot\.pytest_tmp"

Write-Host "=== igris-cli + Tauri Desktop Full Setup ===" -ForegroundColor Cyan

# Create pytest temp directory
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
}
$env:PYTEST_DEBUG_TEMPROOT = $tempDir

# 1. Python Backend
if (-not $SkipPython) {
    Write-Host "`n[1/5] Installing Python backend..." -ForegroundColor Yellow
    cd $projectRoot
    pip install -e . --quiet
    Write-Host "  Python package installed" -ForegroundColor Green
} else {
    Write-Host "`n[1/5] Skipping Python install (--SkipPython)" -ForegroundColor Gray
}

# 2. Frontend Dependencies
Write-Host "`n[2/5] Installing Node.js frontend dependencies..." -ForegroundColor Yellow
cd $desktopDir
npm install
Write-Host "  npm install complete" -ForegroundColor Green

# 3. Build Frontend
if ($BuildFrontend) {
    Write-Host "`n[3/5] Building frontend..." -ForegroundColor Yellow
    cd $desktopDir
    npm run build
    Write-Host "  Build complete" -ForegroundColor Green
} else {
    Write-Host "`n[3/5] Skipping frontend build (--BuildFrontend:$false)" -ForegroundColor Gray
}

# 4. Verify Production Bundle
if ($VerifyBundle) {
    Write-Host "`n[4/5] Verifying production bundle..." -ForegroundColor Yellow
    cd $desktopDir
    npm run verify:bundle
    Write-Host "  Bundle verification PASSED" -ForegroundColor Green
} else {
    Write-Host "`n[4/5] Skipping bundle verification (--VerifyBundle:$false)" -ForegroundColor Gray
}

# 5. Rust/Tauri Setup
if ($InstallRust) {
    Write-Host "`n[5/5] Setting up Rust + Tauri CLI..." -ForegroundColor Yellow
    
    # Check for rustup
    if (-not (Get-Command rustup -ErrorAction SilentlyContinue)) {
        Write-Host "  Installing rustup..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile "$env:TEMP\rustup-init.exe" -UseBasicParsing
        & "$env:TEMP\rustup-init.exe" -y --default-toolchain stable
        $env:PATH += ";$env:USERPROFILE\.cargo\bin"
        Write-Host "  rustup installed" -ForegroundColor Green
    } else {
        Write-Host "  rustup already installed" -ForegroundColor Green
    }
    
    # Refresh PATH
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [Environment]::GetEnvironmentVariable("PATH", "Machine")
    
    # Install Tauri CLI
    if (-not (Get-Command tauri -ErrorAction SilentlyContinue)) {
        Write-Host "  Installing Tauri CLI..." -ForegroundColor Yellow
        cargo install tauri-cli
        Write-Host "  Tauri CLI installed" -ForegroundColor Green
    } else {
        Write-Host "  Tauri CLI already installed" -ForegroundColor Green
    }
} else {
    Write-Host "`n[5/5] Skipping Rust/Tauri setup (--InstallRust:$false)" -ForegroundColor Gray
}

Write-Host "`n=== Setup Complete! ===" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Start backend:  uvicorn igris.server:app --port 8765 --reload" -ForegroundColor Gray
Write-Host "  2. Start frontend: cd desktop; npm run dev" -ForegroundColor Gray
Write-Host "  OR run together:  cd desktop; npx tauri dev" -ForegroundColor Gray
Write-Host "`nRun tests: \$env:PYTEST_DEBUG_TEMPROOT = '$tempDir'; python -m pytest tests/ -v --tb=short" -ForegroundColor Gray
Write-Host "Frontend tests: cd desktop; npx vitest run" -ForegroundColor Gray