"""Read-only reconciliation of additional TOA tasks from a fresh bucket export."""
import csv
import datetime as dt
import re
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
