from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".dominium"
JSON_PATH = OUT_DIR / "project-map.json"
MD_PATH = OUT_DIR / "project-map.md"
FILE_INDEX_PATH = OUT_DIR / "file-index.tsv"
SYMBOL_INDEX_PATH = OUT_DIR / "symbol-index.tsv"
API_INDEX_PATH = OUT_DIR / "api-index.tsv"
DEPENDENCY_INDEX_PATH = OUT_DIR / "dependency-index.tsv"
BT = chr(96)

TEXT_EXTENSIONS = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".html", ".css",
    ".md", ".txt", ".json", ".toml", ".sql", ".ps1", ".cmd", ".bat",
}
EXCLUDED_DIRS = {
    ".git", ".venv", ".dominium", "__pycache__", "node_modules",
    "logs", "data", "tmp", "backups", "reports", "output", "diagnostics",
    "captures", ".pytest_cache", ".ruff_cache", "dist", "coverage",
    "references", "history", "toa_chrome_profile",
}
MAX_TEXT_BYTES = 512_000
API_RE = re.compile(r"""["'](/api/[A-Za-z0-9_./{}?=&:\\()\-+*]+)""")
ENV_PATTERNS = (
    re.compile(r"""os\.getenv\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\]"""),
    re.compile(r"""process\.env\.([A-Z][A-Z0-9_]*)"""),
    re.compile(r"""\$env:([A-Z][A-Z0-9_]*)""", re.IGNORECASE),
)
DATASNAP_RE = re.compile(r"""\b(T[A-Za-z0-9_]+\.[A-Za-z0-9_]+)\b""")
JS_SYMBOL_PATTERNS = (
    ("function", re.compile(r"""\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(""")),
    ("class", re.compile(r"""\bclass\s+([A-Za-z_$][\w$]*)\b""")),
    ("function", re.compile(
        r"""\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"""
    )),
)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""
def versionable_files() -> list[Path]:
    raw = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    ).stdout
    paths: list[Path] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        rel = Path(item.decode("utf-8", errors="surrogateescape"))
        if should_index(rel, ROOT / rel):
            paths.append(rel)
    return sorted(set(paths), key=lambda value: value.as_posix().casefold())


def should_index(rel: Path, path: Path) -> bool:
    parts = {part.casefold() for part in rel.parts[:-1]}
    if parts & EXCLUDED_DIRS:
        return False
    name = rel.name.casefold()
    if name == ".env" or name.startswith(".env."):
        return False
    if name.endswith((".dat", ".key", ".pem", ".crt", ".pfx", ".p12")):
        return False
    if "ed25519" in name:
        return False
    if path.suffix.casefold() not in TEXT_EXTENSIONS:
        return False
    try:
        return path.is_file() and path.stat().st_size <= MAX_TEXT_BYTES
    except OSError:
        return False
def read_text(rel: Path) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def first_summary(rel: Path, text: str) -> str:
    if rel.suffix.casefold() == ".py":
        try:
            value = ast.get_docstring(ast.parse(text))
            if value:
                return value.strip().splitlines()[0][:180]
        except SyntaxError:
            pass
    punctuation = {"=", "-", "_", "*", "#", "/", " "}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped) <= punctuation:
            continue
        if stripped.startswith("#"):
            value = stripped.lstrip("#").strip()
            if value and not set(value) <= punctuation:
                return value[:180]
            continue
        if stripped.startswith(("//", "/*", "<!--")):
            value = stripped.lstrip("/< !-*").strip()
            if value and not set(value) <= punctuation:
                return value[:180]
            continue
        if rel.suffix.casefold() in {".md", ".txt"}:
            return stripped[:180]
        return ""
    return ""


