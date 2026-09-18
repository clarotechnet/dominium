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
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _text(value: Any, limit: int = 4000) -> str:
    return str(value if value is not None else "").strip()[:limit]


def _digits(value: Any) -> str:
    return "".join(re.findall(r"\d", _text(value)))


def _first(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return ""


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _fingerprint(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _profile(bucket: str, explicit: str = "") -> str:
    if explicit:
        return explicit.casefold()
    prefix = bucket.upper().split("-", 1)[0]
    return {
        "NTL": "natal", "PWM": "natal", "FTZ": "fortaleza",
        "MRO": "mossoro", "JCR": "recife", "REC": "recife",
    }.get(prefix, "other")


class TOADatalakeStore:
    """Incremental, read-only TOA mirror fed by n8n or another authorized collector."""

    SCHEMA = "dominium.toa.datalake.v1"
    MAX_ITEMS = 20_000

    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=20000")
        return connection

    def _initialize(self) -> None:
        with self.lock, closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS activities (
                    activity_id TEXT PRIMARY KEY,
                    profile TEXT NOT NULL DEFAULT '', contract TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '', activity_type TEXT NOT NULL DEFAULT '',
                    parent_id TEXT NOT NULL DEFAULT '', bucket TEXT NOT NULL DEFAULT '',
                    technician_id TEXT NOT NULL DEFAULT '', technician_login TEXT NOT NULL DEFAULT '',
                    technician_name TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT '',
                    scheduled_date TEXT NOT NULL DEFAULT '', start_min TEXT NOT NULL DEFAULT '',
                    service_window TEXT NOT NULL DEFAULT '', start_time TEXT NOT NULL DEFAULT '',
                    end_time TEXT NOT NULL DEFAULT '', city TEXT NOT NULL DEFAULT '',
                    observation TEXT NOT NULL DEFAULT '', fingerprint TEXT NOT NULL,
                    detail_state TEXT NOT NULL DEFAULT 'pending', first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, collected_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    os_number TEXT PRIMARY KEY, activity_id TEXT NOT NULL DEFAULT '',
                    contract TEXT NOT NULL DEFAULT '', task_index TEXT NOT NULL DEFAULT '',
                    service TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT '',
                    close_code TEXT NOT NULL DEFAULT '', fingerprint TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    activity_id TEXT NOT NULL, category TEXT NOT NULL, item_key TEXT NOT NULL,
                    contract TEXT NOT NULL DEFAULT '', inventory_id TEXT NOT NULL DEFAULT '',
                    code TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
                    serial TEXT NOT NULL DEFAULT '', quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '', pool TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(activity_id, category, item_key)
                );
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                    collector_id TEXT NOT NULL DEFAULT '', observed_at TEXT NOT NULL,
                    received_at TEXT NOT NULL, activity_count INTEGER NOT NULL,
                    order_count INTEGER NOT NULL, detail_count INTEGER NOT NULL,
                    changed_count INTEGER NOT NULL, bucket_count INTEGER NOT NULL,
                    warnings TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_dl_activity_date ON activities(scheduled_date);
                CREATE INDEX IF NOT EXISTS idx_dl_activity_bucket ON activities(bucket);
                CREATE INDEX IF NOT EXISTS idx_dl_order_activity ON orders(activity_id);
                CREATE INDEX IF NOT EXISTS idx_dl_inventory_contract ON inventory(contract);
            """)

    @staticmethod
    def _activity(raw: dict[str, Any], profile: str = "") -> dict[str, str]:
        bucket = _text(_first(raw, "bucket", "resource_bucket"), 120)
        technician = raw.get("technician") if isinstance(raw.get("technician"), dict) else {}
        return {
            "activity_id": _digits(_first(raw, "activity_id", "atividade_id", "id", "pid")),
            "profile": _profile(bucket, _text(_first(raw, "profile", "profile_key") or profile, 40)),
            "contract": _digits(_first(raw, "contract", "contrato", "customer_number")),
            "description": _text(_first(raw, "description", "descricao", "atividade_descricao", "work_type")),
            "activity_type": _text(_first(raw, "activity_type", "atividade_tipo", "type_id", "t"), 120),
            "parent_id": _text(_first(raw, "parent_id", "tipo_id", "parent", "p"), 120),
            "bucket": bucket,
            "technician_id": _text(_first(raw, "technician_id", "tecnico_id", "resource_id") or technician.get("id"), 160),
            "technician_login": _text(_first(raw, "technician_login", "login", "user_id", "usuario_id") or technician.get("login"), 160),
            "technician_name": _text(_first(raw, "technician_name", "tecnico_nome", "resource_name") or technician.get("name")),
            "status": _text(_first(raw, "status", "status_toa", "activity_status", "s"), 120),
            "scheduled_date": _text(_first(raw, "scheduled_date", "atividade_data", "date", "data_atividade"), 40)[:10],
            "start_min": _text(_first(raw, "start_min", "inicio_min", "S"), 20),
            "service_window": _text(_first(raw, "service_window", "time_window", "janela"), 120),
            "start_time": _text(_first(raw, "start_time", "started_at", "inicio"), 60),
            "end_time": _text(_first(raw, "end_time", "ended_at", "fim"), 60),
            "city": _text(_first(raw, "city", "cidade"), 160),
            "observation": _text(_first(raw, "observation", "technician_observation", "observacao")),
        }

    @staticmethod
    def _order(raw: dict[str, Any], activity_id: str = "", contract: str = "") -> dict[str, str]:
        return {
            "os_number": _digits(_first(raw, "os_number", "os_id", "num_os", "id")),
            "activity_id": _digits(_first(raw, "activity_id", "atividade_id") or activity_id),
            "contract": _digits(_first(raw, "contract", "contrato") or contract),
            "task_index": _text(_first(raw, "task_index", "indice", "index"), 20),
            "service": _text(_first(raw, "service", "tipo_os", "description")),
            "status": _text(_first(raw, "status", "status_toa", "os_status"), 120),
            "close_code": _digits(_first(raw, "close_code", "codigo_baixa", "codigo_baixa_id")),
        }

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        activities = _list(payload.get("activities") or payload.get("atividades"))
        orders = _list(payload.get("orders") or payload.get("activities_os") or payload.get("atividades_os"))
        details = _list(payload.get("details") or payload.get("detalhes"))
        total = len(activities) + len(orders) + len(details)
        if not total:
            raise ValueError("O lote nao contem activities, orders ou details")
        if total > self.MAX_ITEMS:
            raise ValueError(f"O lote excede o limite de {self.MAX_ITEMS} itens")
        observed_at = _text(payload.get("observed_at") or payload.get("collected_at"), 80) or _now()
        source = _text(payload.get("source"), 120) or "n8n"
        collector_id = _text(payload.get("collector_id"), 120)
        explicit_profile = _text(payload.get("profile"), 40)
        changed = 0
        buckets: set[str] = set()
        warnings: list[str] = []
        with self.lock, closing(self._connect()) as connection, connection:
            for raw in activities:
                row = self._activity(raw, explicit_profile)
                if not row["activity_id"]:
                    warnings.append("activity_without_id")
                    continue
                buckets.add(row["bucket"])
                nested_orders = _list(raw.get("orders") or raw.get("tasks"))
                fingerprint = _fingerprint(row)
                previous = connection.execute(
                    "SELECT fingerprint FROM activities WHERE activity_id=?", (row["activity_id"],)
                ).fetchone()
                is_changed = previous is None or previous["fingerprint"] != fingerprint
                changed += int(is_changed)
                connection.execute("""
                    INSERT INTO activities (
                        activity_id,profile,contract,description,activity_type,parent_id,bucket,
                        technician_id,technician_login,technician_name,status,scheduled_date,
                        start_min,service_window,start_time,end_time,city,observation,fingerprint,
                        detail_state,first_seen_at,updated_at,collected_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(activity_id) DO UPDATE SET
                        profile=excluded.profile,
                        contract=CASE WHEN excluded.contract<>'' THEN excluded.contract ELSE contract END,
                        description=excluded.description,activity_type=excluded.activity_type,
                        parent_id=excluded.parent_id,bucket=excluded.bucket,
                        technician_id=excluded.technician_id,technician_login=excluded.technician_login,
                        technician_name=excluded.technician_name,status=excluded.status,
                        scheduled_date=excluded.scheduled_date,start_min=excluded.start_min,
                        service_window=CASE WHEN excluded.service_window<>'' THEN excluded.service_window ELSE service_window END,
                        start_time=CASE WHEN excluded.start_time<>'' THEN excluded.start_time ELSE start_time END,
                        end_time=CASE WHEN excluded.end_time<>'' THEN excluded.end_time ELSE end_time END,
                        city=CASE WHEN excluded.city<>'' THEN excluded.city ELSE city END,
                        observation=CASE WHEN excluded.observation<>'' THEN excluded.observation ELSE observation END,
                        fingerprint=excluded.fingerprint,
                        detail_state=CASE WHEN ? THEN 'pending' ELSE detail_state END,
                        updated_at=CASE WHEN ? THEN excluded.updated_at ELSE updated_at END,
                        collected_at=excluded.collected_at
                """, (*row.values(), fingerprint, "pending", observed_at, observed_at, observed_at,
                      int(is_changed), int(is_changed)))
                for nested in nested_orders:
                    orders.append({**nested, "activity_id": row["activity_id"], "contract": row["contract"]})

            for raw in orders:
                row = self._order(raw)
                if not row["os_number"]:
                    warnings.append("order_without_number")
                    continue
                fingerprint = _fingerprint(row)
                previous = connection.execute(
                    "SELECT fingerprint FROM orders WHERE os_number=?", (row["os_number"],)
                ).fetchone()
                changed += int(previous is None or previous["fingerprint"] != fingerprint)
                connection.execute("""
                    INSERT INTO orders (os_number,activity_id,contract,task_index,service,status,close_code,fingerprint,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(os_number) DO UPDATE SET
                        activity_id=CASE WHEN excluded.activity_id<>'' THEN excluded.activity_id ELSE activity_id END,
                        contract=CASE WHEN excluded.contract<>'' THEN excluded.contract ELSE contract END,
                        task_index=excluded.task_index,
                        service=CASE WHEN excluded.service<>'' THEN excluded.service ELSE service END,
                        status=CASE WHEN excluded.status<>'' THEN excluded.status ELSE status END,
                        close_code=CASE WHEN excluded.close_code<>'' THEN excluded.close_code ELSE close_code END,
                        fingerprint=excluded.fingerprint,updated_at=excluded.updated_at
                """, (*row.values(), fingerprint, observed_at))

            for detail in details:
                changed += self._ingest_detail(connection, detail, observed_at, explicit_profile)

            connection.execute("""
                INSERT INTO collection_runs (
                    source,collector_id,observed_at,received_at,activity_count,order_count,
                    detail_count,changed_count,bucket_count,warnings
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (source, collector_id, observed_at, _now(), len(activities), len(orders),
                  len(details), changed, len({item for item in buckets if item}),
                  json.dumps(sorted(set(warnings)), ensure_ascii=False)))
        return {"ok": True, "schema": self.SCHEMA, "activities": len(activities),
                "orders": len(orders), "details": len(details), "changed": changed,
                "warnings": sorted(set(warnings)), "status": self.status()}

    def _ingest_detail(self, connection: sqlite3.Connection, raw: dict[str, Any], now: str, profile: str) -> int:
        activity_id = _digits(_first(raw, "activity_id", "atividade_id", "aid", "id"))
        contract = _digits(_first(raw, "contract", "contrato", "customer_number"))
        activity = self._activity(raw, profile)
        if not activity_id:
            activity_id = activity["activity_id"]
        if activity_id:
            connection.execute("""
                UPDATE activities SET
                    contract=CASE WHEN ?<>'' THEN ? ELSE contract END,
                    service_window=CASE WHEN ?<>'' THEN ? ELSE service_window END,
                    start_time=CASE WHEN ?<>'' THEN ? ELSE start_time END,
                    end_time=CASE WHEN ?<>'' THEN ? ELSE end_time END,
                    observation=CASE WHEN ?<>'' THEN ? ELSE observation END,
                    detail_state='complete',updated_at=? WHERE activity_id=?
            """, (contract, contract, activity["service_window"], activity["service_window"],
                  activity["start_time"], activity["start_time"], activity["end_time"],
                  activity["end_time"], activity["observation"], activity["observation"],
                  now, activity_id))
        detail_orders = _list(raw.get("orders") or raw.get("tasks"))
        for order_raw in detail_orders:
            row = self._order(order_raw, activity_id, contract)
            if not row["os_number"]:
                continue
            fingerprint = _fingerprint(row)
            connection.execute("""
                INSERT INTO orders (os_number,activity_id,contract,task_index,service,status,close_code,fingerprint,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(os_number) DO UPDATE SET
                    activity_id=CASE WHEN excluded.activity_id<>'' THEN excluded.activity_id ELSE activity_id END,
                    contract=CASE WHEN excluded.contract<>'' THEN excluded.contract ELSE contract END,
                    service=CASE WHEN excluded.service<>'' THEN excluded.service ELSE service END,
                    status=CASE WHEN excluded.status<>'' THEN excluded.status ELSE status END,
                    close_code=CASE WHEN excluded.close_code<>'' THEN excluded.close_code ELSE close_code END,
                    fingerprint=excluded.fingerprint,updated_at=excluded.updated_at
            """, (*row.values(), fingerprint, now))
        equipment = raw.get("equipment") if isinstance(raw.get("equipment"), dict) else {}
        categories = {
            "installed": raw.get("installed_equipment") or equipment.get("installed", []),
            "removed": raw.get("removed_equipment") or equipment.get("removed", []),
            "customer": raw.get("customer_equipment") or equipment.get("customer", []),
            "material": raw.get("materials") or raw.get("miscelaneas") or [],
        }
        for category, values in categories.items():
            for position, item in enumerate(_list(values)):
                serial = _text(_first(item, "serial", "numero_serial"), 240)
                code = _text(_first(item, "code", "material_code", "codigo"), 120)
                inventory_id = _text(_first(item, "inventory_id", "invid", "id"), 160)
                item_key = inventory_id or serial or f"{code}:{position}"
                try:
                    quantity = float(str(_first(item, "quantity", "quantidade", "used_quantity") or 0).replace(",", "."))
                except (TypeError, ValueError):
                    quantity = 0
                connection.execute("""
                    INSERT INTO inventory (activity_id,category,item_key,contract,inventory_id,code,description,serial,quantity,unit,pool,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(activity_id,category,item_key) DO UPDATE SET
                        contract=excluded.contract,code=excluded.code,description=excluded.description,
                        serial=excluded.serial,quantity=excluded.quantity,unit=excluded.unit,
                        pool=excluded.pool,updated_at=excluded.updated_at
                """, (activity_id or f"contract:{contract}", category, item_key, contract,
                      inventory_id, code, _text(_first(item, "description", "descricao", "name", "type")),
                      serial, quantity, _text(_first(item, "unit", "unidade"), 40),
                      _text(_first(item, "pool", "movimentacao"), 80), now))
        return 1

    def status(self) -> dict[str, Any]:
        with self.lock, closing(self._connect()) as connection:
            counts = {
                "activities": connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0],
                "orders": connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
                "inventory": connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0],
                "pending_details": connection.execute("SELECT COUNT(*) FROM activities WHERE detail_state='pending'").fetchone()[0],
            }
            last = connection.execute("SELECT * FROM collection_runs ORDER BY id DESC LIMIT 1").fetchone()
            buckets = [dict(row) for row in connection.execute(
                "SELECT bucket,COUNT(*) AS activities FROM activities WHERE bucket<>'' GROUP BY bucket ORDER BY bucket"
            ).fetchall()]
        return {"ok": True, "schema": self.SCHEMA, "database": self.path.name,
                "counts": counts, "buckets": buckets, "last_run": dict(last) if last else None}

    def detail_queue(self, limit: int = 100) -> dict[str, Any]:
        safe_limit = min(1000, max(1, int(limit)))
        with self.lock, closing(self._connect()) as connection:
            rows = [dict(row) for row in connection.execute("""
                SELECT a.activity_id,a.contract,a.bucket,a.scheduled_date,a.updated_at,
                    GROUP_CONCAT(o.os_number) AS os_numbers
                FROM activities a LEFT JOIN orders o ON o.activity_id=a.activity_id
                WHERE a.detail_state='pending'
                GROUP BY a.activity_id ORDER BY a.updated_at DESC LIMIT ?
            """, (safe_limit,)).fetchall()]
        return {"ok": True, "count": len(rows), "items": rows}

    def record(self, identifier: str) -> dict[str, Any]:
        key = _digits(identifier)
        if not key:
            raise ValueError("Contrato ou atividade invalida")
        with self.lock, closing(self._connect()) as connection:
            activities = [dict(row) for row in connection.execute(
                "SELECT * FROM activities WHERE contract=? OR activity_id=? ORDER BY scheduled_date,start_min",
                (key, key),
            ).fetchall()]
            activity_ids = [row["activity_id"] for row in activities]
            orders: list[dict[str, Any]] = []
            inventory: list[dict[str, Any]] = []
            if activity_ids:
                placeholders = ",".join("?" for _ in activity_ids)
                orders = [dict(row) for row in connection.execute(
                    f"SELECT * FROM orders WHERE activity_id IN ({placeholders}) OR contract=? ORDER BY task_index,os_number",
                    (*activity_ids, key),
                ).fetchall()]
                inventory = [dict(row) for row in connection.execute(
                    f"SELECT * FROM inventory WHERE activity_id IN ({placeholders}) OR contract=? ORDER BY category,description,serial",
                    (*activity_ids, key),
                ).fetchall()]
            else:
                orders = [dict(row) for row in connection.execute(
                    "SELECT * FROM orders WHERE contract=? ORDER BY task_index,os_number", (key,)
                ).fetchall()]
                inventory = [dict(row) for row in connection.execute(
                    "SELECT * FROM inventory WHERE contract=? ORDER BY category,description,serial", (key,)
                ).fetchall()]
        grouped = {name: [] for name in ("installed", "removed", "customer", "material")}
        for item in inventory:
            grouped.setdefault(item["category"], []).append(item)
        return {"ok": True, "schema": self.SCHEMA, "identifier": key,
                "activities": activities, "orders": orders, "inventory": grouped,
                "summary": {"activity_count": len(activities), "os_count": len(orders),
                            "inventory_count": len(inventory),
                            "detail_complete": bool(activities) and all(row["detail_state"] == "complete" for row in activities)}}

    def feed(self, *, profile: str = "", date: str = "") -> dict[str, Any]:
        clauses: list[str] = []
        values: list[Any] = []
        if profile and profile != "all":
            clauses.append("a.profile=?")
            values.append(profile.casefold())
        if date:
            clauses.append("a.scheduled_date=?")
            values.append(date)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.lock, closing(self._connect()) as connection:
            activities = [dict(row) for row in connection.execute(
                f"SELECT a.* FROM activities a{where} ORDER BY a.scheduled_date,a.start_min,a.activity_id", values
            ).fetchall()]
            activity_ids = [row["activity_id"] for row in activities]
            orders: list[dict[str, Any]] = []
            if activity_ids:
                placeholders = ",".join("?" for _ in activity_ids)
                orders = [dict(row) for row in connection.execute(
                    f"SELECT * FROM orders WHERE activity_id IN ({placeholders}) ORDER BY task_index,os_number", activity_ids
                ).fetchall()]
            last = connection.execute("SELECT * FROM collection_runs ORDER BY id DESC LIMIT 1").fetchone()
        by_activity: dict[str, list[dict[str, Any]]] = {}
        for order in orders:
            by_activity.setdefault(order["activity_id"], []).append(order)
        output: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []
        for activity in activities:
            common = {
                "profile": activity["profile"],
                "date": activity["scheduled_date"], "scheduled_date": activity["scheduled_date"],
                "technician": activity["technician_name"] or activity["technician_login"] or activity["technician_id"],
                "technician_name": activity["technician_name"], "technician_login": activity["technician_login"],
                "activity_status": activity["status"], "city": activity["city"], "contract": activity["contract"],
                "service_window": activity["service_window"], "time_window": activity["service_window"],
                "started_at": activity["start_time"], "ended_at": activity["end_time"],
                "activity_type": activity["activity_type"], "activity_id": activity["activity_id"],
                "bucket": activity["bucket"], "observation": activity["observation"],
                "source_file": "DATALAKE TOA",
            }
            linked = by_activity.get(activity["activity_id"], [])
            if not linked:
                timeline.append({**common, "service": activity["description"], "status": activity["status"],
                                 "is_auxiliary": True, "auxiliary_type": "toa_activity"})
            for order in linked:
                output.append({**common, "contract": order["contract"] or activity["contract"],
                               "os_number": order["os_number"], "num_os": order["os_number"],
                               "service": order["service"] or activity["description"],
                               "status": order["status"] or activity["status"],
                               "toa_status": order["status"] or activity["status"],
                               "close_code": order["close_code"]})
        observed_at = dict(last)["observed_at"] if last else ""
        return {"ok": True, "schema": self.SCHEMA, "source": "toa_datalake",
                "files": [{"filename": "DATALAKE TOA", "bucket": "TODOS", "sourceRows": len(activities)}],
                "orders": output, "timelineActivities": timeline, "errors": [],
                "loadedAt": observed_at or _now(), "activity_count": len(activities),
                "order_count": len(output), "last_run": dict(last) if last else None}
