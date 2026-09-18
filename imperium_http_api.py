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
import argparse
import base64
import datetime as dt
import json
import re
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from datasnap_client import load_credentials


DEFAULT_BASE_URL = "https://www.sistemaimperium.com.br"
# Mapeamento tenant → (login_path, close_path).
# Adicionar um novo tenant aqui automaticamente o inclui em ALLOWED_API_PATHS.
TENANT_PATHS: dict[str, tuple[str, str]] = {
    "natal":     ("/technet/login",            "/technet/ordemservico"),
    "fortaleza": ("/technetfortalezace/login", "/technetfortalezace/ordemservico"),
}
# Retrocompatibilidade: aliases escalares para o tenant padrao (Natal).
LOGIN_PATH = TENANT_PATHS["natal"][0]
CLOSE_PATH = TENANT_PATHS["natal"][1]
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 512 * 1024
MAX_TOKEN_BYTES = 16 * 1024
ALLOWED_API_HOSTS = frozenset({"www.sistemaimperium.com.br"})
ALLOWED_API_PATHS = frozenset(p for paths in TENANT_PATHS.values() for p in paths)
TENANT_PREFIXES = {
    tenant: login_path.rsplit("/", 1)[0]
    for tenant, (login_path, _close_path) in TENANT_PATHS.items()
}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Nao deixa JWT/credenciais seguirem redirecionamentos inesperados."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_SECURE_OPENER = urllib.request.build_opener(_NoRedirectHandler())


def _secure_urlopen(request: urllib.request.Request, *, timeout: float):
    return _SECURE_OPENER.open(request, timeout=timeout)


class ImperiumHTTPValidationError(ValueError):
    pass


