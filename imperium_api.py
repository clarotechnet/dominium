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
import csv
import datetime as dt
import difflib
import html
import json
import logging
import re
import socket
import struct
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Callable

from datasnap_client import DataSnapClient, DataSnapError, load_credentials
from installer_change import InstallerChangeProtocol
from manual_materials import ManualMaterial, parse_manual_material_catalog
from manual_orders import ManualOrderProtocol
from material_matching import (
    approved_equivalence_group_for_code,
    distribute_by_group,
    resolve_material_requests,
    toa_material_ignore_reason,
)
from native_orders import NativeContractContext, NativeOrderProtocol
from serialized_transfer import (
    SerializedTransferProtocol,
    SerializedTransferUncertainError,
)
from stock_inventory import (
    StockProtocol,
    attach_serials,
    parse_stock_items,
    parse_stock_serials,
    parse_technicians,
)
from toa_import import TOAImportProtocol, TOAOrder, TOAPreview


HOST = "www.sistemaimperium.com.br"
PORT = 212
DEFAULT_CODE = "106"
CAPTURED_CONTROLLER_ID = 313101
STATUS = "EM CAMPO"
SERVICE_TYPE = "TODOS"
ORDER_STATUS_FILTERS = {
    "all": "%",
    "field": "1",
    "completed": "2",
    "canceled": "3",
    "rescheduled": "4",
}
ORDER_STATUS_LABELS = {
    "all": "TODOS",
    "field": "EM CAMPO",
    "completed": "CONCLUIDA",
    "canceled": "CANCELADA",
    "rescheduled": "REAGENDADA",
}
ORDER_SERVICE_TYPE_FILTERS = {
    "all": "%",
    "installation": "1",
    "technical": "2",
    "disconnection": "3",
    "stock": "7",
}
MAIN_QUERY_TIMEOUT = 90.0
MAIN_FRAGMENT_TIMEOUT = 30.0
MAX_MAIN_DATASET_FRAGMENTS = 256
LOGGER = logging.getLogger("imperium")
MATERIAL_REPLENISHMENT_STOCK_NAME = "RETORNO"
MATERIAL_SHORTFALL_ITEM_HUMAN_REVIEW_THRESHOLD = 5

CLIENT_123_PROFILE = {
    "client": "CLIENTE 123",
    "person_id": 189368,
    "address_type": "CASA",
    "address": "BUMBA-MEU-BOI",
    "number": "750",
    "complement": "",
    "district": "LAGOA AZUL",
    "city": "NATAL",
    "state": "RN",
    "zip_code": "59135000",
}


class MaterialTransferUncertainError(DataSnapError):
    """The material transfer may have reached the server and must not be repeated."""


class CloseConfirmationUncertainError(DataSnapError):
    """The close write was sent, but its final state could not be confirmed."""


class CloseStateConflictError(DataSnapError):
    """The remote order is already closed with a conflicting close code."""


class _MaterialTransferReconnectRequired(OSError):
    """A material transfer was confirmed, but the current socket is no longer safe."""


@dataclass(frozen=True)
class Order:
    id_os: int
    num_os: str
    contract: str
    id_service: int
    service: str
    status: str = STATUS

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CloseCode:
    code: str
    wire_code: str
    description: str
    id_code: int
    suffixes: tuple[bytes, ...]
    productive: bool = False
    requires_observation: bool = False
    observation_marker: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "description": self.description,
            "productive": self.productive,
            "requires_observation": self.requires_observation,
        }


@dataclass(frozen=True)
class Equipment:
    id_equipment: int
    code: str
    name: str
    identified: str
    id_brand: int
    brand: str
    id_unit: int
    unit: str
    serial: str
    id_stock: int = 0
    id_group: int = 0


@dataclass(frozen=True)
class StockMaterial:
    id_equipment: int
    code: str
    name: str
    stock_quantity: int
    id_stock: int
    unit: str
    id_unit: int
    identified: str
    requested_quantity: int = 0
    id_group: int = 0
    group: str = ""
    business_unit_id: int = 0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "stock_quantity": self.stock_quantity,
            "unit": self.unit,
            "group_id": self.id_group,
            "group": self.group,
            "business_unit_id": self.business_unit_id,
        }


@dataclass(frozen=True)
class DetailContext:
    id_os: int
    contract: str
    installer_id: int
    installer_name: str


def normalize_text(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
        .split()
    )


