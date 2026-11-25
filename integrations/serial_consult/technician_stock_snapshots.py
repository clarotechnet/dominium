"""Persist daily balances read from the existing Imperium stock consultation."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Thread
from uuid import uuid4

LOGGER = logging.getLogger(__name__)
BRAZIL = timezone(timedelta(hours=-3))
PORTS = {"natal": 212, "fortaleza": 596, "mossoro": 579, "recife": 599}
BATCH_SIZE = 5
LEASE = timedelta(minutes=15)
CODE = re.compile(r"[A-Z0-9_-]{1,32}\Z")


def now():
    return datetime.now(BRAZIL)


def material_code(value):
    code = str(value if value is not None else "").strip().upper()
    if not CODE.fullmatch(code):
        raise ValueError("Código de material inválido")
    return (code.lstrip("0") or "0") if code.isdigit() else code


def quantity(value):
    try:
        amount = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Quantidade inválida") from exc
    if not amount.is_finite():
        raise ValueError("Quantidade inválida")
    return amount


def build_inventory(stock):
    if stock.get("ok") is not True or not isinstance(stock.get("items"), list):
        raise ValueError("Consulta de estoque incompleta")
    items = []
    for item in stock["items"]:
        if "code" not in item or "quantity" not in item:
            raise ValueError("Consulta de estoque sem código ou saldo")
        items.append({
            "code": material_code(item["code"]),
            "description": str(item.get("equipment") or "").strip(),
            "unit": str(item.get("unit") or "").strip().upper(),
            "quantity": format(quantity(item["quantity"]), "f"),
        })
    return items


def operational_stock_client(city):
    from imperium_api import ImperiumAPI
    from order_reports import RUNTIME

    return ImperiumAPI(RUNTIME, port=PORTS[city], company=city, profile_key=city)


class TechnicianStockSnapshots:
    def __init__(self, root, client_factory=operational_stock_client, clock=now):
        Path(root).mkdir(parents=True, exist_ok=True)
        self.db_path = Path(root) / "technician-stock.sqlite3"
        self.client_factory = client_factory
        self.clock = clock
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS technician_stock_runs (
                    id TEXT PRIMARY KEY,
                    city TEXT NOT NULL,
                    day TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('running','complete','failed')),
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expected INTEGER NOT NULL DEFAULT 0,
                    collected INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS technician_stock_one_run_per_day
                ON technician_stock_runs(city, day) WHERE state IN ('running','complete');
                CREATE TABLE IF NOT EXISTS technician_stock_locations (
                    run_id TEXT NOT NULL REFERENCES technician_stock_runs(id),
                    stock_id INTEGER NOT NULL,
                    installer_id INTEGER NOT NULL,
                    stock_name TEXT NOT NULL,
                    technician_name TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    inventory TEXT NOT NULL,
                    PRIMARY KEY(run_id, stock_id)
                );
            """)

    @contextmanager
    def _connect(self):
        with closing(sqlite3.connect(self.db_path, timeout=15)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db

    def status(self, city, day):
        with self._connect() as db:
            row = db.execute("""
                SELECT id, city, day, state, started_at, updated_at, expected, collected, error
                FROM technician_stock_runs WHERE city=? AND day=?
                ORDER BY started_at DESC, rowid DESC LIMIT 1
            """, (city, day)).fetchone()
        result = dict(row) if row else None
        if result and result["state"] == "running" and self._expired(result):
            result.update(state="failed", error="Coleta interrompida. Inicie novamente.")
        return result

    def _expired(self, row):
        return self.clock() - datetime.fromisoformat(row["updated_at"]) > LEASE

    def start(self, city, actor, *, background=True):
        if city not in PORTS:
            raise ValueError("Selecione uma cidade")
        started = self.clock()
        day = started.date().isoformat()
        run_id = uuid4().hex
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("""
                SELECT id, state, updated_at FROM technician_stock_runs WHERE city=? AND day=?
                AND state IN ('running','complete')
            """, (city, day)).fetchone()
            if current and current["state"] == "running" and self._expired(current):
                db.execute("""
                    UPDATE technician_stock_runs SET state='failed', error=? WHERE id=?
                """, ("Coleta interrompida. Inicie novamente.", current["id"]))
                current = None
            if current is None:
                db.execute("""
                    INSERT INTO technician_stock_runs(id, city, day, actor, state, started_at, updated_at)
                    VALUES(?,?,?,?,'running',?,?)
                """, (run_id, city, day, actor, started.isoformat(), started.isoformat()))
        if current is None:
            if background:
                Thread(target=self._capture, args=(run_id, city, day), daemon=True,
                       name=f"technician-stock-{city}").start()
            else:
                self._capture(run_id, city, day)
        return self.status(city, day)

    def _capture(self, run_id, city, day):
        try:
            api = self.client_factory(city)
            locations = api.list_stock_technicians()
            stock_ids = list(dict.fromkeys(int(row["stock_id"]) for row in locations))
            if not stock_ids:
                raise ValueError("O Imperium não retornou estoques de técnicos")
            with self._connect() as db:
                db.execute("""
                    UPDATE technician_stock_runs SET expected=?, updated_at=? WHERE id=? AND state='running'
                """, (len(stock_ids), self.clock().isoformat(), run_id))
            for start in range(0, len(stock_ids), BATCH_SIZE):
                ids = stock_ids[start:start+BATCH_SIZE]
                stocks = api.technician_stocks(ids)
                captured = self.clock()
                if captured.date().isoformat() != day:
                    raise ValueError("A coleta terminou após a virada do dia")
                by_stock = {int(s["technician"]["stock_id"]): s for s in stocks}
                if len(stocks) != len(ids) or set(by_stock) != set(ids):
                    raise ValueError("A consulta retornou locais diferentes do solicitado")
                rows = []
                for stock_id in ids:
                    stock = by_stock[stock_id]
                    owner = stock["technician"]
                    rows.append((
                        run_id, stock_id, int(owner["installer_id"]), owner["stock_name"],
                        owner["technician_name"], captured.isoformat(),
                        json.dumps(build_inventory(stock), ensure_ascii=False, separators=(",", ":")),
                    ))
                with self._connect() as db:
                    active = db.execute("""
                        UPDATE technician_stock_runs SET collected=collected+?, updated_at=?
                        WHERE id=? AND state='running'
                    """, (len(rows), captured.isoformat(), run_id)).rowcount
                    if not active:
                        return
                    db.executemany("""
                        INSERT INTO technician_stock_locations
                        (run_id,stock_id,installer_id,stock_name,technician_name,captured_at,inventory)
                        VALUES(?,?,?,?,?,?,?)
                    """, rows)
            with self._connect() as db:
                db.execute("""
                    UPDATE technician_stock_runs SET state='complete', updated_at=?
                    WHERE id=? AND state='running' AND expected>0 AND collected=expected
                """, (self.clock().isoformat(), run_id))
        except Exception as exc:
            LOGGER.warning("Technician stock capture failed: city=%s error=%s", city, type(exc).__name__)
            with self._connect() as db:
                db.execute("""
                    UPDATE technician_stock_runs SET state='failed', updated_at=?, error=?
                    WHERE id=? AND state='running'
                """, (self.clock().isoformat(),
                      "Coleta incompleta. Consulte o Imperium e tente novamente.", run_id))

    def saved_locations(self, city, day):
        with self._connect() as db:
            rows = db.execute("""
                SELECT l.* FROM technician_stock_locations l
                JOIN technician_stock_runs r ON r.id=l.run_id
                WHERE r.city=? AND r.day=? AND r.state='complete' ORDER BY l.stock_id
            """, (city, day)).fetchall()
        return [dict(row, inventory=json.loads(row["inventory"])) for row in rows]
