"""Short-lived TOA evidence for the exact Natal adhesion order."""

import re
import threading
import time
import unicodedata
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


def matches_imported_unproductive_alias(
    profile, order, date, supplied, installer_id, installer_name, approved_order,
):
    """Resolve a verified spelling difference using the exact imported order."""
    if profile != "natal" or not isinstance(supplied, dict):
        return False
    login = str(supplied.get("external_id") or supplied.get("login") or "").strip().upper()
    signed_login = str(approved_order.get("technician_login") or "").strip().upper()
    signed_name = _name(approved_order.get("technician"))
    stock_name = _IMPERIUM_STOCK_NAMES.get((str(installer_id), login, signed_name))
    current_name = _name(installer_name)
    if not stock_name or login != signed_login or len(current_name) < 12 or not stock_name.startswith(current_name):
        return False
    scope = approved_order.get("import_scope") or {}
    identity = approved_order.get("operation_identity") or {}
    if not isinstance(scope, dict) or not isinstance(identity, dict):
        return False
    filename = PurePosixPath(str(scope.get("source_file") or "").replace("\\", "/")).name
    date_suffix = date.strftime("%d_%m_%y")
    return bool(
        approved_order.get("operation_source") == "toa_import"
        and approved_order.get("approved_state_hash")
        and not approved_order.get("read_only")
        and not approved_order.get("operation_blockers")
        and str(approved_order.get("id_os")) == str(order.id_os)
        and str(approved_order.get("num_os")) == str(order.num_os)
        and str(approved_order.get("contract")) == str(order.contract)
        and str(identity.get("contract")) == str(order.contract)
        and identity.get("activity_id")
        and identity.get("profile_key") == profile
        and scope.get("expected_profile_key") == profile
        and scope.get("source_hash")
        and re.fullmatch(rf"Atividades-(?:NTL|PWM)-DMV_{date_suffix}(?: \(\d+\))?\.(?:csv|xlsx)", filename, re.I)
    )


class AdhesionTechnicianEvidence:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._records = {}
        self._lock = threading.Lock()

    def record(self, profile, result):
        if profile != "natal" or result.get("source") != "toa_secondary_chrome_cdp":
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
            route = str(capture.get("route_name") or capture.get("route") or "").upper()
            date = str(capture.get("scheduled_date") or "")[:10]
            assigned = capture.get("assigned_technician") or {}
            provider = capture.get("route_provider") or {}
            if not isinstance(assigned, dict) or not isinstance(provider, dict):
                continue
            login = str(assigned.get("external_id") or "").upper()
            name = _name(assigned.get("name"))
            if (route not in {"NTL-DMV", "PWM-DMV"} or not activity
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
                    or not assigned.get("id") or str(assigned["id"]) != str(provider.get("id"))
                    or not re.fullmatch(r"Z\d+", login) or len(name.split()) < 2
                    or str(capture.get("activity_status")).lower() not in {"complete", "completed", "concluido"}
                    or capture.get("validation_errors") or capture.get("operation_blockers")):
                continue
            no_movements = has_no_adhesion_movements(capture)
            tasks = [str(task.get("os_number") or "") for task in capture.get("tasks") or ()
                     if isinstance(task, dict) and not task.get("imperium_only") and not task.get("registry_only")
                     and task.get("source") != "imperium_contract_status"
                     and (str(task.get("status")).upper() in {"E", "EXECUTED", "EXECUTADA", "EXECUTADO"}
                          or (no_movements and is_unproductive_task(task)))]
            for order in capture.get("imperium_matches") or ():
                if not isinstance(order, dict):
                    continue
                number = str(order.get("num_os") or "")
                scope = order.get("import_scope") or {}
                identity = order.get("operation_identity") or {}
                if not isinstance(scope, dict) or not isinstance(identity, dict):
                    continue
                filename = PurePosixPath(str(scope.get("source_file") or "").replace("\\", "/")).name
                yy, mm, dd = date[2:].split("-")
                if (tasks.count(number) != 1 or str(order.get("contract")) != contract
                        or order.get("operation_source") != "toa_import" or order.get("operation_blockers")
                        or str(identity.get("contract")) != contract or identity.get("profile_key") != profile
                        or str(identity.get("activity_id")) != activity or not scope.get("source_hash")
                        or scope.get("expected_profile_key") != profile
                        or not re.fullmatch(rf"Atividades-{route}_{dd}_{mm}_{yy}(?: \(\d+\))?\.(?:csv|xlsx)", filename, re.I)):
                    continue
                key = (contract, number, date)
                if key in records:
                    ambiguous.add(key)
                records[key] = (now, login, name, str(order.get("id_os") or ""))
        with self._lock:
            self._records = {key: value for key, value in self._records.items()
                             if key[0] != contract and now - value[0] <= 300}
            self._records.update({key: value for key, value in records.items() if key not in ambiguous})

    def matches(self, profile, order, date, supplied, installer_id, get_technicians):
        if profile != "natal" or not isinstance(supplied, dict) or not installer_id:
            return False
        login = str(supplied.get("external_id") or supplied.get("login") or "").strip().upper()
        name = _name(supplied.get("name"))
        with self._lock:
            recent = [value for value in self._records.values() if self._clock() - value[0] <= 300]
            value = self._records.get((str(order.contract), str(order.num_os), date.isoformat()))
            if (value not in recent or value[1:] != (login, name, str(order.id_os))
                    or any(other[1] == login and other[2] != name for other in recent)):
                return False
        technicians = get_technicians()
        same_installer = [row for row in technicians if str(row.get("installer_id")) == str(installer_id)]
        names = {_name(row.get("technician_name")) for row in same_installer}
        expected_stock_name = _IMPERIUM_STOCK_NAMES.get((str(installer_id), login, name))
        return names == {name} or (expected_stock_name is not None and names == {expected_stock_name})
