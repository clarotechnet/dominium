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
"""Restricted single-request executor for an official Imperium close payload."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import hmac
import http.client
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

from official_close_dry_run import (
    ControlledDryRunError,
    validate_single_official_payload,
)


OFFICIAL_CLOSE_ENDPOINT = (
    "https://www.sistemaimperium.com.br/technet/ordemservico"
)
TOKEN_ENVIRONMENT_VARIABLE = "IMPERIUM_OFFICIAL_TOKEN"
OPERATION_STATES = frozenset(
    {"prepared", "sending", "queued", "rejected", "uncertain"}
)
BLOCKING_STATES = frozenset(
    {"prepared", "sending", "queued", "confirmed", "uncertain"}
)


class OfficialCloseSenderError(RuntimeError):
    pass


class OfficialCloseValidationError(OfficialCloseSenderError):
    pass


class FingerprintMismatchError(OfficialCloseSenderError):
    pass


class OperationConflictError(OfficialCloseSenderError):
    pass


class RejectedReauthorizationRequired(OfficialCloseSenderError):
    pass


class OfficialCloseUncertainError(OfficialCloseSenderError):
    pass


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    body: bytes | str | None = b""


class OfficialCloseTransport(Protocol):
    def send(
        self,
        *,
        endpoint: str,
        body: bytes,
        token: str,
    ) -> TransportResponse:
        ...


class HttpsOfficialCloseTransport:
    """One-shot standard-library transport with no internal repetition."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser maior que zero")
        self.timeout_seconds = timeout_seconds

    def send(
        self,
        *,
        endpoint: str,
        body: bytes,
        token: str,
    ) -> TransportResponse:
        if endpoint != OFFICIAL_CLOSE_ENDPOINT:
            raise ValueError("Endpoint oficial inesperado")
        connection = http.client.HTTPSConnection(
            "www.sistemaimperium.com.br",
            timeout=self.timeout_seconds,
        )
        try:
            connection.request(
                "POST",
                "/technet/ordemservico",
                body=body,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "DOMINIUM/1.0",
                },
            )
            response = connection.getresponse()
            return TransportResponse(
                status_code=int(response.status),
                body=response.read(8193),
            )
        finally:
            connection.close()


def canonical_official_json(payload: Any) -> str:
    validated = validate_single_official_payload(payload)
    return json.dumps(
        validated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def official_payload_fingerprint(payload: Any) -> str:
    canonical = canonical_official_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _timestamp(clock: Callable[[], dt.datetime]) -> str:
    value = clock()
    if not isinstance(value, dt.datetime):
        raise OfficialCloseSenderError("O relogio do executor retornou valor invalido")
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _operation_id(value: Any) -> str:
    operation_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", operation_id):
        raise OfficialCloseSenderError(
            "operation_id deve usar somente letras, numeros, ponto, hifen ou sublinhado"
        )
    return operation_id


def _sanitize_response_body(
    value: bytes | str | None,
    *,
    secrets: tuple[str, ...] = (),
) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value or "")
    text = text[:8192]
    secret_patterns = (
        (
            re.compile(r"(?i)\bAuthorization\s*[:=]\s*Bearer\s+\S+"),
            "Authorization: [REDACTED]",
        ),
        (
            re.compile(
                r"(?i)\b(token|password|senha|cookie|client[_-]?secret)"
                r"\b(\s*[:=]\s*)([\"']?)[^,\s\"'<>]+"
            ),
            r"\1\2[REDACTED]",
        ),
        (
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
            "Bearer [REDACTED]",
        ),
    )
    for pattern, replacement in secret_patterns:
        text = pattern.sub(replacement, text)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


