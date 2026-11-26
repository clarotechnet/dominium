from __future__ import annotations

import datetime as dt
import json
import logging
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from adhesion_technician_evidence import has_no_adhesion_movements, is_unproductive_task

DEBUG_PORT = 9341
TOA_HOSTS = {
    "clarobrasil.etadirect.com",
    "clarobrasil.fs.ocs.oraclecloud.com",
}
LOOKUP_TIMEOUT_SECONDS = 90
BUSY_RETRY_DELAYS = (0.4, 0.8, 1.2, 1.6, 2.0)
BUSY_ERROR_CODE = "toa_consulta_em_andamento"


class TOASecondaryBusyError(RuntimeError):
    """The shared TOA page is already servicing another direct lookup."""



def _digits(value: object) -> str:
    return "".join(re.findall(r"\d", str(value or "")))


def _text(value: object) -> str:
    return str(value or "").strip()

def _targets(port: int = DEBUG_PORT) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json",
            timeout=1.0,
        ) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _toa_page() -> dict[str, Any] | None:
    for item in _targets():
        try:
            host = (urlsplit(_text(item.get("url"))).hostname or "").casefold()
        except ValueError:
            continue
        if item.get("type") == "page" and host in TOA_HOSTS:
            return item
    return None


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")

def _confirmed_adhesion_provider(value: dict, capture: dict, adhesion_date: str) -> dict | None:
    """Reconcile a historical assignment only with evidence from the completed activity."""
    if (not adhesion_date or capture.get("scheduled_date") != adhesion_date
            or capture.get("route_name") not in {"NTL-DMV", "PWM-DMV"}
            or _text(capture.get("activity_status")).lower() not in {"complete", "completed"}
            or capture.get("validation_errors") or capture.get("operation_blockers")):
        return None
    normalized = value.get("normalizedCapture")
    responsibility = normalized.get("responsibility") if isinstance(normalized, dict) else None
    search = value.get("searchRow")
    if not isinstance(responsibility, dict) or not isinstance(search, dict):
        return None
    current = responsibility.get("route_provider")
    historical = responsibility.get("assigned_technician")
    if not isinstance(current, dict) or not isinstance(historical, dict):
        return None
    pid = _text(current.get("id"))
    login = _text(current.get("external_id")).upper()
    name = _text(current.get("name"))
    if (not pid.isdecimal() or not re.fullmatch(r"Z\d+", login) or len(name.split()) < 2
            or not _text(historical.get("id")).isdecimal() or _text(historical.get("id")) == pid
            or _text(historical.get("external_id")).upper() != login
            or _text(historical.get("name")).casefold() == name.casefold()
            or _text(search.get("pid")) != pid or _text(search.get("external_id")).upper() != login
            or _text(search.get("date")) != adhesion_date or _text(value.get("pid")) != pid
            or _text(value.get("externalId")).upper() != login
            or _text(value.get("tecnico")).casefold() != name.casefold()):
        return None
    inventory = responsibility.get("inventory_providers")
    forms = responsibility.get("form_submitters")
    if not isinstance(inventory, list) or not isinstance(forms, list) or not forms:
        return None
    if not inventory:
        tasks = normalized.get("tasks")
        if (not isinstance(tasks, list) or not tasks or not all(is_unproductive_task(task) for task in tasks)
                or not has_no_adhesion_movements(normalized)):
            return None
    if not all(isinstance(item, dict) and _text(item.get("id")) == pid
               and _text(item.get("external_id")).upper() == login
               and _text(item.get("name")).casefold() == name.casefold() for item in inventory):
        return None
    if not all(isinstance(form, dict) and _text(form.get("provider_id")) == pid
               and _text(form.get("user_name")).casefold() == name.casefold() for form in forms):
        return None
    return {"id": pid, "name": name, "external_id": login}


