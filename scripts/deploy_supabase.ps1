param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ProjectRef = ([string]$env:SUPABASE_PROJECT_REF).Trim()
if (-not $ProjectRef) {
    throw "SUPABASE_PROJECT_REF nao foi definido"
}
if (-not ([string]$env:SUPABASE_DB_PASSWORD).Trim()) {
    throw "SUPABASE_DB_PASSWORD nao foi definido"
}

Write-Host "Projeto Supabase: $ProjectRef"
Write-Host "Linkando projeto sem exibir a senha do banco..."
& npx --yes supabase@latest link --project-ref $ProjectRef --yes
if ($LASTEXITCODE -ne 0) { throw "Falha ao linkar o projeto Supabase" }

Write-Host "Validando migrations em dry-run..."
& npx --yes supabase@latest db push --linked --dry-run --yes
if ($LASTEXITCODE -ne 0) { throw "Dry-run das migrations falhou" }
Write-Host "Comparando configuracao Auth remota..."
& npx --yes supabase@latest config diff `
    --workdir ".\deploy\supabase-hosted" --project-ref $ProjectRef
if ($LASTEXITCODE -ne 0) { throw "Diff da configuracao Auth falhou" }

if (-not $Apply) {
    Write-Host "DRY_RUN=1"
    Write-Host "Use -Apply somente depois de revisar migration e config diff."
    exit 0
}

Write-Host "Aplicando migrations pendentes..."
& npx --yes supabase@latest db push --linked --yes
if ($LASTEXITCODE -ne 0) { throw "Aplicacao das migrations falhou" }

Write-Host "Aplicando somente a configuracao Auth declarada no perfil minimo..."
& npx --yes supabase@latest config push `
    --workdir ".\deploy\supabase-hosted" --project-ref $ProjectRef --yes
if ($LASTEXITCODE -ne 0) { throw "Configuracao Auth remota falhou" }

Write-Host "SUPABASE_REMOTE_READY=1"
