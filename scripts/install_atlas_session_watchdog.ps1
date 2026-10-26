param(
    [Parameter(Mandatory=$true)][string]$SourceModule,
    [string]$RuntimeDir = 'C:\DominiumRuntime\DescRelay-20261010',
    [string]$WatchdogDir = 'C:\DominiumRuntime\BrowserHealth-20261022',
    [string]$Python = 'C:\DominiumRuntime\Python312\python.exe'
)
$ErrorActionPreference = 'Stop'
$watchdog = Join-Path $WatchdogDir 'browser_watchdog.py'
$module = Join-Path $RuntimeDir 'atlas_query_health.py'
foreach ($file in @($SourceModule, $watchdog, $Python)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'Required input is missing' }
}
if (-not (Test-Path -LiteralPath $RuntimeDir -PathType Container)) { throw 'Runtime directory missing' }
$text = [IO.File]::ReadAllText($watchdog)
$runtimeLiteral = ConvertTo-Json -InputObject $RuntimeDir -Compress
$outputLiteral = ConvertTo-Json -InputObject (Join-Path $WatchdogDir 'atlas-service-health.json') -Compress
$block = @"
# BEGIN DOMINIUM ATLAS SESSION PROBE
sys.path.insert(0, $runtimeLiteral)
_atlas_health_path = Path($outputLiteral)
try:
    from atlas_query_health import record_health
    _atlas_health = record_health(output_path=_atlas_health_path)
except Exception:
    _atlas_health = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                     "session": "unknown", "authenticated": None, "reason": "monitor_unavailable"}
    _atlas_health_tmp = _atlas_health_path.with_suffix('.tmp')
    _atlas_health_tmp.write_text(json.dumps(_atlas_health) + '\n', encoding='utf-8')
    os.replace(_atlas_health_tmp, _atlas_health_path)
print('ATLAS_SERVICE_HEALTH', _atlas_health['session'], _atlas_health['reason'])
# END DOMINIUM ATLAS SESSION PROBE
"@
$pattern = '(?s)# BEGIN DOMINIUM ATLAS SESSION PROBE\r?\n.*?# END DOMINIUM ATLAS SESSION PROBE'
$begins = ([regex]::Matches($text, '# BEGIN DOMINIUM ATLAS SESSION PROBE')).Count
$ends = ([regex]::Matches($text, '# END DOMINIUM ATLAS SESSION PROBE')).Count
if ($begins -gt 1 -or $begins -ne $ends) { throw 'Unexpected probe markers; no patch applied' }
if ($begins -eq 1) {
    if (([regex]::Matches($text, $pattern)).Count -ne 1) { throw 'Malformed probe block; no patch applied' }
    $newText = [regex]::Replace($text, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{param($m) $block})
} else {
    $newText = $text.TrimEnd() + "`n`n" + $block + "`n"
}
$stage = $watchdog + '.atlas-session-stage'
[IO.File]::WriteAllText($stage, $newText, (New-Object Text.UTF8Encoding($false)))
$validator = $stage + '.validate.py'
[IO.File]::WriteAllText($validator, "import sys`nfor p in sys.argv[1:]:`n    compile(open(p, 'rb').read(), p, 'exec')`n")
try {
    & $Python $validator $SourceModule $stage
    if ($LASTEXITCODE -ne 0) { throw 'Python syntax validation failed; runtime unchanged' }
} finally {
    Remove-Item -LiteralPath $validator -ErrorAction SilentlyContinue
}
$backup = Join-Path $WatchdogDir ('backups\atlas-session-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -LiteralPath $watchdog -Destination (Join-Path $backup 'browser_watchdog.py')
if (Test-Path -LiteralPath $module) {
    Copy-Item -LiteralPath $module -Destination (Join-Path $backup 'atlas_query_health.py')
}
Copy-Item -LiteralPath $SourceModule -Destination ($module + '.stage')
Move-Item -LiteralPath ($module + '.stage') -Destination $module -Force
Move-Item -LiteralPath $stage -Destination $watchdog -Force
[pscustomobject]@{
    installed=$true; backup=$backup;
    module_sha256=(Get-FileHash -LiteralPath $module -Algorithm SHA256).Hash.ToLower();
    watchdog_sha256=(Get-FileHash -LiteralPath $watchdog -Algorithm SHA256).Hash.ToLower()
} | ConvertTo-Json
