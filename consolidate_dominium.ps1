# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO DIRETO - infraestrutura comum, sem regra de negocio Imperium.
#
# TOA
# - NAO DIRETO - infraestrutura comum, sem regra de negocio TOA.
#
# DOMINIUM COMPARTILHADO
# - SIM - seguranca, interface, voz, empacotamento ou inicializacao.
#
# Categoria deste arquivo: COMPARTILHADO.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
param(
    [string]$Destination = "C:\Users\Public\Documents\Dominium_Technet"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ecosystemRoot = "C:\Users\Public\Documents\Consulte Sistemas\Imperium"
$destinationRoot = [System.IO.Path]::GetFullPath($Destination).TrimEnd("\")
$sourceRoot = [System.IO.Path]::GetFullPath($ecosystemRoot).TrimEnd("\")

if ($destinationRoot.StartsWith($sourceRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "O destino nao pode ficar dentro do ecossistema de origem."
}
if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
    throw "Ecossistema principal nao encontrado: $sourceRoot"
}

$folders = @(
    $destinationRoot,
    (Join-Path $destinationRoot "00_LEIA_PRIMEIRO"),
    (Join-Path $destinationRoot "01_ECOSSISTEMA_PRINCIPAL"),
    (Join-Path $destinationRoot "02_PROJETOS_E_FERRAMENTAS_EXTERNAS"),
    (Join-Path $destinationRoot "03_ARQUIVOS_AVULSOS"),
    (Join-Path $destinationRoot "04_ANEXOS_CODEX"),
    (Join-Path $destinationRoot "99_INVENTARIO")
)
foreach ($folder in $folders) {
    [System.IO.Directory]::CreateDirectory($folder) | Out-Null
}

$copyRecords = [System.Collections.Generic.List[object]]::new()
$excludedRecords = [System.Collections.Generic.List[object]]::new()
$errorRecords = [System.Collections.Generic.List[object]]::new()

function Add-CopyRecord {
    param([string]$Source, [string]$Target, [string]$Kind, [string]$Note = "")
    $copyRecords.Add([pscustomobject]@{
        source = $Source
        destination = $Target
        kind = $Kind
        note = $Note
    })
}

function Copy-TreeSafe {
    param(
        [string]$Source,
        [string]$Target,
        [bool]$KeepDependencies = $false
    )
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        return
    }
    [System.IO.Directory]::CreateDirectory($Target) | Out-Null
    $arguments = @(
        $Source,
        $Target,
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/R:1",
        "/W:1",
        "/XJ",
        "/NP",
        "/NFL",
        "/NDL",
        "/XF",
        "*.rartemp"
    )
    if (-not $KeepDependencies) {
        $arguments += @(
            "/XD",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            "Cache",
            "Code Cache",
            "GPUCache"
        )
    }
    & robocopy @arguments | Out-Null
    $exitCode = $LASTEXITCODE
    if ($exitCode -gt 7) {
        $errorRecords.Add([pscustomobject]@{
            source = $Source
            destination = $Target
            error = "robocopy exit code $exitCode"
        })
    } else {
        Add-CopyRecord -Source $Source -Target $Target -Kind "directory" -Note $(if ($KeepDependencies) { "copia completa" } else { "sem caches e dependencias regeneraveis" })
    }
}

function Test-IsBelow {
    param([string]$Path, [string[]]$Roots)
    $full = [System.IO.Path]::GetFullPath($Path)
    foreach ($root in $Roots) {
        $normalized = [System.IO.Path]::GetFullPath($root).TrimEnd("\")
        if ($full.Equals($normalized, [System.StringComparison]::OrdinalIgnoreCase) -or
            $full.StartsWith($normalized + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-Category {
    param([System.IO.FileInfo]$File)
    $name = $File.Name
    $extension = $File.Extension.ToLowerInvariant()
    if ($name -match "(?i)^Atividades-" -or $extension -eq ".csv") { return "01_CSV_TOA" }
    if ($name -match "(?i)(inventario|estoque|tecnico)") { return "02_INVENTARIOS_E_EQUIPE" }
    if ($name -match "(?i)^imperium-" -or $extension -in @(".pcapng", ".etl", ".har")) { return "03_CAPTURAS_E_FLUXOS" }
    if ($extension -in @(".mp4", ".m4a", ".opus", ".wav")) { return "04_AUDIOS_E_GRAVACOES" }
    if ($extension -in @(".pptx", ".docx", ".pdf", ".md", ".txt")) { return "05_DOCUMENTOS_E_APRESENTACOES" }
    if ($extension -in @(".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")) { return "06_IMAGENS_E_REFERENCIAS" }
    if ($extension -in @(".zip", ".rar", ".7z")) { return "07_PACOTES_E_BACKUPS" }
    if ($extension -in @(".py", ".js", ".mjs", ".css", ".html", ".json", ".cmd", ".ps1")) { return "08_CODIGO_E_EXTENSOES" }
    if ($extension -eq ".dat") { return "09_PRIVADO_CREDENCIAIS" }
    return "10_OUTROS"
}

function Copy-StandaloneFile {
    param([System.IO.FileInfo]$File, [string]$BaseTarget, [string]$Kind = "standalone")
    $hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash
    $category = Get-Category -File $File
    $categoryRoot = Join-Path $BaseTarget $category
    [System.IO.Directory]::CreateDirectory($categoryRoot) | Out-Null
    $safeName = $File.Name
    $target = Join-Path $categoryRoot $safeName
    if (Test-Path -LiteralPath $target) {
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        if ($targetHash -eq $hash) {
            Add-CopyRecord -Source $File.FullName -Target $target -Kind "duplicate" -Note "conteudo identico; mantida uma copia"
            return
        }
        $base = [System.IO.Path]::GetFileNameWithoutExtension($safeName)
        $extension = [System.IO.Path]::GetExtension($safeName)
        $target = Join-Path $categoryRoot ("{0}__{1}{2}" -f $base, $hash.Substring(0, 10), $extension)
    }
    Copy-Item -LiteralPath $File.FullName -Destination $target -Force
    Add-CopyRecord -Source $File.FullName -Target $target -Kind $Kind -Note ("SHA256=" + $hash)
}

$ecosystemTarget = Join-Path $destinationRoot "01_ECOSSISTEMA_PRINCIPAL\Imperium"
Copy-TreeSafe -Source $sourceRoot -Target $ecosystemTarget -KeepDependencies $true

$externalDirectories = @(
    "C:\Users\User\Documents\Backlogs IMPERIUM",
    "C:\Users\User\Documents\FerramentaImperiumDireto",
    "C:\Users\User\Documents\TOA",
    "C:\Users\User\Documents\toa_ext",
    "C:\Users\User\Documents\toa-system",
    "C:\Users\User\Downloads\CAPTURAS DE AUTOMAÇÃO DE OS",
    "C:\Users\User\Downloads\Extensão de materiais",
    "C:\Users\User\Downloads\FerramentaImperiumDireto-BAIXA-RAPIDA-MATERIAL (1)",
    "C:\Users\User\Downloads\GravadorImperium-1.2.0",
    "C:\Users\User\Downloads\TECHNET_BAIXA_TOA_UNIVERSAL_2.0.2_desinstalado_serial",
    "C:\Users\User\Downloads\TECHNET_BAIXA_TOA_UNIVERSAL_2.0.3_corrigido",
    "C:\Users\User\Downloads\TECHNET_TOA_Unificado_2.4.3_sem_bloco_tel",
    "C:\Users\User\Downloads\TECHNET_TOA_Unificado_v2.4.4_Improdutiva",
    "C:\Users\User\Downloads\toa-technet-bridge-atlas-localizacao",
    "C:\Users\User\Downloads\toa-technet-bridge-atlas-localizacao-BACKUP-ORIGINAL-20260729",
    "C:\Users\User\Downloads\toa-technet-bridge-atlas-localizacao-v2"
)

$externalTarget = Join-Path $destinationRoot "02_PROJETOS_E_FERRAMENTAS_EXTERNAS"
foreach ($directory in $externalDirectories) {
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) { continue }
    $rootLabel = if ($directory -match "\\Downloads\\") { "Downloads" } else { "Documents" }
    $target = Join-Path (Join-Path $externalTarget $rootLabel) (Split-Path $directory -Leaf)
    Copy-TreeSafe -Source $directory -Target $target -KeepDependencies $false
}

$relatedPattern = "(?i)(dominium|technet|ferramenta.?imperium|gravador.?imperium|imperium-|toa[_ .-]|oracle.?field|etadirect|techcap|atividades-(ntl|ftz|pwm|mro|jcr)|toa_inventario|clarobrasil|codex-clipboard|nova grava)"
$allowedExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(".py", ".js", ".mjs", ".css", ".html", ".json", ".md", ".txt", ".csv", ".xlsx", ".xls", ".pptx", ".docx", ".pdf", ".zip", ".rar", ".7z", ".har", ".pcapng", ".etl", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".mp4", ".m4a", ".wav", ".opus", ".cmd", ".ps1", ".dat", ".bin") | ForEach-Object { [void]$allowedExtensions.Add($_) }

$skipRoots = @($sourceRoot, $destinationRoot) + $externalDirectories
$skipPatterns = @(
    "\\node_modules\\",
    "\\__pycache__\\",
    "\\\.git\\objects\\",
    "\\AppData\\Local\\Temp\\dominium-toa-chrome-",
    "\\AppData\\Roaming\\Cursor\\snapshots\\",
    "\\AppData\\Local\\Google\\Chrome\\User Data\\",
    "\\AppData\\Roaming\\Opera Software\\",
    "\\AppData\\Local\\Microsoft\\Edge\\"
)

$allCandidates = [System.Collections.Generic.List[System.IO.FileInfo]]::new()
$seenPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

$driveRoots = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { $_.DeviceID + "\" }
foreach ($driveRoot in $driveRoots) {
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $foundPaths = @(& rg --files -uu $driveRoot 2>$null) | Where-Object { $_ -match $relatedPattern }
    $ErrorActionPreference = $previousErrorPreference
    foreach ($path in $foundPaths) {
        if (Test-IsBelow -Path $path -Roots $skipRoots) { continue }
        $skip = $false
        foreach ($pattern in $skipPatterns) {
            if ($path -match $pattern) { $skip = $true; break }
        }
        if ($skip) {
            $excludedRecords.Add([pscustomobject]@{ path = $path; reason = "cache, dependencia ou snapshot regeneravel" })
            continue
        }
        $file = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
        if ($null -eq $file -or $file.PSIsContainer -or -not $allowedExtensions.Contains($file.Extension)) { continue }
        if ($seenPaths.Add($file.FullName)) { $allCandidates.Add($file) }
    }
}

$attachmentsRoot = "C:\Users\User\.codex\attachments"
if (Test-Path -LiteralPath $attachmentsRoot) {
    $attachmentFiles = Get-ChildItem -LiteralPath $attachmentsRoot -Recurse -Force -File -ErrorAction SilentlyContinue
    foreach ($file in $attachmentFiles) {
        if ($seenPaths.Contains($file.FullName)) { continue }
        $include = $file.Name -match $relatedPattern
        if (-not $include -and $file.Extension -in @(".txt", ".md", ".json")) {
            $include = [bool](Select-String -LiteralPath $file.FullName -Pattern "(?i)(dominium|imperium|oracle field|etadirect|\bTOA\b|technet)" -Quiet -ErrorAction SilentlyContinue)
        }
        if ($include -and $allowedExtensions.Contains($file.Extension) -and $seenPaths.Add($file.FullName)) {
            $allCandidates.Add($file)
        }
    }
}

$standaloneTarget = Join-Path $destinationRoot "03_ARQUIVOS_AVULSOS"
$codexTarget = Join-Path $destinationRoot "04_ANEXOS_CODEX"
foreach ($file in $allCandidates) {
    try {
        if ($file.FullName.StartsWith($attachmentsRoot + "\", [System.StringComparison]::OrdinalIgnoreCase) -or
            $file.Name -match "(?i)^codex-clipboard-") {
            Copy-StandaloneFile -File $file -BaseTarget $codexTarget -Kind "codex_attachment"
        } else {
            Copy-StandaloneFile -File $file -BaseTarget $standaloneTarget
        }
    } catch {
        $errorRecords.Add([pscustomobject]@{
            source = $file.FullName
            destination = ""
            error = $_.Exception.Message
        })
    }
}

$privateFiles = Get-ChildItem -LiteralPath $ecosystemTarget -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -in @("credentials.dat", "imperium_http_credentials.dat", "toa_credentials.dat")
}

$readme = @"
DOMINIUM TECHNET - CONSOLIDACAO LOCAL
=====================================

Criado em: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
Destino: $destinationRoot

Esta pasta consolida o ecossistema principal, versoes anteriores, ferramentas TOA/Imperium,
capturas, importacoes CSV, inventarios, documentos, apresentacoes, imagens e anexos encontrados.

ESTRUTURA
00_LEIA_PRIMEIRO                 Avisos e orientacoes.
01_ECOSSISTEMA_PRINCIPAL         Copia completa da pasta Consulte Sistemas\Imperium.
02_PROJETOS_E_FERRAMENTAS_EXTERNAS Versoes e ferramentas encontradas em Documents/Downloads.
03_ARQUIVOS_AVULSOS              CSV, inventarios, capturas, midias, pacotes e documentos.
04_ANEXOS_CODEX                  Anexos e imagens relacionados ao projeto.
99_INVENTARIO                    Manifestos de origem, exclusoes, erros e arquivos consolidados.

IMPORTANTE
- Os arquivos originais nao foram movidos nem apagados.
- Arquivos .dat de credenciais continuam protegidos pelo DPAPI do Windows.
- NAO envie a pasta inteira para GitHub, Hostinger ou terceiros.
- Para publicacao, use um pacote separado sem credenciais, logs, capturas e dados operacionais.
- Caches de navegador, snapshots internos, __pycache__ e node_modules de copias antigas foram excluidos.
  O node_modules do projeto/ecossistema principal foi preservado na copia completa.
"@
$readmePath = Join-Path $destinationRoot "00_LEIA_PRIMEIRO\README_CONSOLIDACAO.txt"
[System.IO.File]::WriteAllText($readmePath, $readme, [System.Text.UTF8Encoding]::new($false))

$privateNotice = @"
ATENCAO: CREDENCIAIS PRIVADAS
=============================

Foram localizados $($privateFiles.Count) arquivos de credenciais criptografadas no ecossistema copiado.
Eles podem incluir credentials.dat, imperium_http_credentials.dat e toa_credentials.dat.

Nao publique esses arquivos. A protecao DPAPI depende do usuario/perfil do Windows que os criou.
Para hospedagem, crie uma entrega separada e use variaveis de ambiente/gerenciador de segredos.
"@
$privateNoticePath = Join-Path $destinationRoot "00_LEIA_PRIMEIRO\NAO_PUBLICAR_CREDENCIAIS.txt"
[System.IO.File]::WriteAllText($privateNoticePath, $privateNotice, [System.Text.UTF8Encoding]::new($false))

$inventoryRoot = Join-Path $destinationRoot "99_INVENTARIO"
$copyRecords | Export-Csv -LiteralPath (Join-Path $inventoryRoot "origens_copiadas.csv") -NoTypeInformation -Encoding UTF8
$excludedRecords | Export-Csv -LiteralPath (Join-Path $inventoryRoot "itens_excluidos.csv") -NoTypeInformation -Encoding UTF8
$errorRecords | Export-Csv -LiteralPath (Join-Path $inventoryRoot "erros_de_copia.csv") -NoTypeInformation -Encoding UTF8

$finalFiles = Get-ChildItem -LiteralPath $destinationRoot -Recurse -Force -File -ErrorAction SilentlyContinue
$finalInventory = foreach ($file in $finalFiles) {
    $relative = $file.FullName.Substring($destinationRoot.Length).TrimStart("\")
    [pscustomobject]@{
        relative_path = $relative
        size_bytes = $file.Length
        modified = $file.LastWriteTime.ToString("o")
    }
}
$finalInventory | Export-Csv -LiteralPath (Join-Path $inventoryRoot "inventario_arquivos.csv") -NoTypeInformation -Encoding UTF8

$summary = [pscustomobject]@{
    created_at = (Get-Date).ToString("o")
    destination = $destinationRoot
    files = $finalFiles.Count
    size_bytes = ($finalFiles | Measure-Object Length -Sum).Sum
    size_gb = [math]::Round((($finalFiles | Measure-Object Length -Sum).Sum / 1GB), 3)
    copied_sources = $copyRecords.Count
    excluded_cache_items = $excludedRecords.Count
    errors = $errorRecords.Count
    private_credential_files = $privateFiles.Count
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $inventoryRoot "resumo.json") -Encoding UTF8
$summary | ConvertTo-Json -Depth 4
