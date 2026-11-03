"""Fail-closed guard for read-only Imperium history when OS writers are active."""
from __future__ import annotations
import json
import threading
import time
import urllib.request

class OperationalReadGate:
    def __init__(self, *, api_base="http://127.0.0.1:8765/api/", cache_seconds=10):
        self.api_base=api_base
        self.cache_seconds=cache_seconds
        self._next_check=0.0
        self._mutex=threading.Lock()

    def __call__(self):
        with self._mutex:
            now=time.monotonic()
            if now<self._next_check:
                return
            def status(route):
                with urllib.request.urlopen(self.api_base+route,timeout=4) as res:
                    if res.status!=200:
                        raise RuntimeError("Status operacional indisponivel")
                    return json.load(res)
            # Fail closed on authentication failure, broken JSON, timeout, or uncertain state.
            auto=status("auto-improductive-close")
            if auto.get("enabled") or auto.get("running") or (auto.get("productive_autoclose") or {}).get("enabled"):
                raise RuntimeError("Consulta historica adiada: baixa automatica ativa")
            nightly=status("nightly-backlog")
            if nightly.get("running"):
                raise RuntimeError("Consulta historica adiada: lote 106 ativo")
            disconnect=status("disconnect-automation")
            if disconnect.get("current_contract"):
                raise RuntimeError("Consulta historica adiada: DESC em execucao")
            batch=status("disconnect-batch/status")
            if str(batch.get("status") or "").lower() in ("running","processing","queued"):
                raise RuntimeError("Consulta historica adiada: lote DESC ativo")
            self._next_check=time.monotonic()+self.cache_seconds
