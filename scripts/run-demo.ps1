$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & "$PSScriptRoot/init-env.ps1"
    docker compose --profile demo up -d --build demo-frontend
    if ($LASTEXITCODE -ne 0) { throw 'Demo startup failed.' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        docker compose --profile demo exec -T demo-backend python -c 'import socket, sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex(("127.0.0.1", 8000)))' 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'Demo API did not start; inspect docker compose logs demo-backend.' }
    docker compose --profile demo exec -T demo-backend python -m app.cli demo-seed
    if ($LASTEXITCODE -ne 0) { throw 'Demo seeding failed.' }
    Write-Host 'Demo ready: http://localhost:8081'
} finally { Pop-Location }
