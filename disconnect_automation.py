# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - contem validacao, consulta ou operacao ligada ao Imperium.
#
# TOA
# - SIM - contem captura, contexto, importacao ou evidencia vinda do TOA.
#
# DOMINIUM COMPARTILHADO
# - Ponte entre os dois dominios; alterar com testes dos dois lados.
#
# Categoria deste arquivo: MISTO.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import copy
import datetime as dt
import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_PROFILE = "natal"
SUPPORTED_TARGET = "rn"
WAIT_SECONDS = 30
LEASE_SECONDS = 10 * 60

WINDOWS = {
    "08:00-11:00": {
        "start": 8 * 60,
        "end": 11 * 60,
        "cutoff": 11 * 60 + 20,
        "priority": 0,
        "label": "08:00 - 11:00",
    },
    "08:00-12:00": {
        "start": 8 * 60,
        "end": 12 * 60,
        "cutoff": 12 * 60 + 20,
        "priority": 1,
        "label": "08:00 - 12:00",
    },
    "11:00-14:00": {
        "start": 11 * 60,
        "end": 14 * 60,
        "cutoff": 14 * 60 + 20,
        "priority": 2,
        "label": "11:00 - 14:00",
    },
    "08:00-22:00": {
        "start": 8 * 60,
        "end": 22 * 60,
        "cutoff": 22 * 60 + 20,
        "priority": 3,
        "label": "08:00 - 22:00",
    },
}

ACTIVE_STATUSES = {
    "pending",
    "checking_toa",
    "waiting_toa",
    "ready",
}
NON_REPEATABLE_STATUSES = {
    "submitting",
    "awaiting_confirmation",
    "completed",
    "manual_review",
    "failed",
    "expired",
}
SUBMIT_RESULT_STATUSES = {
    "awaiting_confirmation",
    "completed",
    "failed",
}
TERMINAL_STATUSES = {
    "awaiting_confirmation",
    "completed",
    "manual_review",
    "failed",
    "expired",
}
UPDATE_STATUSES = ACTIVE_STATUSES | NON_REPEATABLE_STATUSES

_SOURCE_PATTERN = re.compile(
    r"(?:^|[-_])(NTL|PWM)[-_]DMV[-_]ADM(?:[-_.]|$)",
    re.IGNORECASE,
)
_WINDOW_PATTERN = re.compile(
    r"(?<!\d)(\d{1,2})(?::(\d{2}))?\s*[-\u2013]\s*"
    r"(\d{1,2})(?::(\d{2}))?(?!\d)"
)


def _now(value: dt.datetime | None = None) -> dt.datetime:
    current = value or dt.datetime.now()
    return current.replace(microsecond=0)


