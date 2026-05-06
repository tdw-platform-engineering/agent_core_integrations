<#
.SYNOPSIS
    Deploy a specific agent to AWS Bedrock Agent Core.

.EXAMPLE
    .\deploy.ps1 -AgentName agente-ventas-carton
    .\deploy.ps1 -AgentName agente-presupuesto -DryRun
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

# -- Paths -------------------------------------------------------------
$agentsDir = Join-Path $PSScriptRoot "agents"
$configPath = Join-Path $agentsDir "$AgentName.json"
$sharedPath = Join-Path $agentsDir "_shared.json"
$registryPath = Join-Path $agentsDir ".registry.json"
$yamlPath = Join-Path $PSScriptRoot ".bedrock_agentcore.yaml"

# -- Load configs ------------------------------------------------------
if (-not (Test-Path $sharedPath)) { Write-Host "[ERROR] _shared.json not found" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $configPath)) { Write-Host "[ERROR] $AgentName.json not found" -ForegroundColor Red; exit 1 }

$shared = Get-Content $sharedPath -Raw | ConvertFrom-Json
$config = Get-Content $configPath -Raw | ConvertFrom-Json

$region = if ($config.region) { $config.region } else { $shared.aws.region }
$model = if ($config.model) { $config.model } else { $shared.defaults.model }
$platform = if ($config.platform) { $config.platform } else { $shared.defaults.platform }

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Agent: $($config.name)" -ForegroundColor Cyan
Write-Host "  Runtime: $($config.runtime_name) | Region: $region" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# -- Load registry -----------------------------------------------------
$registry = @{ agents = @{} }
if (Test-Path $registryPath) {
    $registryRaw = Get-Content $registryPath -Raw | ConvertFrom-Json
    $registry = @{ agents = @{} }
    if ($registryRaw.agents) {
        foreach ($prop in $registryRaw.agents.PSObject.Properties) {
            $registry.agents[$prop.Name] = @{
                arn = $prop.Value.arn
                runtime_name = $prop.Value.runtime_name
                deployed_at = $prop.Value.deployed_at
            }
        }
    }
}

# -- Resolve sub-agent ARNs (orchestrators only) -----------------------
$resolvedSubAgents = @{}
if ($config.sub_agents) {
    Write-Host "[ORCHESTRATOR] Resolving sub-agent ARNs..." -ForegroundColor Yellow
    $allResolved = $true

    foreach ($prop in $config.sub_agents.PSObject.Properties) {
        $alias = $prop.Name
        $currentArn = $prop.Value.arn

        if ([string]::IsNullOrWhiteSpace($currentArn) -or $currentArn -match "^REPLACE_") {
            $lookupName = "agente-$($alias -replace '_', '-')"
            if ($registry.agents.ContainsKey($lookupName)) {
                $currentArn = $registry.agents[$lookupName].arn
                Write-Host "   [OK] $alias -> $currentArn" -ForegroundColor Green
            } else {
                Write-Host "   [MISSING] $alias -> Deploy '$lookupName' first." -ForegroundColor Red
                $allResolved = $false
            }
        } else {
            Write-Host "   [OK] $alias -> $currentArn" -ForegroundColor Green
        }

        $resolvedSubAgents[$alias] = @{ arn = $currentArn; description = $prop.Value.description }
    }

    if (-not $allResolved) {
        Write-Host "[ERROR] Missing sub-agent ARNs. Deploy base agents first." -ForegroundColor Red
        exit 1
    }
}

# -- Build env vars ----------------------------------------------------
$envArgs = @()
$envArgs += "--env"; $envArgs += "AGENT_NAME=$($config.prompt)"
$envArgs += "--env"; $envArgs += "MODEL_ID=$model"
$envArgs += "--env"; $envArgs += "AWS_REGION=$region"
$envArgs += "--env"; $envArgs += "BYPASS_TOOL_CONSENT=true"

foreach ($prop in $config.features.PSObject.Properties) {
    $envArgs += "--env"; $envArgs += "$($prop.Name)=$($prop.Value)"
}

