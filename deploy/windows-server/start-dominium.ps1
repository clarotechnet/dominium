$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$EnvFile = Join-Path $Root '.env'
$Port = 8791

if (-not (Test-Path $Python)) { throw "Python virtualenv nao encontrado: $Python" }
if (-not (Test-Path $EnvFile)) { throw ".env de producao nao encontrado: $EnvFile" }

Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $parts = $line -split '=', 2
    if ($parts.Count -ne 2) { return }
    $name = $parts[0].Trim()
    $value = $parts[1].Trim()
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}

Set-Location $Root
& $Python -u .\app.py --host 0.0.0.0 --port $Port
exit $LASTEXITCODE
