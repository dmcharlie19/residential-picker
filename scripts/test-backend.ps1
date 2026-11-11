$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & "$PSScriptRoot/init-env.ps1"
    docker compose up -d --wait mysql
    if ($LASTEXITCODE -ne 0) { throw 'MySQL startup failed.' }
    @'
CREATE DATABASE IF NOT EXISTS residential_picker_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON residential_picker_test.* TO 'residential_app'@'%';
'@ | docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot'
    if ($LASTEXITCODE -ne 0) { throw 'Test database setup failed.' }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    ./.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    $localConfig = Get-Content -LiteralPath '.env' | ConvertFrom-StringData
    $previousDatabaseUrl = $env:DATABASE_URL
    $previousTestUrl = $env:TEST_DATABASE_URL
    $previousDemoMode = $env:DEMO_MODE
    try {
        $env:DATABASE_URL = "mysql+pymysql://residential_app:$($localConfig.MYSQL_PASSWORD)@127.0.0.1:13306/residential_picker_test?charset=utf8mb4"
        $env:TEST_DATABASE_URL = $env:DATABASE_URL
        $env:DEMO_MODE = 'false'
        Push-Location backend
        try {
            ../.venv/Scripts/python.exe -m pytest -q
            if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
        } finally { Pop-Location }
    } finally {
        $env:DATABASE_URL = $previousDatabaseUrl
        $env:TEST_DATABASE_URL = $previousTestUrl
        $env:DEMO_MODE = $previousDemoMode
    }
} finally { Pop-Location }
