from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "deploy" / "hostinger-web"
STATIC = ROOT / "static"
DEFAULT_OUTPUT = ROOT / "output" / "hostinger-node-release"

RUNTIME_FILES = (
    "disconnection-proxy.js",
    "server.js",
    "package.json",
    "package-lock.json",
    "protocol_templates.json",
)

BLOCKED_NAMES = {
    ".env",
    ".secrets",
    ".git",
}
BLOCKED_SUFFIXES = (
    ".bak",
    ".tmp",
    ".old",
    "~",
)


def _allowed_static(path: Path) -> bool:
    if not path.is_file():
        return False
    rel = path.relative_to(STATIC)
    for part in rel.parts:
        lowered = part.casefold()
        if lowered in BLOCKED_NAMES or lowered.startswith("."):
            return False
        if lowered.endswith(BLOCKED_SUFFIXES) or ".bak_" in lowered:
            return False
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output: Path = DEFAULT_OUTPUT) -> tuple[Path, Path]:
    output = output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    # Server-only configuration supplied by the encrypted deployment secret.
    # It is absent from source, static assets, and ordinary downloadable releases.
    connection = os.environ.get("DOMINIUM_DESC_REVIEW_CONNECTION", "").strip()
    if connection:
        value = json.loads(connection)
        if set(value) != {"origin", "token"} or not str(value['origin']).startswith('https://') or len(str(value['token'])) < 43:
            raise ValueError("Invalid private DESC connection")
        (output / ".desc-review-connection.json").write_text(json.dumps(value), encoding="utf-8")

    entries: list[dict[str, object]] = []

    def copy(source: Path, relative: Path) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        entries.append(
            {
                "path": relative.as_posix(),
                "bytes": source.stat().st_size,
                "sha256": _sha256(source),
            }
        )

    for name in RUNTIME_FILES:
        copy(RUNTIME / name, Path(name))

    if not STATIC.is_dir():
        raise FileNotFoundError(STATIC)
    for source in sorted(STATIC.rglob("*")):
        if _allowed_static(source):
            copy(source, Path("static") / source.relative_to(STATIC))

    required = {
        "server.js",
        "package.json",
        "package-lock.json",
        "protocol_templates.json",
        "static/index.html",
        "static/app.js",
        "static/styles.css",
    }
    packaged = {str(item["path"]) for item in entries}
    missing = sorted(required - packaged)
    if missing:
        raise RuntimeError(
            "Hostinger release incompleto: " + ", ".join(missing)
        )

    manifest = {
        "schema": "dominium_hostinger_node_release_v1",
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "runtime_source": "deploy/hostinger-web",
        "frontend_source": "static",
        "files": len(entries),
        "bytes": sum(int(item["bytes"]) for item in entries),
        "entries": entries,
    }
    manifest_path = output / "RELEASE_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )

    archive = output.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(
        archive,
        "w",
        zipfile.ZIP_DEFLATED,
        strict_timestamps=False,
    ) as bundle:
        for source in sorted(output.rglob("*")):
            if source.is_file():
                bundle.write(
                    source,
                    source.relative_to(output).as_posix(),
                )

    return output, archive


def main() -> None:
    output, archive = build()
    print(f"release_dir={output}")
    print(f"release_zip={archive}")
    print(f"release_zip_mb={archive.stat().st_size / (1024 * 1024):.2f}")


if __name__ == "__main__":
    main()
