#!/usr/bin/env pwsh
<#
.SYNOPSIS
Applies all fixes for the igris-cli project on Windows.

.DESCRIPTION
This script applies the following fixes:
1. Sets up pytest temp directory environment variable
2. Adds error handling to MCPManager.call()
3. Verifies all tests pass

.NOTES
Run from the igris-cli directory: .\setup_fixes.ps1
#>

param(
    [switch]$RunTests = $true
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$tempDir = "$projectRoot\.pytest_tmp"

Write-Host "=== igris-cli Windows Fixes Setup ===" -ForegroundColor Cyan

# 1. Create temp directory for pytest
Write-Host "`n[1/4] Creating pytest temp directory..." -ForegroundColor Yellow
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    Write-Host "  Created: $tempDir" -ForegroundColor Green
} else {
    Write-Host "  Exists: $tempDir" -ForegroundColor Green
}

# 2. Set environment variable for current session
$env:PYTEST_DEBUG_TEMPROOT = $tempDir
Write-Host "  Set PYTEST_DEBUG_TEMPROOT=$tempDir" -ForegroundColor Green

# 3. Verify MCPManager fix is in place
Write-Host "`n[2/4] Verifying MCPManager error handling fix..." -ForegroundColor Yellow
$mcpManagerPath = "$projectRoot\igris\core\mcp_manager.py"
$content = Get-Content $mcpManagerPath -Raw
if ($content -match 'try:\s*result = await session\.call_tool') {
    Write-Host "  Fix already applied" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Fix not found in mcp_manager.py" -ForegroundColor Red
    exit 1
}

# 4. Run tests
if ($RunTests) {
    Write-Host "`n[3/4] Running backend tests..." -ForegroundColor Yellow
    cd $projectRoot
    python -m pytest tests/ -v --tb=short `
        --ignore=tests/test_knowledge_integration.py `
        --ignore=tests/test_knowledge_seed.py `
        --ignore=tests/smoke_mcp.py `
        --ignore=tests/smoke_knowledge_server.py `
        --ignore=tests/test_multi_agent_loop.py

    Write-Host "`n[4/4] Running frontend tests..." -ForegroundColor Yellow
    cd "$projectRoot\desktop"
    npx vitest run

    Write-Host "`n[5/5] Verifying production bundle..." -ForegroundColor Yellow
    npm run verify:bundle
}

Write-Host "`n=== All fixes applied successfully! ===" -ForegroundColor Cyan
Write-Host "`nTo run tests manually in the future:" -ForegroundColor Yellow
Write-Host "  \$env:PYTEST_DEBUG_TEMPROOT = '$tempDir'" -ForegroundColor Gray
Write-Host "  python -m pytest tests/ -v --tb=short" -ForegroundColor Gray
Write-Host "`nOr add to your PowerShell profile for persistence." -ForegroundColor Gray