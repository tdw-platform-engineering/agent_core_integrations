<#
.SYNOPSIS
    Deploy a specific agent to AWS Bedrock Agent Core.

.DESCRIPTION
    Reads the agent configuration from agents/<agent-name>.json,
    configures the runtime, and deploys it. Each agent gets its own
    isolated runtime with its own ARN, memory, and prompt.

    After a successful deploy, the agent's ARN is saved to agents/.registry.json.
    Orchestrator agents automatically resolve sub-agent ARNs from the registry.

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

# ── Paths ────────────────────────────────────────────────────────────
$agentsDir = Join-Path $PSScriptRoot "agents"
$configPath = Join-Path $agentsDir "$AgentName.json"
$registryPath = Join-Path $agentsDir ".registry.json"

# ── Load agent config ────────────────────────────────────────────────
if (-not (Test-Path $configPath)) {
    Write-Host "❌ Agent config not found: $configPath" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Deploying Agent: $($config.name)" -ForegroundColor Cyan
Write-Host "║  Description: $($config.description)" -ForegroundColor Cyan
Write-Host "║  Runtime: $($config.runtime_name)" -ForegroundColor Cyan
Write-Host "║  Region: $($config.region)" -ForegroundColor Cyan
Write-Host "║  Model: $($config.model)" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Load registry ────────────────────────────────────────────────────
$registry = @{ agents = @{} }
if (Test-Path $registryPath) {
    $registry = Get-Content $registryPath -Raw | ConvertFrom-Json -AsHashtable
    if (-not $registry.agents) { $registry.agents = @{} }
}

# ── Resolve sub-agent ARNs from registry (for orchestrators) ─────────
$resolvedSubAgents = @{}
if ($config.sub_agents) {
    Write-Host "🔗 Orchestrator mode — resolving sub-agent ARNs from registry..." -ForegroundColor Yellow

    $allResolved = $true
    foreach ($prop in $config.sub_agents.PSObject.Properties) {
        $alias = $prop.Name
        $subConfig = $prop.Value
        $currentArn = $subConfig.arn

        # If ARN is a placeholder, try to resolve from registry
        if ($currentArn -match "^REPLACE_" -or [string]::IsNullOrWhiteSpace($currentArn)) {
            # Try to find the sub-agent in the registry by matching the alias to an agent name
            # Convention: alias "ventas_papel" maps to agent "agente-ventas-papel"
            $possibleNames = @(
                "agente-$($alias -replace '_', '-')",
                $alias
            )

            $resolved = $false
            foreach ($name in $possibleNames) {
                if ($registry.agents.ContainsKey($name)) {
                    $currentArn = $registry.agents[$name].arn
                    Write-Host "   ✅ $alias → $currentArn (from registry: $name)" -ForegroundColor Green
                    $resolved = $true
                    break
                }
            }

            if (-not $resolved) {
                Write-Host "   ❌ $alias → NOT FOUND in registry. Deploy '$($possibleNames[0])' first." -ForegroundColor Red
                $allResolved = $false
            }
        } else {
            Write-Host "   ✅ $alias → $currentArn (from config)" -ForegroundColor Green
        }

        $resolvedSubAgents[$alias] = @{
            arn = $currentArn
            description = $subConfig.description
        }
    }

    if (-not $allResolved) {
        Write-Host ""
        Write-Host "❌ Cannot deploy orchestrator — missing sub-agent ARNs." -ForegroundColor Red
        Write-Host "   Deploy the base agents first, then retry this orchestrator." -ForegroundColor Red
        Write-Host "   Registry location: $registryPath" -ForegroundColor Gray
        exit 1
    }
}

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

# Sub-agents (serialized JSON for orchestrators)
if ($resolvedSubAgents.Count -gt 0) {
    $subAgentsJson = ($resolvedSubAgents | ConvertTo-Json -Compress -Depth 5)
    $envArgs += "--env"
    $envArgs += "SUB_AGENTS=$subAgentsJson"
}

# Memory config
if ($config.features.ENABLE_MEMORY -eq "true" -and $config.memory.memory_name) {
    Write-Host "📝 Memory enabled: $($config.memory.memory_name)" -ForegroundColor Yellow
    if ($config.memory.shared) {
        Write-Host "   ⚠️  Shared memory — ensure MEMORY_ID is set in runtime env" -ForegroundColor Yellow
    }
}

# Load credentials and shared vars from .env
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $key = ($line -split '=', 2)[0]
            # Only pass credentials and shared config (not feature flags — those come from agent JSON)
            $sharedKeys = @(
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "ATHENA_LAMBDA_NAME", "ATHENA_LAMBDA_REGION",
                "MEMORY_ID", "KNOWLEDGE_BASE_ID"
            )
            if ($key -in $sharedKeys) {
                $envArgs += "--env"
                $envArgs += $line
            }
        }
    }
}

