"""DOMINIUM portable agent memory: Git/Markdown source + rebuildable SQLite FTS5.

Never indexes runtime, .env, browser sessions, private client records or secrets.
No network or API keys. The index is a disposable local cache, not a source.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sqlite3
import subprocess
import sys
import zipfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "docs" / "agent" / "memory"
CACHE = ROOT / "output" / "agent-memory.sqlite3"
AUTOMATIC = MEMORY / "AUTO_CHANGES.md"
PRIVATE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{15,}|sb_secret_[A-Za-z0-9_-]{10,}|"
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"(?i:password|senha|token|cookie|authorization|secret)\s*[:=]\s*\S+|"
    r"\b\d{11,18}\b)"
)
GUIDES = (
    "AGENTS.md", "CLAUDE.md", "GEMINI.md",
    ".github/copilot-instructions.md", "docs/agent/MEMORY_SYSTEM.md",
    "docs/agent/TASK_ROUTER.md", ".dominium/project-map.md",
)


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          check=False, text=True, encoding="utf-8",
                          errors="replace")


def memory_files() -> list[tuple[str, str]]:
    candidates = [ROOT / path for path in GUIDES]
    candidates += sorted(MEMORY.glob("*.md"))
    result = []
    for file in candidates:
        if (file.is_file() and file.stat().st_size <= 500_000
                and file.resolve().is_relative_to(ROOT.resolve())):
            relative = file.relative_to(ROOT).as_posix()
            result.append((relative, file.read_text(encoding="utf-8", errors="replace")))
    return result


def memory_fingerprint(items: list[tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for name, content in items:
        h.update(name.encode("utf-8"))
        h.update(content.encode("utf-8"))
    return h.hexdigest()


def create_index(path: Path | None = None) -> tuple[sqlite3.Connection, bool]:
    path = path if path is not None else CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10.0)
    db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS documents (path TEXT PRIMARY KEY, body TEXT NOT NULL)")
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(path UNINDEXED, body, tokenize='unicode61 remove_diacritics 2')")
        fts = True
    except sqlite3.OperationalError:
        fts = False
    items = memory_files()
    fingerprint = memory_fingerprint(items)
    stored = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
    if not stored or stored[0] != fingerprint:
        with db:
            db.execute("DELETE FROM documents")
            db.executemany("INSERT INTO documents(path,body) VALUES (?,?)", items)
            if fts:
                db.execute("DELETE FROM content_fts")
                db.executemany("INSERT INTO content_fts(path,body) VALUES (?,?)", items)
            db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES ('fingerprint',?)",
                       (fingerprint,))
    return db, fts


def brief() -> None:
    page = MEMORY / "CURRENT_STATE.md"
    if not page.is_file():
        raise SystemExit("Memória ausente: docs/agent/memory/CURRENT_STATE.md")
    print(page.read_text(encoding="utf-8")[:8500].strip())
    print("\n--- Git: alterações recentes ---")
    history(5)
    print("\nPróximo passo: python scripts/agent_memory.py search \"<tarefa>\"")


def history(limit: int) -> None:
    result = run_git("--no-pager", "log", "--max-count=" + str(min(50,max(1,limit))),
                     "--format=%h | %as | %s")
    if result.returncode:
        print("Git indisponível para histórico", file=sys.stderr)
        return
    for line in result.stdout.splitlines():
        # git message can be untrusted; truncate as context hint only
        print(line[:240])


def safe_text(value: str) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 500 or "\n" in value or "\r" in value:
        raise ValueError("Campo obrigatório de no máximo 500 caracteres em uma linha")
    if PRIVATE.search(value):
        raise ValueError("Conteúdo semelhante a dado privado ou credencial; reformule sem identificadores")
    return value


def record(args: argparse.Namespace) -> None:
    fields = [safe_text(getattr(args, f)) for f in ("title","why","changed","tests","next")]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    note = (f"\n## {now} — {fields[0]}\n\n"
            f"**Motivo:** {fields[1]}\n\n"
            f"**Alterado:** {fields[2]}\n\n"
            f"**Verificação:** {fields[3]}\n\n"
            f"**Próximo passo/pendência:** {fields[4]}\n")
    with (MEMORY / "OPERATIONS_JOURNAL.md").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(note)
    print("MEMORY_RECORDED — commit este arquivo e atualize CURRENT_STATE.md quando necessário")


def autolog_staged() -> None:
    """Create a repeat-safe record of staged file NAMES. Staging is handled by hook."""
    changed = run_git("diff", "--cached", "--name-only", "--diff-filter=ACDMRT", "-z")
    raw = run_git("diff", "--cached", "--raw", "--no-abbrev")
    if changed.returncode or raw.returncode:
        raise SystemExit("Git index indisponível")
    paths = [p for p in changed.stdout.split("\0") if p and
             not p.startswith(".dominium/") and
             p != "docs/agent/memory/AUTO_CHANGES.md"]
    if not paths:
        print("AUTOLOG_NO_CODE_CHANGES")
        return
    for p in paths:
        if PRIVATE.search(p) or p.startswith((".env", ".secrets/", "data/", "logs/", "output/")):
            raise SystemExit("Caminho sensível staged; verifique antes de prosseguir")
    # Ignore our own generated memory/index entries when computing fingerprint:
    # rerunning pre-commit must not append a second record for the same change.
    raw_lines = [line for line in raw.stdout.splitlines()
                 if not line.split("\\t")[-1].startswith(".dominium/")
                 and line.split("\\t")[-1] != "docs/agent/memory/AUTO_CHANGES.md"]
    digest = hashlib.sha256("\\n".join(raw_lines).encode("utf-8")).hexdigest()[:16]
    AUTOMATIC.parent.mkdir(parents=True, exist_ok=True)
    existing = AUTOMATIC.read_text(encoding="utf-8") if AUTOMATIC.exists() else ""
    if f"staged:{digest}" in existing:
        print("AUTOLOG_ALREADY_RECORDED",digest)
        return
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    body = (f"\n## {stamp} | staged:{digest}\n\n"
            f"Alterações preparadas para commit ({len(paths)} arquivos). "
            "Para motivação e resultado consulte a mensagem do commit e "
            "OPERATIONS_JOURNAL.md.\n\n")
    body += "".join(f"- `{p.replace(chr(96), '')}`\n" for p in paths[:60])
    if len(paths)>60:
        body+=f"- ... e {len(paths)-60} outros arquivos\n"
    AUTOMATIC.write_text(existing + body, encoding="utf-8", newline="\n")
    print("AUTOLOG_UPDATED",digest,len(paths))


def search(query: str, limit: int) -> None:
    words = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
    words = [word for word in words if len(word) > 1][:8]
    if not words:
        raise SystemExit("Busca exige termos com ao menos 2 caracteres")
    db, fts = create_index()
    try:
        if fts:
            expression = " OR ".join('"' + w.replace('"','') + '"' for w in words)
            rows = db.execute(
                "SELECT path, snippet(content_fts,1,'[',']',' … ',24),"
                "bm25(content_fts) FROM content_fts WHERE content_fts MATCH ? "
                "ORDER BY bm25(content_fts) LIMIT ?", (expression,min(30,max(1,limit)))
            ).fetchall()
        else:
            condition = " OR ".join("body LIKE ?" for _ in words)
            rows = db.execute(
                f"SELECT path,substr(body,1,360),0 FROM documents WHERE {condition} "
                "LIMIT ?", tuple('%'+w+'%' for w in words)+(min(30,max(1,limit)),)
            ).fetchall()
        print("INDEX", "SQLite-FTS5" if fts else "SQLite-LIKE-fallback",
              "RESULTADOS",len(rows))
        for path, excerpt, _ in rows:
            print(f"\nSOURCE {path}\n{excerpt[:530]}")
        if not rows:
            print("Sem nota indexada: tente scripts/query_agent_context.py para símbolos de código")
    finally:
        db.close()


def export_bundle() -> None:
    """Portable sanitized handoff for a new account without file-system access."""
    candidates = memory_files()
    output = ROOT / "output" / "dominium-agent-handoff.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Archive contains ONLY the curated, versionable notes + code-navigation map.
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in candidates:
            # This is an extra safeguard; project secrets are never indexed.
            if PRIVATE.search(body):
                raise ValueError("Handoff contem identificador que precisa ser revisado: " + name)
            archive.writestr(name, body)
        git_log = run_git("--no-pager", "log", "--max-count=20",
                          "--format=%h | %as | %s")
        if git_log.returncode == 0 and not PRIVATE.search(git_log.stdout):
            archive.writestr("RECENT_GIT_COMMITS.md",
                "# Git history (compact, advisory only)\\n\\n" + git_log.stdout)
    print("PORTABLE_HANDOFF_BUILT", output)
    print("NOTE: code source itself remains in the authenticated Git repository")


def doctor() -> None:
    result = run_git("rev-parse", "--show-toplevel")
    print("GIT_OK",result.returncode==0)
    for p in ("AGENTS.md","CLAUDE.md","GEMINI.md",".github/copilot-instructions.md",
              "docs/agent/memory/CURRENT_STATE.md",
              "docs/agent/memory/DECISIONS.md","docs/agent/memory/OPERATIONS_JOURNAL.md"):
        print("GUIDE",p,(ROOT/p).is_file())
    db, fts = create_index()
    print("SEARCH_ENGINE","FTS5" if fts else "fallback-LIKE")
    print("DOCUMENTS_INDEXED",db.execute("SELECT count(*) FROM documents").fetchone()[0])
    db.close()
    hook_value = run_git("rev-parse", "--git-path", "hooks/pre-commit")
    hook = Path(hook_value.stdout.strip()) if hook_value.returncode == 0 else ROOT / ".git" / "hooks" / "pre-commit"
    if not hook.is_absolute():
        hook = ROOT / hook
    print("AUTOMATIC_HOOK_INSTALLED",
          hook.is_file() and "DOMINIUM_AGENT_CONTEXT_HOOK" in
          hook.read_text(encoding="utf-8",errors="replace") if hook.is_file() else False)
    print("RUNTIME_SECRET_INDEXED",False)  # restricted curated files only


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("brief")
    q=sub.add_parser("search");q.add_argument("query",nargs="+")
    q.add_argument("--limit",type=int,default=8)
    hist=sub.add_parser("history");hist.add_argument("--limit",type=int,default=10)
    sub.add_parser("build")
    sub.add_parser("export")
    sub.add_parser("doctor")
    sub.add_parser("autolog-staged")
    note=sub.add_parser("record")
    for key in ("title","why","changed","tests","next"):
        note.add_argument("--"+key,required=True)
    args=parser.parse_args()
    if args.command=="brief":brief()
    elif args.command=="search":search(" ".join(args.query),args.limit)
    elif args.command=="history":history(args.limit)
    elif args.command=="record":record(args)
    elif args.command=="autolog-staged":autolog_staged()
    elif args.command=="doctor":doctor()
    elif args.command=="export":export_bundle()
    else:
        db, fts=create_index()
        print("MEMORY_INDEX_BUILT",db.execute("SELECT count(*) FROM documents").fetchone()[0],
              "FTS5",fts)
        db.close()


if __name__ == "__main__":
    main()
