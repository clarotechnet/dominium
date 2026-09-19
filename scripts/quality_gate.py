from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_TESTS = (
    ROOT / "tests" / "test_disconnect_frontend.js",
    ROOT / "tests" / "test_operations_monitor.js",
    ROOT / "tests" / "test_semiauto_frontend.js",
)
SECRET_PATTERNS = (
    re.compile(r"sb_secret_[A-Za-z0-9_-]{10,}"),
    re.compile(r"sbp_[A-Za-z0-9_-]{10,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ANTHROPIC_AUTH_TOKEN\\s*=\\s*[^\\s\\r\\n]{12,}", re.IGNORECASE),
)


def run(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise SystemExit(f"{label} falhou com exit code {result.returncode}")


def ruff_command() -> list[str]:
    sibling = Path(sys.executable).with_name(
        "ruff.exe" if sys.platform == "win32" else "ruff"
    )
    executable = sibling if sibling.is_file() else shutil.which("ruff")
    if not executable:
        raise SystemExit(
            "Ruff nao encontrado. Instale requirements-dev.txt antes do gate."
        )
    return [
        str(executable),
        "check",
        ".",
        "--select",
        "E9,F63,F7,F82",
        "--exclude",
        ".venv,backups,config/toa_chrome_profile,logs,tmp,output,data,integrations",
        "--output-format",
        "concise",
    ]


def audit_repository() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit("Nao foi possivel listar os arquivos do Git para auditoria")
    hits: list[str] = []
    for raw in result.stdout.split(b"\\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="surrogateescape")
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(rel)
    if hits:
        joined = ", ".join(sorted(hits))
        raise SystemExit(
            f"Segredo potencial detectado em arquivo versionavel: {joined}"
        )


def audit_release(release: Path) -> None:
    forbidden_dirs = {
        ".git",
        ".venv",
        ".secrets",
        ".ruff_cache",
        ".temp",
        "backups",
        "data",
        "logs",
        "tests",
        "tmp",
        "toa_chrome_profile",
    }
    for path in release.rglob("*"):
        if path.is_dir() and path.name in forbidden_dirs:
            raise SystemExit(f"Release contem diretorio proibido: {path}")
        if not path.is_file():
            continue
        if path.name.startswith("test_"):
            raise SystemExit(f"Release contem teste: {path}")
        lowered_name = path.name.casefold()
        if (
            lowered_name.endswith(".bak")
            or ".bak_" in lowered_name
            or lowered_name.endswith(".tmp")
        ):
            raise SystemExit(f"Release contem artefato local/backup: {path}")
        if path.suffix.lower() == ".cmd":
            raise SystemExit(f"Release contem helper local: {path}")
        if path.suffix.lower() == ".ps1":
            rel = path.relative_to(release).as_posix()
            if not rel.startswith("deploy/windows-server/"):
                raise SystemExit(f"Release contem PowerShell fora do deploy: {path}")
        if path.name == ".env" or ".dat" in path.name:
            raise SystemExit(f"Release contem credencial/runtime: {path}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise SystemExit(f"Release contem segredo detectado em {path}")


def main() -> None:
    print("\\n== Repository secret audit ==", flush=True)
    audit_repository()
    print("Repository secret audit: OK", flush=True)

    run(
        "Python tests",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-t",
            ".",
            "-p",
            "test_*.py",
            "-q",
        ],
    )
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js nao encontrado; testes JS nao podem ser executados")
    for test in JS_TESTS:
        run(f"JS {test.name}", [node, str(test)])

    run("Ruff critical", ruff_command())

    run(
        "Build release",
        [sys.executable, str(ROOT / "scripts" / "build_web_release.py")],
    )
    release = ROOT / "output" / "dominium-web-release"
    audit_release(release)
    print("\nQUALITY_GATE_OK", flush=True)


if __name__ == "__main__":
    main()