# ── Show summary ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "📋 Environment variables:" -ForegroundColor Gray
for ($i = 0; $i -lt $envArgs.Count; $i += 2) {
    $val = $envArgs[$i + 1]
    if ($val -match "SECRET|KEY|TOKEN") {
        $parts = $val -split '=', 2
        Write-Host "   $($parts[0])=***" -ForegroundColor Gray
    } else {
        # Truncate long values (like SUB_AGENTS JSON)
        if ($val.Length -gt 100) {
            Write-Host "   $($val.Substring(0, 100))..." -ForegroundColor Gray
        } else {
            Write-Host "   $val" -ForegroundColor Gray
        }
    }
}
Write-Host ""

if ($DryRun) {
    Write-Host "🔍 DRY RUN — would execute:" -ForegroundColor Yellow
    Write-Host "   uv run agentcore configure ..." -ForegroundColor Yellow
    Write-Host "   uv run agentcore deploy ..." -ForegroundColor Yellow
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

if ($config.features.ENABLE_MEMORY -ne "true") {
    $configureArgs += "--disable-memory"
}

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

# ── Capture ARN from status and save to registry ─────────────────────
Write-Host ""
Write-Host "📋 Capturing deployed ARN..." -ForegroundColor Cyan

try {
    $statusOutput = uv run agentcore status 2>&1 | Out-String

    # Try to extract ARN from status output
    $arnMatch = [regex]::Match($statusOutput, 'arn:aws:bedrock-agentcore:[^:]+:\d+:runtime/[^\s"]+')

    if ($arnMatch.Success) {
        $deployedArn = $arnMatch.Value

        # Update registry
        $registry.agents[$AgentName] = @{
            arn = $deployedArn
            runtime_name = $config.runtime_name
            deployed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
        }

        $registryJson = $registry | ConvertTo-Json -Depth 5
        Set-Content -Path $registryPath -Value $registryJson -Encoding UTF8

        Write-Host "   ✅ ARN saved to registry: $deployedArn" -ForegroundColor Green
    } else {
        # Fallback: try to read from .bedrock_agentcore.yaml
        $yamlPath = Join-Path $PSScriptRoot ".bedrock_agentcore.yaml"
        if (Test-Path $yamlPath) {
            $yamlContent = Get-Content $yamlPath -Raw
            $arnYamlMatch = [regex]::Match($yamlContent, 'agent_arn:\s*(arn:aws:bedrock-agentcore:[^\s]+)')
            if ($arnYamlMatch.Success) {
                $deployedArn = $arnYamlMatch.Groups[1].Value

                $registry.agents[$AgentName] = @{
                    arn = $deployedArn
                    runtime_name = $config.runtime_name
                    deployed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
                }

                $registryJson = $registry | ConvertTo-Json -Depth 5
                Set-Content -Path $registryPath -Value $registryJson -Encoding UTF8

                Write-Host "   ✅ ARN saved to registry (from yaml): $deployedArn" -ForegroundColor Green
            }
        }

        if (-not $deployedArn) {
            Write-Host "   ⚠️  Could not capture ARN automatically." -ForegroundColor Yellow
            Write-Host "   Run 'uv run agentcore status' and update $registryPath manually." -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "   ⚠️  Could not capture ARN: $_" -ForegroundColor Yellow
}

# ── Done ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "✅ Agent '$($config.name)' deployed successfully!" -ForegroundColor Green
Write-Host "   Runtime: $($config.runtime_name)" -ForegroundColor Gray
Write-Host "   Registry: $registryPath" -ForegroundColor Gray
Write-Host "   Check status: uv run agentcore status" -ForegroundColor Gray
