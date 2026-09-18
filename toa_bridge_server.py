# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# TOA
# - SIM - recebe dados da extensao TOA TechNet Bridge (porta 8787).
#
# IMPERIUM
# - NAO - este arquivo nao consulta nem automatiza o Imperium.
#
# DOMINIUM COMPARTILHADO
# - Apoio local apenas: converte o payload da extensao para o
#   formato do TOADatalakeStore.
#
# Categoria deste arquivo: TOA.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# =============================================================================
"""Bridge local escutando na porta 8787.

A extensao Chrome TOA TechNet Bridge 2.6.12 envia todos os dados capturados
(equipamentos, miscelaneas, codigos de baixa, observacoes, contratos) para
http://localhost:8787/<rota>. Este modulo implementa as rotas esperadas e
repassa os dados normalizados para o TOADatalakeStore.

Rotas implementadas
-------------------
GET  /toa/health          - keepalive; devolve {"ok": true}
POST /toa/sync            - captura individual ou lote de contratos
GET  /toa/pending-lookup  - proximo contrato pendente na fila de detalhes
POST /toa/ack-lookup      - confirma enriquecimento de uma atividade
POST /toa/ping            - keepalive da extensao
POST /atlas/ping          - keepalive do Atlas

O servidor escuta apenas em 127.0.0.1 para nao expor dados a outras
maquinas na rede.
"""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

LOGGER = logging.getLogger(__name__)

_MAX_REQUEST_BYTES = 4 * 1024 * 1024  # 4 MiB


# ---------------------------------------------------------------------------
# Conversores de payload
# ---------------------------------------------------------------------------

def _text(value: Any, maxlen: int = 0) -> str:
    result = str(value or "").strip()
    return result[:maxlen] if maxlen else result


def _digits(value: Any) -> str:
    return "".join(c for c in str(value or "") if c.isdigit())


def _list_of(value: Any) -> list:
    if isinstance(value, list):
        return value
    return []


def _convert_equipment_item(item: dict) -> dict:
    """Normaliza um item de equipamento da extensao para o formato do datalake."""
    return {
        "inventory_id": _text(item.get("inventory_id") or item.get("invid")),
        "code": _text(item.get("material_code") or item.get("code")),
        "description": _text(item.get("description") or item.get("name") or item.get("type")),
        "serial": _text(item.get("serial", "")).upper(),
        "quantity": _text(item.get("quantity") or item.get("used_quantity") or "1"),
        "pool": _text(item.get("pool")),
        "unit": "",
    }


