from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "dominium-web-release"

ROOT_SUPPORT_FILES = {
    ".env.example",
    ".imperium-project.json",
    "requirements-web.txt",
    "requirements-voice.txt",
    "supabase_schema.sql",
}

ROOT_SUPPORT_PATTERNS = (
    "*_protocol_templates.json",
    "protocol_templates.json",
    "serialized_transfer_apply_template.bin",
)

SERVER_SCRIPT_FILES = {
    "bootstrap_admin.py",
    "check_supabase_ready.py",
    "configure_imperium_credentials.py",
}
PRODUCTION_CONFIG_FILES = {
    "technicians.json",
    "official_close_code_catalog/Tabela_codigo_baixa0711.catalog.json",
}
LOCAL_ONLY_DIRS = {
    ".git",
    ".secrets",
    ".temp",
    ".venv",
    "__pycache__",
    "backups",
    "data",
    "logs",
    "tests",
    "tmp",
}


def release_source_allowed(rel: Path) -> bool:
    if any(part in LOCAL_ONLY_DIRS for part in rel.parts):
        return False
    name = rel.name.casefold()
    if name.endswith(".bak") or ".bak_" in name or name.endswith(".tmp"):
        return False
    return True


def include_release_source(path: Path) -> bool:
    return path.is_file() and release_source_allowed(path.relative_to(ROOT))


def runtime_python_files() -> set[Path]:
    modules = {
        path.stem: path
        for path in ROOT.glob("*.py")
        if not path.name.startswith("test_")
    }
    seen: set[str] = set()
    queue = ["app"]
    while queue:
        name = queue.pop(0)
        if name in seen or name not in modules:
            continue
        seen.add(name)
        tree = ast.parse(modules[name].read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.Import):
                candidates = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                candidates = [node.module.split(".")[0]]
            for candidate in candidates:
                if candidate in modules and candidate not in seen:
                    queue.append(candidate)
    return {modules[name] for name in seen}


def include_config_file(path: Path) -> bool:
    if not path.is_file():
        return False
    rel = path.relative_to(ROOT / "config").as_posix()
    return rel in PRODUCTION_CONFIG_FILES


def collect_release_files() -> set[Path]:
    files = set(runtime_python_files())
    for name in ROOT_SUPPORT_FILES:
        path = ROOT / name
        if path.is_file():
            files.add(path)
    for pattern in ROOT_SUPPORT_PATTERNS:
        files.update(path for path in ROOT.glob(pattern) if path.is_file())

    for directory in ("static", "supabase"):
        base = ROOT / directory
        if base.is_dir():
            files.update(
                path
                for path in base.rglob("*")
                if include_release_source(path)
            )

    deploy = ROOT / "deploy"
    if deploy.is_dir():
        files.update(
            path
            for path in deploy.rglob("*")
            if (
                include_release_source(path)
                and "legacy-vps" not in path.relative_to(deploy).parts
            )
        )

    config = ROOT / "config"
    if config.is_dir():
        files.update(path for path in config.rglob("*") if include_config_file(path))

    scripts = ROOT / "scripts"
    for name in SERVER_SCRIPT_FILES:
        path = scripts / name
        if path.is_file():
            files.add(path)
    return files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output: Path) -> tuple[Path, Path]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    manifest: list[dict[str, object]] = []
    for source in sorted(collect_release_files()):
        rel = source.relative_to(ROOT)
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append(
            {
                "path": rel.as_posix(),
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
            }
        )

    metadata = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "files": len(manifest),
        "bytes": sum(int(item["bytes"]) for item in manifest),
        "entries": manifest,
    }
    (output / "RELEASE_MANIFEST.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    archive = output.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(
        archive, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False
    ) as bundle:
        for source in sorted(output.rglob("*")):
            if source.is_file():
                bundle.write(source, source.relative_to(output).as_posix())
    return output, archive


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a minimal DOMINIUM web production release"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output, archive = build(args.output.resolve())
    print(f"release_dir={output}")
    print(f"release_zip={archive}")
    print(f"release_zip_mb={archive.stat().st_size / (1024 * 1024):.2f}")


if __name__ == "__main__":
    main()
