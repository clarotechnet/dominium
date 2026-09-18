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
import datetime as dt
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

from toa_browser import (
    TOA_DUO_URL,
    TOA_URL,
    authenticated,
    create_driver,
    debugger_running,
    login_visible,
)
from toa_capture import TOACaptureLot


BATCH_STORAGE_KEY = "technet_toa_batch_v4"
CHECK_INTERVAL_SECONDS = 30
LOOKUP_TIMEOUT_SECONDS = 240
AUTHENTICATION_MISS_LIMIT = 2
AUTHENTICATION_RECHECK_SECONDS = 5.0


def _driver_connection_lost(exc: BaseException) -> bool:
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

    if isinstance(exc, InvalidSessionIdException):
        return True
    if not isinstance(exc, WebDriverException):
        return False
    message = str(exc).casefold()
    markers = (
        "invalid session id",
        "session deleted as the browser has closed the connection",
        "disconnected: not connected to devtools",
        "chrome not reachable",
        "target window already closed",
    )
    return any(marker in message for marker in markers)


TOA_ACCESS_URLS = {
    "direct": TOA_URL,
    "duo": TOA_DUO_URL,
}


def _digits(value: object) -> str:
    return "".join(re.findall(r"\d", str(value or "")))


def capture_payload_from_storage(storage: object, contract: object) -> dict[str, Any]:
    """Build a strict V5.6 payload containing only one contract."""
    wanted = _digits(contract)
    if not wanted:
        raise ValueError("Informe um contrato valido")
    if not isinstance(storage, dict):
        raise ValueError("O lote local do TECHCAP esta ausente ou invalido")
    raw_items = storage.get("items")
    raw_order = storage.get("order")
    if not isinstance(raw_items, dict) or not isinstance(raw_order, list):
        raise ValueError("O lote local do TECHCAP esta incompleto")

    entries: list[dict[str, Any]] = []
    for aid in raw_order:
        entry = raw_items.get(str(aid))
        if not isinstance(entry, dict):
            continue
        activity_contract = _digits(entry.get("contract"))
        if not activity_contract:
            activity_contract = _digits(
                (entry.get("os") or {}).get("activity", {}).get("contract")
                if isinstance(entry.get("os"), dict)
                else ""
            )
        if activity_contract == wanted:
            entries.append(entry)

    if not entries:
        raise ValueError(f"O TECHCAP nao capturou o contrato {wanted}")
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "metadata": {
            "version": "5.6-queue",
            "exportedAt": now,
            "source": "TECHCAP V5.6 live lookup",
            "count": len(entries),
            "rejectionCount": 0,
        },
        "summary": {"total": len(entries)},
        "rejections": [],
        "os_list": entries,
    }