if ($resolvedSubAgents.Count -gt 0) {
    $envArgs += "--env"; $envArgs += "SUB_AGENTS=$($resolvedSubAgents | ConvertTo-Json -Compress -Depth 5)"
}

# Load shared vars from .env (credentials, memory, athena)
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    $sharedKeys = @(
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
        "ATHENA_LAMBDA_NAME", "ATHENA_LAMBDA_REGION",
        "MEMORY_ID", "MEMORY_ACTOR_ID",
        "KNOWLEDGE_BASE_ID", "KNOWLEDGE_BASE_REGION",
        "ENABLE_THINKING", "THINKING_BUDGET"
    )
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $key = ($line -split '=', 2)[0]
            if ($key -in $sharedKeys) {
                $envArgs += "--env"; $envArgs += $line
            }
        }
    }
}

Write-Host "[ENV] Variables: $($envArgs.Count / 2) total" -ForegroundColor Gray

if ($DryRun) {
    Write-Host "[DRY RUN] Would configure + deploy $($config.runtime_name)" -ForegroundColor Yellow
    exit 0
}

# ======================================================================
# STEP 1: Write seed yaml (always fresh for this agent)
# ======================================================================
Write-Host "[STEP 1] Writing yaml for $($config.runtime_name)..." -ForegroundColor Cyan

# Always write a clean seed - the yaml is the "active agent" config.
# Previous agents are tracked in .registry.json, not in the yaml.
# Determine if we have roles from a previous deploy
$hasExecutionRole = $shared.aws.execution_role -and $shared.aws.execution_role -ne "null"
$hasCodebuildRole = $shared.aws.codebuild_role -and $shared.aws.codebuild_role -ne "null"

$seedLines = @(
    "default_agent: $($config.runtime_name)",
    "agents:",
    "  $($config.runtime_name):",
    "    name: $($config.runtime_name)",
    "    language: python",
    "    node_version: '20'",
    "    entrypoint: $($shared.defaults.entrypoint)",
    "    deployment_type: container",
    "    runtime_type: null",
    "    platform: $platform",
    "    container_runtime: docker",
    "    source_path: $PSScriptRoot",
    "    aws:"
)

if ($hasExecutionRole) {
    $seedLines += "      execution_role: $($shared.aws.execution_role)"
    $seedLines += "      execution_role_auto_create: false"
} else {
    $seedLines += "      execution_role: null"
    $seedLines += "      execution_role_auto_create: true"
}

$seedLines += @(
    "      account: '$($shared.aws.account)'",
    "      region: $region",
    "      ecr_auto_create: true",
    "      s3_path: null",
    "      s3_auto_create: false",
    "      network_configuration:",
    "        network_mode: PUBLIC",
    "        network_mode_config: null",
    "      protocol_configuration:",
    "        server_protocol: HTTP",
    "      observability:",
    "        enabled: true",
    "      lifecycle_configuration:",
    "        idle_runtime_session_timeout: null",
    "        max_lifetime: null",
    "    bedrock_agentcore:",
    "      agent_id: null",
    "      agent_arn: null",
    "      agent_session_id: null",
    "    codebuild:",
    "      project_name: null"
)

if ($hasCodebuildRole) {
    $seedLines += "      execution_role: $($shared.aws.codebuild_role)"
} else {
    $seedLines += "      execution_role: null"
}

$seedLines += @(
    "      source_bucket: $($shared.aws.source_bucket)",
    "    memory:",
    "      mode: STM_ONLY",
    "      memory_id: $($shared.aws.shared_memory_id)",
    "      memory_arn: null",
    "      memory_name: $($config.memory.memory_name)",
    "      event_expiry_days: 7",
    "      first_invoke_memory_check_done: true",
    "      was_created_by_toolkit: false",
    "    identity:",
    "      credential_providers: []",
    "      workload: null",
    "    is_generated_by_agentcore_create: false"
)
$seedLines -join "`n" | Set-Content -Path $yamlPath -Encoding UTF8 -NoNewline
Write-Host "   [OK] Yaml written" -ForegroundColor Green

