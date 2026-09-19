from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static"
OUTPUT = ROOT / "output" / "hostinger-frontend"

EXCLUDED_NAMES = {
    ".env",
    ".secrets",
}
EXCLUDED_SUFFIXES = (
    ".bak",
    ".tmp",
)


def allowed(path: Path) -> bool:
    rel = path.relative_to(SOURCE)
    for part in rel.parts:
        lowered = part.casefold()
        if lowered in EXCLUDED_NAMES:
            return False
        if lowered.endswith(EXCLUDED_SUFFIXES) or ".bak_" in lowered:
            return False
    return path.is_file()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"Frontend nao encontrado: {SOURCE}")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    entries: list[dict[str, object]] = []
    for source in sorted(SOURCE.rglob("*")):
        if not allowed(source):
            continue
        rel = source.relative_to(SOURCE)
        target = OUTPUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        entries.append(
            {
                "path": rel.as_posix(),
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
            }
        )

    manifest = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "source": "static/",
        "target": "hostinger-frontend",
        "files": len(entries),
        "bytes": sum(int(item["bytes"]) for item in entries),
        "entries": entries,
    }
    manifest_path = OUTPUT / "HOSTINGER_FRONTEND_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    archive = OUTPUT.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(
        archive, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False
    ) as bundle:
        for source in sorted(OUTPUT.rglob("*")):
            if source.is_file():
                bundle.write(source, source.relative_to(OUTPUT).as_posix())

    print(f"frontend_dir={OUTPUT}")
    print(f"frontend_zip={archive}")
    print(f"files={len(entries)}")
    print(f"zip_mb={archive.stat().st_size / (1024 * 1024):.2f}")


if __name__ == "__main__":
    main()
