"""Idempotent 22:00 (UTC-03:00) read-only DataSnap history scheduling.

This scheduler is scoped to the existing private backlog sidecar, not to
production OS-closing or WhatsApp bots. It only calls BacklogHistoryService.
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
import threading
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOGGER = logging.getLogger("dominium.backlog.daily")
try:
    LOCAL_TZ = ZoneInfo("America/Fortaleza")
except ZoneInfoNotFoundError:
    LOCAL_TZ = dt.timezone(dt.timedelta(hours=-3))

DAILY_SCHEMA = """CREATE TABLE IF NOT EXISTS daily_history_attempts (
 scheduled_date TEXT PRIMARY KEY,
 started_at TEXT NOT NULL,
 run_id TEXT,
 outcome TEXT NOT NULL
)"""

class DailyHistoryScheduler:
    """Starts at most once between 22:00 and 22:44 per local calendar day."""

    def __init__(self, service, *, now=None, max_days_per_profile=7, interval=45.0):
        self.service = service
        self.now = now or (lambda: dt.datetime.now(LOCAL_TZ))
        self.max_days_per_profile = max_days_per_profile
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None
        with service._connect() as conn:
            conn.execute(DAILY_SCHEMA)
            conn.commit()

    def tick(self):
        clock = self.now().astimezone(LOCAL_TZ)
        if clock.hour != 22 or clock.minute >= 45:
            return "outside_window"
        today = clock.date().isoformat()
        with self.service._connect() as conn:
            if conn.execute("SELECT 1 FROM daily_history_attempts WHERE scheduled_date=?",
                            (today,)).fetchone():
                return "already_started"
        if self.service.snapshot()["running"]:
            return "reader_busy"
        # The daily task must not overlap itself, including after restarts.
        with self.service._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO daily_history_attempts"
                "(scheduled_date,started_at,outcome) VALUES(?,?,'starting')",
                (today, clock.isoformat()))
            conn.commit()
            if not cur.rowcount:
                return "already_started"
        try:
            result = self.service.start(mode="batch", days_per_profile=self.max_days_per_profile,
                                        include_today=True)
        except RuntimeError:
            # A competing manual run was started after the busy check.
            with self.service._connect() as conn:
                conn.execute("DELETE FROM daily_history_attempts WHERE scheduled_date=?",
                             (today,))
                conn.commit()
            return "reader_busy"
        except Exception:
            with self.service._connect() as conn:
                conn.execute("UPDATE daily_history_attempts SET outcome='start_failed'"
                             " WHERE scheduled_date=?", (today,))
                conn.commit()
            LOGGER.exception("Unable to start daily DESC history read")
            return "start_failed"
        with self.service._connect() as conn:
            conn.execute("UPDATE daily_history_attempts SET outcome='started',run_id=?"
                         " WHERE scheduled_date=?", (result["run_id"], today))
            conn.commit()
        return "started"

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="dominium-desc-history-22h",
                                        daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except (sqlite3.Error, ValueError):
                LOGGER.exception("Daily history scheduler check failed")
            self._stop.wait(self.interval)

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
