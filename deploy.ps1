<#
.SYNOPSIS
    Deploy a specific agent to AWS Bedrock Agent Core.

.DESCRIPTION
    Reads the agent configuration from agents/<agent-name>.json,
    configures the runtime, and deploys it. Each agent gets its own
    isolated runtime with its own ARN, memory, and prompt.

.PARAMETER AgentName
    Name of the agent to deploy (must match a file in agents/ folder).

.PARAMETER LocalBuild
    If set, builds the Docker image locally instead of using CodeBuild.

.PARAMETER DryRun
    If set, only shows what would be deployed without actually deploying.

.EXAMPLE
    .\deploy.ps1 -AgentName agente-ventas-carton
    .\deploy.ps1 -AgentName agente-presupuesto -LocalBuild
    .\deploy.ps1 -AgentName agente-orquestador-papel-carton -DryRun
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        "agente-ventas-carton",
        "agente-ventas-papel",
        "agente-orquestador-papel-carton",
        "agente-presupuesto",
        "agente-orquestador-presupuesto"
    )]
    [string]$AgentName,

    [switch]$LocalBuild,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ── Load agent config ────────────────────────────────────────────────
$configPath = Join-Path $PSScriptRoot "agents" "$AgentName.json"
if (-not (Test-Path $configPath)) {
    Write-Host "❌ Agent config not found: $configPath" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath | ConvertFrom-Json
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Deploying Agent: $($config.name)" -ForegroundColor Cyan
Write-Host "║  Description: $($config.description)" -ForegroundColor Cyan
Write-Host "║  Runtime: $($config.runtime_name)" -ForegroundColor Cyan
Write-Host "║  Region: $($config.region)" -ForegroundColor Cyan
Write-Host "║  Model: $($config.model)" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Build env vars from config ───────────────────────────────────────
$envArgs = @()

# Core vars
$envArgs += "--env"; $envArgs += "AGENT_NAME=$($config.prompt)"
$envArgs += "--env"; $envArgs += "MODEL_ID=$($config.model)"
$envArgs += "--env"; $envArgs += "AWS_REGION=$($config.region)"
$envArgs += "--env"; $envArgs += "BYPASS_TOOL_CONSENT=true"

# Feature flags
foreach ($prop in $config.features.PSObject.Properties) {
    $envArgs += "--env"
    $envArgs += "$($prop.Name)=$($prop.Value)"
}

# Memory config
if ($config.features.ENABLE_MEMORY -eq "true" -and $config.memory.memory_name) {
    # Memory ID will be set after creation or from existing
    Write-Host "📝 Memory enabled: $($config.memory.memory_name)" -ForegroundColor Yellow
    if ($config.memory.shared) {
        Write-Host "   ⚠️  Shared memory — ensure MEMORY_ID is set in runtime env" -ForegroundColor Yellow
    }
}

# Sub-agents config (for orchestrators)
if ($config.sub_agents) {
    $subAgentsJson = ($config.sub_agents | ConvertTo-Json -Compress)
    $envArgs += "--env"
    $envArgs += "SUB_AGENTS=$subAgentsJson"
    Write-Host "🔗 Orchestrator mode — sub-agents:" -ForegroundColor Yellow
    foreach ($prop in $config.sub_agents.PSObject.Properties) {
        Write-Host "   - $($prop.Name): $($prop.Value.description)" -ForegroundColor Yellow
    }
}

# Load AWS credentials from .env if they exist
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $key = ($line -split '=', 2)[0]
            # Only pass credentials and region, not feature flags (those come from agent config)
            if ($key -in @("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "ATHENA_LAMBDA_NAME", "ATHENA_LAMBDA_REGION", "MEMORY_ID", "KNOWLEDGE_BASE_ID")) {
                $envArgs += "--env"
                $envArgs += $line
            }
        }
    }
}

# ── Show what will be deployed ───────────────────────────────────────
Write-Host "📋 Environment variables:" -ForegroundColor Gray
for ($i = 0; $i -lt $envArgs.Count; $i += 2) {
    $val = $envArgs[$i + 1]
    # Mask secrets
    if ($val -match "SECRET|KEY|TOKEN") {
        $parts = $val -split '=', 2
        Write-Host "   $($parts[0])=***" -ForegroundColor Gray
    } else {
        Write-Host "   $val" -ForegroundColor Gray
    }
}
Write-Host ""

if ($DryRun) {
    Write-Host "🔍 DRY RUN — would execute:" -ForegroundColor Yellow
    Write-Host "   uv run agentcore deploy $($envArgs -join ' ')" -ForegroundColor Yellow
    exit 0
}

# ── Configure the agent runtime ──────────────────────────────────────
Write-Host "⚙️  Configuring agent runtime: $($config.runtime_name)..." -ForegroundColor Cyan

$configureArgs = @(
    "--entrypoint", "src/main.py",
    "--name", $config.runtime_name,
    "--region", $config.region,
    "--non-interactive"
)

if ($config.features.ENABLE_MEMORY -eq "true") {
    # Memory will be created/attached during configure
} else {
    $configureArgs += "--disable-memory"
}

Write-Host "   Running: uv run agentcore configure $($configureArgs -join ' ')" -ForegroundColor Gray
uv run agentcore configure @configureArgs

# ── Deploy ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "🚀 Deploying..." -ForegroundColor Green

$deployArgs = @()
if ($LocalBuild) {
    $deployArgs += "--local-build"
    Write-Host "   Using local Docker build" -ForegroundColor Gray
}

uv run agentcore deploy @envArgs @deployArgs

Write-Host ""
Write-Host "✅ Agent '$($config.name)' deployed successfully!" -ForegroundColor Green
Write-Host "   Runtime: $($config.runtime_name)" -ForegroundColor Gray
Write-Host "   Check status: uv run agentcore status" -ForegroundColor Gray
