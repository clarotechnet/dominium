param(
  [string]$Output = "$PSScriptRoot\\dominium-web-prod.zip"
)

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
$Stage = Join-Path $env:TEMP "dominium-hostinger-package"

if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage | Out-Null

Copy-Item (Join-Path $PSScriptRoot "server.js") (Join-Path $Stage "server.js")
Copy-Item (Join-Path $PSScriptRoot "package.json") (Join-Path $Stage "package.json")
Copy-Item (Join-Path $RepoRoot "protocol_templates.json") (Join-Path $Stage "protocol_templates.json")
Copy-Item (Join-Path $RepoRoot "static") (Join-Path $Stage "static") -Recurse

if (Test-Path $Output) { Remove-Item $Output -Force }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Output -CompressionLevel Optimal
Write-Host "Pacote criado em $Output"
