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
import json
import logging
import re
import threading
import urllib.error
import urllib.request
from typing import Any, Callable


COLLECT_INTERVAL_SECONDS = 60


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _minutes(value: object) -> int | None:
    try:
        return max(0, int(str(value or "").strip()))
    except (TypeError, ValueError):
        return None


def _clock(minutes: int | None) -> str:
    if minutes is None:
        return ""
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _service_window(start: int | None, duration: int | None) -> str:
    if start is None:
        return ""
    if duration is None or duration <= 0:
        return _clock(start)
    return f"{_clock(start)} - {_clock(start + duration)}"


def _clean_description(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^🏢", "", text).strip()
    # The gantt aria-label ends in the generic Oracle word "activity".
    text = re.sub(r"\s+activity$", "", text, flags=re.IGNORECASE).strip()
    # Oracle also renders customer/address after the service label. The monitor
    # only needs the first segment, so the remainder is deliberately discarded.
    return text.split(",", 1)[0].strip()[:160]


class TOALocalCollector:
    """Mirrors the authenticated OFS allocation console into the local SQLite store.

    It never stores credentials, cookies, headers or raw Oracle payloads. The first
    pass intentionally reads only the operational gantt model already rendered in
    the authorized browser session. Contract/OS/material details remain the job of
    the existing on-demand TECHCAP lookup.
    """

    SNAPSHOT_SCRIPT = r"""
const activities = [];
const resourceName = new Map();
for (const row of document.querySelectorAll('.toaGantt-provTree .toaGantt-tl[par_pid]')) {
  const pid = String(row.getAttribute('par_pid') || '').trim();
  const name = String(row.querySelector('.toaGantt-tb-name')?.innerText || '')
    .replace(/\s+/g, ' ').trim();
  if (pid && name) resourceName.set(pid, name);
}
for (const element of document.querySelectorAll('.toaGantt-timeChart .toaGantt-tb[data-id^="a_"]')) {
  const pid = String(element.getAttribute('par_pid') || '').trim();
  const aid = String(element.getAttribute('aid') || element.dataset.id || '').replace(/\D/g, '');
  if (!aid) continue;
  activities.push({
    activity_id: aid,
    technician_id: pid,
    technician_name: resourceName.get(pid) || '',
    status: String(element.dataset.activityStatus || ''),
    scheduled_date: String(element.getAttribute('par_date') || ''),
    start_min: String(element.getAttribute('start') || ''),
    duration_min: String(element.getAttribute('dur') || ''),
    eta_min: String(element.dataset.activityEta || ''),
    activity_type: String(element.dataset.activityType || ''),
    work_type_id: String(element.dataset.activityWorktype || ''),
    description: String(element.innerText || element.getAttribute('aria-label') || '')
      .replace(/\s+/g, ' ').trim(),
  });
}
const body = String(document.body?.innerText || '');
const bucket = (body.match(/\b(?:PWM|NTL|FTZ|MRO|JCR)-DMV(?:_[A-Z0-9]+)?\b/) || [''])[0];
return { activities, bucket, title: document.title, url: location.href };
"""

    def __init__(
        self,
        live_session: Any,
        datalake: Any,
        sync_callback: Callable[[dict[str, Any]], None] | None = None,
        *,
        logger: logging.Logger | None = None,
        interval: int = COLLECT_INTERVAL_SECONDS,
        mirror_urls: list[str] | None = None,
    ) -> None:
        self.live_session = live_session
        self.datalake = datalake
        self.sync_callback = sync_callback
        self.logger = logger or logging.getLogger("imperium")
        self.interval = max(20, int(interval))
        self.mirror_urls = [str(url).strip() for url in (mirror_urls or []) if str(url).strip()]
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._state: dict[str, Any] = {
            "running": False,
            "last_collected_at": "",
            "last_activity_count": 0,
            "last_bucket": "",
            "last_error": "",
            "last_mirror": [],
        }

    def _mirror_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        results: list[dict[str, Any]] = []
        for url in self.mirror_urls:
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    results.append({"url": url, "ok": 200 <= response.status < 300})
            except (OSError, urllib.error.URLError) as exc:
                results.append({"url": url, "ok": False, "error": str(exc)[:240]})
        return results

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        with self._state_lock:
            self._state["running"] = True
        self._thread = threading.Thread(
            target=self._loop, name="toa-local-collector", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        with self._state_lock:
            self._state["running"] = False

    def public_state(self) -> dict[str, Any]:
        with self._state_lock:
            return {"ok": True, "interval_seconds": self.interval, **self._state}

    def collect_now(self) -> dict[str, Any]:
        raw = self.live_session.execute_readonly_script(self.SNAPSHOT_SCRIPT)
        if not isinstance(raw, dict):
            raise RuntimeError("O TOA nao retornou um retrato operacional valido")
        bucket = str(raw.get("bucket") or "").strip()[:120]
        observed_at = _now()
        activities: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw.get("activities") or []:
            if not isinstance(item, dict):
                continue
            activity_id = "".join(re.findall(r"\d", str(item.get("activity_id") or "")))
            if not activity_id or activity_id in seen:
                continue
            seen.add(activity_id)
            start = _minutes(item.get("start_min"))
            duration = _minutes(item.get("duration_min"))
            eta = _minutes(item.get("eta_min"))
            status = str(item.get("status") or "").strip().casefold()
            activities.append({
                "activity_id": activity_id,
                "activity_type": str(item.get("activity_type") or "").strip(),
                "parent_id": str(item.get("work_type_id") or "").strip(),
                "description": _clean_description(item.get("description")),
                "bucket": bucket,
                "technician_id": str(item.get("technician_id") or "").strip(),
                "technician_name": str(item.get("technician_name") or "").strip()[:300],
                "status": status,
                "scheduled_date": str(item.get("scheduled_date") or "")[:10],
                "start_min": str(start if start is not None else ""),
                "service_window": _service_window(start, duration),
                "start_time": _clock(eta if status in {"started", "complete"} else None),
                "end_time": _clock((eta + duration) if eta is not None and status == "complete" and duration else None),
            })
        if not activities:
            raise RuntimeError("Nenhuma atividade visivel foi encontrada na Console de Alocacao")
        payload = {
            "schema": self.datalake.SCHEMA,
            "source": "toa-local-console",
            "collector_id": "dominium-local-browser",
            "observed_at": observed_at,
            "activities": activities,
            "orders": [],
            "details": [],
        }
        result = self.datalake.ingest(payload)
        if self.sync_callback:
            self.sync_callback(payload)
        mirrors = self._mirror_payload(payload)
        with self._state_lock:
            self._state.update(
                last_collected_at=observed_at,
                last_activity_count=len(activities),
                last_bucket=bucket,
                last_error="",
                last_mirror=mirrors,
            )
        return {
            "ok": True,
            "bucket": bucket,
            "activity_count": len(activities),
            "ingest": result,
            "mirrors": mirrors,
        }

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                state = self.live_session.public_state()
                if state.get("authenticated"):
                    self.collect_now()
            except Exception as exc:
                with self._state_lock:
                    self._state["last_error"] = str(exc)[:500]
                self.logger.warning("Coletor local TOA: %s", exc)
            self._stop.wait(self.interval)
