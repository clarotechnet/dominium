from __future__ import annotations

import datetime as dt
import json
import logging
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEBUG_PORT = 9341
TOA_HOSTS = {
    "clarobrasil.etadirect.com",
    "clarobrasil.fs.ocs.oraclecloud.com",
}
LOOKUP_TIMEOUT_SECONDS = 90


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
    def _direct_lookup(self, contract: str) -> dict[str, Any]:
        if not self.lookup_script.is_file():
            raise RuntimeError("Ponte CDP do TOA secundario nao localizada")
        completed = subprocess.run(
            ["node", str(self.lookup_script), contract],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=LOOKUP_TIMEOUT_SECONDS,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Falha na consulta TOA").strip()
            raise RuntimeError(detail[-1000:])
        try:
            value = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError("Resposta invalida da extensao TOA") from exc
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise ValueError(_text(value.get("error") if isinstance(value, dict) else "") or "Contrato nao localizado no TOA")
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
    def lookup_contract(self, contract: object) -> dict[str, Any]:
        wanted = _digits(contract)
        if not re.fullmatch(r"\d{5,18}", wanted):
            raise ValueError("Informe um contrato com 5 a 18 digitos")
        if _toa_page() is None:
            self._last_error = "TOA secundario nao localizado"
            raise RuntimeError(self._last_error)
        try:
            direct = self._direct_lookup(wanted)
            capture = self._capture(direct)
            if capture["contract"] != wanted:
                raise ValueError("A resposta do TOA nao corresponde ao contrato pesquisado")
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
