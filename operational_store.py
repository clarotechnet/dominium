# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - contem validacao, consulta ou operacao ligada ao Imperium.
#
# TOA
# - SIM - contem captura, contexto, importacao ou evidencia vinda do TOA.
#
# DOMINIUM COMPARTILHADO
# - Ponte entre os dois dominios; alterar com testes dos dois lados.
#
# Categoria deste arquivo: MISTO.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _text(value: Any, limit: int = 2000) -> str:
    return str(value or "").strip()[:limit]


def _digits(value: Any) -> str:
    return "".join(re.findall(r"\d", _text(value)))


def _number(value: Any) -> float:
    try:
        return float(str(value or "0").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _unique_items(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        identity = _json(value)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(value)
    return result


class OperationalStore:
    """SQLite operational history with an automatically generated JSON mirror."""

    SCHEMA_VERSION = 1

    def __init__(self, database_path: Path, json_path: Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.json_path = Path(json_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=20000")
        return connection

    def _initialize(self) -> None:
        with self.lock, closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS contracts (
                    profile TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    scheduled_date TEXT NOT NULL DEFAULT '',
                    appointment_number TEXT NOT NULL DEFAULT '',
                    customer_name TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    district TEXT NOT NULL DEFAULT '',
                    service_window TEXT NOT NULL DEFAULT '',
                    technician_id TEXT NOT NULL DEFAULT '',
                    technician_login TEXT NOT NULL DEFAULT '',
                    technician_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    observation TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile, contract)
                );

                CREATE TABLE IF NOT EXISTS activities (
                    profile TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    activity_id TEXT NOT NULL,
                    scheduled_date TEXT NOT NULL DEFAULT '',
                    appointment_number TEXT NOT NULL DEFAULT '',
                    work_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    service_window TEXT NOT NULL DEFAULT '',
                    start_time TEXT NOT NULL DEFAULT '',
                    end_time TEXT NOT NULL DEFAULT '',
                    technician_id TEXT NOT NULL DEFAULT '',
                    technician_login TEXT NOT NULL DEFAULT '',
                    technician_name TEXT NOT NULL DEFAULT '',
                    observation TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile, contract, activity_id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    profile TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    os_number TEXT NOT NULL,
                    id_os INTEGER NOT NULL DEFAULT 0,
                    activity_id TEXT NOT NULL DEFAULT '',
                    service TEXT NOT NULL DEFAULT '',
                    point TEXT NOT NULL DEFAULT '',
                    toa_status TEXT NOT NULL DEFAULT '',
                    imperium_status TEXT NOT NULL DEFAULT '',
                    close_code TEXT NOT NULL DEFAULT '',
                    scheduled_date TEXT NOT NULL DEFAULT '',
                    assignment_time TEXT NOT NULL DEFAULT '',
                    reservation_time TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile, contract, os_number)
                );

                CREATE TABLE IF NOT EXISTS inventory (
                    profile TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    activity_id TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    inventory_id TEXT NOT NULL DEFAULT '',
                    code TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    serial TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT '',
                    pool TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile, contract, activity_id, category, item_key)
                );

                CREATE TABLE IF NOT EXISTS close_attempts (
                    request_id TEXT PRIMARY KEY,
                    profile TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    os_number TEXT NOT NULL DEFAULT '',
                    id_os INTEGER NOT NULL DEFAULT 0,
                    close_code TEXT NOT NULL DEFAULT '',
                    close_description TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    category_label TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    detail TEXT NOT NULL DEFAULT '',
                    transport TEXT NOT NULL DEFAULT '',
                    installed_count INTEGER NOT NULL DEFAULT 0,
                    removed_count INTEGER NOT NULL DEFAULT 0,
                    material_count INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 1,
                    safe_to_retry INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    accepted_at TEXT NOT NULL DEFAULT '',
                    confirmed_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_contracts_updated
                    ON contracts(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_orders_number
                    ON orders(os_number);
                CREATE INDEX IF NOT EXISTS idx_inventory_serial
                    ON inventory(serial);
                CREATE INDEX IF NOT EXISTS idx_attempts_contract
                    ON close_attempts(profile, contract, updated_at DESC);
                """
            )

    @staticmethod
    def _merge_sql(fields: tuple[str, ...]) -> str:
        return ",".join(
            f"{field}=CASE WHEN excluded.{field}<>'' "
            f"THEN excluded.{field} ELSE {field} END"
            for field in fields
        )

    def _upsert_contract(
        self,
        connection: sqlite3.Connection,
        profile: str,
        contract: str,
        values: dict[str, Any],
        now: str,
    ) -> None:
        if not contract:
            return
        fields = (
            "scheduled_date", "appointment_number", "customer_name", "city",
            "district", "service_window", "technician_id", "technician_login",
            "technician_name", "status", "observation",
        )
        row = {field: _text(values.get(field)) for field in fields}
        connection.execute(
            f"""
            INSERT INTO contracts (
                profile,contract,{','.join(fields)},first_seen_at,updated_at
            ) VALUES ({','.join('?' for _ in range(len(fields) + 4))})
            ON CONFLICT(profile,contract) DO UPDATE SET
                {self._merge_sql(fields)},
                updated_at=CASE WHEN excluded.updated_at>updated_at
                    THEN excluded.updated_at ELSE updated_at END
            """,
            (profile, contract, *(row[field] for field in fields), now, now),
        )

    def ingest_monitor_snapshot(self, profile: str, snapshot: dict[str, Any]) -> None:
        now = _text(snapshot.get("uploaded_at")) or _now()
        with self.lock, closing(self._connect()) as connection, connection:
            for raw in snapshot.get("orders") or []:
                if not isinstance(raw, dict):
                    continue
                contract = _digits(raw.get("contract"))
                os_number = _digits(raw.get("num_os"))
                if not contract or not os_number:
                    continue
                self._upsert_contract(connection, profile, contract, {
                    "scheduled_date": raw.get("date"),
                    "city": raw.get("city"),
                    "district": raw.get("district"),
                    "service_window": raw.get("service_window") or raw.get("time_window"),
                    "technician_login": raw.get("technician_login"),
                    "technician_name": raw.get("technician"),
                    "status": raw.get("toa_status"),
                }, now)
                connection.execute(
                    """
                    INSERT INTO orders (
                        profile,contract,os_number,id_os,activity_id,service,point,
                        toa_status,imperium_status,close_code,scheduled_date,
                        assignment_time,reservation_time,source,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(profile,contract,os_number) DO UPDATE SET
                        activity_id=CASE WHEN excluded.activity_id<>'' THEN excluded.activity_id ELSE activity_id END,
                        service=CASE WHEN excluded.service<>'' THEN excluded.service ELSE service END,
                        toa_status=CASE WHEN excluded.toa_status<>'' THEN excluded.toa_status ELSE toa_status END,
                        close_code=CASE WHEN excluded.close_code<>'' THEN excluded.close_code ELSE close_code END,
                        scheduled_date=CASE WHEN excluded.scheduled_date<>'' THEN excluded.scheduled_date ELSE scheduled_date END,
                        source=excluded.source,updated_at=excluded.updated_at
                    """,
                    (
                        profile, contract, os_number, 0, _text(raw.get("activity_id")),
                        _text(raw.get("service")), _text(raw.get("point")),
                        _text(raw.get("toa_status") or raw.get("toa_os_status")), "",
                        _text(raw.get("close_code")), _text(raw.get("date")),
                        _text(raw.get("assignment_time")), _text(raw.get("reservation_time")),
                        "monitor_csv", now,
                    ),
                )
        self._maybe_export_json()

    def ingest_imperium_orders(
        self,
        profile: str,
        rows: Iterable[dict[str, Any]],
        observed_at: str | None = None,
    ) -> None:
        now = observed_at or _now()
        changed = False
        with self.lock, closing(self._connect()) as connection, connection:
            for raw in rows:
                contract = _digits(raw.get("contract"))
                os_number = _digits(raw.get("num_os"))
                if not contract or not os_number:
                    continue
                changed = True
                self._upsert_contract(connection, profile, contract, {
                    "scheduled_date": raw.get("date"),
                    "city": raw.get("city"),
                    "district": raw.get("district"),
                    "service_window": raw.get("service_window") or raw.get("time_window"),
                    "technician_login": raw.get("technician_login"),
                    "technician_name": raw.get("technician"),
                    "status": raw.get("status"),
                }, now)
                connection.execute(
                    """
                    INSERT INTO orders (
                        profile,contract,os_number,id_os,activity_id,service,point,
                        toa_status,imperium_status,close_code,scheduled_date,
                        assignment_time,reservation_time,source,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(profile,contract,os_number) DO UPDATE SET
                        id_os=CASE WHEN excluded.id_os>0 THEN excluded.id_os ELSE id_os END,
                        activity_id=CASE WHEN excluded.activity_id<>'' THEN excluded.activity_id ELSE activity_id END,
                        service=CASE WHEN excluded.service<>'' THEN excluded.service ELSE service END,
                        point=CASE WHEN excluded.point<>'' THEN excluded.point ELSE point END,
                        imperium_status=excluded.imperium_status,
                        close_code=CASE WHEN excluded.close_code<>'' THEN excluded.close_code ELSE close_code END,
                        scheduled_date=CASE WHEN excluded.scheduled_date<>'' THEN excluded.scheduled_date ELSE scheduled_date END,
                        assignment_time=CASE WHEN excluded.assignment_time<>'' THEN excluded.assignment_time ELSE assignment_time END,
                        reservation_time=CASE WHEN excluded.reservation_time<>'' THEN excluded.reservation_time ELSE reservation_time END,
                        source=excluded.source,updated_at=excluded.updated_at
                    """,
                    (
                        profile, contract, os_number, int(raw.get("id_os") or 0),
                        _text(raw.get("activity_id")), _text(raw.get("service")),
                        _text(raw.get("point")),
                        _text(raw.get("toa_status")), _text(raw.get("status")),
                        _text(raw.get("close_code")), _text(raw.get("date")),
                        _text(raw.get("assignment_time")), _text(raw.get("reservation_time")),
                        "imperium", now,
                    ),
                )
        if changed:
            self._maybe_export_json()

    @staticmethod
    def _inventory_category(item: dict[str, Any]) -> str:
        kind = _text(item.get("kind")).casefold()
        pool = _text(item.get("pool")).casefold()
        action = _text(item.get("action_code"))
        if kind == "material" or item.get("material_code"):
            return "material"
        if pool in {"remove", "removed", "deinstall"} or action in {"2", "3"}:
            return "removed"
        if pool in {"customer", "cliente"}:
            return "customer"
        return "installed"

    def ingest_toa_capture(
        self,
        profile: str,
        payload: dict[str, Any],
        *,
        source: str = "toa_live",
        export: bool = True,
    ) -> None:
        now = _text((payload.get("metadata") or {}).get("exportedAt")) or _now()
        with self.lock, closing(self._connect()) as connection, connection:
            for entry in payload.get("os_list") or []:
                if not isinstance(entry, dict):
                    continue
                os_data = entry.get("os") if isinstance(entry.get("os"), dict) else {}
                activity = os_data.get("activity") if isinstance(os_data.get("activity"), dict) else {}
                contract = _digits(entry.get("contract") or activity.get("contract"))
                activity_id = _text(entry.get("aid") or activity.get("aid")) or "sem-aid"
                if not contract:
                    continue
                self._upsert_contract(connection, profile, contract, {
                    "scheduled_date": activity.get("date"),
                    "appointment_number": activity.get("appointment_number"),
                    "customer_name": activity.get("customer_name"),
                    "city": activity.get("city"),
                    "district": activity.get("district"),
                    "service_window": activity.get("time_slot"),
                    "technician_id": activity.get("technician_id"),
                    "technician_login": activity.get("technician_external_id"),
                    "technician_name": activity.get("technician_name"),
                    "status": activity.get("status"),
                    "observation": activity.get("technician_observation") or activity.get("observation"),
                }, now)
                connection.execute(
                    """
                    INSERT INTO activities (
                        profile,contract,activity_id,scheduled_date,appointment_number,
                        work_type,status,service_window,start_time,end_time,technician_id,
                        technician_login,technician_name,observation,source,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(profile,contract,activity_id) DO UPDATE SET
                        scheduled_date=excluded.scheduled_date,
                        appointment_number=excluded.appointment_number,
                        work_type=excluded.work_type,status=excluded.status,
                        service_window=excluded.service_window,start_time=excluded.start_time,
                        end_time=excluded.end_time,technician_id=excluded.technician_id,
                        technician_login=excluded.technician_login,
                        technician_name=excluded.technician_name,
                        observation=CASE WHEN excluded.observation<>'' THEN excluded.observation ELSE observation END,
                        source=excluded.source,updated_at=excluded.updated_at
                    """,
                    (
                        profile, contract, activity_id, _text(activity.get("date")),
                        _text(activity.get("appointment_number")), _text(activity.get("work_type")),
                        _text(activity.get("status")), _text(activity.get("time_slot")),
                        _text(activity.get("start_time")), _text(activity.get("end_time")),
                        _text(activity.get("technician_id")), _text(activity.get("technician_external_id")),
                        _text(activity.get("technician_name")),
                        _text(activity.get("technician_observation") or activity.get("observation")),
                        source, now,
                    ),
                )
                for task in os_data.get("tasks") or []:
                    if not isinstance(task, dict):
                        continue
                    os_number = _digits(task.get("os_number"))
                    if not os_number:
                        continue
                    connection.execute(
                        """
                        INSERT INTO orders (
                            profile,contract,os_number,activity_id,toa_status,
                            close_code,scheduled_date,source,updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(profile,contract,os_number) DO UPDATE SET
                            activity_id=excluded.activity_id,toa_status=excluded.toa_status,
                            close_code=CASE WHEN excluded.close_code<>'' THEN excluded.close_code ELSE close_code END,
                            scheduled_date=excluded.scheduled_date,source=excluded.source,
                            updated_at=excluded.updated_at
                        """,
                        (
                            profile, contract, os_number, activity_id,
                            _text(task.get("status")), _text(task.get("close_code")),
                            _text(activity.get("date")), source, now,
                        ),
                    )
                inventory = os_data.get("inventory") or (
                    list(os_data.get("equipment") or []) + list(os_data.get("materials") or [])
                )
                for position, item in enumerate(inventory):
                    if not isinstance(item, dict):
                        continue
                    category = self._inventory_category(item)
                    serial = _text(item.get("serial"))
                    code = _text(item.get("material_code") or item.get("code"))
                    inventory_id = _text(item.get("invid") or item.get("inventory_id"))
                    item_key = inventory_id or serial or f"{code}:{position}"
                    connection.execute(
                        """
                        INSERT INTO inventory (
                            profile,contract,activity_id,category,item_key,inventory_id,
                            code,description,serial,quantity,unit,pool,raw_json,updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(profile,contract,activity_id,category,item_key) DO UPDATE SET
                            code=excluded.code,description=excluded.description,
                            serial=excluded.serial,quantity=excluded.quantity,
                            unit=excluded.unit,pool=excluded.pool,raw_json=excluded.raw_json,
                            updated_at=excluded.updated_at
                        """,
                        (
                            profile, contract, activity_id, category, item_key,
                            inventory_id, code,
                            _text(item.get("description") or item.get("type") or item.get("name")),
                            serial, _number(item.get("used_quantity") or item.get("quantity")),
                            _text(item.get("unit")), _text(item.get("pool")), _json(item), now,
                        ),
                    )
        if export:
            self._maybe_export_json()

    def ingest_close_attempts(self, profile: str, records: Iterable[dict[str, Any]]) -> None:
        changed = False
        with self.lock, closing(self._connect()) as connection, connection:
            for record in records:
                request_id = _text(record.get("request_id"), 100)
                contract = _digits(record.get("contract"))
                if not request_id or not contract:
                    continue
                changed = True
                now = _text(record.get("updated_at")) or _now()
                self._upsert_contract(connection, profile, contract, {
                    "scheduled_date": record.get("scheduled_date"),
                    "city": record.get("city"),
                    "technician_id": record.get("technician_id"),
                    "technician_name": record.get("technician"),
                    "status": record.get("state"),
                }, now)
                connection.execute(
                    """
                    INSERT INTO close_attempts (
                        request_id,profile,contract,os_number,id_os,close_code,
                        close_description,state,category,category_label,message,
                        detail,transport,installed_count,removed_count,material_count,
                        attempts,safe_to_retry,created_at,accepted_at,confirmed_at,
                        updated_at,raw_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(request_id) DO UPDATE SET
                        state=excluded.state,category=excluded.category,
                        category_label=excluded.category_label,message=excluded.message,
                        detail=excluded.detail,attempts=excluded.attempts,
                        safe_to_retry=excluded.safe_to_retry,
                        accepted_at=excluded.accepted_at,confirmed_at=excluded.confirmed_at,
                        updated_at=excluded.updated_at,raw_json=excluded.raw_json
                    """,
                    (
                        request_id, profile, contract, _digits(record.get("num_os")),
                        int(record.get("id_os") or 0), _text(record.get("close_code")),
                        _text(record.get("close_description")), _text(record.get("state")),
                        _text(record.get("category")), _text(record.get("category_label")),
                        _text(record.get("message")), _text(record.get("detail")),
                        _text(record.get("transport")), int(record.get("installed_count") or 0),
                        int(record.get("removed_count") or 0), int(record.get("material_count") or 0),
                        int(record.get("attempts") or 1), int(bool(record.get("safe_to_retry"))),
                        _text(record.get("created_at")), _text(record.get("accepted_at")),
                        _text(record.get("confirmed_at")), now, _json(record),
                    ),
                )
        if changed:
            self._maybe_export_json()

    @staticmethod
    def _rows(connection: sqlite3.Connection, query: str, values: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [dict(row) for row in connection.execute(query, values).fetchall()]

    def contract(self, contract: str, *, profile: str = "") -> dict[str, Any] | None:
        wanted = _digits(contract)
        if not wanted:
            return None
        profile_filter = " AND profile=?" if profile else ""
        params: tuple[Any, ...] = (wanted, profile) if profile else (wanted,)
        with self.lock, closing(self._connect()) as connection, connection:
            row = connection.execute(
                f"SELECT * FROM contracts WHERE contract=?{profile_filter} ORDER BY updated_at DESC LIMIT 1",
                params,
            ).fetchone()
            if row is None:
                return None
            value = dict(row)
            key = (value["profile"], value["contract"])
            value["activities"] = self._rows(connection,
                "SELECT * FROM activities WHERE profile=? AND contract=? ORDER BY scheduled_date,activity_id", key)
            value["orders"] = self._rows(connection,
                "SELECT * FROM orders WHERE profile=? AND contract=? ORDER BY os_number", key)
            inventory = self._rows(connection,
                "SELECT * FROM inventory WHERE profile=? AND contract=? ORDER BY category,description,serial", key)
            for item in inventory:
                item.pop("raw_json", None)
            value["inventory"] = {
                category: [item for item in inventory if item["category"] == category]
                for category in ("installed", "removed", "customer", "material")
            }
            attempts = self._rows(connection,
                "SELECT * FROM close_attempts WHERE profile=? AND contract=? ORDER BY updated_at DESC", key)
            for item in attempts:
                item.pop("raw_json", None)
            value["close_attempts"] = attempts
            value["summary"] = {
                "activity_count": len(value["activities"]),
                "os_count": len(value["orders"]),
                "installed_count": len(value["inventory"]["installed"]),
                "removed_count": len(value["inventory"]["removed"]),
                "material_count": len(value["inventory"]["material"]),
                "attempt_count": len(attempts),
            }
            return value

    def list_contracts(
        self,
        *,
        profile: str = "",
        query: str = "",
        date: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        values: list[Any] = []
        if profile:
            clauses.append("c.profile=?")
            values.append(profile)
        if date:
            clauses.append("c.scheduled_date=?")
            values.append(date)
        normalized_query = _text(query, 160)
        if normalized_query:
            wildcard = f"%{normalized_query}%"
            clauses.append("""(
                c.contract LIKE ? OR c.customer_name LIKE ? OR
                c.technician_name LIKE ? OR EXISTS (
                    SELECT 1 FROM orders o WHERE o.profile=c.profile
                    AND o.contract=c.contract AND o.os_number LIKE ?
                ) OR EXISTS (
                    SELECT 1 FROM inventory i WHERE i.profile=c.profile
                    AND i.contract=c.contract AND i.serial LIKE ?
                )
            )""")
            values.extend([wildcard] * 5)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        safe_limit = min(100_000, max(1, int(limit)))
        with self.lock, closing(self._connect()) as connection, connection:
            rows = self._rows(connection, f"""
                SELECT c.*,
                    (SELECT COUNT(*) FROM orders o WHERE o.profile=c.profile AND o.contract=c.contract) AS os_count,
                    (SELECT COUNT(*) FROM close_attempts a WHERE a.profile=c.profile AND a.contract=c.contract) AS attempt_count,
                    (SELECT state FROM close_attempts a WHERE a.profile=c.profile AND a.contract=c.contract ORDER BY updated_at DESC LIMIT 1) AS last_attempt_state
                FROM contracts c{where}
                ORDER BY c.updated_at DESC LIMIT ?
            """, tuple([*values, safe_limit]))
            total = connection.execute(
                f"SELECT COUNT(*) FROM contracts c{where}", tuple(values)
            ).fetchone()[0]
        return {
            "ok": True,
            "schema_version": self.SCHEMA_VERSION,
            "database": self.database_path.name,
            "json_mirror": self.json_path.name,
            "count": len(rows),
            "total": total,
            "contracts": rows,
        }

    def export_document(self) -> dict[str, Any]:
        summaries = self.list_contracts(limit=100000)["contracts"]
        contracts = [
            value for value in (self.contract(row["contract"], profile=row["profile"]) for row in summaries)
            if value is not None
        ]
        return {
            "schema": "dominium.operational.v1",
            "generated_at": _now(),
            "database_file": self.database_path.name,
            "contract_count": len(contracts),
            "contracts": contracts,
        }

    def export_json(self) -> Path:
        document = self.export_document()
        temporary = self.json_path.with_suffix(self.json_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.json_path)
        return self.json_path

    def _maybe_export_json(self, minimum_interval_seconds: int = 30) -> None:
        try:
            age = dt.datetime.now().timestamp() - self.json_path.stat().st_mtime
        except OSError:
            age = minimum_interval_seconds
        if age >= minimum_interval_seconds:
            self.export_json()