class ImperiumHTTPError(RuntimeError):
    def __init__(self, message: str, *, status: int = 0, response: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.response = response


class ImperiumHTTPUncertainError(ImperiumHTTPError):
    """The write may have reached the server and must not be repeated blindly."""


@dataclass(frozen=True)
class ImperiumHTTPResult:
    status: int
    response: Any

    @property
    def accepted(self) -> bool:
        return 200 <= self.status < 300

    @property
    def requires_confirmation(self) -> bool:
        return True


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ImperiumHTTPValidationError(f"Campo obrigatorio ausente: {field}")
    return text


def _quantity_text(value: Any) -> str:
    text = _required_text(value, "qtd").replace(",", ".")
    try:
        quantity = Decimal(text)
    except InvalidOperation as exc:
        raise ImperiumHTTPValidationError(f"Quantidade invalida: {value}") from exc
    if not quantity.is_finite() or quantity <= 0:
        raise ImperiumHTTPValidationError(f"Quantidade deve ser positiva: {value}")
    normalized = format(quantity.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def build_close_payload(
    *,
    number: Any,
    scheduled_date: Any,
    technician_code: Any,
    close_code: Any,
    installed_serials: list[dict[str, Any]] | None = None,
    installed_materials: list[dict[str, Any]] | None = None,
    removed_serials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    materials: dict[str, Decimal] = {}
    for item in installed_materials or []:
        code = _required_text(item.get("codigoequipamento"), "codigoequipamento")
        quantity = Decimal(_quantity_text(item.get("qtd")))
        materials[code] = materials.get(code, Decimal(0)) + quantity

    payload = {
        "ordemservico": {
            "numero": str(number or "").strip(),
            "dataagendamento": str(scheduled_date or "").strip(),
            "codigotecnico": str(technician_code or "").strip().upper(),
            "codigobaixa": close_code,
            "instaladosserializados": [
                {"serialnumber": str(item.get("serialnumber") or "").strip()}
                for item in installed_serials or []
            ],
            "instaladosmiscelaneas": [
                {
                    "codigoequipamento": code,
                    "qtd": _quantity_text(quantity),
                }
                for code, quantity in materials.items()
            ],
            "removidosserializados": [
                {
                    "codigoequipamento": str(
                        item.get("codigoequipamento") or ""
                    ).strip(),
                    "serialnumber": str(item.get("serialnumber") or "").strip(),
                }
                for item in removed_serials or []
            ],
        }
    }
    return validate_close_payload(payload)


def validate_close_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("ordemservico"), dict):
        raise ImperiumHTTPValidationError("Payload deve conter o objeto ordemservico")

    source = payload["ordemservico"]
    number = _required_text(source.get("numero"), "numero")
    if not number.isdigit():
        raise ImperiumHTTPValidationError("Numero da OS deve conter somente digitos")

    scheduled_date = _required_text(source.get("dataagendamento"), "dataagendamento")
    try:
        if dt.date.fromisoformat(scheduled_date).isoformat() != scheduled_date:
            raise ValueError
    except ValueError as exc:
        raise ImperiumHTTPValidationError(
            "Data de agendamento deve estar no formato YYYY-MM-DD"
        ) from exc

    technician_code = _required_text(source.get("codigotecnico"), "codigotecnico").upper()
    if not re.fullmatch(r"[A-Z0-9._-]{2,40}", technician_code):
        raise ImperiumHTTPValidationError("Codigo do tecnico possui formato invalido")

    raw_close_code = source.get("codigobaixa")
    try:
        close_code = int(str(raw_close_code).strip())
    except (TypeError, ValueError) as exc:
        raise ImperiumHTTPValidationError("Codigo de baixa invalido") from exc
    if not 0 <= close_code <= 9999:
        raise ImperiumHTTPValidationError("Codigo de baixa fora do intervalo permitido")

    installed = source.get("instaladosserializados", [])
    materials = source.get("instaladosmiscelaneas", [])
    removed = source.get("removidosserializados", [])
    for field, items in (
        ("instaladosserializados", installed),
        ("instaladosmiscelaneas", materials),
        ("removidosserializados", removed),
    ):
        if not isinstance(items, list):
            raise ImperiumHTTPValidationError(f"{field} deve ser uma lista")

    normalized_installed: list[dict[str, str]] = []
    installed_serials: set[str] = set()
    for item in installed:
        if not isinstance(item, dict):
            raise ImperiumHTTPValidationError("Equipamento instalado invalido")
        serial = _required_text(item.get("serialnumber"), "serialnumber")
        if serial in installed_serials:
            raise ImperiumHTTPValidationError(f"Serial instalado duplicado: {serial}")
        installed_serials.add(serial)
        normalized_installed.append({"serialnumber": serial})

    normalized_materials: list[dict[str, str]] = []
    material_codes: set[str] = set()
    for item in materials:
        if not isinstance(item, dict):
            raise ImperiumHTTPValidationError("Miscelanea instalada invalida")
        code = _required_text(item.get("codigoequipamento"), "codigoequipamento")
        if code in material_codes:
            raise ImperiumHTTPValidationError(f"Miscelanea duplicada: {code}")
        material_codes.add(code)
        normalized_materials.append(
            {"codigoequipamento": code, "qtd": _quantity_text(item.get("qtd"))}
        )

    normalized_removed: list[dict[str, str]] = []
    removed_serials: set[str] = set()
    for item in removed:
        if not isinstance(item, dict):
            raise ImperiumHTTPValidationError("Equipamento removido invalido")
        code = _required_text(item.get("codigoequipamento"), "codigoequipamento")
        serial = _required_text(item.get("serialnumber"), "serialnumber")
        if serial in removed_serials:
            raise ImperiumHTTPValidationError(f"Serial removido duplicado: {serial}")
        if serial in installed_serials:
            raise ImperiumHTTPValidationError(
                f"Serial nao pode estar instalado e removido na mesma baixa: {serial}"
            )
        removed_serials.add(serial)
        normalized_removed.append({"codigoequipamento": code, "serialnumber": serial})

    return {
        "ordemservico": {
            "numero": number,
            "dataagendamento": scheduled_date,
            "codigotecnico": technician_code,
            "codigobaixa": close_code,
            "instaladosserializados": normalized_installed,
            "instaladosmiscelaneas": normalized_materials,
            "removidosserializados": normalized_removed,
        }
    }


def _decode_response(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _safe_positive_id(value: Any, field: str) -> int:
    try:
        identifier = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ImperiumHTTPValidationError(f"{field} invalido") from exc
    if identifier <= 0:
        raise ImperiumHTTPValidationError(f"{field} invalido")
    return identifier


def _login_identity(response: Any, headers: dict[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in headers.items():
        normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
        values[normalized] = value
    if isinstance(response, dict):
        for key, value in response.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            values.setdefault(normalized, value)

    def numeric(*names: str) -> int | None:
        for name in names:
            raw = values.get(name)
            if raw not in (None, ""):
                try:
                    value = int(str(raw).strip())
                except (TypeError, ValueError):
                    continue
                return value if value >= 0 else None
        return None

    return {
        "user_id": numeric("idusuario", "userid"),
        "stock_id": numeric("idestoque", "stockid"),
        "group": str(values.get("grupousuario") or values.get("usergroup") or "").strip(),
        "username": str(values.get("usuario") or values.get("username") or "").strip(),
    }


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "sim", "s", "yes"}


def _data_list(response: Any, label: str) -> list[dict[str, Any]]:
    value = response.get("data") if isinstance(response, dict) and "data" in response else response
    if value is None:
        return []
    if isinstance(value, dict):
        return [dict(value)]
    if not isinstance(value, list):
        raise ImperiumHTTPError(f"Resposta de {label} da API oficial possui formato invalido")
    return [dict(item) for item in value if isinstance(item, dict)]


def _jwt_expiry(token: str) -> float:
    try:
        segment = token.split(".")[1]
        segment += "=" * (-len(segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(segment).decode("utf-8"))
        return float(payload.get("exp") or 0)
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return 0


class ImperiumHTTPClient:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        tenant: str = "natal",
        timeout: float = 30.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._username = _required_text(username, "jwtusername")
        self._password = _required_text(password, "jwtpassword")
        self.base_url = base_url.rstrip("/")
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme.lower() != "https"
            or (parsed.hostname or "").lower() not in ALLOWED_API_HOSTS
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ImperiumHTTPValidationError("Destino da API oficial nao autorizado")
        if tenant not in TENANT_PATHS:
            raise ImperiumHTTPValidationError(
                f"Tenant da API oficial nao reconhecido: {tenant!r}"
            )
        self._tenant = tenant
        self._login_path, self._close_path = TENANT_PATHS[tenant]
        self._api_prefix = TENANT_PREFIXES[tenant]
        if len(self._username) > 256 or len(self._password) > 1024:
            raise ImperiumHTTPValidationError("Credencial da API oficial excede o limite")
        self.timeout = timeout
        if not 1 <= float(timeout) <= 120:
            raise ImperiumHTTPValidationError("Timeout da API oficial fora do limite seguro")
        self._opener = opener or _secure_urlopen
        self._token = ""
        self._token_expiry = 0.0
        self._token_lock = threading.RLock()
        self._last_response_headers: dict[str, str] = {}
        self._login_metadata: dict[str, Any] = {}


    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            result = value
            for secret in (self._username, self._password, self._token):
                if secret:
                    result = result.replace(secret, "[redacted]")
            return result[:4096]
        if isinstance(value, dict):
            return {
                self._sanitize(key): self._sanitize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        return value

    def _request_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        token: str = "",
        write: bool = False,
        timeout: float | None = None,
    ) -> tuple[int, Any]:
        if path not in ALLOWED_API_PATHS:
            raise ImperiumHTTPValidationError("Rota da API oficial nao autorizada")
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ImperiumHTTPValidationError("Requisicao da API oficial excedeu o limite seguro")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DOMINIUM/1.0",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Request-ID": secrets.token_hex(16),
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method="POST",
        )
        effective_timeout = float(timeout if timeout is not None else self.timeout)
        try:
            with self._opener(request, timeout=effective_timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ImperiumHTTPError("Resposta da API oficial excedeu o limite seguro")
                response_headers = getattr(response, "headers", None)
                self._last_response_headers = (
                    {str(key): str(value) for key, value in response_headers.items()}
                    if response_headers is not None
                    else {}
                )
                return int(response.status), _decode_response(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES)
            response = self._sanitize(_decode_response(raw))
            raise ImperiumHTTPError(
                f"API oficial do Imperium retornou HTTP {exc.code}",
                status=int(exc.code),
                response=response,
            ) from exc
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
            if write:
                raise ImperiumHTTPUncertainError(
                    "Resposta da baixa oficial nao foi recebida. Nao repita a operacao; "
                    "confirme primeiro o estado da OS no Imperium."
                ) from exc
            raise ImperiumHTTPError(
                f"Falha de conexao com a API oficial: {type(exc).__name__}"
            ) from exc

    def _official_get_path(self, resource: str, identifier: int | None = None) -> str:
        if resource == "stocks":
            path = f"{self._api_prefix}/estoques"
            if identifier is not None:
                path += f"/{_safe_positive_id(identifier, 'ID do instalador')}"
            return path
        if resource == "stock_balance":
            stock_id = _safe_positive_id(identifier, "ID do estoque")
            return f"{self._api_prefix}/equipamentosestocagem/saldo/{stock_id}"
        raise ImperiumHTTPValidationError("Recurso da API oficial nao autorizado")

    def _request_get_json(self, path: str, *, token: str) -> tuple[int, Any]:
        allowed_prefixes = (
            f"{self._api_prefix}/estoques",
            f"{self._api_prefix}/equipamentosestocagem/saldo",
        )
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in allowed_prefixes):
            raise ImperiumHTTPValidationError("Rota da API oficial nao autorizada")
        if "?" in path or "#" in path or ".." in path:
            raise ImperiumHTTPValidationError("Rota da API oficial nao autorizada")
        headers = {
            "Accept": "application/json",
            "User-Agent": "DOMINIUM/1.0",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Request-ID": secrets.token_hex(16),
            "Authorization": f"Bearer {token}",
        }
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers=headers,
            method="GET",
        )
        try:
            with self._opener(request, timeout=float(self.timeout)) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ImperiumHTTPError("Resposta da API oficial excedeu o limite seguro")
                response_headers = getattr(response, "headers", None)
                self._last_response_headers = (
                    {str(key): str(value) for key, value in response_headers.items()}
                    if response_headers is not None
                    else {}
                )
                return int(response.status), _decode_response(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES)
            raise ImperiumHTTPError(
                f"API oficial do Imperium retornou HTTP {exc.code}",
                status=int(exc.code),
                response=self._sanitize(_decode_response(raw)),
            ) from exc
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
            raise ImperiumHTTPError(
                f"Falha de conexao com a API oficial: {type(exc).__name__}"
            ) from exc

    def _authenticated_get(self, path: str) -> Any:
        token = self.login()
        try:
            status, response = self._request_get_json(path, token=token)
        except ImperiumHTTPError as exc:
            if exc.status not in {401, 403}:
                raise
            self.clear_token()
            token = self.login(force=True)
            status, response = self._request_get_json(path, token=token)
        if not 200 <= status < 300:
            raise ImperiumHTTPError(
                f"API oficial do Imperium retornou HTTP {status}",
                status=status,
                response=self._sanitize(response),
            )
        return self._sanitize(response)

    def login(self, *, force: bool = False) -> str:
        with self._token_lock:
            if (
                not force
                and self._token
                and (not self._token_expiry or self._token_expiry > time.time() + 60)
            ):
                return self._token
            last_exc = None
            for attempt in range(2):
                try:
                    status, response = self._request_json(
                        self._login_path,
                        {"jwtusername": self._username, "jwtpassword": self._password},
                        timeout=15.0,
                    )
                    break
                except ImperiumHTTPError as exc:
                    last_exc = exc
                    if attempt == 0:
                        time.sleep(0.3)
                        continue
                    raise
            else:
                if last_exc:
                    raise last_exc
            if status != 200 or not isinstance(response, dict):
                raise ImperiumHTTPError(
                    "Login da API oficial retornou uma resposta invalida",
                    status=status,
                    response=self._sanitize(response),
                )
            token = str(response.get("token") or "").strip()
            if not token:
                raise ImperiumHTTPError(
                    "Login da API oficial nao retornou token",
                    status=status,
                    response=self._sanitize(response),
                )
            if len(token.encode("utf-8")) > MAX_TOKEN_BYTES:
                raise ImperiumHTTPError("Token da API oficial excedeu o limite seguro")
            self._token = token
            self._token_expiry = _jwt_expiry(token)
            self._login_metadata = _login_identity(
                response,
                self._last_response_headers,
            )
            return token

    def clear_token(self) -> None:
        with self._token_lock:
            self._token = ""
            self._token_expiry = 0.0
            self._login_metadata = {}

    def login_metadata(self, *, force: bool = False) -> dict[str, Any]:
        self.login(force=force)
        return dict(self._login_metadata)

    def list_stocks(self) -> list[dict[str, Any]]:
        response = self._authenticated_get(self._official_get_path("stocks"))
        return _data_list(response, "estoques")

    def installer_stocks(self, installer_id: Any) -> list[dict[str, Any]]:
        response = self._authenticated_get(
            self._official_get_path(
                "stocks",
                _safe_positive_id(installer_id, "ID do instalador"),
            )
        )
        return _data_list(response, "estoques do instalador")

    def stock_balance(self, stock_id: Any) -> list[dict[str, Any]]:
        response = self._authenticated_get(
            self._official_get_path(
                "stock_balance",
                _safe_positive_id(stock_id, "ID do estoque"),
            )
        )
        return _data_list(response, "saldo de estoque")

    def stock_catalog(self, installer_id: Any | None = None) -> list[dict[str, Any]]:
        rows = self.list_stocks() if installer_id in (None, "") else self.installer_stocks(installer_id)
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                stock_id = int(row.get("idestoque") or 0)
                responsible_id = int(row.get("idinstaladorresponsavel") or 0)
            except (TypeError, ValueError):
                continue
            if stock_id <= 0:
                continue
            result.append(
                {
                    "stock_id": stock_id,
                    "installer_id": responsible_id if responsible_id > 0 else None,
                    "name": str(row.get("estoque") or "").strip(),
                    "type": str(row.get("tipo") or "").strip(),
                    "active": _boolish(row.get("ativo")),
                    "capabilities": {
                        "entry": _boolish(row.get("entrada")),
                        "exit": _boolish(row.get("saida")),
                        "transfer": _boolish(row.get("transferencia")),
                        "installation": _boolish(row.get("instalacao")),
                        "return": _boolish(row.get("retorno")),
                    },
                }
            )
        return result

    def stock_items(self, stock_id: Any) -> list[dict[str, Any]]:
        groups = self.stock_balance(stock_id)
        result: list[dict[str, Any]] = []
        for group in groups:
            group_name = str(group.get("Grupo") or "").strip()
            try:
                group_id = int(group.get("IdGrupoEquipamento") or 0)
            except (TypeError, ValueError):
                group_id = 0
            equipments = group.get("Equipamentos")
            if not isinstance(equipments, list):
                continue
            for item in equipments:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("CodigoEquipamento") or "").strip()
                description = str(item.get("Equipamento") or "").strip()
                if not code and not description:
                    continue
                result.append(
                    {
                        "group_id": group_id or None,
                        "group": group_name,
                        "equipment_id": item.get("IdEquipamento"),
                        "code": code,
                        "description": description,
                        "unit": str(item.get("Unidade") or "").strip(),
                        "quantity": item.get("Qtd"),
                        "serialized": _boolish(item.get("Serializados")),
                        "brand": str(item.get("Marca") or "").strip(),
                        "quantity_identified": item.get("QtdIdentificado"),
                        "quantity_outside_box": item.get("QtdEmEstoqueForaCaixa"),
                        "quantity_in_boxes": item.get("QtdCxEmEstoque"),
                    }
                )
        return result

    def close_order(self, payload: dict[str, Any]) -> ImperiumHTTPResult:
        normalized = validate_close_payload(payload)
        token = self.login()
        try:
            status, response = self._request_json(
                self._close_path,
                normalized,
                token=token,
                write=True,
            )
        except ImperiumHTTPError as exc:
            if isinstance(exc, ImperiumHTTPUncertainError) or exc.status not in {401, 403}:
                raise
            # A resposta HTTP comprova que o primeiro envio foi recusado. Somente
            # nesse caso e seguro renovar o JWT e repetir uma unica vez.
            self.clear_token()
            token = self.login(force=True)
            status, response = self._request_json(
                self._close_path,
                normalized,
                token=token,
                write=True,
            )
        if not 200 <= status < 300:
            raise ImperiumHTTPError(
                f"API oficial do Imperium retornou HTTP {status}",
                status=status,
                response=self._sanitize(response),
            )
        return ImperiumHTTPResult(status=status, response=self._sanitize(response))


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida payloads da API oficial do Imperium. O envio exige --send."
    )
    parser.add_argument("payload", type=Path)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("config/imperium_http_credentials.dat"),
    )
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirm-os", default="")
    args = parser.parse_args()

    payload = validate_close_payload(json.loads(args.payload.read_text(encoding="utf-8")))
    order_number = payload["ordemservico"]["numero"]
    if not args.send:
        print(json.dumps({"valid": True, "dry_run": True, "payload": payload}, ensure_ascii=False))
        return 0
    if args.confirm_os != order_number:
        raise SystemExit("Para enviar, repita a OS exata em --confirm-os")

    credentials = load_credentials(args.credentials)
    client = ImperiumHTTPClient(credentials["username"], credentials["password"])
    result = client.close_order(payload)
    print(
        json.dumps(
            {
                "status": result.status,
                "accepted": result.accepted,
                "requires_confirmation": result.requires_confirmation,
                "response": result.response,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
