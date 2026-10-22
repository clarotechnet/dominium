$ErrorActionPreference = 'Stop'
$root = 'C:\DominiumRuntime\DescRelay-20261010'
$backup = Join-Path $root 'backups\pre-confront-20261022-191438\desc_review_relay.py'
$watchdog = Join-Path $root 'ensure-desc-relay.ps1'
$source = Join-Path $root 'desc_review_relay.py'

$listener = @(Get-NetTCPConnection -LocalPort 8793 -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique)
if ($listener.Count -ne 1) { throw 'Unrecognized listener count on port 8793' }
$pidToStop = [int]$listener[0]
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$pidToStop"
if ($process.Name -ne 'python.exe' -or $process.CommandLine -notlike '*desc_review_relay.py*' -or $process.CommandLine -notlike '*8793*') {
    throw 'Port 8793 is not the expected DESC Python relay'
}
if (-not (Test-Path $backup)) { throw 'Pre-deploy backup missing' }
Stop-Process -Id $pidToStop -ErrorAction Stop
Start-Sleep -Seconds 1
try {
    & $watchdog
    $online = @(Get-NetTCPConnection -LocalPort 8793 -State Listen -ErrorAction SilentlyContinue)
    if (-not $online) { throw 'New relay did not listen' }
    Write-Output 'CONFRONT_RELAY_RESTARTED'
} catch {
    # Leave DESC available even if the new code fails to start.
    Copy-Item -LiteralPath $backup -Destination $source -Force
    $live = @(Get-NetTCPConnection -LocalPort 8793 -State Listen -ErrorAction SilentlyContinue)
    if (-not $live) { & $watchdog }
    Write-Output 'CONFRONT_RELAY_ROLLED_BACK'
    throw
}
