# Analise do incidente de escopo por cidade

## Repositorio validado

- Raiz: `C:\Users\Public\Documents\Consulte Sistemas\Imperium\FerramentaImperiumDireto-OLLAMA`
- Branch: `fix/city-scope-os-refresh`
- HEAD inicial: `e7d0225 feat: add official material and stock audit tools`
- Identidade permanente: `IMPERIUM_OLLAMA`

O arquivo `.imperium-project.json` e validado antes do carregamento da
aplicacao (`app.py:62`) e pelo launcher (`Abrir Painel.cmd:4`). A validacao
recusa uma raiz diferente da raiz OLLAMA e registra raiz, branch e build no
inicio do painel (`app.py:3659`).

## Causa raiz comprovada

O incidente nao tinha uma causa unica de interface. Era a combinacao de
quatro permissoes estruturais presentes no codigo-base `e7d0225`:

1. `app.py:210-250` escolhia o perfil pelo destino selecionado no request. O
   prefixo do arquivo era apenas comparado quando existia e o lote nao
   carregava cidade, perfil, hash ou identidade imutaveis.
2. `toa_context.py:122-152` indexava o contexto globalmente apenas pelo numero
   da OS. Uma entrada posterior com o mesmo numero substituia a anterior; nem
   contrato nem `activity_id` faziam parte da chave.
3. `app.py:299-325` aceitava `exact_matches or contract_matches`. Quando o
   numero da OS nao coincidia, qualquer linha do mesmo contrato podia ser
   reutilizada. Isso permitia uma captura de outra atividade alimentar a
   selecao atual.
4. `static/app.js:1`, `static/app.js:1385-1415` e
   `static/app.js:3200/3755/4178/4190` mantinham um estado unico no navegador.
   A troca de perfil nao invalidava rascunhos, importacao, captura TOA ou
   selecao produtiva, e os rascunhos eram indexados apenas por `id_os`.

Havia ainda um defeito independente que explica diretamente o caso
`430 -> 106`: `imperium_api.py:3714-3762` verificava somente se o codigo
solicitado ja estava aplicado. Uma OS contendo `430` nao era reconhecida como
fechada quando a solicitacao posterior pedia `106`; o fluxo seguia para
montagem do delta e `AS_ApplyUpdates`.

Tambem existem launchers em outros diretorios do Imperium. No HEAD inicial, o
launcher OLLAMA executava `app.py` sem validar identidade, portanto a versao
errada podia ser iniciada sem um sinal permanente de projeto.

## Fluxo antigo vulneravel

1. A interface mantinha o ultimo perfil e rascunhos em um objeto global.
2. O destino selecionado definia o profile da importacao.
3. O contexto TOA mais recente sobrescrevia a entrada pelo numero da OS.
4. A pesquisa ao vivo tentava numero da OS e depois caia para contrato.
5. A baixa recebia uma linha escolhida por `id_os`, sem `activity_id`, lote ou
   hash da fonte aprovados.
6. O DataSnap verificava apenas o mesmo codigo pretendido.
7. Uma OS ja fechada com outro codigo ainda podia chegar ao builder de
   equipamentos/materiais e ao `ApplyUpdates`.

Essa cadeia explica tanto a contaminacao entre Natal/Recife quanto a
inconsistencia entre codigo final e movimentacoes.

## Limites imutaveis implementados

`operation_scope.py` concentra estruturas congeladas e tipadas:

- `ProjectIdentity` (`operation_scope.py:153`)
- `ImportScope` (`operation_scope.py:191`)
- `OSIdentity` (`operation_scope.py:306`)
- `OSSnapshot` (`operation_scope.py:361`)
- `PlannedClose` (`operation_scope.py:446`)
- `PreflightResult` (`operation_scope.py:456`)
- `ReconciliationIssue` (`operation_scope.py:465`)
- `ExecutionAudit` (`operation_scope.py:472`)

Mapeamento fechado (`operation_scope.py:21`):

| Origem | Cidade | profile_key |
| --- | --- | --- |
| NTL | NATAL | natal |
| PWM | NATAL | natal |
| MRO | MOSSORO | mossoro |
| JCR | RECIFE | recife |
| FTZ | FORTALEZA | fortaleza |

Prefixos desconhecidos bloqueiam. `ImportScope` conserva
`import_origin`, `expected_city`, `expected_profile_key`, `source_file`,
`source_hash` e `batch_id`. O lote e indexado por
`(origin, profile, city, batch_id)`.

A OS e indexada por
`(project_id, profile_key, city, contract, activity_id)`. Ausencia de
`activity_id` produz `missing_activity_id`.

