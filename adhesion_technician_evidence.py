"""Short-lived TOA evidence for the exact Natal adhesion order."""

import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath


# Verified against the current TOA executor and the Imperium stock record.
_IMPERIUM_STOCK_NAMES = {
    ("338736", "Z657807", "ESLI MELQUISEDEQUE DA SILVA"): "ESLI MELQUISEDEQUI DA SILVA",
    ("249803", "Z660888", "SOMERREGILSON DA SILVA MEDEIROS"): "SONERREGILSON DA SILVA MEDEIROS",
}


def _name(value):
    value = unicodedata.normalize("NFKD", str(value or "").upper())
    return " ".join("".join(ch for ch in value if not unicodedata.combining(ch)).split())


def is_unproductive_task(task):
    return (isinstance(task, dict) and str(task.get("status")).upper() == "N"
            and re.fullmatch(r"\d{3}", str(task.get("close_code") or "")) is not None)


def has_no_adhesion_movements(capture):
    return all(capture.get(field) == [] for field in ("installed_equipment", "removed_equipment", "materials"))


def _is_executed_task(task):
    return str(task.get("status")).upper() in {"E", "EXECUTED", "EXECUTADA", "EXECUTADO"}


@dataclass(frozen=True)
class _Evidence:
    captured_at: float
    login: str
    name: str
    id_os: str
    can_resolve_login: bool
    installed_serials: frozenset[str]


class AdhesionTechnicianEvidence:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._records = {}
        self._lock = threading.Lock()

    def record(self, profile, result):
        source = result.get("source")
        if profile != "natal" or source not in {"toa_secondary_chrome_cdp", "toa_cloud"}:
            return
        contract = str(result.get("contract") or "")
        if not re.fullmatch(r"\d{5,18}", contract):
            return
        records = {}
        ambiguous = set()
        now = self._clock()
        for capture in result.get("results") or ():
            if not isinstance(capture, dict) or str(capture.get("contract")) != contract:
                continue
            activity = str(capture.get("aid") or "")
            date = str(capture.get("scheduled_date") or "")[:10]
            assigned = capture.get("assigned_technician") or {}
            provider = capture.get("route_provider") or {}
            if not isinstance(assigned, dict) or not isinstance(provider, dict):
                continue
            login = str(assigned.get("external_id") or "").upper()
            name = _name(assigned.get("name"))
            if source == "toa_cloud":
                route = str(provider.get("name") or "").upper()
                provider_confirmed = bool(assigned.get("id")) and capture.get("decision") == "candidate_after_validation"
            else:
                route = str(capture.get("route_name") or capture.get("route") or "").upper()
                provider_confirmed = bool(assigned.get("id")) and str(assigned["id"]) == str(provider.get("id"))
            if (route not in {"NTL-DMV", "PWM-DMV"} or not activity or not provider_confirmed
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
                    or not re.fullmatch(r"Z\d+", login) or len(name.split()) < 2
                    or str(capture.get("activity_status")).lower() not in {"complete", "completed", "concluido"}
                    or capture.get("validation_errors") or capture.get("operation_blockers")):
                continue
            no_movements = has_no_adhesion_movements(capture)
            tasks = [task for task in capture.get("tasks") or ()
                     if isinstance(task, dict) and not task.get("imperium_only") and not task.get("registry_only")
                     and task.get("source") != "imperium_contract_status"
                     and (_is_executed_task(task) or (no_movements and is_unproductive_task(task)))]
            installed_serials = frozenset(
                str(item["serial"]).strip().upper()
                for item in capture.get("installed_equipment") or ()
                if isinstance(item, dict) and item.get("serial")
            )
            for order in capture.get("imperium_matches") or ():
                if not isinstance(order, dict):
                    continue
                number = str(order.get("num_os") or "")
                exact_tasks = [task for task in tasks if str(task.get("os_number") or "") == number]
                if (not number or len(exact_tasks) != 1 or str(order.get("contract")) != contract
                        or order.get("operation_blockers")):
                    continue
                source_scope = order.get("import_scope") or {}
                identity = order.get("operation_identity") or {}
                manual_scope = order.get("manual_scope") or {}
                if not all(isinstance(scope, dict) for scope in (source_scope, identity, manual_scope)):
                    continue
                filename = PurePosixPath(str(source_scope.get("source_file") or "").replace("\\", "/")).name
                yy, mm, dd = date[2:].split("-")
                imported = (
                    order.get("operation_source") == "toa_import"
                    and str(identity.get("contract")) == contract
                    and identity.get("profile_key") == profile
                    and str(identity.get("activity_id")) == activity
                    and source_scope.get("source_hash")
                    and source_scope.get("expected_profile_key") == profile
                    and re.fullmatch(rf"Atividades-{route}_{dd}_{mm}_{yy}(?: \(\d+\))?\.(?:csv|xlsx)", filename, re.I)
                )
                cached = (
                    order.get("operation_source") == "imperium_cache"
                    and manual_scope.get("profile_key") == profile
                    and manual_scope.get("cache_date") == date
                    and order.get("approved_state_hash")
                    and str(order.get("status")).upper() == "EM CAMPO"
                )
                task = exact_tasks[0]
                serials = installed_serials if (
                    (imported or cached) and _is_executed_task(task)
                    and str(task.get("close_code")) == "409"
                    and capture.get("materials_complete") is not False
                ) else frozenset()
                can_resolve_login = bool(imported and source == "toa_secondary_chrome_cdp")
                if not (can_resolve_login or serials):
                    continue
                key = (contract, number, date)
                if key in records:
                    ambiguous.add(key)
                records[key] = _Evidence(now, login, name, str(order.get("id_os") or ""), can_resolve_login, serials)
        with self._lock:
            self._records = {key: value for key, value in self._records.items()
                             if key[0] != contract and now - value.captured_at <= 300}
            self._records.update({key: value for key, value in records.items() if key not in ambiguous})

    def matches(self, profile, order, date, supplied, installer_id, get_technicians, *, serial=""):
        if profile != "natal" or not isinstance(supplied, dict) or not installer_id:
            return False
        login = str(supplied.get("external_id") or supplied.get("login") or "").strip().upper()
        name = _name(supplied.get("name"))
        with self._lock:
            recent = [value for value in self._records.values() if self._clock() - value.captured_at <= 300]
            value = self._records.get((str(order.contract), str(order.num_os), date.isoformat()))
            if (value not in recent or (value.login, value.name, value.id_os) != (login, name, str(order.id_os))
                    or any(other.login == login and other.name != name for other in recent)):
                return False
            if (serial and serial not in value.installed_serials) or (not serial and not value.can_resolve_login):
                return False
        technicians = get_technicians()
        same_installer = [row for row in technicians if str(row.get("installer_id")) == str(installer_id)]
        names = {_name(row.get("technician_name")) for row in same_installer}
        expected_stock_name = _IMPERIUM_STOCK_NAMES.get((str(installer_id), login, name))
        if serial and any(
            str(row.get("installer_id")) != str(installer_id)
            and _name(row.get("technician_name")) in {name, expected_stock_name}
            for row in technicians
        ):
            return False
        return names == {name} or (expected_stock_name is not None and names == {expected_stock_name})
