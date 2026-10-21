"""Persistent operator feedback, scoped to the private authenticated DESC relay.

The store accepts structured human reports, not browser logs or credentials.
All filenames are fixed; records are append-only on the TECHNET server.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import uuid
from pathlib import Path

ALLOWED_KINDS = frozenset({"erro", "melhoria", "sugestao"})
ALLOWED_SEVERITIES = frozenset({"baixa", "media", "alta"})
_TOKEN = re.compile(r"(?i)(?:bearer\s+\S+|(?:password|senha|token|secret|cookie|authorization)\s*[:=]\s*(?:bearer\s+)?\S+)")
REPORT_LIMIT = 2 * 1024 * 1024


class ReportError(ValueError):
    pass


def _safe(value: object, limit: int) -> str:
    if not isinstance(value, str):
        raise ReportError("Campo de relatório inválido")
    return _TOKEN.sub("[informação protegida]", value.strip())[:limit]


class OperatorReports:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def _records(self) -> list[dict]:
        if not self.path.is_file():
            return []
        with self.path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - REPORT_LIMIT))
            if size > REPORT_LIMIT:
                f.readline()  # skip potentially partial first line
            tail = f.readlines()
        result = []
        for line in tail[-250:]:
            try:
                value = json.loads(line)
                if isinstance(value, dict) and "id" in value:
                    result.append(value)
            except (ValueError, UnicodeError):
                continue
        return result

    def list(self, limit: int = 50) -> list[dict]:
        with self.lock:
            return list(reversed(self._records()[-min(max(limit, 1), 100):]))

    def add(self, raw: dict, actor: str) -> dict:
        if not isinstance(raw, dict) or len(json.dumps(raw, ensure_ascii=False)) > 12000:
            raise ReportError("Relatório muito grande")
        kind = raw.get("kind")
        severity = raw.get("severity", "media")
        if kind not in ALLOWED_KINDS or severity not in ALLOWED_SEVERITIES:
            raise ReportError("Tipo de relatório inválido")
        title = _safe(raw.get("title", ""), 120)
        detail = _safe(raw.get("detail", ""), 3000)
        area = _safe(raw.get("area", "desconexao"), 50)
        contract = _safe(raw.get("contract", ""), 25)
        diagnostics = _safe(raw.get("diagnostics", ""), 500)
        who = _safe(actor, 100)
        if not (5 <= len(title) and 10 <= len(detail)):
            raise ReportError("Informe título e descrição")
        if area not in {"desconexao", "operacao", "estoque", "seriais", "outros"}:
            area = "outros"
        if contract and not re.fullmatch(r"\d{7}", contract):
            raise ReportError("Contrato inválido")
        if not who:
            raise ReportError("Operador não identificado")
        record = {
            "id": str(uuid.uuid4()), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "actor": who, "kind": kind, "severity": severity,
            "title": title, "detail": detail, "area": area,
            "contract": contract, "diagnostics": diagnostics,
            "status": "recebido",
        }
        with self.lock:
            latest = self._records()
            boundary = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
            recent = sum(1 for item in latest if item.get("actor") == who
                         and item.get("created_at", "") >= boundary.isoformat())
            if recent >= 20:
                raise ReportError("Limite de relatórios atingido; tente novamente mais tarde")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                output.flush()
                os.fsync(output.fileno())
        return record
