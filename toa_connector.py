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
"""API local, sanitizada e somente leitura para dados operacionais do TOA.

O conector reutiliza exclusivamente a sessao de navegador que o operador abriu
e autenticou. Ele nao armazena senha, cookie, token, cabecalho de autorizacao ou
dados pessoais do cliente. A saida publica contem apenas informacao operacional
necessaria ao DOMINIUM.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any

from toa_capture import TOACaptureLot
from toa_cloud_client import TOACloudClient


SCHEMA_VERSION = "dominium-toa-v1"
CONTRACT_PATTERN = re.compile(r"\d{5,18}")


def _digits(value: object) -> str:
    return "".join(re.findall(r"\d", str(value or "")))


def _text(value: object) -> str:
    return str(value if value is not None else "").strip()


def _repair_text(value: object) -> str:
    """Repair the common UTF-8-as-Latin-1 mojibake emitted by legacy captures."""
    text = _text(value)
    if not text or not any(marker in text for marker in ("Ã", "Â", "â")):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _timestamp(value: object) -> str:
    raw = _text(value)
    if not raw:
        return ""
    return raw.replace(" ", "T", 1)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _provider(value: object) -> dict[str, str]:
    provider = value if isinstance(value, dict) else {}
    external_id = _text(
        provider.get("external_id")
        or provider.get("login")
        or provider.get("user_id")
    )
    return {
        "id": _text(provider.get("id")),
        "login": external_id,
        "name": _repair_text(provider.get("name")),
    }


def _task(value: object) -> dict[str, str]:
    task = value if isinstance(value, dict) else {}
    return {
        "index": _text(task.get("index")),
        "os_number": _digits(task.get("os_number")),
        "status": _text(task.get("status")),
        "close_code": _text(task.get("close_code")),
    }


def _inventory_item(value: object) -> dict[str, Any]:
    item = value if isinstance(value, dict) else {}
    return {
        "inventory_id": _text(item.get("invid")),
        "kind": _text(item.get("kind")),
        "pool": _text(item.get("pool")),
        "action_code": _text(item.get("action_code")),
        "material_code": _text(item.get("material_code")),
        "description": _repair_text(
            item.get("description") or item.get("name") or item.get("type")
        ),
        "serial": _text(item.get("serial")),
        "quantity": item.get("quantity"),
    }


def _activity(value: object) -> dict[str, Any]:
    activity = value if isinstance(value, dict) else {}
    tasks = [_task(item) for item in activity.get("tasks", [])]
    tasks = [item for item in tasks if item["os_number"]]
    return {
        "activity_id": _text(activity.get("aid")),
        "contract": _digits(activity.get("contract")),
        "appointment_number": _text(activity.get("appointment_number")),
        "scheduled_date": _text(activity.get("scheduled_date")),
        "service_window": _text(activity.get("service_window")),
        "start_time": _timestamp(activity.get("start_time")),
        "end_time": _timestamp(activity.get("end_time")),
        "city": _repair_text(activity.get("city")),
        "work_type": _repair_text(activity.get("work_type")),
        "status": _text(activity.get("activity_status")),
        "technician": _provider(activity.get("assigned_technician")),
        "technician_observation": _repair_text(
            activity.get("technician_observation")
        ),
        "tasks": tasks,
        "close_codes": _unique(
            [_text(item.get("close_code")) for item in tasks]
        ),
        "equipment": {
            "installed": [
                _inventory_item(item)
                for item in activity.get("installed_equipment", [])
            ],
            "removed": [
                _inventory_item(item)
                for item in activity.get("removed_equipment", [])
            ],
            "customer": [
                _inventory_item(item)
                for item in activity.get("customer_equipment", [])
            ],
        },
        "materials": [
            _inventory_item(item) for item in activity.get("materials", [])
        ],
        "classification": _text(
            activity.get("operational_classification")
        ),
        "validation": {
            "decision": _text(activity.get("decision")),
            "errors": list(activity.get("validation_errors") or ()),
            "warnings": list(activity.get("validation_warnings") or ()),
            "reasons": list(activity.get("decision_reasons") or ()),
        },
    }


def _document(
    contract: str,
    activities: list[dict[str, Any]],
    *,
    source: str,
    observed_at: str,
    stale: bool,
    warning: str = "",
) -> dict[str, Any]:
    os_numbers = _unique([
        task["os_number"]
        for activity in activities
        for task in activity["tasks"]
    ])
    close_codes = _unique([
        code for activity in activities for code in activity["close_codes"]
    ])
    statuses = _unique([activity["status"] for activity in activities])
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "contract": contract,
        "source": source,
        "freshness": {
            "observed_at": observed_at,
            "served_at": dt.datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "stale": stale,
            "warning": warning,
        },
        "summary": {
            "activity_count": len(activities),
            "os_count": len(os_numbers),
            "os_numbers": os_numbers,
            "close_codes": close_codes,
            "statuses": statuses,
        },
        "activities": activities,
        "privacy": {
            "customer_personal_data_included": False,
            "credentials_persisted": False,
        },
        "read_only": True,
    }


class TOAConnector:
    """Stable facade over live TECHCAP capture plus a sanitized local cache."""

    def __init__(
        self,
        root: Path,
        live_session: Any,
        cloud_client: TOACloudClient | None = None,
    ) -> None:
        self.root = root.resolve()
        self.live_session = live_session
        self.cloud_client = cloud_client or TOACloudClient.from_environment(
            self.root / "config" / "toa_cloud_bridge_credentials.dat"
        )
        self.cache_root = self.root / "logs" / "toa-api-cache"
        self.capture_root = self.root / "logs" / "toa-captures"
        self._locks_guard = threading.RLock()
        self._contract_locks: dict[str, threading.Lock] = {}

    def _contract(self, value: object) -> str:
        contract = _digits(value)
        if not CONTRACT_PATTERN.fullmatch(contract):
            raise ValueError("Informe um contrato com 5 a 18 digitos")
        return contract

    def _lock_for(self, contract: str) -> threading.Lock:
        with self._locks_guard:
            return self._contract_locks.setdefault(contract, threading.Lock())

    def _cache_path(self, contract: str) -> Path:
        return self.cache_root / f"{contract}.json"

    def _persist(self, contract: str, document: dict[str, Any]) -> None:
        self.cache_root.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(contract)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _load_cache(self, contract: str) -> dict[str, Any] | None:
        path = self._cache_path(contract)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != SCHEMA_VERSION
            or document.get("contract") != contract
        ):
            return None
        cached = copy.deepcopy(document)
        cached["source"] = "toa_cache"
        freshness = cached.setdefault("freshness", {})
        freshness["served_at"] = dt.datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        freshness["stale"] = True
        return cached

    def _latest_capture(self, contract: str) -> Path | None:
        candidates = list(
            self.capture_root.rglob(f"toa-live-{contract}-*.json")
        ) if self.capture_root.is_dir() else []
        return max(candidates, key=lambda item: item.stat().st_mtime, default=None)

    def _from_capture(self, contract: str, path: Path) -> dict[str, Any]:
        lot = TOACaptureLot.from_path(path)
        activities = [
            _activity(item.to_dict()) for item in lot.find_contract(contract)
        ]
        if not activities:
            raise ValueError(f"O lote nao contem o contrato {contract}")
        observed_at = _text(lot.metadata.get("exportedAt"))
        return _document(
            contract,
            activities,
            source="toa_capture",
            observed_at=observed_at,
            stale=True,
        )

    def _from_live(self, contract: str, result: dict[str, Any]) -> dict[str, Any]:
        activities = [
            _activity(item)
            for item in result.get("results", [])
            if isinstance(item, dict) and item.get("found") is True
        ]
        if not activities:
            raise ValueError(f"O TOA nao retornou atividades do contrato {contract}")
        session = result.get("session") if isinstance(result.get("session"), dict) else {}
        observed_at = _text(session.get("last_lookup_at"))
        return _document(
            contract,
            activities,
            source="toa_live",
            observed_at=observed_at,
            stale=False,
        )

    @staticmethod
    def _cloud_inventory_item(value: object) -> dict[str, Any]:
        item = value if isinstance(value, dict) else {}
        return {
            "inventory_id": _text(item.get("inventory_id") or item.get("invid")),
            "kind": _text(item.get("kind")),
            "pool": _text(item.get("pool")),
            "action_code": _text(item.get("action_code")),
            "material_code": _text(item.get("material_code") or item.get("code")),
            "description": _repair_text(
                item.get("description") or item.get("name") or item.get("type")
            ),
            "serial": _text(item.get("serial")),
            "quantity": item.get("quantity") or item.get("used_quantity"),
        }

    def _from_cloud(self, contract: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        snapshot_contract = _digits(snapshot.get("contract"))
        if snapshot_contract != contract:
            raise ValueError("A ponte TOA retornou um contrato divergente")
        equipment = snapshot.get("equipment")
        equipment = equipment if isinstance(equipment, dict) else {}
        tasks = [
            _task(item) for item in snapshot.get("tasks", [])
            if isinstance(item, dict)
        ]
        tasks = [item for item in tasks if item["os_number"]]
        technician = snapshot.get("technician")
        technician = technician if isinstance(technician, dict) else {}
        validation = snapshot.get("validation")
        validation = validation if isinstance(validation, dict) else {}
        activity = {
            "activity_id": _text(snapshot.get("activity_id")),
            "contract": contract,
            "appointment_number": _text(snapshot.get("appointment_number")),
            "scheduled_date": _text(snapshot.get("scheduled_date")),
            "service_window": _text(snapshot.get("service_window")),
            "start_time": _timestamp(snapshot.get("start_time")),
            "end_time": _timestamp(snapshot.get("end_time")),
            "city": _repair_text(snapshot.get("city")),
            "work_type": _repair_text(snapshot.get("activity_type")),
            "status": _text(snapshot.get("status")),
            "technician": {
                "id": _text(technician.get("id")),
                "login": _text(technician.get("login")),
                "name": _repair_text(technician.get("name")),
            },
            "technician_observation": _repair_text(
                snapshot.get("technician_observation")
            ),
            "tasks": tasks,
            "close_codes": _unique(
                [_text(code) for code in snapshot.get("close_codes", [])]
                + [_text(item.get("close_code")) for item in tasks]
            ),
            "equipment": {
                "installed": [
                    self._cloud_inventory_item(item)
                    for item in equipment.get("installed", [])
                ],
                "removed": [
                    self._cloud_inventory_item(item)
                    for item in equipment.get("removed", [])
                ],
                "customer": [
                    self._cloud_inventory_item(item)
                    for item in equipment.get("customer", [])
                ],
            },
            "materials": [
                self._cloud_inventory_item(item)
                for item in snapshot.get("materials", [])
            ],
            "classification": _text(snapshot.get("classification")),
            "validation": {
                "decision": _text(validation.get("decision")),
                "errors": list(validation.get("errors") or ()),
                "warnings": list(validation.get("warnings") or ()),
                "reasons": list(validation.get("reasons") or ()),
            },
        }
        return _document(
            contract,
            [activity],
            source="toa_cloud",
            observed_at=_text(snapshot.get("captured_at")),
            stale=False,
        )

    def status(self) -> dict[str, Any]:
        session = self.live_session.public_state()
        cache_count = len(list(self.cache_root.glob("*.json"))) if self.cache_root.is_dir() else 0
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "read_only": True,
            "live": {
                "connected": bool(session.get("connected")),
                "authenticated": bool(session.get("authenticated")),
                "busy": bool(session.get("busy")),
                "last_check": _text(session.get("last_check")),
                "last_lookup_at": _text(session.get("last_lookup_at")),
            },
            "cloud": self.cloud_client.public_state(),
            "cache": {"enabled": True, "contract_count": cache_count},
            "privacy": {
                "customer_personal_data_included": False,
                "credentials_persisted": False,
            },
        }

    def lookup(
        self,
        value: object,
        *,
        refresh: bool = True,
        allow_stale: bool = True,
    ) -> dict[str, Any]:
        contract = self._contract(value)
        lock = self._lock_for(contract)
        if not lock.acquire(timeout=5):
            raise RuntimeError(f"O contrato {contract} ja esta sendo atualizado")
        try:
            live_error = ""
            if refresh:
                if self.cloud_client.configured:
                    try:
                        document = self._from_cloud(
                            contract,
                            self.cloud_client.lookup_contract(contract),
                        )
                        self._persist(contract, document)
                        return document
                    except Exception as exc:
                        live_error = "Ponte Cloudflare: " + _repair_text(exc)
                try:
                    document = self._from_live(
                        contract,
                        self.live_session.lookup_contract(contract),
                    )
                    self._persist(contract, document)
                    return document
                except Exception as exc:
                    local_error = _repair_text(exc)
                    live_error = " | ".join(
                        value for value in (live_error, local_error) if value
                    )
                    if not allow_stale:
                        raise

            cached = self._load_cache(contract)
            if cached is not None:
                if live_error:
                    cached["freshness"]["warning"] = (
                        "Atualizacao ao vivo indisponivel; exibindo ultimo retrato: "
                        + live_error
                    )
                return cached

            capture = self._latest_capture(contract)
            if capture is not None:
                document = self._from_capture(contract, capture)
                if live_error:
                    document["freshness"]["warning"] = (
                        "Atualizacao ao vivo indisponivel; exibindo captura local: "
                        + live_error
                    )
                self._persist(contract, document)
                return document

            if live_error:
                raise RuntimeError(live_error)
            raise ValueError(f"Nenhum dado local encontrado para o contrato {contract}")
        finally:
            lock.release()

    @staticmethod
    def openapi_document() -> dict[str, Any]:
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "DOMINIUM TOA Connector",
                "version": "1.0.0",
                "description": (
                    "Consulta local e somente leitura de dados operacionais que "
                    "a sessao autorizada do TOA disponibiliza ao operador."
                ),
            },
            "servers": [{"url": "http://127.0.0.1:8765/api/toa/v1"}],
            "paths": {
                "/status": {"get": {"summary": "Estado do conector"}},
                "/contracts/{contract}": {
                    "get": {
                        "summary": "Consulta operacional por contrato",
                        "parameters": [
                            {
                                "name": "contract",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string", "pattern": "^[0-9]{5,18}$"},
                            },
                            {
                                "name": "refresh",
                                "in": "query",
                                "schema": {"type": "boolean", "default": True},
                            },
                            {
                                "name": "allow_stale",
                                "in": "query",
                                "schema": {"type": "boolean", "default": True},
                            },
                        ],
                        "responses": {"200": {"description": "Contrato encontrado"}},
                    }
                },
            },
        }