class ImperiumAPI:
    def __init__(
        self,
        root: Path | None = None,
        *,
        host: str = HOST,
        port: int = PORT,
        company: str = "NATAL",
        profile_key: str | None = None,
        controller_id: int = CAPTURED_CONTROLLER_ID,
        log_root: Path | None = None,
    ) -> None:
        self.root = root or Path(__file__).resolve().parent
        self.host = host
        self.port = port
        self.company = company.strip().upper()
        self.profile_key = (
            str(profile_key).strip().lower()
            if profile_key is not None
            else {212: "natal", 596: "fortaleza", 579: "mossoro", 599: "recife"}.get(
                port,
                "",
            )
        )
        if controller_id <= 0:
            raise ValueError("controller_id must be positive")
        self.controller_id = controller_id
        self.log_root = log_root or self.root / "logs"
        self.credentials_path = self.root / "config" / "credentials.dat"
        template_path = self.root / "protocol_templates.json"
        try:
            templates = json.loads(template_path.read_text(encoding="ascii"))
        except FileNotFoundError as exc:
            raise DataSnapError("Protocol templates were not found") from exc

        if templates.get("version") != 1:
            raise DataSnapError("Unsupported protocol template version")
        productive_path = self.root / "productive_protocol_templates.json"
        try:
            productive_templates = json.loads(
                productive_path.read_text(encoding="ascii")
            )
        except FileNotFoundError as exc:
            raise DataSnapError(
                "Productive protocol templates were not found"
            ) from exc
        if productive_templates.get("version") != 1:
            raise DataSnapError("Unsupported productive protocol template version")
        close_lookup = productive_templates.get("close_code_lookup", {})
        self.close_code_lookup_method = str(close_lookup.get("server_method", ""))
        self.close_code_lookup_template = base64.b64decode(
            close_lookup.get("query", "")
        )
        self.close_code_lookup_marker = str(close_lookup.get("code_marker", ""))
        self.close_code_lookup_service_marker = int(
            close_lookup.get("service_marker", 0)
        )
        self.close_code_lookup_page_offset = int(
            close_lookup.get("page_offset", -1)
        )
        self.close_code_lookup_length_offset = int(
            close_lookup.get("length_offset", -1)
        )
        if (
            not self.close_code_lookup_method
            or not self.close_code_lookup_template
            or not self.close_code_lookup_marker.endswith("%")
            or self.close_code_lookup_service_marker <= 0
            or self.close_code_lookup_page_offset < 0
            or self.close_code_lookup_length_offset < 0
        ):
            raise DataSnapError("The close-code lookup template is invalid")
        self._close_code_id_cache: dict[tuple[int, str], int] = {}
        self.stock_protocol = StockProtocol(
            self.root / "stock_protocol_templates.json"
        )
        material_path = self.root / "material_protocol_templates.json"
        try:
            material_templates = json.loads(
                material_path.read_text(encoding="ascii")
            )
        except FileNotFoundError as exc:
            raise DataSnapError(
                "Material write-off protocol templates were not found"
            ) from exc
        if material_templates.get("version") != 1:
            raise DataSnapError(
                "Unsupported material write-off protocol template version"
            )
        self.material_row_prefix = base64.b64decode(
            material_templates["material_row_prefix"]
        )
        self.material_business_unit_id = int(
            material_templates.get("business_unit_id", 1)
        )
        material_preflight = material_templates.get("preflight", {})
        try:
            self.material_preflight_method = str(
                material_preflight["server_method"]
            )
            self.material_preflight_captured_installer = int(
                material_preflight["captured_installer_id"]
            )
            self.material_preflight_contract_id = int(
                material_preflight["contract_id"]
            )
            self.material_preflight_reset_offset = int(
                material_preflight["reset_installer_offset"]
            )
            self.material_preflight_query_offset = int(
                material_preflight["query_installer_offset"]
            )
            self.material_preflight_reset = base64.b64decode(
                material_preflight["reset_query"]
            )
            self.material_preflight_query = base64.b64decode(
                material_preflight["query"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSnapError(
                "The material preflight template is invalid"
            ) from exc
        for packet, offset in (
            (
                self.material_preflight_reset,
                self.material_preflight_reset_offset,
            ),
            (
                self.material_preflight_query,
                self.material_preflight_query_offset,
            ),
        ):
            if (
                offset < 0
                or offset + 4 > len(packet)
                or struct.unpack_from("<I", packet, offset)[0]
                != self.material_preflight_captured_installer
                or b"DspBaixarMiscelaneasRomaneio" not in packet
            ):
                raise DataSnapError(
                    "The material preflight installer marker is invalid"
                )
        material_suffix = base64.b64decode(
            material_templates["close_suffix_400"]
        )
        self.material_controller_id = int(
            material_templates["captured_controller_id"]
        )
        captured_material_controller = struct.pack(
            "<I", self.material_controller_id
        )
        if material_suffix.count(captured_material_controller) != 1:
            raise DataSnapError(
                "The material close controller marker is invalid"
            )
        # SqlEquipSai requires the controller captured in this suffix. Replacing
        # it makes ApplyUpdates return while silently discarding material rows.
        self.material_close_suffix = material_suffix
        material_code = material_templates.get("close_code", {})
        self.material_close_code = str(material_code.get("code", "400"))
        self.material_close_description = str(
            material_code.get("description", "CORRECAO DE CADASTRO")
        )
        material_transforms = material_templates.get("delta_record_transforms", {})
        try:
            self.material_header_old = base64.b64decode(
                material_transforms["header_old"]
            )
            self.material_header_new = base64.b64decode(
                material_transforms["header_new"]
            )
            self.material_quantity_old = base64.b64decode(
                material_transforms["quantity_old"]
            )
            self.material_quantity_new = base64.b64decode(
                material_transforms["quantity_new"]
            )
            self.material_values_old = base64.b64decode(
                material_transforms["material_old"]
            )
            self.material_values_new = base64.b64decode(
                material_transforms["material_new"]
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise DataSnapError(
                "The material delta record transforms are invalid"
            ) from exc
        if (
            len(self.material_row_prefix) != 7
            or self.material_business_unit_id <= 0
            or self.material_close_code != "400"
            or not self.material_close_description
            or len(self.material_header_old) != len(self.material_header_new)
            or len(self.material_quantity_old) != len(self.material_quantity_new)
            or len(self.material_values_old) != len(self.material_values_new)
        ):
            raise DataSnapError(
                "The material write-off protocol template is invalid"
            )
        self.captured_date = dt.date.fromisoformat(templates["captured_date"])
        self.main_query_template = base64.b64decode(templates["main_query"])
        service_field = "IdTipoServico".encode("utf-16le")
        captured_service = (
            service_field + struct.pack("<II", 8, 1) + b"3"
        )
        if self.main_query_template.count(captured_service) != 1:
            raise DataSnapError("The service type query marker is invalid")
        status_field = "Status".encode("utf-16le")
        captured_status = status_field + struct.pack("<II", 8, 1) + b"1"
        if self.main_query_template.count(captured_status) != 1:
            raise DataSnapError("The status query marker is invalid")
        self.main_query_service_marker = captured_service
        self.main_query_status_marker = captured_status
        self.detail_query_template = base64.b64decode(templates["detail_query"])
        self.detail_template_id = int(templates["detail_template_id"])
        self.apply_packet_prefix = base64.b64decode(
            templates["apply_packet_prefix"]
        )
        self.old_mask = base64.b64decode(templates["old_mask"])
        self.new_mask = base64.b64decode(templates["new_mask"])
        captured_controller = struct.pack("<I", CAPTURED_CONTROLLER_ID)
        profile_controller = struct.pack("<I", self.controller_id)

        def for_profile(suffix: bytes) -> bytes:
            if suffix.count(captured_controller) != 1:
                raise DataSnapError("The close packet controller marker is invalid")
            return suffix.replace(captured_controller, profile_controller, 1)

        lookup_template = productive_templates.get("lookup_installed", {})
        self.installed_lookup_method = str(
            lookup_template.get("server_method", "")
        )
        self.installed_lookup_template = base64.b64decode(
            lookup_template.get("query", "")
        )
        self.installed_lookup_serial_marker = str(
            lookup_template.get("serial_marker", "")
        )
        self.installed_lookup_serial_offset = int(
            lookup_template.get("serial_offset", -1)
        )
        self.installed_lookup_serial_length_offset = int(
            lookup_template.get("serial_length_offset", -1)
        )
        self.installed_lookup_query_length_offset = int(
            lookup_template.get("query_length_offset", -1)
        )
        self.installed_lookup_contract_marker = str(
            lookup_template.get("contract_marker", "")
        )
        self.installed_lookup_contract_offset = int(
            lookup_template.get("contract_offset", -1)
        )
        self.installed_lookup_installer_offset = int(
            lookup_template.get("installer_offset", -1)
        )
        if (
            not self.installed_lookup_method
            or len(self.installed_lookup_serial_marker) != 12
            or self.installed_lookup_serial_offset < 0
            or self.installed_lookup_serial_length_offset < 0
            or self.installed_lookup_query_length_offset < 0
            or len(self.installed_lookup_contract_marker) != 7
            or self.installed_lookup_contract_offset < 0
            or self.installed_lookup_installer_offset < 0
        ):
            raise DataSnapError("The installed equipment lookup template is invalid")

        material_template = productive_templates.get("material_stock", {})
        self.material_stock_method = str(material_template.get("server_method", ""))
        self.material_catalog_template = base64.b64decode(
            material_template.get("catalog_query", "")
        )
        self.material_catalog_installer_marker = str(
            material_template.get("catalog_installer_marker", "")
        )
        self.material_catalog_page_offset = int(
            material_template.get("catalog_page_offset", -1)
        )
        self.material_catalog_length_offset = int(
            material_template.get("catalog_length_offset", -1)
        )
        self.manual_material_picker_template = base64.b64decode(
            material_template.get("manual_picker_query", "")
        )
        self.manual_material_installer_parameter = str(
            material_template.get("manual_picker_installer_parameter", "")
        )
        self.manual_material_contract_parameter = str(
            material_template.get("manual_picker_contract_parameter", "")
        )
        self.manual_material_contract_id = int(
            material_template.get("manual_picker_contract_id", 0)
        )
        self.toa_material_lookup_template = base64.b64decode(
            material_template.get("toa_lookup_query", "")
        )
        self.toa_material_lookup_installer_marker = str(
            material_template.get("toa_lookup_installer_marker", "")
        )
        self.toa_material_lookup_description_marker = str(
            material_template.get("toa_lookup_description_marker", "")
        )
        self.toa_material_lookup_page_offset = int(
            material_template.get("toa_lookup_page_offset", -1)
        )
        self.toa_material_lookup_length_offset = int(
            material_template.get("toa_lookup_length_offset", -1)
        )
        self.material_transfer_template = base64.b64decode(
            material_template.get("automatic_transfer_query", "")
        )
        self.material_transfer_page_offset = int(
            material_template.get("transfer_page_offset", -1)
        )
        self.material_transfer_length_offset = int(
            material_template.get("transfer_length_offset", -1)
        )
        self.material_captured_installer_id = int(
            material_template.get("captured_installer_id", 0)
        )
        self.material_captured_user_id = int(
            material_template.get("captured_user_id", 0)
        )
        if (
            not self.material_stock_method
            or not self.material_catalog_template
            or not self.material_transfer_template
            or not self.material_catalog_installer_marker
            or self.material_catalog_page_offset < 0
            or self.material_catalog_length_offset < 0
            or not self.manual_material_picker_template
            or not self.manual_material_installer_parameter
            or not self.manual_material_contract_parameter
            or self.manual_material_contract_id <= 0
            or not self.toa_material_lookup_template
            or not self.toa_material_lookup_installer_marker
            or not self.toa_material_lookup_description_marker
            or self.toa_material_lookup_page_offset < 0
            or self.toa_material_lookup_length_offset < 0
            or self.material_transfer_page_offset < 0
            or self.material_transfer_length_offset < 0
            or self.material_captured_installer_id <= 0
            or self.material_captured_user_id <= 0
        ):
            raise DataSnapError("The material stock protocol template is invalid")

        self.delta_suffix = for_profile(
            base64.b64decode(templates["delta_suffix"])
        )
        # The official client uses both delta layouts for the same close code.
        self.delta_suffix_without_optional = for_profile(
            bytes.fromhex(
                "08aaaa0aa8aaaa8aaaa8aaaaaaaaaaaaaaaaaaaaaa"
                "0207000000033130360f434c49454e544520415553454e5445"
                "04000dc7040060601000050200000000c0"
            )
        )
        self.delta_suffix_variants = (
            self.delta_suffix_without_optional,
            self.delta_suffix,
        )
        cancel_suffix = for_profile(
            bytes.fromhex(
                "08aaaa0aa8aaaa8aaaa8aaaaaaaaaaaaaaaaaaaaaa"
                "023d010000033030300c43414e43454c414d454e544f"
                "03000dc7040060601000050200000000c0"
            )
        )
        productive_suffixes = productive_templates.get("close_suffixes", {})
        no_resident_suffix = for_profile(
            base64.b64decode(productive_suffixes.get("306", ""))
        )
        not_requested_suffix = for_profile(
            base64.b64decode(productive_suffixes.get("312", ""))
        )
        install_suffix = for_profile(
            base64.b64decode(productive_suffixes.get("409", ""))
        )
        removal_suffix = for_profile(
            base64.b64decode(productive_suffixes.get("430", ""))
        )
        remote_control_suffix = for_profile(
            base64.b64decode(productive_suffixes.get("512", ""))
        )
        captured_refusal_observation = (
            "3460070 404 Via ativo informar que fez acordo 84994839330 "
            "est\u00e1 em negocia\u00e7\u00e3o."
        )
        refusal_observation_marker = "OBSERVACAO OBRIGATORIA"
        refusal_suffix = for_profile(
            bytes.fromhex(
                "08aaaa0aa8aaaa82aaa8aaaaa8aaaaaaaaaaaaaaaa"
                "02280000000334303443"
                "434c49454e5445205245435553412d5345204445564f4c56455220"
                "4f204445434f444552202f204341424c4553204d4f44454d"
                "4d0033343630303730203430342056696120617469766f20696e66"
                "6f726d6172207175652066657a2061636f72646f20383439393438"
                "333933333020657374e120656d206e65676f636961e7e36f2e"
                "04000dc70400030060601000050200000000c0"
            )
        )
        captured_refusal_token = (
            struct.pack("<H", len(captured_refusal_observation.encode("cp1252")))
            + captured_refusal_observation.encode("cp1252")
        )
        refusal_marker_token = (
            struct.pack("<H", len(refusal_observation_marker))
            + refusal_observation_marker.encode("ascii")
        )
        if refusal_suffix.count(captured_refusal_token) != 1:
            raise DataSnapError("The 404 observation marker is invalid")
        refusal_suffix = refusal_suffix.replace(
            captured_refusal_token,
            refusal_marker_token,
            1,
        )
        chip_suffixes: tuple[bytes, ...] = ()
        chip_close_ids = productive_templates.get("close_ids", {}).get("706", {})
        chip_id_by_port = chip_close_ids.get("by_port", {})
        runtime_chip_id = chip_id_by_port.get(str(self.port))
        if runtime_chip_id is not None:
            captured_chip_id = int(chip_close_ids.get("captured", 0))
            runtime_chip_id = int(runtime_chip_id)
            encoded_chip_suffixes = productive_suffixes.get("706", [])
            if isinstance(encoded_chip_suffixes, str):
                encoded_chip_suffixes = [encoded_chip_suffixes]
            captured_chip_marker = struct.pack("<I", captured_chip_id)
            runtime_chip_marker = struct.pack("<I", runtime_chip_id)
            built_chip_suffixes = []
            for encoded_suffix in encoded_chip_suffixes:
                raw_suffix = base64.b64decode(encoded_suffix)
                if raw_suffix.count(captured_chip_marker) != 1:
                    raise DataSnapError("The chip close code marker is invalid")
                raw_suffix = raw_suffix.replace(
                    captured_chip_marker,
                    runtime_chip_marker,
                    1,
                )
                built_chip_suffixes.append(for_profile(raw_suffix))
            chip_suffixes = tuple(built_chip_suffixes)
        self.close_codes = {
            "106": CloseCode(
                code="106",
                wire_code="106",
                description="CLIENTE AUSENTE",
                id_code=7,
                suffixes=self.delta_suffix_variants,
            ),
            "125": CloseCode(
                code="125",
                wire_code="125",
                description="CLIENTE DESISTE DA AGENDA",
                id_code=7,
                suffixes=self.delta_suffix_variants,
            ),
            "301": CloseCode(
                code="301",
                wire_code="301",
                description="TIPO DE OS INCORRETO",
                id_code=7,
                suffixes=self.delta_suffix_variants,
            ),
            "0": CloseCode(
                code="0",
                wire_code="000",
                description="CANCELAMENTO",
                id_code=317,
                suffixes=(cancel_suffix,),
            ),
            "306": CloseCode(
                code="306",
                wire_code="306",
                description="N\u00c3O RESIDE NO ENDERE\u00c7O",
                id_code=30,
                suffixes=(no_resident_suffix,),
            ),
            "312": CloseCode(
                code="312",
                wire_code="312",
                description="NÃO SOLICITOU SERVIÇO",
                id_code=36,
                suffixes=(not_requested_suffix,),
            ),
            "409": CloseCode(
                code="409",
                wire_code="409",
                description="INSTALAÇÃO CONCLUIDA",
                id_code=44,
                suffixes=(install_suffix,),
                productive=True,
            ),
            "404": CloseCode(
                code="404",
                wire_code="404",
                description=(
                    "CLIENTE RECUSA-SE DEVOLVER O DECODER / CABLES MODEM"
                ),
                id_code=40,
                suffixes=(refusal_suffix,),
                requires_observation=True,
                observation_marker=refusal_observation_marker,
            ),
            "430": CloseCode(
                code="430",
                wire_code="430",
                description="EQUIPAMENTO RETIRADO",
                id_code=63,
                suffixes=(removal_suffix,),
                productive=True,
            ),
            "512": CloseCode(
                code="512",
                wire_code="512",
                description="CONTROLE REMOTO COM DEFEITO - TROCA",
                id_code=121,
                suffixes=(remote_control_suffix,),
            ),
        }
        if chip_suffixes:
            self.close_codes["706"] = CloseCode(
                code="706",
                wire_code="706",
                description="CHIP ENTREGUE",
                id_code=runtime_chip_id,
                suffixes=chip_suffixes,
                productive=True,
            )
        self.removed_equipment = {
            "decoder": Equipment(
                id_equipment=280,
                code="41001272",
                name="DECODER DIG. HD DCR7121 - PACE",
                identified="S",
                id_brand=6,
                brand="DIVERSOS",
                id_unit=2,
                unit="UN",
                serial="",
            ),
            "emta": Equipment(
                id_equipment=260,
                code="41001352",
                name="EMTA WIFI 2.0 DOCSIS SVG1202",
                identified="S",
                id_brand=2,
                brand="MOTOROLA",
                id_unit=2,
                unit="UN",
                serial="",
            ),
            "smart": Equipment(
                id_equipment=288,
                code="41001234",
                name="SMART CARD AVULSO PRETO NOVO",
                identified="S",
                id_brand=6,
                brand="DIVERSOS",
                id_unit=2,
                unit="UN",
                serial="",
            ),
        }
        self.apply_success = bytes.fromhex(templates["apply_success"])
        self.import_protocol = TOAImportProtocol(
            self.root / "import_protocol_templates.json",
            self.controller_id,
        )
        self.native_order_protocol = NativeOrderProtocol(
            self.root / "native_order_protocol_templates.json",
            self.profile_key,
            self.controller_id,
        )
        self.manual_order_protocol = ManualOrderProtocol(
            self.root / "manual_order_protocol_templates.json"
        )
        self.installer_change_protocol = InstallerChangeProtocol(
            self.root / "installer_change_protocol_templates.json"
        )
        self.serialized_transfer_protocol = SerializedTransferProtocol(
            self.root / "serialized_transfer_protocol_templates.json"
        )
        self._operation_lock = threading.RLock()
        self._serial_owner_cache: dict[str, tuple[float, dict]] = {}
        self._equipment_group_cache: dict[str, dict | None] = {}

    def _credentials(self) -> dict[str, str]:
        return load_credentials(self.credentials_path)

    def _client(self, timeout: float = 25.0) -> DataSnapClient:
        credentials = self._credentials()
        return DataSnapClient(
            self.host,
            self.port,
            credentials["username"],
            credentials["password"],
            timeout=timeout,
        )

    @staticmethod
    def _handle(client: DataSnapClient, method: str) -> int:
        prepared = client.prepare(method)
        try:
            return int(prepared["result"][0]["handle"][0])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DataSnapError(f"Invalid prepare response for {method}") from exc

    @staticmethod
    def _automation_date(value: dt.date, end_of_day: bool = False) -> bytes:
        days = (value - dt.date(1899, 12, 30)).days
        number = float(days)
        if end_of_day:
            number += 1 - (1 / 86_400_000)
        return struct.pack("<d", number)

    def _main_query_for(
        self,
        date: dt.date,
        *,
        status: str = "field",
        service_type: str = "all",
    ) -> bytes:
        try:
            status_value = ORDER_STATUS_FILTERS[status]
        except KeyError as exc:
            raise ValueError("Filtro de status invalido") from exc
        try:
            service_type_value = ORDER_SERVICE_TYPE_FILTERS[service_type]
        except KeyError as exc:
            raise ValueError("Filtro de tipo de servico invalido") from exc
        captured_start = self._automation_date(self.captured_date)
        captured_end = self._automation_date(self.captured_date, end_of_day=True)
        query = self.main_query_template
        if query.count(captured_start) != 1 or query.count(captured_end) != 1:
            raise DataSnapError("The query date markers are invalid")
        query = query.replace(
            captured_start, self._automation_date(date)
        ).replace(captured_end, self._automation_date(date, end_of_day=True))
        status_marker = (
            "Status".encode("utf-16le")
            + struct.pack("<II", 8, 1)
            + status_value.encode("ascii")
        )
        service_marker = (
            "IdTipoServico".encode("utf-16le")
            + struct.pack("<II", 8, 1)
            + service_type_value.encode("ascii")
        )
        return query.replace(
            self.main_query_status_marker, status_marker, 1
        ).replace(self.main_query_service_marker, service_marker, 1)

    def _fetch_main_payload(
        self,
        date: dt.date,
        *,
        status: str = "field",
        service_type: str = "all",
    ) -> bytes:
        with self._client(timeout=MAIN_QUERY_TIMEOUT) as client:
            handle = self._handle(client, "TDtmOrdemServico.AS_GetRecords")
            LOGGER.info(
                "DataSnap: aguardando dataset principal por ate %.0fs",
                MAIN_QUERY_TIMEOUT,
            )
            response = client.request(
                "execute",
                [
                    {"handle": [handle]},
                    self._main_query_for(
                        date,
                        status=status,
                        service_type=service_type,
                    ),
                ],
            )
            try:
                payload = bytearray(response["result"][1]["data"][1])
            except (KeyError, IndexError, TypeError) as exc:
                raise DataSnapError("The order query returned no dataset") from exc

            if len(payload) < 24:
                raise DataSnapError("The order dataset is incomplete")
            expected_length = struct.unpack_from("<I", payload, 20)[0] + 28
            remainder_count = 0
            fragmented = expected_length > len(payload)
            while fragmented and len(payload) < expected_length:
                remainder_count += 1
                if remainder_count > MAX_MAIN_DATASET_FRAGMENTS:
                    raise DataSnapError("The order dataset has too many fragments")
                client.set_timeout(MAIN_FRAGMENT_TIMEOUT)
                remainder = client.request(
                    "more_blob", [handle, 1, 0, 7, True, 0]
                )
                try:
                    chunk = remainder["result"][0]["data"][1]
                except (KeyError, IndexError, TypeError) as exc:
                    raise DataSnapError("The order dataset remainder is invalid") from exc
                if not chunk:
                    raise DataSnapError("The order dataset remainder is empty")
                payload.extend(chunk)
            if fragmented and len(payload) != expected_length:
                raise DataSnapError(
                    f"Incomplete order dataset: {len(payload)} of {expected_length} bytes"
                )
            return bytes(payload)

    @staticmethod
    def _parse_orders(payload: bytes) -> list[Order]:
        if len(payload) < 46:
            raise DataSnapError("The order dataset header is invalid")
        if payload[:3] == b"\xc0\xc0\x60":
            return []
        count_width = payload[2] - 0x60 if payload[:2] == b"\xc0\xc0" else 0
        if count_width not in (1, 2, 3, 4):
            raise DataSnapError("The order dataset marker is invalid")
        orders: list[Order] = []
        seen: set[int] = set()

        for match in re.finditer(rb"[\x01-\x14](\d{1,20})", payload):
            num_os_bytes = match.group(1)
            if payload[match.start()] != len(num_os_bytes):
                continue
            id_position = match.start() - 4
            if id_position < 0:
                continue
            id_os = struct.unpack_from("<I", payload, id_position)[0]
            if id_os <= 0 or id_os > 0x0FFFFFFF or id_os in seen:
                continue

            position = match.end()
            try:
                contract_length = payload[position]
                position += 1
                if contract_length <= 0 or contract_length > 20:
                    continue
                contract_bytes = payload[position : position + contract_length]
                if len(contract_bytes) != contract_length or not contract_bytes.isdigit():
                    continue
                position += contract_length
                id_service = struct.unpack_from("<I", payload, position)[0]
                position += 4
                if id_service <= 0 or id_service > 1_000_000:
                    continue
                service_length = payload[position]
                position += 1
                if service_length <= 0 or service_length > 120:
                    continue
                service_bytes = payload[position : position + service_length]
                if len(service_bytes) != service_length or any(
                    byte < 0x20 or byte == 0x7F for byte in service_bytes
                ):
                    continue
                service = service_bytes.decode("latin-1")
            except (IndexError, struct.error, UnicodeDecodeError):
                continue

            seen.add(id_os)
            orders.append(
                Order(
                    id_os=id_os,
                    num_os=num_os_bytes.decode("ascii"),
                    contract=contract_bytes.decode("ascii"),
                    id_service=id_service,
                    service=service,
                )
            )

        if not orders:
            raise DataSnapError("No valid orders were parsed from a non-empty dataset")
        return orders

    def list_orders(
        self,
        date: dt.date | None = None,
        *,
        status: str = "field",
        service_type: str = "all",
    ) -> list[Order]:
        if status == "all":
            raise ValueError(
                "Use um status especifico para preservar a situacao de cada OS"
            )
        if status not in ORDER_STATUS_LABELS:
            raise ValueError("Filtro de status invalido")
        query_date = date or dt.date.today()
        with self._operation_lock:
            started = time.monotonic()
            last_network_error: Exception | None = None
            for attempt in range(1, 4):
                LOGGER.info(
                    "DataSnap: iniciando consulta de OS, tentativa %s/3",
                    attempt,
                )
                try:
                    orders = self._parse_orders(
                        self._fetch_main_payload(
                            query_date,
                            status=status,
                            service_type=service_type,
                        )
                    )
                    orders = [
                        replace(order, status=ORDER_STATUS_LABELS[status])
                        for order in orders
                    ]
                    break
                except (OSError, DataSnapError) as exc:
                    last_network_error = exc
                    LOGGER.warning(
                        "DataSnap: consulta incompleta ou sem conexao %s/3: %s",
                        attempt,
                        exc,
                    )
                    if attempt < 3:
                        time.sleep(attempt)
                except Exception:
                    LOGGER.exception(
                        "DataSnap: consulta de OS falhou apos %.1fs",
                        time.monotonic() - started,
                    )
                    raise
            else:
                if isinstance(last_network_error, OSError):
                    message = (
                        "Nao foi possivel conectar ao servidor do Imperium "
                        "apos 3 tentativas"
                    )
                else:
                    message = (
                        "O servidor do Imperium retornou dados invalidos apos "
                        f"3 tentativas: {last_network_error}"
                    )
                error = DataSnapError(message)
                raise error from last_network_error
            LOGGER.info(
                "DataSnap: consulta retornou %s OS em %.1fs",
                len(orders),
                time.monotonic() - started,
            )
            return orders

    @property
    def installer_change_enabled(self) -> bool:
        return self.profile_key == self.installer_change_protocol.profile

    @property
    def serialized_transfer_enabled(self) -> bool:
        return self.profile_key == self.serialized_transfer_protocol.profile

    def order_installer(self, order: Order) -> dict:
        with self._operation_lock:
            last_error: OSError | DataSnapError | None = None
            for attempt in range(1, 4):
                try:
                    detail = self._fetch_detail(order.id_os, timeout=15.0)
                    context = self._detail_context(detail)
                    if (
                        context.id_os != order.id_os
                        or context.contract != order.contract
                        or order.num_os.encode("ascii") not in detail
                    ):
                        raise DataSnapError(
                            "O servidor retornou outra OS ao validar o instalador"
                        )
                    return {
                        "ok": True,
                        "id_os": context.id_os,
                        "contract": context.contract,
                        "installer_id": context.installer_id,
                        "installer_name": context.installer_name,
                        "source": "imperium_detail",
                    }
                except (OSError, DataSnapError) as exc:
                    last_error = exc
                    if attempt < 3:
                        time.sleep(attempt)
            raise DataSnapError(
                "Nao foi possivel confirmar o instalador atual da OS"
            ) from last_error

    def change_order_installer(
        self,
        order_id: int,
        installer_id: int,
    ) -> dict:
        if not self.installer_change_enabled:
            raise ValueError(
                "A alteracao de instalador foi validada somente em Natal"
            )
        query = self.installer_change_protocol.build_query(
            installer_id,
            self.controller_id,
            order_id,
        )
        with self._operation_lock:
            with self._client(timeout=30.0) as client:
                handle = self._handle(
                    client,
                    self.installer_change_protocol.server_method,
                )
                client.set_timeout(45.0)
                response = client.request(
                    "execute",
                    [{"handle": [handle]}, query],
                )
        if not self.installer_change_protocol.confirmed(response):
            raise DataSnapError(
                "O servidor nao confirmou a alteracao do instalador da OS"
            )
        confirmed_context: DetailContext | None = None
        last_context: DetailContext | None = None
        last_error: OSError | DataSnapError | None = None
        for attempt in range(1, 4):
            try:
                detail = self._fetch_detail(order_id, timeout=15.0)
                context = self._detail_context(detail)
                last_context = context
                if context.id_os == order_id and context.installer_id == installer_id:
                    confirmed_context = context
                    break
            except (OSError, DataSnapError) as exc:
                last_error = exc
            if attempt < 3:
                time.sleep(attempt)
        if confirmed_context is None:
            current = (
                f"; a OS permanece com {last_context.installer_name}"
                if last_context is not None
                else ""
            )
            error = DataSnapError(
                "O servidor respondeu a alteracao, mas a leitura de confirmacao "
                f"nao encontrou o novo instalador{current}"
            )
            if last_error is not None:
                raise error from last_error
            raise error
        LOGGER.info(
            "IdOS %s: instalador confirmado como %s (IdInstalador %s)",
            order_id,
            confirmed_context.installer_name,
            installer_id,
        )
        return {
            "ok": True,
            "id_os": order_id,
            "installer_id": installer_id,
            "installer_name": confirmed_context.installer_name,
        }

    @staticmethod
    def _dataset_payload(
        client: DataSnapClient,
        handle: int,
        query: bytes,
        label: str,
    ) -> bytes:
        response = client.request(
            "execute", [{"handle": [handle]}, query]
        )
        try:
            payload = bytearray(response["result"][1]["data"][1])
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError(
                f"A consulta de {label} nao retornou um dataset"
            ) from exc

        expected_length = None
        if len(payload) >= 24 and payload[:3] == b"\xc0\xc0\x62":
            candidate = struct.unpack_from("<I", payload, 20)[0] + 28
            if candidate >= len(payload):
                expected_length = candidate
        fragment_count = 0
        while expected_length is not None and len(payload) < expected_length:
            fragment_count += 1
            if fragment_count > 64:
                raise DataSnapError(
                    f"A consulta de {label} possui fragmentos demais"
                )
            remainder = client.request(
                "more_blob", [handle, 1, 0, 7, True, 0]
            )
            try:
                chunk = remainder["result"][0]["data"][1]
            except (KeyError, IndexError, TypeError) as exc:
                raise DataSnapError(
                    f"O fragmento de {label} e invalido"
                ) from exc
            if not chunk:
                raise DataSnapError(
                    f"O fragmento de {label} veio vazio"
                )
            payload.extend(chunk)
        if expected_length is not None and len(payload) != expected_length:
            raise DataSnapError(
                f"Dataset de {label} incompleto: "
                f"{len(payload)} de {expected_length} bytes"
            )
        return bytes(payload)

    def list_stock_technicians(self) -> list[dict]:
        with self._operation_lock:
            with self._client(timeout=20.0) as client:
                handle = self._handle(
                    client, self.stock_protocol.technicians_method
                )
                payload = self._dataset_payload(
                    client,
                    handle,
                    self.stock_protocol.technicians_query,
                    "estoques dos tecnicos",
                )
            technicians = parse_technicians(payload)
            LOGGER.info(
                "DataSnap: %s estoques de tecnicos localizados em %s",
                len(technicians),
                self.company,
            )
            return [technician.to_dict() for technician in technicians]

    @staticmethod
    def _decimal_text(value: Decimal) -> str:
        normalized = format(value, "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

    def _stock_result(self, technician, items) -> dict:
        positive = [item for item in items if item.quantity_number > 0]
        quantity_total = sum(
            (item.quantity_number for item in positive),
            start=Decimal(0),
        )
        serial_count = sum(len(item.serials) for item in items)
        return {
            "ok": True,
            "technician": technician.to_dict(),
            "summary": {
                "item_count": len(items),
                "positive_item_count": len(positive),
                "zero_item_count": len(items) - len(positive),
                "group_count": len({item.group for item in positive}),
                "quantity_total": self._decimal_text(quantity_total),
                "serial_count": serial_count,
            },
            "items": [item.to_dict() for item in items],
        }

    def technician_stocks(self, stock_ids: list[int]) -> list[dict]:
        ordered_ids: list[int] = []
        seen: set[int] = set()
        for raw_id in stock_ids:
            stock_id = int(raw_id)
            if stock_id <= 0:
                raise ValueError("Selecione tecnicos validos")
            if stock_id not in seen:
                seen.add(stock_id)
                ordered_ids.append(stock_id)
        if not ordered_ids:
            raise ValueError("Selecione pelo menos um tecnico")
        if len(ordered_ids) > 150:
            raise ValueError("Selecione no maximo 150 tecnicos por lote")

        with self._operation_lock:
            with self._client(timeout=45.0) as client:
                stock_handle = self._handle(
                    client, self.stock_protocol.technicians_method
                )
                technician_payload = self._dataset_payload(
                    client,
                    stock_handle,
                    self.stock_protocol.technicians_query,
                    "estoques dos tecnicos",
                )
                technicians = parse_technicians(technician_payload)
                technician_by_id = {item.stock_id: item for item in technicians}
                missing = [
                    stock_id
                    for stock_id in ordered_ids
                    if stock_id not in technician_by_id
                ]
                if missing:
                    raise ValueError(
                        "Um ou mais estoques selecionados nao pertencem a lista de tecnicos"
                    )

                equipment_handle = self._handle(
                    client, self.stock_protocol.items_method
                )
                results: list[dict] = []
                for position, stock_id in enumerate(ordered_ids, start=1):
                    technician = technician_by_id[stock_id]
                    LOGGER.info(
                        "DataSnap: consultando estoque %s de %s (%s/%s)",
                        stock_id,
                        technician.technician_name,
                        position,
                        len(ordered_ids),
                    )
                    item_payload = self._dataset_payload(
                        client,
                        equipment_handle,
                        self.stock_protocol.items_query(stock_id),
                        "equipamentos do tecnico",
                    )
                    serial_payload = self._dataset_payload(
                        client,
                        equipment_handle,
                        self.stock_protocol.serials_query(stock_id),
                        "seriais do tecnico",
                    )
                    items = attach_serials(
                        parse_stock_items(item_payload),
                        parse_stock_serials(serial_payload),
                    )
                    result = self._stock_result(technician, items)
                    summary = result["summary"]
                    LOGGER.info(
                        "DataSnap: estoque %s consultado em %s: "
                        "%s itens com saldo, %s seriais",
                        stock_id,
                        self.company,
                        summary["positive_item_count"],
                        summary["serial_count"],
                    )
                    results.append(result)
                return results

    def technician_stock(self, stock_id: int) -> dict:
        return self.technician_stocks([stock_id])[0]

    def find_serial_owner(self, serial: str, *, fresh: bool = False) -> dict:
        requested = str(serial).strip().upper()
        if not re.fullmatch(r"[A-Z0-9._/\-]{4,50}", requested):
            raise ValueError("Serial invalido")

        if fresh:
            self._serial_owner_cache.pop(requested, None)
        cached = self._serial_owner_cache.get(requested)
        if cached is not None and time.monotonic() - cached[0] < 300:
            return {**cached[1], "cached": True}

        started = time.monotonic()
        with self._operation_lock:
            LOGGER.info(
                "DataSnap: procurando o proprietario do serial %s em %s",
                requested,
                self.company,
            )
            with self._client(timeout=30.0) as client:
                technician_handle = self._handle(
                    client, self.stock_protocol.technicians_method
                )
                technician_payload = self._dataset_payload(
                    client,
                    technician_handle,
                    self.stock_protocol.technicians_query,
                    "estoques dos tecnicos",
                )
                technicians = parse_technicians(technician_payload)
                serial_handle = self._handle(
                    client, self.stock_protocol.serials_method
                )

                match = None
                owner = None
                scanned = 0
                failed_stocks = 0
                for technician in technicians:
                    scanned += 1
                    try:
                        serial_payload = self._dataset_payload(
                            client,
                            serial_handle,
                            self.stock_protocol.serials_query(technician.stock_id),
                            f"seriais de {technician.technician_name}",
                        )
                    except (DataSnapError, OSError) as exc:
                        failed_stocks += 1
                        LOGGER.warning(
                            "DataSnap: estoque %s ignorado na busca do serial %s: %s",
                            technician.stock_id,
                            requested,
                            exc,
                        )
                        continue
                    match = next(
                        (
                            item
                            for item in parse_stock_serials(serial_payload)
                            if requested in (item.serial.upper(), item.smart.upper())
                        ),
                        None,
                    )
                    if match is not None:
                        owner = technician
                        break

                equipment = None
                if owner is not None and match is not None:
                    item_handle = self._handle(
                        client, self.stock_protocol.items_method
                    )
                    item_payload = self._dataset_payload(
                        client,
                        item_handle,
                        self.stock_protocol.items_query(owner.stock_id),
                        f"equipamentos de {owner.technician_name}",
                    )
                    stock_item = next(
                        (
                            item
                            for item in parse_stock_items(item_payload)
                            if item.equipment_id == match.equipment_id
                        ),
                        None,
                    )
                    if stock_item is not None:
                        equipment = {
                            "equipment_id": stock_item.equipment_id,
                            "group_id": stock_item.group_id,
                            "code": stock_item.code,
                            "name": stock_item.equipment,
                            "group": stock_item.group,
                            "brand_id": stock_item.brand_id,
                            "brand": stock_item.brand,
                            "unit_id": stock_item.unit_id,
                            "unit": stock_item.unit,
                            "identified": stock_item.identified,
                        }

        elapsed = round(time.monotonic() - started, 2)
        result = {
            "ok": True,
            "found": owner is not None and match is not None,
            "serial": requested,
            "owner": owner.to_dict() if owner is not None else None,
            "stock_serial": match.to_dict() if match is not None else None,
            "equipment": equipment,
            "scanned": scanned,
            "total_stocks": len(technicians),
            "failed_stocks": failed_stocks,
            "elapsed_seconds": elapsed,
            "cached": False,
        }
        self._serial_owner_cache[requested] = (time.monotonic(), result)
        if result["found"]:
            LOGGER.info(
                "DataSnap: serial %s localizado em %s apos %s estoques (%.2fs)",
                requested,
                owner.technician_name,
                scanned,
                elapsed,
            )
        else:
            LOGGER.warning(
                "DataSnap: serial %s nao localizado em %s estoques (%.2fs)",
                requested,
                scanned,
                elapsed,
            )
        return result

    @staticmethod
    def _stock_serial_match(stock: dict, serial: str) -> dict | None:
        requested = str(serial).strip().upper()
        for item in stock.get("items", ()):
            for stock_serial in item.get("serials", ()):
                if requested in (
                    str(stock_serial.get("serial", "")).upper(),
                    str(stock_serial.get("smart", "")).upper(),
                ):
                    return {"item": item, "stock_serial": stock_serial}
        return None

    def serialized_transfer_preview(self, id_os: int, serial: str) -> dict:
        if not self.serialized_transfer_enabled:
            raise ValueError(
                "A transferencia de equipamento foi validada somente em Natal"
            )
        requested = str(serial).strip().upper()
        if not re.fullmatch(r"[A-Z0-9._/\-]{4,50}", requested):
            raise ValueError("Serial invalido")
        with self._operation_lock:
            context = self._detail_context(self._fetch_detail(id_os, timeout=15.0))
            if context.id_os != id_os:
                raise DataSnapError(
                    "O servidor retornou outra OS ao preparar a transferencia"
                )
            technicians = self.list_stock_technicians()
            target = next(
                (
                    technician
                    for technician in technicians
                    if int(technician.get("installer_id", 0))
                    == context.installer_id
                ),
                None,
            )
            if target is None:
                raise ValueError(
                    "O instalador atual da OS nao possui estoque de tecnico"
                )
            ownership = self.find_serial_owner(requested)
        if not ownership.get("found"):
            raise ValueError("O proprietario atual do serial nao foi localizado")
        source = ownership.get("owner")
        equipment = ownership.get("equipment")
        stock_serial = ownership.get("stock_serial")
        if not all(isinstance(value, dict) for value in (source, equipment, stock_serial)):
            raise DataSnapError(
                "O servidor nao retornou os dados completos do equipamento"
            )
        if int(source.get("stock_id", 0)) == int(target.get("stock_id", 0)):
            raise ValueError(
                "O equipamento ja esta no estoque do instalador atual da OS"
            )
        required_equipment = (
            "equipment_id",
            "code",
            "name",
            "brand_id",
            "brand",
            "unit_id",
            "unit",
            "identified",
        )
        if any(not str(equipment.get(field, "")).strip() for field in required_equipment):
            raise DataSnapError(
                "O cadastro do equipamento esta incompleto para transferencia"
            )
        actual_serial = str(stock_serial.get("serial", "")).strip().upper()
        if not actual_serial:
            actual_serial = str(stock_serial.get("smart", "")).strip().upper()
        if not actual_serial:
            raise DataSnapError("O estoque nao retornou o serial identificado")
        return {
            "ok": True,
            "profile": self.profile_key,
            "id_os": context.id_os,
            "contract": context.contract,
            "requested_serial": requested,
            "serial": actual_serial,
            "source": source,
            "target": target,
            "equipment": equipment,
            "stock_serial": stock_serial,
        }

    def _serialized_transfer_state(
        self,
        source_stock_id: int,
        target_stock_id: int,
        serial: str,
    ) -> dict:
        stocks = self.technician_stocks([source_stock_id, target_stock_id])
        by_id = {
            int(stock["technician"]["stock_id"]): stock
            for stock in stocks
        }
        source_match = self._stock_serial_match(
            by_id[source_stock_id],
            serial,
        )
        target_match = self._stock_serial_match(
            by_id[target_stock_id],
            serial,
        )
        return {
            "source_has_serial": source_match is not None,
            "target_has_serial": target_match is not None,
            "source_match": source_match,
            "target_match": target_match,
        }

    def transfer_serialized_equipment(self, preview: dict) -> dict:
        if not self.serialized_transfer_enabled:
            raise ValueError(
                "A transferencia de equipamento foi validada somente em Natal"
            )
        source = preview.get("source")
        target = preview.get("target")
        equipment = preview.get("equipment")
        stock_serial = preview.get("stock_serial")
        if not all(isinstance(value, dict) for value in (
            source,
            target,
            equipment,
            stock_serial,
        )):
            raise ValueError("A previa da transferencia esta incompleta")
        try:
            id_os = int(preview["id_os"])
            source_stock_id = int(source["stock_id"])
            source_installer_id = int(source["installer_id"])
            target_stock_id = int(target["stock_id"])
            target_installer_id = int(target["installer_id"])
            equipment_id = int(equipment["equipment_id"])
            brand_id = int(equipment["brand_id"])
            unit_id = int(equipment["unit_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "A previa da transferencia possui identificadores invalidos"
            ) from exc
        serial = str(preview.get("serial", "")).strip().upper()
        requested_serial = str(
            preview.get("requested_serial", serial)
        ).strip().upper()
        if (
            min(
                id_os,
                source_stock_id,
                source_installer_id,
                target_stock_id,
                target_installer_id,
                equipment_id,
                brand_id,
                unit_id,
            )
            <= 0
            or source_stock_id == target_stock_id
            or not serial
        ):
            raise ValueError("A previa da transferencia possui dados invalidos")

        with self._operation_lock:
            context = self._detail_context(self._fetch_detail(id_os, timeout=15.0))
            if context.installer_id != target_installer_id:
                raise ValueError(
                    "O instalador da OS mudou desde a previa. Localize o serial novamente"
                )
            technicians = self.list_stock_technicians()
            technician_by_stock = {
                int(item["stock_id"]): item for item in technicians
            }
            current_source = technician_by_stock.get(source_stock_id)
            current_target = technician_by_stock.get(target_stock_id)
            if current_source is None or current_target is None:
                raise ValueError("A origem ou o destino nao pertence mais aos estoques")
            if (
                int(current_source.get("installer_id", 0)) != source_installer_id
                or int(current_target.get("installer_id", 0)) != target_installer_id
            ):
                raise ValueError(
                    "O vinculo de um dos estoques mudou desde a previa"
                )

            before = self._serialized_transfer_state(
                source_stock_id,
                target_stock_id,
                serial,
            )
            source_match = before["source_match"]
            if source_match is None:
                raise ValueError(
                    "O serial nao esta mais no estoque de origem. Localize novamente"
                )
            if before["target_has_serial"]:
                raise ValueError(
                    "O serial ja aparece no estoque de destino. Atualize a consulta"
                )
            current_item = source_match["item"]
            current_serial = source_match["stock_serial"]
            if int(current_item.get("equipment_id", 0)) != equipment_id:
                raise ValueError(
                    "O equipamento do serial mudou desde a previa"
                )
            wire_serial = str(current_serial.get("serial", "")).strip().upper()
            if not wire_serial:
                wire_serial = str(current_serial.get("smart", "")).strip().upper()
            if wire_serial != serial:
                raise ValueError("O serial do estoque mudou desde a previa")

            values = {
                "controller_id": self.controller_id,
                "source_stock_id": source_stock_id,
                "source_stock_name": str(current_source["stock_name"]).strip(),
                "source_installer_id": source_installer_id,
                "source_technician_name": str(
                    current_source["technician_name"]
                ).strip(),
                "target_stock_id": target_stock_id,
                "target_stock_name": str(current_target["stock_name"]).strip(),
                "target_installer_id": target_installer_id,
                "target_technician_name": str(
                    current_target["technician_name"]
                ).strip(),
                "equipment_id": equipment_id,
                "equipment_code": str(current_item["code"]).strip(),
                "equipment_name": str(current_item["equipment"]).strip(),
                "brand_id": int(current_item["brand_id"]),
                "brand": str(current_item["brand"]).strip(),
                "unit_id": int(current_item["unit_id"]),
                "unit": str(current_item["unit"]).strip(),
                "identified": str(current_item["identified"]).strip(),
                "serial": wire_serial,
            }
            apply_blob = self.serialized_transfer_protocol.build_apply(values)
            write_error: Exception | None = None
            try:
                with self._client(timeout=30.0) as client:
                    apply_handle = self._handle(
                        client,
                        self.serialized_transfer_protocol.apply_method,
                    )
                    client.set_timeout(45.0)
                    LOGGER.warning(
                        "Transferindo serial %s de %s para %s",
                        wire_serial,
                        current_source["technician_name"],
                        current_target["technician_name"],
                    )
                    client.request(
                        "execute",
                        [{"handle": [apply_handle]}, apply_blob],
                    )
                    finalize_handle = self._handle(
                        client,
                        self.serialized_transfer_protocol.finalize_method,
                    )
                    client.set_timeout(30.0)
                    client.request(
                        "execute",
                        [
                            {"handle": [finalize_handle]},
                            self.serialized_transfer_protocol.finalize_blob,
                        ],
                    )
            except (DataSnapError, OSError, socket.timeout) as exc:
                write_error = exc
                LOGGER.warning(
                    "Transferencia do serial %s respondeu com erro; "
                    "confirmando os estoques: %s",
                    wire_serial,
                    exc,
                )

            final_state = None
            confirmation_error: Exception | None = None
            for delay in (0.0, 2.0, 5.0):
                if delay:
                    time.sleep(delay)
                try:
                    final_state = self._serialized_transfer_state(
                        source_stock_id,
                        target_stock_id,
                        wire_serial,
                    )
                    confirmation_error = None
                    if (
                        not final_state["source_has_serial"]
                        and final_state["target_has_serial"]
                    ):
                        break
                except (DataSnapError, OSError, socket.timeout) as exc:
                    confirmation_error = exc
                    LOGGER.warning(
                        "Confirmacao da transferencia do serial %s falhou: %s",
                        wire_serial,
                        exc,
                    )

            self._serial_owner_cache.pop(requested_serial, None)
            self._serial_owner_cache.pop(wire_serial, None)
            if final_state and (
                not final_state["source_has_serial"]
                and final_state["target_has_serial"]
            ):
                LOGGER.warning(
                    "Transferencia do serial %s confirmada em %s",
                    wire_serial,
                    current_target["technician_name"],
                )
                return {
                    "ok": True,
                    "id_os": id_os,
                    "serial": wire_serial,
                    "requested_serial": requested_serial,
                    "source": current_source,
                    "target": current_target,
                    "equipment": {
                        "equipment_id": equipment_id,
                        "code": current_item["code"],
                        "name": current_item["equipment"],
                    },
                    "confirmed_after_error": write_error is not None,
                }

            detail = write_error or confirmation_error or (
                "o serial nao apareceu exclusivamente no estoque de destino"
            )
            raise SerializedTransferUncertainError(
                "O resultado da transferencia ficou incerto e ela nao sera "
                f"repetida automaticamente: {detail}"
            )

    @staticmethod
    def _encode_material_quantity(value: Decimal | str | int | float) -> bytes:
        try:
            quantity = Decimal(str(value).replace(",", ".")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Quantidade de material invalida") from exc
        if quantity <= 0:
            raise ValueError("A quantidade deve ser maior que zero")
        scaled = int(quantity * 100)
        digits = str(scaled)
        if len(digits) > 16:
            raise ValueError("A quantidade excede o limite do Imperium")
        digits = digits.zfill(16)
        packed = bytes(
            (int(digits[index]) << 4) | int(digits[index + 1])
            for index in range(0, 16, 2)
        )
        return bytes((16, 2)) + packed + (b"\x00" * 8)

    def _writeoff_material_row(
        self,
        context: DetailContext,
        material: dict,
        temporary_id: int,
        *,
        followed_by_row: bool = False,
    ) -> bytes:
        try:
            stock_id = int(material["stock_id"])
            equipment_id = int(material["equipment_id"])
            equipment = str(material["equipment"]).strip()
            unit = str(material["unit"]).strip()
            identified = str(material.get("identified", "N")).strip().upper()
            code = str(material["code"]).strip()
            business_unit_id = int(
                material.get("business_unit_id", self.material_business_unit_id)
            )
            quantity = material["quantity"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Material incompleto para a baixa") from exc
        if not all((stock_id > 0, equipment_id > 0, business_unit_id > 0)):
            raise ValueError("Identificadores do material invalidos")
        if identified != "N":
            raise ValueError(
                "A baixa rapida atual aceita somente materiais sem serial"
            )
        if not equipment or not code or not unit:
            raise ValueError("Dados do material incompletos")
        encoded_quantity = self._encode_material_quantity(quantity)
        if followed_by_row:
            encoded_quantity = (
                encoded_quantity[:-8] + b"\x10\x02" + b"\x00" * 6
            )
        row = b"".join(
            (
                self.material_row_prefix,
                struct.pack("<I", context.id_os),
                struct.pack("<I", equipment_id),
                struct.pack("<I", stock_id),
                struct.pack("<i", temporary_id),
                self._short_text(equipment),
                self._short_text(unit),
                self._short_text(identified),
                encoded_quantity,
                self._short_text(code),
                struct.pack("<I", business_unit_id),
                self._short_text("N"),
            )
        )
        return row + (b"\x00" * 4 if followed_by_row else b"")

    def _prepare_material_delta_record(self, record: bytes) -> bytes:
        modified = record
        for old, new, label in (
            (self.material_header_old, self.material_header_new, "cabecalho"),
            (
                self.material_quantity_old,
                self.material_quantity_new,
                "quantidade-base",
            ),
            (self.material_values_old, self.material_values_new, "valores"),
        ):
            position = modified.find(old)
            if position < 0:
                raise DataSnapError(
                    f"A estrutura de {label} da OS nao foi validada "
                    "para baixa de material"
                )
            modified = modified[:position] + new + modified[position + len(old) :]

        state_zip_pattern = re.compile(
            rb"(?P<state>\x02[A-Z]{2})\x00(?P<zip>\x08[0-9]{8})"
            rb"\x00\x00\x00\x00\x01"
        )
        matches = list(state_zip_pattern.finditer(modified[-180:]))
        if len(matches) != 1:
            raise DataSnapError(
                "A estrutura de endereco da OS nao foi validada para baixa de material"
            )
        tail_start = len(modified) - 180 if len(modified) >= 180 else 0
        state_start = tail_start + matches[0].start()

        district_start = None
        for candidate in range(max(0, state_start - 100), state_start):
            length = modified[candidate]
            if candidate + 1 + length != state_start or length > 80:
                continue
            try:
                value = modified[candidate + 1 : state_start].decode("cp1252")
            except UnicodeDecodeError:
                continue
            if value and all(character.isprintable() for character in value):
                district_start = candidate
        if (
            district_start is None
            or district_start == 0
            or modified[district_start - 1] != 0
        ):
            raise DataSnapError(
                "A estrutura de bairro da OS nao foi validada para baixa de material"
            )
        modified = (
            modified[: district_start - 1]
            + b"\x01"
            + modified[district_start - 1 :]
        )

        matches = list(state_zip_pattern.finditer(modified[-190:]))
        if len(matches) != 1:
            raise DataSnapError(
                "A estrutura de CEP da OS nao foi validada para baixa de material"
            )
        tail_start = len(modified) - 190 if len(modified) >= 190 else 0
        match = matches[0]
        start = tail_start + match.start()
        end = tail_start + match.end()
        replacement = (
            match.group("state")
            + b"\x01\x00"
            + match.group("zip")
            + b"\x01\x00\x01\x00\x01\x00\x01\x00\x01"
        )
        return modified[:start] + replacement + modified[end:]

    def _build_material_apply_blob(
        self,
        detail: bytes,
        materials: list[dict],
    ) -> bytes:
        if not materials:
            raise ValueError("Selecione pelo menos um material")
        if len(materials) > 30:
            raise ValueError("O limite e de 30 materiais por OS")
        record, record_mask = self._detail_parts(detail)
        modified = self._prepare_material_delta_record(record)
        if not modified.endswith(b"\x00" * 8):
            raise DataSnapError(
                "A estrutura de materiais desta OS nao foi validada"
            )
        context = self._detail_context(detail)
        rows = [
            self._writeoff_material_row(
                context,
                material,
                -index,
                followed_by_row=index < len(materials),
            )
            for index, material in enumerate(materials, start=1)
        ]
        modified = (
            modified[:-8]
            + struct.pack("<I", len(rows))
            + b"".join(rows)
            + modified[-8:]
        )
        return self._packet_from_modified_record(
            modified,
            record_mask,
            self.material_close_suffix,
        )

    def _material_preflight_for(
        self,
        installer_id: int,
    ) -> tuple[bytes, bytes, bytes]:
        if installer_id <= 0 or installer_id > 1_000_000:
            raise ValueError("Instalador invalido")
        reset = bytearray(self.material_preflight_reset)
        query = bytearray(self.material_preflight_query)
        struct.pack_into(
            "<I",
            reset,
            self.material_preflight_reset_offset,
            installer_id,
        )
        struct.pack_into(
            "<I",
            query,
            self.material_preflight_query_offset,
            installer_id,
        )
        return bytes(reset), bytes(query), bytes(reset)

    def _run_material_preflight(
        self,
        client: DataSnapClient,
        installer_id: int,
    ) -> None:
        handle = self._handle(client, self.material_preflight_method)
        reset_before, query, reset_after = self._material_preflight_for(
            installer_id
        )
        for payload, label in (
            (reset_before, "abertura da baixa de miscelaneas"),
            (query, "materiais do instalador"),
            (reset_after, "fechamento da baixa de miscelaneas"),
        ):
            self._dataset_payload(client, handle, payload, label)

    def _correction_location(self) -> tuple[str, str, str]:
        company = self.company.upper()
        if "FORTALEZA" in company:
            return "FORTALEZA", "CE", "60000000"
        if "MOSSOR" in company:
            return "MOSSORO", "RN", "59600000"
        if "RECIFE" in company:
            return "RECIFE", "PE", "50000000"
        return "NATAL", "RN", "59000000"

    @staticmethod
    def _correction_identifiers(attempt: int = 0) -> tuple[str, str]:
        value = int(time.time() * 1000) + attempt
        os_number = str(900_000_000 + (value % 100_000_000))
        contract = str(80_000_000 + (value % 10_000_000))
        return os_number, contract

    def _create_correction_order(self, technician_name: str) -> Order:
        city, state, zip_code = self._correction_location()
        last_status = ""

        def locate_created(os_number: str) -> Order | None:
            for lookup_attempt in range(6):
                try:
                    orders = self.list_orders(dt.date.today())
                except (DataSnapError, OSError) as exc:
                    LOGGER.warning(
                        "OS de correcao %s: consulta de confirmacao %s/6 falhou: %s",
                        os_number,
                        lookup_attempt + 1,
                        exc,
                    )
                else:
                    found = next(
                        (order for order in orders if order.num_os == os_number),
                        None,
                    )
                    if found is not None:
                        return found
                time.sleep(1 + lookup_attempt)
            return None

        for identifier_attempt in range(3):
            os_number, contract = self._correction_identifiers(identifier_attempt)
            toa_order = TOAOrder(
                date=dt.date.today().strftime("%d/%m/%Y"),
                technician=technician_name,
                activity_status="AGENDADA",
                address="BAIXA DE ESTOQUE",
                address_complement="",
                district="ADMINISTRATIVO",
                zip_code=zip_code,
                time_window="VT - PRIORIDADE",
                city=city,
                state=state,
                contract=contract,
                work_order="",
                node="",
                os_number=os_number,
                point="",
                os_status="",
                os_type="CORRECAO ESTOQUE",
                close_code="",
                workzone_key="",
            )
            preview = TOAPreview(
                filename=f"baixa-rapida-{os_number}.csv",
                source_rows=1,
                orders=(toa_order,),
            )
            try:
                import_result = self.import_toa(preview)
            except (DataSnapError, OSError) as exc:
                LOGGER.warning(
                    "OS de correcao %s: resposta da criacao incompleta; confirmando por consulta",
                    os_number,
                )
                found = locate_created(os_number)
                if found is not None:
                    return found
                raise DataSnapError(
                    f"O servidor nao confirmou a criacao da OS {os_number}"
                ) from exc
            row = (import_result.get("orders") or [{}])[0]
            last_status = str(row.get("import_status", "")).strip()
            if not row.get("imported"):
                if "JA CADASTR" in normalize_text(last_status):
                    time.sleep(0.02)
                    continue
                raise DataSnapError(
                    "O Imperium nao criou a OS de correcao: "
                    + (last_status or "resultado nao informado")
                )
            found = locate_created(os_number)
            if found is not None:
                return found
            raise DataSnapError(
                f"A OS {os_number} foi criada, mas ainda nao apareceu na consulta"
            )
        raise DataSnapError(
            "Nao foi possivel gerar um numero unico para a OS de correcao"
            + (f": {last_status}" if last_status else "")
        )

    def _material_was_applied(
        self,
        order: Order,
        detail: bytes,
        materials: list[dict],
    ) -> bool:
        if not (
            order.num_os.encode("ascii") in detail
            and self.material_close_code.encode("ascii") in detail
            and self.material_close_description.encode("cp1252") in detail
        ):
            return False
        return all(
            str(material["code"]).encode("ascii") in detail
            for material in materials
        )

    def _apply_materials(
        self,
        order: Order,
        technician: dict,
        materials: list[dict],
    ) -> dict:
        apply_error: Exception | None = None
        with self._client(timeout=12.0) as client:
            detail = self._fetch_detail_on(client, order.id_os)
            context = self._detail_context(detail)
            expected_name = str(technician.get("technician_name", "")).strip()
            if order.num_os.encode("ascii") not in detail:
                raise DataSnapError("O servidor devolveu outra OS")
            actual_normalized = normalize_text(context.installer_name)
            expected_normalized = normalize_text(expected_name)
            names_match = (
                not expected_normalized
                or actual_normalized == expected_normalized
                or actual_normalized in expected_normalized
                or expected_normalized in actual_normalized
            )
            if not names_match:
                raise DataSnapError(
                    "A OS de correcao foi vinculada a outro tecnico; "
                    "nenhuma baixa foi enviada"
                )
            if len(materials) > 1:
                LOGGER.info(
                    "OS %s: preparando baixa conjunta de %s materiais para "
                    "IdInstalador %s",
                    order.num_os,
                    len(materials),
                    context.installer_id,
                )
                self._run_material_preflight(client, context.installer_id)
            packet = self._build_material_apply_blob(detail, materials)
            handle = self._handle(client, "TDtmOrdemServico.AS_ApplyUpdates")
            try:
                client.set_timeout(20.0)
                client.request("execute", [{"handle": [handle]}, packet])
            except (DataSnapError, OSError, socket.timeout) as exc:
                apply_error = exc
                LOGGER.warning(
                    "OS %s: servidor nao confirmou imediatamente a baixa "
                    "de material: %s",
                    order.num_os,
                    exc,
                )

        confirmation_error: Exception | None = None
        for attempt, delay in enumerate((0, 1, 2, 4, 7), start=1):
            if delay:
                time.sleep(delay)
            try:
                detail = self._fetch_detail(order.id_os, timeout=10.0)
                if self._material_was_applied(order, detail, materials):
                    return {
                        "ok": True,
                        "apply_confirmed": True,
                        "apply_after_timeout": apply_error is not None,
                    }
            except (DataSnapError, OSError, socket.timeout) as exc:
                confirmation_error = exc
                LOGGER.warning(
                    "OS %s: confirmacao da baixa de material %s/5 falhou: %s",
                    order.num_os,
                    attempt,
                    exc,
                )
        cause = apply_error or confirmation_error
        error = DataSnapError(
            f"A OS {order.num_os} foi criada, mas o servidor nao confirmou "
            "a baixa do material"
        )
        if cause is not None:
            raise error from cause
        raise error

    def _append_material_audit(
        self,
        order: Order,
        technician: dict,
        materials: list[dict],
        result: str,
        detail: str = "",
    ) -> None:
        self.log_root.mkdir(parents=True, exist_ok=True)
        path = self.log_root / f"baixas-materiais-{dt.date.today():%Y%m%d}.csv"
        new_file = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            if new_file:
                writer.writerow(
                    [
                        "DataHora",
                        "IdOS",
                        "NumOS",
                        "Tecnico",
                        "IdEstoque",
                        "Codigo",
                        "Material",
                        "Quantidade",
                        "Resultado",
                        "Detalhe",
                    ]
                )
            for material in materials:
                writer.writerow(
                    [
                        dt.datetime.now().isoformat(timespec="seconds"),
                        order.id_os,
                        order.num_os,
                        technician.get("technician_name", ""),
                        technician.get("stock_id", ""),
                        material.get("code", ""),
                        material.get("equipment", ""),
                        material.get("quantity", ""),
                        result,
                        detail,
                    ]
                )

    def _confirm_material_stock_decrease(
        self,
        stock_id: int,
        materials: list[dict],
    ) -> tuple[bool, dict | None]:
        refreshed = None
        for delay in (0, 1, 2, 4):
            if delay:
                time.sleep(delay)
            try:
                refreshed = self.technician_stock(stock_id)
                refreshed_by_id = {
                    int(item["equipment_id"]): item
                    for item in refreshed.get("items", [])
                }
                confirmed = all(
                    Decimal(
                        str(
                            refreshed_by_id.get(
                                int(material["equipment_id"]), {}
                            ).get("quantity", "0")
                        )
                    )
                    <= Decimal(material["quantity_before"])
                    - Decimal(material["quantity"])
                    for material in materials
                )
                if confirmed:
                    return True, refreshed
            except (DataSnapError, OSError, InvalidOperation):
                refreshed = None
        return False, refreshed

    def quick_material_writeoff(
        self,
        stock_id: int,
        requested_materials: list[dict],
    ) -> dict:
        if stock_id <= 0:
            raise ValueError("Estoque invalido")
        if not isinstance(requested_materials, list) or not requested_materials:
            raise ValueError("Selecione pelo menos um material")
        if len(requested_materials) > 30:
            raise ValueError("O limite e de 30 materiais por OS")

        with self._operation_lock:
            stock = self.technician_stock(stock_id)
            technician = stock["technician"]
            by_id = {
                int(item["equipment_id"]): item
                for item in stock.get("items", [])
            }
            materials: list[dict] = []
            seen: set[int] = set()
            for requested in requested_materials:
                if not isinstance(requested, dict):
                    raise ValueError("Material invalido")
                try:
                    equipment_id = int(requested.get("equipment_id", 0))
                    quantity = Decimal(
                        str(requested.get("quantity", "")).replace(",", ".")
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                except (ValueError, InvalidOperation) as exc:
                    raise ValueError("Quantidade de material invalida") from exc
                if equipment_id in seen:
                    raise ValueError(
                        "O mesmo material foi selecionado mais de uma vez"
                    )
                seen.add(equipment_id)
                item = by_id.get(equipment_id)
                if item is None:
                    raise ValueError(
                        f"O material {equipment_id} nao pertence ao estoque selecionado"
                    )
                if (
                    str(item.get("identified", "")).upper() != "N"
                    or item.get("serials")
                ):
                    raise ValueError(
                        f"{item.get('equipment', 'Material')}: use a baixa por serial"
                    )
                available = Decimal(str(item.get("quantity", "0")))
                if quantity <= 0:
                    raise ValueError("A quantidade deve ser maior que zero")
                if quantity > available:
                    raise ValueError(
                        f"Saldo insuficiente de {item.get('equipment')}: "
                        f"disponivel {available}, solicitado {quantity}"
                    )
                materials.append(
                    {
                        **item,
                        "stock_id": stock_id,
                        "quantity": self._decimal_text(quantity),
                        "business_unit_id": self.material_business_unit_id,
                        "quantity_before": self._decimal_text(available),
                    }
                )

            order = self._create_correction_order(
                str(technician.get("technician_name", "")).strip()
            )
            refreshed = None
            confirmation_detail = ""
            try:
                apply_result = self._apply_materials(order, technician, materials)
            except Exception as exc:
                stock_confirmed, refreshed = self._confirm_material_stock_decrease(
                    stock_id, materials
                )
                if not stock_confirmed:
                    self._append_material_audit(
                        order, technician, materials, "FALHA", str(exc)
                    )
                    raise
                confirmation_detail = str(exc)
                apply_result = {
                    "ok": True,
                    "apply_confirmed": False,
                    "apply_after_timeout": True,
                }
            else:
                stock_confirmed, refreshed = self._confirm_material_stock_decrease(
                    stock_id, materials
                )

            result_materials = []
            refreshed_by_id = {
                int(item["equipment_id"]): item
                for item in (refreshed or {}).get("items", [])
            }
            for material in materials:
                current = refreshed_by_id.get(int(material["equipment_id"]), {})
                result_materials.append(
                    {
                        "equipment_id": material["equipment_id"],
                        "code": material["code"],
                        "equipment": material["equipment"],
                        "unit": material["unit"],
                        "quantity": material["quantity"],
                        "quantity_before": material["quantity_before"],
                        "quantity_after": current.get("quantity"),
                    }
                )
            audit_result = (
                "SUCESSO" if stock_confirmed else "SUCESSO_OS_CONFIRMADA"
            )
            self._append_material_audit(
                order,
                technician,
                materials,
                audit_result,
                confirmation_detail,
            )
            return {
                "ok": True,
                "id_os": order.id_os,
                "num_os": order.num_os,
                "contract": order.contract,
                "code": self.material_close_code,
                "description": self.material_close_description,
                "technician": technician,
                "materials": result_materials,
                "stock_confirmed": stock_confirmed,
                **apply_result,
            }

    def _detail_query(self, id_os: int) -> bytes:
        old_id = struct.pack("<I", self.detail_template_id)
        if self.detail_query_template.count(old_id) != 1:
            raise DataSnapError("The detail query identifier is invalid")
        return self.detail_query_template.replace(old_id, struct.pack("<I", id_os))

    def _fetch_detail_on(self, client: DataSnapClient, id_os: int) -> bytes:
        handle = self._handle(client, "TDtmOrdemServico.AS_GetRecords")
        response = client.request(
            "execute", [{"handle": [handle]}, self._detail_query(id_os)]
        )
        try:
            return response["result"][1]["data"][1]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError("The order detail query returned no dataset") from exc

    def _fetch_detail(self, id_os: int, timeout: float = 7.0) -> bytes:
        with self._client(timeout=timeout) as client:
            return self._fetch_detail_on(client, id_os)

    @staticmethod
    def _detail_parts(detail: bytes) -> tuple[bytes, bytes]:
        if len(detail) < 64 or detail[:4] != b"\xc0\xc0\x61\x01":
            raise DataSnapError("The order detail packet is invalid")
        packet = detail[15:]
        metadata_length = struct.unpack_from("<H", packet, 0x22)[0]
        record_start = 0x22 + metadata_length
        if record_start < 19 or record_start >= len(packet):
            raise DataSnapError("The order detail record is missing")
        return packet[record_start:], packet[record_start - 19 : record_start]

    @staticmethod
    def _detail_record(detail: bytes) -> bytes:
        return ImperiumAPI._detail_parts(detail)[0]

    @staticmethod
    def _read_short_text(data: bytes, position: int) -> tuple[str, int]:
        if position >= len(data):
            raise DataSnapError("The order detail text is incomplete")
        length = data[position]
        position += 1
        end = position + length
        if end > len(data):
            raise DataSnapError("The order detail text is incomplete")
        try:
            return data[position:end].decode("cp1252"), end
        except UnicodeDecodeError as exc:
            raise DataSnapError("The order detail text is invalid") from exc

    @staticmethod
    def _short_text(value: str) -> bytes:
        try:
            encoded = value.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise ValueError(f"Texto nao suportado pelo Imperium: {value}") from exc
        if len(encoded) > 255:
            raise ValueError("Texto excede o limite do Imperium")
        return bytes([len(encoded)]) + encoded

    @staticmethod
    def _looks_like_installer_name(value: str) -> bool:
        if not value or not value.isprintable():
            return False
        normalized = normalize_text(value)
        letters = sum(character.isalpha() for character in normalized)
        return letters >= 3 and all(
            character.isalpha() or character in " .'-"
            for character in normalized
        )

    @classmethod
    def _installer_context_from_record(
        cls,
        record: bytes,
        position: int,
    ) -> tuple[int, str]:
        if position + 4 > len(record):
            raise DataSnapError("The order installer is missing")

        installer_id = struct.unpack_from("<I", record, position)[0]
        installer_name, _ = cls._read_short_text(record, position + 4)
        if installer_id > 0 and cls._looks_like_installer_name(installer_name):
            return installer_id, installer_name

        # OS already closed include close-code fields before the installer.
        # Older packets do not, so keep the original fixed-position read above
        # and only recover when it clearly yielded a code such as "409".
        search_end = min(len(record), position + 256)
        for text_position in range(position + 4, search_end):
            candidate_id_position = text_position - 4
            if candidate_id_position < position:
                continue
            candidate_id = struct.unpack_from(
                "<I", record, candidate_id_position
            )[0]
            if not 1_000 <= candidate_id <= 10_000_000:
                continue
            try:
                candidate_name, _ = cls._read_short_text(record, text_position)
            except DataSnapError:
                continue
            if cls._looks_like_installer_name(candidate_name):
                return candidate_id, candidate_name

        raise DataSnapError("The order equipment context is invalid")

    @classmethod
    def _detail_context(cls, detail: bytes) -> DetailContext:
        record = cls._detail_record(detail)
        if len(record) < 32:
            raise DataSnapError("The order detail record is incomplete")
        position = 0
        id_os = struct.unpack_from("<I", record, position)[0]
        position += 4
        _, position = cls._read_short_text(record, position)  # NumOs
        contract, position = cls._read_short_text(record, position)
        position += 4  # IdServico
        _, position = cls._read_short_text(record, position)  # CodigoServico
        _, position = cls._read_short_text(record, position)  # Servico
        position += 4  # IdTurnoInstalacao
        _, position = cls._read_short_text(record, position)  # Turno
        position += 8  # HoraIni, HoraFim
        installer_id, installer_name = cls._installer_context_from_record(
            record,
            position,
        )
        if not contract.isdigit() or installer_id <= 0 or not installer_name:
            raise DataSnapError("The order equipment context is invalid")
        return DetailContext(
            id_os=id_os,
            contract=contract,
            installer_id=installer_id,
            installer_name=installer_name,
        )

    def _installed_lookup_query(
        self,
        serial: str,
        contract: str,
        installer_id: int,
    ) -> bytes:
        if not re.fullmatch(r"[A-Z0-9]{4,25}", serial):
            raise ValueError(
                "O serial instalado deve ter de 4 a 25 letras ou numeros"
            )
        if not re.fullmatch(r"\d{7,12}", contract):
            raise ValueError(
                "A consulta de equipamento requer um contrato de 7 a 12 digitos"
            )
        serial_marker = self.installed_lookup_serial_marker.encode("utf-16le")
        contract_marker = self.installed_lookup_contract_marker.encode("utf-16le")
        query = bytearray(self.installed_lookup_template)
        serial_offset = self.installed_lookup_serial_offset
        serial_length_offset = self.installed_lookup_serial_length_offset
        query_length_offset = self.installed_lookup_query_length_offset
        contract_offset = self.installed_lookup_contract_offset
        installer_offset = self.installed_lookup_installer_offset
        if (
            query[serial_offset : serial_offset + len(serial_marker)]
            != serial_marker
            or serial_length_offset + 4 > len(query)
            or struct.unpack_from("<I", query, serial_length_offset)[0]
            != len(self.installed_lookup_serial_marker)
            or query_length_offset >= len(query)
            or query[contract_offset : contract_offset + len(contract_marker)]
            != contract_marker
            or installer_offset + 4 > len(query)
        ):
            raise DataSnapError("The equipment lookup markers are invalid")
        encoded_serial = serial.encode("utf-16le")
        encoded_contract = contract.encode("utf-16le")
        serial_delta = len(encoded_serial) - len(serial_marker)
        contract_delta = len(encoded_contract) - len(contract_marker)
        adjusted_query_length = (
            query[query_length_offset] + serial_delta + contract_delta
        )
        if not 0 <= adjusted_query_length <= 0xFF:
            raise DataSnapError("The equipment lookup length is invalid")
        query[query_length_offset] = adjusted_query_length
        struct.pack_into("<I", query, serial_length_offset, len(serial))
        query[serial_offset : serial_offset + len(serial_marker)] = encoded_serial
        contract_offset += serial_delta
        installer_offset += serial_delta
        contract_length_offset = contract_offset - 4
        if (
            contract_length_offset < 0
            or struct.unpack_from("<I", query, contract_length_offset)[0]
            != len(self.installed_lookup_contract_marker)
        ):
            raise DataSnapError("The equipment contract length marker is invalid")
        struct.pack_into("<I", query, contract_length_offset, len(contract))
        query[contract_offset : contract_offset + len(contract_marker)] = encoded_contract
        if installer_offset + 4 > len(query):
            raise DataSnapError("The equipment installer marker is invalid")
        struct.pack_into("<I", query, installer_offset, installer_id)
        return bytes(query)

    @classmethod
    def _parse_installed_equipment(
        cls,
        payload: bytes,
        serial: str,
    ) -> Equipment:
        serial_bytes = serial.encode("ascii")
        for match in re.finditer(rb"([\x04-\x0c])(\d{4,12})", payload):
            if match.group(1)[0] != len(match.group(2)):
                continue
            code = match.group(2).decode("ascii")
            if match.start() < 4 or match.end() >= len(payload):
                continue
            id_equipment = struct.unpack_from("<I", payload, match.start() - 4)[0]
            position = match.end()
            try:
                name, position = cls._read_short_text(payload, position)
                id_brand = struct.unpack_from("<I", payload, position)[0]
                position += 4
                brand, position = cls._read_short_text(payload, position)
                id_unit = struct.unpack_from("<I", payload, position)[0]
                position += 4
                unit, position = cls._read_short_text(payload, position)
            except (DataSnapError, struct.error):
                continue
            serial_position = payload.find(serial_bytes, position)
            if serial_position < 0:
                continue
            serial_match = next(
                (
                    candidate
                    for candidate in re.finditer(rb"[A-Z0-9]{4,25}", payload)
                    if candidate.start() <= serial_position
                    and candidate.end() >= serial_position + len(serial_bytes)
                ),
                None,
            )
            if serial_match is None:
                continue
            resolved_serial = serial_match.group(0).decode("ascii")
            identified_position = payload.rfind(
                b"\x01S",
                position,
                serial_position,
            )
            if identified_position < 0 or identified_position + 6 > len(payload):
                continue
            id_stock = struct.unpack_from(
                "<I", payload, identified_position + 2
            )[0]
            id_group = struct.unpack_from("<I", payload, len(payload) - 4)[0]
            if not all(
                (
                    id_equipment > 0,
                    id_stock > 0,
                    id_brand > 0,
                    id_unit > 0,
                    id_group > 0,
                    bool(name),
                    bool(brand),
                    bool(unit),
                )
            ):
                continue
            return Equipment(
                id_equipment=id_equipment,
                code=code,
                name=name,
                identified="S",
                id_brand=id_brand,
                brand=brand,
                id_unit=id_unit,
                unit=unit,
                serial=resolved_serial,
                id_stock=id_stock,
                id_group=id_group,
            )
        raise DataSnapError(
            "O serial instalado nao foi localizado no estoque do instalador"
        )

    def _lookup_installed_equipment(
        self,
        client: DataSnapClient,
        context: DetailContext,
        serial: str,
    ) -> Equipment:
        handle = self._handle(client, self.installed_lookup_method)
        response = client.request(
            "execute",
            [
                {"handle": [handle]},
                self._installed_lookup_query(
                    serial,
                    context.contract,
                    context.installer_id,
                ),
            ],
        )
        try:
            payload = response["result"][1]["data"][1]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError(
                "A consulta do serial instalado nao retornou equipamento"
            ) from exc
        try:
            return self._parse_installed_equipment(payload, serial)
        except DataSnapError as exc:
            if "nao foi localizado no estoque" not in str(exc):
                raise
            raise DataSnapError(
                f"O serial {serial} nao foi localizado no estoque de "
                f"{context.installer_name}; se estiver em outro tecnico, "
                "transfira antes da baixa 409/706"
            ) from exc

    @staticmethod
    def _equipment_matches_type(equipment: Equipment, equipment_type: str) -> bool:
        if equipment_type == "auto":
            return True
        name = normalize_text(equipment.name)
        aliases = {
            "decoder": ("DECODER", "SET TOP BOX", "STB"),
            "emta": (
                "EMTA",
                "MODEM",
                "TERMINAL DOCSIS",
                "TERMINAL GPON",
                "ONT",
                "ONU",
            ),
            "smart": ("SMART CARD",),
            "chip": ("CHIP", "SIM CARD", "SIMCARD", "SC BOPP"),
        }
        return any(alias in name for alias in aliases.get(equipment_type, ()))

    @staticmethod
    def _adjust_query_length(
        query: bytes,
        original_length: int,
        page_offset: int,
        length_offset: int,
    ) -> bytes:
        if page_offset >= len(query) or length_offset + 2 > len(query):
            raise DataSnapError("The DataSnap query length marker is invalid")
        delta = len(query) - original_length
        output = bytearray(query)
        captured_dynamic = struct.unpack_from("<H", output, length_offset)[0]
        dynamic_length = captured_dynamic + delta
        page_delta = dynamic_length // 256 - captured_dynamic // 256
        encoded_dynamic = dynamic_length - page_delta * 256
        encoded_page = output[page_offset] + page_delta
        if (
            dynamic_length < 0
            or encoded_dynamic < 0
            or encoded_dynamic > 0xFFFF
            or encoded_page < 0
            or encoded_page > 0xFF
        ):
            raise DataSnapError("The DataSnap query dynamic length is invalid")
        output[page_offset] = encoded_page
        struct.pack_into("<H", output, length_offset, encoded_dynamic)
        return bytes(output)

    @staticmethod
    def _replace_utf16_value(query: bytes, old: str, new: str) -> bytes:
        old_bytes = old.encode("utf-16le")
        new_bytes = new.encode("utf-16le")
        if query.count(old_bytes) != 1:
            raise DataSnapError("The DataSnap text parameter marker is invalid")
        position = query.index(old_bytes)
        if position < 4 or struct.unpack_from("<I", query, position - 4)[0] != len(old):
            raise DataSnapError("The DataSnap text parameter length is invalid")
        return b"".join(
            (
                query[: position - 4],
                struct.pack("<I", len(new)),
                new_bytes,
                query[position + len(old_bytes) :],
            )
        )

    @classmethod
    def _replace_utf16_parameter(
        cls,
        query: bytes,
        name: str,
        new: str,
    ) -> bytes:
        marker = name.encode("utf-16le")
        if query.count(marker) != 1:
            raise DataSnapError(f"The DataSnap parameter {name} is invalid")
        marker_end = query.index(marker) + len(marker)
        type_position = query.find(bytes.fromhex("08000000"), marker_end, marker_end + 24)
        if type_position < 0 or type_position + 8 > len(query):
            raise DataSnapError(f"The DataSnap parameter {name} has no text value")
        value_length = struct.unpack_from("<I", query, type_position + 4)[0]
        value_start = type_position + 8
        value_end = value_start + value_length * 2
        if value_end > len(query):
            raise DataSnapError(f"The DataSnap parameter {name} is incomplete")
        return b"".join(
            (
                query[: type_position + 4],
                struct.pack("<I", len(new)),
                new.encode("utf-16le"),
                query[value_end:],
            )
        )

    @staticmethod
    def _replace_integer_parameter(query: bytes, name: str, value: int) -> bytes:
        marker = name.encode("utf-16le")
        if query.count(marker) != 1:
            raise DataSnapError(f"The DataSnap parameter {name} is invalid")
        marker_end = query.index(marker) + len(marker)
        type_position = query.find(bytes.fromhex("03000000"), marker_end, marker_end + 24)
        if type_position < 0 or type_position + 8 > len(query):
            raise DataSnapError(f"The DataSnap parameter {name} has no integer value")
        output = bytearray(query)
        struct.pack_into("<I", output, type_position + 4, value)
        return bytes(output)

    def _material_catalog_query(self, installer_id: int) -> bytes:
        query = self._replace_utf16_value(
            self.material_catalog_template,
            self.material_catalog_installer_marker,
            str(installer_id),
        )
        return self._adjust_query_length(
            query,
            len(self.material_catalog_template),
            self.material_catalog_page_offset,
            self.material_catalog_length_offset,
        )

    def _toa_material_lookup_query(
        self,
        installer_id: int,
        description: str,
    ) -> bytes:
        query = self._replace_utf16_parameter(
            self.toa_material_lookup_template,
            "@IdInst",
            str(installer_id),
        )
        query = self._replace_utf16_parameter(
            query,
            "@DescEquip",
            description,
        )
        return self._adjust_query_length(
            query,
            len(self.toa_material_lookup_template),
            self.toa_material_lookup_page_offset,
            self.toa_material_lookup_length_offset,
        )

    @staticmethod
    def _decimal_integer(value: bytes) -> int:
        if len(value) != 18 or any(value[8:]):
            raise DataSnapError("The material stock quantity is invalid")
        return int.from_bytes(value[2:8], "big")

    @classmethod
    def _parse_material_catalog(cls, payload: bytes) -> list[StockMaterial]:
        if not isinstance(payload, (bytes, bytearray)):
            return []
        materials: list[StockMaterial] = []
        seen: set[str] = set()
        for match in re.finditer(rb"\x08(\d{8})", payload):
            if match.start() < 4:
                continue
            code = match.group(1).decode("ascii")
            if code in seen:
                continue
            id_equipment = struct.unpack_from("<I", payload, match.start() - 4)[0]
            try:
                name, position = cls._read_short_text(payload, match.end())
                quantity_end = position + 18
                stock_quantity = cls._decimal_integer(payload[position:quantity_end])
                id_stock = struct.unpack_from("<I", payload, quantity_end)[0]
                unit, position = cls._read_short_text(payload, quantity_end + 4)
                id_unit = struct.unpack_from("<I", payload, position)[0]
                identified, _ = cls._read_short_text(payload, position + 4)
            except (DataSnapError, struct.error):
                continue
            if not all((id_equipment > 0, id_stock > 0, id_unit > 0, name, unit)):
                continue
            material = StockMaterial(
                id_equipment=id_equipment,
                code=code,
                name=name,
                stock_quantity=stock_quantity,
                id_stock=id_stock,
                unit=unit,
                id_unit=id_unit,
                identified=identified or "N",
            )
            materials.append(material)
            seen.add(code)
        if not materials and payload[:3] != b"\xc0\xc0\x60":
            raise DataSnapError("O estoque do instalador retornou dados invalidos")
        return materials

    def _material_catalog_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
    ) -> list[StockMaterial]:
        handle = self._handle(client, self.material_stock_method)
        query = self._material_catalog_query(context.installer_id)
        response = client.request(
            "execute",
            [{"handle": [handle]}, query],
        )
        client.request(
            "execute",
            [{"handle": [handle]}, self._provider_close_query(query)],
        )
        try:
            payload = response["result"][1]["data"][1]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError("A consulta do estoque nao retornou materiais") from exc
        return self._parse_material_catalog(payload)

    def _stock_inventory_material_catalog_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
    ) -> list[StockMaterial]:
        """Read the complete inventory used by the manual material picker."""
        technician_handle = self._handle(
            client,
            self.stock_protocol.technicians_method,
        )
        technician_payload = self._dataset_payload(
            client,
            technician_handle,
            self.stock_protocol.technicians_query,
            "estoques para baixa manual de miscelaneas",
        )
        technicians = parse_technicians(technician_payload)
        technician = next(
            (
                item
                for item in technicians
                if item.installer_id == context.installer_id
            ),
            None,
        )
        if technician is None:
            wanted_name = normalize_text(context.installer_name)
            technician = next(
                (
                    item
                    for item in technicians
                    if normalize_text(item.technician_name) == wanted_name
                    or normalize_text(item.stock_name) == wanted_name
                ),
                None,
            )
        if technician is None:
            raise DataSnapError(
                f"O estoque completo de {context.installer_name} nao foi localizado"
            )

        item_handle = self._handle(client, self.stock_protocol.items_method)
        item_payload = self._dataset_payload(
            client,
            item_handle,
            self.stock_protocol.items_query(technician.stock_id),
            f"baixa manual de miscelaneas de {technician.technician_name}",
        )
        materials: list[StockMaterial] = []
        for item in parse_stock_items(item_payload):
            if item.identified != "N" or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]*",
                item.code,
            ):
                continue
            materials.append(
                StockMaterial(
                    id_equipment=item.equipment_id,
                    code=item.code,
                    name=item.equipment,
                    stock_quantity=max(int(item.quantity_number), 0),
                    id_stock=technician.stock_id,
                    unit=item.unit,
                    id_unit=item.unit_id,
                    identified=item.identified,
                )
            )
        return materials

    def _manual_material_picker_query(self, installer_id: int) -> bytes:
        query = self._replace_integer_parameter(
            self.manual_material_picker_template,
            self.manual_material_installer_parameter,
            installer_id,
        )
        return self._replace_integer_parameter(
            query,
            self.manual_material_contract_parameter,
            self.manual_material_contract_id,
        )

    def _manual_material_picker_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
    ) -> list[ManualMaterial]:
        """Query the exact dataset behind Imperium's Adicionar Miscelaneas."""
        handle = self._handle(client, self.material_stock_method)
        query = self._manual_material_picker_query(context.installer_id)
        response = client.request(
            "execute",
            [{"handle": [handle]}, query],
        )
        client.request(
            "execute",
            [{"handle": [handle]}, self._provider_close_query(query)],
        )
        try:
            payload = response["result"][1]["data"][1]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError(
                "A baixa manual nao retornou o catalogo de miscelaneas"
            ) from exc
        return parse_manual_material_catalog(payload)

    def _reconcile_manual_materials(
        self,
        stock_materials: list[StockMaterial],
        picker_materials: list[ManualMaterial],
    ) -> list[StockMaterial]:
        """Trust only the balance from the official integration business unit."""
        materials = {item.code: item for item in stock_materials}
        unit_ids = {
            normalize_text(item.unit): item.id_unit
            for item in stock_materials
            if item.id_unit > 0
        }
        pickers_by_code: dict[str, list[ManualMaterial]] = {}
        for picker in picker_materials:
            pickers_by_code.setdefault(picker.code, []).append(picker)

        for candidates in pickers_by_code.values():
            preferred = [
                picker
                for picker in candidates
                if picker.business_unit_id == self.material_business_unit_id
            ]
            picker = preferred[0] if preferred else candidates[0]
            current = materials.get(picker.code)
            id_unit = current.id_unit if current else unit_ids.get(normalize_text(picker.unit))
            if not id_unit or picker.quantity != picker.quantity.to_integral_value():
                continue
            stock_quantity = (
                int(picker.quantity)
                if picker.business_unit_id == self.material_business_unit_id
                else 0
            )
            materials[picker.code] = StockMaterial(
                id_equipment=picker.equipment_id,
                code=picker.code,
                name=picker.name,
                stock_quantity=stock_quantity,
                id_stock=picker.stock_id,
                unit=picker.unit,
                id_unit=id_unit,
                identified=picker.identified,
                requested_quantity=(current.requested_quantity if current else 0),
                id_group=picker.group_id,
                group=picker.group,
                business_unit_id=self.material_business_unit_id,
            )
        return sorted(materials.values(), key=lambda item: (item.code, item.name))

    def _manual_material_catalog_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
    ) -> list[StockMaterial]:
        stock_materials = self._stock_inventory_material_catalog_on(client, context)
        try:
            picker_materials = self._manual_material_picker_on(client, context)
        except (DataSnapError, OSError) as exc:
            LOGGER.warning(
                "IdOS %s: catalogo direto da baixa manual indisponivel; "
                "usando estoque consolidado: %s",
                context.id_os,
                exc,
            )
            return stock_materials
        return self._reconcile_manual_materials(stock_materials, picker_materials)

    def _combined_material_catalog_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
    ) -> list[StockMaterial]:
        primary_error: DataSnapError | OSError | None = None
        try:
            order_materials = self._material_catalog_on(client, context)
        except (DataSnapError, OSError) as exc:
            primary_error = exc
            materials: dict[str, StockMaterial] = {}
            LOGGER.warning(
                "IdOS %s: catalogo da OS indisponivel; tentando estoque completo: %s",
                context.id_os,
                exc,
            )
        else:
            materials = {item.code: item for item in order_materials}

        try:
            manual_materials = self._manual_material_catalog_on(client, context)
        except (DataSnapError, OSError) as exc:
            if primary_error is not None:
                raise DataSnapError(
                    "O catalogo da OS veio invalido e o estoque completo tambem "
                    f"nao pode ser consultado: {exc}"
                ) from exc
            LOGGER.warning(
                "IdOS %s: estoque da baixa manual indisponivel; usando catalogo "
                "da OS: %s",
                context.id_os,
                exc,
            )
        else:
            # This is the same source shown by Imperium's "Baixar Miscelaneas"
            # dialog, so its IDs and balances are authoritative for the delta.
            materials.update({item.code: item for item in manual_materials})
        return sorted(materials.values(), key=lambda item: (item.code, item.name))

    @staticmethod
    def _toa_material_lookup_terms(code: str, description: str) -> tuple[str, ...]:
        value = " ".join(str(description or "").strip().split())
        prefix = re.compile(rf"^{re.escape(str(code))}[\s_-]+", re.IGNORECASE)
        while prefix.match(value):
            value = prefix.sub("", value, count=1).strip()
        terms: list[str] = []
        if value:
            terms.append(value)
            normalized = " ".join(
                part for part in re.split(r"[^A-Za-z0-9]+", value) if part
            )
            if normalized and normalized not in terms:
                terms.append(normalized)
        legacy = f"{code}_{value}" if value else ""
        if legacy and legacy not in terms:
            terms.append(legacy)
        return tuple(terms)

    def _lookup_material_by_code_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
        code: str,
        description: str,
        handle: int | None = None,
    ) -> StockMaterial | None:
        for term in self._toa_material_lookup_terms(code, description):
            matches = self._toa_material_lookup_on(
                client,
                context,
                term,
                handle,
            )
            material = next(
                (item for item in matches if item.code == code),
                None,
            )
            if material is not None:
                return material
        return None

    def _toa_material_lookup_on(
        self,
        client: DataSnapClient,
        context: DetailContext,
        description: str,
        handle: int | None = None,
    ) -> list[StockMaterial]:
        provider_handle = handle or self._handle(client, self.material_stock_method)
        query = self._toa_material_lookup_query(
            context.installer_id,
            description,
        )
        response = client.request(
            "execute",
            [{"handle": [provider_handle]}, query],
        )
        client.request(
            "execute",
            [{"handle": [provider_handle]}, self._provider_close_query(query)],
        )
        try:
            payload = response["result"][1]["data"][1]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError("A correlacao TOA nao retornou materiais") from exc
        return self._parse_material_catalog(payload)

    def resolve_toa_materials(self, id_os: int, values: list[dict]) -> dict:
        if not isinstance(values, list) or not values:
            raise ValueError("A colagem TOA nao possui miscelaneas")
        requested = []
        for value in values:
            if not isinstance(value, dict):
                raise ValueError("A miscelanea colada e invalida")
            code = str(value.get("code", "")).strip()
            description = str(value.get("description", "")).strip()
            point = str(value.get("point", "")).strip()
            try:
                quantity = int(value.get("quantity", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError("A quantidade colada e invalida") from exc
            if (
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", code)
                or not description
            ):
                raise ValueError("Codigo ou descricao TOA invalida")
            if quantity <= 0 or quantity > 0xFFFF:
                raise ValueError("A quantidade colada deve estar entre 1 e 65535")
            requested.append(
                {
                    "code": code,
                    "description": description,
                    "quantity": quantity,
                    "point": point,
                }
            )

        with self._operation_lock:
            with self._client(timeout=15.0) as client:
                detail = self._fetch_detail_on(client, id_os)
                context = self._detail_context(detail)
                local = {
                    material.code: material
                    for material in self._combined_material_catalog_on(
                        client,
                        context,
                    )
                }
                lookup_handle: int | None = None
                for item in requested:
                    if item["code"] not in local:
                        if lookup_handle is None:
                            lookup_handle = self._handle(
                                client,
                                self.material_stock_method,
                            )
                        material = self._lookup_material_by_code_on(
                            client,
                            context,
                            item["code"],
                            item["description"],
                            lookup_handle,
                        )
                        if material is not None:
                            local[material.code] = material
                resolution = resolve_material_requests(
                    requested,
                    [material.to_dict() for material in local.values()],
                )
                return_stock_error = ""
                if self.port == PORT:
                    try:
                        return_quantities = (
                            self._material_virtual_stock_quantities_on(client)
                        )
                    except (DataSnapError, OSError, socket.timeout) as exc:
                        return_quantities = {}
                        return_stock_error = str(exc)
                        LOGGER.warning(
                            "IdOS %s: estoque RETORNO indisponivel durante a "
                            "correlacao TOA: %s",
                            id_os,
                            exc,
                        )
                    self._attach_return_stock_preview(
                        resolution.get("materials", []),
                        return_quantities,
                    )
        return {
            "ok": True,
            "id_os": context.id_os,
            "installer": context.installer_name,
            "return_stock_name": (
                MATERIAL_REPLENISHMENT_STOCK_NAME if self.port == PORT else ""
            ),
            "return_stock_error": return_stock_error,
            **resolution,
        }

    def _attach_return_stock_preview(
        self,
        materials: list[dict],
        quantities: dict[str, Decimal],
    ) -> None:
        """Attach RETORNO balances to rows discovered after TOA correlation."""
        for material in materials:
            code = str(material.get("code") or "").strip()
            material["return_stock_name"] = MATERIAL_REPLENISHMENT_STOCK_NAME
            material["return_stock_quantity"] = self._decimal_text(
                quantities.get(code, Decimal("0"))
            )

    def list_material_inventory(
        self,
        id_os: int,
        *,
        installer_id: int | None = None,
    ) -> dict:
        return_quantities: dict[str, Decimal] = {}
        return_stock_error = ""
        with self._operation_lock:
            last_error: OSError | DataSnapError | None = None
            for attempt in range(1, 4):
                LOGGER.info(
                    "IdOS %s: consultando estoque, tentativa %s/3",
                    id_os,
                    attempt,
                )
                try:
                    with self._client(timeout=12.0) as client:
                        detail = self._fetch_detail_on(client, id_os)
                        context = self._detail_context(detail)
                        if installer_id is not None and int(installer_id) > 0:
                            context = DetailContext(
                                id_os=context.id_os,
                                contract=context.contract,
                                installer_id=int(installer_id),
                                installer_name=context.installer_name,
                            )
                        materials = self._combined_material_catalog_on(
                            client,
                            context,
                        )
                        if self.port == PORT:
                            try:
                                return_quantities = (
                                    self._material_virtual_stock_quantities_on(client)
                                )
                            except (DataSnapError, OSError, socket.timeout) as exc:
                                return_stock_error = str(exc)
                                LOGGER.warning(
                                    "IdOS %s: estoque RETORNO indisponivel na "
                                    "pre-visualizacao: %s",
                                    id_os,
                                    exc,
                                )
                    break
                except (OSError, DataSnapError) as exc:
                    last_error = exc
                    LOGGER.warning(
                        "IdOS %s: consulta de estoque falhou %s/3: %s",
                        id_os,
                        attempt,
                        exc,
                    )
                    if attempt < 3:
                        time.sleep(attempt)
            else:
                error = DataSnapError(
                    "Nao foi possivel consultar o estoque do instalador "
                    "apos 3 tentativas"
                )
                raise error from last_error
        serialized_materials = []
        for material in materials:
            value = material.to_dict()
            if self.port == PORT:
                value["return_stock_name"] = MATERIAL_REPLENISHMENT_STOCK_NAME
                value["return_stock_quantity"] = self._decimal_text(
                    return_quantities.get(material.code, Decimal("0"))
                )
            serialized_materials.append(value)
        return {
            "ok": True,
            "id_os": context.id_os,
            "installer": context.installer_name,
            "count": len(materials),
            "return_stock_name": (
                MATERIAL_REPLENISHMENT_STOCK_NAME if self.port == PORT else ""
            ),
            "return_stock_error": return_stock_error,
            "materials": serialized_materials,
        }

    @staticmethod
    def _build_dsploc_string_param(name: str, value: str) -> bytes:
        desc = (
            b"\x0c \x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x06\x00\x00\x00\x08\x00\x00\x00"
        )
        name_utf16 = name.encode("utf-16le")
        name_len = struct.pack("<I", len(name))
        val_type = b"\x08\x00\x00\x00"
        val_utf16 = value.encode("utf-16le")
        val_len = struct.pack("<I", len(value))
        trailer = (
            b"\x10\x00\x00\x00\x01\x10\x00\x00\x00\x01"
            b"\x03\x00\x00\x00\x00\x00\x00\x00"
            b"\x03\x00\x00\x00\x00\x00\x00\x00"
            b"\x03\x00\x00\x00\x00\x00\x00\x00"
        )
        return desc + name_len + name_utf16 + val_type + val_len + val_utf16 + trailer

    @classmethod
    def _build_dsploc_equipment_query(cls, code: str) -> bytes:
        pname = b"DspLoc"
        header = bytes([32 + len(pname)]) + pname + b"!\x01`a\x01"
        param_defs = [
            ("Equipamento", "%"),
            ("DESCRICAO", "%"),
            ("CodigoEquipamento", f"{code}%"),
            ("Contrato", "%"),
            ("Marca", "%"),
            ("GTIN", "%"),
            ("IDAUX", "%"),
            ("IDEQUIPAMENTO", "%"),
            ("STATUS", "%"),
        ]
        params_data = bytearray()
        for name, val in param_defs:
            params_data.extend(cls._build_dsploc_string_param(name, val))

        arr_header = (
            b"\x0c \x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
            + struct.pack("<I", len(param_defs) - 1)
        )
        body = arr_header + params_data + b"\x10\x00\x05\x02\x00\x00\x00\x00\xc0"
        dyn_len = len(body) - 8
        page = dyn_len // 256
        rem = dyn_len % 256
        len_bytes = b"\x20\x10" + bytes([page, rem, 0x02])
        return header + len_bytes + body

    @staticmethod
    def _parse_dsploc_equipment_record(
        payload: bytes,
        target_code: str,
    ) -> dict | None:
        target_code = str(target_code or "").strip()
        if not target_code or not isinstance(payload, (bytes, bytearray)):
            return None
        code_marker = bytes([len(target_code)]) + target_code.encode("ascii")
        for match in re.finditer(re.escape(code_marker), payload):
            pos = match.start()
            if pos < 4:
                continue
            id_equipment = struct.unpack_from("<I", payload, pos - 4)[0]
            cur = match.end()
            try:
                if cur >= len(payload):
                    continue
                eq_len = payload[cur]
                cur += 1
                equipment = payload[cur : cur + eq_len].decode("cp1252", errors="replace")
                cur += eq_len

                if cur + 2 > len(payload):
                    continue
                desc_len = struct.unpack_from("<H", payload, cur)[0]
                cur += 2
                descricao = payload[cur : cur + desc_len].decode("cp1252", errors="replace")
                cur += desc_len

                if cur + 4 > len(payload):
                    continue
                id_marca = struct.unpack_from("<I", payload, cur)[0]
                cur += 4

                if cur >= len(payload):
                    continue
                m_len = payload[cur]
                cur += 1
                marca = payload[cur : cur + m_len].decode("cp1252", errors="replace")
                cur += m_len

                if cur + 4 > len(payload):
                    continue
                id_unidade = struct.unpack_from("<I", payload, cur)[0]
                cur += 4

                if cur >= len(payload):
                    continue
                u_len = payload[cur]
                cur += 1
                unidade = payload[cur : cur + u_len].decode("cp1252", errors="replace")
                cur += u_len

                cur += 18  # valor BCD
                if cur + 4 > len(payload):
                    continue
                id_contrato = struct.unpack_from("<I", payload, cur)[0]
                cur += 4

                if cur >= len(payload):
                    continue
                c_len = payload[cur]
                cur += 1
                contrato = payload[cur : cur + c_len].decode("cp1252", errors="replace")
                cur += c_len

                if cur >= len(payload):
                    continue
                id_len = payload[cur]
                cur += 1
                identificado = payload[cur : cur + id_len].decode("cp1252", errors="replace")
                cur += id_len

                if cur >= len(payload):
                    continue
                n_len = payload[cur]
                cur += 1 + n_len

                if cur >= len(payload):
                    continue
                cst_len = payload[cur]
                cur += 1 + cst_len

                if cur >= len(payload):
                    continue
                g_len = payload[cur]
                cur += 1
                gtin = payload[cur : cur + g_len].decode("cp1252", errors="replace")
                cur += g_len


                if cur >= len(payload):
                    continue
                aux_len = payload[cur]
                cur += 1
                aux = payload[cur : cur + aux_len].decode("cp1252", errors="replace")
                cur += aux_len

                if cur >= len(payload):
                    continue
                st_len = payload[cur]
                cur += 1
                status_tail = payload[cur : cur + st_len].decode("cp1252", errors="replace")
                cur += st_len
                status = next(
                    (
                        value for value in (status_tail, aux, gtin)
                        if value.strip().upper() in {"ATIVO", "INATIVO"}
                    ),
                    status_tail,
                )
            except (struct.error, IndexError):
                continue

            if status and status.strip().upper() != "ATIVO":
                return None
            if identificado.strip().upper() != "N":
                return None

            items: list[dict[str, str]] = []
            equivalents: list[str] = []
            seen: set[str] = set()

            for part in descricao.split("|"):
                part = part.strip()
                if not part:
                    continue
                if "_" in part:
                    c, d = part.split("_", 1)
                else:
                    c, d = part, ""
                c = c.strip()
                d = d.strip()
                if (
                    c
                    and c not in seen
                    and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", c)
                ):
                    seen.add(c)
                    equivalents.append(c)
                    items.append({"code": c, "description": d})

            if target_code not in seen:
                equivalents.insert(0, target_code)
                items.insert(0, {"code": target_code, "description": equipment})

            words_list = [it["description"].split() for it in items if it["description"]]
            common: list[str] = []
            if words_list:
                for i, w in enumerate(words_list[0]):
                    if all(len(words) > i and words[i].upper() == w.upper() for words in words_list):
                        common.append(w)
                    else:
                        break
            group = " ".join(common) if common else (equipment.split()[0] if equipment.strip() else "")

            return {
                "requested_code": target_code,
                "group": group,
                "equivalents": equivalents,
                "id_equipment": id_equipment,
                "equipment": equipment,
                "unit": unidade,
                "id_unit": id_unidade,
                "status": status,
                "identificado": identificado,
                "items": items,
            }
        return None

    def lookup_equipment_group_by_code(self, code: str) -> dict | None:
        """Official equipment group and equivalents lookup via DspLoc."""
        code = str(code or "").strip()
        if not code or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", code):
            return None
        if code in self._equipment_group_cache:
            return self._equipment_group_cache[code]
        with self._operation_lock:
            with self._client(timeout=15.0) as client:
                result = self._lookup_equipment_group_by_code_on(client, code)
        self._equipment_group_cache[code] = result
        return result

    def _lookup_equipment_group_by_code_on(
        self,
        client: DataSnapClient,
        code: str,
    ) -> dict | None:
        code = str(code or "").strip()
        if not code or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", code):
            return None
        if code in self._equipment_group_cache:
            return self._equipment_group_cache[code]
        try:
            handle = self._handle(client, "TDtmEquipamentos.AS_GetRecords")
            query = self._build_dsploc_equipment_query(code)
            response = client.request(
                "execute",
                [{"handle": [handle]}, query],
            )
            client.request(
                "execute",
                [{"handle": [handle]}, self._provider_close_query(query)],
            )
            payload = response["result"][1]["data"][1]
            if not isinstance(payload, (bytes, bytearray)):
                return None
        except Exception as exc:
            LOGGER.warning(
                "Erro ao consultar grupo do equipamento %s no DspLoc: %s",
                code,
                exc,
            )
            return None
        result = self._parse_dsploc_equipment_record(payload, code)
        self._equipment_group_cache[code] = result
        return result

    def prepare_official_materials(
        self,
        order: Order,
        values: list[dict],
        *,
        expected_installer_id: int,
    ) -> dict:
        """Prepare technician stock before the single official HTTP close."""
        if not isinstance(values, list):
            raise ValueError("A lista de miscelaneas da integracao IMPERIUM e invalida")
        if len(values) > 300:
            raise ValueError("O limite tecnico e de 300 miscelaneas por baixa")
        try:
            expected_installer_id = int(expected_installer_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "O instalador esperado para preparar as miscelaneas e invalido"
            ) from exc
        if expected_installer_id <= 0:
            raise ValueError(
                "O instalador esperado para preparar as miscelaneas e invalido"
            )

        requested: list[dict] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, dict):
                raise ValueError(
                    "Cada miscelanea da integracao IMPERIUM deve informar codigo e quantidade"
                )
            code = str(value.get("code", "")).strip()
            description = str(value.get("description", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", code):
                raise ValueError(
                    f"O formato do codigo da miscelanea {code or '(vazio)'} "
                    "e invalido"
                )
            if code in seen:
                raise ValueError(f"A miscelanea {code} foi informada mais de uma vez")
            seen.add(code)
            raw_quantity = value.get("quantity", "")
            if isinstance(raw_quantity, bool):
                raise ValueError("A quantidade da miscelanea e invalida")
            try:
                quantity = Decimal(str(raw_quantity))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("A quantidade da miscelanea e invalida") from exc
            if (
                not quantity.is_finite()
                or quantity <= 0
                or quantity > Decimal(0xFFFF)
            ):
                raise ValueError(
                    "A quantidade da miscelanea deve ser maior que zero e "
                    "no maximo 65535"
                )
            requested.append(
                {
                    "code": code,
                    "description": description,
                    "quantity": quantity,
                }
            )

        if not requested:
            return {
                "prepared": True,
                "transferred": False,
                "source": "none",
                "installer_id": expected_installer_id,
                "installer_name": "",
                "material_count": 0,
                "shortfalls": [],
                "resolved_materials": [],
                "group_distributions": [],
            }

        with self._operation_lock:
            with self._client(timeout=20.0) as client:
                detail = self._fetch_detail_on(client, order.id_os)
                if order.num_os.encode("ascii") not in detail:
                    raise DataSnapError(
                        "O servidor retornou outra OS ao preparar as miscelaneas"
                    )
                context = self._detail_context(detail)
                if context.id_os != order.id_os or context.contract != order.contract:
                    raise DataSnapError(
                        "O servidor retornou outra OS ao preparar as miscelaneas"
                    )
                if context.installer_id != expected_installer_id:
                    raise ValueError(
                        "O instalador da OS mudou antes da preparacao das "
                        "miscelaneas; atualize a lista e revise a baixa"
                    )

                catalog = list(self._combined_material_catalog_on(client, context))
                available = {material.code: material for material in catalog}
                lookup_handle: int | None = None
                resolved: list[tuple[StockMaterial, Decimal]] = []
                for item in requested:
                    material = available.get(item["code"])
                    if material is None and item["description"]:
                        if lookup_handle is None:
                            lookup_handle = self._handle(
                                client,
                                self.material_stock_method,
                            )
                        material = self._lookup_material_by_code_on(
                            client,
                            context,
                            item["code"],
                            item["description"],
                            lookup_handle,
                        )
                    if material is None:
                        group_info = self._lookup_equipment_group_by_code_on(
                            client,
                            item["code"],
                        )
                        if group_info is not None:
                            material = StockMaterial(
                                id_equipment=group_info["id_equipment"],
                                code=item["code"],
                                name=group_info["equipment"],
                                stock_quantity=0,
                                id_stock=context.installer_id,
                                unit=group_info.get("unit") or "UN",
                                id_unit=group_info.get("id_unit") or 2,
                                identified="N",
                                id_group=0,
                                group=group_info["group"],
                            )
                    if material is None:
                        raise ValueError(
                            f"A miscelanea {item['description'] or 'sem descricao'} "
                            f"({item['code']}) nao existe no estoque "
                            "do instalador nem no catalogo da baixa manual"
                        )
                    if material.code not in available:
                        catalog.append(material)
                        available[material.code] = material
                    resolved.append((material, item["quantity"]))

                shortfalls: list[dict] = []
                tolerated_shortfalls: list[dict] = []
                transfer_materials: list[StockMaterial] = []
                allocations: list[dict] = []
                group_distributions: list[dict] = []
                remaining_by_code = {
                    material.code: Decimal(material.stock_quantity)
                    for material in catalog
                }
                remaining_return_by_code: dict[str, Decimal] | None = None
                for material, quantity in resolved:
                    needed = quantity
                    item_allocations: list[dict] = []

                    # 1. Exact code from technician stock first
                    available_exact = remaining_by_code.get(
                        material.code,
                        Decimal("0"),
                    )
                    if available_exact > 0:
                        take_exact = min(needed, available_exact)
                        remaining_by_code[material.code] -= take_exact
                        needed -= take_exact
                        allocations.append(
                            {"code": material.code, "quantity": take_exact}
                        )
                        item_allocations.append(
                            {"code": material.code, "quantity": take_exact}
                        )

                    # 2. If insufficient exact balance, check official DspLoc group equivalents
                    used_group = ""
                    if needed > 0:
                        group_info = self._lookup_equipment_group_by_code_on(
                            client,
                            material.code,
                        )
                        equivalents = (
                            group_info.get("equivalents", [])
                            if group_info
                            else []
                        )
                        if group_info:
                            used_group = group_info.get("group", "")

                        # Some real TOA codes are valid but are not indexed by DspLoc
                        # (for example 22066906). Only after the exact code and DspLoc
                        # fail, fall back to the explicit operator-approved code group.
                        if not equivalents:
                            approved_group = approved_equivalence_group_for_code(
                                material.code
                            )
                            if approved_group:
                                equivalents = list(approved_group["codes"])
                                used_group = approved_group["label"]

                        if equivalents:
                            for eq_code in equivalents:
                                if eq_code == material.code:
                                    continue
                                eq_stock = remaining_by_code.get(
                                    eq_code,
                                    Decimal("0"),
                                )
                                if eq_stock > 0:
                                    take_eq = min(needed, eq_stock)
                                    remaining_by_code[eq_code] -= take_eq
                                    needed -= take_eq
                                    allocations.append(
                                        {"code": eq_code, "quantity": take_eq}
                                    )
                                    item_allocations.append(
                                        {"code": eq_code, "quantity": take_eq}
                                    )
                                    if needed <= 0:
                                        break
                        elif material.id_group > 0 or material.group.strip():
                            # Fallback to legacy distribute_by_group if DspLoc has no equivalents
                            inventory = []
                            for candidate in catalog:
                                candidate_data = candidate.to_dict()
                                candidate_data["stock_quantity"] = remaining_by_code.get(
                                    candidate.code,
                                    Decimal("0"),
                                )
                                inventory.append(candidate_data)
                            distributed = None
                            try:
                                distributed = distribute_by_group(
                                    inventory,
                                    group_id=material.id_group,
                                    group_name=material.group,
                                    requested_quantity=needed,
                                    preferred_code=material.code,
                                )
                            except ValueError as exc:
                                if "Estoque insuficiente" not in str(exc):
                                    raise
                            if distributed is not None:
                                for row in distributed:
                                    row_quantity = Decimal(row["quantity"])
                                    remaining_by_code[row["code"]] -= row_quantity
                                    allocations.append(
                                        {"code": row["code"], "quantity": row_quantity}
                                    )
                                    item_allocations.append(
                                        {"code": row["code"], "quantity": row_quantity}
                                    )
                                needed = Decimal("0")
                                used_group = material.group

                    # 3. If technician group balance is insufficient, consume RETORNO
                    # using the same official DspLoc codes before declaring shortage.
                    if needed > 0:
                        if needed != needed.to_integral_value():
                            raise ValueError(
                                "O complemento automatico de estoque aceita somente "
                                f"quantidade inteira para a miscelanea {material.code}"
                            )
                        if remaining_return_by_code is None:
                            remaining_return_by_code = {
                                code: Decimal(value)
                                for code, value in self._material_virtual_stock_quantities_on(
                                    client
                                ).items()
                            }
                        return_codes = list(dict.fromkeys(
                            [material.code]
                            + [
                                str(code).strip()
                                for code in equivalents
                                if str(code).strip() and str(code).strip() != material.code
                            ]
                        ))
                        for return_code in return_codes:
                            if needed <= 0:
                                break
                            source_available = remaining_return_by_code.get(
                                return_code,
                                Decimal("0"),
                            )
                            if source_available <= 0:
                                continue
                            transfer_material = available.get(return_code)
                            if transfer_material is None:
                                return_info = self._lookup_equipment_group_by_code_on(
                                    client,
                                    return_code,
                                )
                                if return_info is None:
                                    continue
                                transfer_material = StockMaterial(
                                    id_equipment=int(return_info.get("id_equipment") or 0),
                                    code=return_code,
                                    name=str(return_info.get("equipment") or return_code),
                                    stock_quantity=0,
                                    id_stock=material.id_stock,
                                    unit=str(return_info.get("unit") or material.unit or "UN"),
                                    id_unit=int(return_info.get("id_unit") or material.id_unit or 2),
                                    identified="N",
                                    id_group=material.id_group,
                                    group=used_group or material.group,
                                    business_unit_id=material.business_unit_id,
                                )
                                if transfer_material.id_equipment <= 0:
                                    continue
                                catalog.append(transfer_material)
                                available[return_code] = transfer_material
                                remaining_by_code.setdefault(return_code, Decimal("0"))
                            take_return = min(needed, source_available)
                            if take_return != take_return.to_integral_value():
                                continue
                            remaining_return_by_code[return_code] -= take_return
                            needed -= take_return
                            transfer_quantity = int(take_return)
                            transfer_materials.append(
                                replace(
                                    transfer_material,
                                    stock_quantity=0,
                                    requested_quantity=transfer_quantity,
                                )
                            )
                            shortfalls.append(
                                {
                                    "code": return_code,
                                    "requested_code": material.code,
                                    "requested_quantity": str(quantity),
                                    "technician_available": int(transfer_material.stock_quantity),
                                    "transfer_quantity": transfer_quantity,
                                    "group": used_group or material.group,
                                }
                            )
                            allocations.append(
                                {"code": return_code, "quantity": take_return}
                            )
                            item_allocations.append(
                                {"code": return_code, "quantity": take_return}
                            )
                        if needed > 0:
                            group_label = used_group or material.group or material.code
                            tolerated_shortfalls.append(
                                {
                                    "code": material.code,
                                    "group": group_label,
                                    "missing_quantity": self._decimal_text(needed),
                                }
                            )
                            needed = Decimal("0")

                    # Audit group distribution if equivalents were used
                    if any(
                        alloc["code"] != material.code
                        for alloc in item_allocations
                    ) or (material.id_group > 0 and len(item_allocations) > 1):
                        distribution_rows: dict[str, Decimal] = {}
                        for alloc in item_allocations:
                            c = alloc["code"]
                            distribution_rows[c] = (
                                distribution_rows.get(c, Decimal("0"))
                                + alloc["quantity"]
                            )
                        group_distributions.append(
                            {
                                "requested_code": material.code,
                                "group_id": material.id_group,
                                "group": used_group or material.group,
                                "allocations": [
                                    {
                                        "code": c,
                                        "quantity": self._decimal_text(q),
                                    }
                                    for c, q in distribution_rows.items()
                                ],
                            }
                        )

                shortfall_item_count = len(tolerated_shortfalls)
                total_missing_quantity = sum(
                    (Decimal(row["missing_quantity"]) for row in tolerated_shortfalls),
                    Decimal("0"),
                )
                if shortfall_item_count >= MATERIAL_SHORTFALL_ITEM_HUMAN_REVIEW_THRESHOLD:
                    details = ", ".join(
                        f"{row['code']} ({row['group']}): {row['missing_quantity']}"
                        for row in tolerated_shortfalls
                    )
                    raise ValueError(
                        "O estoque do tecnico + RETORNO nao cobre miscelaneas distintas; "
                        f"faltam {shortfall_item_count} miscelaneas sem cobertura "
                        f"({details}). Limite para baixa automatica: ate 4 miscelaneas distintas sem saldo"
                    )
                if shortfall_item_count > 0:
                    LOGGER.warning(
                        "IdOS %s: baixa seguira com %s miscelanea(s) sem saldo; "
                        "quantidade total faltante=%s (limite operacional: 4 miscelaneas)",
                        order.id_os,
                        shortfall_item_count,
                        self._decimal_text(total_missing_quantity),
                    )

                if transfer_materials:
                    merged_transfers: dict[str, StockMaterial] = {}
                    for transfer_material in transfer_materials:
                        current = merged_transfers.get(transfer_material.code)
                        if current is None:
                            merged_transfers[transfer_material.code] = transfer_material
                        else:
                            merged_transfers[transfer_material.code] = replace(
                                current,
                                stock_quantity=0,
                                requested_quantity=(
                                    current.requested_quantity
                                    + transfer_material.requested_quantity
                                ),
                            )
                    self._transfer_material_shortfalls(
                        client,
                        context,
                        list(merged_transfers.values()),
                    )

        aggregated: dict[str, Decimal] = {}
        for allocation in allocations:
            aggregated[allocation["code"]] = (
                aggregated.get(allocation["code"], Decimal("0"))
                + allocation["quantity"]
            )

        return {
            "prepared": True,
            "transferred": bool(shortfalls),
            "source": (
                MATERIAL_REPLENISHMENT_STOCK_NAME
                if shortfalls
                else "technician_stock"
            ),
            "installer_id": context.installer_id,
            "installer_name": context.installer_name,
            "material_count": len(resolved),
            "shortfalls": shortfalls,
            "tolerated_shortfalls": tolerated_shortfalls,
            "tolerated_shortfall_count": len(tolerated_shortfalls),
            "resolved_materials": [
                {
                    "codigoequipamento": code,
                    "qtd": self._decimal_text(quantity),
                }
                for code, quantity in aggregated.items()
            ],
            "group_distributions": group_distributions,
        }

    @classmethod
    def _installed_parts(
        cls,
        context: DetailContext,
        equipment: Equipment,
        temporary_id: int = -1,
    ) -> tuple[bytes, bytes]:
        part_a = b"".join(
            (
                bytes.fromhex("01000000040000800a0000"),
                struct.pack("<I", context.id_os),
                struct.pack("<I", equipment.id_equipment),
                struct.pack("<I", equipment.id_stock),
                struct.pack("<i", temporary_id),
                cls._short_text(equipment.name),
                struct.pack("<I", equipment.id_brand),
                cls._short_text(equipment.brand),
                struct.pack("<I", equipment.id_unit),
                cls._short_text(equipment.unit),
                cls._short_text(equipment.identified),
                cls._short_text(context.installer_name),
                bytes.fromhex("100200000000000001"),
            )
        )
        part_b = b"".join(
            (
                b"\x00",
                cls._short_text(equipment.code),
                struct.pack("<I", 1),
                cls._short_text("N"),
                cls._short_text(equipment.serial),
                b"\x01\x00",
                struct.pack("<I", equipment.id_group),
                struct.pack("<I", 1),
                b"\x04\x00",
                struct.pack("<i", temporary_id),
                cls._short_text(equipment.serial),
                b"\x01\x00",
            )
        )
        return part_a, part_b

    @classmethod
    def _removed_parts(
        cls,
        context: DetailContext,
        equipment: Equipment,
    ) -> tuple[bytes, bytes]:
        part_a = b"".join(
            (
                struct.pack("<I", 1),
                bytes.fromhex("040000200000"),
                struct.pack("<I", context.id_os),
                struct.pack("<I", equipment.id_equipment),
                cls._short_text(equipment.code),
                cls._short_text(equipment.name),
                cls._short_text(equipment.identified),
                struct.pack("<I", equipment.id_brand),
                cls._short_text(equipment.brand),
                struct.pack("<I", equipment.id_unit),
                cls._short_text(equipment.unit),
                cls._short_text(equipment.serial),
                struct.pack("<I", equipment.id_equipment),
                cls._short_text(equipment.serial),
                bytes.fromhex("01000100014e1002"),
            )
        )
        return part_a, bytes.fromhex("000001000000000000000000")

    @classmethod
    def _material_row(
        cls,
        context: DetailContext,
        material: StockMaterial,
        temporary_id: int,
        continuation: bool,
    ) -> bytes:
        quantity = material.requested_quantity
        if quantity <= 0 or quantity > 0xFFFF:
            raise ValueError("A quantidade da miscelanea deve estar entre 1 e 65535")
        return b"".join(
            (
                bytes.fromhex("0400a8a00aa002"),
                struct.pack("<I", context.id_os),
                struct.pack("<I", material.id_equipment),
                struct.pack("<I", material.id_stock),
                struct.pack("<i", temporary_id),
                cls._short_text(material.name),
                cls._short_text(material.unit),
                cls._short_text(material.identified),
                bytes.fromhex("1002000000000000"),
                struct.pack("<H", quantity),
                bytes.fromhex("1002") if continuation else b"\x00\x00",
                b"\x00" * 6,
                cls._short_text(material.code),
                struct.pack("<I", material.business_unit_id or 1),
                cls._short_text("N"),
                b"\x00" * (4 if continuation else 6),
            )
        )

    @staticmethod
    def _material_transfer_xml(materials: list[StockMaterial]) -> str:
        lines = ['<?xml version="1.0" encoding="ISO-8859-1" ?>', "<MovimentacaoEstoqueItens>"]
        for material in materials:
            lines.extend(
                (
                    "<Itens>",
                    f"<IdEquipamento>{material.id_equipment}</IdEquipamento>",
                    f"<CodigoEquipamento>{material.code}</CodigoEquipamento>",
                    f"<Descricao>{html.escape(material.name, quote=False)}</Descricao>",
                    f"<Quantidade>{material.requested_quantity}</Quantidade>",
                    f"<QtdEmEstoque>{material.stock_quantity}</QtdEmEstoque>",
                    "<Baixado>False</Baixado>",
                    f"<IdUnidadeNegocio>{material.business_unit_id or 1}</IdUnidadeNegocio>",
                    f"<Unidade>{html.escape(material.unit, quote=False)}</Unidade>",
                    f"<IdEstoque>{material.id_stock}</IdEstoque>",
                    f"<Identificado>{html.escape(material.identified, quote=False)}</Identificado>",
                    "<PodeBaixar>True</PodeBaixar>",
                    "</Itens>",
                )
            )
        lines.append("</MovimentacaoEstoqueItens>")
        return "\r\n".join(lines) + "\r\n"

    def _material_transfer_query(
        self,
        context: DetailContext,
        materials: list[StockMaterial],
    ) -> bytes:
        query = self._replace_utf16_parameter(
            self.material_transfer_template,
            "@ArqXml",
            self._material_transfer_xml(materials),
        )
        query = self._replace_integer_parameter(
            query,
            "@IdEstoqueDestino",
            context.installer_id,
        )
        query = self._replace_integer_parameter(
            query,
            "@IdUsuario",
            self.controller_id,
        )
        return self._adjust_query_length(
            query,
            len(self.material_transfer_template),
            self.material_transfer_page_offset,
            self.material_transfer_length_offset,
        )

    @staticmethod
    def _provider_close_query(query: bytes) -> bytes:
        open_marker = b"!\x01`a\x01"
        if query.count(open_marker) != 1:
            raise DataSnapError("The provider query phase marker is invalid")
        return query.replace(open_marker, b"``a\x02", 1)

    def _close_code_lookup_query(
        self,
        id_service: int,
        close_code: CloseCode,
    ) -> bytes:
        if id_service <= 0:
            raise ValueError("O servico da OS e invalido")
        query = self._replace_utf16_value(
            self.close_code_lookup_template,
            self.close_code_lookup_marker,
            f"{close_code.wire_code}%",
        )
        query = self._replace_integer_parameter(
            query,
            "pIdServico",
            id_service,
        )
        return self._adjust_query_length(
            query,
            len(self.close_code_lookup_template),
            self.close_code_lookup_page_offset,
            self.close_code_lookup_length_offset,
        )

    @staticmethod
    def _parse_close_code_id(payload: bytes, close_code: CloseCode) -> int:
        marker = bytes((len(close_code.wire_code),)) + close_code.wire_code.encode(
            "ascii"
        )
        for match in re.finditer(re.escape(marker), payload):
            if match.start() < 4 or match.end() >= len(payload):
                continue
            id_code = struct.unpack_from("<I", payload, match.start() - 4)[0]
            description_length = payload[match.end()]
            description_start = match.end() + 1
            description_end = description_start + description_length
            if id_code <= 0 or description_end > len(payload):
                continue
            description = payload[description_start:description_end].decode(
                "cp1252",
                errors="replace",
            )
            norm_desc = normalize_text(description)
            norm_target = normalize_text(close_code.description)
            if (
                norm_desc == norm_target
                or difflib.SequenceMatcher(None, norm_desc, norm_target).ratio() >= 0.75
                or (len(norm_desc) >= 6 and norm_target.startswith(norm_desc[:6]))
            ):
                return id_code
        raise DataSnapError(
            f"O codigo {close_code.code} nao esta disponivel para este servico"
        )

    def _lookup_close_code_id(
        self,
        client: DataSnapClient,
        order: Order,
        close_code: CloseCode,
    ) -> int:
        cache_key = (order.id_service, close_code.code)
        cached = self._close_code_id_cache.get(cache_key)
        if cached is not None:
            return cached

        query = self._close_code_lookup_query(order.id_service, close_code)
        handle = self._handle(client, self.close_code_lookup_method)
        response = client.request("execute", [{"handle": [handle]}, query])
        try:
            payload = response["result"][1]["data"][1]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataSnapError(
                "A consulta do codigo de baixa nao retornou resultado"
            ) from exc
        client.request(
            "execute",
            [{"handle": [handle]}, self._provider_close_query(query)],
        )
        id_code = self._parse_close_code_id(payload, close_code)
        self._close_code_id_cache[cache_key] = id_code
        LOGGER.info(
            "Servico %s: codigo %s usa IdCodigoBaixa %s",
            order.id_service,
            close_code.code,
            id_code,
        )
        return id_code

    @staticmethod
    def _suffix_with_close_code_id(
        suffix: bytes,
        close_code: CloseCode,
        id_code: int,
    ) -> bytes:
        captured = struct.pack("<I", close_code.id_code)
        if suffix.count(captured) != 1:
            raise DataSnapError("The close-code identifier marker is invalid")
        return suffix.replace(captured, struct.pack("<I", id_code), 1)

    @staticmethod
    def _suffix_with_observation(
        suffix: bytes,
        close_code: CloseCode,
        observation: str,
    ) -> bytes:
        value = " ".join(str(observation).strip().split())
        if close_code.requires_observation and not value:
            raise ValueError(
                f"O codigo {close_code.code} requer uma observacao"
            )
        if not value:
            return suffix
        if not close_code.observation_marker:
            return suffix
        try:
            marker = close_code.observation_marker.encode("cp1252")
            encoded = value.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise ValueError(
                "A observacao possui um caractere nao suportado pelo Imperium"
            ) from exc
        if len(encoded) > 1000:
            raise ValueError("A observacao deve ter no maximo 1000 caracteres")
        captured = struct.pack("<H", len(marker)) + marker
        replacement = struct.pack("<H", len(encoded)) + encoded
        if suffix.count(captured) != 1:
            raise DataSnapError("The close observation marker is invalid")
        return suffix.replace(captured, replacement, 1)

    @staticmethod
    def _apply_error_message(payload: bytes) -> str | None:
        marker = b"[FireDAC]"
        position = payload.find(marker)
        if position < 0:
            return None
        match = re.match(
            rb"[\x20-\x7e\x80-\xff]+",
            payload[position:],
        )
        if match is None:
            return None
        message = match.group(0).decode("cp1252", errors="replace").strip()
        sql_server_marker = "[SQL Server]"
        if sql_server_marker in message:
            message = message.split(sql_server_marker, 1)[1].strip()
        return message or None

    def _transfer_material_shortfalls(
        self,
        client: DataSnapClient,
        context: DetailContext,
        materials: list[StockMaterial],
    ) -> bool:
        shortfalls = [
            material
            for material in materials
            if material.requested_quantity > material.stock_quantity
        ]
        if not shortfalls:
            return True
        if self.port != PORT:
            raise DataSnapError(
                "A transferencia automatica de miscelaneas foi validada somente em Natal"
            )
        source_shortages = self._material_source_shortages_on(
            client,
            shortfalls,
        )
        if source_shortages:
            material_names = {
                material.code: material.name
                for material in shortfalls
                if material.code and material.name
            }
            detail = ", ".join(
                f"{material_names.get(code, 'MATERIAL')} ({code}) "
                f"(precisa {required}, disponivel {available})"
                for code, (required, available) in source_shortages.items()
            )
            raise ValueError(
                "O estoque virtual RETORNO nao tem saldo suficiente para: "
                f"{detail}. Remova essas miscelaneas da baixa e tente novamente"
            )
        LOGGER.info(
            "IdOS %s: transferindo saldo para %s miscelaneas do estoque do instalador",
            context.id_os,
            len(shortfalls),
        )
        handle = self._handle(client, self.material_stock_method)
        client.set_timeout(180.0)
        query = self._material_transfer_query(context, shortfalls)
        try:
            client.request(
                "execute",
                [
                    {"handle": [handle]},
                    query,
                ],
            )
        except (DataSnapError, OSError, socket.timeout) as exc:
            codes = ", ".join(material.code for material in shortfalls)
            LOGGER.warning(
                "IdOS %s: complemento de miscelaneas %s sem resposta; "
                "confirmando saldos em uma conexao limpa: %s",
                context.id_os,
                codes,
                exc,
            )
            client.close()
            if self._material_shortfalls_confirmed(context, shortfalls):
                LOGGER.info(
                    "IdOS %s: complemento de miscelaneas %s confirmado "
                    "apos timeout",
                    context.id_os,
                    codes,
                )
                return False
            LOGGER.error(
                "IdOS %s: complemento de miscelaneas %s nao confirmado "
                "apos timeout",
                context.id_os,
                codes,
            )
            raise MaterialTransferUncertainError(
                "O resultado do complemento das miscelaneas ficou incerto e "
                "nao sera repetido automaticamente. A baixa da OS nao foi "
                "enviada. Os saldos nao apareceram em uma consulta nova para "
                f"os codigos {codes}: {exc}"
            ) from exc

        LOGGER.info(
            "IdOS %s: complemento de %s miscelaneas confirmado pelo servidor",
            context.id_os,
            len(shortfalls),
        )
        try:
            client.request(
                "execute",
                [{"handle": [handle]}, self._provider_close_query(query)],
            )
        except (DataSnapError, OSError, socket.timeout) as exc:
            LOGGER.warning(
                "IdOS %s: complemento confirmado, mas o provider nao fechou; "
                "a baixa continuara em uma conexao limpa: %s",
                context.id_os,
                exc,
            )
            return False
        return True

    def _material_source_shortages_on(
        self,
        client: DataSnapClient,
        materials: list[StockMaterial],
    ) -> dict[str, tuple[int, int]]:
        quantities = self._material_virtual_stock_quantities_on(client)

        shortages: dict[str, tuple[int, int]] = {}
        for material in materials:
            required = max(
                material.requested_quantity - material.stock_quantity,
                0,
            )
            available = max(int(quantities.get(material.code, Decimal(0))), 0)
            if available < required:
                shortages[material.code] = (required, available)
        return shortages

    def _material_virtual_stock_quantities_on(
        self,
        client: DataSnapClient,
    ) -> dict[str, Decimal]:
        """Read RETORNO balances without moving any material."""
        handle = self._handle(
            client,
            self.stock_protocol.technicians_method,
        )
        technician_payload = self._dataset_payload(
            client,
            handle,
            self.stock_protocol.technicians_query,
            "estoques para complemento de miscelaneas",
        )
        source_stock_id = self._named_virtual_stock_id(
            technician_payload,
            MATERIAL_REPLENISHMENT_STOCK_NAME,
        )

        item_handle = self._handle(client, self.stock_protocol.items_method)
        item_payload = self._dataset_payload(
            client,
            item_handle,
            self.stock_protocol.items_query(source_stock_id),
            "miscelaneas do estoque virtual RETORNO",
        )
        quantities: dict[str, Decimal] = {}
        for item in parse_stock_items(item_payload):
            quantities[item.code] = quantities.get(item.code, Decimal(0)) + (
                item.quantity_number
            )
        return quantities

    @staticmethod
    def _named_virtual_stock_id(payload: bytes, stock_name: str) -> int:
        """Locate a stock without an installer in the raw technician dataset."""
        encoded_name = str(stock_name or "").strip().encode(
            "cp1252",
            errors="strict",
        )
        if not encoded_name or len(encoded_name) > 255:
            raise DataSnapError("O nome do estoque virtual e invalido")

        marker = bytes((len(encoded_name),)) + encoded_name
        candidates: list[int] = []
        offset = 0
        while True:
            position = payload.find(marker, offset)
            if position < 0:
                break
            if position >= 4:
                stock_id = struct.unpack_from("<I", payload, position - 4)[0]
                if 0 < stock_id <= 1_000_000 and stock_id not in candidates:
                    candidates.append(stock_id)
            offset = position + len(marker)

        if len(candidates) != 1:
            detail = "nao foi localizado" if not candidates else "ficou ambiguo"
            raise DataSnapError(
                f"O estoque virtual {stock_name} {detail}; "
                "o complemento automatico foi bloqueado"
            )
        return candidates[0]

    def _material_shortfalls_confirmed(
        self,
        context: DetailContext,
        materials: list[StockMaterial],
    ) -> bool:
        required = {
            material.code: material.requested_quantity
            for material in materials
        }
        for attempt in range(1, 4):
            try:
                with self._client(timeout=20.0) as client:
                    detail = self._fetch_detail_on(client, context.id_os)
                    current_context = self._detail_context(detail)
                    if current_context.installer_id != context.installer_id:
                        LOGGER.warning(
                            "IdOS %s: instalador mudou durante a confirmacao "
                            "do complemento (%s -> %s)",
                            context.id_os,
                            context.installer_name,
                            current_context.installer_name,
                        )
                        return False
                    current = {
                        material.code: material.stock_quantity
                        for material in self._combined_material_catalog_on(
                            client,
                            current_context,
                        )
                    }
                missing = {
                    code: (current.get(code, 0), quantity)
                    for code, quantity in required.items()
                    if current.get(code, 0) < quantity
                }
                if not missing:
                    return True
                LOGGER.warning(
                    "IdOS %s: complemento ainda ausente na confirmacao %s/3: %s",
                    context.id_os,
                    attempt,
                    ", ".join(
                        f"{code}={available}/{quantity}"
                        for code, (available, quantity) in missing.items()
                    ),
                )
            except (DataSnapError, OSError, socket.timeout) as exc:
                LOGGER.warning(
                    "IdOS %s: falha ao confirmar complemento %s/3: %s",
                    context.id_os,
                    attempt,
                    exc,
                )
            if attempt < 3:
                time.sleep(attempt)
        return False

    def _assemble_apply_blob(
        self,
        record: bytes,
        record_mask: bytes,
        delta_suffix: bytes,
    ) -> bytes:
        main_old_mask = self.old_mask[:18]
        main_new_mask = self.new_mask[:18]
        main_position = record.find(main_old_mask)
        if main_position < 0:
            raise DataSnapError(
                "This order has a detail format that is not validated for closing"
            )
        modified = bytearray(record)
        modified[main_position : main_position + len(main_old_mask)] = main_new_mask

        # Some old OS rows omit the second optional empty dataset. When it is
        # present, mark it exactly as the official client does; when absent,
        # the next byte already belongs to the following field and is kept.
        optional_position = main_position + len(main_old_mask)
        optional_old_mask = self.old_mask[18:]
        optional_new_mask = self.new_mask[18:]
        if (
            modified[
                optional_position : optional_position + len(optional_old_mask)
            ]
            == optional_old_mask
        ):
            modified[
                optional_position : optional_position + len(optional_old_mask)
            ] = optional_new_mask
        return self._packet_from_modified_record(
            bytes(modified),
            record_mask,
            delta_suffix,
        )

    def _packet_from_modified_record(
        self,
        modified: bytes,
        record_mask: bytes,
        delta_suffix: bytes,
    ) -> bytes:
        packet = bytearray(self.apply_packet_prefix)
        if len(record_mask) != 19 or len(packet) < len(record_mask):
            raise DataSnapError("The order detail field mask is invalid")
        # Both the field mask and the two packet lengths vary with each order.
        packet[-len(record_mask) :] = record_mask
        packet.extend(modified)
        packet.extend(delta_suffix)

        captured_packet_length = (
            struct.unpack_from("<I", self.apply_packet_prefix, 4)[0] + 23
        )
        dynamic_length_base = captured_packet_length - struct.unpack_from(
            "<H", self.apply_packet_prefix, 2
        )[0]
        dynamic_length = len(packet) - dynamic_length_base
        captured_dynamic = struct.unpack_from(
            "<H", self.apply_packet_prefix, 2
        )[0]
        page_delta = dynamic_length // 256 - captured_dynamic // 256
        encoded_dynamic = dynamic_length - page_delta * 256
        encoded_page = self.apply_packet_prefix[1] + page_delta
        if (
            dynamic_length < 0
            or encoded_dynamic < 0
            or encoded_dynamic > 0xFFFF
            or encoded_page < 0
            or encoded_page > 0xFF
        ):
            raise DataSnapError("The ApplyUpdates dynamic length is invalid")
        packet[1] = encoded_page
        struct.pack_into("<H", packet, 2, encoded_dynamic)
        struct.pack_into("<I", packet, 4, len(packet) - 23)
        return b"#Dsp" + bytes(packet)

    def _build_apply_blob(self, detail: bytes, delta_suffix: bytes) -> bytes:
        record, record_mask = self._detail_parts(detail)
        return self._assemble_apply_blob(record, record_mask, delta_suffix)

    def _build_productive_apply_blob(
        self,
        detail: bytes,
        delta_suffix: bytes,
        installed: list[Equipment] | tuple[Equipment, ...],
        removed: list[Equipment] | tuple[Equipment, ...],
        materials: list[StockMaterial] | tuple[StockMaterial, ...] = (),
    ) -> bytes:
        if not installed and not removed:
            raise ValueError("Informe pelo menos um equipamento")
        if materials and not installed:
            raise ValueError("Miscelaneas requerem equipamento instalado")
        record, record_mask = self._detail_parts(detail)
        if self.old_mask not in record:
            raise DataSnapError(
                "This order has a detail format that is not validated for closing"
            )
        modified = record.replace(self.old_mask, self.new_mask, 1)
        context = self._detail_context(detail)
        if installed:
            if not modified.endswith(b"\x00" * 8):
                raise DataSnapError(
                    "A estrutura de equipamento instalado desta OS nao foi validada"
                )
            rows_a = []
            rows_b = []
            for index, equipment in enumerate(installed, start=1):
                part_a, part_b = self._installed_parts(
                    context,
                    equipment,
                    -index,
                )
                rows_a.append(part_a[4:])
                rows_b.append(part_b)
            modified = (
                modified[:-8]
                + struct.pack("<I", len(installed) + len(materials))
                + b"".join(rows_a)
                + modified[-8:]
                + b"".join(rows_b)
                + b"\x00" * 4
            )
        if materials:
            if not modified.endswith(b"\x00" * 4):
                raise DataSnapError(
                    "A estrutura de miscelaneas desta OS nao foi validada"
                )
            material_rows = [
                self._material_row(
                    context,
                    material,
                    -(len(installed) + index + 1),
                    index < len(materials) - 1,
                )
                for index, material in enumerate(materials)
            ]
            modified = modified[:-4] + b"".join(material_rows)
        if removed:
            if not modified.endswith(b"\x00" * 4):
                raise DataSnapError(
                    "A estrutura de equipamento retirado desta OS nao foi validada"
                )
            rows = []
            for index, equipment in enumerate(removed):
                row_a, part_b = self._removed_parts(context, equipment)
                if index < len(removed) - 1:
                    part_b = part_b[:4] + b"\x10\x02" + part_b[6:]
                rows.append(row_a[4:] + modified[-4:] + part_b)
            modified = (
                modified[:-4]
                + struct.pack("<I", len(removed))
                + b"".join(rows)
            )
        return self._packet_from_modified_record(
            modified,
            record_mask,
            delta_suffix,
        )

    def _append_audit(
        self,
        order: Order,
        close_code: CloseCode,
        result: str,
        detail: str = "",
    ) -> None:
        log_dir = self.log_root
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"baixas-{dt.date.today():%Y%m%d}.csv"
        new_file = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            if new_file:
                writer.writerow(
                    ["DataHora", "IdOS", "NumOS", "Contrato", "Servico", "Codigo", "Resultado", "Detalhe"]
                )
            writer.writerow(
                [
                    dt.datetime.now().isoformat(timespec="seconds"),
                    order.id_os,
                    order.num_os,
                    order.contract,
                    order.service,
                    close_code.code,
                    result,
                    detail,
                ]
            )

    def close_code(self, code: str) -> CloseCode:
        normalized = str(code).strip()
        try:
            return self.close_codes[normalized]
        except KeyError as exc:
            raise ValueError(f"Codigo de baixa nao permitido: {normalized}") from exc

    @staticmethod
    def _is_closed(order: Order, detail: bytes, close_code: CloseCode) -> bool:
        norm_detail = detail.upper()
        norm_desc = close_code.description.upper().encode("cp1252", errors="replace")
        return (
            order.num_os.encode("ascii") in detail
            and close_code.wire_code.encode("ascii") in detail
            and (
                not norm_desc
                or norm_desc in norm_detail
                or (len(norm_desc) >= 6 and norm_desc[:6] in norm_detail)
            )
        )

    def _detect_applied_close_codes(
        self,
        order: Order,
        detail: bytes,
    ) -> tuple[CloseCode, ...]:
        return tuple(
            close_code
            for close_code in self.close_codes.values()
            if self._is_closed(order, detail, close_code)
        )

    def _guard_remote_close_state(
        self,
        order: Order,
        detail: bytes,
        requested_close_code: CloseCode,
    ) -> CloseCode | None:
        applied = self._detect_applied_close_codes(order, detail)
        if not applied:
            return None
        if len(applied) > 1:
            detected = ",".join(sorted(code.code for code in applied))
            raise CloseStateConflictError(
                "shared_state_contamination; "
                f"multiple_remote_close_codes:{detected}; operation_blocked"
            )

        current = applied[0]
        if current.code != requested_close_code.code:
            raise CloseStateConflictError(
                "already_closed; "
                f"already_closed_with_different_code:{current.code}; "
                "remote_state_changed; operation_blocked"
            )
        return current

    def _close_order_with_builder(
        self,
        order: Order,
        close_code: CloseCode,
        blob_builder: Callable[[DataSnapClient, bytes, bytes], bytes],
        *,
        apply_timeout: float = 10.0,
        confirmation_delays: tuple[float, ...] | None = None,
    ) -> dict:
        suffix_variants = close_code.suffixes
        with self._operation_lock:
            first_apply_error: Exception | None = None
            final_confirmation_error: Exception | None = None
            sent_any_variant = False

            for variant_index, delta_suffix in enumerate(
                suffix_variants,
                start=1,
            ):
                client: DataSnapClient | None = None
                apply_blob = b""
                handle = 0
                last_network_error: OSError | None = None

                for attempt in range(1, 4):
                    candidate = self._client(timeout=7.0)
                    try:
                        LOGGER.info(
                            "IdOS %s: consultando detalhes para a variante %s/%s, "
                            "tentativa %s/3",
                            order.id_os,
                            variant_index,
                            len(suffix_variants),
                            attempt,
                        )
                        candidate.connect()
                        detail = self._fetch_detail_on(candidate, order.id_os)
                        if order.num_os.encode("ascii") not in detail:
                            raise DataSnapError(
                                "The server returned a different order"
                            )
                        applied_close_code = self._guard_remote_close_state(
                            order,
                            detail,
                            close_code,
                        )
                        if applied_close_code is not None:
                            result = (
                                "SUCESSO_APOS_TIMEOUT"
                                if sent_any_variant
                                else "JA_BAIXADA"
                            )
                            LOGGER.info(
                                "IdOS %s: baixa %s ja esta aplicada",
                                order.id_os,
                                close_code.code,
                            )
                            self._append_audit(order, close_code, result)
                            candidate.close()
                            return {
                                "ok": True,
                                "already_closed": not sent_any_variant,
                                "id_os": order.id_os,
                                "num_os": order.num_os,
                                "code": close_code.code,
                                "description": close_code.description,
                            }
                        id_code = self._lookup_close_code_id(
                            candidate,
                            order,
                            close_code,
                        )
                        resolved_suffix = self._suffix_with_close_code_id(
                            delta_suffix,
                            close_code,
                            id_code,
                        )
                        apply_blob = blob_builder(
                            candidate,
                            detail,
                            resolved_suffix,
                        )
                        handle = self._handle(
                            candidate,
                            "TDtmOrdemServico.AS_ApplyUpdates",
                        )
                        client = candidate
                        break
                    except _MaterialTransferReconnectRequired as exc:
                        candidate.close()
                        LOGGER.info(
                            "IdOS %s: %s",
                            order.id_os,
                            exc,
                        )
                    except OSError as exc:
                        last_network_error = exc
                        candidate.close()
                        LOGGER.warning(
                            "IdOS %s: falha de conexao antes do envio %s/3: %s",
                            order.id_os,
                            attempt,
                            exc,
                        )
                        if attempt < 3:
                            time.sleep(attempt)
                    except Exception:
                        candidate.close()
                        raise
                else:
                    error = DataSnapError(
                        "Nao foi possivel conectar ao servidor do Imperium "
                        "apos 3 tentativas"
                    )
                    self._append_audit(
                        order,
                        close_code,
                        "FALHA",
                        str(last_network_error or error),
                    )
                    raise error from last_network_error

                apply_error: Exception | None = None
                definitive_apply_failure = False
                sent_any_variant = True
                try:
                    client.set_timeout(apply_timeout)
                    LOGGER.info(
                        "IdOS %s: enviando ApplyUpdates variante %s/%s "
                        "(limite %.0fs)",
                        order.id_os,
                        variant_index,
                        len(suffix_variants),
                        apply_timeout,
                    )
                    response = client.request(
                        "execute", [{"handle": [handle]}, apply_blob]
                    )
                    try:
                        response_blob = response["result"][1]["data"][1]
                    except (KeyError, IndexError, TypeError) as exc:
                        LOGGER.warning(
                            "IdOS %s: ApplyUpdates sem result; chaves=%s",
                            order.id_os,
                            sorted(response.keys()),
                        )
                        raise DataSnapError(
                            "ApplyUpdates returned no result"
                        ) from exc
                    if response_blob != self.apply_success:
                        error_message = self._apply_error_message(response_blob)
                        LOGGER.warning(
                            "IdOS %s: pacote ApplyUpdates len=%s hex=%s",
                            order.id_os,
                            len(response_blob),
                            response_blob[:256].hex(),
                        )
                        if error_message:
                            definitive_apply_failure = True
                            raise DataSnapError(error_message)
                        raise DataSnapError(
                            "ApplyUpdates returned an unexpected result packet"
                        )
                    client.set_timeout(7.0)
                except (DataSnapError, OSError, socket.timeout) as exc:
                    apply_error = exc
                    if first_apply_error is None:
                        first_apply_error = exc
                    LOGGER.warning(
                        "IdOS %s: ApplyUpdates variante %s falhou ou expirou: %s",
                        order.id_os,
                        variant_index,
                        exc,
                    )
                    client.close()
                    client = None

                confirmation = b""
                confirmation_read = False
                final_confirmation_error = None
                active_confirmation_delays = (
                    (0.0,)
                    if definitive_apply_failure
                    else confirmation_delays or (
                        (0.0, 2.0, 4.0, 8.0, 12.0)
                        if apply_error is not None
                        or variant_index == len(suffix_variants)
                        else (0.0, 2.0, 4.0, 8.0)
                    )
                )
                for attempt, delay in enumerate(
                    active_confirmation_delays,
                    start=1,
                ):
                    if delay:
                        time.sleep(delay)
                    try:
                        if client is None:
                            client = self._client(timeout=7.0)
                            client.connect()
                        LOGGER.info(
                            "IdOS %s: confirmando variante %s, tentativa %s/%s",
                            order.id_os,
                            variant_index,
                            attempt,
                            len(active_confirmation_delays),
                        )
                        confirmation = self._fetch_detail_on(
                            client,
                            order.id_os,
                        )
                        confirmation_read = True
                        final_confirmation_error = None
                        if self._is_closed(order, confirmation, close_code):
                            break
                        LOGGER.warning(
                            "IdOS %s: codigo %s ainda nao apareceu na tentativa %s",
                            order.id_os,
                            close_code.code,
                            attempt,
                        )
                    except (DataSnapError, OSError, socket.timeout) as exc:
                        final_confirmation_error = exc
                        LOGGER.warning(
                            "IdOS %s: consulta de confirmacao %s falhou: %s",
                            order.id_os,
                            attempt,
                            exc,
                        )
                        if client is not None:
                            client.close()
                            client = None

                if client is not None:
                    client.close()

                if self._is_closed(order, confirmation, close_code):
                    result = (
                        "SUCESSO_APOS_TIMEOUT"
                        if apply_error is not None or variant_index > 1
                        else "SUCESSO"
                    )
                    LOGGER.info(
                        "IdOS %s: codigo %s confirmado com a variante %s",
                        order.id_os,
                        close_code.code,
                        variant_index,
                    )
                    self._append_audit(order, close_code, result)
                    return {
                        "ok": True,
                        "already_closed": False,
                        "id_os": order.id_os,
                        "num_os": order.num_os,
                        "code": close_code.code,
                        "description": close_code.description,
                    }

                has_alternate = variant_index < len(suffix_variants)
                if has_alternate and confirmation_read:
                    LOGGER.warning(
                        "IdOS %s: servidor respondeu sem gravar a variante %s; "
                        "tentando a variante oficial alternativa",
                        order.id_os,
                        variant_index,
                    )
                    continue
                break

            detail_message = str(
                first_apply_error
                or final_confirmation_error
                or "servidor respondeu, mas a baixa nao foi gravada"
            )
            if definitive_apply_failure and first_apply_error is not None:
                self._append_audit(order, close_code, "FALHA", detail_message)
                raise DataSnapError(detail_message) from first_apply_error
            self._append_audit(order, close_code, "INCERTO", detail_message)
            error = CloseConfirmationUncertainError(
                "A solicitacao de baixa foi enviada, mas o Imperium ainda nao "
                f"confirmou o codigo {close_code.code}. Nao repita a operacao; "
                "o painel continuara verificando sem reenviar."
            )
            cause = first_apply_error or final_confirmation_error
            if cause is not None:
                raise error from cause
            raise error

    def close_order(
        self,
        order: Order,
        code: str | CloseCode = DEFAULT_CODE,
        *,
        observation: str = "",
    ) -> dict:
        if isinstance(code, CloseCode):
            close_code = code
        else:
            close_code = self.close_code(code)
        if close_code.productive:
            raise ValueError(
                f"O codigo {close_code.code} requer os seriais dos equipamentos"
            )
        if close_code.requires_observation and not observation.strip():
            raise ValueError(
                f"O codigo {close_code.code} requer uma observacao"
            )
        close_code = replace(
            close_code,
            suffixes=tuple(
                self._suffix_with_observation(
                    suffix,
                    close_code,
                    observation,
                )
                for suffix in close_code.suffixes
            ),
        )
        return self._close_order_with_builder(
            order,
            close_code,
            lambda _client, detail, suffix: self._build_apply_blob(
                detail,
                suffix,
            ),
        )

    def close_productive(
        self,
        order: Order,
        code: str,
        *,
        installed_serial: str = "",
        removed_serial: str = "",
        removed_type: str = "",
        installed_equipment: list[dict] | None = None,
        removed_equipment: list[dict] | None = None,
        materials: list[dict] | None = None,
    ) -> dict:
        close_code = self.close_code(code)
        if not close_code.productive:
            raise ValueError(f"O codigo {close_code.code} nao movimenta equipamento")
        if isinstance(materials, list):
            filtered_materials = []
            for value in materials:
                ignore_reason = (
                    toa_material_ignore_reason(
                        value.get("description", ""),
                        value.get("code", ""),
                    )
                    if isinstance(value, dict)
                    else ""
                )
                if ignore_reason:
                    LOGGER.info(
                        "IdOS %s: miscelanea %s removida da baixa pela regra %s",
                        order.id_os,
                        str(value.get("code", "")).strip(),
                        ignore_reason,
                    )
                    continue
                filtered_materials.append(value)
            materials = filtered_materials
        service = order.service.upper()
        if service.startswith("ADES") and "ASSINATURA" in service:
            has_inventory = bool(
                installed_serial.strip()
                or removed_serial.strip()
                or installed_equipment
                or removed_equipment
                or materials
            )
            if has_inventory:
                raise ValueError(
                    "Adesao de assinatura nao permite equipamento ou miscelanea"
                )
            return self._close_order_with_builder(
                order,
                close_code,
                lambda _client, detail, suffix: self._build_apply_blob(
                    detail,
                    suffix,
                ),
            )

        if installed_equipment is None:
            installed_equipment = (
                [{"serial": installed_serial, "type": "auto"}]
                if installed_serial.strip()
                else []
            )
        if removed_equipment is None:
            removed_equipment = (
                [{"serial": removed_serial, "type": removed_type}]
                if removed_serial.strip()
                else []
            )
        if not isinstance(installed_equipment, list) or not isinstance(
            removed_equipment, list
        ):
            raise ValueError("A lista de equipamentos e invalida")
        if materials is None:
            materials = []
        if not isinstance(materials, list):
            raise ValueError("A lista de miscelaneas e invalida")
        if len(installed_equipment) > 300 or len(removed_equipment) > 300:
            raise ValueError("O limite tecnico e de 300 equipamentos por movimentacao")
        if len(materials) > 300:
            raise ValueError("O limite tecnico e de 300 miscelaneas por baixa")

        def normalize_items(values: list[dict], installed: bool) -> list[dict]:
            output = []
            for value in values:
                if not isinstance(value, dict):
                    raise ValueError("Cada equipamento deve informar serial e tipo")
                serial = str(value.get("serial", "")).strip().upper()
                equipment_type = str(value.get("type", "")).strip().lower()
                if not serial:
                    raise ValueError("Informe o serial de todos os equipamentos")
                pattern = r"[A-Z0-9]{4,25}" if installed else r"[A-Z0-9]{8,25}"
                if not re.fullmatch(pattern, serial):
                    message = (
                        "O serial instalado deve ter de 4 a 25 letras ou numeros"
                        if installed
                        else "O serial retirado deve ter de 8 a 25 letras ou numeros"
                    )
                    raise ValueError(message)
                if not installed and equipment_type in {"", "auto"}:
                    if re.fullmatch(r"[0-9A-F]{12}", serial, re.IGNORECASE):
                        equipment_type = "emta"
                    elif serial.isdigit():
                        equipment_type = "decoder"
                    else:
                        equipment_type = "emta"
                allowed_types = (
                    {"auto", "decoder", "emta", "smart", "chip"}
                    if installed
                    else {"decoder", "emta", "smart"}
                )
                if equipment_type not in allowed_types:
                    raise ValueError(
                        "Selecione se o equipamento e decoder, EMTA, Smart ou Chip"
                    )
                output.append({"serial": serial, "type": equipment_type})
            return output

        installed_items = normalize_items(installed_equipment, True)
        removed_items = normalize_items(removed_equipment, False)
        material_items = []
        material_codes: set[str] = set()
        for value in materials:
            if not isinstance(value, dict):
                raise ValueError("Cada miscelanea deve informar codigo e quantidade")
            code = str(value.get("code", "")).strip()
            description = str(value.get("description", "")).strip()
            requires_confirmation = bool(value.get("requires_confirmation", False))
            equivalence_confirmed = value.get("equivalence_confirmed") is True
            if requires_confirmation and not equivalence_confirmed:
                raise ValueError(
                    f"Confirme a substituicao equivalente usada na miscelanea {code}"
                )
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", code):
                raise ValueError(
                    f"O formato do codigo da miscelanea {code or '(vazio)'} "
                    "e invalido"
                )
            raw_quantity = value.get("quantity", 0)
            if isinstance(raw_quantity, bool):
                raise ValueError("A quantidade da miscelanea e invalida")
            try:
                quantity = int(raw_quantity)
            except (TypeError, ValueError) as exc:
                raise ValueError("A quantidade da miscelanea e invalida") from exc
            if quantity <= 0 or quantity > 0xFFFF:
                raise ValueError(
                    "A quantidade da miscelanea deve estar entre 1 e 65535"
                )
            if code in material_codes:
                raise ValueError(f"A miscelanea {code} foi informada mais de uma vez")
            material_codes.add(code)
            material_items.append(
                {
                    "code": code,
                    "description": description,
                    "quantity": quantity,
                    "requires_confirmation": requires_confirmation,
                }
            )
        serials = [item["serial"] for item in installed_items + removed_items]
        if len(set(serials)) != len(serials):
            raise ValueError("O mesmo serial foi informado mais de uma vez")
        if close_code.code == "430":
            if material_items:
                raise ValueError("O codigo 430 nao permite miscelaneas instaladas")
            if installed_items:
                raise ValueError("O codigo 430 permite somente equipamento retirado")
            if not removed_items:
                raise ValueError("Informe o serial do equipamento retirado")
        elif close_code.code == "409":
            if not installed_items:
                raise ValueError("Informe o serial do equipamento instalado")
            if "TROCA" in service and not removed_items:
                raise ValueError(
                    "Esta OS de troca requer um serial instalado e um retirado"
                )
            if "MUDAN" in service and removed_items:
                raise ValueError(
                    "Mudanca de pacote foi validada somente com equipamento instalado"
                )
            if material_items and removed_items:
                raise ValueError(
                    "Miscelaneas com troca de equipamento ainda nao foram validadas"
                )
        elif close_code.code == "706":
            if len(installed_items) != 1:
                raise ValueError("O codigo 706 requer exatamente um chip instalado")
            if removed_items or material_items:
                raise ValueError(
                    "O codigo 706 permite somente o chip instalado, sem retirada ou miscelanea"
                )
            if installed_items[0]["type"] not in {"auto", "chip"}:
                raise ValueError("O codigo 706 aceita somente equipamento do tipo Chip")

        resolved_installed: list[Equipment] = []
        resolved_removed: list[Equipment] = []
        resolved_materials: list[StockMaterial] = []
        material_transfer_completed = False
        resources_prepared = False
        prepared_installer_id = 0

        def build(
            client: DataSnapClient,
            detail: bytes,
            suffix: bytes,
        ) -> bytes:
            nonlocal material_transfer_completed
            nonlocal resources_prepared
            nonlocal prepared_installer_id
            context = self._detail_context(detail)
            if context.id_os != order.id_os or context.contract != order.contract:
                raise DataSnapError(
                    "O servidor retornou outra OS durante a baixa produtiva"
                )
            if resources_prepared and context.installer_id != prepared_installer_id:
                raise DataSnapError(
                    "O instalador da OS mudou durante a preparacao da baixa"
                )
            if not resources_prepared:
                resolved_installed.clear()
                resolved_removed.clear()
                resolved_materials.clear()
                for item in installed_items:
                    equipment = self._lookup_installed_equipment(
                        client,
                        context,
                        item["serial"],
                    )
                    selected_type = item["type"]
                    if not self._equipment_matches_type(equipment, selected_type):
                        raise ValueError(
                            f"O serial {item['serial']} nao corresponde ao tipo selecionado"
                        )
                    resolved_installed.append(equipment)
                for item in removed_items:
                    resolved_removed.append(
                        replace(
                            self.removed_equipment[item["type"]],
                            serial=item["serial"],
                        )
                    )
                if material_items:
                    available = {
                        material.code: material
                        for material in self._combined_material_catalog_on(
                            client,
                            context,
                        )
                    }
                    for item in material_items:
                        material = available.get(item["code"])
                        if material is None and item["description"]:
                            material = self._lookup_material_by_code_on(
                                client,
                                context,
                                item["code"],
                                item["description"],
                            )
                        if material is None:
                            raise ValueError(
                                f"A miscelanea {item['code']} nao existe no estoque do instalador"
                            )
                        resolved_materials.append(
                            replace(
                                material,
                                requested_quantity=item["quantity"],
                            )
                        )
                    if not material_transfer_completed:
                        self._transfer_material_shortfalls(
                            client,
                            context,
                            resolved_materials,
                        )
                        material_transfer_completed = True
                prepared_installer_id = context.installer_id
                resources_prepared = True
                if material_items:
                    # The complete/manual stock providers can keep state on the
                    # DataSnap session. The official client sends ApplyUpdates
                    # from a clean session after preparing the material rows.
                    raise _MaterialTransferReconnectRequired(
                        "Miscelaneas preparadas; reconectando antes da baixa"
                    )
            return self._build_productive_apply_blob(
                detail,
                suffix,
                resolved_installed,
                resolved_removed,
                resolved_materials,
            )

        result = self._close_order_with_builder(
            order,
            close_code,
            build,
            apply_timeout=180.0 if material_items else 10.0,
            confirmation_delays=(0.0, 5.0, 10.0, 20.0, 30.0, 45.0)
            if material_items
            else None,
        )
        result["equipment"] = {
            "installed": [
                {
                    "serial": equipment.serial,
                    "type": installed_items[index]["type"],
                    "code": equipment.code,
                    "name": equipment.name,
                }
                for index, equipment in enumerate(resolved_installed)
            ],
            "removed": [
                {
                    "serial": equipment.serial,
                    "type": removed_items[index]["type"],
                    "code": equipment.code,
                    "name": equipment.name,
                }
                for index, equipment in enumerate(resolved_removed)
            ],
        }
        result["materials"] = [
            {
                "code": material.code,
                "name": material.name,
                "quantity": material.requested_quantity,
                "unit": material.unit,
            }
            for material in resolved_materials
        ]
        return result

    def close_106(self, order: Order) -> dict:
        return self.close_order(order, "106")

    def _send_import_packet(
        self,
        chunks: tuple[bytes, ...],
        final_timeout: float,
    ) -> bytes:
        with self._client(timeout=30.0) as client:
            handle = self._handle(client, self.import_protocol.server_method)
            if len(chunks) == 1:
                client.set_timeout(final_timeout)
                LOGGER.info(
                    "Importacao TOA: bloco unico enviado; "
                    "aguardando processamento por ate %.0fs",
                    final_timeout,
                )
            response = client.request(
                "execute", [{"handle": [handle]}, chunks[0]]
            )
            for index, chunk in enumerate(chunks[1:], start=1):
                if "more_blob" not in response:
                    raise DataSnapError(
                        "O servidor nao solicitou a continuacao da importacao"
                    )
                is_final = index == len(chunks) - 1
                if is_final:
                    client.set_timeout(final_timeout)
                    LOGGER.info(
                        "Importacao TOA: ultimo bloco enviado; "
                        "aguardando processamento por ate %.0fs",
                        final_timeout,
                    )
                elif index == 1 or index % 5 == 0:
                    LOGGER.info(
                        "Importacao TOA: bloco %s/%s enviado",
                        index + 1,
                        len(chunks),
                    )
                response = client.continue_blob(
                    chunk,
                    final=is_final,
                )
            try:
                payload = bytearray(response["result"][1]["data"][1])
            except (KeyError, IndexError, TypeError) as exc:
                raise DataSnapError(
                    "O servidor nao devolveu o resultado da importacao"
                ) from exc
            expected_length = self.import_protocol.incomplete_result_length(payload)
            if expected_length is not None:
                fragment_count = 0
                while len(payload) < expected_length:
                    fragment_count += 1
                    if fragment_count > 64:
                        raise DataSnapError(
                            "O resultado da importacao tem fragmentos demais"
                        )
                    client.set_timeout(30.0)
                    remainder = client.request(
                        "more_blob", [handle, 1, 0, 7, True, 0]
                    )
                    try:
                        chunk = remainder["result"][0]["data"][1]
                    except (KeyError, IndexError, TypeError) as exc:
                        raise DataSnapError(
                            "O fragmento do resultado da importacao e invalido"
                        ) from exc
                    if not chunk:
                        raise DataSnapError(
                            "O fragmento do resultado da importacao veio vazio"
                        )
                    payload.extend(chunk)
                if len(payload) != expected_length:
                    raise DataSnapError(
                        "Resultado da importacao incompleto: "
                        f"{len(payload)} de {expected_length} bytes"
                    )
            LOGGER.info(
                "Importacao TOA: resultado recebido (%s bytes)", len(payload)
            )
            return bytes(payload)

    @property
    def native_creation_enabled(self) -> bool:
        return self.native_order_protocol.enabled

    def native_creation_services(self) -> list[str]:
        return sorted(self.native_order_protocol.services)

    def _native_contract_payload(self, contract: str) -> bytes:
        query = self.native_order_protocol.contract_query(contract)
        with self._client(timeout=20.0) as client:
            handle = self._handle(
                client,
                self.native_order_protocol.contract_method,
            )
            payload = self._dataset_payload(
                client,
                handle,
                query,
                f"contrato {contract}",
            )
            try:
                client.request(
                    "execute",
                    [
                        {"handle": [handle]},
                        self._provider_close_query(query),
                    ],
                )
            except (DataSnapError, OSError, socket.timeout) as exc:
                LOGGER.warning(
                    "Cadastro nativo: nao foi possivel fechar a consulta do "
                    "contrato %s: %s",
                    contract,
                    exc,
                )
            return payload

    def _native_contract_context(
        self,
        payload: bytes,
        contract: str,
        client_mode: str,
    ) -> NativeContractContext:
        if client_mode == "registered":
            return NativeOrderProtocol.parse_contract(payload, contract)
        if client_mode != "fixed_123":
            raise ValueError("Modo de cliente invalido para criacao de OS")
        if self.profile_key != "natal":
            raise ValueError(
                "O cadastro fixo CLIENTE 123 esta validado somente para Natal"
            )
        return NativeContractContext(
            contract=contract,
            os_numbers=(),
            client=CLIENT_123_PROFILE["client"],
            address=CLIENT_123_PROFILE["address"],
            city=CLIENT_123_PROFILE["city"],
            person_id=CLIENT_123_PROFILE["person_id"],
            number=CLIENT_123_PROFILE["number"],
            complement=CLIENT_123_PROFILE["complement"],
            district=CLIENT_123_PROFILE["district"],
            state=CLIENT_123_PROFILE["state"],
            zip_code=CLIENT_123_PROFILE["zip_code"],
            address_type=CLIENT_123_PROFILE["address_type"],
        )

    def _confirm_native_order(
        self,
        contract: str,
        os_number: str,
        query_date: dt.date | None = None,
        delays: tuple[float, ...] = (0.5, 1.5, 3.0, 5.0, 8.0, 13.0, 20.0),
    ) -> tuple[bool, Exception | None]:
        query_date = query_date or dt.date.today()
        last_error: Exception | None = None
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                orders = self.list_orders(query_date)
            except (DataSnapError, OSError, socket.timeout) as exc:
                last_error = exc
                LOGGER.warning(
                    "Cadastro nativo: confirmacao %s/%s da OS %s falhou: %s",
                    attempt,
                    len(delays),
                    os_number,
                    exc,
                )
                continue
            matches = [
                order
                for order in orders
                if re.sub(r"\s+", "", order.num_os)
                == re.sub(r"\s+", "", os_number)
            ]
            if any(order.contract == contract for order in matches):
                return True, None
            if matches:
                raise DataSnapError(
                    f"A OS {os_number} apareceu vinculada a outro contrato"
                )
            LOGGER.info(
                "Cadastro nativo: OS %s ainda nao localizada na confirmacao %s/%s",
                os_number,
                attempt,
                len(delays),
            )
        return False, last_error

    @staticmethod
    def _native_creation_result(rows: list[dict], *, uncertain: bool = False) -> dict:
        imported = sum(1 for row in rows if row.get("imported") is True)
        already_existing = sum(
            1 for row in rows if row.get("already_existed") is True
        )
        result = {
            "ok": not uncertain,
            "count": len(rows),
            "imported": imported,
            "already_existing": already_existing,
            "not_imported": len(rows) - imported - already_existing,
            "orders": rows,
        }
        if uncertain:
            result["uncertain"] = True
        return result

    def create_native_orders(
        self,
        preview: TOAPreview,
        technician_id: int,
        technician_name: str,
        client_mode: str = "registered",
    ) -> dict:
        if not self.native_creation_enabled:
            raise ValueError("Criacao nativa ainda nao mapeada para esta base")
        if technician_id <= 0 or not technician_name.strip():
            raise ValueError("Selecione um tecnico valido")
        if not isinstance(preview, TOAPreview) or not preview.orders:
            raise ValueError("A criacao nao possui ordens")

        service_name = preview.orders[0].os_type
        self.native_order_protocol.service(service_name)
        client_mode = str(client_mode).strip().lower()
        if client_mode not in {"registered", "fixed_123"}:
            raise ValueError("Modo de cliente invalido para criacao de OS")
        if client_mode == "fixed_123" and self.profile_key != "natal":
            raise ValueError(
                "O cadastro fixo CLIENTE 123 esta validado somente para Natal"
            )
        if any(order.os_type != service_name for order in preview.orders):
            raise ValueError("O lote possui mais de um tipo de OS")

        rows: list[dict] = []
        with self._operation_lock:
            for index, order in enumerate(preview.orders):
                row = order.to_dict()
                row["technician"] = technician_name
                try:
                    order_date = dt.datetime.strptime(order.date, "%d/%m/%Y").date()
                except ValueError:
                    row.update(
                        imported=False,
                        import_status="DATA INVALIDA; NAO ENVIADA",
                    )
                    rows.append(row)
                    continue
                if order_date != dt.date.today():
                    row.update(
                        imported=False,
                        import_status="A CRIACAO NATIVA PERMITE SOMENTE A DATA DE HOJE",
                    )
                    rows.append(row)
                    continue

                try:
                    if client_mode == "fixed_123":
                        payload = b""
                        context = self._native_contract_context(
                            payload,
                            order.contract,
                            client_mode,
                        )
                        existing_orders = self.list_orders(dt.date.today())
                    else:
                        payload = self._native_contract_payload(order.contract)
                        context = self._native_contract_context(
                            payload,
                            order.contract,
                            client_mode,
                        )
                        existing_orders = []
                except (DataSnapError, OSError, socket.timeout, ValueError) as exc:
                    row.update(
                        imported=False,
                        import_status=f"NAO ENVIADA: {exc}",
                    )
                    rows.append(row)
                    continue

                compact_os = re.sub(r"\s+", "", order.os_number)
                existing = next(
                    (
                        current
                        for current in existing_orders
                        if re.sub(r"\s+", "", current.num_os) == compact_os
                    ),
                    None,
                )
                if (
                    self.native_order_protocol.contains_os(payload, order.os_number)
                    or existing is not None
                ):
                    if existing is not None and existing.contract != order.contract:
                        row.update(
                            imported=False,
                            import_status=(
                                "NAO ENVIADA: NUMERO DA OS JA VINCULADO "
                                "A OUTRO CONTRATO"
                            ),
                        )
                        rows.append(row)
                        continue
                    row.update(
                        imported=False,
                        already_existed=True,
                        import_status="JA EXISTIA; NAO DUPLICADA",
                    )
                    rows.append(row)
                    continue

                try:
                    service = self.native_order_protocol.service(service_name)
                    if client_mode == "fixed_123":
                        packet = self.manual_order_protocol.build_packet(
                            order.os_number,
                            order.contract,
                            service,
                            technician_id,
                            technician_name,
                            order_date,
                        )
                        apply_method = self.manual_order_protocol.apply_method
                    else:
                        packet = self.native_order_protocol.build_packet(
                            context,
                            order.os_number,
                            service_name,
                            technician_id,
                            technician_name,
                            order_date,
                        )
                        apply_method = self.native_order_protocol.apply_method
                except ValueError as exc:
                    row.update(
                        imported=False,
                        import_status=f"NAO ENVIADA: {exc}",
                    )
                    rows.append(row)
                    continue

                try:
                    with self._client(timeout=30.0) as client:
                        handle = self._handle(
                            client,
                            apply_method,
                        )
                        client.set_timeout(60.0)
                        LOGGER.info(
                            "Cadastro nativo: enviando OS %s, contrato %s, "
                            "servico %s, tecnico %s",
                            order.os_number,
                            order.contract,
                            service_name,
                            technician_name,
                        )
                        client.request(
                            "execute",
                            [{"handle": [handle]}, packet],
                        )
                    write_error: Exception | None = None
                except (DataSnapError, OSError, socket.timeout) as exc:
                    write_error = exc
                    LOGGER.warning(
                        "Cadastro nativo: resposta da OS %s falhou: %s",
                        order.os_number,
                        exc,
                    )

                confirmed, confirmation_error = self._confirm_native_order(
                    order.contract,
                    order.os_number,
                    query_date=order_date,
                )
                if confirmed:
                    status = "CRIADA"
                    if write_error is not None:
                        status = "CRIADA; CONFIRMADA APOS RESPOSTA INCOMPLETA"
                    row.update(imported=True, import_status=status)
                    rows.append(row)
                    continue

                detail = write_error or confirmation_error
                message = (
                    "O resultado da OS nao foi confirmado. A escrita nao sera "
                    "repetida automaticamente"
                )
                if detail is not None:
                    message += f": {detail}"
                row.update(
                    imported=False,
                    import_status="RESULTADO NAO CONFIRMADO",
                )
                rows.append(row)
                for pending in preview.orders[index + 1 :]:
                    pending_row = pending.to_dict()
                    pending_row["technician"] = technician_name
                    pending_row.update(
                        imported=False,
                        import_status="NAO ENVIADA; LOTE INTERROMPIDO",
                    )
                    rows.append(pending_row)
                result = self._native_creation_result(rows, uncertain=True)
                result["error"] = message
                return result

        result = self._native_creation_result(rows)
        result["client_mode"] = client_mode
        result["client"] = (
            CLIENT_123_PROFILE["client"]
            if client_mode == "fixed_123"
            else "CADASTRO DO CONTRATO"
        )
        return result

    def _confirm_import_after_timeout(
        self,
        preview: TOAPreview,
        delays: tuple[float, ...] = (0.0, 3.0, 8.0),
    ) -> dict | None:
        expected = {
            (str(order.os_number), str(order.contract)): order
            for order in preview.orders
        }
        if not expected:
            return None

        last_orders: list[Order] | None = None
        for attempt, delay in enumerate(delays, start=1):
            if delay > 0:
                time.sleep(delay)
            try:
                field_orders = self.list_orders(dt.date.today(), status="field")
                try:
                    completed_orders = self.list_orders(
                        dt.date.today(), status="completed"
                    )
                except Exception:
                    completed_orders = []
                last_orders = field_orders + completed_orders
            except (DataSnapError, OSError) as exc:
                LOGGER.warning(
                    "Confirmacao da importacao falhou na tentativa %s/%s: %s",
                    attempt,
                    len(delays),
                    exc,
                )
                continue

            current = {
                (str(order.num_os), str(order.contract))
                for order in last_orders
            }
            confirmed_count = len(expected.keys() & current)
            LOGGER.info(
                "Importacao apos timeout: %s de %s OS presentes na tentativa %s/%s",
                confirmed_count,
                len(expected),
                attempt,
                len(delays),
            )
            if confirmed_count == len(expected):
                break

        if last_orders is None:
            return None

        current = {
            (str(order.num_os), str(order.contract))
            for order in last_orders
        }
        rows: list[dict] = []
        retry_os_numbers: list[str] = []
        for key, order in expected.items():
            confirmed = key in current
            if not confirmed:
                retry_os_numbers.append(order.os_number)
            rows.append(
                {
                    **order.to_dict(),
                    "import_status": (
                        "PRESENTE NO IMPERIUM; CONFIRMADA APOS RESPOSTA INCOMPLETA"
                        if confirmed
                        else "NAO CONFIRMADA; NAO FOI REENVIADA"
                    ),
                    "imported": confirmed,
                }
            )

        imported = len(rows) - len(retry_os_numbers)
        if imported == 0:
            LOGGER.warning(
                "Importacao apos timeout: nenhuma das %s OS foi confirmada no Imperium",
                len(expected),
            )
            return None

        return {
            "ok": True,
            "count": len(rows),
            "imported": imported,
            "not_imported": len(retry_os_numbers),
            "confirmed": imported,
            "confirmed_after_incomplete_response": True,
            "partial": bool(retry_os_numbers),
            "requires_human": bool(retry_os_numbers),
            "retry_os_numbers": retry_os_numbers,
            "orders": rows,
        }

    def import_toa(self, preview: TOAPreview) -> dict:
        packet = self.import_protocol.build_packet(preview)
        chunks = self.import_protocol.chunks(packet)
        final_timeout = min(300.0, max(180.0, len(preview.orders) * 0.5))
        LOGGER.info(
            "Importacao TOA: enviando %s OS em %s blocos (%s bytes)",
            len(preview.orders),
            len(chunks),
            len(packet),
        )
        with self._operation_lock:
            try:
                payload = self._send_import_packet(chunks, final_timeout)
            except TimeoutError as exc:
                confirmation = self._confirm_import_after_timeout(preview)
                if confirmation is not None:
                    return confirmation
                raise DataSnapError(
                    "O servidor DataSnap nao respondeu a tempo (timeout de importacao) "
                    "e nenhuma OS do lote foi confirmada no Imperium. "
                    "O lote nao sera repetido automaticamente; consulte as OS "
                    "no Imperium antes de tentar novamente"
                ) from exc
        try:
            return self.import_protocol.parse_result(payload, preview)
        except ValueError as exc:
            raise DataSnapError(str(exc)) from exc

    def status(self) -> dict:
        with self._client(timeout=7.0) as client:
            self._handle(client, "TDtmOrdemServico.AS_GetRecords")
        return {
            "ok": True,
            "company": self.company,
            "host": self.host,
            "port": self.port,
            "code": DEFAULT_CODE,
            "description": self.close_codes[DEFAULT_CODE].description,
            "default_code": DEFAULT_CODE,
            "codes": [
                self.close_codes[code].to_dict()
                for code in (
                    "106",
                    "0",
                    "125",
                    "301",
                    "306",
                    "312",
                    "404",
                    "409",
                    "430",
                    "512",
                    "706",
                )
                if code in self.close_codes
            ],
            "service_type": SERVICE_TYPE,
            "status_filter": STATUS,
            "native_creation_enabled": self.native_creation_enabled,
            "native_creation_services": self.native_creation_services(),
        }
