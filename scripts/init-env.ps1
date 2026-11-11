$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root '.env'
if (Test-Path -LiteralPath $target) { Write-Host '.env already exists; unchanged.'; exit 0 }
function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
$content = "MYSQL_ROOT_PASSWORD=$(New-LocalSecret)`nMYSQL_PASSWORD=$(New-LocalSecret)`n"
[System.IO.File]::WriteAllText($target, $content, (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Created .env with random local credentials.'
