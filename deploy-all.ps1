<#
.SYNOPSIS
    Deploy all agents to AWS Bedrock Agent Core.

.DESCRIPTION
    Iterates over all agent configs in agents/ folder and deploys each one
    as a separate, isolated runtime.

.PARAMETER LocalBuild
    If set, builds Docker images locally.

.PARAMETER DryRun
    If set, only shows what would be deployed.

.EXAMPLE
    .\deploy-all.ps1
    .\deploy-all.ps1 -DryRun
    .\deploy-all.ps1 -LocalBuild
#>

param(
    [switch]$LocalBuild,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$agentsDir = Join-Path $PSScriptRoot "agents"
$configs = Get-ChildItem -Path $agentsDir -Filter "*.json"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Multi-Agent Deploy — $($configs.Count) agents found" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$results = @()

foreach ($configFile in $configs) {
    $agentName = $configFile.BaseName
    Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  [$($results.Count + 1)/$($configs.Count)] $agentName" -ForegroundColor White
    Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor Gray

    $deployArgs = @("-AgentName", $agentName)
    if ($LocalBuild) { $deployArgs += "-LocalBuild" }
    if ($DryRun) { $deployArgs += "-DryRun" }

    try {
        & (Join-Path $PSScriptRoot "deploy.ps1") @deployArgs
        $results += @{ Name = $agentName; Status = "✅ OK" }
    } catch {
        Write-Host "❌ Failed to deploy $agentName : $_" -ForegroundColor Red
        $results += @{ Name = $agentName; Status = "❌ FAILED" }
    }

    Write-Host ""
}

# ── Summary ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Deploy Summary" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
foreach ($r in $results) {
    Write-Host "  $($r.Status)  $($r.Name)"
}
Write-Host ""