def _iso(value: dt.datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse_iso(value: object) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _unique(values: Iterable[object]) -> list[str]:
    return list(dict.fromkeys(
        str(value).strip() for value in values if str(value).strip()
    ))


def normalize_window(value: object) -> str:
    match = _WINDOW_PATTERN.search(str(value))
    if not match:
        return ""
    start_hour, start_minute, end_hour, end_minute = match.groups()
    start = f"{int(start_hour):02d}:{int(start_minute or 0):02d}"
    end = f"{int(end_hour):02d}:{int(end_minute or 0):02d}"
    key = f"{start}-{end}"
    return key if key in WINDOWS else ""


def validate_sources(values: Iterable[object]) -> tuple[list[str], list[str]]:
    sources = _unique(values)
    if not sources:
        return [], ["source_file_missing"]
    routes: list[str] = []
    errors: list[str] = []
    for source in sources:
        match = _SOURCE_PATTERN.search(Path(source).name)
        if not match:
            errors.append(f"source_not_ntl_pwm_adm:{Path(source).name}")
            continue
        routes.append(match.group(1).upper())
    return _unique(routes), errors


def _is_transient_legacy_manual_review(item: dict[str, Any]) -> bool:
    if item.get("status") != "manual_review":
        return False
    error = str(item.get("last_error") or "").strip().casefold()
    return (
        error == "a sessao toa nao esta autenticada"
        or error == "activity_not_complete"
        or (error.startswith("task_not_executed:") and error.endswith(":n"))
    )


class DisconnectAutomation:
    """Durable scheduler for the operator-controlled disconnect queue."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.lock = threading.RLock()
        self._recover_interrupted_run()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "version": 1,
            "profile": SUPPORTED_PROFILE,
            "target": SUPPORTED_TARGET,
            "date": "",
            "status": "idle",
            "items": {},
            "current_contract": "",
            "message": "",
        }

    def _load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
            return self._empty()
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def _recover_interrupted_run(self) -> None:
        with self.lock:
            payload = self._load()
            if payload.get("status") != "running":
                return
            current = str(payload.get("current_contract", ""))
            item = payload.get("items", {}).get(current)
            if item and item.get("status") == "checking_toa":
                item.update(
                    status="pending",
                    lease_token="",
                    lease_until="",
                    last_error="",
                )
            payload.update(
                status="paused",
                current_contract="",
                message="Painel reiniciado; clique em Continuar para retomar.",
                updated_at=_iso(_now()),
            )
            self._save(payload)

    @staticmethod
    def _record_item(record: dict[str, Any], current: dt.datetime) -> dict[str, Any]:
        contract = str(record.get("contract", "")).strip()
        routes, source_errors = validate_sources(record.get("source_files", ()))
        normalized_windows = _unique(
            normalize_window(value) for value in record.get("windows", ())
        )
        normalized_windows = [value for value in normalized_windows if value]
        errors = list(source_errors)
        if len(normalized_windows) != 1:
            errors.append(
                "window_missing_or_ambiguous"
                if not normalized_windows
                else "multiple_supported_windows"
            )
        if not contract:
            errors.append("contract_missing")
        window = normalized_windows[0] if len(normalized_windows) == 1 else ""
        status = "manual_review" if errors else "pending"
        return {
            "contract": contract,
            "date": str(record.get("date", "")),
            "profile": str(record.get("profile", "")),
            "target": str(record.get("target", "")),
            "routes": routes,
            "source_files": _unique(record.get("source_files", ())),
            "windows": _unique(record.get("windows", ())),
            "window": window,
            "window_label": WINDOWS.get(window, {}).get("label", ""),
            "priority": WINDOWS.get(window, {}).get("priority", 99),
            "os_numbers": _unique(record.get("os_numbers", ())),
            "technicians": _unique(record.get("technicians", ())),
            "status": status,
            "attempts": 0,
            "created_at": _iso(current),
            "updated_at": _iso(current),
            "last_check_at": "",
            "next_check_at": "",
            "lease_token": "",
            "lease_until": "",
            "last_error": "",
            "reasons": errors,
            "result": {},
        }

    def prepare(
        self,
        records: Iterable[dict[str, Any]],
        *,
        date: str,
        profile: str,
        target: str,
        now: dt.datetime | None = None,
    ) -> dict[str, Any]:
        current = _now(now)
        if profile != SUPPORTED_PROFILE or target != SUPPORTED_TARGET:
            raise ValueError("A automacao aceita somente NATAL/PARNAMIRIM (RN)")
        with self.lock:
            previous = self._load()
            previous_items = (
                previous.get("items", {})
                if previous.get("date") == date
                and previous.get("profile") == profile
                and previous.get("target") == target
                else {}
            )
            items: dict[str, dict[str, Any]] = {}
            ignored = 0
            for record in records:
                if (
                    str(record.get("profile", "")) != profile
                    or str(record.get("target", "")) != target
                    or str(record.get("date", "")) != date
                ):
                    ignored += 1
                    continue
                item = self._record_item(record, current)
                contract = item["contract"]
                if not contract:
                    ignored += 1
                    continue
                if any(
                    reason == "source_file_missing"
                    or reason.startswith("source_not_ntl_pwm_adm:")
                    for reason in item["reasons"]
                ):
                    ignored += 1
                    continue
                old = previous_items.get(contract)
                if old and _is_transient_legacy_manual_review(old):
                    item.update(
                        attempts=int(old.get("attempts") or 0),
                        created_at=str(old.get("created_at") or item["created_at"]),
                        result={
                            "stage": "Aguardando nova consulta no TOA",
                            "message": (
                                "Tratativa transitória reaberta após a correção "
                                "do monitor TOA."
                            ),
                        },
                    )
                elif old and old.get("status") in (
                    NON_REPEATABLE_STATUSES | ACTIVE_STATUSES
                ):
                    preserved = copy.deepcopy(old)
                    preserved.update({
                        "source_files": item["source_files"],
                        "routes": item["routes"],
                        "windows": item["windows"],
                        "window": item["window"],
                        "window_label": item["window_label"],
                        "priority": item["priority"],
                        "os_numbers": item["os_numbers"],
                        "technicians": item["technicians"],
                    })
                    item = preserved
                items[contract] = item
            payload = {
                "version": 1,
                "profile": profile,
                "target": target,
                "date": date,
                "status": "paused",
                "items": items,
                "current_contract": "",
                "message": (
                    (
                        "Fila preparada somente com NTL/PWM-DMV_ADM. "
                        f"{ignored} registro(s) de outros buckets foram ignorados."
                    )
                    if items else
                    "Nenhum contrato NTL/PWM-DMV_ADM encontrado para a data."
                ),
                "prepared_at": _iso(current),
                "updated_at": _iso(current),
                "ignored_records": ignored,
            }
            self._save(payload)
            return self._public(payload, current)

    def action(
        self,
        action: str,
        *,
        now: dt.datetime | None = None,
    ) -> dict[str, Any]:
        current = _now(now)
        normalized = str(action).strip().casefold()
        status_by_action = {
            "start": "running",
            "continue": "running",
            "pause": "paused",
            "stop": "stopped",
        }
        if normalized not in status_by_action:
            raise ValueError("Acao de automacao invalida")
        with self.lock:
            payload = self._load()
            if normalized in {"start", "continue"} and not payload.get("items"):
                raise ValueError("A fila de desconexao esta vazia")
            if (
                normalized in {"start", "continue"}
                and payload.get("status") == "completed"
            ):
                raise ValueError("A fila ja foi concluida")
            payload["status"] = status_by_action[normalized]
            payload["message"] = {
                "start": "Automacao iniciada.",
                "continue": "Automacao retomada.",
                "pause": "Automacao pausada e salva.",
                "stop": "Automacao parada. O progresso foi preservado.",
            }[normalized]
            payload["updated_at"] = _iso(current)
            self._save(payload)
            return self._public(payload, current)

    @staticmethod
    def _minute_of_day(current: dt.datetime) -> int:
        return current.hour * 60 + current.minute

    @staticmethod
    def _is_due(item: dict[str, Any], current: dt.datetime) -> bool:
        due = _parse_iso(item.get("next_check_at"))
        return due is None or due <= current

    @staticmethod
    def _eligible(item: dict[str, Any], current: dt.datetime) -> bool:
        window = WINDOWS.get(str(item.get("window", "")))
        if not window:
            return False
        minute = DisconnectAutomation._minute_of_day(current)
        return window["start"] <= minute <= window["cutoff"]

    @staticmethod
    def _unfinished(item: dict[str, Any]) -> bool:
        # A queued official request is no longer consuming this scheduling
        # window. Its asynchronous confirmation is tracked separately and
        # must not hold every later 08:00-12:00 order indefinitely.
        return item.get("status") in (ACTIVE_STATUSES | {"submitting"})

    def _expire_and_recover(
        self, payload: dict[str, Any], current: dt.datetime
    ) -> None:
        minute = self._minute_of_day(current)
        for item in payload.get("items", {}).values():
            if item.get("status") == "checking_toa":
                lease_until = _parse_iso(item.get("lease_until"))
                if lease_until and lease_until <= current:
                    item.update(
                        status="pending",
                        lease_token="",
                        lease_until="",
                        last_error="Consulta interrompida; pronta para nova leitura.",
                    )
            window = WINDOWS.get(str(item.get("window", "")))
            if (
                window
                and minute > window["cutoff"]
                and item.get("status") in ACTIVE_STATUSES
            ):
                item.update(
                    status="expired",
                    reasons=_unique((*item.get("reasons", ()), "window_expired")),
                    updated_at=_iso(current),
                    lease_token="",
                    lease_until="",
                )

    def claim(self, *, now: dt.datetime | None = None) -> dict[str, Any]:
        current = _now(now)
        with self.lock:
            payload = self._load()
            self._expire_and_recover(payload, current)
            if payload.get("status") != "running":
                self._save(payload)
                return {"ok": True, "claimed": False, "state": self._public(payload, current)}

            items = list(payload.get("items", {}).values())
            unfinished_0811 = any(
                item.get("window") == "08:00-11:00" and self._unfinished(item)
                for item in items
            )
            candidates = [
                item for item in items
                if item.get("status") in {"pending", "waiting_toa", "ready"}
                and self._eligible(item, current)
                and self._is_due(item, current)
                and not (
                    item.get("window") == "08:00-12:00" and unfinished_0811
                )
            ]
            candidates.sort(key=lambda item: (
                int(item.get("priority", 99)),
                int(item.get("attempts", 0)),
                str(item.get("contract", "")),
            ))
            if not candidates:
                self._finish_if_done(payload, current)
                self._save(payload)
                return {"ok": True, "claimed": False, "state": self._public(payload, current)}

            item = candidates[0]
            token = uuid.uuid4().hex
            item.update(
                status="checking_toa",
                attempts=int(item.get("attempts", 0)) + 1,
                last_check_at=_iso(current),
                lease_token=token,
                lease_until=_iso(current + dt.timedelta(seconds=LEASE_SECONDS)),
                updated_at=_iso(current),
                last_error="",
            )
            payload["current_contract"] = item["contract"]
            payload["message"] = f"Consultando contrato {item['contract']} no TOA."
            payload["updated_at"] = _iso(current)
            self._save(payload)
            return {
                "ok": True,
                "claimed": True,
                "lease_token": token,
                "item": copy.deepcopy(item),
                "state": self._public(payload, current),
            }

    def update(
        self,
        contract: str,
        lease_token: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str = "",
        reasons: Iterable[object] = (),
        now: dt.datetime | None = None,
    ) -> dict[str, Any]:
        current = _now(now)
        normalized_status = str(status).strip()
        if normalized_status not in UPDATE_STATUSES:
            raise ValueError("Status de automacao invalido")
        with self.lock:
            payload = self._load()
            item = payload.get("items", {}).get(str(contract))
            if not item:
                raise ValueError("Contrato nao pertence a fila atual")
            expected = str(item.get("lease_token", ""))
            if expected and expected != str(lease_token):
                raise ValueError("A consulta deste contrato pertence a outra execucao")
            current_status = str(item.get("status", ""))
            is_submit_result = (
                current_status == "submitting"
                and normalized_status in SUBMIT_RESULT_STATUSES | {"submitting"}
                and expected
                and expected == str(lease_token)
            )
            if current_status in NON_REPEATABLE_STATUSES and not is_submit_result:
                raise ValueError("Este contrato ja possui resultado nao repetivel")
            item.update(
                status=normalized_status,
                updated_at=_iso(current),
                last_error=str(error).strip(),
                reasons=_unique((*item.get("reasons", ()), *reasons)),
                result=copy.deepcopy(result or item.get("result", {})),
            )
            if normalized_status == "waiting_toa":
                item["next_check_at"] = _iso(
                    current + dt.timedelta(seconds=WAIT_SECONDS)
                )
            else:
                item["next_check_at"] = ""
            if normalized_status not in {"checking_toa", "submitting"}:
                item["lease_token"] = ""
                item["lease_until"] = ""
                payload["current_contract"] = ""
            payload["message"] = {
                "waiting_toa": f"Contrato {contract} ainda aguarda conclusao no TOA.",
                "ready": f"Contrato {contract} pronto para validacao final.",
                "submitting": f"Enviando uma unica solicitacao do contrato {contract}.",
                "awaiting_confirmation": (
                    f"Contrato {contract} enviado; aguardando confirmacao."
                ),
                "completed": f"Contrato {contract} concluido.",
                "manual_review": f"Contrato {contract} requer tratativa humana.",
                "failed": f"Contrato {contract} falhou e nao sera repetido.",
                "expired": f"A janela do contrato {contract} expirou.",
                "pending": f"Contrato {contract} devolvido a fila.",
                "checking_toa": f"Consultando contrato {contract}.",
            }[normalized_status]
            self._finish_if_done(payload, current)
            payload["updated_at"] = _iso(current)
            self._save(payload)
            return self._public(payload, current)

    @staticmethod
    def _finish_if_done(payload: dict[str, Any], current: dt.datetime) -> None:
        items = list(payload.get("items", {}).values())
        if items and all(item.get("status") in TERMINAL_STATUSES for item in items):
            payload["status"] = "completed"
            payload["current_contract"] = ""
            payload["message"] = "Fila concluida. Revise os itens com tratativa humana."
            payload["completed_at"] = _iso(current)

    def public_state(self, *, now: dt.datetime | None = None) -> dict[str, Any]:
        current = _now(now)
        with self.lock:
            payload = self._load()
            self._expire_and_recover(payload, current)
            self._finish_if_done(payload, current)
            self._save(payload)
            return self._public(payload, current)

    @staticmethod
    def _public(payload: dict[str, Any], current: dt.datetime) -> dict[str, Any]:
        items = list(payload.get("items", {}).values())
        counts: dict[str, int] = {}
        for item in items:
            key = str(item.get("status", "pending"))
            counts[key] = counts.get(key, 0) + 1
        visible_items = sorted(
            (copy.deepcopy(item) for item in items),
            key=lambda item: (
                int(item.get("priority", 99)),
                str(item.get("contract", "")),
            ),
        )
        next_checks = [
            value for value in (
                _parse_iso(item.get("next_check_at")) for item in items
            )
            if value is not None
        ]
        return {
            "ok": True,
            "profile": payload.get("profile", SUPPORTED_PROFILE),
            "target": payload.get("target", SUPPORTED_TARGET),
            "date": payload.get("date", ""),
            "status": payload.get("status", "idle"),
            "message": payload.get("message", ""),
            "current_contract": payload.get("current_contract", ""),
            "count": len(items),
            "ignored_records": int(payload.get("ignored_records", 0)),
            "counts": counts,
            "next_check_at": _iso(min(next_checks)) if next_checks else "",
            "updated_at": payload.get("updated_at", ""),
            "now": _iso(current),
            "items": visible_items,
        }
