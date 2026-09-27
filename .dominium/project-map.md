# DOMINIUM project map

Generated index for agent navigation. Source code remains authoritative.

- Generated: 2026-09-27T04:05:41+00:00
- Source fingerprint: `e2073c0f18b97cb2`
- Indexed files: 234
- Indexed symbols: 2635
- API path references: 95

## Navigation rule

Use this map to choose files. Then read the real implementation and narrow tests.
Do not recursively scan the repository when this map already identifies candidates.
For operational-language routing, read docs/agent/TASK_ROUTER.md.

## orchestration

- `app.py` (130 symbols, 74 API paths, 39 DataSnap methods) - =============================================================================
- `disconnect_automation.py` (26 symbols) - =============================================================================
- `operation_scope.py` (55 symbols) - =============================================================================
- `operational_store.py` (23 symbols) - =============================================================================
- `operations_intelligence.py` (13 symbols) - =============================================================================

## toa

- `Conectar TOA.cmd` - @echo off
- `Configurar TOA.cmd` - @echo off
- `Configurar_Coletor_TOA.cmd` - @echo off
- `configurar_toa_credenciais.py` (1 symbols) - =============================================================================
- `configure_toa_cloud_bridge.py` (1 symbols) - Grava a credencial primaria da ponte com protecao DPAPI do Windows.
- `integrations/n8n/DOMINIUM_Ponte_Datalake_TOA.json` - {
- `integrations/toa_cloud_bridge/extension-central-2.6.3/test-toa-inventory-core.js` (1 symbols) - 'use strict';
- `integrations/toa_cloud_bridge/extension-central-2.6.3/test-toa-route-tree.cjs` (1 symbols, 1 DataSnap methods) - const assert = require('node:assert/strict');
- `integrations/toa_cloud_bridge/extension-central-2.6.3/toa-auto-export.js` (22 symbols, 1 DataSnap methods) - (function installTOAAutoExport(root) {
- `integrations/toa_cloud_bridge/extension-central-2.6.3/toa-inventory-core.js` (16 symbols, 1 DataSnap methods) - (function (root, factory) {
- `official_close_toa_dry_run.py` (29 symbols, 3 DataSnap methods) - Read-only bridge from a TECHCAP capture to the official close dry-run.
- `patch_remote_toa.py` (2 API paths, 5 DataSnap methods) - from pathlib import Path
- `show_toa_cloud_collector_setup.py` (1 symbols) - Mostra a URL e a chave do coletor protegidas pelo DPAPI deste Windows.
- `toa-discovery/content.js` (1 symbols) - =============================================================================
- `toa-discovery/core.js` (25 symbols) - =============================================================================
- `toa-discovery/exporter.js` (20 symbols, 1 DataSnap methods) - =============================================================================
- `toa-discovery/manifest.json` - {
- `toa-discovery/page-hook.js` (31 symbols) - =============================================================================
- `toa-discovery/popup.css` - :root {
- `toa-discovery/popup.html` - <!doctype html>
- `toa-discovery/popup.js` (5 symbols, 3 DataSnap methods) - =============================================================================
- `toa-discovery/README.md` (1 DataSnap methods) - TOA Discovery
- `toa-discovery/service-worker.js` (16 symbols) - =============================================================================
- `toa-discovery/service-worker.test.js` - "use strict";
- `toa-discovery/test.js` - "use strict";
- `toa_agenda.py` (11 symbols) - =============================================================================
- `toa_automation.py` (22 symbols) - =============================================================================
- `toa_bridge_server.py` (21 symbols, 1 DataSnap methods) - Bridge local escutando na porta 8787.
- `toa_browser.py` (10 symbols) - =============================================================================
- `toa_capture.py` (29 symbols, 1 DataSnap methods) - Read-only validator for TECHCAP V5.6 capture exports.
- `toa_capture_panel.py` (10 symbols, 2 DataSnap methods) - =============================================================================
- `toa_cloud_client.py` (9 symbols) - Cliente da fila privada Cloudflare usada pelo DOMINIUM primario.
- `toa_connector.py` (25 symbols, 2 DataSnap methods) - API local, sanitizada e somente leitura para dados operacionais do TOA.
- `toa_context.py` (8 symbols) - =============================================================================
- `toa_contract_registry.py` (13 symbols) - =============================================================================
- `toa_datalake_store.py` (19 symbols) - =============================================================================
- `toa_discovery_browser.py` (2 symbols) - =============================================================================
- `toa_discovery_check.py` (1 symbols) - =============================================================================
- `toa_import.py` (23 symbols) - =============================================================================
- `toa_inventory.py` (11 symbols) - =============================================================================
- `toa_live.py` (34 symbols, 8 DataSnap methods) - =============================================================================
- `toa_local_collector.py` (13 symbols) - =============================================================================
- `toa_secondary_direct_lookup.mjs` - const contract = String(process.argv[2] || '').replace(/\D/g, '');
- `toa_secondary_session.py` (14 symbols) - import datetime as dt
- `verify_toa_cloud_bridge.py` (3 symbols) - Teste online seguro da ponte Cloudflare/D1 sem expor as chaves.

## imperium

- `.imperium-project.json` - {
- `imperium_api.py` (134 symbols, 3 DataSnap methods) - =============================================================================
- `imperium_http_api.py` (37 symbols, 2 DataSnap methods) - =============================================================================
- `imperium_http_plan.py` (9 symbols) - =============================================================================
- `installer_change.py` (5 symbols) - =============================================================================
- `manual_orders.py` (7 symbols, 1 DataSnap methods) - =============================================================================
- `native_orders.py` (16 symbols) - =============================================================================
- `serialized_transfer.py` (7 symbols) - =============================================================================
- `stock_inventory.py` (21 symbols) - =============================================================================

## frontend

- `static/index.html` (1 API paths) - <!doctype html>
- `static/LUCIDE-LICENSE.txt` - ISC License
- `static/lucide.min.js` (1 symbols) - * @license lucide v1.8.0 - ISC
- `static/motion-ui.js` (10 symbols) - =============================================================================
- `static/operations-monitor.js` (34 symbols) - =============================================================================
- `static/styles.css` - :root {
- `static/theme-init.js` - try {

## shared core

- `ABRIR LEITOR DE FLUXOS.cmd` - @echo off
- `Abrir Painel.cmd` - @echo off
- `AGENTS.md` (1 DataSnap methods) - DOMINIUM agent guide
- `api_security.py` (9 symbols, 6 API paths) - Controles centrais de seguranca para as integracoes do DOMINIUM.
- `auth_store.py` (28 symbols) - Autenticacao local do DOMINIUM.
- `auth_store_postgres.py` (18 symbols) - Backend PostgreSQL para identidade, sessao e auditoria do DOMINIUM.
- `bulk_orders.py` (2 symbols) - =============================================================================
- `cancel_all_open.py` (3 symbols) - =============================================================================
- `CLAUDE.md` (1 DataSnap methods) - DOMINIUM / Claude Code
- `close_report.py` (15 symbols) - =============================================================================
- `close_report_excel.py` (3 symbols) - =============================================================================
- `consolidate_dominium.ps1` (4 DataSnap methods) - =============================================================================
- `datasnap_client.py` (23 symbols) - =============================================================================
- `edge_voice.py` (8 symbols) - =============================================================================
- `flow_reader/__init__.py` - Read-only Imperium/DataSnap capture analyzer.
- `flow_reader/analyzer.py` (28 symbols) - =============================================================================
- `flow_reader/LEIA-ME.txt` - DOMINIUM FLOWSCOPE 1.0 - LEITOR DE FLUXOS IMPERIUM
- `flow_reader/server.py` (11 symbols, 2 API paths) - =============================================================================
- `flow_reader/static/app.js` (30 symbols, 1 API paths) - =============================================================================
- `flow_reader/static/index.html` - <!doctype html>
- `flow_reader/static/styles.css` - :root {
- `import_protocol_templates.json` (1 DataSnap methods) - {"version":1,"server_method":"TDtmOrdemServico.AS_GetRecords","captured_controller_id":313101,"chunk_size":30720,"chunk_length_offset":21,"xml_length_offset":170,"transport_trailer
- `import_technicians_xlsx.py` (4 symbols, 1 DataSnap methods) - =============================================================================
- `installer_change_protocol_templates.json` (1 DataSnap methods) - {
- `manual_materials.py` (8 symbols) - =============================================================================
- `manual_order_protocol_templates.json` (1 DataSnap methods) - {
- `material_matching.py` (9 symbols) - =============================================================================
- `material_protocol_templates.json` (1 DataSnap methods) - {
- `native_order_protocol_templates.json` (2 DataSnap methods) - {
- `official_candidate_locator.py` (4 symbols) - Read-only offline candidate locator for official API closes.
- `official_close.py` (4 symbols) - =============================================================================
- `official_close_code_catalog.py` (8 symbols, 1 DataSnap methods) - =============================================================================
- `official_close_code_reconciliation.py` (12 symbols) - =============================================================================
- `official_close_dry_run.py` (28 symbols) - =============================================================================
- `official_close_sender.py` (29 symbols) - Restricted single-request executor for an official Imperium close payload.
- `official_material_catalog.py` (27 symbols) - =============================================================================
- `official_material_resolver.py` (6 symbols) - Unified, strictly offline facade for official material resolution.
- `official_stock_audit.py` (14 symbols, 2 DataSnap methods) - =============================================================================
- `official_stock_blocker_review.py` (15 symbols) - =============================================================================
- `official_stock_remediation_plan.py` (25 symbols, 1 DataSnap methods) - =============================================================================
- `productive_protocol_templates.json` (3 DataSnap methods) - {
- `protocol_templates.json` - {"version":1,"captured_date":"2026-07-15","main_query":"KERzcEdldE9zIQFgYQEgEATBAgwgAAABAAAAAAAAAA0AAAAMIAAAAQAAAAAAAAAGAAAACAAAAA0AAABAAFIARQBUAFUAUgBOAF8AVgBBAEwAVQBFAAAAAAAQAAAA
- `README.md` - DOMINIUM
- `requirements-dev.txt` - -r requirements-web.txt
- `requirements-voice.txt` - Voz neural gratuita dos alertas TEC1. A voz local do navegador permanece como fallback.
- `requirements-web.txt` - Runtime do DOMINIUM web em producao
- `serialized_transfer_protocol_templates.json` (2 DataSnap methods) - {
- `stock_pdf.py` (28 symbols) - Geracao de relatorios PDF de estoque sem dependencias externas.
- `stock_protocol_templates.json` (2 DataSnap methods) - {
- `supabase_auth_store.py` (28 symbols) - import datetime as dt
- `supabase_schema.sql` - -- DOMINIUM web auth schema for Supabase.
- `technician_directory.py` (7 symbols) - =============================================================================

## Indexed areas not expanded here

- shared: 80 files
- tooling-deploy: 18 files
- docs: 5 files
- tests: 65 files

## Search indexes

- file-index.tsv: compact file/category/summary index.
- symbol-index.tsv: symbol -> file -> line lookup.
- api-index.tsv: API path -> file lookup.
- dependency-index.tsv: Python import -> file lookup.
- project-map.json: structured file metadata fallback; search it, do not read it whole.

## Environment variable names

`DOMINIUM_AUTH_BACKEND`, `DOMINIUM_AUTH_EMAIL_DOMAIN`, `DOMINIUM_CHROMEDRIVER`, `DOMINIUM_DATABASE_URL`, `DOMINIUM_HTTPS`, `DOMINIUM_INGEST_TOKEN`, `DOMINIUM_LOCAL_TOA_AUTOMATION`, `DOMINIUM_PROJECT_ROOT`, `DOMINIUM_PROXY_TOKEN`, `DOMINIUM_PUBLIC_ORIGIN`, `DOMINIUM_TOA_AUTOMATION_REMOTE`, `DOMINIUM_TOA_BRIDGE_LOOKUP_TIMEOUT`, `DOMINIUM_TOA_BRIDGE_POLL_INTERVAL`, `DOMINIUM_TOA_BRIDGE_REQUEST_TIMEOUT`, `DOMINIUM_TOA_BRIDGE_URL`, `DOMINIUM_TOA_COLLECTOR_TOKEN`, `DOMINIUM_TOA_DEBUG_PORT`, `DOMINIUM_TOA_PRIMARY_TOKEN`, `DOMINIUM_TV_INGEST_URL`, `DOMINIUM_WEB_MODE`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF`, `SUPABASE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`
