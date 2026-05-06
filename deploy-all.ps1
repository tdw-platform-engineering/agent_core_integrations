<#
.SYNOPSIS
    Deploy all agents to AWS Bedrock Agent Core in the correct order.

.DESCRIPTION
    Deploys base agents first (so their ARNs get registered), then
    deploys orchestrators (which resolve sub-agent ARNs from the registry).

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

# Deploy order: base agents first, orchestrators last
$baseAgents = @(
    "agente-ventas-carton",
    "agente-ventas-papel",
    "agente-presupuesto"
)

$orchestrators = @(
    "agente-orquestador-papel-carton",
    "agente-orquestador-presupuesto"
)

$allAgents = $baseAgents + $orchestrators

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Multi-Agent Deploy - $($allAgents.Count) agents" -ForegroundColor Cyan
Write-Host "  Order: Base agents ($($baseAgents.Count)) then Orchestrators ($($orchestrators.Count))" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$results = @()
$step = 0

# -- Phase 1: Base agents ---------------------------------------------
Write-Host "--- Phase 1: Base Agents ---" -ForegroundColor White
Write-Host ""

foreach ($agentName in $baseAgents) {
    $step++
    Write-Host "  [$step/$($allAgents.Count)] $agentName" -ForegroundColor White

    try {
        $scriptPath = Join-Path $PSScriptRoot "deploy.ps1"
        if ($LocalBuild -and $DryRun) {
            & $scriptPath -AgentName $agentName -LocalBuild -DryRun
        } elseif ($LocalBuild) {
            & $scriptPath -AgentName $agentName -LocalBuild
        } elseif ($DryRun) {
            & $scriptPath -AgentName $agentName -DryRun
        } else {
            & $scriptPath -AgentName $agentName
        }
        $results += @{ Name = $agentName; Status = "[OK]"; Phase = "base" }
    } catch {
        Write-Host "FAILED: $_" -ForegroundColor Red
        $results += @{ Name = $agentName; Status = "[FAILED]"; Phase = "base" }
    }
    Write-Host ""
}

# -- Phase 2: Orchestrators -------------------------------------------
Write-Host "--- Phase 2: Orchestrators ---" -ForegroundColor White
Write-Host ""

foreach ($agentName in $orchestrators) {
    $step++
    Write-Host "  [$step/$($allAgents.Count)] $agentName" -ForegroundColor White

    try {
        $scriptPath = Join-Path $PSScriptRoot "deploy.ps1"
        if ($LocalBuild -and $DryRun) {
            & $scriptPath -AgentName $agentName -LocalBuild -DryRun
        } elseif ($LocalBuild) {
            & $scriptPath -AgentName $agentName -LocalBuild
        } elseif ($DryRun) {
            & $scriptPath -AgentName $agentName -DryRun
        } else {
            & $scriptPath -AgentName $agentName
        }
        $results += @{ Name = $agentName; Status = "[OK]"; Phase = "orchestrator" }
    } catch {
        Write-Host "FAILED: $_" -ForegroundColor Red
        $results += @{ Name = $agentName; Status = "[FAILED]"; Phase = "orchestrator" }
    }
    Write-Host ""
}

# -- Summary -----------------------------------------------------------
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Deploy Summary" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Base Agents:" -ForegroundColor White
foreach ($r in ($results | Where-Object { $_.Phase -eq "base" })) {
    Write-Host "    $($r.Status)  $($r.Name)"
}
Write-Host ""
Write-Host "  Orchestrators:" -ForegroundColor White
foreach ($r in ($results | Where-Object { $_.Phase -eq "orchestrator" })) {
    Write-Host "    $($r.Status)  $($r.Name)"
}
Write-Host ""

# Show registry
$registryPath = Join-Path (Join-Path $PSScriptRoot "agents") ".registry.json"
if (Test-Path $registryPath) {
    $registry = Get-Content $registryPath -Raw | ConvertFrom-Json
    $agentCount = ($registry.agents.PSObject.Properties | Measure-Object).Count
    Write-Host "  Registry: $agentCount agents registered" -ForegroundColor Gray
    Write-Host "  Location: $registryPath" -ForegroundColor Gray
}
Write-Host ""
