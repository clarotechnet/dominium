from __future__ import annotations

import copy
import datetime as dt
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable


DEFAULT_INTERVAL_SECONDS = 300
HISTORY_LIMIT = 40


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_clock(value: object) -> tuple[int, int] | None:
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return hour, minute


def review_record_is_due(record: dict[str, Any], now: dt.datetime) -> bool:
    slots = record.get("review_slots")
    if not isinstance(slots, list):
        return False
    current = now.hour * 60 + now.minute
    for raw_slot in slots:
        if str(raw_slot).strip() == "sem_janela":
            continue
        parsed = _parse_clock(raw_slot)
        if parsed is None:
            continue
        if current >= parsed[0] * 60 + parsed[1]:
            return True
    return False


def toa_activity_is_complete(value: object) -> bool:
    normalized = str(value or "").strip().casefold()
    return normalized in {
        "complete",
        "completed",
        "concluida",
        "concluído",
        "concluido",
        "executada",
        "executado",
    }


class AutoImproductiveCloser:
    """Persistent 5-minute controller for TOA -> Imperium improductive closes."""

    def __init__(
        self,
        state_path: Path,
        history_path: Path,
        run_callback: Callable[["AutoImproductiveCloser"], dict[str, Any]],
        *,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        logger: logging.Logger | None = None,
    ) -> None:
        if interval_seconds < 60:
            raise ValueError("interval_seconds must be at least 60")
        self.state_path = state_path.resolve()
        self.history_path = history_path.resolve()
        self.run_callback = run_callback
        self.interval_seconds = int(interval_seconds)
        self.logger = logger or logging.getLogger("imperium.auto-improductive")
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.running = False
        self.next_run_at = 0.0
        self.enabled = False
        self.blocked: dict[str, dict[str, Any]] = {}
        self.last_run: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self.history_totals: dict[str, int] = {
            "runs": 0,
            "closed": 0,
            "closed_new": 0,
            "already_closed": 0,
        }
        self.current_run: dict[str, Any] | None = None
        self._progress_published_at = 0.0
        self._reload_state()
        self._load_history()

    def _state_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "enabled": bool(self.enabled),
            "interval_seconds": self.interval_seconds,
            "blocked": self.blocked,
            "updated_at": _now(),
        }

    def _reload_state(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        with self.lock:
            self.enabled = payload.get("enabled") is True
            raw_blocked = payload.get("blocked")
            if isinstance(raw_blocked, dict):
                self.blocked = {
                    str(key): dict(value)
                    for key, value in raw_blocked.items()
                    if isinstance(value, dict)
                }

    def _persist_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(
            f"{self.state_path.name}.{threading.get_ident()}.tmp"
        )
        serialized = json.dumps(
            self._state_payload(),
            ensure_ascii=True,
            indent=2,
        )
        temporary.write_text(serialized, encoding="utf-8")
        last_error: PermissionError | None = None
        for attempt in range(6):
            try:
                temporary.replace(self.state_path)
                return
            except PermissionError as exc:
                last_error = exc
                if attempt >= 5:
                    break
                time.sleep(0.05 * (attempt + 1))

        try:
            self.state_path.write_text(serialized, encoding="utf-8")
            self.logger.warning(
                "Persistencia atomica do estado foi bloqueada pelo Windows; "
                "fallback para overwrite direto aplicado: %s",
                last_error,
            )
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_history(self) -> None:
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        all_runs: list[dict[str, Any]] = []
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                all_runs.append(value)
        totals = {
            "runs": len(all_runs),
            "closed": sum(int(item.get("closed") or 0) for item in all_runs),
            "closed_new": sum(
                int(item.get("closed_new", item.get("closed") or 0) or 0)
                for item in all_runs
            ),
            "already_closed": sum(
                int(item.get("already_closed") or 0) for item in all_runs
            ),
        }
        loaded = all_runs[-HISTORY_LIMIT:]
        with self.lock:
            self.history = loaded
            self.last_run = loaded[-1] if loaded else None
            self.history_totals = totals

    def _append_history(self, value: dict[str, Any]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        persisted = dict(value)
        persisted.pop("audit_items", None)
        with self.history_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(persisted, ensure_ascii=True, separators=(",", ":"))
            )
            stream.write("\n")
        with self.lock:
            self.history = (self.history + [copy.deepcopy(value)])[-HISTORY_LIMIT:]
            self.last_run = copy.deepcopy(value)
            self.history_totals["runs"] += 1
            self.history_totals["closed"] += int(value.get("closed") or 0)
            self.history_totals["closed_new"] += int(
                value.get("closed_new", value.get("closed") or 0) or 0
            )
            self.history_totals["already_closed"] += int(
                value.get("already_closed") or 0
            )

    def publish_progress(
        self,
        value: dict[str, Any],
        *,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        with self.lock:
            if not force and now - self._progress_published_at < 0.5:
                return
            started_at = (
                self.current_run.get("started_at")
                if isinstance(self.current_run, dict)
                else _now()
            )
            self.current_run = {
                "started_at": started_at,
                "running": True,
                **copy.deepcopy(value),
            }
            self._progress_published_at = now

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._loop,
            name="auto-improductive-close",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        with self.lock:
            self.enabled = bool(enabled)
            if self.enabled:
                self.next_run_at = 0.0
            self._persist_state()
        return self.public_state()

    def block(
        self,
        key: str,
        reason: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        normalized = str(key).strip()
        if not normalized:
            return
        with self.lock:
            self.blocked[normalized] = {
                "reason": str(reason).strip()[:1000],
                "blocked_at": _now(),
                "metadata": dict(metadata or {}),
            }
            self._persist_state()

    def unblock(self, key: str) -> None:
        normalized = str(key).strip()
        with self.lock:
            if normalized in self.blocked:
                self.blocked.pop(normalized, None)
                self._persist_state()

    def is_blocked(self, key: str) -> bool:
        with self.lock:
            return str(key).strip() in self.blocked

    def is_enabled(self) -> bool:
        self._reload_state()
        with self.lock:
            return self.enabled

    def public_state(self) -> dict[str, Any]:
        self._reload_state()
        now = time.monotonic()
        with self.lock:
            next_seconds = (
                max(0, int(self.next_run_at - now))
                if self.enabled and self.next_run_at > 0
                else 0
            )
            return {
                "ok": True,
                "enabled": self.enabled,
                "running": self.running,
                "interval_seconds": self.interval_seconds,
                "next_run_seconds": next_seconds,
                "last_run": copy.deepcopy(self.last_run),
                "current_run": copy.deepcopy(self.current_run),
                "history": [
                    copy.deepcopy(item)
                    for item in reversed(self.history[-10:])
                ],
                "totals": dict(self.history_totals),
                "blocked_count": len(self.blocked),
                "blocked": copy.deepcopy(self.blocked),
            }

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            self._reload_state()
            with self.lock:
                enabled = self.enabled
                due = self.next_run_at <= time.monotonic()
            if not enabled:
                self.stop_event.wait(1.0)
                continue
            if not due:
                self.stop_event.wait(min(1.0, max(0.1, self.next_run_at - time.monotonic())))
                continue
            self._run_once()
            with self.lock:
                self.next_run_at = time.monotonic() + self.interval_seconds

    def _run_once(self) -> None:
        started_monotonic = time.monotonic()
        started_at = _now()
        with self.lock:
            if self.running:
                return
            self.running = True
            self.current_run = {
                "started_at": started_at,
                "running": True,
            }
            self._progress_published_at = 0.0
        try:
            result = self.run_callback(self)
            if not isinstance(result, dict):
                raise TypeError("run_callback must return a dict")
            run = {
                "started_at": started_at,
                "completed_at": _now(),
                "seconds": round(time.monotonic() - started_monotonic, 2),
                "ok": result.get("ok") is not False,
                **result,
            }
        except Exception as exc:
            self.logger.exception("Auto-baixa improdutiva: falha na rodada")
            run = {
                "started_at": started_at,
                "completed_at": _now(),
                "seconds": round(time.monotonic() - started_monotonic, 2),
                "ok": False,
                "error": str(exc),
            }
        finally:
            with self.lock:
                self.running = False
        try:
            self._append_history(run)
        finally:
            with self.lock:
                self.current_run = None
        except OSError:
            self.logger.exception("Auto-baixa improdutiva: falha ao persistir historico")