# ======================================================================
# STEP 2: Configure
# ======================================================================
Write-Host "[STEP 2] Running agentcore configure..." -ForegroundColor Cyan

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

# ======================================================================
# STEP 3: Deploy
# ======================================================================
Write-Host "[STEP 3] Deploying..." -ForegroundColor Green

$deployArgs = @()
if ($LocalBuild) { $deployArgs += "--local-build" }

uv run agentcore deploy @envArgs @deployArgs

# ======================================================================
# STEP 4: Capture ARN and save to registry
# ======================================================================
Write-Host "[STEP 4] Saving ARN to registry..." -ForegroundColor Cyan

$deployedArn = $null
$deployedExecutionRole = $null
$deployedCodebuildRole = $null

# Read from yaml (agentcore updates it after deploy)
if (Test-Path $yamlPath) {
    $yamlContent = Get-Content $yamlPath -Raw
    if ($yamlContent -match "agent_arn:\s*(arn:aws:bedrock-agentcore:\S+)") {
        $deployedArn = $Matches[1]
    }
    # Capture execution roles for reuse in future deploys
    $lines = $yamlContent -split "`n"
    $inAws = $false; $inCodebuild = $false
    foreach ($line in $lines) {
        if ($line -match "^\s{4}aws:") { $inAws = $true; $inCodebuild = $false }
        elseif ($line -match "^\s{4}codebuild:") { $inCodebuild = $true; $inAws = $false }
        elseif ($line -match "^\s{4}\w" -and $line -notmatch "^\s{6}") { $inAws = $false; $inCodebuild = $false }

        if ($inAws -and $line -match "^\s{6}execution_role:\s*(arn:aws:iam::\S+)") {
            $deployedExecutionRole = $Matches[1]
        }
        if ($inCodebuild -and $line -match "^\s{6}execution_role:\s*(arn:aws:iam::\S+)") {
            $deployedCodebuildRole = $Matches[1]
        }
    }
}

# Fallback: agentcore status
if (-not $deployedArn) {
    try {
        $statusOutput = uv run agentcore status 2>&1 | Out-String
        if ($statusOutput -match "arn:aws:bedrock-agentcore:[^:]+:\d+:runtime/[^\s""]+") {
            $deployedArn = $Matches[0]
        }
    } catch {}
}

if ($deployedArn) {
    $registry.agents[$AgentName] = @{
        arn = $deployedArn
        runtime_name = $config.runtime_name
        deployed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    }
    $registry | ConvertTo-Json -Depth 5 | Set-Content -Path $registryPath -Encoding UTF8
    Write-Host "   [OK] $deployedArn" -ForegroundColor Green
} else {
    Write-Host "   [WARN] Could not capture ARN. Check: uv run agentcore status" -ForegroundColor Yellow
}

# Update _shared.json with discovered roles (so next deploys reuse them)
if ($deployedExecutionRole -or $deployedCodebuildRole) {
    $sharedContent = Get-Content $sharedPath -Raw | ConvertFrom-Json
    $updated = $false
    if ($deployedExecutionRole -and $sharedContent.aws.execution_role -ne $deployedExecutionRole) {
        $sharedContent.aws.execution_role = $deployedExecutionRole
        $updated = $true
        Write-Host "   [OK] Saved execution_role to _shared.json" -ForegroundColor Green
    }
    if ($deployedCodebuildRole -and $sharedContent.aws.codebuild_role -ne $deployedCodebuildRole) {
        $sharedContent.aws.codebuild_role = $deployedCodebuildRole
        $updated = $true
        Write-Host "   [OK] Saved codebuild_role to _shared.json" -ForegroundColor Green
    }
    if ($updated) {
        $sharedContent | ConvertTo-Json -Depth 5 | Set-Content -Path $sharedPath -Encoding UTF8
    }
}

Write-Host ""
Write-Host "[DONE] $($config.name) deployed!" -ForegroundColor Green
