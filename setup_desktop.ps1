#!/usr/bin/env pwsh
<#
.SYNOPSIS
Frontend-only setup for igris-cli Tauri+React desktop app.

.DESCRIPTION
Installs Node.js dependencies, builds frontend, verifies production bundle,
and optionally installs Tauri CLI for desktop development.

.NOTES
Run from igris-cli root or desktop directory: .\setup_desktop.ps1
Requires: Node.js 18+
#>

param(
    [switch]$InstallTauriCLI = $true,
    [switch]$Build = $true,
    [switch]$Verify = $true,
    [switch]$DevMode = $false
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$desktopDir = "$projectRoot\desktop"

Write-Host "=== igris-cli Desktop (Frontend) Setup ===" -ForegroundColor Cyan

# 1. Install Dependencies
Write-Host "`n[1/4] Installing Node.js dependencies..." -ForegroundColor Yellow
cd $desktopDir
npm install
Write-Host "  npm install complete" -ForegroundColor Green

# 2. Build Frontend
if ($Build) {
    Write-Host "`n[2/4] Building frontend..." -ForegroundColor Yellow
    npm run build
    Write-Host "  Build complete" -ForegroundColor Green
} else {
    Write-Host "`n[2/4] Skipping build (--Build:$false)" -ForegroundColor Gray
}

# 3. Verify Production Bundle
if ($Verify) {
    Write-Host "`n[3/4] Verifying production bundle..." -ForegroundColor Yellow
    npm run verify:bundle
    Write-Host "  Bundle verification PASSED" -ForegroundColor Green
} else {
    Write-Host "`n[3/4] Skipping verification (--Verify:$false)" -ForegroundColor Gray
}

# 4. Tauri CLI
if ($InstallTauriCLI) {
    Write-Host "`n[4/4] Installing Tauri CLI..." -ForegroundColor Yellow
    if (-not (Get-Command tauri -ErrorAction SilentlyContinue)) {
        npm install -g @tauri-apps/cli
        Write-Host "  Tauri CLI installed globally" -ForegroundColor Green
    } else {
        Write-Host "  Tauri CLI already installed" -ForegroundColor Green
    }
} else {
    Write-Host "`n[4/4] Skipping Tauri CLI (--InstallTauriCLI:$false)" -ForegroundColor Gray
}

Write-Host "`n=== Desktop Setup Complete! ===" -ForegroundColor Cyan

if ($DevMode) {
    Write-Host "`nStarting dev mode..." -ForegroundColor Yellow
    Write-Host "  Terminal 1: uvicorn igris.server:app --port 8765 --reload" -ForegroundColor Gray
    Write-Host "  Terminal 2: npm run dev" -ForegroundColor Gray
} else {
    Write-Host "`nTo run:" -ForegroundColor Yellow
    Write-Host "  Dev mode:     npx tauri dev" -ForegroundColor Gray
    Write-Host "  Dev (split):  uvicorn igris.server:app --port 8765 --reload" -ForegroundColor Gray
    Write-Host "                npm run dev" -ForegroundColor Gray
    Write-Host "  Build:        npm run tauri build" -ForegroundColor Gray
    Write-Host "  Tests:        npx vitest run" -ForegroundColor Gray
}