# Checkpoint - City Scope / OS Refresh

Salvo em: 2026-07-23 22:04:20 -03:00

## Estado

- Projeto: `IMPERIUM_OLLAMA`
- Repositorio: `C:\Users\Public\Documents\Consulte Sistemas\Imperium\FerramentaImperiumDireto-OLLAMA`
- Branch: `fix/city-scope-os-refresh`
- HEAD inicial e atual: `e7d0225 feat: add official material and stock audit tools`
- Nenhum commit foi criado nesta etapa.
- Nenhum processo, teste ou comando permanece em execucao.
- Nenhuma rede, POST, baixa, movimentacao ou escrita DataSnap foi executada.

## Objetivo concluido

Foi implementada offline a correcao estrutural para impedir contaminacao entre:

- projeto;
- cidade;
- profile_key;
- origem e lote de importacao;
- contrato;
- activity_id;
- snapshot aprovado;
- codigo de baixa planejado e codigo remoto atual.

Tambem foi implementado o bloqueio direto contra uma tentativa de aplicar
`106` em uma OS que ja possui `430`.

## Arquivos desta etapa

Modificados:

- `Abrir Painel.cmd`
- `app.py`
- `imperium_api.py`
- `static/app.js`
- `test_imperium_api.py`
- `toa_context.py`
- `toa_import.py`

Novos:

- `.imperium-project.json`
- `operation_scope.py`
- `test_operation_scope.py`
- `test_city_scope_integration.py`
- `CITY_SCOPE_INCIDENT_ANALYSIS.md`
- `CHECKPOINT_CITY_SCOPE_RESTART.md`

## Validacao concluida

- `python -m unittest discover`: 391 testes, todos aprovados.
- Testes de escopo e integracao: 41 aprovados.
- `python -m py_compile` dos arquivos alterados: aprovado.
- `node --check static/app.js`: aprovado.
- `git diff --check` dos arquivos versionados desta etapa: aprovado.
- Verificacao de whitespace dos arquivos novos: aprovada.
- `python -m operation_scope --check-project`: aprovado.

## Fatos principais

- Mapeamento imutavel:
  - `NTL -> NATAL -> natal`
  - `PWM -> NATAL -> natal`
  - `MRO -> MOSSORO -> mossoro`
  - `JCR -> RECIFE -> recife`
  - `FTZ -> FORTALEZA -> fortaleza`
- Identidade operacional:
  `(project_id, profile_key, city, contract, activity_id)`.
- Arquivo importado preserva origem, cidade, perfil, nome, SHA-256 e batch_id.
- Prefixo desconhecido bloqueia.
- Sem activity_id bloqueia com `missing_activity_id`.
- Resposta ou cache de outro perfil/cidade bloqueia.
- Preflight exige snapshot e state_hash inalterados.
- OS ja fechada bloqueia antes de preparar payload ou movimentacao.
- `430 -> 106` gera:
  - `already_closed`
  - `already_closed_with_different_code:430`
  - `remote_state_changed`
  - `operation_blocked`
- Divergencia Imperium/Dominium exige reconciliacao manual.

## Worktree

O worktree ja possuia muitas alteracoes anteriores e arquivos gerados pelo
Chrome, catalogos, relatorios e estados locais. Eles nao foram revertidos,
limpos, adicionados ao stage ou alterados por esta etapa.

Ao retomar, nao executar limpeza global, reset, checkout ou stage geral.
Trabalhar apenas nos arquivos listados neste checkpoint.

## Retomada obrigatoria

Antes de continuar:

```powershell
Set-Location "C:\Users\Public\Documents\Consulte Sistemas\Imperium\FerramentaImperiumDireto-OLLAMA"
git rev-parse --show-toplevel
git branch --show-current
git log -1 --oneline
Get-Location
python -m operation_scope --check-project
```

Valores esperados:

- raiz termina em `FerramentaImperiumDireto-OLLAMA`;
- branch `fix/city-scope-os-refresh`;
- HEAD `e7d0225`;
- project_id `IMPERIUM_OLLAMA`.

## Proximo passo

O proximo passo permitido e apenas revisar este checkpoint e o relatorio
`CITY_SCOPE_INCIDENT_ANALYSIS.md`.

A validacao controlada descrita no relatorio ainda nao foi executada. Ela deve
ser iniciada somente mediante nova autorizacao explicita, sem misturar com
arquivos antigos, perfis Chrome ou outra copia do projeto.