class TOASecondarySession:
    """Read-only bridge to the TOA already open in the bot Chrome."""

    def __init__(self, root: Path, *, logger: logging.Logger | None = None) -> None:
        self.root = root.resolve()
        self.logger = logger or logging.getLogger("imperium")
        self.lookup_script = self.root / "toa_secondary_direct_lookup.mjs"
        self._last_lookup_at = ""
        self._last_contract = ""
        self._last_error = ""

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def public_state(self) -> dict[str, Any]:
        page = _toa_page()
        connected = page is not None
        return {
            "ok": True,
            "configured": connected,
            "running": True,
            "connected": connected,
            "authenticated": connected,
            "busy": False,
            "current_url": _text(page.get("url")) if page else "",
            "last_check": _now(),
            "last_connected_at": _now() if connected else "",
            "last_lookup_at": self._last_lookup_at,
            "last_contract": self._last_contract,
            "last_error": self._last_error if connected else "TOA secundario nao localizado",
            "live_lookup_enabled": self.lookup_script.is_file(),
            "imperium_write_enabled": False,
            "credentials_persisted": False,
            "manual_login": False,
            "shared_bot_session": True,
            "browser_launch_enabled": False,
            "transport": "secondary_chrome_cdp",
            "debug_port": DEBUG_PORT,
        }

    def open_session(self, username: object = "", password: object = "", access_mode: object = "direct") -> dict[str, Any]:
        del username, password, access_mode
        state = self.public_state()
        if not state["connected"]:
            raise RuntimeError("O TOA secundario ja aberto pelo bot nao foi localizado")
        return state
    def _direct_lookup(self, contract: str, *, adhesion_date: str = "") -> dict[str, Any]:
        if not self.lookup_script.is_file():
            raise RuntimeError("Ponte CDP do TOA secundario nao localizada")

        arguments = ["node", str(self.lookup_script), contract]
        if adhesion_date:
            arguments.append(adhesion_date)
        completed: subprocess.CompletedProcess[str] | None = None
        for attempt in range(len(BUSY_RETRY_DELAYS) + 1):
            completed = subprocess.run(
                arguments,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=LOOKUP_TIMEOUT_SECONDS,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode == 0:
                break

            detail = (
                completed.stderr
                or completed.stdout
                or "Falha na consulta TOA"
            ).strip()
            if BUSY_ERROR_CODE not in detail:
                raise RuntimeError(detail[-1000:])
            if attempt >= len(BUSY_RETRY_DELAYS):
                raise TOASecondaryBusyError(detail[-1000:])

            delay = BUSY_RETRY_DELAYS[attempt]
            self.logger.info(
                "TOA secundario ocupado; contrato %s sera tentado novamente "
                "em %.1fs (%s/%s)",
                contract,
                delay,
                attempt + 1,
                len(BUSY_RETRY_DELAYS),
            )
            time.sleep(delay)

        if completed is None:
            raise RuntimeError("Falha na consulta TOA")
        try:
            value = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError("Resposta invalida da extensao TOA") from exc
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise ValueError(
                _text(value.get("error") if isinstance(value, dict) else "")
                or "Contrato nao localizado no TOA"
            )
        return value
    @staticmethod
    def _capture(value: dict[str, Any]) -> dict[str, Any]:
        normalized = value.get("normalizedCapture")
        normalized = normalized if isinstance(normalized, dict) else {}
        activity = normalized.get("activity")
        activity = activity if isinstance(activity, dict) else {}
        validation = normalized.get("validation")
        validation = validation if isinstance(validation, dict) else {}
        responsibility = normalized.get("responsibility")
        responsibility = responsibility if isinstance(responsibility, dict) else {}
        route_provider = responsibility.get("route_provider")
        route_provider = route_provider if isinstance(route_provider, dict) else {}
        technician_name = _text(value.get("tecnico")) or _text(route_provider.get("name"))
        technician_external_id = _text(value.get("externalId")) or _text(route_provider.get("external_id"))
        tasks = normalized.get("tasks") if isinstance(normalized.get("tasks"), list) else value.get("tasks", [])
        installed = normalized.get("installed_equipment") if isinstance(normalized.get("installed_equipment"), list) else value.get("installedEquipment", [])
        removed = normalized.get("removed_equipment") if isinstance(normalized.get("removed_equipment"), list) else value.get("removedEquipment", [])
        customer = normalized.get("customer_equipment") if isinstance(normalized.get("customer_equipment"), list) else value.get("customerEquipment", [])
        materials = normalized.get("materials") if isinstance(normalized.get("materials"), list) else value.get("materialsRaw", [])
        return {
            "found": True,
            "contract": _text(value.get("contrato")) or _text(normalized.get("contract")),
            "aid": _text(value.get("aid")) or _text(activity.get("aid")),
            "city": _text(value.get("cidade")),
            "work_type": _text(value.get("tipoOS")) or _text(activity.get("work_type")),
            "activity_status": _text(value.get("status")) or _text(activity.get("status")),
            "scheduled_date": _text(value.get("date")) or _text(activity.get("scheduled_date")),
            "observation": _text(value.get("observacao")),
            "tasks": tasks,
            "installed_equipment": installed,
            "removed_equipment": removed,
            "customer_equipment": customer,
            "materials": materials,
            "assigned_technician": {
                "external_id": technician_external_id,
                "name": technician_name,
            },
            "validation_errors": list(validation.get("errors") or ()),
            "validation_warnings": list(validation.get("warnings") or ()),
            "route_name": _text((value.get("searchRow") or {}).get("route_name") if isinstance(value.get("searchRow"), dict) else ""),
        }
    def lookup_contract(self, contract: object, *, adhesion_date: str = "") -> dict[str, Any]:
        wanted = _digits(contract)
        if not re.fullmatch(r"\d{5,18}", wanted):
            raise ValueError("Informe um contrato com 5 a 18 digitos")
        if _toa_page() is None:
            self._last_error = "TOA secundario nao localizado"
            raise RuntimeError(self._last_error)
        try:
            direct = self._direct_lookup(wanted, adhesion_date=adhesion_date) if adhesion_date else self._direct_lookup(wanted)
            capture = self._capture(direct)
            if capture["contract"] != wanted:
                raise ValueError("A resposta do TOA nao corresponde ao contrato pesquisado")
            provider = _confirmed_adhesion_provider(direct, capture, adhesion_date)
            if provider is not None:
                capture["assigned_technician"] = provider
                capture["route_provider"] = provider
            self._last_contract = wanted
            self._last_lookup_at = _now()
            self._last_error = ""
            self.logger.info(
                "TOA secundario: contrato %s consultado via Chrome CDP %s",
                wanted,
                DEBUG_PORT,
            )
            return {
                "ok": True,
                "source": "toa_secondary_chrome_cdp",
                "contract": wanted,
                "results": [capture],
                "session": self.public_state(),
                "imperium_write_enabled": False,
            }
        except Exception as exc:
            self._last_error = str(exc)
            raise
