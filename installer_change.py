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
import base64
import json
import struct
from pathlib import Path
from typing import Any

from datasnap_client import DataSnapError


class InstallerChangeProtocol:
    def __init__(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="ascii"))
        except FileNotFoundError as exc:
            raise DataSnapError(
                "O template de alteracao de instalador nao foi encontrado"
            ) from exc
        except json.JSONDecodeError as exc:
            raise DataSnapError(
                "O template de alteracao de instalador esta invalido"
            ) from exc

        if payload.get("version") != 1:
            raise DataSnapError(
                "Versao de alteracao de instalador nao suportada"
            )
        self.profile = str(payload.get("profile", "")).strip().lower()
        self.server_method = str(payload.get("server_method", "")).strip()
        self.template = base64.b64decode(payload.get("query", ""))
        self.success_response = base64.b64decode(
            payload.get("success_response", "")
        )
        self.installer_id_offset = int(payload.get("installer_id_offset", -1))
        self.controller_id_offset = int(payload.get("controller_id_offset", -1))
        self.order_id_offset = int(payload.get("order_id_offset", -1))
        self.captured_installer_id = int(
            payload.get("captured_installer_id", 0)
        )
        self.captured_controller_id = int(
            payload.get("captured_controller_id", 0)
        )
        self.captured_order_id = int(payload.get("captured_order_id", 0))

        if (
            not self.profile
            or not self.server_method
            or not self.template
            or not self.success_response
        ):
            raise DataSnapError(
                "O template de alteracao de instalador esta incompleto"
            )
        markers = (
            (self.installer_id_offset, self.captured_installer_id),
            (self.controller_id_offset, self.captured_controller_id),
            (self.order_id_offset, self.captured_order_id),
        )
        for offset, captured_value in markers:
            if (
                offset < 0
                or offset + 4 > len(self.template)
                or captured_value <= 0
                or struct.unpack_from("<I", self.template, offset)[0]
                != captured_value
            ):
                raise DataSnapError(
                    "Um marcador do template de alteracao de instalador e invalido"
                )

    def build_query(
        self,
        installer_id: int,
        controller_id: int,
        order_id: int,
    ) -> bytes:
        if min(installer_id, controller_id, order_id) <= 0:
            raise ValueError(
                "Instalador, controlador e IdOS devem ser positivos"
            )
        query = bytearray(self.template)
        struct.pack_into("<I", query, self.installer_id_offset, installer_id)
        struct.pack_into("<I", query, self.controller_id_offset, controller_id)
        struct.pack_into("<I", query, self.order_id_offset, order_id)
        return bytes(query)

    @classmethod
    def _contains_blob(cls, value: Any, expected: bytes) -> bool:
        if isinstance(value, bytes):
            return value == expected
        if isinstance(value, dict):
            return any(cls._contains_blob(item, expected) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(cls._contains_blob(item, expected) for item in value)
        return False

    def confirmed(self, response: dict[str, Any]) -> bool:
        return self._contains_blob(response, self.success_response)