class OperationStore:
    def __init__(
        self,
        root: str | Path,
        *,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.root = Path(root)
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.lock_path = self.root / ".operations.lock"

    def _path(self, operation_id: str) -> Path:
        return self.root / f"{_operation_id(operation_id)}.json"

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as error:
            raise OperationConflictError(
                "O diario de operacoes esta bloqueado por outra execucao"
            ) from error
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.fsync(descriptor)
            yield
        finally:
            os.close(descriptor)
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    def _atomic_write(self, path: Path, record: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _records_unlocked(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise OperationConflictError(
                    f"O diario possui registro ilegivel: {path.name}"
                ) from error
            if not isinstance(record, dict):
                raise OperationConflictError(
                    f"O diario possui registro invalido: {path.name}"
                )
            records.append(record)
        return records

    def create_prepared(
        self,
        *,
        operation_id: str,
        number: str,
        fingerprint: str,
        rejected_reauthorization: str | None,
    ) -> dict[str, Any]:
        operation_id = _operation_id(operation_id)
        path = self._path(operation_id)
        with self._locked():
            if path.exists():
                raise OperationConflictError("operation_id ja utilizado")

            records = self._records_unlocked()
            if any(
                record.get("operation_id") == operation_id for record in records
            ):
                raise OperationConflictError("operation_id ja utilizado")

            matching_os = [
                record
                for record in records
                if record.get("numero_os") == number
            ]
            blocking = sorted(
                {
                    str(record.get("state") or "")
                    for record in matching_os
                    if record.get("state") in BLOCKING_STATES
                }
            )
            if blocking:
                raise OperationConflictError(
                    "A mesma OS ja possui operacao em estado: "
                    + ", ".join(blocking)
                )

            rejected = any(
                record.get("state") == "rejected" for record in matching_os
            )
            required_reauthorization = f"REAUTORIZAR-OS-{number}"
            if rejected and rejected_reauthorization != required_reauthorization:
                raise RejectedReauthorizationRequired(
                    "Uma rejeicao anterior exige reautorizacao manual separada"
                )

            now = _timestamp(self.clock)
            record = {
                "version": 1,
                "operation_id": operation_id,
                "numero_os": number,
                "fingerprint": fingerprint,
                "endpoint": OFFICIAL_CLOSE_ENDPOINT,
                "created_at": now,
                "updated_at": now,
                "state": "prepared",
                "transport_calls": 0,
                "history": [{"state": "prepared", "timestamp": now}],
            }
            self._atomic_write(path, record)
            return record

    def transition(
        self,
        operation_id: str,
        expected_state: str,
        new_state: str,
        **fields: Any,
    ) -> dict[str, Any]:
        if new_state not in OPERATION_STATES:
            raise OfficialCloseSenderError(f"Estado nao permitido: {new_state}")
        path = self._path(operation_id)
        with self._locked():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as error:
                raise OperationConflictError("Registro da operacao nao encontrado") from error
            if not isinstance(record, dict) or record.get("state") != expected_state:
                raise OperationConflictError(
                    "A operacao nao esta no estado esperado para a transicao"
                )
            now = _timestamp(self.clock)
            record.update(fields)
            record["state"] = new_state
            record["updated_at"] = now
            history = list(record.get("history") or [])
            history.append({"state": new_state, "timestamp": now})
            record["history"] = history
            self._atomic_write(path, record)
            return record

    def read(self, operation_id: str) -> dict[str, Any]:
        path = self._path(operation_id)
        return json.loads(path.read_text(encoding="utf-8"))


def execute_single_official_close(
    payload: Any,
    *,
    expected_fingerprint: str,
    operation_id: str,
    confirmation: str,
    state_directory: str | Path,
    transport: OfficialCloseTransport,
    rejected_reauthorization: str | None = None,
    token_environment_variable: str = TOKEN_ENVIRONMENT_VARIABLE,
    clock: Callable[[], dt.datetime] | None = None,
) -> dict[str, Any]:
    """Execute at most one transport call after all durable guards pass."""
    try:
        validated = validate_single_official_payload(payload)
    except ControlledDryRunError as error:
        raise OfficialCloseValidationError(str(error)) from error

    canonical = canonical_official_json(validated)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    informed_fingerprint = str(expected_fingerprint or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", informed_fingerprint) or not hmac.compare_digest(
        fingerprint,
        informed_fingerprint,
    ):
        raise FingerprintMismatchError(
            "O fingerprint informado nao corresponde ao JSON canonico"
        )

    order = validated["ordemservico"]
    number = order["numero"]
    if confirmation != f"ENVIAR-OS-{number}":
        raise OfficialCloseSenderError(
            "A confirmacao literal da OS nao corresponde ao payload"
        )

    token = os.environ.get(token_environment_variable, "")
    if not token:
        raise OfficialCloseSenderError(
            f"Defina a variavel de ambiente {token_environment_variable}"
        )

    store = OperationStore(state_directory, clock=clock)
    store.create_prepared(
        operation_id=operation_id,
        number=number,
        fingerprint=fingerprint,
        rejected_reauthorization=rejected_reauthorization,
    )
    store.transition(
        operation_id,
        "prepared",
        "sending",
        transport_calls=1,
    )

    try:
        response = transport.send(
            endpoint=OFFICIAL_CLOSE_ENDPOINT,
            body=canonical.encode("utf-8"),
            token=token,
        )
        if not isinstance(response, TransportResponse):
            raise TypeError("Resposta do transporte possui formato invalido")
        status_code = response.status_code
        if type(status_code) is not int or not 100 <= status_code <= 599:
            raise ValueError("Status HTTP invalido")
        response_body = _sanitize_response_body(response.body, secrets=(token,))
    except Exception:
        store.transition(
            operation_id,
            "sending",
            "uncertain",
            error="O resultado da chamada nao pode ser determinado com seguranca",
        )
        raise OfficialCloseUncertainError(
            "Resultado incerto; a operacao nao pode ser repetida automaticamente"
        ) from None

    if 200 <= status_code < 300:
        return store.transition(
            operation_id,
            "sending",
            "queued",
            http_status=status_code,
            response_body=response_body,
        )
    return store.transition(
        operation_id,
        "sending",
        "rejected",
        http_status=status_code,
        response_body=response_body,
    )


def _load_payload(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Executor restrito de uma unica baixa oficial"
    )
    parser.add_argument("payload_file")
    parser.add_argument(
        "--state-dir",
        default="config/official_close_operations",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--fingerprint")
    parser.add_argument("--operation-id")
    parser.add_argument("--confirm")
    parser.add_argument("--reauthorize-rejected")
    args = parser.parse_args()

    payload = _load_payload(args.payload_file)
    fingerprint = official_payload_fingerprint(payload)
    number = validate_single_official_payload(payload)["ordemservico"]["numero"]
    if not args.execute:
        print("MODO BLOQUEADO: nenhuma requisicao foi executada.")
        print(f"OS: {number}")
        print(f"Fingerprint SHA-256: {fingerprint}")
        return 0

    missing = [
        option
        for option, value in (
            ("--fingerprint", args.fingerprint),
            ("--operation-id", args.operation_id),
            ("--confirm", args.confirm),
        )
        if not value
    ]
    if missing:
        parser.error("Argumentos obrigatorios com --execute: " + ", ".join(missing))

    result = execute_single_official_close(
        payload,
        expected_fingerprint=args.fingerprint,
        operation_id=args.operation_id,
        confirmation=args.confirm,
        state_directory=args.state_dir,
        transport=HttpsOfficialCloseTransport(),
        rejected_reauthorization=args.reauthorize_rejected,
    )
    print(
        json.dumps(
            {
                "operation_id": result["operation_id"],
                "numero_os": result["numero_os"],
                "state": result["state"],
                "http_status": result.get("http_status"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
