# DOMINIUM task router

This file converts operational language into the smallest useful code path. Start here when the request does not name files.

## TOA automatic import / schedule / route buckets

Read in this order:
1. `toa_automation.py`
2. `toa_import.py`
3. `imperium_api.py`
4. `app.py` only for API/orchestration glue
5. `tests/test_toa_automation.py`
6. `tests/test_toa_import.py`

Typical symptoms: scheduled import did not run, bucket missing, counts wrong, route export failed, existing OS skipped.

## Existing OS / installer changed in TOA but not Imperium

Read:
1. `toa_import.py`
2. `imperium_api.py` import/reconciliation path
3. `installer_change.py` only for explicit installer-change flow
4. `app.py` import endpoint
5. `tests/test_installer_reassignment.py`
6. `tests/test_toa_import.py`

Never accept “OS exists” as proof of installer reconciliation.
## DataSnap login / controller identity / protocol errors

Read:
1. `datasnap_client.py`
2. `imperium_api.py`
3. `operation_scope.py`
4. protocol template used by the operation
5. narrow test for that operation

Search the generated map for `controller_id`, `IdUsuarioCadastro`, or the server method before broad search.
Never expose `config/credentials.dat` contents.

## Manual OS creation

Read:
1. `manual_orders.py`
2. `native_orders.py`
3. `native_order_protocol_templates.json`
4. `app.py`
5. `tests/test_native_orders.py`
6. registration/manual-order tests if request originates from WhatsApp parsing.

## Disconnect / baixa automation

Read:
1. `disconnect_automation.py`
2. `official_close.py` and sender/catalog modules when using official flow
3. `imperium_api.py`
4. `app.py`
5. `static/app.js`
6. `tests/test_disconnect_automation.py`
7. `tests/test_disconnect_frontend.js`
## Stock / materials / miscelaneas / serials

Read:
1. `stock_inventory.py`
2. `material_matching.py`
3. `manual_materials.py`
4. `official_material_catalog.py`
5. `official_material_resolver.py`
6. `official_stock_audit.py`
7. relevant tests: stock, material matching, write-off, serialized transfer

For “item exists in Atlas but Dominium says missing”, verify normalization/matching before changing protocol bytes.

## TOA live session / browser / collector

Read:
1. `toa_secondary_session.py`
2. `toa_live.py`
3. `toa_browser.py`
4. `toa_local_collector.py`
5. `toa_connector.py`
6. TOA browser/live/collector tests

Do not restart the browser/session tree just to diagnose. Check health/session state first.

## Contract registry / outside route / historical TOA state

Read:
1. `toa_contract_registry.py`
2. `toa_datalake_store.py`
3. `operational_store.py`
4. `operations_intelligence.py`
5. matching tests
## Authentication / permissions / web deployment

Read:
1. `auth_store.py`, `auth_store_postgres.py`, `supabase_auth_store.py`
2. `api_security.py`
3. `supabase/`
4. `deploy/`
5. `scripts/build_web_release.py`
6. authentication/release tests

Never put Supabase secret/service keys in browser code or generated context.

## Frontend-only issue

Read:
1. `static/app.js`
2. related `static/*.js`
3. `static/index.html` / `static/styles.css`
4. relevant JS test

If UI displays derived TOA data, verify the Imperium backend value separately before declaring backend state correct.

## “Where is X?” / architecture question

Search the generated indexes first:
- `.dominium/symbol-index.tsv` for function/class names and line numbers
- `.dominium/api-index.tsv` for API paths
- `.dominium/dependency-index.tsv` for Python import edges
- `.dominium/file-index.tsv` for file/category summaries
- `.dominium/project-map.json` only for structured file metadata and environment-variable names

Only use recursive repository search if these indexes have no candidate.
## Production/runtime incident

Source checkout and runtime are separate concerns.

For incidents:
1. establish which process/path is actually serving the request;
2. collect read-only health/log evidence;
3. identify the source implementation;
4. patch source first when practical;
5. deploy/restart only the smallest affected component;
6. verify through the backend/system of record, not only the UI.

Avoid whole-server restarts and avoid changing unrelated services.

## Historical/protocol archaeology

Use `docs/history/`, `docs/reference/`, and `references/` only after current code fails to explain behavior.
Historical captures are evidence, not automatically current protocol truth.
