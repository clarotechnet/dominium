# DOMINIUM agent guide

Use this file as the first navigation layer for Codex, Claude Code, and other coding agents.

## First move

1. Read `.dominium/project-map.md`.
2. Use the TSV indexes for targeted lookup: `symbol-index.tsv` for symbols, `api-index.tsv` for API paths, `dependency-index.tsv` for imports, and `file-index.tsv` for file/category summaries. Use `project-map.json` only as structured file-metadata fallback.
3. For a named symbol, endpoint, module, or concept, run `.\.venv\Scripts\python.exe .\scripts\query_agent_context.py <terms>` and open only the top candidates.
4. Open only the source files relevant to the task.
5. Verify behavior in real code before editing; the map is an index, not source of truth.
6. Do not recursively scan the whole repository unless the map is stale or the target is genuinely unknown.

Regenerate the map with:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_agent_context.py
```

Check whether generated context is current with:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_agent_context.py --check
```
## Repository boundaries

Treat this checkout as source code. Runtime state is not source.

Never inspect or modify these unless the task explicitly requires runtime evidence:
- `.env*`, `config/*.dat*`, `.secrets/`
- `logs/`, `data/`, `tmp/`, `backups/`, `reports/`, `output/`
- `config/toa_chrome_profile/`
- private keys, certificates, browser profiles, SQLite databases, packet captures

Do not use broad recursive reads of `.venv/`, `node_modules/`, generated assets, or historical backups.

Never use destructive Git commands such as `reset --hard`, `clean -fd`, or forced checkout to remove local work.

Before changing production-sensitive code, inspect `git status --short` and preserve unrelated modifications.
## Architecture shortcuts

Use `docs/agent/TASK_ROUTER.md` for task-to-file routing.

Core boundaries:
- `app.py`: HTTP server, orchestration, profile selection, operation gate.
- `imperium_api.py`: DataSnap/MIDAS access and Imperium operations.
- `toa_automation.py`: scheduled TOA export/import orchestration.
- `toa_import.py`: TOA CSV -> Imperium import packet conversion.
- `toa_secondary_session.py`: secondary/dedicated TOA browser session integration.
- `disconnect_automation.py`: automated disconnect workflow.
- `operational_store.py`: persisted operational state.
- `static/app.js`: main web UI behavior.
- `tests/`: behavior contracts; prefer the narrowest relevant test first.

Cross-system changes touching TOA and Imperium require tests on both sides.
## Change protocol

For a normal code change:
1. Locate with project map/symbol index.
2. Read the smallest relevant implementation and tests.
3. Inspect callers before changing public behavior.
4. Add or update a regression test.
5. Run the narrow test.
6. Regenerate agent context if structure, routes, symbols, dependencies, or task routing changed.
7. Run `scripts/quality_gate.py` before push/deploy.

Do not report success from UI state alone when the Imperium/TOA backend can be queried directly.
Do not treat existence of an OS as proof that installer/controller/state reconciliation succeeded.

## Context discipline

Prefer symbol-targeted search over file-by-file exploration.
Prefer current source and tests over old checkpoint/history documents.
Use `docs/history/` only when investigating why a design exists or recovering prior protocol knowledge.
Keep generated context compact: summaries and indexes should point to code rather than duplicate it.
