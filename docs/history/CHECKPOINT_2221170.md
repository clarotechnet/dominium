# Checkpoint - contrato 2221170

Gerado em: 2026-07-22
Clone: `C:\Users\Public\Documents\Consulte Sistemas\Imperium\FerramentaImperiumDireto-OLLAMA`

## Etapa atual

Auditoria somente leitura encerrada. A captura disponivel foi preservada,
o coletor foi corrigido para separar quantidade usada de saldo disponivel e
`INSPECAO_2221170.json` foi regenerado. O caso permanece bloqueado, sem
autorizacao e sem capacidade de envio acionada.

## Fatos comprovados

- Imperium, em 2026-07-22:
  - OS `2646508672`, `MUDANCA DE PACOTE`, status `EM CAMPO`, capacidade
    `material_capable`;
  - OS `2646508683`, `INSTALACAO DE CABO GPON`, status `EM CAMPO`, capacidade
    `close_only`;
  - ambas apontam para `installer_id=328898`, nome `DENIS NUNES`.
- TOA:
  - contrato `2221170`, AID `194300555`;
  - slots `193/194/195 = 2646508672/E/409`;
  - slots `196/197/198 = 2646508683/E/409`;
  - tecnico `provider_id=63661`, `external_id=Z637677`, nome
    `DENNIS NUNES DE OLIVEIRA`;
  - rota observada no inventario continha `aid=194300555`.
- Equipamentos:
  - entrada `2CD8AE5D436F`, ponto `335=25471541`;
  - saida `B4F26757B818`, ponto `335=25471541`;
  - o codigo TOA `3222` e codigo de tipo, nao prova o
    `codigoequipamento` concreto exigido pelo Imperium.
- Materiais:
  - foram identificados oito codigos: `22061736`, `22069613`, `22025072`,
    `22056332`, `22056343`, `22056341`, `22056344` e `22057659`;
  - `Inventory.quantity` e `_identifier_structure.quantity.text` representam
    saldo disponivel (`39, 2, 1, 1, 1, 1, 1, 3`), nao quantidade usada;
  - a quantidade usada `1` de cada item foi confirmada pelo operador, mas nao
    existe como campo da resposta bruta preservada;
  - a propriedade `335` nao chegou nos oito registros de material;
  - `RequiredInventory` e `MissingInventoryProperties` estavam vazios;
  - `FormData` e `ServiceRequest` nao forneceram ponto ou quantidade por item.
- Tecnico:
  - `config/technicians.json` associa `Z637677` a
    `DENNIS NUNES DE OLIVEIRA`;
  - a leitura da lista de instaladores do Imperium associa o ID interno
    `328898` a `DENIS NUNES`;
  - o Imperium nao expos login/external_id nessa leitura, portanto a
    equivalencia entre os sistemas nao foi presumida.
- Serial removido:
  - nao apareceu no detalhe atual das duas OS;
  - nao foi localizado pela leitura de estoque atual ja implementada;
  - nenhum codigo concreto foi inferido por nome, tipo ou serial.
- Seguranca:
  - nenhum POST de baixa;
  - nenhum endpoint de baixa chamado;
  - nenhum ApplyUpdates ou DataSnap de escrita;
  - nenhuma movimentacao de estoque;
  - nenhuma alteracao de OS;
  - nenhuma autorizacao gerada;
  - nenhum commit criado.
- Testes offline aprovados:
  - coletor de quantidades: `3/3`;
  - `test_official_close_toa_dry_run`: `26/26`;
  - `test_official_close_dry_run`: `22/22`;
  - `py_compile`: aprovado;
  - `git diff --check` dos arquivos desta etapa: aprovado.

## Blockers restantes

1. `raw_capture_full_identifier_structure_not_persisted`
2. `material_point_335_missing:8_items`
3. `material_used_quantity_not_present_in_raw_capture:8_items`
4. `removed_equipment_code_not_found:B4F26757B818`
5. `imperium_installer_external_login_not_exposed:328898`
6. `payload_preview_invalid:removed_codigoequipamento_missing`

## Arquivos modificados nesta etapa

- `references/techcap-v5.6/TECHCAP_TOA_V5_6_FLUXO_OS_PARA_OS.txt`
  - separa `used_quantity` de `available_stock` e nunca infere uso pelo saldo.
- `references/techcap-v5.6/test_inventory_quantities_v56.js`
  - cobre saldo sem uso explicito, uso explicito decimal e fallback do saldo.
- `INSPECAO_2221170.json`
  - relatorio somente leitura v3, payloads apenas para preview e seis blockers.
- `logs/toa-captures/raw/20260722/toa-raw-sanitized-2221170-194300555-193840.json`
  - evidencia sanitizada; sem cookies, token, senha ou cabecalhos de autenticacao.
- `CHECKPOINT_2221170.md`
  - este checkpoint.
- `CHECKPOINT_git_status_short.txt`
  - saida integral do `git status --short`.

Ha outras alteracoes anteriores no worktree, inclusive codigo de dry-run,
material matching, estado de automacao e muitos arquivos gerados pelo perfil
do Chrome. Nenhuma delas foi revertida ou limpa.

## Comandos ainda em execucao

- Painel DOMINIUM:
  - PID `7052`;
  - `python.exe -u app.py --port 8765 --open`;
  - escutando em `127.0.0.1:8765`.
- Chrome TOA:
  - processo principal PID `12816`;
  - `--remote-debugging-port=9339`;
  - tela de login aberta e credenciais preenchidas.
- Nao ha shell, teste, consulta TOA ou consulta DataSnap em execucao.

## Git status --short

A saida integral esta em `CHECKPOINT_git_status_short.txt`. Ela possui mais de
300 linhas, em grande parte cache, IndexedDB, Service Worker e outros arquivos
do perfil `config/toa_chrome_profile`. Os arquivos relevantes desta etapa sao:

```text
 M references/techcap-v5.6/TECHCAP_TOA_V5_6_FLUXO_OS_PARA_OS.txt
?? INSPECAO_2221170.json
?? references/techcap-v5.6/test_inventory_quantities_v56.js
?? CHECKPOINT_2221170.md
?? CHECKPOINT_git_status_short.txt
```

O artefato em `logs/toa-captures/raw/...` existe, mas a arvore `logs` e
ignorada pelo Git.

## Proximo passo exato para retomada

1. Ler este checkpoint e `INSPECAO_2221170.json`.
2. Nao repetir enumeracao ou adaptacao de providers DataSnap.
3. Obter, por uma fonte de leitura ja validada, somente as tres provas ainda
   necessarias para um payload confiavel:
   - ponto `335` de cada uma das oito miscelaneas;
   - quantidade usada emitida por uma fonte de maquina, separada do saldo;
   - `codigoequipamento` concreto do serial removido `B4F26757B818`.
4. Obter a correspondencia oficial entre `installer_id=328898` e
   `external_id=Z637677`, sem casar apenas pelo nome.
5. Regenerar a inspecao offline e remover blockers somente quando cada prova
   estiver presente.
6. Mesmo com zero blockers, continuar sem POST ate nova autorizacao humana
   explicita e separada.