## Pesquisa e cache

- `toa_import.py:71/116/149` preserva `activity_id` e `ImportScope`.
- `toa_context.py:34/159/176` mantem entradas separadas, exige rota + numero
  da OS + contrato e valida novamente o hash do arquivo antes da baixa.
- `app.py:329` invalida snapshots anteriores do mesmo contrato dentro do
  profile/cidade e cria snapshots imutaveis com hash deterministico.
- `app.py:459` casa captura ao vivo somente por contrato + `activity_id` +
  numero da OS e deriva o lote apenas da atividade exata. Nao existe fallback
  por contrato.
- Cada `ProfileRuntime` possui seu proprio `OperationCoordinator`
  (`app.py:93/121`).
- `static/app.js:1386/1458` invalida todo estado operacional na troca de
  perfil e rejeita respostas assincronas de uma epoca anterior.
- Rascunhos usam projeto + perfil + cidade + contrato + atividade + numero da
  OS (`static/app.js:3218`).

## Preflight e bloqueio de escrita

O preflight logico (`operation_scope.py:509`) compara identidade, lote, hash
aprovado, hash atual, status e codigo atual. Alteracao produz bloqueio e exige
nova revisao. `guard_before_write` (`operation_scope.py:840`) prova em testes
que nenhum writer e chamado quando o resultado nao e permitido.

O endpoint existente valida identidade, lote registrado no servidor, arquivo
original e snapshot aprovado antes de montar materiais ou payload
(`app.py:524` e `app.py:3165`).

No caminho DataSnap, a leitura de detalhe imediatamente anterior a qualquer
builder agora procura todos os codigos conhecidos
(`imperium_api.py:3725-3802`). Se encontrar `430` durante uma tentativa de
`106`, levanta exatamente:

- `already_closed`
- `already_closed_with_different_code:430`
- `remote_state_changed`
- `operation_blocked`

O lookup do codigo, o builder de materiais/equipamentos, o handle de escrita
e o blob de `ApplyUpdates` nao sao chamados.

## Conflito entre sistemas e reconciliacao

`evaluate_preflight` bloqueia quando o snapshot Dominium indica aberto mas a
leitura atual Imperium indica fechado. O resultado inclui
`cross_system_status_conflict`, o codigo divergente e `operation_blocked`.

`reconcile_execution` (`operation_scope.py:585`) detecta:

- movimento pertencente a outra identidade;
- codigo do movimento diferente do codigo planejado;
- movimento sem baixa final;
- codigo final diferente do movimento;
- reexecucao de identidade finalizada.

Nao existe compensacao destrutiva automatica. Qualquer divergencia gera
`ReconciliationIssue` e permanece em reconciliacao manual.

## Estados bloqueantes

Foram cobertos:

`wrong_project_root`, `wrong_project_identity`, `unknown_import_origin`,
`city_scope_mismatch`, `profile_scope_mismatch`,
`contract_identity_mismatch`, `activity_identity_mismatch`,
`missing_activity_id`, `already_closed`,
`already_closed_with_different_code`, `remote_state_changed`,
`cross_system_status_conflict`, `stale_snapshot`,
`material_close_code_inconsistency`, `shared_state_contamination`,
`source_file_changed` e `payload_scope_violation`.

## Testes

- `test_operation_scope.py`: 30 cenarios obrigatorios mais testes de hash,
  lote forjado, escopo forjado e associacao snapshot/lote.
- `test_city_scope_integration.py`: integracao offline de CSV, contexto,
  pesquisa ao vivo e validacao anterior a baixa.
- `test_imperium_api.py`: `430 -> 106` e multiplos codigos remotos, com fakes
  que falham se lookup, builder, handle ou escrita forem chamados.

Todos usam mocks, fakes, arquivos temporarios ou capturas locais. Nenhuma
consulta, baixa, movimentacao, POST ou escrita DataSnap foi executada durante
esta etapa.

## Validacao controlada futura

Ainda sem executar:

1. Abrir somente o launcher OLLAMA e conferir `project_id`, raiz, branch e
   build no log.
2. Importar um CSV pequeno de uma unica origem e confirmar escopo/hash/lote na
   previa.
3. Consultar uma OS controlada e revisar o snapshot e o `state_hash`.
4. Alterar remotamente uma copia de teste entre aprovacao e preflight e
   confirmar bloqueio.
5. Testar uma OS ja fechada com `430` solicitando `106` e confirmar zero
   chamadas de escrita.
6. Somente depois dessa evidencia, autorizar separadamente uma unica operacao
   controlada. Esta etapa nao concede essa autorizacao.
