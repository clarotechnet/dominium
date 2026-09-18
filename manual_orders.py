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
import datetime as dt
import json
import re
import struct
from pathlib import Path

from native_orders import NativeService, short_text


class ManualOrderProtocol:
    """Builds a complete manual-order packet captured with CLIENTE 123."""

    def __init__(self, template_path: Path) -> None:
        templates = json.loads(template_path.read_text(encoding="ascii"))
        if templates.get("version") != 1:
            raise ValueError("Unsupported manual order protocol template version")
        self.apply_method = str(templates.get("server_method", ""))
        self.template = base64.b64decode(templates.get("template", ""))
        self.captured = dict(templates.get("captured", {}))
        self.fixed = dict(templates.get("fixed", {}))
        if (
            self.apply_method != "TDtmOrdemServico.AS_ApplyUpdates"
            or not self.template.startswith(b"#Dsp")
            or len(self.template) < 7800
        ):
            raise ValueError("Invalid manual order protocol template")
        self._validate_template()

    @staticmethod
    def _time_milliseconds(value: str) -> int:
        parsed = dt.datetime.strptime(str(value), "%H:%M").time()
        return ((parsed.hour * 60 + parsed.minute) * 60 + parsed.second) * 1000

    @staticmethod
    def _replace(
        packet: bytes,
        old: bytes,
        new: bytes,
        *,
        label: str,
        expected_count: int = 1,
    ) -> bytes:
        found = packet.count(old)
        if found != expected_count:
            raise ValueError(
                f"Marcador de {label} do cadastro manual mudou "
                f"({found}/{expected_count})"
            )
        return packet.replace(old, new, expected_count)

    @staticmethod
    def _recalculate_packet(packet: bytes) -> bytes:
        if not packet.startswith(b"#Dsp") or len(packet) < 32:
            raise ValueError("Pacote do cadastro manual invalido")
        body = bytearray(packet[4:])
        captured_packet_length = struct.unpack_from("<I", body, 4)[0] + 23
        captured_dynamic = struct.unpack_from("<H", body, 2)[0]
        dynamic_length_base = captured_packet_length - captured_dynamic
        dynamic_length = len(body) - dynamic_length_base
        page_delta = dynamic_length // 256 - captured_dynamic // 256
        encoded_dynamic = dynamic_length - page_delta * 256
        encoded_page = body[1] + page_delta
        if not (0 <= encoded_dynamic <= 0xFFFF and 0 <= encoded_page <= 0xFF):
            raise ValueError("Comprimento do cadastro manual invalido")
        body[1] = encoded_page
        struct.pack_into("<H", body, 2, encoded_dynamic)
        struct.pack_into("<I", body, 4, len(body) - 23)
        return b"#Dsp" + bytes(body)

    def _validate_template(self) -> None:
        required_captured = {
            "os_number",
            "contract",
            "installer_id",
            "installer_name",
            "execution_date",
            "controller_id",
            "start_time",
            "end_time",
        }
        required_fixed = {
            "service_id",
            "service_code",
            "service",
            "client",
            "client_person_id",
            "street",
            "number",
            "district",
            "city",
            "state",
            "zip_code",
            "address_type",
        }
        if not required_captured.issubset(self.captured):
            raise ValueError("Marcadores do cadastro manual estao incompletos")
        if not required_fixed.issubset(self.fixed):
            raise ValueError("Dados fixos do cadastro manual estao incompletos")

        captured_date = dt.date.fromisoformat(str(self.captured["execution_date"]))
        checks = (
            (short_text(self.captured["os_number"]), 1, "numero da OS"),
            (short_text(self.captured["contract"]), 1, "contrato"),
            (
                struct.pack("<I", int(self.captured["installer_id"])),
                1,
                "instalador",
            ),
            (
                short_text(self.captured["installer_name"]),
                1,
                "nome do instalador",
            ),
            (struct.pack("<I", captured_date.toordinal()), 2, "data"),
            (
                struct.pack("<I", int(self.captured["controller_id"])),
                2,
                "controlador",
            ),
            (
                struct.pack(
                    "<I",
                    self._time_milliseconds(self.captured["start_time"]),
                ),
                1,
                "hora inicial",
            ),
            (
                struct.pack(
                    "<I",
                    self._time_milliseconds(self.captured["end_time"]),
                ),
                1,
                "hora final",
            ),
            (
                struct.pack("<I", int(self.fixed["service_id"])),
                1,
                "IdServico",
            ),
            (short_text(self.fixed["service_code"]), 1, "codigo do servico"),
            (short_text(self.fixed["service"]), 1, "servico"),
        )
        for marker, expected_count, label in checks:
            if self.template.count(marker) != expected_count:
                raise ValueError(f"Marcador de {label} do cadastro manual invalido")

        for key in required_fixed - {"client_person_id", "service_id"}:
            value = str(self.fixed[key])
            if value and value.encode("cp1252") not in self.template:
                raise ValueError(
                    f"Dado fixo {key} nao foi localizado no cadastro manual"
                )

    def build_packet(
        self,
        os_number: str,
        contract: str,
        service: NativeService,
        technician_id: int,
        technician_name: str,
        order_date: dt.date,
    ) -> bytes:
        os_number = " ".join(str(os_number).strip().split())
        contract = str(contract).strip()
        technician_name = " ".join(str(technician_name).strip().split())
        if not re.fullmatch(r"[0-9 ]{4,40}", os_number):
            raise ValueError("Numero da OS invalido para o cadastro manual")
        if not re.fullmatch(r"\d{7,8}", contract):
            raise ValueError("Contrato invalido para o cadastro manual")
        if technician_id <= 0 or not technician_name:
            raise ValueError("Tecnico invalido para o cadastro manual")

        captured = self.captured
        captured_date = dt.date.fromisoformat(str(captured["execution_date"]))
        packet = self.template
        packet = self._replace(
            packet,
            short_text(captured["os_number"]),
            short_text(os_number),
            label="numero da OS",
        )
        packet = self._replace(
            packet,
            short_text(captured["contract"]),
            short_text(contract),
            label="contrato",
        )
        packet = self._replace(
            packet,
            struct.pack("<I", int(captured["installer_id"])),
            struct.pack("<I", int(technician_id)),
            label="IdInstalador",
        )
        packet = self._replace(
            packet,
            short_text(captured["installer_name"]),
            short_text(technician_name),
            label="nome do tecnico",
        )
        packet = self._replace(
            packet,
            struct.pack("<I", captured_date.toordinal()),
            struct.pack("<I", order_date.toordinal()),
            label="data",
            expected_count=2,
        )
        packet = self._replace(
            packet,
            struct.pack("<I", int(self.fixed["service_id"])),
            struct.pack("<I", int(service.id_service)),
            label="IdServico",
        )
        packet = self._replace(
            packet,
            short_text(self.fixed["service_code"]),
            short_text(service.code),
            label="codigo do servico",
        )
        packet = self._replace(
            packet,
            short_text(self.fixed["service"]),
            short_text(service.name),
            label="servico",
        )
        return self._recalculate_packet(packet)
