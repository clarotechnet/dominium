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
import datetime as dt
import json
import re
import threading
from pathlib import Path
from typing import Any, Iterable


DEFAULT_REVIEW_TIMES = ("09:00", "14:00", "17:20")


def _unique(values: Iterable[object]) -> list[str]:
    return list(dict.fromkeys(
        str(value).strip() for value in values if str(value).strip()
    ))


def _window_start(value: str) -> int | None:
    match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})", str(value))
    if not match:
        return None
    hour, minute = map(int, match.groups())
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def review_slot_for_window(value: str) -> str:
    start = _window_start(value)
    if start is None:
        return "sem_janela"
    for slot in DEFAULT_REVIEW_TIMES:
        hour, minute = map(int, slot.split(":"))
        if start <= hour * 60 + minute:
            return slot
    return DEFAULT_REVIEW_TIMES[-1]


def _iso_date(value: str, fallback: str) -> str:
    normalized = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            continue
    return fallback


class TOAContractRegistry:
    """Persistent, local index of imported contracts grouped by time window."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.lock = threading.RLock()

    def _load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": 1, "records": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), dict):
            return {"version": 1, "records": {}}
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _record_key(profile: str, date: str, contract: str) -> str:
        return f"{profile}:{date}:{contract}"

    @staticmethod
    def _agenda_record_key(profile: str, date: str, contract: str) -> str:
        # A agenda e apenas o indice de pesquisa por janela. Ela nao pode
        # sobrescrever a fotografia completa do mesmo contrato capturada do TOA.
        return f"{profile}:{date}:agenda:{contract}"

    def record_preview(
        self,
        preview: object,
        *,
        profile: str,
        target: str,
        source: str = "",
        seen_at: str | None = None,
    ) -> dict[str, Any]:
        orders = tuple(getattr(preview, "orders", ()) or ())
        now = seen_at or dt.datetime.now().isoformat(timespec="seconds")
        with self.lock:
            payload = self._load()
            records = payload["records"]
            touched: set[str] = set()
            for order in orders:
                contract = str(getattr(order, "contract", "")).strip()
                if not contract:
                    continue
                date = _iso_date(getattr(order, "date", ""), now[:10])
                key = self._record_key(profile, date, contract)
                existing = records.get(key, {})
                window = str(getattr(order, "time_window", "")).strip()
                service_window = str(getattr(order, "service_window", "")).strip()
                os_number = str(getattr(order, "os_number", "")).strip()
                order_context = {
                    "contract": contract,
                    "os_number": os_number,
                    "num_os": os_number,
                    "date": date,
                    "city": str(getattr(order, "city", "")).strip(),
                    "technician": str(getattr(order, "technician_name", "")).strip(),
                    "technician_login": str(
                        getattr(order, "technician_login", "")
                        or getattr(order, "technician", "")
                    ).strip(),
                    "activity_status": str(
                        getattr(order, "activity_status", "")
                    ).strip(),
                    "activity_id": str(getattr(order, "activity_id", "")).strip(),
                    "service": str(getattr(order, "os_type", "")).strip(),
                    "os_status": str(getattr(order, "os_status", "")).strip(),
                    "close_code": str(getattr(order, "close_code", "")).strip(),
                    "time_window": window,
                    "service_window": service_window,
                    "workzone_key": str(
                        getattr(order, "workzone_key", "")
                    ).strip(),
                    "source_file": source,
                }
                existing_orders = {
                    str(item.get("os_number") or item.get("num_os") or ""): item
                    for item in existing.get("orders", ())
                    if isinstance(item, dict)
                    and str(item.get("os_number") or item.get("num_os") or "")
                }
                if os_number:
                    previous_order = existing_orders.get(os_number, {})
                    existing_orders[os_number] = {
                        **previous_order,
                        **{
                            field: value
                            for field, value in order_context.items()
                            if value or field in {
                                "contract", "os_number", "num_os", "date",
                                "os_status", "close_code",
                            }
                        },
                    }
                windows = _unique((*existing.get("windows", ()), window))
                slots = _unique((
                    *existing.get("review_slots", ()),
                    *(review_slot_for_window(item) for item in windows),
                ))
                records[key] = {
                    "profile": profile,
                    "target": target,
                    "date": date,
                    "contract": contract,
                    "cities": _unique((
                        *existing.get("cities", ()),
                        getattr(order, "city", ""),
                    )),
                    "technicians": _unique((
                        *existing.get("technicians", ()),
                        getattr(order, "technician_name", ""),
                        getattr(order, "technician", ""),
                    )),
                    "windows": windows,
                    "service_windows": _unique((
                        *existing.get("service_windows", ()), service_window,
                    )),
                    "review_slots": slots or ["sem_janela"],
                    "os_numbers": _unique((
                        *existing.get("os_numbers", ()),
                        os_number,
                    )),
                    "orders": list(existing_orders.values()),
                    "source_files": _unique((
                        *existing.get("source_files", ()), source,
                    )),
                    "first_seen_at": existing.get("first_seen_at", now),
                    "last_seen_at": now,
                }
                touched.add(key)
            payload.update(
                version=1,
                updated_at=now,
                review_times=list(DEFAULT_REVIEW_TIMES),
            )
            self._save(payload)
        return {"ok": True, "recorded": len(touched), "updated_at": now}

    def replace_agenda(
        self,
        agenda: Iterable[dict[str, Any]],
        *,
        profile: str,
        target: str,
        date: str,
        source: str,
        seen_at: str | None = None,
    ) -> dict[str, Any]:
        """Replace the agenda snapshot without importing or closing any OS."""
        now = seen_at or dt.datetime.now().isoformat(timespec="seconds")
        normalized_date = _iso_date(date, now[:10])
        with self.lock:
            payload = self._load()
            records = payload["records"]
            prefix = f"{profile}:{normalized_date}:"
            for key in [
                key for key, record in records.items()
                if key.startswith(prefix) and record.get("agenda_only") is True
            ]:
                records.pop(key, None)
            recorded = 0
            for item in agenda:
                contract = re.sub(r"\D", "", str(item.get("contract", "")))
                item_date = _iso_date(item.get("date", ""), normalized_date)
                if not contract or item_date != normalized_date:
                    continue
                window = str(item.get("window", "")).strip()
                key = self._agenda_record_key(profile, item_date, contract)
                records[key] = {
                    "profile": profile,
                    "target": target,
                    "date": item_date,
                    "contract": contract,
                    "cities": [],
                    "technicians": [],
                    "windows": [window] if window else [],
                    "service_windows": [],
                    "review_slots": [review_slot_for_window(window)],
                    "os_numbers": [],
                    "orders": [],
                    "source_files": [source] if source else [],
                    "source_rows": list(item.get("source_rows", ())),
                    "window_start": item.get("window_start"),
                    "window_end": item.get("window_end"),
                    "agenda_only": True,
                    "first_seen_at": now,
                    "last_seen_at": now,
                }
                recorded += 1
            payload.update(
                version=1,
                updated_at=now,
                review_times=list(DEFAULT_REVIEW_TIMES),
            )
            self._save(payload)
        return {"ok": True, "recorded": recorded, "updated_at": now}

    def public_state(
        self,
        *,
        profile: str = "",
        date: str = "",
        slot: str = "",
    ) -> dict[str, Any]:
        with self.lock:
            payload = self._load()
        records = list(payload.get("records", {}).values())
        if profile:
            records = [item for item in records if item.get("profile") == profile]
        if date:
            records = [item for item in records if item.get("date") == date]
        if slot:
            records = [item for item in records if slot in item.get("review_slots", ())]
        records.sort(key=lambda item: (
            item.get("date", ""), item.get("review_slots", [""])[0],
            item.get("contract", ""),
        ))
        counts = {
            value: sum(value in item.get("review_slots", ()) for item in records)
            for value in (*DEFAULT_REVIEW_TIMES, "sem_janela")
        }
        return {
            "ok": True,
            "updated_at": payload.get("updated_at", ""),
            "review_times": list(DEFAULT_REVIEW_TIMES),
            "count": len(records),
            "counts_by_slot": counts,
            "records": records,
        }
