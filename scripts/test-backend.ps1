$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    ./.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    $previousUrl = $env:DATABASE_URL
    $previousDemo = $env:DEMO_MODE
    try {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
        $env:DEMO_MODE = 'false'
        Push-Location backend
        try {
            ../.venv/Scripts/python.exe -m pytest -q
            if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
        } finally { Pop-Location }
    } finally {
        $env:DATABASE_URL = $previousUrl
        $env:DEMO_MODE = $previousDemo
    }
} finally { Pop-Location }
