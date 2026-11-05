"""Read-only, fail-closed integration foundation for Imperium Equipamentos Utilizados.

This module owns the contract, offline packet inspection and prepare-only
probe. The separately isolated used_equipment_live_datasnap module now builds
requests byte-identical to the captured ClientVCL and supports bounded,
explicit read-only extraction. Nothing here is wired to the public HTTP UI.
The probe below only calls connect + prepare, never execute.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Callable, Any

CONTRACT_PATH = Path(__file__).with_name("used_equipment_report_contract.json")
PREPARE_METHOD = "TDtmOrdemServico.AS_GetRecords"
PROVIDERS = {"consolidado": "DspConsolidadoEquip", "por_os": "DspConsolidadoOS"}
DATASETS = {"consolidado": "CdsConsolidadoEquip", "por_os": "CdsConsolidadoOS"}
PARAM_NAMES = (
    "@RETURN_VALUE", "@DataIni", "@DataFim", "@IdParceiro",
    "@IdTipoServico", "@IdGrupoEquipamento",
)
EXPECTED_TYPES = {
    "@RETURN_VALUE": 0, "@DataIni": 7, "@DataFim": 7,
    "@IdParceiro": 3, "@IdTipoServico": 8, "@IdGrupoEquipamento": 8,
}
PARAM_MARKER = bytes.fromhex("0c20000001000000000000000600000008000000")
END_MARKER = bytes.fromhex("1000050200000000c0")
PROFILE_PORTS = {"natal": 212, "fortaleza": 596, "mossoro": 579, "recife": 599}


class LiveReportNotValidated(RuntimeError):
    """A safe refusal, never to be converted to a successful empty report."""


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (data.get("form") != "TFrmConEquipUtilizados"
            or data.get("server_class") != "TDtmOrdemServico"
            or data.get("prepare_only_method") != PREPARE_METHOD):
        raise ValueError("Contrato não corresponde ao formulário de Equipamentos Utilizados")
    modes = data.get("dataset_modes")
    if not isinstance(modes, dict) or set(modes) != set(PROVIDERS):
        raise ValueError("Modos DataSnap divergentes")
    for mode, provider in PROVIDERS.items():
        if (modes[mode].get("provider") != provider
                or modes[mode].get("client_dataset") != DATASETS[mode]
                or not modes[mode].get("columns")):
            raise ValueError("Dataset/provedor inesperado: " + mode)
    params = data.get("params")
    if not isinstance(params, list) or tuple(p.get("name") for p in params) != PARAM_NAMES:
        raise ValueError("Parâmetros DataSnap divergentes")
    return data


def normalize_range(start: str, end: str, *, today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("Informe data inicial e final")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
        raise ValueError("Formato de data inválido")
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    limit = today or dt.date.today()
    if first > last or last > limit or (last-first).days > 30:
        raise ValueError("Período futuro, invertido ou maior que 31 dias")
    return first, last


def validate_capture_packet(packet: bytes, mode: str) -> dict:
    """Inspect a REAL capture offline. This never sends it to the network.

    The presence of a plausible envelope is NOT proof the report will work.
    """
    if mode not in PROVIDERS:
        raise ValueError("Modo de relatório inválido")
    if not isinstance(packet, bytes) or len(packet) > 65536 or len(packet) < 120:
        raise ValueError("Pacote binário ausente ou fora dos limites")
    provider_length = packet[0] - 32
    provider = PROVIDERS[mode].encode("ascii")
    if provider_length != len(provider) or packet[1:1+provider_length] != provider:
        raise ValueError("Provedor não corresponde à tela de equipamentos utilizados")
    if packet[1+provider_length:6+provider_length] != b"!\x01\x60a\x01":
        raise ValueError("Envelope DataSnap inesperado")
    if not packet.endswith(END_MARKER):
        raise ValueError("Pacote DataSnap incompleto")
    positions = [m.start() for m in re.finditer(re.escape(PARAM_MARKER), packet)]
    if len(positions) != len(PARAM_NAMES):
        raise ValueError("Quantidade de parâmetros diferente do contrato")
    types: dict[str,int] = {}
    for index, position in enumerate(positions):
        pos = position + len(PARAM_MARKER)
        if pos + 4 > len(packet):
            raise ValueError("Parâmetro incompleto")
        length = struct.unpack_from("<I",packet,pos)[0]
        if length < 1 or length > 50 or pos+4+2*length+4 > len(packet):
            raise ValueError("Comprimento do nome inválido")
        name = packet[pos+4:pos+4+2*length].decode("utf-16le")
        kind = struct.unpack_from("<I",packet,pos+4+2*length)[0]
        if name != PARAM_NAMES[index] or kind != EXPECTED_TYPES[name]:
            raise ValueError("Nome ou tipo de parâmetro não corresponde ao contrato")
        types[name] = kind
    return {"mode":mode,"provider":PROVIDERS[mode],
            "parameter_names":tuple(types),"sha256":hashlib.sha256(packet).hexdigest(),
            "status":"offline_envelope_only"}


def check_executable(path: Path, contract: dict | None = None) -> dict:
    """Compare installed ClientVCL version with the supplied ZIP evidence."""
    info = contract or load_contract()
    path = Path(path)
    if path.stat().st_size > 100_000_000:
        raise ValueError("Executable fora do tamanho permitido")
    data = path.read_bytes()
    if not data.startswith(b"MZ"):
        raise ValueError("Não é executável Windows")
    markers = (b"TFrmConEquipUtilizados",b"CdsConsolidadoEquip",b"CdsConsolidadoOS",
               b"DspConsolidadoEquip",b"DspConsolidadoOS")
    digest=hashlib.sha256(data).hexdigest()
    return {"bytes":len(data),"sha256":digest,
            "same_version_as_zip":digest==info["evidence_executable_sha256"],
            "required_markers_present":all(m in data for m in markers)}


def probe_prepare_only(profile: str, username: str, password: str, *,
                       client_factory: Callable[...,Any] | None = None,
                       timeout: float = 12.) -> dict:
    """Authentication + prepare only. No AS_GetRecords execute is issued."""
    load_contract()
    if profile not in PROFILE_PORTS:
        raise ValueError("Praça não autorizada")
    if not username or not password:
        raise ValueError("Credenciais vazias")
    if not 1 <= timeout <= 30:
        raise ValueError("Timeout fora do limite")
    if client_factory is None:
        from datasnap_client import DataSnapClient
        from imperium_api import HOST
        client_factory = DataSnapClient
    else:
        HOST = "injected-test-host"
    with client_factory(HOST, PROFILE_PORTS[profile], username, password, timeout=timeout) as client:
        response = client.prepare(PREPARE_METHOD)
    handle = response.get("result", [{}])[0].get("handle", [])
    if not handle or not isinstance(handle[0], int):
        raise ValueError("Método não preparado pelo DataSnap")
    return {"authenticated":True,"method_prepared":True,"provider_payload_verified":False,
            "query_executed":False,"report_downloaded":False}


def require_live_report_capture(*_args,**_kwargs) -> None:
    """Guard the legacy six-sheet UI until full workflow is homologated."""
    raise LiveReportNotValidated(
        "As duas consultas reais de Equipamentos Utilizados já foram capturadas "
        "e validadas. Falta integrar os dados na análise diária, conferir as seis "
        "abas com o fluxo Atlas e homologar permissões, histórico e download. "
        "O histórico salvo não equivale a uma extração ao vivo."
    )
