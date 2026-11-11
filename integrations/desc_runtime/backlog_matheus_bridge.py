"""Optional read-only daily Imperium overlay for existing Backlog sidecar.

Preserves BacklogHistoryService and the 42-column XLSX export unchanged.
When five TOA routes are imported, refreshes the day's four Imperium profiles.
Never writes to the Imperium, TOA, legacy history table, or the XLSX module.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import threading
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError

from backlog_imperium_service import BacklogHistoryService
from backlog_matheus_current import MatheusCurrentSnapshot, PROFILES
from backlog_route_today_compare import reconcile_today

try:
    LOCAL_TZ=ZoneInfo("America/Fortaleza")
except ZoneInfoNotFoundError:
    LOCAL_TZ=dt.timezone(dt.timedelta(hours=-3))

class BacklogWithMatheusCurrent(BacklogHistoryService):
    def __init__(self,*args,current_db_path,report_fetcher,current_gate,
                 current_now=None,**kwargs):
        super().__init__(*args,**kwargs)
        self._current_now=current_now or (lambda:dt.datetime.now(LOCAL_TZ))
        self._current=MatheusCurrentSnapshot(
            Path(current_db_path),fetch=report_fetcher,gate=current_gate,
            clock=self._current_now)
        self._current_job={"state":"idle","day":"","last_error":None,
                           "profiles_complete":[]}
        self._current_job_thread=None
        self._current_mutex=threading.RLock()

    def import_route_files(self,files):
        result=super().import_route_files(files)
        # A successful route transaction is already committed. A DataSnap
        # failure must never undo a good TOA route import.
        try:
            self.trigger_current_refresh()
        except Exception as exc:
            with self._current_mutex:
                self._current_job.update(
                    state="blocked",last_error=type(exc).__name__)
        return result

    def trigger_current_refresh(self):
        clock=self._current_now().astimezone(LOCAL_TZ)
        # No unattended processing after 21:00 or before 07:00 local.
        if not 7<=clock.hour<21:
            with self._current_mutex:
                self._current_job.update(
                    state="outside_working_hours",day=clock.date().isoformat())
            return {"started":False,"reason":"outside_working_hours"}
        with self._current_mutex:
            if self._current_job_thread and self._current_job_thread.is_alive():
                return {"started":False,"reason":"already_running"}
            self._current_job={"state":"running","day":clock.date().isoformat(),
                              "last_error":None,"profiles_complete":[]}
            self._current_job_thread=threading.Thread(
                target=self._current_worker,args=(clock.date().isoformat(),),
                name="dominium-native-todos-current",
                daemon=True)
            self._current_job_thread.start()
        return {"started":True,"day":clock.date().isoformat()}

    def _current_worker(self,day):
        completed=[]
        try:
            for profile in PROFILES:
                self._current.refresh(profile,day)
                completed.append(profile)
                with self._current_mutex:
                    self._current_job["profiles_complete"]=list(completed)
        except Exception as exc:
            with self._current_mutex:
                self._current_job.update(
                    state="failed",last_error=type(exc).__name__)
        else:
            with self._current_mutex:
                self._current_job.update(state="completed",last_error=None)

    def current_status(self):
        today=self._current_now().astimezone(LOCAL_TZ).date()
        with self._current_mutex:
            job=dict(self._current_job)
            job["profiles_complete"]=list(job.get("profiles_complete") or ())
        snapshots=[x for x in self._current.summary() if x["day"]==today.isoformat()]
        now=self._current_now().astimezone(dt.timezone.utc)
        recent=(len(snapshots)==len(PROFILES) and
                all(abs((now-dt.datetime.fromisoformat(x["captured_at"]))
                        .total_seconds())<15*60 for x in snapshots))
        summary={"ok":True,"day":today.isoformat(),"job":job,
                 "profiles":snapshots,"fresh":recent,
                 "source":"Imperium TODOS/TODOS - read only",
                 "warning":"This snapshot cannot authorize an OS closure."}
        if len(snapshots)==len(PROFILES):
            try:
                comparison=reconcile_today(self.db_path,self._current.path,today,limit=1)
                summary["routes"]={
                    "route_rows":comparison["route_rows"],
                    "snapshot_rows":comparison["snapshot_rows"],
                    "matches":comparison["matches"],
                    "discrepancies":comparison["discrepancies"],
                    "route_cities":comparison["route_cities"],
                }
            except (OSError,ValueError,sqlite3.Error) as exc:
                summary["routes"]={"state":"unavailable",
                    "reason":type(exc).__name__}
        return summary
