"""Private, read-only serial consultation: real DataSnap history + local evidence."""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from serial_datasnap import fetch_serial_history, RUNTIME_ROOT, PROFILE_PORTS
from imperium_api import ImperiumAPI

DB_PATH = Path(r"C:\DominiumMain\data\dominium_operacional.sqlite3")
PROFILE_COMPANIES = {"natal": "NATAL", "fortaleza": "FORTALEZA", "mossoro": "MOSSORO", "recife": "RECIFE"}
ROUTE = "/api/serials/consult"


def parse_route(method: str, target: str):
    if method != "GET" or len(target) > 1500 or not target.startswith("/"):
        return None
    try:
        url = urlsplit(target)
        if url.path != ROUTE or url.fragment or url.scheme or url.netloc:
            return None
        values = parse_qs(url.query, strict_parsing=True)
    except ValueError as exc:
        raise ValueError("Parametros de consulta invalidos") from exc
    if any(key not in ("serials", "mode", "profile") or len(v) != 1 for key, v in values.items()):
        raise ValueError("Parametros de consulta invalidos")
    raw = values.get("serials", [""])[0]
    serials = list(dict.fromkeys(x.upper() for x in re.split(r"[,;\s]+", raw.strip()) if x))
    if not 1 <= len(serials) <= 20:
        raise ValueError("Informe de 1 a 20 seriais")
    if any(not re.fullmatch(r"[A-Z0-9._/-]{4,50}", s) for s in serials):
        raise ValueError("Seriais invalidos")
    mode = values.get("mode", ["analitico"])[0]
    if mode not in ("analitico", "sintetico"):
        raise ValueError("Modo invalido")
    profile = values.get("profile", ["natal"])[0]
    if profile not in ("natal", "fortaleza", "mossoro", "recife"):
        raise ValueError("Praca invalida")
    return serials, mode, profile


def local_references(serial: str, profile: str) -> list[dict]:
    if not DB_PATH.is_file():
        return []
    with sqlite3.connect(DB_PATH.as_uri()+"?mode=ro", uri=True, timeout=2) as con:
        con.row_factory = sqlite3.Row
        query = """
          SELECT i.profile, i.contract, i.activity_id, i.category,
                 i.code, i.description, i.serial, i.quantity, i.unit,
                 i.pool, i.updated_at,
                 COALESCE(c.customer_name, '') AS customer_name,
                 COALESCE(c.technician_name, '') AS technician_name,
                 COALESCE(c.status, '') AS contract_status,
                 COALESCE(c.city, '') AS city,
                 COALESCE(c.scheduled_date, '') AS scheduled_date
          FROM inventory i
          LEFT JOIN contracts c ON c.profile=i.profile AND c.contract=i.contract
          WHERE UPPER(TRIM(i.serial))=? AND i.profile=?
          ORDER BY i.updated_at DESC LIMIT 25
        """
        refs = [dict(x) for x in con.execute(query, (serial, profile))]
        for ref in refs:
            ref["orders"] = [dict(x) for x in con.execute(
                """SELECT os_number, service, imperium_status, toa_status, close_code, updated_at
                   FROM orders WHERE profile=? AND contract=?
                   ORDER BY updated_at DESC LIMIT 8""",
                (ref["profile"], ref["contract"])
            )]
        return refs


def latest_destination(movements: list[dict]):
    if not movements:
        return None
    # MIDAS provider returns event ordering in the same order as the native
    # Analitico report. Sort using its monotonic movement identifier, not dates guessed.
    last = max(movements, key=lambda x: int(x.get("Id") or 0))
    return {
        "stock_id": last.get("IdEstoqueDestino"),
        "stock_name": last.get("EstDestino"),
        "movement": last.get("Movimento"),
        "date": last.get("Data"),
        "source": "last_imperium_movement_unverified",
    }


def consult_serials(parsed) -> dict:
    serials, mode, profile = parsed
    results = []
    stock_cache = {}
    stock_api = None
    failures = 0
    for serial in serials:
        historical = local_references(serial, profile)
        entry = {
            "serial": serial,
            "live": {"found": False, "verified": False, "failed_stocks": 0},
            "history": historical,
            "datasnap": None,
            "last_destination": None,
            "history_error": "",
        }
        if not re.fullmatch(r"[A-Z0-9]{12}", serial):
            entry["history_error"] = "Consulta direta validada para seriais alfanumericos de 12 caracteres."
        else:
            try:
                movement = fetch_serial_history(serial, mode=mode, profile=profile)
                entry["datasnap"] = movement
                entry["last_destination"] = latest_destination(movement["movements"])
                # Confirm actual possession using the CURRENT contents of the
                # reported destination stock, never infer ownership from history.
                destination = entry["last_destination"] or {}
                stock_id = destination.get("stock_id")
                if isinstance(stock_id, int) and 0 < stock_id < 1_000_000:
                    try:
                        if stock_id not in stock_cache:
                            if stock_api is None:
                                stock_api = ImperiumAPI(RUNTIME_ROOT, port=PROFILE_PORTS[profile],
                                                       company=PROFILE_COMPANIES[profile], profile_key=profile,
                                                       expected_username="DOMINIUM")
                            stock_cache[stock_id] = stock_api.technician_stock(stock_id)
                        stock = stock_cache[stock_id]
                        for item in stock.get("items", []):
                            for linked in item.get("serials", []):
                                if serial in (str(linked.get("serial") or "").upper(),
                                              str(linked.get("smart") or "").upper()):
                                    entry["live"] = {
                                        "found": True, "verified": True,
                                        "owner": stock.get("technician", {}),
                                        "equipment": item,
                                        "stock_serial": linked,
                                        "scanned": 1, "total_stocks": 1,
                                        "failed_stocks": 0,
                                    }
                                    break
                            if entry["live"]["verified"]:
                                break
                    except (ValueError, OSError, RuntimeError):
                        pass  # Last destination is NOT proof of current stock.
            except Exception as exc:
                failures += 1
                entry["history_error"] = "Consulta DataSnap indisponivel para este serial."
        results.append(entry)
    return {
        "ok": True,
        "profile": profile,
        "mode": mode,
        "source": "imperium_datasnap_live",
        "historical_source": "dominium_operational_store",
        "live_error": "",
        "failed_queries": failures,
        "results": results,
    }
