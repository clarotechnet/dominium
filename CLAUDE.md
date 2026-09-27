# DOMINIUM / Claude Code

Read `AGENTS.md` first and follow it.

For navigation, read `.dominium/project-map.md` before searching the repository. Use `.dominium/symbol-index.tsv`, `api-index.tsv`, `dependency-index.tsv`, and `file-index.tsv` for exact lookup; use `project-map.json` only as structured file-metadata fallback.

Do not scan the whole repository by default. For named concepts/symbols/endpoints, run `.\.venv\Scripts\python.exe .\scripts\query_agent_context.py <terms>`, open only the top candidates, then verify the real implementation before editing.

Use `docs/agent/TASK_ROUTER.md` when the request is described operationally rather than by filename.

Generated context can be refreshed with:
`.\.venv\Scripts\python.exe .\scripts\generate_agent_context.py`