def _sync_payload_to_ingest(body: dict) -> dict:
    """Converte o payload /toa/sync para o formato TOADatalakeStore.ingest().

    Dois formatos de entrada:
    1. Schema 'dominium-toa-v1' - captura de uma unica atividade com
       equipment, materials, tasks, close_codes.
    2. Source 'toa-extension-batch' ou 'toa-extension-export' - lote de
       contratos com campos simples (contrato, aid, tecnico, ...).
    """
    source = _text(body.get("source") or body.get("schema_version") or "toa-extension")
    now = _text(body.get("captured_at") or body.get("observed_at") or "")

    # Formato 2: lote de contratos simples
    entries = _list_of(body.get("entries"))
    if entries:
        activities = []
        for entry in entries:
            aid = _digits(entry.get("aid") or entry.get("activity_id") or "")
            contract = _digits(entry.get("contrato") or entry.get("contract") or "")
            if not aid and not contract:
                continue
            tech = entry.get("tecnico") or entry.get("technician") or ""
            activities.append({
                "activity_id": aid,
                "contract": contract,
                "technician_name": _text(tech if isinstance(tech, str) else tech.get("name", "")),
                "service_window": _text(entry.get("janela") or entry.get("service_window") or ""),
                "city": _text(entry.get("cidade") or entry.get("city") or ""),
            })
        return {
            "schema": "dominium.toa.datalake.v1",
            "source": source,
            "collector_id": "toa-extension-bridge",
            "observed_at": now,
            "activities": activities,
            "orders": [],
            "details": [],
        }

    # Formato 1: snapshot individual (dominium-toa-v1)
    activity_id = _digits(body.get("activity_id") or body.get("aid") or "")
    contract = _digits(body.get("contract") or body.get("contrato") or "")

    if not activity_id and not contract:
        return {}

    equipment = body.get("equipment") if isinstance(body.get("equipment"), dict) else {}
    tech = body.get("technician") if isinstance(body.get("technician"), dict) else {}
    tech_name = tech.get("name") or body.get("tecnico") or ""

    # Montar as OS a partir de tasks/close_codes
    tasks = _list_of(body.get("tasks"))
    close_codes = _list_of(body.get("close_codes"))
    orders: list[dict] = []
    for task in tasks:
        os_number = _digits(task.get("os_number") or task.get("num_os") or task.get("id") or "")
        if not os_number:
            continue
        orders.append({
            "os_number": os_number,
            "activity_id": activity_id,
            "contract": contract,
            "service": _text(task.get("service") or task.get("tipo") or ""),
            "status": _text(task.get("status") or ""),
            "close_code": _digits(task.get("close_code") or task.get("codigo_baixa") or ""),
        })
    # Complementar close_codes quando tasks estiver vazio
    if not orders and close_codes:
        for cc in close_codes:
            os_number = _digits(cc.get("os_number") or cc.get("num_os") or "")
            code = _digits(cc.get("code") or cc.get("codigo") or "")
            if os_number or code:
                orders.append({
                    "os_number": os_number,
                    "activity_id": activity_id,
                    "contract": contract,
                    "close_code": code,
                    "status": "",
                    "service": "",
                })

    detail: dict[str, Any] = {
        "activity_id": activity_id,
        "contract": contract,
        "activity_type": _text(body.get("activity_type") or ""),
        "status": _text(body.get("status") or ""),
        "scheduled_date": _text(body.get("scheduled_date") or ""),
        "service_window": _text(body.get("service_window") or ""),
        "city": _text(body.get("city") or ""),
        "technician_name": _text(tech_name if isinstance(tech_name, str) else ""),
        "technician_id": _text(tech.get("id") or ""),
        "technician_login": _text(tech.get("login") or ""),
        "observation": _text(body.get("technician_observation") or body.get("observacao") or ""),
        "orders": orders,
        "installed_equipment": [_convert_equipment_item(i) for i in _list_of(equipment.get("installed"))],
        "removed_equipment": [_convert_equipment_item(i) for i in _list_of(equipment.get("removed"))],
        "customer_equipment": [_convert_equipment_item(i) for i in _list_of(equipment.get("customer"))],
        "materials": [_convert_equipment_item(i) for i in _list_of(body.get("materials"))],
    }

    return {
        "schema": "dominium.toa.datalake.v1",
        "source": source,
        "collector_id": "toa-extension-bridge",
        "observed_at": now,
        "activities": [],
        "orders": [],
        "details": [detail],
    }


# ---------------------------------------------------------------------------
# Handler HTTP
# ---------------------------------------------------------------------------

