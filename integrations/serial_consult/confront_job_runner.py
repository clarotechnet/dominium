"""Durable, one-step-at-a-time confrontation worker (not a public HTTP endpoint).

Do NOT start this in production without operator authentication and ACL review.
State is stored outside the Git working tree. No automated Atlas re-enqueue
after uncertainty; BotDMV's queue is in-memory and has no idempotency key.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
import time
import uuid
from pathlib import Path
from typing import Callable

from atlas_bridge_client import AtlasBridgeClient, AtlasBridgeError
from confront_engine import classify_pair, normalize_serials, SUPPORTED_MODES, SUPPORTED_PROFILES

TERMINAL = frozenset({"complete", "review_needed"})
LEASE_SECONDS = 120
ATLAS_RESULT_MAX_SECONDS = 8 * 60


class ConfrontJobStore:
    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        if self.path.suffix != ".sqlite3":
            raise ValueError("Arquivo de trabalho precisa ser SQLite")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, profile TEXT NOT NULL, mode TEXT NOT NULL,
                    created_at REAL NOT NULL, created_by TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS job_items (
                    job_id TEXT NOT NULL, position INTEGER NOT NULL, serial TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending_imperium',
                    imperium_json TEXT, atlas_json TEXT, request_id TEXT,
                    submitted_at REAL, result_json TEXT, error_code TEXT,
                    retry_after REAL NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (job_id, position),
                    UNIQUE (job_id, serial),
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_job_items_work ON
                    job_items (job_id, state, retry_after, lease_until, position);
            """)

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(str(self.path), timeout=5.0)
        try:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA busy_timeout = 5000")
            con.execute("PRAGMA foreign_keys = ON")
            with con:
                yield con
        finally:
            con.close()

    def create(self, serials: str | list[str], *, profile: str, mode: str,
               created_by: str = "") -> str:
        if profile not in SUPPORTED_PROFILES or mode not in SUPPORTED_MODES:
            raise ValueError("Praca ou modo invalido")
        values = normalize_serials(serials)
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as con:
            con.execute("INSERT INTO jobs(id,profile,mode,created_at,created_by) VALUES (?,?,?,?,?)",
                        (job_id, profile, mode, now, created_by[:100]))
            con.executemany("""
                INSERT INTO job_items(job_id, position, serial, state, updated_at)
                VALUES (?, ?, ?, 'pending_imperium', ?)
            """, [(job_id, i, serial, now) for i, serial in enumerate(values)])
        return job_id

    def owned(self, job_id: str, actor: str) -> bool:
        with self._connect() as con:
            row = con.execute("SELECT 1 FROM jobs WHERE id=? AND created_by=?",
                              (job_id, actor[:100])).fetchone()
            return row is not None

    def list_jobs(self, actor: str, limit: int = 20) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("""
                SELECT id, profile, mode, created_at FROM jobs
                WHERE created_by=? ORDER BY created_at DESC LIMIT ?
            """, (actor[:100], min(20, max(1, limit)))).fetchall()
        return [dict(row) for row in rows]

    def resumable_job_ids(self, limit: int = 40) -> list[str]:
        with self._connect() as con:
            rows = con.execute("""
                SELECT jobs.id FROM jobs JOIN job_items ON job_items.job_id=jobs.id
                WHERE job_items.state NOT IN ('complete','review_needed')
                GROUP BY jobs.id ORDER BY MIN(jobs.created_at) ASC LIMIT ?
            """, (min(40, max(1, limit)),)).fetchall()
        return [row[0] for row in rows]

    def recover_uncertain(self, job_id: str, *, now: float | None = None) -> int:
        """Resolve orphaned submission states WITHOUT enqueuing another request."""
        timestamp = float(now if now is not None else time.time())
        with self._connect() as con:
            cur = con.execute("""
                UPDATE job_items SET state='review_needed',
                    error_code='atlas_submission_interrupted', updated_at=?,
                    retry_after=0, lease_until=0
                WHERE job_id=? AND state='submitting_atlas'
                  AND updated_at < ?
            """, (timestamp, job_id, timestamp - LEASE_SECONDS))
            return cur.rowcount

    def progress(self, job_id: str, *, include_rows: bool = False) -> dict:
        with self._connect() as con:
            job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if job is None:
                raise ValueError("Trabalho nao encontrado")
            grouped = con.execute("""
                SELECT state, COUNT(*) as count FROM job_items WHERE job_id = ?
                GROUP BY state
            """, (job_id,)).fetchall()
            counts = {row["state"]: row["count"] for row in grouped}
            total = sum(counts.values())
            out = {"job_id": job_id, "profile": job["profile"], "mode": job["mode"],
                   "total": total, "done": sum(counts.get(x, 0) for x in TERMINAL),
                   "states": counts}
            if include_rows:
                out["rows"] = [
                    {"serial": item["serial"], "state": item["state"],
                     "error_code": item["error_code"],
                     "resultado": json.loads(item["result_json"]) if item["result_json"] else None}
                    for item in con.execute("""
                        SELECT serial, state, error_code, result_json FROM job_items
                        WHERE job_id=? ORDER BY position
                    """, (job_id,))
                ]
            return out

    def _claim(self, job_id: str, now: float):
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            job = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None:
                raise ValueError("Trabalho nao encontrado")
            row = con.execute("""
                SELECT * FROM job_items WHERE job_id = ?
                  AND state IN ('pending_imperium','pending_atlas','awaiting_atlas')
                  AND lease_until <= ? AND retry_after <= ?
                ORDER BY position LIMIT 1
            """, (job_id, now, now)).fetchone()
            if row:
                con.execute("""
                    UPDATE job_items SET lease_until=?,updated_at=?
                    WHERE job_id=? AND position=?
                """, (now + LEASE_SECONDS, now, job_id, row["position"]))
                return dict(job), dict(row)
            return dict(job), None

    def _update(self, job_id: str, position: int, now: float, **fields) -> None:
        values = {**fields, "lease_until": 0, "updated_at": now}
        keys = list(values)
        with self._connect() as con:
            con.execute("UPDATE job_items SET " +
                        ", ".join(f"{key}=?" for key in keys) +
                        " WHERE job_id=? AND position=?",
                        [*(values[key] for key in keys), job_id, position])

    def step(self, job_id: str, *, imperium_query: Callable, atlas_client: AtlasBridgeClient,
             now: float | None = None) -> str:
        """Process at most one phase of one serial. Safe to call from a timed worker.

        Returns a phase label, not customer data. Never runs in a request handler.
        """
        now = float(now if now is not None else time.time())
        job, item = self._claim(job_id, now)
        if item is None:
            return "idle"
        serial, position, state = item["serial"], item["position"], item["state"]
        if state == "pending_imperium":
            try:
                answer = imperium_query(([serial], job["mode"], job["profile"]))
                matching = [r for r in (answer.get("results") or [])
                            if isinstance(r, dict) and r.get("serial") == serial]
                current = matching[0] if answer.get("ok") is True and matching else None
            except Exception:
                current = None
            self._update(job_id, position, now, state="pending_atlas",
                         imperium_json=json.dumps(current, ensure_ascii=False))
            return "imperium_consulted"

        imperium = json.loads(item["imperium_json"]) if item["imperium_json"] else None
        if state == "pending_atlas":
            if not atlas_client.valid_serial(serial):
                result = classify_pair(serial, imperium, {"ok": False})
                self._update(job_id, position, now, state="complete",
                             atlas_json=json.dumps({"ok": False}),
                             result_json=json.dumps(result), error_code="unsupported_atlas_serial")
                return "serial_not_supported"
            try:
                status = atlas_client.status()
                if status.get("online") is not True or int(status.get("pendingQueries") or 0) > 0:
                    self._update(job_id, position, now, retry_after=now + 8)
                    return "atlas_busy"
            except Exception:
                self._update(job_id, position, now, retry_after=now + 15)
                return "atlas_offline"

            # Persist uncertainty BEFORE POST. Power loss at this point cannot
            # cause automatic duplicate submissions after process restart.
            self._update(job_id, position, now, state="submitting_atlas")
            try:
                request_id = atlas_client.enqueue(serial)
            except Exception:
                self._update(job_id, position, now, state="review_needed",
                             error_code="atlas_submission_uncertain")
                return "atlas_submit_uncertain"
            self._update(job_id, position, now, state="awaiting_atlas",
                         request_id=request_id, submitted_at=now,
                         retry_after=now + 2)
            return "atlas_enqueued"

        if state == "awaiting_atlas":
            request_id = item.get("request_id")
            age = now - float(item.get("submitted_at") or now)
            if not request_id or age >= ATLAS_RESULT_MAX_SECONDS:
                self._update(job_id, position, now, state="review_needed",
                             error_code="atlas_result_expired")
                return "atlas_result_expired"
            try:
                atlas = atlas_client.poll_result(request_id, serial)
            except (AtlasBridgeError, OSError, ValueError):
                atlas = None
            if atlas is None:
                self._update(job_id, position, now, retry_after=now + 4)
                return "atlas_waiting"
            result = classify_pair(serial, imperium, atlas)
            self._update(job_id, position, now, state="complete",
                         atlas_json=json.dumps(atlas, ensure_ascii=False),
                         result_json=json.dumps(result, ensure_ascii=False))
            return "serial_complete"

        return "idle"
