<#
.SYNOPSIS
    Deploy a specific agent to AWS Bedrock Agent Core.

.DESCRIPTION
    Reads the agent configuration from agents/<agent-name>.json,
    configures the runtime, and deploys it. Each agent gets its own
    isolated runtime with its own ARN, memory, and prompt.

    The .bedrock_agentcore.yaml is preserved with ALL agents listed.
    After deploy, the new agent is added/updated without removing others.

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
$sharedPath = Join-Path $agentsDir "_shared.json"
$registryPath = Join-Path $agentsDir ".registry.json"
$yamlPath = Join-Path $PSScriptRoot ".bedrock_agentcore.yaml"

# ── Load shared config ───────────────────────────────────────────────
if (-not (Test-Path $sharedPath)) {
    Write-Host "❌ Shared config not found: $sharedPath" -ForegroundColor Red
    exit 1
}
$shared = Get-Content $sharedPath -Raw | ConvertFrom-Json

# ── Load agent config ────────────────────────────────────────────────
if (-not (Test-Path $configPath)) {
    Write-Host "❌ Agent config not found: $configPath" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json

# Merge defaults from shared
$region = if ($config.region) { $config.region } else { $shared.aws.region }
$model = if ($config.model) { $config.model } else { $shared.defaults.model }
$platform = if ($config.platform) { $config.platform } else { $shared.defaults.platform }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Deploying Agent: $($config.name)" -ForegroundColor Cyan
Write-Host "║  Description: $($config.description)" -ForegroundColor Cyan
Write-Host "║  Runtime: $($config.runtime_name)" -ForegroundColor Cyan
Write-Host "║  Region: $region" -ForegroundColor Cyan
Write-Host "║  Model: $model" -ForegroundColor Cyan
Write-Host "║  Source Bucket: $($shared.aws.source_bucket)" -ForegroundColor Cyan
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
        exit 1
    }
}

# ── Build env vars from config ───────────────────────────────────────
$envArgs = @()

# Core vars
$envArgs += "--env"; $envArgs += "AGENT_NAME=$($config.prompt)"
$envArgs += "--env"; $envArgs += "MODEL_ID=$model"
$envArgs += "--env"; $envArgs += "AWS_REGION=$region"
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
}

# Load credentials and shared vars from .env
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $key = ($line -split '=', 2)[0]
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
    } elseif ($val.Length -gt 100) {
        Write-Host "   $($val.Substring(0, 100))..." -ForegroundColor Gray
    } else {
        Write-Host "   $val" -ForegroundColor Gray
    }
}
Write-Host ""

if ($DryRun) {
    Write-Host "🔍 DRY RUN — would execute:" -ForegroundColor Yellow
    Write-Host "   1. Backup existing yaml entries" -ForegroundColor Yellow
    Write-Host "   2. agentcore configure --name $($config.runtime_name) ..." -ForegroundColor Yellow
    Write-Host "   3. agentcore deploy ..." -ForegroundColor Yellow
    Write-Host "   4. Merge all agents back into yaml" -ForegroundColor Yellow
    Write-Host "   5. Save ARN to registry" -ForegroundColor Yellow
    exit 0
}

# ══════════════════════════════════════════════════════════════════════
# STEP 1: Backup existing yaml (preserve all other agents)
# ══════════════════════════════════════════════════════════════════════
Write-Host "📄 Backing up existing yaml entries..." -ForegroundColor Cyan

$existingYamlContent = ""
if (Test-Path $yamlPath) {
    $existingYamlContent = Get-Content $yamlPath -Raw
}

# ══════════════════════════════════════════════════════════════════════
# STEP 2: Configure (this overwrites the yaml with only the new agent)
# ══════════════════════════════════════════════════════════════════════
Write-Host "⚙️  Configuring agent runtime: $($config.runtime_name)..." -ForegroundColor Cyan

$configureArgs = @(
    "--entrypoint", $shared.defaults.entrypoint,
    "--name", $config.runtime_name,
    "--region", $region,
    "--non-interactive"
)

if ($config.features.ENABLE_MEMORY -ne "true") {
    $configureArgs += "--disable-memory"
}

uv run agentcore configure @configureArgs

# ── Patch yaml to use shared resources ───────────────────────────────
Write-Host "   Patching yaml to use shared bucket and roles..." -ForegroundColor Gray
if (Test-Path $yamlPath) {
    $yamlText = Get-Content $yamlPath -Raw

    # Use shared source bucket (same for all agents)
    $yamlText = $yamlText -replace "source_bucket:.*", "source_bucket: $($shared.aws.source_bucket)"

    # Use shared execution role
    $yamlText = $yamlText -replace "(execution_role:)\s*arn:aws:iam::\d+:role/AmazonBedrockAgentCoreSDKRuntime[^\s]*", "`$1 $($shared.aws.execution_role)"

    # Use shared codebuild role
    $yamlText = $yamlText -replace "(execution_role:)\s*arn:aws:iam::\d+:role/AmazonBedrockAgentCoreSDKCodeBuild[^\s]*", "`$1 $($shared.aws.codebuild_role)"

    # Disable auto-create for shared resources
    $yamlText = $yamlText -replace "s3_auto_create:\s*true", "s3_auto_create: false"
    $yamlText = $yamlText -replace "execution_role_auto_create:\s*true", "execution_role_auto_create: false"

    Set-Content -Path $yamlPath -Value $yamlText -Encoding UTF8
    Write-Host "   ✅ Shared bucket: $($shared.aws.source_bucket)" -ForegroundColor Green
}

