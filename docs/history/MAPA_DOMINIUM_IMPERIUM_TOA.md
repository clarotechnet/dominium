# Mapa de código do DOMINIUM primário

Este arquivo identifica a responsabilidade dos scripts próprios do DOMINIUM. Os
arquivos de perfil do Chrome, bibliotecas de terceiros, builds, logs, relatórios,
temporários e testes não fazem parte deste inventário operacional.

## Padrão aplicado nos scripts

Todo script operacional começa com um cabeçalho contendo estas seções:

```text
IMPERIUM
TOA
DOMINIUM COMPARTILHADO
```

O cabeçalho informa se o arquivo atua em cada domínio. A ordem executável não foi
alterada: mover funções ou inicializações apenas para agrupá-las visualmente poderia
quebrar imports, registro de rotas, inicialização do servidor ou listeners do navegador.

## IMPERIUM

Arquivos de DataSnap/MIDAS, baixa de OS, estoque, materiais, seriais, criação de OS,
transferência e auditoria dos protocolos do Imperium:

- `ABRIR LEITOR DE FLUXOS.cmd`
- `cancel_all_open.py`
- `close_report.py`
- `datasnap_client.py`
- `flow_reader/__init__.py`
- `flow_reader/analyzer.py`
- `flow_reader/server.py`
- `flow_reader/static/app.js`
- `imperium_api.py`
- `imperium_http_api.py`
- `imperium_http_plan.py`
- `installer_change.py`
- `manual_materials.py`
- `manual_orders.py`
- `native_orders.py`
- `official_close.py`
- `official_close_code_catalog.py`
- `official_close_code_reconciliation.py`
- `official_close_dry_run.py`
- `official_close_sender.py`
- `official_material_catalog.py`
- `official_stock_audit.py`
- `official_stock_blocker_review.py`
- `official_stock_remediation_plan.py`
- `serialized_transfer.py`
- `stock_inventory.py`
- `stock_pdf.py`

## TOA

Arquivos de sessão, navegador, captura, atividades, inventário, datalake, monitor,
extensão de descoberta e exportação Oracle:

- `Conectar TOA.cmd`
- `Configurar TOA.cmd`
- `configurar_toa_credenciais.py`
- `static/operations-monitor.js`
- `technician_directory.py`
- `toa_automation.py`
- `toa_browser.py`
- `toa_capture.py`
- `toa_capture_panel.py`
- `toa_connector.py`
- `toa_context.py`
- `toa_contract_registry.py`
- `toa_datalake_store.py`
- `toa_discovery_browser.py`
- `toa_discovery_check.py`
- `toa_inventory.py`
- `toa_live.py`
- `toa_local_collector.py`
- `toa-auto-export/src/background/service-worker.js`
- `toa-auto-export/src/content/content.js`
- `toa-auto-export/src/content/page-bridge.js`
- `toa-auto-export/src/export/download-manager.js`
- `toa-auto-export/src/export/export-manager.js`
- `toa-auto-export/src/export/live-snapshot-store.js`
- `toa-auto-export/src/export/oracle-api.js`
- `toa-auto-export/src/popup/popup.js`
- `toa-auto-export/src/utils/logger.js`
- `toa-auto-export/src/utils/storage.js`
- `toa-discovery/content.js`
- `toa-discovery/core.js`
- `toa-discovery/exporter.js`
- `toa-discovery/page-hook.js`
- `toa-discovery/popup.js`
- `toa-discovery/service-worker.js`

## MISTO: TOA + IMPERIUM

Estes arquivos são pontes. Uma alteração pode afetar leitura do TOA e escrita,
validação ou consulta do Imperium ao mesmo tempo:

- `app.py` — servidor, endpoints e orquestração geral.
- `static/app.js` — interface operacional completa.
- `bulk_orders.py` — entrada preparada no formato TOA para criação no Imperium.
- `disconnect_automation.py` — fila baseada no desfecho TOA e execução operacional.
- `material_matching.py` — correspondência entre material observado e catálogo.
- `official_candidate_locator.py` — cruza evidências TOA e estado Imperium.
- `official_close_toa_dry_run.py` — transforma captura TOA em plano de baixa.
- `official_material_resolver.py` — resolve material TOA contra catálogo operacional.
- `operation_scope.py` — delimita cidade, base, perfil e autorização operacional.
- `operational_store.py` — histórico consolidado das duas fontes.
- `operations_intelligence.py` — relatórios e auditorias cruzadas.
- `toa_import.py` — CSV/atividade TOA convertido em importação DataSnap do Imperium.

## DOMINIUM COMPARTILHADO

Infraestrutura sem regra de negócio exclusiva de uma das integrações:

- `Abrir Painel.cmd`
- `api_security.py`
- `consolidate_dominium.ps1`
- `edge_voice.py`
- `import_technicians_xlsx.py`
- `PREPARAR_ARQUIVOS_PARA_SKYNET.ps1`
- `PREPARAR_ARQUIVOS_PARA_SKYNET_CORRIGIDO.ps1`
- `RODAR_AGENTE_MADRUGADA_CORRIGIDO.ps1`
- `RODAR_AGENTE_MADRUGADA_V2.ps1`
- `static/motion-ui.js`

## Fluxos principais

```text
TOA -> captura/datalake -> app.py -> monitor/SQLite
TOA -> CSV/importação -> toa_import.py -> DataSnap -> IMPERIUM
TOA -> atividade/inventário -> validação -> baixa/estoque -> IMPERIUM
IMPERIUM -> resultado da baixa -> relatório/SQLite -> painel DOMINIUM
```

## Regra para código novo

1. Código que somente consulta ou automatiza Oracle Field Service fica em `TOA`.
2. Código que fala DataSnap/MIDAS, movimenta estoque ou baixa OS fica em `IMPERIUM`.
3. Conversões, cruzamentos e orquestrações entre fontes ficam em `MISTO`.
4. Segurança, visual, voz, inicialização e empacotamento ficam em `COMPARTILHADO`.
5. Um arquivo misto deve manter testes dos dois lados antes de ser alterado.
