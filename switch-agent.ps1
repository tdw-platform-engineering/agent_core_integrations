<#
.SYNOPSIS
    Switch the active agent in .bedrock_agentcore.yaml.

.DESCRIPTION
    Changes the 'default_agent' field in the yaml to point to a different
    agent runtime. This allows running agentcore CLI commands (status, invoke,
    destroy) against any deployed agent.

.PARAMETER AgentName
    Name of the agent to switch to (uses the runtime_name from its config).

.EXAMPLE
    .\switch-agent.ps1 -AgentName agente-ventas-carton
    uv run agentcore status
    uv run agentcore invoke '{"input": "ventas enero 2025", "runtimeSessionId": "test-1"}'
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$AgentName
)

$yamlPath = Join-Path $PSScriptRoot ".bedrock_agentcore.yaml"
$configPath = Join-Path $PSScriptRoot "agents" "$AgentName.json"

if (-not (Test-Path $yamlPath)) {
    Write-Host "❌ No .bedrock_agentcore.yaml found. Deploy an agent first." -ForegroundColor Red
    exit 1
}

# Get the runtime_name from the agent config
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    $runtimeName = $config.runtime_name
} else {
    # Fallback: convert agent name to runtime name (replace - with _)
    $runtimeName = $AgentName -replace '-', '_'
}

# Check if this agent exists in the yaml
$yamlContent = Get-Content $yamlPath -Raw
if ($yamlContent -notmatch "^\s{2}${runtimeName}:" ) {
    Write-Host "❌ Agent '$runtimeName' not found in yaml." -ForegroundColor Red
    Write-Host "   Available agents in yaml:" -ForegroundColor Gray

    $yamlContent -split "`n" | ForEach-Object {
        if ($_ -match "^\s{2}(\w[\w_-]*):$") {
            Write-Host "   - $($Matches[1])" -ForegroundColor Gray
        }
    }
    exit 1
}

# Update default_agent
$updatedYaml = $yamlContent -replace "^default_agent:\s*\S+", "default_agent: $runtimeName"
Set-Content -Path $yamlPath -Value $updatedYaml -Encoding UTF8

Write-Host "✅ Switched active agent to: $runtimeName" -ForegroundColor Green
Write-Host ""
Write-Host "   You can now run:" -ForegroundColor Gray
Write-Host "   uv run agentcore status" -ForegroundColor Gray
Write-Host "   uv run agentcore invoke '{""input"": ""test"", ""runtimeSessionId"": ""test-1""}'" -ForegroundColor Gray
