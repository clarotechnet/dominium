"""Idempotent bridge from *verified* Backlog SQLite days to private Supabase.

No credentials are stored here. The connection is supplied by a trusted server
process. This module cannot start the DataSnap importer or close an O.S.
"""
from __future__ import annotations

import datetime as dt
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping

PROFILES = {
    "natal": "NATAL/PARNAMIRIM",
    "fortaleza": "FORTALEZA",
    "mossoro": "MOSSORO",
    "recife": "RECIFE",
}
VERIFICATIONS = {"confirmed", "missing_code"}
STATUSES = {"EM CAMPO", "CONCLUIDA", "CANCELADA", "REAGENDADA", "DESCONHECIDO"}
FIELDS = (
    "legacy_id", "contract", "baixa_code", "activity_date", "service",
    "os_number", "cidade", "source_imported_at", "source_profile",
    "source_id_os", "source_verification", "source_status",
    "datasnap_captured_at",
)

UPSERT_HISTORY_SQL = """
INSERT INTO backlog_lab.history (
  legacy_id, contract, baixa_code, activity_date, service,
  os_number, cidade, source_imported_at, source_profile,
  source_id_os, source_verification, source_status, datasnap_captured_at
) VALUES (
  %(legacy_id)s, %(contract)s, %(baixa_code)s, %(activity_date)s, %(service)s,
  %(os_number)s, %(cidade)s, %(source_imported_at)s, %(source_profile)s,
  %(source_id_os)s, %(source_verification)s, %(source_status)s, %(datasnap_captured_at)s
)
ON CONFLICT (legacy_id) DO UPDATE SET
  contract=excluded.contract, baixa_code=excluded.baixa_code,
  activity_date=excluded.activity_date, service=excluded.service,
  os_number=excluded.os_number, cidade=excluded.cidade,
  source_imported_at=excluded.source_imported_at,
  source_profile=excluded.source_profile, source_id_os=excluded.source_id_os,
  source_verification=excluded.source_verification,
  source_status=excluded.source_status,
  datasnap_captured_at=excluded.datasnap_captured_at,
  synced_at=now();
"""

COUNT_HISTORY_SQL = """
SELECT count(*) FROM backlog_lab.history
WHERE source_profile=%s AND activity_date=%s;
"""

UPSERT_CHECKPOINT_SQL = """
INSERT INTO backlog_lab.datasnap_checkpoints
(profile,last_completed_day,rows_written,updated_at)
VALUES (%s,%s,%s,now())
ON CONFLICT (profile) DO UPDATE SET
 last_completed_day=EXCLUDED.last_completed_day,
 rows_written=EXCLUDED.rows_written, updated_at=now()
 WHERE backlog_lab.datasnap_checkpoints.last_completed_day <= EXCLUDED.last_completed_day;
"""

class IncompleteDay(ValueError):
    """A source day was not reconciled and checkpointed in SQLite."""


def _iso_date(value: object) -> str:
    raw = str(value or "")
    try:
        date = dt.date.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid activity date") from exc
    if date.isoformat() != raw:
        raise ValueError("date must be ISO-8601")
    return raw


def _iso_timestamp(value: object) -> str:
    raw = str(value or "")
    try:
        timestamp = dt.datetime.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid capture timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("capture timestamp must include timezone")
    return raw