class TOALiveSession:
    """Keeps a visible TOA session alive and performs read-only TECHCAP lookups."""

    def __init__(
        self,
        root: Path,
        *,
        logger: logging.Logger | None = None,
        driver_factory: Callable[..., Any] = create_driver,
        check_interval: int = CHECK_INTERVAL_SECONDS,
    ) -> None:
        self.root = root.resolve()
        self.logger = logger or logging.getLogger("imperium")
        self.driver_factory = driver_factory
        self.check_interval = max(5, int(check_interval))
        self.collector_path = (
            self.root
            / "references"
            / "techcap-v5.6"
            / "TECHCAP_TOA_V5_6_FLUXO_OS_PARA_OS.txt"
        )
        self.capture_root = self.root / "logs" / "toa-captures" / "live"
        self._driver = None
        self._collector_source: str | None = None
        self._collector_preload_id = ""
        self._authentication_misses = 0
        self._driver_lock = threading.RLock()
        self._inventory_ledger_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "configured": False,
            "running": False,
            "connected": False,
            "authenticated": False,
            "busy": False,
            "current_url": "",
            "last_check": "",
            "last_connected_at": "",
            "last_lookup_at": "",
            "last_contract": "",
            "last_error": "",
            "last_recovery_at": "",
            "access_mode": "direct",
        }

    @staticmethod
    def _now() -> str:
        return dt.datetime.now().astimezone().isoformat(timespec="seconds")

    def _update_state(self, **values: Any) -> None:
        with self._state_lock:
            self._state.update(values)

    def public_state(self) -> dict[str, Any]:
        with self._state_lock:
            state = dict(self._state)
        state.update({
            "ok": True,
            "monitor_interval_seconds": self.check_interval,
            "live_lookup_enabled": self.collector_path.is_file(),
            "imperium_write_enabled": False,
            "credentials_persisted": False,
            "manual_login": True,
        })
        return state

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._update_state(running=True)
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="toa-live-session-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._update_state(running=False, busy=False)
        with self._driver_lock:
            driver = self._driver
            self._driver = None
            self._collector_preload_id = ""
            try:
                if driver is not None and getattr(driver, "service", None):
                    driver.service.stop()
            except Exception:
                pass

    def _discard_driver_locked(self) -> None:
        driver = self._driver
        self._driver = None
        self._collector_preload_id = ""
        if driver is None:
            return
        try:
            service = getattr(driver, "service", None)
            if service is not None:
                service.stop()
        except Exception:
            pass

    def _recover_driver_locked(self, *, launch_if_missing: bool, reason: str) -> bool:
        self._discard_driver_locked()
        try:
            self._driver = self.driver_factory(
                headless=False,
                launch_if_missing=launch_if_missing,
            )
        except Exception as exc:
            self._update_state(
                connected=False,
                authenticated=False,
                last_check=self._now(),
                last_error=f"Falha ao recuperar Chrome/TOA: {exc}",
            )
            self.logger.warning("TOA ao vivo: recuperacao do Chrome falhou: %s", exc)
            return False
        self._authentication_misses = 0
        self._collector_preload_id = ""
        self._update_state(last_recovery_at=self._now(), last_error="")
        self.logger.warning("TOA ao vivo: Chrome/driver recuperado automaticamente (%s)", reason)
        return True

    def _monitor_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._driver_lock.acquire(timeout=1):
                    try:
                        self._refresh_session_state_locked()
                    finally:
                        self._driver_lock.release()
            except Exception as exc:
                self._update_state(
                    connected=False,
                    authenticated=False,
                    last_check=self._now(),
                    last_error=str(exc),
                )
                self.logger.warning("TOA ao vivo: verificacao da sessao falhou: %s", exc)
            self._stop.wait(self.check_interval)

    def _refresh_session_state_locked(self) -> None:
        now = self._now()
        had_driver = self._driver is not None
        if had_driver and not self._driver_is_alive():
            self._recover_driver_locked(
                launch_if_missing=True,
                reason="sessao Chrome/DevTools desconectada",
            )
        elif self._driver is None and debugger_running():
            self._recover_driver_locked(
                launch_if_missing=False,
                reason="sessao de automacao existente detectada",
            )
        if not self._driver_is_alive():
            self._authentication_misses = 0
            self._update_state(
                configured=False,
                connected=False,
                authenticated=False,
                current_url="",
                last_check=now,
                last_error="",
            )
            return
        if login_visible(self._driver):
            self._authentication_misses = AUTHENTICATION_MISS_LIMIT
            is_authenticated = False
        else:
            is_authenticated = authenticated(self._driver)
            if is_authenticated:
                self._authentication_misses = 0
            else:
                self._authentication_misses += 1
                with self._state_lock:
                    previously_authenticated = bool(
                        self._state.get("authenticated")
                    )
                if (
                    previously_authenticated
                    and self._authentication_misses < AUTHENTICATION_MISS_LIMIT
                ):
                    self._update_state(
                        configured=True,
                        connected=True,
                        authenticated=True,
                        current_url=str(self._driver.current_url or ""),
                        last_check=now,
                        last_error="",
                    )
                    return
        self._update_state(
            configured=is_authenticated,
            connected=True,
            authenticated=is_authenticated,
            current_url=str(self._driver.current_url or ""),
            last_check=now,
            last_connected_at=now if is_authenticated else "",
            last_error="" if is_authenticated else "Login TOA necessario",
        )

    def _driver_is_alive(self) -> bool:
        if self._driver is None:
            return False
        try:
            _ = self._driver.current_url
            return True
        except Exception as exc:
            if _driver_connection_lost(exc):
                self.logger.warning("TOA ao vivo: sessao Selenium/DevTools perdida: %s", exc)
            self._discard_driver_locked()
            return False

    def _fill_credentials_locked(self, username: str, password: str) -> None:
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import NoSuchElementException

        try:
            username_input = self._driver.find_element(By.ID, "username")
            password_input = self._driver.find_element(By.ID, "password")
        except NoSuchElementException:
            username_input = self._driver.find_element(By.NAME, "username")
            password_input = self._driver.find_element(By.NAME, "password")
        username_input.clear()
        username_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

    def _click_login_locked(self) -> None:
        from selenium.webdriver.common.by import By

        # The TOA page may contain injected side tools with unrelated submit
        # buttons. Anchor the action to the password field/form instead of
        # blindly clicking the first submit element in the document.
        password = None
        for locator in ((By.ID, "password"), (By.NAME, "password")):
            matches = self._driver.find_elements(*locator)
            if matches:
                password = matches[0]
                break
        candidates = []
        if password is not None:
            candidates = password.find_elements(
                By.XPATH,
                "ancestor::form[1]//button[normalize-space(.)='ENVIAR']"
                " | ancestor::form[1]//input[@type='submit']"
                " | ancestor::form[1]//button[@type='submit']",
            )
        if not candidates:
            candidates = self._driver.find_elements(
                By.XPATH,
                "//button[normalize-space(.)='ENVIAR'] | //input[@type='submit' and @value='ENVIAR']",
            )
        candidates = [candidate for candidate in candidates if candidate.is_displayed()]
        if not candidates:
            raise RuntimeError("O botao de login do TOA nao foi localizado")
        self._driver.execute_script("arguments[0].click()", candidates[0])

    def _wait_authenticated(self, timeout: float = 120) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if authenticated(self._driver):
                    return
            except Exception:
                pass
            time.sleep(1)
        raise TimeoutError("O TOA nao confirmou o login automatico")

    def _ensure_session_locked(self) -> None:
        if not self.collector_path.is_file():
            raise RuntimeError("Coletor TECHCAP V5.6 nao localizado")
        had_driver = self._driver is not None
        if not self._driver_is_alive():
            recovered = had_driver and self._recover_driver_locked(
                launch_if_missing=True,
                reason="sessao perdida antes da operacao",
            )
            if not recovered or not self._driver_is_alive():
                raise RuntimeError("Abra o TOA pelo botao antes de consultar contratos")
        deadline = time.monotonic() + AUTHENTICATION_RECHECK_SECONDS
        while True:
            if login_visible(self._driver):
                self._authentication_misses = AUTHENTICATION_MISS_LIMIT
                raise RuntimeError("A sessao TOA nao esta autenticada")
            if authenticated(self._driver):
                self._authentication_misses = 0
                break
            if time.monotonic() >= deadline:
                self._authentication_misses = AUTHENTICATION_MISS_LIMIT
                raise RuntimeError("A sessao TOA nao esta autenticada")
            time.sleep(0.25)

        now = self._now()
        self._update_state(
            configured=True,
            connected=True,
            authenticated=True,
            current_url=str(self._driver.current_url or ""),
            last_check=now,
            last_connected_at=now,
            last_error="",
        )

    def execute_readonly_script(self, script: str) -> Any:
        """Execute a read-only DOM snapshot while sharing the live driver lock."""
        if not isinstance(script, str) or not script.strip():
            raise ValueError("Script de leitura vazio")
        with self._driver_lock:
            self._ensure_session_locked()
            try:
                return self._driver.execute_script(script)
            except Exception as exc:
                if not _driver_connection_lost(exc):
                    raise
                if not self._recover_driver_locked(
                    launch_if_missing=True,
                    reason="queda durante leitura do TOA",
                ):
                    raise RuntimeError("A sessao do Chrome foi perdida") from exc
                self._ensure_session_locked()
                return self._driver.execute_script(script)

    def open_session(
        self,
        username: object,
        password: object,
        access_mode: object = "direct",
    ) -> dict[str, Any]:
        login = str(username or "").strip()
        secret = str(password or "")
        mode = str(access_mode or "direct").strip().casefold()
        if not login or not secret:
            raise ValueError("Informe usuario e senha do TOA")
        if mode not in TOA_ACCESS_URLS:
            raise ValueError("Selecione acesso direto/token ou acesso com DUO")
        entry_url = TOA_ACCESS_URLS[mode]
        with self._driver_lock:
            self._update_state(busy=True)
            try:
                if not self.collector_path.is_file():
                    raise RuntimeError("Coletor TECHCAP V5.6 nao localizado")
                if not self._driver_is_alive():
                    self._driver = self.driver_factory(headless=False)
                # Always honor the selected entrance. This also lets the operator
                # escape a stale CAP/DUO redirect by choosing the direct /toa/ URL.
                try:
                    self._driver.get(entry_url)
                except Exception as exc:
                    if not _driver_connection_lost(exc) or not self._recover_driver_locked(
                        launch_if_missing=True,
                        reason="queda ao abrir a tela do TOA",
                    ):
                        raise
                    self._driver.get(entry_url)
                time.sleep(2)
                if not authenticated(self._driver):
                    if not login_visible(self._driver):
                        raise RuntimeError("A tela de login do TOA nao foi localizada")
                    self._fill_credentials_locked(login, secret)
                    self._click_login_locked()
                    self._wait_authenticated()
                now = self._now()
                self._update_state(
                    configured=True,
                    connected=True,
                    authenticated=True,
                    current_url=str(self._driver.current_url or ""),
                    last_check=now,
                    last_connected_at=now,
                    last_error="",
                    access_mode=mode,
                )
                return self.public_state()
            finally:
                secret = ""
                self._update_state(busy=False)

    def _collector_source_locked(self) -> str:
        if self._collector_source is None:
            self._collector_source = self.collector_path.read_text(encoding="utf-8")
        return self._collector_source

    def _install_collector_preload_locked(self) -> None:
        if self._collector_preload_id:
            return
        result = self._driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": self._collector_source_locked()},
        )
        self._collector_preload_id = str(result.get("identifier") or "")
        if not self._collector_preload_id:
            raise RuntimeError("O Chrome nao confirmou a persistencia do TECHCAP")

    def _inject_collector_locked(self) -> None:
        self._install_collector_preload_locked()
        loaded = self._driver.execute_script(
            "return Boolean(window.TECHCAP && window.TECHCAP.state "
            "&& window.TECHCAP.state.version === '5.6-queue');"
        )
        if loaded:
            return
        self._driver.execute_script(self._collector_source_locked())
        loaded = self._driver.execute_script("return Boolean(window.TECHCAP);")
        if not loaded:
            raise RuntimeError("O TECHCAP V5.6 nao iniciou dentro do TOA")

    def _queue_row_locked(self, contract: str) -> dict[str, Any] | None:
        value = self._driver.execute_script(
            "if (!window.TECHCAP || typeof window.TECHCAP.queueList !== 'function') "
            "return null;"
            "return window.TECHCAP.queueList().find("
            "item => String(item.contract) === String(arguments[0])) || null;",
            contract,
        )
        return value if isinstance(value, dict) else None

    def _resume_pending_queue_locked(self, row: dict[str, Any] | None) -> None:
        if not row or row.get("status") != "pending":
            return
        self._driver.execute_script(
            "if (window.TECHCAP && !window.TECHCAP.automationState.running) "
            "window.TECHCAP.startQueue();"
        )

    def _start_single_lookup_locked(self, contract: str) -> None:
        """Start an isolated lookup without deleting the accumulated batch."""
        self._driver.execute_script(
            "if (!window.TECHCAP || "
            "typeof window.TECHCAP.clearQueue !== 'function') "
            "throw new Error('TECHCAP queue unavailable');"
            "window.TECHCAP.clearQueue('APAGAR');"
            "window.TECHCAP.addContracts(arguments[0], '');"
            "window.TECHCAP.startQueue();",
            contract,
        )

    def _storage_locked(self) -> dict[str, Any]:
        value = self._driver.execute_script(
            "const raw = localStorage.getItem(arguments[0]);"
            "return raw ? JSON.parse(raw) : null;",
            BATCH_STORAGE_KEY,
        )
        if not isinstance(value, dict):
            raise ValueError("O TECHCAP nao salvou o lote capturado")
        return value

    def _persist_capture(self, contract: str, payload: dict[str, Any]) -> Path:
        day_root = self.capture_root / dt.date.today().strftime("%Y%m%d")
        day_root.mkdir(parents=True, exist_ok=True)
        aid = str(payload["os_list"][0].get("aid", "sem-aid"))
        stamp = dt.datetime.now().strftime("%H%M%S")
        path = day_root / f"toa-live-{contract}-{aid}-{stamp}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    @staticmethod
    def _inventory_item(item: object) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        allowed = (
            "invid",
            "inventory_id",
            "serial",
            "material_code",
            "code",
            "description",
            "equipment_type",
            "type",
            "model",
            "quantity",
            "unit",
            "pool",
            "kind",
        )
        return {
            key: item.get(key)
            for key in allowed
            if item.get(key) not in (None, "")
        }

    @classmethod
    def _inventory_items(cls, values: object) -> list[dict[str, Any]]:
        if not isinstance(values, list):
            return []
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in values:
            item = cls._inventory_item(value)
            if not item:
                continue
            identity = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if identity in seen:
                continue
            seen.add(identity)
            result.append(item)
        return result

    @staticmethod
    def _task_item(task: object) -> dict[str, Any] | None:
        if not isinstance(task, dict):
            return None
        allowed = ("index", "os_number", "status", "close_code")
        result = {
            key: task.get(key)
            for key in allowed
            if task.get(key) not in (None, "")
        }
        return result or None

    def _persist_inventory_ledger(
        self,
        contract: str,
        results: list[dict[str, Any]],
    ) -> Path:
        day_root = self.capture_root / dt.date.today().strftime("%Y%m%d")
        day_root.mkdir(parents=True, exist_ok=True)
        path = day_root / "toa-window-inventory.json"
        now = self._now()
        with self._inventory_ledger_lock:
            try:
                ledger = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                ledger = {}
            if not isinstance(ledger, dict):
                ledger = {}
            contracts = ledger.get("contracts")
            if not isinstance(contracts, dict):
                contracts = {}
            contract_entry = contracts.get(contract)
            if not isinstance(contract_entry, dict):
                contract_entry = {"contract": contract, "activities": {}}
            activities = contract_entry.get("activities")
            if not isinstance(activities, dict):
                activities = {}

            for position, capture in enumerate(results):
                if not isinstance(capture, dict):
                    continue
                aid = str(capture.get("aid") or "").strip()
                activity_key = aid or f"sem-aid-{position + 1}"
                tasks = [
                    task
                    for task in (
                        self._task_item(value) for value in (capture.get("tasks") or [])
                    )
                    if task
                ]
                activities[activity_key] = {
                    "aid": aid,
                    "contract": str(capture.get("contract") or contract),
                    "scheduled_date": str(capture.get("scheduled_date") or ""),
                    "service_window": str(capture.get("service_window") or ""),
                    "work_type": str(capture.get("work_type") or ""),
                    "activity_status": str(capture.get("activity_status") or ""),
                    "technician_observation": str(
                        capture.get("technician_observation") or ""
                    ),
                    "tasks": tasks,
                    "installed_equipment": self._inventory_items(
                        capture.get("installed_equipment")
                    ),
                    "removed_equipment": self._inventory_items(
                        capture.get("removed_equipment")
                    ),
                    "materials": self._inventory_items(capture.get("materials")),
                    "collected_at": now,
                }

            contract_entry["activities"] = activities
            contract_entry["last_collected_at"] = now
            contracts[contract] = contract_entry
            ledger.update({
                "schema": "dominium.toa.window-inventory.v1",
                "date": dt.date.today().isoformat(),
                "updated_at": now,
                "contracts": contracts,
            })
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(ledger, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
        return path

    def lookup_contract(
        self,
        contract: object,
        *,
        _recovery_attempted: bool = False,
    ) -> dict[str, Any]:
        wanted = _digits(contract)
        if not re.fullmatch(r"\d{5,18}", wanted):
            raise ValueError("Informe um contrato com 5 a 18 digitos")

        with self._driver_lock:
            self._update_state(busy=True, last_contract=wanted, last_error="")
            started = time.monotonic()
            try:
                self._ensure_session_locked()
                self._inject_collector_locked()
                self._start_single_lookup_locked(wanted)

                deadline = time.monotonic() + LOOKUP_TIMEOUT_SECONDS
                row: dict[str, Any] | None = None
                last_url = str(self._driver.current_url or "")
                while time.monotonic() < deadline:
                    self._inject_collector_locked()
                    row = self._queue_row_locked(wanted)
                    current_url = str(self._driver.current_url or "")
                    if current_url != last_url:
                        self.logger.info(
                            "TOA ao vivo: navegacao detectada; retomando contrato %s",
                            wanted,
                        )
                        last_url = current_url
                    self._resume_pending_queue_locked(row)
                    if row and row.get("status") in {"done", "not-found", "error"}:
                        break
                    time.sleep(0.75)
                if not row:
                    raise TimeoutError("O TECHCAP nao iniciou a pesquisa do contrato")
                if row.get("status") != "done":
                    message = str(row.get("message") or "Contrato nao localizado no TOA")
                    raise ValueError(message)

                payload = capture_payload_from_storage(self._storage_locked(), wanted)
                lot = TOACaptureLot.from_dict(payload)
                results = lot.review_contracts([wanted])
                path = self._persist_capture(wanted, payload)
                inventory_ledger = self._persist_inventory_ledger(wanted, results)
                now = self._now()
                self._update_state(
                    connected=True,
                    authenticated=True,
                    current_url=str(self._driver.current_url or ""),
                    last_check=now,
                    last_lookup_at=now,
                    last_contract=wanted,
                    last_error="",
                )
                self.logger.info(
                    "TOA ao vivo: contrato %s capturado em %.1fs (%s)",
                    wanted,
                    time.monotonic() - started,
                    path.name,
                )
                return {
                    "ok": True,
                    "source": "toa_live",
                    "contract": wanted,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "capture_file": str(path.relative_to(self.root)).replace("\\", "/"),
                    "inventory_ledger_file": str(
                        inventory_ledger.relative_to(self.root)
                    ).replace("\\", "/"),
                    "session": self.public_state(),
                    "results": results,
                    "imperium_write_enabled": False,
                }
            except Exception as exc:
                if not _recovery_attempted and _driver_connection_lost(exc):
                    self.logger.warning(
                        "TOA ao vivo: conexao Selenium caiu durante contrato %s; recuperando",
                        wanted,
                    )
                    if self._recover_driver_locked(
                        launch_if_missing=True,
                        reason=f"queda durante consulta do contrato {wanted}",
                    ):
                        self._ensure_session_locked()
                        return self.lookup_contract(
                            wanted,
                            _recovery_attempted=True,
                        )
                self._update_state(last_error=str(exc), last_check=self._now())
                raise
            finally:
                self._update_state(busy=False)
