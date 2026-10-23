"""Install durable-memory Git hooks safely, including linked worktrees.

Git does not transport hooks in commits. Run once for each machine/clone.
Shared hooks are protected: never overwrite an unrelated existing script.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

PRE_COMMIT = """#!/bin/sh
# DOMINIUM_AGENT_CONTEXT_HOOK
set -e
cd "$(git rev-parse --show-toplevel)" || exit 1
PY=python
if [ -f ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"; fi
if [ -f ".venv/bin/python" ]; then PY=".venv/bin/python"; fi
if [ -f scripts/agent_memory.py ]; then
  "$PY" scripts/agent_memory.py autolog-staged
  git add docs/agent/memory/AUTO_CHANGES.md
fi
if [ -f scripts/generate_agent_context.py ]; then
  "$PY" scripts/generate_agent_context.py
  git add .dominium/project-map.md .dominium/project-map.json \
    .dominium/file-index.tsv .dominium/symbol-index.tsv \
    .dominium/api-index.tsv .dominium/dependency-index.tsv
fi
"""

POST_REFRESH = """#!/bin/sh
# DOMINIUM_AGENT_CONTEXT_HOOK
cd "$(git rev-parse --show-toplevel)" || exit 0
PY=python
if [ -f ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"; fi
if [ -f ".venv/bin/python" ]; then PY=".venv/bin/python"; fi
if [ -f scripts/generate_agent_context.py ]; then
  "$PY" scripts/generate_agent_context.py >/dev/null 2>&1 || true
fi
if [ -f scripts/agent_memory.py ]; then
  "$PY" scripts/agent_memory.py build >/dev/null 2>&1 || true
fi
"""


def git_hooks_path() -> Path:
    cmd=subprocess.run(["git","rev-parse","--git-path","hooks"],
        cwd=ROOT,capture_output=True,text=True,check=True)
    path=Path(cmd.stdout.strip())
    return path if path.is_absolute() else ROOT/path


def install(name: str, contents: str, hooks: Path) -> bool:
    target=hooks/name
    if target.exists():
        current=target.read_text(encoding="utf-8",errors="replace")
        if "DOMINIUM_AGENT_CONTEXT_HOOK" not in current:
            print("PRESERVED_EXISTING_HOOK",name,"(manual merge required)")
            return False
    target.write_text(contents,encoding="utf-8",newline="\n")
    os.chmod(target,target.stat().st_mode|stat.S_IEXEC)
    print("INSTALLED",name)
    return True


def main():
    hooks=git_hooks_path()
    hooks.mkdir(parents=True,exist_ok=True)
    success=0
    success+=install("pre-commit",PRE_COMMIT,hooks)
    success+=install("post-merge",POST_REFRESH,hooks)
    success+=install("post-checkout",POST_REFRESH,hooks)
    print("DOMINIUM_MEMORY_HOOKS_INSTALLED",success,"OF_3")
    print("HOOKS_SCOPE", "shared-Git-dir; guarded for old worktrees")
    return 0 if success==3 else 2


if __name__=="__main__":
    raise SystemExit(main())
