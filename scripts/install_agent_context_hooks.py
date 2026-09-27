from __future__ import annotations

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".git" / "hooks"

PRE_COMMIT = """#!/bin/sh
set -e
cd "$(git rev-parse --show-toplevel)"
PY=".venv/Scripts/python.exe"
if [ ! -f "$PY" ]; then
  PY="python"
fi
"$PY" scripts/generate_agent_context.py
git add \
  .dominium/project-map.md \
  .dominium/project-map.json \
  .dominium/file-index.tsv \
  .dominium/symbol-index.tsv \
  .dominium/api-index.tsv \
  .dominium/dependency-index.tsv
"""
POST_REFRESH = """#!/bin/sh
cd "$(git rev-parse --show-toplevel)" || exit 0
PY=".venv/Scripts/python.exe"
if [ ! -f "$PY" ]; then
  PY="python"
fi
"$PY" scripts/generate_agent_context.py >/dev/null 2>&1 || true
"""


def install(name: str, content: str) -> None:
    path = HOOKS / name
    marker = "# DOMINIUM_AGENT_CONTEXT_HOOK"
    if content.startswith("#!/bin/sh\n"):
        body = "#!/bin/sh\n" + marker + "\n" + content[len("#!/bin/sh\n"):]
    else:
        body = marker + "\n" + content
    if path.exists():
        current = path.read_text(encoding="utf-8", errors="ignore")
        if marker not in current:
            backup = path.with_suffix(path.suffix + ".before-dominium")
            if not backup.exists():
                backup.write_text(current, encoding="utf-8")
    path.write_text(body, encoding="utf-8", newline="\n")
    os.chmod(path, path.stat().st_mode | stat.S_IEXEC)
    print(f"installed {path.relative_to(ROOT)}")


def main() -> int:
    if not (ROOT / ".git").is_dir():
        raise SystemExit("Git checkout not found")
    HOOKS.mkdir(parents=True, exist_ok=True)
    install("pre-commit", PRE_COMMIT)
    install("post-merge", POST_REFRESH)
    install("post-checkout", POST_REFRESH)
    print("DOMINIUM_AGENT_CONTEXT_HOOKS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