# ══════════════════════════════════════════════════════════════════════
# STEP 3: Merge — read the new yaml, then merge back all previous agents
# ══════════════════════════════════════════════════════════════════════
Write-Host "🔀 Merging agent entries into yaml..." -ForegroundColor Cyan

if ($existingYamlContent -and (Test-Path $yamlPath)) {
    $newYamlContent = Get-Content $yamlPath -Raw

    # Strategy: The new yaml has the freshly configured agent.
    # We need to append all OTHER agent blocks from the old yaml.
    # 
    # Since PowerShell doesn't have a native YAML parser, we use a 
    # simple approach: extract agent blocks by indentation pattern.
    
    # Get the runtime_name of the newly configured agent (it's now default_agent)
    $newAgentKey = $config.runtime_name

    # Extract all agent blocks from the OLD yaml (except the one we just configured)
    $oldAgentBlocks = @{}
    $currentAgent = ""
    $currentBlock = @()
    
    foreach ($line in ($existingYamlContent -split "`n")) {
        # Detect agent entry start (2-space indent, ends with colon)
        if ($line -match "^  (\w[\w_-]*):$" -and $line -notmatch "^\s{4}") {
            # Save previous block
            if ($currentAgent -and $currentAgent -ne $newAgentKey) {
                $oldAgentBlocks[$currentAgent] = $currentBlock -join "`n"
            }
            $currentAgent = $Matches[1]
            $currentBlock = @($line)
        } elseif ($currentAgent -and ($line -match "^\s{4}" -or $line -match "^\s*$")) {
            # Lines belonging to current agent (4+ spaces indent)
            $currentBlock += $line
        } else {
            # Save last block if we hit a non-agent line
            if ($currentAgent -and $currentAgent -ne $newAgentKey) {
                $oldAgentBlocks[$currentAgent] = $currentBlock -join "`n"
            }
            $currentAgent = ""
            $currentBlock = @()
        }
    }
    # Don't forget last block
    if ($currentAgent -and $currentAgent -ne $newAgentKey) {
        $oldAgentBlocks[$currentAgent] = $currentBlock -join "`n"
    }

    # Append old agent blocks to the new yaml
    if ($oldAgentBlocks.Count -gt 0) {
        $appendContent = ""
        foreach ($block in $oldAgentBlocks.Values) {
            $appendContent += "`n$block"
        }
        Add-Content -Path $yamlPath -Value $appendContent -Encoding UTF8
        Write-Host "   ✅ Merged $($oldAgentBlocks.Count) existing agent(s) back into yaml" -ForegroundColor Green
    }
}

# ══════════════════════════════════════════════════════════════════════
# STEP 4: Deploy
# ══════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "🚀 Deploying..." -ForegroundColor Green

$deployArgs = @()
if ($LocalBuild) {
    $deployArgs += "--local-build"
    Write-Host "   Using local Docker build" -ForegroundColor Gray
}

uv run agentcore deploy @envArgs @deployArgs

# ══════════════════════════════════════════════════════════════════════
# STEP 5: Capture ARN and save to registry
# ══════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "📋 Capturing deployed ARN..." -ForegroundColor Cyan

$deployedArn = $null

# Primary: read from the yaml (agentcore updates it after deploy)
if (Test-Path $yamlPath) {
    $yamlContent = Get-Content $yamlPath -Raw
    # Look for the agent_arn of the current agent
    $arnPattern = "agent_arn:\s*(arn:aws:bedrock-agentcore:[^\s]+)"
    
    # Find the section for our agent and extract its ARN
    $inOurAgent = $false
    foreach ($line in ($yamlContent -split "`n")) {
        if ($line -match "^\s{2}$($config.runtime_name):") {
            $inOurAgent = $true
        } elseif ($line -match "^\s{2}\w" -and $inOurAgent) {
            break  # hit next agent
        }
        if ($inOurAgent -and $line -match "agent_arn:\s*(arn:aws:bedrock-agentcore:\S+)") {
            $deployedArn = $Matches[1]
            break
        }
    }
}

# Fallback: try agentcore status
if (-not $deployedArn) {
    try {
        $statusOutput = uv run agentcore status 2>&1 | Out-String
        $arnMatch = [regex]::Match($statusOutput, 'arn:aws:bedrock-agentcore:[^:]+:\d+:runtime/[^\s"]+')
        if ($arnMatch.Success) {
            $deployedArn = $arnMatch.Value
        }
    } catch {}
}

if ($deployedArn) {
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
    Write-Host "   ⚠️  Could not capture ARN automatically." -ForegroundColor Yellow
    Write-Host "   Run 'uv run agentcore status' and check the yaml." -ForegroundColor Yellow
}

# ── Done ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "✅ Agent '$($config.name)' deployed successfully!" -ForegroundColor Green
Write-Host "   Runtime: $($config.runtime_name)" -ForegroundColor Gray
Write-Host "   Active in yaml: default_agent = $($config.runtime_name)" -ForegroundColor Gray
Write-Host ""
Write-Host "   To switch active agent: .\switch-agent.ps1 -AgentName <name>" -ForegroundColor Gray
Write-Host "   To check status: uv run agentcore status" -ForegroundColor Gray