def line_number(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1
def python_details(text: str) -> tuple[list[dict], list[str]]:
    symbols: list[dict] = []
    imports: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return symbols, []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"name": node.name, "kind": "function", "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            symbols.append({"name": node.name, "kind": "class", "line": node.lineno})
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append({
                        "name": child.name, "kind": "method",
                        "line": child.lineno, "parent": node.name,
                    })
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return symbols, sorted(imports)


def javascript_details(text: str) -> list[dict]:
    symbols: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    for kind, pattern in JS_SYMBOL_PATTERNS:
        for match in pattern.finditer(text):
            item = (match.group(1), kind, line_number(text, match.start()))
            if item in seen:
                continue
            seen.add(item)
            symbols.append({"name": item[0], "kind": item[1], "line": item[2]})
    return sorted(symbols, key=lambda item: (item["line"], item["name"]))


def category(rel: Path) -> str:
    posix = rel.as_posix().casefold()
    name = rel.name.casefold()
    if posix.startswith("tests/") or name.startswith("test_"):
        return "tests"
    if posix.startswith("static/"):
        return "frontend"
    if posix.startswith("deploy/") or posix.startswith("scripts/"):
        return "tooling-deploy"
    if posix.startswith("docs/"):
        return "docs"
    if "toa" in name or posix.startswith("toa-"):
        return "toa"
    if "imperium" in name or name in {
        "native_orders.py", "manual_orders.py", "stock_inventory.py",
        "serialized_transfer.py", "installer_change.py",
    }:
        return "imperium"
    if name in {"app.py", "disconnect_automation.py", "operational_store.py",
                "operations_intelligence.py", "operation_scope.py"}:
        return "orchestration"
    return "shared"
def analyze_file(rel: Path) -> dict:
    text = read_text(rel)
    suffix = rel.suffix.casefold()
    symbols: list[dict] = []
    imports: list[str] = []
    if suffix == ".py":
        symbols, imports = python_details(text)
    elif suffix in {".js", ".mjs", ".cjs", ".ts", ".tsx"}:
        symbols = javascript_details(text)

    endpoints = sorted(set(match.group(1) for match in API_RE.finditer(text)))
    env_vars: set[str] = set()
    for pattern in ENV_PATTERNS:
        env_vars.update(match.group(1).upper() for match in pattern.finditer(text))
    datasnap = sorted(set(DATASNAP_RE.findall(text)))
    return {
        "path": rel.as_posix(),
        "category": category(rel),
        "bytes": len(text.encode("utf-8")),
        "sha256": digest(text),
        "summary": first_summary(rel, text),
        "symbols": symbols,
        "imports": imports,
        "endpoints": endpoints,
        "env_vars": sorted(env_vars),
        "datasnap_methods": datasnap,
        "entrypoint": "__main__" in text if suffix == ".py" else suffix in {".cmd", ".bat"},
    }
def source_fingerprint(files: list[dict]) -> str:
    value = "\n".join(f'{item["path"]}\0{item["sha256"]}' for item in files)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_model() -> dict:
    files = [analyze_file(rel) for rel in versionable_files()]
    flattened_symbols = [
        {**symbol, "path": item["path"]}
        for item in files for symbol in item["symbols"]
    ]
    endpoints = [
        {"path": item["path"], "endpoint": endpoint}
        for item in files for endpoint in item["endpoints"]
    ]
    env_vars = sorted({name for item in files for name in item["env_vars"]})
    datasnap_methods = sorted({
        method for item in files for method in item["datasnap_methods"]
    })
    tests = [item["path"] for item in files if item["category"] == "tests"]
    for item in files:
        item["symbol_count"] = len(item["symbols"])
        item.pop("symbols", None)
    return {
        "schema": 2,
        "source_fingerprint": source_fingerprint(files),
        "files": files,
        "symbols": flattened_symbols,
        "symbol_count": len(flattened_symbols),
        "endpoints": endpoints,
        "env_vars": env_vars,
        "datasnap_methods": datasnap_methods,
        "tests": tests,
    }
def compact_file_line(item: dict) -> str:
    details: list[str] = []
    if item["symbol_count"]:
        details.append(f'{item["symbol_count"]} symbols')
    if item["endpoints"]:
        details.append(f'{len(item["endpoints"])} API paths')
    if item["datasnap_methods"]:
        details.append(f'{len(item["datasnap_methods"])} DataSnap methods')
    tail = f" ({', '.join(details)})" if details else ""
    summary = f" - {item['summary']}" if item["summary"] else ""
    return f"- {BT}{item['path']}{BT}{tail}{summary}"


def build_markdown(model: dict, generated_at: str) -> str:
    lines = [
        "# DOMINIUM project map",
        "",
        "Generated index for agent navigation. Source code remains authoritative.",
        "",
        f"- Generated: {generated_at}",
        f"- Source fingerprint: {BT}{model['source_fingerprint'][:16]}{BT}",
        f"- Indexed files: {len(model['files'])}",
        f"- Indexed symbols: {model['symbol_count']}",
        f"- API path references: {len(model['endpoints'])}",
        "",
        "## Navigation rule",
        "",
        "Use this map to choose files. Then read the real implementation and narrow tests.",
        "Do not recursively scan the repository when this map already identifies candidates.",
        "For operational-language routing, read docs/agent/TASK_ROUTER.md.",
        "",
    ]
    grouped: dict[str, list[dict]] = {}
    for item in model["files"]:
        grouped.setdefault(item["category"], []).append(item)

    for group in ("orchestration", "toa", "imperium", "frontend"):
        items = grouped.get(group, [])
        if not items:
            continue
        lines.extend([f"## {group}", ""])
        lines.extend(compact_file_line(item) for item in items)
        lines.append("")

    shared = [
        item for item in grouped.get("shared", [])
        if "/" not in item["path"] or item["path"].startswith("flow_reader/")
    ]
    if shared:
        lines.extend(["## shared core", ""])
        lines.extend(compact_file_line(item) for item in shared)
        lines.append("")

    lines.extend(["## Indexed areas not expanded here", ""])
    for group in ("shared", "tooling-deploy", "docs", "tests"):
        lines.append(f"- {group}: {len(grouped.get(group, []))} files")
    lines.extend([
        "",
        "## Search indexes",
        "",
        "- file-index.tsv: compact file/category/summary index.",
        "- symbol-index.tsv: symbol -> file -> line lookup.",
        "- api-index.tsv: API path -> file lookup.",
        "- dependency-index.tsv: Python import -> file lookup.",
        "- project-map.json: structured file metadata fallback; search it, do not read it whole.",
        "",
    ])

    if model["env_vars"]:
        lines.extend(["## Environment variable names", ""])
        lines.append(", ".join(f"{BT}{value}{BT}" for value in model["env_vars"]))
        lines.append("")
    return "\n".join(lines)


def tsv_cell(value: object) -> str:
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_indexes(model: dict) -> None:
    file_lines = [
        "category\tpath\tsymbols\tapi_paths\tdatasnap_methods\tsummary\thash16"
    ]
    for item in model["files"]:
        file_lines.append("\t".join([
            tsv_cell(item["category"]),
            tsv_cell(item["path"]),
            tsv_cell(item["symbol_count"]),
            tsv_cell(len(item["endpoints"])),
            tsv_cell(len(item["datasnap_methods"])),
            tsv_cell(item["summary"]),
            tsv_cell(item["sha256"][:16]),
        ]))
    FILE_INDEX_PATH.write_text("\n".join(file_lines) + "\n", encoding="utf-8")

    symbol_lines = ["name\tkind\tpath\tline\tparent"]
    for item in model["symbols"]:
        symbol_lines.append("\t".join([
            tsv_cell(item["name"]), tsv_cell(item["kind"]),
            tsv_cell(item["path"]), tsv_cell(item["line"]),
            tsv_cell(item.get("parent") or "-"),
        ]))
    SYMBOL_INDEX_PATH.write_text("\n".join(symbol_lines) + "\n", encoding="utf-8")

    api_lines = ["endpoint\tpath"]
    for item in model["endpoints"]:
        api_lines.append(
            f'{tsv_cell(item["endpoint"])}\t{tsv_cell(item["path"])}'
        )
    API_INDEX_PATH.write_text("\n".join(api_lines) + "\n", encoding="utf-8")

    dep_lines = ["import\tpath"]
    for item in model["files"]:
        for imported in item["imports"]:
            dep_lines.append(f'{tsv_cell(imported)}\t{tsv_cell(item["path"])}')
    DEPENDENCY_INDEX_PATH.write_text("\n".join(dep_lines) + "\n", encoding="utf-8")


def write_outputs(model: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    serializable = {
        "generated_at": generated_at,
        "schema": model["schema"],
        "source_fingerprint": model["source_fingerprint"],
        "files": model["files"],
        "env_vars": model["env_vars"],
        "datasnap_methods": model["datasnap_methods"],
    }
    JSON_PATH.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    MD_PATH.write_text(build_markdown(model, generated_at), encoding="utf-8")
    write_indexes(model)
def check_outputs(model: dict) -> int:
    try:
        existing = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("AGENT_CONTEXT_STALE: project-map.json missing or invalid")
        return 1
    if existing.get("source_fingerprint") != model["source_fingerprint"]:
        print("AGENT_CONTEXT_STALE: source fingerprint changed")
        return 1
    print("AGENT_CONTEXT_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate compact repository context for coding agents."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when generated context does not match indexable source files.",
    )
    args = parser.parse_args()
    model = build_model()
    if args.check:
        return check_outputs(model)
    write_outputs(model)
    print(
        "AGENT_CONTEXT_WRITTEN "
        f"files={len(model['files'])} symbols={len(model['symbols'])} "
        f"fingerprint={model['source_fingerprint'][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
