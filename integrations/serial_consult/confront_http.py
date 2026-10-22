"""Private HTTP interface and supervised background job scheduler.

Only mounted AFTER the existing DESC relay validates its server-to-server token,
operator identity and operational role. Never bind this module directly to the web.
"""
from __future__ import annotations

import io
import json
import logging
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from atlas_bridge_client import AtlasBridgeClient
from confront_export import confront_csv
from confront_job_runner import ConfrontJobStore
from serial_service import consult_serials

JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
ACTOR = re.compile(r"user-[1-9][0-9]{0,18}\Z")
DB_FILE = Path(r"C:\DominiumRuntime\ConfrontJobData\jobs.sqlite3")


def parse_confront_route(method: str, target: str):
    if method not in {"GET", "POST"} or len(target) > 2048:
        return None
    try:
        url = urlsplit(target)
    except ValueError:
        return None
    if url.query or url.fragment or url.scheme or url.netloc:
        return None
    if url.path == "/api/confront/status" and method == "GET":
        return ("status", None)
    if url.path == "/api/confront/jobs":
        return ("create" if method == "POST" else "list", None)
    match = re.fullmatch(r"/api/confront/jobs/([a-f0-9]{32})(/export)?", url.path)
    if match and method == "GET":
        return ("export" if match.group(2) else "detail", match.group(1))
    return None


class ConfrontService:
    def __init__(self, *, store=None, atlas=None, imperium=None, start_worker=True):
        self.store = store if store is not None else ConfrontJobStore(DB_FILE)
        self.atlas = atlas if atlas is not None else AtlasBridgeClient()
        self.imperium = imperium if imperium is not None else consult_serials
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopped = threading.Event()
        self._thread = None
        if start_worker:
            self._thread = threading.Thread(target=self._run, name="dominium-confront",
                                            daemon=True)
            self._thread.start()

    def close(self):
        self._stopped.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self):
        # Revisit jobs after a process restart; never resubmit uncertain POSTs.
        while not self._stopped.is_set():
            try:
                jobs = self.store.resumable_job_ids()
                worked = False
                for job_id in jobs:
                    self.store.recover_uncertain(job_id)
                    phase = self.store.step(job_id, imperium_query=self.imperium,
                                            atlas_client=self.atlas)
                    if phase not in ("idle", "atlas_busy", "atlas_waiting", "atlas_offline"):
                        worked = True
                if not worked:
                    self._wake.wait(timeout=4)
                    self._wake.clear()
            except Exception as exc:
                logging.warning("Confront background exception type=%s", type(exc).__name__)
                self._wake.wait(timeout=10)
                self._wake.clear()

    @staticmethod
    def _actor(raw: str):
        if not ACTOR.fullmatch(raw or ""):
            raise ValueError("Identidade operacional invalida")
        return raw

    def handle(self, method: str, target: str, actor: str, body: dict | None = None):
        route = parse_confront_route(method, target)
        if route is None:
            return 404, {"ok": False, "error": "Rota nao permitida"}, None
        try:
            actor = self._actor(actor)
            action, job_id = route
            if action == "status":
                try:
                    info = self.atlas.status()
                except Exception:
                    info = {}
                return 200, {"ok": True, "atlas_online": info.get("online") is True,
                             "atlas_pendentes": int(info.get("pendingQueries") or 0),
                             "modo": "somente_leitura"}, None
            if action == "list":
                return 200, {"ok": True, "jobs": self.store.list_jobs(actor)}, None
            if action == "create":
                body = body if isinstance(body, dict) else {}
                if set(body) - {"serials", "profile", "mode"}:
                    raise ValueError("Campos desconhecidos")
                with self._lock:
                    open_jobs = [entry["id"] for entry in self.store.list_jobs(actor)
                                 if self.store.progress(entry["id"])["done"]
                                 < self.store.progress(entry["id"])["total"]]
                    if open_jobs:
                        return 409, {"ok": False, "error": "Conclua o trabalho atual antes de iniciar outro"}, None
                    job_id = self.store.create(body.get("serials", ""),
                        profile=body.get("profile", ""),
                        mode=body.get("mode", "analitico"), created_by=actor)
                self._wake.set()
                return 201, {"ok": True, "job": self.store.progress(job_id)}, None
            if not JOB_ID.fullmatch(job_id or "") or not self.store.owned(job_id, actor):
                return 404, {"ok": False, "error": "Trabalho nao encontrado"}, None
            if action == "detail":
                return 200, {"ok": True, "job": self.store.progress(job_id, include_rows=True)}, None
            if action == "export":
                report = self.store.progress(job_id, include_rows=True)
                if report["done"] < report["total"]:
                    return 409, {"ok": False, "error": "Relatorio ainda em processamento"}, None
                rows = []
                for record in report["rows"]:
                    result = record.get("resultado")
                    if result is None:
                        result = {"serial": record["serial"], "situacao": "inconclusivo",
                                  "motivos": [record.get("error_code") or "revisao_manual"],
                                  "alertas": [], "atlas": None, "imperium": None,
                                  "evidencias": []}
                    rows.append(result)
                return 200, confront_csv({"resultados": rows}), "text/csv; charset=utf-8"
            return 404, {"ok": False, "error": "Rota nao permitida"}, None
        except ValueError:
            return 400, {"ok": False, "error": "Parametros de confronto invalidos"}, None
        except Exception as exc:
            logging.warning("Confront HTTP error type=%s", type(exc).__name__)
            return 503, {"ok": False, "error": "Confronto temporariamente indisponivel"}, None
