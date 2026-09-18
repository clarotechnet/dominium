# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - protocolo, baixa, estoque ou operacao do Imperium.
#
# TOA
# - NAO - este arquivo nao consulta nem automatiza o TOA.
#
# DOMINIUM COMPARTILHADO
# - Apoio local apenas quando necessario ao fluxo Imperium.
#
# Categoria deste arquivo: IMPERIUM.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any


ACTIVE_STATES = {"sending", "pending", "uncertain"}
FINAL_STATES = {"confirmed", "failed"}
VALID_STATES = ACTIVE_STATES | FINAL_STATES


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _text(value: Any, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


class CloseReportStore:
    """Thread-safe, append-oriented audit for close attempts.

    The report intentionally stores metadata and counts only. Credentials, tokens,
    request payloads and full serial lists never belong in this file.
    """

    def __init__(self, root: Path, profile: str) -> None:
        self.root = Path(root)
        self.profile = _text(profile, 40).lower()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def path_for(self, date: dt.date) -> Path:
        return self.root / f"relatorio-baixas-{date:%Y%m%d}.json"

    def _read_unlocked(self, date: dt.date) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path_for(date).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        if not isinstance(payload, list):
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _write_unlocked(self, date: dt.date, records: list[dict[str, Any]]) -> None:
        path = self.path_for(date)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def begin(
        self,
        record: dict[str, Any],
        *,
        date: dt.date | None = None,
        block_active_duplicate: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        report_date = date or dt.date.today()
        now = _now()
        with self._lock:
            records = self._read_unlocked(report_date)
            id_os = int(record.get("id_os") or 0)
            fingerprint = _text(record.get("fingerprint"), 128)
            if block_active_duplicate:
                for previous in records:
                    same_order = int(previous.get("id_os") or 0) == id_os
                    same_fingerprint = bool(
                        fingerprint
                        and _text(previous.get("fingerprint"), 128) == fingerprint
                    )
                    if (
                        previous.get("state") in ACTIVE_STATES
                        and (same_order or same_fingerprint)
                    ):
                        duplicate = dict(previous)
                        duplicate["duplicate_request"] = True
                        return duplicate, True

            value = {
                "request_id": uuid.uuid4().hex,
                "report_date": report_date.isoformat(),
                "profile": self.profile,
                "id_os": id_os,
                "id_service": max(0, int(record.get("id_service") or 0)),
                "num_os": _text(record.get("num_os"), 40),
                "contract": _text(record.get("contract"), 40),
                "service": _text(record.get("service"), 240),
                "city": _text(record.get("city"), 100),
                "technician": _text(
                    record.get("technician") or record.get("installer"), 160
                ),
                "technician_id": _nonnegative_int(
                    record.get("technician_id")
                    or record.get("installer_id")
                ),
                "close_code": _text(record.get("close_code"), 16),
                "close_description": _text(record.get("close_description"), 240),
                "transport": _text(record.get("transport"), 40) or "datasnap",
                "state": "sending",
                "category": "PROCESSING",
                "category_label": "Processando",
                "message": "Enviando solicitacao de baixa",
                "detail": "",
                "installed_count": max(0, int(record.get("installed_count") or 0)),
                "removed_count": max(0, int(record.get("removed_count") or 0)),
                "material_count": max(0, int(record.get("material_count") or 0)),
                "materials_summary": _text(record.get("materials_summary"), 1000),
                "installed_equipment_summary": _text(
                    record.get("installed_equipment_summary"), 1000
                ),
                "removed_equipment_summary": _text(
                    record.get("removed_equipment_summary"), 1000
                ),
                "materials": record.get("materials") if isinstance(record.get("materials"), list) else [],
                "installed_equipment": record.get("installed_equipment") if isinstance(record.get("installed_equipment"), list) else [],
                "removed_equipment": record.get("removed_equipment") if isinstance(record.get("removed_equipment"), list) else [],
                "observation": _text(record.get("observation"), 1000),
                "fingerprint": fingerprint,
                "toa_paste_key": _text(record.get("toa_paste_key"), 64),
                "scheduled_date": _text(record.get("scheduled_date"), 20),
                "retry_of_request_id": _text(
                    record.get("retry_of_request_id"), 80
                ),
                "attempts": max(1, int(record.get("attempts") or 1)),
                "safe_to_retry": False,
                "attribution": _text(record.get("attribution"), 40) or "pending",
                "created_at": now,
                "updated_at": now,
                "accepted_at": "",
                "confirmed_at": "",
            }
            records.insert(0, value)
            self._write_unlocked(report_date, records)
            return dict(value), False

    def update(
        self,
        request_id: str,
        changes: dict[str, Any],
        *,
        date: dt.date | None = None,
    ) -> dict[str, Any] | None:
        report_date = date or dt.date.today()
        identifier = _text(request_id, 80)
        with self._lock:
            records = self._read_unlocked(report_date)
            for index, record in enumerate(records):
                if record.get("request_id") != identifier:
                    continue
                value = dict(record)
                state = _text(changes.get("state", value.get("state")), 40)
                if state not in VALID_STATES:
                    raise ValueError(f"Estado de relatorio invalido: {state}")
                value.update(
                    {
                        "state": state,
                        "category": _text(
                            changes.get("category", value.get("category")), 40
                        ),
                        "category_label": _text(
                            changes.get(
                                "category_label", value.get("category_label")
                            ),
                            120,
                        ),
                        "message": _text(
                            changes.get("message", value.get("message")), 1000
                        ),
                        "detail": _text(
                            changes.get("detail", value.get("detail")), 2000
                        ),
                        "safe_to_retry": bool(
                            changes.get(
                                "safe_to_retry", value.get("safe_to_retry", False)
                            )
                        ),
                        "updated_at": _now(),
                    }
                )
                for field in ("accepted_at", "confirmed_at"):
                    if field in changes:
                        value[field] = _text(changes[field], 80)
                if "attempts" in changes:
                    value["attempts"] = max(1, int(changes["attempts"] or 1))
                for field in ("official_http_status", "confirmation_checks"):
                    if field in changes:
                        value[field] = max(0, int(changes[field] or 0))
                if "last_confirmation_error" in changes:
                    value["last_confirmation_error"] = _text(
                        changes["last_confirmation_error"], 1000
                    )
                if "attribution" in changes:
                    value["attribution"] = _text(changes["attribution"], 40)
                if "official_http_response" in changes:
                    value["official_http_response"] = _text(
                        changes["official_http_response"], 2000
                    )
                records[index] = value
                self._write_unlocked(report_date, records)
                return dict(value)
        return None

    def get(
        self,
        request_id: str,
        *,
        date: dt.date | None = None,
    ) -> dict[str, Any] | None:
        identifier = _text(request_id, 80)
        return next(
            (
                record
                for record in self.list(date)
                if record.get("request_id") == identifier
            ),
            None,
        )

    def authorize_retry(
        self,
        request_id: str,
        id_os: int,
        *,
        date: dt.date | None = None,
        close_code: str = "",
        transport: str = "",
    ) -> dict[str, Any]:
        report_date = date or dt.date.today()
        previous = self.get(request_id, date=report_date)
        if previous is None:
            raise ValueError("A tentativa anterior nao existe no relatorio")
        if int(previous.get("id_os") or 0) != int(id_os):
            raise ValueError("A tentativa anterior pertence a outra OS")
        if previous.get("state") != "uncertain":
            raise ValueError("Somente uma tentativa nao confirmada pode ser repetida")
        if int(previous.get("confirmation_checks") or 0) < 7:
            raise ValueError("A confirmacao da tentativa anterior ainda nao terminou")
        expected_code = _text(close_code, 16)
        if expected_code and _text(previous.get("close_code"), 16) != expected_code:
            raise ValueError("A nova tentativa deve manter o mesmo codigo de baixa")
        expected_transport = _text(transport, 40)
        previous_transport = _text(previous.get("transport"), 40)
        allowed_transport_fallback = {
            previous_transport,
            expected_transport,
        } == {"official_http", "datasnap"}
        if (
            expected_transport
            and previous_transport != expected_transport
            and not allowed_transport_fallback
        ):
            raise ValueError("A nova tentativa deve manter o mesmo canal de envio")
        updated = self.update(
            request_id,
            {
                "state": "failed",
                "category": "CONFIRMED_OPEN",
                "category_label": "Confirmada aberta",
                "message": (
                    "A OS foi relida aberta no Imperium; repeticao controlada "
                    "liberada"
                ),
                "detail": (
                    "A tentativa anterior nao alterou o estado observado da OS"
                ),
                "safe_to_retry": True,
                "attribution": "not_closed",
            },
            date=report_date,
        )
        if updated is None:
            raise ValueError("Nao foi possivel atualizar a tentativa anterior")
        return updated

    def list(self, date: dt.date | None = None) -> list[dict[str, Any]]:
        report_date = date or dt.date.today()
        with self._lock:
            records = self._read_unlocked(report_date)
        return sorted(
            records,
            key=lambda item: _text(item.get("updated_at"), 80),
            reverse=True,
        )

    def unresolved(self, date: dt.date | None = None) -> list[dict[str, Any]]:
        return [
            record
            for record in self.list(date)
            if record.get("state") in ACTIVE_STATES
        ]

    def public_state(self, date: dt.date | None = None) -> dict[str, Any]:
        report_date = date or dt.date.today()
        records = self.list(report_date)
        summary = {
            "confirmed": 0,
            "pending": 0,
            "uncertain": 0,
            "failed": 0,
        }
        for record in records:
            state = record.get("state")
            if state == "confirmed":
                summary["confirmed"] += 1
            elif state in {"sending", "pending"}:
                summary["pending"] += 1
            elif state == "uncertain":
                summary["uncertain"] += 1
            elif state == "failed":
                summary["failed"] += 1
        public_records = []
        for record in records:
            value = dict(record)
            value.pop("fingerprint", None)
            value.pop("toa_paste_key", None)
            public_records.append(value)
        return {
            "ok": True,
            "date": report_date.isoformat(),
            "count": len(records),
            "summary": summary,
            "records": public_records,
        }
