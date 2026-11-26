"""Read-only reconciliation of additional TOA tasks from a fresh bucket export."""
import csv
import datetime as dt
import re
import threading
import time
import tempfile
import os
import unicodedata
from pathlib import Path


def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", "".join(
        char for char in value if not unicodedata.combining(char)
    )).upper().split())


def _status(value):
    key = _norm(value)
    if key in {"E", "EXECUTADA", "EXECUTADO"}:
        return "E"
    if key in {"N", "NAO EXECUTADA", "NAO EXECUTADO"}:
        return "N"
    return ""


def _code(value):
    match = re.fullmatch(r"\s*(\d{3})(?:\s*-\s*.+)?\s*", str(value or ""))
    return match.group(1) if match else ""


def reconcile_export_tasks(capture, export_root, *, now=None, max_age_seconds=900):
    """Return a new task list only when the latest exact bucket row corroborates live data."""
    original = list(capture.get("tasks") or ())
    now = now or dt.datetime.now().astimezone()
    route = str(capture.get("route_name") or capture.get("route") or "").upper()
    date = str(capture.get("scheduled_date") or "")[:10]
    contract, aid = str(capture.get("contract") or ""), str(capture.get("aid") or "")
    assigned = capture.get("assigned_technician") or {}
    login = str(assigned.get("external_id") or assigned.get("login") or "").upper()
    if (route not in {"NTL-DMV", "PWM-DMV"} or not re.fullmatch(r"\d+", aid)
            or not re.fullmatch(r"\d{5,18}", contract) or not re.fullmatch(r"[ZT]\d+", login)
            or date != now.date().isoformat()
            or _norm(capture.get("activity_status")) not in {"COMPLETE", "COMPLETED", "CONCLUIDO", "CONCLUIDA"}
            or capture.get("validation_errors") or capture.get("operation_blockers")):
        return original
    day = dt.date.fromisoformat(date)
    filename = f"Atividades-{route}_{day:%d_%m_%y}.csv"
    try:
        paths = list((Path(export_root) / day.strftime("%Y%m%d")).glob(f"**/{filename}"))
        path = max(paths, key=lambda p: p.stat().st_mtime)
        age = now.timestamp() - path.stat().st_mtime
        if not 0 <= age <= max_age_seconds:
            return original
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            matches = []
            for raw in reader:
                row = {_norm(k): str(v or "").strip() for k, v in raw.items() if k}
                if row.get("CONTRATO") == contract and row.get("ID DA ATIVIDADE") == aid:
                    matches.append(row)
    except (ValueError, OSError, UnicodeError, csv.Error):
        return original
    if len(matches) != 1:
        return original
    row = matches[0]
    if (row.get("DATA") not in {day.strftime("%d/%m/%y"), day.strftime("%d/%m/%Y"), date}
            or row.get("LOGIN DO TECNICO", "").upper() != login
            or _norm(row.get("STATUS DA ATIVIDADE")) not in {"CONCLUIDO", "CONCLUIDA", "COMPLETE", "COMPLETED"}):
        return original
    tasks = {}
    for index in range(1, 11):
        os = row.get(f"NUMERO DA O S {index}", "")
        if not os:
            continue
        status, code = _status(row.get(f"STATUS DA O S {index}")), _code(row.get(f"COD DE BAIXA {index}"))
        if not re.fullmatch(r"\d{10}", os) or os in tasks or not status or not code:
            return original
        tasks[os] = {"index": index, "os_number": os, "status": status, "close_code": code,
                     "source": "toa_bucket_export_confirmed", "registry_only": True,
                     "export_activity_id": aid, "export_date": date, "export_bucket": route}
    if row.get("TOTAL DE TAREFAS") != str(len(tasks)):
        return original
    existing = {}
    for task in original:
        if task.get("imperium_only") or task.get("registry_only"):
            continue
        os = str(task.get("os_number") or "")
        if not os:
            continue
        if os in existing or os not in tasks:
            return original
        if _status(task.get("status")) != tasks[os]["status"] or _code(task.get("close_code")) != tasks[os]["close_code"]:
            return original
        existing[os] = task
    if not existing:
        return original
    additions = [v for k, v in tasks.items() if k not in existing]
    if not additions:
        return original
    # Replace display-only placeholders, never a contradictory live task.
    added_numbers = {task["os_number"] for task in additions}
    retained = [task for task in original if not (
        (task.get("imperium_only") or task.get("registry_only")) and str(task.get("os_number")) in added_numbers
    )]
    return retained + additions

