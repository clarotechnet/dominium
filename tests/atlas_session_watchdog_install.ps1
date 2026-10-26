param([Parameter(Mandatory=$true)][string]$Installer,
      [Parameter(Mandatory=$true)][string]$SourceModule,
      [Parameter(Mandatory=$true)][string]$Output,
      [string]$Python='C:\DominiumRuntime\Python312\python.exe')
$ErrorActionPreference='Stop'
$root=Join-Path ([IO.Path]::GetTempPath()) ('dominium-atlas-watchdog-test-'+[guid]::NewGuid().ToString('N'))
$runtime=Join-Path $root 'runtime'
$watchdir=Join-Path $root 'watchdog'
New-Item -ItemType Directory -Force $runtime,$watchdir | Out-Null
$watch=Join-Path $watchdir 'browser_watchdog.py'
$prefix="import sys, os, json, datetime as dt`nfrom pathlib import Path`nprint('BASE_WATCHDOG')`n"
[IO.File]::WriteAllText($watch,$prefix)
$checks=@()
function Assert-Condition($condition,$name) {
    if (-not $condition) { throw ('Fixture failed: '+$name) }
}
& $Installer -SourceModule $SourceModule -RuntimeDir $runtime -WatchdogDir $watchdir -Python $Python | Out-Null
$first=[IO.File]::ReadAllText($watch)
Assert-Condition ($first.StartsWith($prefix.TrimEnd())) 'original watchdog preserved'
$checks+='prefix_preserved'
$firstHash=(Get-FileHash $watch).Hash
& $Installer -SourceModule $SourceModule -RuntimeDir $runtime -WatchdogDir $watchdir -Python $Python | Out-Null
Assert-Condition ((Get-FileHash $watch).Hash -eq $firstHash) 'second install must be idempotent'
$checks+='idempotent_install'
Assert-Condition ((Get-ChildItem (Join-Path $watchdir 'backups') -Recurse -Filter browser_watchdog.py).Count -eq 2) 'both backups exist'
$checks+='backups_created'
# Fixture runtime has no connector dependencies: import must fail closed and
# replace a stale authenticated record with monitor_unavailable.
$health=Join-Path $watchdir 'atlas-service-health.json'
[IO.File]::WriteAllText($health,'{"session":"authenticated"}')
& $Python $watch | Out-Null
Assert-Condition ($LASTEXITCODE -eq 0) 'fallback execution'
$state=Get-Content $health -Raw | ConvertFrom-Json
Assert-Condition ($state.session -eq 'unknown' -and $state.reason -eq 'monitor_unavailable') 'stale success replaced on import failure'
$checks+='import_failure_replaces_success'
$badSource=Join-Path $root 'invalid.py'
[IO.File]::WriteAllText($badSource,'def broken(:')
$failed=$false
try { & $Installer -SourceModule $badSource -RuntimeDir $runtime -WatchdogDir $watchdir -Python $Python | Out-Null } catch { $failed=$true }
Assert-Condition $failed 'invalid source rejected'
Assert-Condition ((Get-FileHash $watch).Hash -eq $firstHash) 'invalid source leaves runtime unchanged'
$checks+='syntax_failure_preserves_runtime'
$malformed=$prefix+"`n# END DOMINIUM ATLAS SESSION PROBE`n# BEGIN DOMINIUM ATLAS SESSION PROBE`n"
[IO.File]::WriteAllText($watch,$malformed)
$failed=$false
try { & $Installer -SourceModule $SourceModule -RuntimeDir $runtime -WatchdogDir $watchdir -Python $Python | Out-Null } catch { $failed=$true }
Assert-Condition $failed 'reversed markers rejected'
Assert-Condition ([IO.File]::ReadAllText($watch) -eq $malformed) 'rejected markers preserve watchdog'
$checks+='reversed_markers_rejected'
[pscustomobject]@{passed=$true;checks=$checks;fixture=$root} | ConvertTo-Json | Set-Content $Output