class _BridgeHandler(BaseHTTPRequestHandler):
    """Handler leve; delega logica de negocio ao ToaBridgeServer."""

    server: "ToaBridgeServer"  # type: ignore[assignment]

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > _MAX_REQUEST_BYTES:
                return None
            raw = self.rfile.read(length) if length else b""
            return json.loads(raw) if raw else {}
        except (ValueError, OSError):
            return None

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _cors_preflight(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-toa-token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._cors_preflight()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/toa/health":
            self._send_json(200, {"ok": True, "version": "dominium-bridge-8787", "status": "online"})
        elif path == "/toa/pending-lookup":
            self._send_json(200, self.server.handle_pending_lookup())
        else:
            self._send_json(404, {"ok": False, "error": "rota nao encontrada"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        body = self._read_json()
        if body is None:
            self._send_json(400, {"ok": False, "error": "corpo invalido ou muito grande"})
            return

        if path == "/toa/sync":
            self._send_json(200, self.server.handle_sync(body))
        elif path == "/toa/ack-lookup":
            self._send_json(200, self.server.handle_ack_lookup(body))
        elif path in {"/toa/ping", "/atlas/ping"}:
            self._send_json(200, {"ok": True})
        else:
            self._send_json(404, {"ok": False, "error": "rota nao encontrada"})


# ---------------------------------------------------------------------------
# Servidor
# ---------------------------------------------------------------------------

class ToaBridgeServer:
    """Mini-servidor HTTP na porta 8787 para a extensao TOA TechNet Bridge.

    Parameters
    ----------
    datalake:
        Instancia de TOADatalakeStore usada para persistir os dados.
    port:
        Porta onde o servidor vai escutar (padrao 8787).
    host:
        Interface de rede (padrao 127.0.0.1 - apenas loopback).
    """

    def __init__(self, datalake: Any, *, port: int = 8787, host: str = "127.0.0.1") -> None:
        self._datalake = datalake
        self._port = port
        self._host = host
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # Metodos de logica de negocio (chamados pelo handler)

    def handle_sync(self, body: dict) -> dict:
        """Recebe captura da extensao e persiste no datalake."""
        if not body:
            return {"ok": False, "error": "corpo vazio", "inserted": 0}
        try:
            ingest_payload = _sync_payload_to_ingest(body)
        except Exception as exc:
            LOGGER.warning("[bridge-8787] falha ao converter /toa/sync: %s", exc)
            return {"ok": False, "error": str(exc), "inserted": 0}

        if not ingest_payload:
            return {"ok": False, "error": "payload sem activity_id ou contract", "inserted": 0}

        total = (
            len(ingest_payload.get("activities", []))
            + len(ingest_payload.get("orders", []))
            + len(ingest_payload.get("details", []))
        )
        if total == 0:
            return {"ok": True, "inserted": 0, "message": "nenhum item para persistir"}

        try:
            result = self._datalake.ingest(ingest_payload)
            inserted = result.get("changed", 0) + result.get("details", 0)
            LOGGER.info(
                "[bridge-8787] /toa/sync aceito: %d atividades, %d ordens, %d detalhes, %d alterados",
                result.get("activities", 0),
                result.get("orders", 0),
                result.get("details", 0),
                result.get("changed", 0),
            )
            return {"ok": True, "inserted": inserted, "result": result}
        except ValueError as exc:
            LOGGER.warning("[bridge-8787] /toa/sync rejeitado pelo datalake: %s", exc)
            return {"ok": False, "error": str(exc), "inserted": 0}
        except Exception as exc:
            LOGGER.error("[bridge-8787] /toa/sync erro interno: %s", exc, exc_info=True)
            return {"ok": False, "error": "erro interno", "inserted": 0}

    def handle_pending_lookup(self) -> dict:
        """Retorna o proximo contrato/atividade que precisa de detalhes."""
        try:
            queue = self._datalake.detail_queue(limit=1)
            items = queue.get("items") or []
            if not items:
                return {"ok": True, "contrato": None, "activity_id": None, "source": "local"}
            item = items[0]
            return {
                "ok": True,
                "contrato": item.get("contract") or None,
                "activity_id": item.get("activity_id") or None,
                "source": "local",
                "scheduled_date": item.get("scheduled_date") or "",
            }
        except Exception as exc:
            LOGGER.warning("[bridge-8787] /toa/pending-lookup erro: %s", exc)
            return {"ok": True, "contrato": None, "activity_id": None, "source": "local"}

    def handle_ack_lookup(self, body: dict) -> dict:
        """Marca uma atividade como enriquecida no datalake."""
        contrato = _digits(body.get("contrato") or body.get("contract") or "")
        activity_id = _digits(body.get("activity_id") or body.get("aid") or "")
        if not activity_id and not contrato:
            return {"ok": False, "error": "activity_id ou contrato obrigatorio"}
        try:
            ack_payload: dict = {
                "schema": "dominium.toa.datalake.v1",
                "source": "toa-extension-ack",
                "collector_id": "toa-extension-bridge",
                "activities": [],
                "orders": [],
                "details": [{
                    "activity_id": activity_id,
                    "contract": contrato,
                }],
            }
            self._datalake.ingest(ack_payload)
            return {"ok": True}
        except Exception as exc:
            LOGGER.warning("[bridge-8787] /toa/ack-lookup erro: %s", exc)
            return {"ok": True}

    # Ciclo de vida do servidor

    def start(self) -> None:
        """Inicia o servidor HTTP em uma thread daemon."""
        if self._thread and self._thread.is_alive():
            return
        try:
            server = ThreadingHTTPServer((self._host, self._port), _BridgeHandler)
            # Injeta referencia ao ToaBridgeServer no atributo do ThreadingHTTPServer
            # para que o handler possa chamar handle_sync, handle_pending_lookup etc.
            server.handle_sync = self.handle_sync  # type: ignore[attr-defined]
            server.handle_pending_lookup = self.handle_pending_lookup  # type: ignore[attr-defined]
            server.handle_ack_lookup = self.handle_ack_lookup  # type: ignore[attr-defined]
            self._server = server
            self._thread = threading.Thread(
                target=server.serve_forever,
                name="toa-bridge-8787",
                daemon=True,
            )
            self._thread.start()
            LOGGER.info("[bridge-8787] servidor iniciado em %s:%d", self._host, self._port)
        except OSError as exc:
            LOGGER.error("[bridge-8787] nao foi possivel iniciar o servidor: %s", exc)

    def stop(self) -> None:
        """Para o servidor HTTP de forma ordenada."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            LOGGER.info("[bridge-8787] servidor encerrado")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