# The import exporter is a read-only, same-day bucket download. It is not an
# import job, and must never feed the DESC registry or Imperium.
_refresh_lock = threading.Lock()
_refresh_attempts = {}


def recover_tasks_with_refresh(capture, export_root, orders, refresh, *, now=None):
    """Refresh a stale adhesion bucket only when a current OS is missing."""
    explicit_now = now
    now = now or dt.datetime.now().astimezone()
    result = reconcile_export_tasks(capture, export_root, now=now)
    route = str(capture.get("route_name") or capture.get("route") or "").upper()
    date = str(capture.get("scheduled_date") or "")[:10]
    contract = str(capture.get("contract") or "")
    aid = str(capture.get("aid") or "")
    assigned = capture.get("assigned_technician") or {}
    login = str(assigned.get("external_id") or assigned.get("login") or "").upper()
    if (route not in {"NTL-DMV", "PWM-DMV"} or date != now.date().isoformat()
            or not re.fullmatch(r"\d+", aid) or not re.fullmatch(r"\d{5,18}", contract)
            or not re.fullmatch(r"[ZT]\d+", login)
            or _norm(capture.get("activity_status")) not in {"COMPLETE", "COMPLETED", "CONCLUIDO", "CONCLUIDA"}
            or capture.get("validation_errors") or capture.get("operation_blockers")):
        return result
    actual = {str(t.get("os_number") or "") for t in result
              if not t.get("imperium_only") and not t.get("registry_only")
              and _status(t.get("status")) and _code(t.get("close_code"))}
    actual.update(str(t.get("os_number") or "") for t in result
                  if t.get("source") == "toa_bucket_export_confirmed")
    if not actual:
        return result
    missing = {str(o.get("num_os") or "") for o in orders
               if isinstance(o, dict) and str(o.get("contract") or "") == contract
               and _norm(o.get("status")) == "EM CAMPO"
               and re.fullmatch(r"\d{10}", str(o.get("num_os") or ""))} - actual
    if not missing:
        return result
    day = now.date()
    filename = f"Atividades-{route}_{day:%d_%m_%y}.csv"
    def fresh():
        try:
            path = max((Path(export_root) / day.strftime("%Y%m%d")).glob(f"**/{filename}"),
                       key=lambda p: p.stat().st_mtime)
            return 0 <= now.timestamp() - path.stat().st_mtime <= 900
        except (ValueError, OSError):
            return False
    # Never replace evidence from a fresh but contradictory CSV.
    if fresh() or not _refresh_lock.acquire(blocking=False):
        return result
    try:
        if fresh():
            return reconcile_export_tasks(capture, export_root, now=now)
        key = (route, date)
        tick = time.monotonic()
        if tick - _refresh_attempts.get(key, -1e9) < 60:
            return result
        if len(_refresh_attempts) > 10:
            _refresh_attempts.clear()
        _refresh_attempts[key] = tick
        try:
            refresh(route, day)
        except Exception:
            return result
        return reconcile_export_tasks(capture, export_root, now=explicit_now)
    finally:
        _refresh_lock.release()


def download_adhesion_export(root, route, day):
    """Atomic CSV export through the existing scope-checked read-only gateway."""
    if route not in {"NTL-DMV", "PWM-DMV"} or day != dt.date.today():
        raise ValueError("adhesion_export_scope_mismatch")
    from toa_bucket_collector import TOAImportExporter
    class BoundedExporter(TOAImportExporter):
        def _call(self, *args, **kwargs):
            kwargs["timeout"] = min(30.0, kwargs.get("timeout", 30.0))
            return super()._call(*args, **kwargs)
    root = Path(root)
    dest = root / "logs" / "toa-exports" / day.strftime("%Y%m%d")
    dest.mkdir(parents=True, exist_ok=True)
    # Keep temporary files outside the recursive search until fully written.
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix="adhesion-staging-") as tmp:
        with BoundedExporter(root, Path(tmp)) as exporter:
            path = exporter.export_route(route, day)
        filename = f"Atividades-{route}_{day:%d_%m_%y}.csv"
        if path.name != filename or path.stat().st_size <= 0:
            raise ValueError("invalid_adhesion_export")
        final = dest / ("adhesion-readonly-" + dt.datetime.now().strftime("%H%M%S-%f"))
        final.mkdir()
        os.replace(path, final / filename)