def map_history_row(row: Mapping[str, Any]) -> dict[str, Any]:
    profile = str(row.get("profile") or "")
    if profile not in PROFILES:
        raise ValueError("invalid profile")
    day = _iso_date(row.get("activity_date"))
    try:
        id_os = int(row["id_os"])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid id_os") from exc
    if id_os <= 0 or id_os > 2**63 - 1:
        raise ValueError("invalid id_os")
    contract = str(row.get("contract") or "").strip()
    os_number = str(row.get("os_number") or "").strip()
    if not re.fullmatch(r"[0-9]{1,32}", contract):
        raise ValueError("invalid contract")
    if not re.fullmatch(r"[0-9]{5,32}", os_number):
        raise ValueError("invalid O.S. number")
    verification = str(row.get("verification") or "")
    if verification not in VERIFICATIONS:
        raise ValueError("unconfirmed source verification")
    raw_code = str(row.get("code") or "").strip()
    if verification == "confirmed":
        if not re.fullmatch(r"[0-9]{3}", raw_code) or raw_code == "000":
            raise ValueError("confirmed code is invalid")
    elif raw_code:
        raise ValueError("missing_code must not carry an inferred code")
    status = str(row.get("status") or "")
    if status not in STATUSES:
        raise ValueError("invalid DataSnap status")
    timestamp = _iso_timestamp(row.get("captured_at"))
    service = str(row.get("service") or "")
    if not service or len(service) > 300:
        raise ValueError("invalid service")
    payload = {
        "legacy_id": f"{profile}:{id_os}:{day}",
        "contract": contract,
        "baixa_code": raw_code,
        "activity_date": day,
        "service": service,
        "os_number": os_number,
        "cidade": PROFILES[profile],
        "source_imported_at": timestamp,
        "source_profile": profile,
        "source_id_os": id_os,
        "source_verification": verification,
        "source_status": status,
        "datasnap_captured_at": timestamp,
    }
    assert tuple(payload) == FIELDS
    return payload


def read_verified_day(sqlite_path: str | Path, profile: str, day: str) -> list[dict[str, Any]]:
    """Read a day ONLY after the source checkpoint was durably committed."""
    if profile not in PROFILES:
        raise ValueError("invalid profile")
    day = _iso_date(day)
    path = Path(sqlite_path)
    if not path.is_file():
        raise FileNotFoundError("source SQLite database unavailable")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        cp = conn.execute("SELECT date FROM checkpoint WHERE profile=?", (profile,)).fetchone()
        if cp is None or _iso_date(cp["date"]) < day:
            raise IncompleteDay("source checkpoint has not confirmed this day")
        rows = conn.execute(
            """SELECT profile,id_os,activity_date,os_number,contract,service,
                      code,verification,status,captured_at
                 FROM history WHERE profile=? AND activity_date=?
                 ORDER BY id_os LIMIT 3001""",
            (profile, day),
        ).fetchall()
        if len(rows) > 3000:
            raise IncompleteDay("unbounded DataSnap day")
        mapped = [map_history_row(dict(row)) for row in rows]
        keys = [row["legacy_id"] for row in mapped]
        if len(keys) != len(set(keys)):
            raise IncompleteDay("duplicate O.S. identity in day")
        return mapped
    finally:
        conn.close()


def write_verified_day(pg_connection: Any, profile: str, day: str, rows: list[dict[str, Any]]) -> int:
    """One PostgreSQL transaction for ALL rows and the checkpoint.

    Requires a trusted server-side psycopg3 connection. Never use REST
    single-row writes, public keys, or browser credentials.
    """
    if profile not in PROFILES:
        raise ValueError("invalid profile")
    day = _iso_date(day)
    if len(rows) > 3000:
        raise ValueError("unbounded day")
    for row in rows:
        if row["source_profile"] != profile or row["activity_date"] != day:
            raise ValueError("row belongs to another profile/day")
        if tuple(row) != FIELDS:
            raise ValueError("row payload differs from allowlist")
    with pg_connection.transaction():
        with pg_connection.cursor() as cursor:
            for row in rows:
                cursor.execute(UPSERT_HISTORY_SQL, row)
            cursor.execute(COUNT_HISTORY_SQL, (profile, day))
            actual = int(cursor.fetchone()[0])
            if actual != len(rows):
                raise IncompleteDay("row count mismatch; checkpoint not advanced")
            cursor.execute(UPSERT_CHECKPOINT_SQL, (profile, day, len(rows)))
    return len(rows)


def sync_verified_day(pg_connection: Any, sqlite_path: str | Path, profile: str, day: str) -> int:
    """Safe entrypoint: will NEVER advance Supabase before SQLite checkpoint."""
    verified_rows = read_verified_day(sqlite_path, profile, day)
    return write_verified_day(pg_connection, profile, day, verified_rows)
