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
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from datasnap_client import load_credentials


ROOT = Path(__file__).resolve().parent
TOA_URL = "https://clarobrasil.etadirect.com/toa/"
TOA_DUO_URL = "https://clarobrasil.etadirect.com/"
PROFILE_PATH = ROOT / "config" / "toa_chrome_profile"
CREDENTIALS_PATH = ROOT / "config" / "toa_credentials.dat"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEBUG_PORT = 9339


def _debug_port() -> int:
    raw = os.environ.get("DOMINIUM_TOA_DEBUG_PORT", str(DEBUG_PORT)).strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError("DOMINIUM_TOA_DEBUG_PORT invalida") from exc
    if port < 1 or port > 65535:
        raise RuntimeError("DOMINIUM_TOA_DEBUG_PORT invalida")
    return port


def _webdriver_service() -> Service | None:
    raw = os.environ.get("DOMINIUM_CHROMEDRIVER", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_file():
        raise RuntimeError(f"ChromeDriver configurado nao encontrado: {path}")
    return Service(executable_path=str(path))


def create_driver(
    *,
    headless: bool = False,
    launch_if_missing: bool = True,
) -> webdriver.Chrome:
    PROFILE_PATH.mkdir(parents=True, exist_ok=True)
    debug_port = _debug_port()
    if not _debugger_running(debug_port):
        if not launch_if_missing:
            raise RuntimeError("O Chrome TOA de automacao nao esta aberto")
        arguments = [
            str(CHROME_PATH),
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={PROFILE_PATH}",
            "--profile-directory=Default",
            "--window-size=1600,1000",
            "--lang=pt-BR",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
        ]
        if headless:
            arguments.append("--headless=new")
        subprocess.Popen(
            arguments,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not _debugger_running(debug_port):
            time.sleep(0.25)
        if not _debugger_running(debug_port):
            raise RuntimeError("O Chrome TOA nao abriu a porta de automacao")

    options = Options()
    options.binary_location = str(CHROME_PATH)
    options.debugger_address = f"127.0.0.1:{debug_port}"
    service = _webdriver_service()
    if service is not None:
        return webdriver.Chrome(options=options, service=service)
    return webdriver.Chrome(options=options)


def _debugger_running(port: int | None = None) -> bool:
    debug_port = port if port is not None else _debug_port()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{debug_port}/json/version",
            timeout=1,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def debugger_running() -> bool:
    """Return whether the DOMINIUM-managed Chrome can be reattached."""
    return _debugger_running()


def close_browser(driver: webdriver.Chrome) -> None:
    try:
        driver.execute_cdp_cmd("Browser.close", {})
    except Exception:
        pass


def login_visible(driver: webdriver.Chrome) -> bool:
    try:
        if driver.find_element(By.ID, "sign-in").is_displayed():
            return True
    except NoSuchElementException:
        pass
    try:
        return (
            "cap.claro.com.br" in driver.current_url
            and driver.find_element(By.NAME, "username").is_displayed()
        )
    except NoSuchElementException:
        return False


def authenticated(driver: webdriver.Chrome) -> bool:
    if login_visible(driver):
        return False
    current_url = str(driver.current_url or "").strip()
    hostname = (urllib.parse.urlparse(current_url).hostname or "").casefold()
    if hostname != "clarobrasil.etadirect.com":
        return False
    text = driver.find_element(By.TAG_NAME, "body").text.casefold()
    authenticated_markers = (
        "console de aloca",
        "detalhes da atividade",
        "pesquisa em atividades",
        "atividades",
        "recursos",
    )
    return any(marker in text for marker in authenticated_markers)


def prefill_credentials(driver: webdriver.Chrome) -> None:
    if not login_visible(driver):
        return
    credentials = load_credentials(CREDENTIALS_PATH)
    try:
        username = driver.find_element(By.ID, "username")
        password = driver.find_element(By.ID, "password")
    except NoSuchElementException:
        username = driver.find_element(By.NAME, "username")
        password = driver.find_element(By.NAME, "password")
    username.clear()
    username.send_keys(credentials["username"])
    password.clear()
    password.send_keys(credentials["password"])


def connect_interactively(timeout: int = 900) -> None:
    driver = create_driver(headless=False)
    try:
        driver.get(TOA_URL)
        time.sleep(2)
        if authenticated(driver):
            print("Sessao TOA ja esta autenticada.")
            return
        prefill_credentials(driver)
        print("Janela DOMINIUM TOA aberta. Clique em Conectar.")
        print("Aguardando o Console de Alocacao...")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if authenticated(driver):
                print("Sessao TOA confirmada e salva com seguranca no perfil local.")
                time.sleep(3)
                return
            time.sleep(1)
        raise TimeoutError("O login TOA nao foi concluido dentro de 15 minutos")
    except WebDriverException as exc:
        raise RuntimeError(f"Falha ao abrir a sessao TOA: {exc.msg}") from exc
    finally:
        close_browser(driver)


if __name__ == "__main__":
    connect_interactively()
