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
import datetime as dt
import re
from pathlib import Path

from toa_import import TOAOrder, TOAPreview


MAX_BULK_ORDERS = 200
DEFAULT_SERVICE = "RETIRADA FORA TOA"

_PROFILE_LOCATIONS = {
    "natal": ("NATAL", "RN", "59000000"),
    "fortaleza": ("FORTALEZA", "CE", "60000000"),
    "mossoro": ("MOSSORO", "RN", "59600000"),
    "recife": ("RECIFE", "PE", "50000000"),
}


def normalize_contracts(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = re.split(r"[\s,;]+", value.strip())
    elif isinstance(value, (list, tuple)):
        candidates = [str(item).strip() for item in value]
    else:
        raise ValueError("Informe os contratos da criacao em massa")

    contracts: list[str] = []
    seen: set[str] = set()
    invalid: list[str] = []
    for candidate in candidates:
        contract = candidate.strip()
        if not contract:
            continue
        if not re.fullmatch(r"\d{7}", contract):
            invalid.append(contract[:30])
            continue
        if contract not in seen:
            seen.add(contract)
            contracts.append(contract)

    if invalid:
        raise ValueError(
            "Contrato invalido; informe 7 digitos: " + ", ".join(invalid[:5])
        )
    if not contracts:
        raise ValueError("Informe pelo menos um contrato")
    if len(contracts) > MAX_BULK_ORDERS:
        raise ValueError(
            f"O limite e de {MAX_BULK_ORDERS} contratos por criacao"
        )
    return tuple(contracts)


def build_bulk_preview(
    contracts: object,
    technician: str,
    profile_key: str,
    *,
    service: str = DEFAULT_SERVICE,
    today: dt.date | None = None,
) -> TOAPreview:
    normalized_contracts = normalize_contracts(contracts)
    technician = " ".join(str(technician).strip().split())
    if not technician:
        raise ValueError("Selecione o tecnico")
    if len(technician.encode("cp1252", errors="ignore")) > 100:
        raise ValueError("O nome do tecnico e muito longo")

    profile_key = str(profile_key).strip().lower()
    try:
        city, state, zip_code = _PROFILE_LOCATIONS[profile_key]
    except KeyError as exc:
        raise ValueError("Perfil invalido para criacao de OS") from exc

    service = " ".join(str(service).strip().split()).upper()
    if not service:
        raise ValueError("Informe o tipo da OS")
    try:
        encoded_service = service.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise ValueError("O tipo da OS possui caracteres nao suportados") from exc
    if len(encoded_service) > 120:
        raise ValueError("O tipo da OS e muito longo")

    order_date = today or dt.date.today()
    date_text = order_date.strftime("%d/%m/%Y")
    orders = tuple(
        TOAOrder(
            date=date_text,
            technician=technician,
            activity_status="AGENDADA",
            address="CADASTRO MANUAL",
            address_complement="",
            district="ADMINISTRATIVO",
            zip_code=zip_code,
            time_window="IMEDIATA",
            city=city,
            state=state,
            contract=contract,
            work_order="",
            node="",
            os_number=f"{contract} {contract}",
            point="",
            os_status="",
            os_type=service,
            close_code="",
            workzone_key="",
        )
        for contract in normalized_contracts
    )
    filename = Path(
        f"cadastro-em-massa-{profile_key}-{order_date:%Y%m%d}.csv"
    ).name
    return TOAPreview(
        filename=filename,
        source_rows=len(orders),
        orders=orders,
    )
