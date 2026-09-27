# DOMINIUM agent context

This directory is generated navigation context for coding agents.

Read order:
1. `../AGENTS.md`
2. `project-map.md`
3. `../docs/agent/TASK_ROUTER.md` when the request is operational
4. use the TSV indexes with search instead of opening the full JSON

Files:
- `project-map.md`: compact human-readable architecture/file map
- `file-index.tsv`: file/category/summary lookup
- `symbol-index.tsv`: symbol, kind, path, line, parent
- `api-index.tsv`: API path to source file
- `dependency-index.tsv`: imported Python module to source file
- `project-map.json`: structured file-metadata fallback

Refresh:
```powershell
.\.venv\Scripts\python.exe .\scripts\generate_agent_context.py
```

Query without scanning source:
```powershell
.\.venv\Scripts\python.exe .\scripts\query_agent_context.py installer reassignment
```

Verify freshness:
```powershell
.\.venv\Scripts\python.exe .\scripts\generate_agent_context.py --check
```

Generated context never indexes local credentials, browser profiles, runtime logs,
databases, packet captures, private keys, certificates, virtualenvs, or node_modules.
