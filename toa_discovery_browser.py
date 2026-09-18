# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO - este arquivo nao envia operacoes ao Imperium.
#
# TOA
# - SIM - sessao, coleta, importacao, inventario ou monitor do TOA.
#
# DOMINIUM COMPARTILHADO
# - A saida pode alimentar o restante do DOMINIUM em modo leitura.
#
# Categoria deste arquivo: TOA.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE_PATH = ROOT / "config" / "toa_chrome_profile"
EXTENSION_PATH = ROOT / "toa-discovery"
TOA_URL = "https://clarobrasil.etadirect.com/"
DEBUG_PORT = 9341


def _targets() -> list[dict[str, object]]:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{DEBUG_PORT}/json/list",
            timeout=2,
        ) as response:
            payload = json.load(response)
        return payload if isinstance(payload, list) else []
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []


def launch() -> dict[str, object]:
    if not CHROME_PATH.is_file():
        raise FileNotFoundError(f"Chrome não encontrado: {CHROME_PATH}")
    if not (EXTENSION_PATH / "manifest.json").is_file():
        raise FileNotFoundError(f"Extensão não encontrada: {EXTENSION_PATH}")
    PROFILE_PATH.mkdir(parents=True, exist_ok=True)

    targets = _targets()
    if not targets:
        arguments = [
            str(CHROME_PATH),
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={PROFILE_PATH}",
            "--profile-directory=Default",
            f"--disable-extensions-except={EXTENSION_PATH}",
            f"--load-extension={EXTENSION_PATH}",
            "--window-size=1600,1000",
            "--lang=pt-BR",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            TOA_URL,
        ]
        subprocess.Popen(
            arguments,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            targets = _targets()
            if targets:
                break
            time.sleep(0.25)
    if not targets:
        raise RuntimeError("Chrome de descoberta não abriu a porta de inspeção")

    extension_targets = [
        target for target in targets
        if str(target.get("url", "")).startswith("chrome-extension://")
    ]
    toa_targets = [
        target for target in targets
        if "clarobrasil.etadirect.com" in str(target.get("url", ""))
    ]
    return {
        "ok": True,
        "debug_port": DEBUG_PORT,
        "extension_targets": len(extension_targets),
        "toa_targets": len(toa_targets),
        "extension_loaded": bool(extension_targets),
        "profile": str(PROFILE_PATH),
    }


if __name__ == "__main__":
    print(json.dumps(launch(), ensure_ascii=False))
