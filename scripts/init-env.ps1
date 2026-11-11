$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $target)) {
    Copy-Item -LiteralPath (Join-Path $root '.env.example') -Destination $target
}
Write-Host 'SQLite file: data/residential-picker.sqlite3. No database credentials are required.'
