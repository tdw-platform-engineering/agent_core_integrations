$envArgs = @()
Get-Content .env | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#')) {
        $envArgs += "--env"
        $envArgs += $line
    }
}

Write-Host "🚀 Deploying with env vars..."
uv run agentcore deploy @envArgs @args
