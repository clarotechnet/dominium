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
import argparse
import base64
import csv
import datetime as dt
import difflib
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import re
import secrets
import socket
import threading
import time
import unicodedata
import webbrowser
from collections import Counter
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from api_security import (
    LOCAL_RATE_LIMITER,
    SECURITY_HEADERS,
    rate_limit_for,
    redact_log_text,
    validate_local_request,
)
from auth_store import AuthError, AuthStore
from bulk_orders import DEFAULT_SERVICE, build_bulk_preview
from close_report import CloseReportStore
from close_report_excel import (
    build_close_report_xlsx,
    format_equipment_readable,
    format_materials_readable,
)
from datasnap_client import DataSnapError, load_credentials
from disconnect_automation import DisconnectAutomation
from edge_voice import EDGE_VOICE, EdgeVoiceError
from imperium_http_api import (
    ImperiumHTTPClient,
    ImperiumHTTPError,
    ImperiumHTTPUncertainError,
)
from imperium_api import (
    CAPTURED_CONTROLLER_ID,
    CloseCode,
    CloseConfirmationUncertainError,
    ImperiumAPI,
    MaterialTransferUncertainError,
    Order,
)
from official_close import build_manual_official_plan
from operation_scope import (
    ImportScope,
    OSIdentity,
    OSSnapshot,
    OperationBlocked,
    OperationCoordinator,
    PlannedClose,
    ProjectIdentity,
    validate_payload_scope,
)
from operations_intelligence import (
    HealthCheckService,
    audit_serial_assignments,
    build_intelligence_snapshot,
    render_daily_pdf,
)
from operational_store import OperationalStore
from serialized_transfer import SerializedTransferUncertainError
from stock_pdf import build_stock_pdf, safe_pdf_filename
from technician_directory import TechnicianDirectory, normalize as normalize_technician
from toa_datalake_store import TOADatalakeStore
from toa_automation import TOAAutomation
from toa_capture_panel import TOACaptureCatalog
from toa_context import PROFILE_ROUTES, TOAContextIndex
from toa_connector import TOAConnector
from toa_contract_registry import TOAContractRegistry
from toa_agenda import parse_agenda
from toa_import import (
    parse_toa_csv,
    parse_toa_timeline_activities,
    unpack_toa_content,
)
from toa_inventory import parse_toa_clipboard
from toa_live import TOALiveSession
from toa_local_collector import TOALocalCollector
from toa_bridge_server import ToaBridgeServer


ROOT = Path(__file__).resolve().parent
PROJECT_IDENTITY = ProjectIdentity.load(ROOT)
STATIC_ROOT = ROOT / "static"
LOG_ROOT = ROOT / "logs"
LOG_ROOT.mkdir(parents=True, exist_ok=True)
TECHNICIANS = TechnicianDirectory(ROOT / "config" / "technicians.json")
TOA_CONTEXT = TOAContextIndex(ROOT, TECHNICIANS.resolve)
TOA_CAPTURE_CATALOG = TOACaptureCatalog(ROOT)
TOA_CONTRACTS = TOAContractRegistry(ROOT / "config" / "toa_contract_registry.json")
TOA_LIVE_TECHNICIAN_LOCK = threading.RLock()
TOA_LIVE_TECHNICIANS: dict[tuple[str, str, str], dict] = {}
TOA_LIVE_TECHNICIAN_TTL_SECONDS = 30 * 60
OPERATIONAL_STORE = OperationalStore(
    ROOT / "data" / "dominium_operacional.sqlite3",
    ROOT / "data" / "dominium_operacional.json",
)
DATABASE_URL = os.environ.get("DOMINIUM_DATABASE_URL", "").strip()
AUTH_BACKEND = os.environ.get("DOMINIUM_AUTH_BACKEND", "").strip().lower()
if not AUTH_BACKEND:
    AUTH_BACKEND = "postgres" if DATABASE_URL else "sqlite"
if AUTH_BACKEND == "supabase":
    from supabase_auth_store import SupabaseAuthStore

    AUTH_STORE = SupabaseAuthStore.from_environment()
elif AUTH_BACKEND in {"postgres", "postgresql"}:
    if not DATABASE_URL:
        raise RuntimeError("DOMINIUM_DATABASE_URL e obrigatoria para o backend PostgreSQL")
    from auth_store_postgres import PostgresAuthStore

    AUTH_STORE = PostgresAuthStore(DATABASE_URL)
elif AUTH_BACKEND == "sqlite":
    AUTH_STORE = AuthStore(ROOT / "data" / "dominium_auth.sqlite3")
else:
    raise RuntimeError(f"DOMINIUM_AUTH_BACKEND invalido: {AUTH_BACKEND}")


def _env_enabled(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _web_mode_enabled() -> bool:
    return _env_enabled("DOMINIUM_WEB_MODE")


def _registration_enabled() -> bool:
    return _env_enabled(
        "DOMINIUM_ALLOW_REGISTRATION",
        default=not _web_mode_enabled(),
    )


def _bootstrap_enabled() -> bool:
    return _env_enabled(
        "DOMINIUM_ALLOW_WEB_BOOTSTRAP",
        default=not _web_mode_enabled(),
    )


def _auth_public_state() -> dict[str, bool]:
    bootstrap_required = not AUTH_STORE.has_users()
    return {
        "bootstrap_required": bootstrap_required,
        "bootstrap_allowed": bootstrap_required and _bootstrap_enabled(),
        "registration_enabled": _registration_enabled(),
    }
TOA_DATALAKE = TOADatalakeStore(ROOT / "data" / "toa_datalake.sqlite3")
DISCONNECT_AUTOMATION = DisconnectAutomation(
    ROOT / "config" / "disconnect_automation_state.json"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger("imperium")


def _repair_catalog_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _load_official_close_codes() -> dict[str, CloseCode]:
    path = (
        ROOT
        / "config"
        / "official_close_code_catalog"
        / "Tabela_codigo_baixa0711.catalog.json"
    )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Catalogo oficial de codigos indisponivel: %s", exc)
        return {}

    definitions: dict[str, CloseCode] = {}
    for entry in document.get("entries", []):
        if not isinstance(entry, dict) or entry.get("status") != "valid":
            continue
        code = str(entry.get("code") or "").strip()
        description = _repair_catalog_text(entry.get("description"))
        if not re.fullmatch(r"\d{3}", code) or not description:
            continue
        category = _repair_catalog_text(entry.get("category"))
        definitions[code] = CloseCode(
            code=code,
            wire_code=code,
            description=description,
            id_code=0,
            suffixes=(),
            productive=normalize_technician(category) != "IMPRODUTIVOS",
        )
    return definitions


OFFICIAL_CLOSE_CODES = _load_official_close_codes()


def _resolve_close_definition(
    profile: "ProfileRuntime",
    code: str,
    transport: str,
) -> CloseCode:
    try:
        return profile.api.close_code(code)
    except ValueError:
        if transport == "official_http" and code in OFFICIAL_CLOSE_CODES:
            return OFFICIAL_CLOSE_CODES[code]
        raise


def _merged_close_code_metadata(profile: "ProfileRuntime") -> list[dict]:
    definitions = {
        code: definition.to_dict()
        for code, definition in OFFICIAL_CLOSE_CODES.items()
    }
    for definition in profile.api.close_codes.values():
        definitions[definition.code] = definition.to_dict()

    def sort_key(item: dict) -> tuple[int, str]:
        code = str(item.get("code") or "")
        return (int(code) if code.isdigit() else 999999, code)

    return sorted(definitions.values(), key=sort_key)


TOA_LIVE = TOALiveSession(ROOT, logger=LOGGER)
TOA_CONNECTOR = TOAConnector(ROOT, TOA_LIVE)
TOA_LOCAL_COLLECTOR: TOALocalCollector | None = None
TOA_BRIDGE_SERVER: ToaBridgeServer | None = None
if __name__ == "__main__":
    FILE_HANDLER = logging.FileHandler(
        LOG_ROOT / "painel.log",
        encoding="utf-8",
    )
    FILE_HANDLER.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    LOGGER.addHandler(FILE_HANDLER)


class InstallerMismatchUnresolvedError(ValueError):
    code = "installer_mismatch_unresolved"


class InstallerReassignmentFailedError(ValueError):
    code = "installer_reassignment_failed"


class InstallerReassignmentUnconfirmedError(ValueError):
    code = "installer_reassignment_unconfirmed"


@dataclass
class ProfileRuntime:
    key: str
    label: str
    port: int
    controller_id: int | None
    log_root: Path
    api: ImperiumAPI = field(init=False)
    order_cache: dict[int, Order] = field(default_factory=dict)
    installer_overrides: dict[int, str] = field(default_factory=dict)
    cache_date: dt.date | None = None
    cache_generation: int = 0
    cache_lock: threading.RLock = field(default_factory=threading.RLock)
    failure_date: dt.date = field(default_factory=dt.date.today)
    failure_cache: dict[int, dict] = field(default_factory=dict)
    failure_lock: threading.RLock = field(default_factory=threading.RLock)
    close_report: CloseReportStore = field(init=False)
    operations: OperationCoordinator = field(init=False)
    _stock_technicians_cache: tuple[float, list[dict]] | None = None

    def __post_init__(self) -> None:
        self.log_root.mkdir(parents=True, exist_ok=True)
        self.api = ImperiumAPI(
            ROOT,
            port=self.port,
            company=self.label,
            profile_key=self.key,
            controller_id=self.controller_id or CAPTURED_CONTROLLER_ID,
            log_root=self.log_root,
        )
        self.close_report = CloseReportStore(self.log_root, self.key)
        self.operations = OperationCoordinator(PROJECT_IDENTITY)

    @property
    def close_enabled(self) -> bool:
        return self.controller_id is not None

    @property
    def material_writeoff_enabled(self) -> bool:
        # The captured correction packet is validated only for Natal.
        return self.key == "natal" and self.close_enabled

    @property
    def native_creation_enabled(self) -> bool:
        return self.close_enabled and self.api.native_creation_enabled

    @property
    def installer_change_enabled(self) -> bool:
        return self.close_enabled and self.api.installer_change_enabled

    @property
    def serialized_transfer_enabled(self) -> bool:
        return self.close_enabled and self.api.serialized_transfer_enabled

    def public_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "project": PROJECT_IDENTITY.to_dict(),
            "close_enabled": self.close_enabled,
            "material_writeoff_enabled": self.material_writeoff_enabled,
            "native_creation_enabled": self.native_creation_enabled,
            "installer_change_enabled": self.installer_change_enabled,
            "serialized_transfer_enabled": self.serialized_transfer_enabled,
            "official_close_enabled": (
                ROOT / "config" / "imperium_http_credentials.dat"
            ).is_file(),
            "native_creation_services": self.api.native_creation_services(),
        }


PROFILE_SPECS = (
    ("natal", "NATAL / PARNAMIRIM", 212, 313101, LOG_ROOT),
    ("fortaleza", "FORTALEZA", 596, 49127, LOG_ROOT / "fortaleza"),
    ("mossoro", "MOSSORÓ", 579, 20857, LOG_ROOT / "mossoro"),
    ("recife", "RECIFE", 599, 1766, LOG_ROOT / "recife"),
)
PROFILES = {
    key: ProfileRuntime(key, label, port, controller_id, log_root)
    for key, label, port, controller_id, log_root in PROFILE_SPECS
}
HEALTH_CHECK = HealthCheckService()
DEFAULT_PROFILE = "natal"
OPERATION_GATE = threading.Lock()
IMPORT_AUDIT_LOCK = threading.Lock()
MATERIAL_ASSIGNMENT_LOCK = threading.Lock()
WRITE_OFF_REQUESTS_LOCK = threading.Lock()
WRITE_OFF_REQUESTS: dict[tuple[str, str], dict] = {}
WRITE_OFF_UNCERTAIN: dict[tuple[str, int, tuple[int, ...]], str] = {}
BULK_CREATE_REQUESTS_LOCK = threading.Lock()
BULK_CREATE_REQUESTS: dict[tuple[str, str], dict] = {}
INSTALLER_CHANGE_REQUESTS_LOCK = threading.Lock()
INSTALLER_CHANGE_REQUESTS: dict[tuple[str, str], dict] = {}
SERIAL_TRANSFER_LOCK = threading.Lock()
SERIAL_TRANSFER_PREVIEWS: dict[tuple[str, str], dict] = {}
SERIAL_TRANSFER_REQUESTS: dict[tuple[str, str], dict] = {}
SERIAL_TRANSFER_PREVIEW_TTL = 10 * 60
OFFICIAL_HTTP_CREDENTIALS = ROOT / "config" / "imperium_http_credentials.dat"
OFFICIAL_HTTP_LOCK = threading.RLock()
OFFICIAL_HTTP_CLIENTS: dict[str, ImperiumHTTPClient] = {}
CLOSE_CONFIRM_LOCK = threading.RLock()
CLOSE_CONFIRM_RUNNING: set[tuple[str, str]] = set()
IMPORT_TARGETS = (
    {
        "key": "rn",
        "label": "RN",
        "profile": "natal",
        "description": "Natal e Parnamirim",
        "routes": ("NTL", "PWM"),
    },
    {
        "key": "ftz",
        "label": "FTZ",
        "profile": "fortaleza",
        "description": "Rota Fortaleza",
        "routes": ("FTZ",),
    },
    {
        "key": "jcr",
        "label": "JCR",
        "profile": "recife",
        "description": "Rota Recife",
        "routes": ("JCR",),
    },
    {
        "key": "mro",
        "label": "MRO",
        "profile": "mossoro",
        "description": "Rota Mossoro",
        "routes": ("MRO",),
    },
)
IMPORT_TARGET_BY_KEY = {target["key"]: target for target in IMPORT_TARGETS}


# =============================================================================
# TOA -> IMPERIUM | PREVIA, ESCOPO E PREPARACAO DA IMPORTACAO DE O.S.
# =============================================================================
def _scoped_import_preview(
    content: bytes,
    filename: str,
    profile: ProfileRuntime,
    *,
    batch_id: str = "",
):
    content, filename = unpack_toa_content(content, filename)
    scope = ImportScope.from_source(filename, content, batch_id=batch_id)
    scope.validate_target(profile.key, scope.expected_city)
    preview = TECHNICIANS.enrich_preview(parse_toa_csv(content, filename))
    blockers: list[str] = []
    scoped_orders = []
    scope_exclusions = list(preview.scope_exclusions)
    for order in preview.orders:
        try:
            scope.validate_target(profile.key, order.city)
        except OperationBlocked as exc:
            if exc.blockers == ("city_scope_mismatch",):
                scope_exclusions.append(
                    {
                        "os_number": order.os_number,
                        "contract": order.contract,
                        "city": order.city,
                        "state": order.state,
                        "service": order.os_type,
                        "reason": "city_scope_mismatch",
                    }
                )
                continue
            blockers.extend(exc.blockers)
            continue
        scoped_orders.append(order)
    if not scoped_orders:
        blockers.append("city_scope_mismatch")
    if blockers:
        raise OperationBlocked(blockers)
    if scope_exclusions:
        LOGGER.warning(
            "[%s] Importacao %s: %s OS fora do escopo foram excluidas do lote",
            profile.label,
            filename,
            len(scope_exclusions),
        )
    return replace(
        preview,
        orders=tuple(scoped_orders),
        import_scope=scope,
        scope_exclusions=tuple(scope_exclusions),
    )


def _parse_import_request(
    body: dict,
    *,
    require_approval: bool = False,
) -> tuple[dict, ProfileRuntime, object]:
    target_key = str(body.get("target", "")).strip().lower()
    target = IMPORT_TARGET_BY_KEY.get(target_key)
    if target is None:
        raise ValueError("Destino de importacao invalido")
    profile = PROFILES[target["profile"]]
    filename = Path(str(body.get("filename", "atividades.csv"))).name
    if not (filename.lower().endswith(".csv") or filename.lower().endswith(".zip")):
        raise ValueError("Selecione um arquivo CSV ou ZIP exportado pelo TOA")
    encoded = str(body.get("content_base64", ""))
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("O conteudo do arquivo e invalido") from exc
    preview = _scoped_import_preview(
        content,
        filename,
        profile,
        batch_id=str(body.get("batch_id", "")).strip(),
    )
    scope = preview.import_scope
    if scope is None:
        raise OperationBlocked(("shared_state_contamination",))
    if require_approval:
        if str(body.get("approved_source_hash", "")).strip() != scope.source_hash:
            raise OperationBlocked(("source_file_changed",))
        if str(body.get("approved_batch_id", "")).strip() != scope.batch_id:
            raise OperationBlocked(("shared_state_contamination",))
    only_os_numbers = body.get("only_os_numbers")
    if only_os_numbers is not None:
        if not isinstance(only_os_numbers, list) or not only_os_numbers:
            raise ValueError("A lista de OS para reprocessar e invalida")
        requested = {
            str(value).strip() for value in only_os_numbers if str(value).strip()
        }
        available = {order.os_number for order in preview.orders}
        if not requested or not requested <= available:
            raise ValueError("Uma OS solicitada nao pertence a este CSV")
        preview = replace(
            preview,
            orders=tuple(
                order for order in preview.orders if order.os_number in requested
            ),
        )
    return target, profile, preview


MONITOR_SNAPSHOT_ROOT = LOG_ROOT / "monitor-snapshots"
MONITOR_SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
MONITOR_SNAPSHOT_LOCK = threading.RLock()


# =============================================================================
# TOA | SNAPSHOTS, DATALAKE E MONITORAMENTO OPERACIONAL
# =============================================================================
def _monitor_snapshot_path(profile: ProfileRuntime) -> Path:
    return MONITOR_SNAPSHOT_ROOT / f"{profile.key}.json"


def _monitor_order_dict(order, source_file: str = "") -> dict:
    """Keep only operational TOA fields required by the monitor."""
    technician = order.technician_name or order.technician
    service = order.service_name or order.activity_type or order.os_type
    return {
        "id_os": f"{order.activity_id or order.work_order}:{order.os_number}",
        "num_os": order.os_number,
        "contract": order.contract,
        "service": service,
        "toa_status": order.activity_status,
        "toa_os_status": order.os_status,
        "technician": technician,
        "technician_login": order.technician_login or order.technician,
        "city": order.city,
        "district": order.district,
        "node": order.node,
        "close_code": order.close_code,
        "date": order.date,
        "time_window": order.time_window,
        "service_window": order.service_window,
        "started_at": order.started_at,
        "ended_at": order.ended_at,
        "start_end": order.start_end,
        "sla_start": order.sla_start,
        "sla_end": order.sla_end,
        "duration": order.duration,
        "travel_time": order.travel_time,
        "assignment_time": order.assignment_time,
        "reservation_time": order.reservation_time,
        "activity_type": order.activity_type,
        "work_area": order.work_area,
        "coordinate_x": order.coordinate_x,
        "coordinate_y": order.coordinate_y,
        "activity_id": order.activity_id,
        "read_only": True,
        "source": "monitor_csv",
        "source_file": source_file,
    }


def _monitor_timeline_dict(activity, source_file: str = "") -> dict:
    technician = TECHNICIANS.resolve(activity.technician)
    technician_name = technician["name"] if technician else activity.technician
    timeline_id = (
        f"timeline:{source_file}:{activity.technician}:{activity.source_row}"
    )
    return {
        "id_os": timeline_id,
        "num_os": "",
        "contract": "",
        "service": activity.label,
        "toa_status": activity.activity_status,
        "technician": technician_name,
        "technician_login": activity.technician,
        "date": activity.date,
        "time_window": activity.time_window,
        "service_window": activity.service_window,
        "started_at": activity.started_at,
        "ended_at": activity.ended_at,
        "start_end": activity.start_end,
        "duration": activity.duration,
        "travel_time": "00:00",
        "activity_id": timeline_id,
        "auxiliary_type": "meal",
        "is_auxiliary": True,
        "read_only": True,
        "source": "monitor_csv",
        "source_file": source_file,
    }


def _monitor_profile_for_source(filename: str, content: bytes) -> ProfileRuntime:
    """Resolve the read-only Monitor destination from the official TOA filename."""
    scope = ImportScope.from_source(Path(filename).name, content)
    try:
        return PROFILES[scope.expected_profile_key]
    except KeyError as exc:
        raise OperationBlocked(("profile_scope_mismatch",)) from exc


def _monitor_order_key(order: dict) -> tuple[str, ...]:
    activity_id = str(order.get("activity_id", "")).strip().upper()
    common = (
        str(order.get("num_os", "")).strip().upper(),
        str(order.get("technician_login", "")).strip().upper(),
        str(order.get("contract", "")).strip().upper(),
        str(order.get("city", "")).strip().upper(),
    )
    if activity_id:
        return ("activity", activity_id, *common)
    return (
        "fallback",
        *common,
        str(order.get("date", "")).strip().upper(),
        str(order.get("service", "")).strip().upper(),
    )


def _monitor_timeline_key(activity: dict) -> tuple[str, ...]:
    return tuple(
        str(activity.get(field, "")).strip().upper()
        for field in (
            "technician_login",
            "date",
            "started_at",
            "ended_at",
            "service",
            "toa_status",
        )
    )


def _build_monitor_snapshot_batch(
    profile: ProfileRuntime,
    sources: list[tuple[str, bytes]] | tuple[tuple[str, bytes], ...],
    *,
    persist: bool = True,
) -> dict:
    if not sources:
        raise ValueError("Selecione ao menos um arquivo CSV exportado pelo TOA")

    source_files: list[str] = []
    source_rows = 0
    excluded_count = 0
    order_index: dict[tuple[str, ...], dict] = {}
    timeline_index: dict[tuple[str, ...], dict] = {}

    for filename, content in sources:
        content, safe_filename = unpack_toa_content(content, Path(filename).name)
        if not safe_filename.lower().endswith(".csv"):
            raise ValueError("Selecione apenas arquivos CSV ou ZIP exportados pelo TOA")
        if safe_filename not in source_files:
            source_files.append(safe_filename)
        preview = _scoped_import_preview(content, safe_filename, profile)
        source_rows += preview.source_rows
        excluded_count += len(preview.scope_exclusions)
        for parsed_order in preview.orders:
            order = _monitor_order_dict(parsed_order, safe_filename)
            order_index[_monitor_order_key(order)] = order

        allowed_technicians = {
            str(order.technician or order.technician_login).strip().upper()
            for order in preview.orders
            if str(order.technician or order.technician_login).strip()
        }
        for parsed_activity in parse_toa_timeline_activities(content):
            if parsed_activity.technician.strip().upper() not in allowed_technicians:
                continue
            activity = _monitor_timeline_dict(parsed_activity, safe_filename)
            timeline_index[_monitor_timeline_key(activity)] = activity

    orders = list(order_index.values())
    timeline_activities = list(timeline_index.values())
    assignments_by_os: dict[str, list[dict]] = {}
    for order in orders:
        os_number = str(order.get("num_os", "")).strip()
        if os_number:
            assignments_by_os.setdefault(os_number, []).append(order)
    reallocation_count = sum(
        1
        for assignments in assignments_by_os.values()
        if len({
            str(item.get("technician_login", "")).strip().upper()
            for item in assignments
            if str(item.get("technician_login", "")).strip()
        }) > 1
        and any(
            normalize_technician(item.get("toa_status")) == "SUSPENSO"
            for item in assignments
        )
    )
    activity_keys = {
        str(order.get("activity_id") or order.get("id_os")) for order in orders
    }
    statuses = Counter(
        str(order.get("toa_status", "")).strip() for order in orders
        if str(order.get("toa_status", "")).strip()
    )
    dates = Counter(
        str(order.get("date", "")).strip() for order in orders
        if str(order.get("date", "")).strip()
    )
    snapshot = {
        "schema_version": 2,
        "profile": profile.key,
        "filename": source_files[0] if len(source_files) == 1 else f"{len(source_files)} arquivos TOA",
        "source_files": source_files,
        "uploaded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_rows": source_rows,
        "order_count": len(assignments_by_os),
        "assignment_count": len(orders),
        "historical_assignment_count": len(orders) - len(assignments_by_os),
        "reallocation_count": reallocation_count,
        "suspended_activity_count": len({
            str(order.get("activity_id") or order.get("id_os"))
            for order in orders
            if normalize_technician(order.get("toa_status")) == "SUSPENSO"
        }),
        "activity_count": len(activity_keys),
        "timeline_activity_count": len(timeline_activities),
        "statuses": dict(sorted(statuses.items())),
        "dates": dict(sorted(dates.items())),
        "excluded_count": excluded_count,
        "orders": orders,
        "timeline_activities": timeline_activities,
    }
    if persist:
        _persist_monitor_snapshot(profile, snapshot)
    return snapshot


def _persist_monitor_snapshot(profile: ProfileRuntime, snapshot: dict) -> None:
    path = _monitor_snapshot_path(profile)
    temporary = path.with_suffix(".tmp")
    with MONITOR_SNAPSHOT_LOCK:
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
    LOGGER.info(
        "[%s] Monitor atualizado por CSV: %s OS unicas, %s alocacoes, %s atividades + %s blocos de apoio (%s)",
        profile.label,
        snapshot["order_count"],
        snapshot["assignment_count"],
        snapshot["activity_count"],
        snapshot["timeline_activity_count"],
        ", ".join(snapshot.get("source_files", [])),
    )
    try:
        OPERATIONAL_STORE.ingest_monitor_snapshot(profile.key, snapshot)
    except Exception:
        LOGGER.exception("[%s] Falha ao atualizar a base operacional", profile.label)


def _record_operational_orders(profile: ProfileRuntime, rows: list[dict]) -> None:
    try:
        OPERATIONAL_STORE.ingest_imperium_orders(profile.key, rows)
    except Exception:
        LOGGER.exception("[%s] Falha ao registrar ordens na base operacional", profile.label)


def _record_operational_toa_capture(
    profile: ProfileRuntime,
    result: dict,
) -> None:
    capture_file = str(result.get("capture_file") or "").strip()
    if not capture_file:
        return
    path = (ROOT / capture_file).resolve()
    try:
        path.relative_to((ROOT / "logs" / "toa-captures").resolve())
        payload = json.loads(path.read_text(encoding="utf-8"))
        OPERATIONAL_STORE.ingest_toa_capture(
            profile.key,
            payload,
            source="toa_live",
        )
    except Exception:
        LOGGER.exception(
            "[%s] Falha ao registrar captura TOA na base operacional",
            profile.label,
        )


def _record_live_technician_evidence(
    profile: ProfileRuntime,
    result: dict,
) -> None:
    """Keep short-lived, server-side evidence from an authenticated TOA lookup.

    The browser never becomes the source of truth for the technician login.  We
    bind the login returned by TOA to the exact contract + OS task so the
    official Imperium request can reuse it even when today's CSV was not
    exported yet.
    """
    now = time.time()
    records: dict[tuple[str, str, str], dict] = {}
    for capture in result.get("results") or ():
        if not isinstance(capture, dict):
            continue
        contract = "".join(re.findall(r"\d", str(capture.get("contract") or "")))
        technician = capture.get("assigned_technician")
        technician = technician if isinstance(technician, dict) else {}
        login = str(
            technician.get("external_id") or technician.get("login") or ""
        ).strip().upper()
        name = str(technician.get("name") or "").strip()
        activity_id = str(capture.get("aid") or capture.get("activity_id") or "").strip()
        route_value = capture.get("route_provider")
        route_value = route_value if isinstance(route_value, dict) else {}
        route = str(
            route_value.get("name")
            or route_value.get("external_id")
            or capture.get("route")
            or ""
        ).strip().upper()
        allowed_routes = PROFILE_ROUTES.get(profile.key, ())
        route_allowed = any(
            route == prefix or route.startswith(f"{prefix}-")
            for prefix in allowed_routes
        )
        if (
            not contract
            or not activity_id
            or not re.fullmatch(r"Z\d+", login)
            or not name
            or not route_allowed
        ):
            continue
        for task in capture.get("tasks") or ():
            if not isinstance(task, dict):
                continue
            os_number = "".join(re.findall(
                r"\d",
                str(task.get("os_number") or task.get("num_os") or ""),
            ))
            if not os_number:
                continue
            key = (profile.key, contract, os_number)
            records[key] = {
                "profile_key": profile.key,
                "contract": contract,
                "os_number": os_number,
                "activity_id": activity_id,
                "technician_login": login,
                "technician_name": name,
                "route": route,
                "captured_at": now,
            }
    if not records:
        return
    with TOA_LIVE_TECHNICIAN_LOCK:
        expired_before = now - TOA_LIVE_TECHNICIAN_TTL_SECONDS
        for key, evidence in list(TOA_LIVE_TECHNICIANS.items()):
            if float(evidence.get("captured_at") or 0) < expired_before:
                TOA_LIVE_TECHNICIANS.pop(key, None)
        TOA_LIVE_TECHNICIANS.update(records)


def _live_technician_evidence(
    profile: ProfileRuntime,
    order: Order,
) -> dict | None:
    key = (str(getattr(profile, "key", "")), order.contract, order.num_os)
    now = time.time()
    with TOA_LIVE_TECHNICIAN_LOCK:
        evidence = TOA_LIVE_TECHNICIANS.get(key)
        if evidence is None:
            return None
        if now - float(evidence.get("captured_at") or 0) > TOA_LIVE_TECHNICIAN_TTL_SECONDS:
            TOA_LIVE_TECHNICIANS.pop(key, None)
            return None
        return dict(evidence)


def _sync_operational_close_reports() -> None:
    for profile in PROFILES.values():
        try:
            records = profile.close_report.list(dt.date.today())
            OPERATIONAL_STORE.ingest_close_attempts(profile.key, records)
        except Exception:
            LOGGER.exception(
                "[%s] Falha ao sincronizar baixas na base operacional",
                profile.label,
            )


def _bootstrap_operational_store() -> None:
    _sync_operational_close_reports()
    capture_root = ROOT / "logs" / "toa-captures" / "live"
    try:
        registry_records = TOA_CONTRACTS.public_state().get("records", [])
        captures = sorted(
            capture_root.glob("*/*.json"),
            key=lambda path: path.stat().st_mtime,
        )[-1000:]
        for path in captures:
            if not path.name.startswith("toa-live-"):
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            contracts = {
                str(item.get("contract") or "").strip()
                for item in payload.get("os_list") or []
                if isinstance(item, dict)
            }
            profile_key = "natal"
            for contract in contracts:
                match = next(
                    (
                        record for record in registry_records
                        if record.get("contract") == contract
                    ),
                    None,
                )
                if match and match.get("profile") in PROFILES:
                    profile_key = str(match["profile"])
                    break
            OPERATIONAL_STORE.ingest_toa_capture(
                profile_key,
                payload,
                source="toa_capture_archive",
                export=False,
            )
        OPERATIONAL_STORE.export_json()
    except Exception:
        LOGGER.exception("Falha ao reconstruir a base operacional local")


def _sync_datalake_to_operational(payload: dict) -> None:
    """Projeta o espelho incremental na Base operacional já exibida no painel."""
    explicit_profile = str(payload.get("profile") or "").strip().lower()
    feed = TOA_DATALAKE.feed(profile=explicit_profile)
    grouped: dict[str, list[dict]] = {}
    for row in feed.get("orders") or []:
        profile = str(row.get("profile") or explicit_profile or "other").strip().lower()
        grouped.setdefault(profile, []).append(row)
    for profile, rows in grouped.items():
        OPERATIONAL_STORE.ingest_monitor_snapshot(
            profile,
            {"orders": rows, "uploaded_at": feed.get("loadedAt")},
        )

    for raw in payload.get("details") or payload.get("detalhes") or []:
        if not isinstance(raw, dict):
            continue
        identifier = "".join(re.findall(
            r"\d",
            str(raw.get("contract") or raw.get("contrato") or raw.get("activity_id")
                or raw.get("atividade_id") or raw.get("id") or ""),
        ))
        if not identifier:
            continue
        record = TOA_DATALAKE.record(identifier)
        inventory: list[dict] = []
        pool_by_category = {
            "installed": "install", "removed": "remove",
            "customer": "customer", "material": "material",
        }
        for category, items in (record.get("inventory") or {}).items():
            for item in items or []:
                normalized = dict(item)
                normalized["pool"] = pool_by_category.get(category, category)
                if category == "material":
                    normalized["kind"] = "material"
                    normalized["material_code"] = normalized.get("code")
                inventory.append(normalized)
        orders_by_activity: dict[str, list[dict]] = {}
        for order in record.get("orders") or []:
            orders_by_activity.setdefault(str(order.get("activity_id") or ""), []).append({
                "os_number": order.get("os_number"), "status": order.get("status"),
                "close_code": order.get("close_code"),
            })
        os_list = []
        for activity in record.get("activities") or []:
            activity_id = str(activity.get("activity_id") or "")
            os_list.append({
                "contract": activity.get("contract"), "aid": activity_id,
                "os": {
                    "activity": {
                        "aid": activity_id, "contract": activity.get("contract"),
                        "date": activity.get("scheduled_date"),
                        "work_type": activity.get("description") or activity.get("activity_type"),
                        "status": activity.get("status"),
                        "time_slot": activity.get("service_window"),
                        "start_time": activity.get("start_time"), "end_time": activity.get("end_time"),
                        "technician_id": activity.get("technician_id"),
                        "technician_external_id": activity.get("technician_login"),
                        "technician_name": activity.get("technician_name"),
                        "technician_observation": activity.get("observation"),
                        "city": activity.get("city"),
                    },
                    "tasks": orders_by_activity.get(activity_id, []),
                    "inventory": [item for item in inventory if str(item.get("activity_id") or "") == activity_id],
                },
            })
        if os_list:
            profile = str((record.get("activities") or [{}])[0].get("profile") or explicit_profile or "other")
            OPERATIONAL_STORE.ingest_toa_capture(
                profile, {"metadata": {"exportedAt": feed.get("loadedAt")}, "os_list": os_list},
                source="toa_datalake", export=False,
            )
    OPERATIONAL_STORE.export_json()


# Initialized after the projection callback exists, so the local collector can
# use the same SQLite and monitor pipeline as network/n8n ingestion.
TOA_LOCAL_COLLECTOR = TOALocalCollector(
    TOA_LIVE,
    TOA_DATALAKE,
    _sync_datalake_to_operational,
    logger=LOGGER,
    mirror_urls=[
        value.strip()
        for value in os.environ.get(
            "DOMINIUM_TV_INGEST_URL",
            "http://127.0.0.1:5173/api/toa-datalake/ingest",
        ).split(",")
        if value.strip()
    ],
)
TOA_BRIDGE_SERVER = ToaBridgeServer(TOA_DATALAKE, port=8787)


def _build_monitor_snapshot(profile: ProfileRuntime, content: bytes, filename: str) -> dict:
    return _build_monitor_snapshot_batch(profile, [(filename, content)])


def _decode_monitor_sources(body: dict) -> list[tuple[str, bytes]]:
    raw_files = body.get("files")
    if raw_files is None:
        raw_files = [body]
    if not isinstance(raw_files, list) or not raw_files or len(raw_files) > 40:
        raise ValueError("Selecione entre 1 e 40 arquivos CSV do TOA")

    sources: list[tuple[str, bytes]] = []
    for raw_file in raw_files:
        if not isinstance(raw_file, dict):
            raise ValueError("A lista de arquivos CSV e invalida")
        filename = Path(str(raw_file.get("filename", "atividades.csv"))).name
        encoded = str(raw_file.get("content_base64", ""))
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"O conteudo de {filename} e invalido") from exc
        if not content:
            raise ValueError(f"O arquivo {filename} esta vazio")
        sources.append((filename, content))
    return sources


def _route_monitor_sources(
    sources: list[tuple[str, bytes]],
) -> dict[str, list[tuple[str, bytes]]]:
    grouped: dict[str, list[tuple[str, bytes]]] = {}
    for filename, content in sources:
        profile = _monitor_profile_for_source(filename, content)
        grouped.setdefault(profile.key, []).append((filename, content))
    return grouped


def _load_monitor_snapshot(profile: ProfileRuntime) -> dict | None:
    path = _monitor_snapshot_path(profile)
    try:
        with MONITOR_SNAPSHOT_LOCK:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(snapshot, dict) or snapshot.get("profile") != profile.key:
        return None
    orders = snapshot.get("orders")
    if not isinstance(orders, list):
        return None
    return snapshot


def _clear_monitor_snapshot(profile: ProfileRuntime) -> bool:
    path = _monitor_snapshot_path(profile)
    with MONITOR_SNAPSHOT_LOCK:
        try:
            path.unlink()
            removed = True
        except FileNotFoundError:
            removed = False
    LOGGER.info("[%s] Retrato CSV do monitor removido", profile.label)
    return removed


def _failure_path(profile: ProfileRuntime, date: dt.date) -> Path:
    return profile.log_root / f"falhas-{date:%Y%m%d}.json"


def _load_failures(profile: ProfileRuntime, date: dt.date) -> dict[int, dict]:
    try:
        values = json.loads(
            _failure_path(profile, date).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return {
        int(value["id_os"]): value
        for value in values
        if isinstance(value, dict) and str(value.get("id_os", "")).isdigit()
    }


for runtime in PROFILES.values():
    runtime.failure_cache = _load_failures(runtime, runtime.failure_date)


def _profile_from_query(query_string: str) -> ProfileRuntime:
    query = parse_qs(query_string)
    key = query.get("profile", [DEFAULT_PROFILE])[0].strip().lower()
    try:
        return PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Base do Imperium invalida: {key}") from exc


MANUAL_PROFILE_CITY_SCOPE = {
    "natal": "NATAL",
    "fortaleza": "FORTALEZA",
    "mossoro": "MOSSORO",
    "recife": "RECIFE",
}


def _manual_close_scope(
    profile: ProfileRuntime,
    order: Order,
    *,
    cache_date: dt.date | None = None,
    cache_generation: int | None = None,
) -> dict:
    """Bind a manual close to one exact row from the current Imperium cache."""
    city_scope = MANUAL_PROFILE_CITY_SCOPE.get(profile.key)
    if not city_scope:
        raise OperationBlocked(("profile_scope_mismatch", "operation_blocked"))
    effective_date = cache_date or profile.cache_date
    generation = (
        profile.cache_generation
        if cache_generation is None
        else cache_generation
    )
    if effective_date is None or generation <= 0:
        raise OperationBlocked(("stale_snapshot", "operation_blocked"))
    state = {
        "project_id": PROJECT_IDENTITY.project_id,
        "source": "imperium_cache_v1",
        "profile_key": profile.key,
        "city_scope": city_scope,
        "cache_date": effective_date.isoformat(),
        "cache_generation": generation,
        "id_os": order.id_os,
        "num_os": order.num_os,
        "contract": order.contract,
        "id_service": order.id_service,
        "service": order.service,
        "status": order.status,
    }
    encoded = json.dumps(
        state,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        **state,
        "state_hash": hashlib.sha256(encoded).hexdigest(),
    }


def _validate_manual_close_operation(
    profile: ProfileRuntime,
    order: Order,
    body: dict,
) -> dict:
    scope = body.get("manual_scope")
    if not isinstance(scope, dict):
        raise OperationBlocked(("payload_scope_violation", "operation_blocked"))
    with profile.cache_lock:
        cached = profile.order_cache.get(order.id_os)
        cache_date = profile.cache_date
        cache_generation = profile.cache_generation
    if cached is None or cached != order:
        raise OperationBlocked(("stale_snapshot", "operation_blocked"))
    if cache_date is None or cache_generation <= 0:
        raise OperationBlocked(("stale_snapshot", "operation_blocked"))

    client_generation = int(scope.get("cache_generation") or 0)
    if (
        client_generation != cache_generation
        or scope.get("cache_date") != cache_date.isoformat()
    ):
        raise OperationBlocked(("stale_snapshot", "operation_blocked"))

    expected = _manual_close_scope(
        profile,
        cached,
        cache_date=cache_date,
        cache_generation=cache_generation,
    )
    blockers: list[str] = []
    if scope.get("project_id") != expected["project_id"]:
        blockers.append("wrong_project_identity")
    if scope.get("profile_key") != expected["profile_key"]:
        blockers.append("profile_scope_mismatch")
    if scope.get("city_scope") != expected["city_scope"]:
        blockers.append("city_scope_mismatch")
    if scope.get("source") != expected["source"]:
        blockers.append("payload_scope_violation")
    exact_fields = (
        "cache_date",
        "id_os",
        "num_os",
        "contract",
        "id_service",
        "service",
        "status",
    )
    if any(scope.get(field) != expected[field] for field in exact_fields):
        blockers.append("stale_snapshot")
    approved_hash = str(body.get("approved_state_hash", "")).strip()
    if (
        scope.get("state_hash") != expected["state_hash"]
        or approved_hash != expected["state_hash"]
    ):
        blockers.append("stale_snapshot")
    if blockers:
        blockers.append("operation_blocked")
        raise OperationBlocked(blockers)
    return expected

def _enrich_orders(
    profile: ProfileRuntime,
    date: dt.date,
    orders: list[Order],
) -> list[dict]:
    rows = TOA_CONTEXT.enrich(profile.key, date, orders)
    with profile.cache_lock:
        overrides = profile.installer_overrides.copy()
    for row in rows:
        override = overrides.get(int(row.get("id_os", 0)))
        if override:
            row["technician"] = override
    grouped: dict[
        tuple[tuple[str, str, str, str], str],
        list[dict],
    ] = {}
    for row in rows:
        scope_value = row.get("import_scope")
        activity_id = str(row.get("activity_id", "")).strip()
        if not isinstance(scope_value, dict) or not activity_id:
            blockers = list(row.get("operation_blockers") or ())
            blockers.append("missing_activity_id")
            row["operation_blockers"] = list(dict.fromkeys(blockers))
            continue
        try:
            scope = ImportScope.from_dict(scope_value)
            scope.validate_target(profile.key, row.get("city", ""))
        except OperationBlocked as exc:
            row["operation_blockers"] = list(exc.blockers)
            continue
        grouped.setdefault(
            (scope.batch_key, str(row.get("contract", "")).strip()),
            [],
        ).append(row)

    response_timestamp = dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="seconds"
    )
    for (_batch_key, contract), contract_rows in grouped.items():
        scope = ImportScope.from_dict(contract_rows[0]["import_scope"])
        identity_rows: dict[tuple[str, str, str, str, str], list[dict]] = {}
        for row in contract_rows:
            try:
                identity = OSIdentity(
                    project_id=PROJECT_IDENTITY.project_id,
                    profile_key=profile.key,
                    city=row.get("city", ""),
                    contract=row.get("contract", ""),
                    activity_id=row.get("activity_id", ""),
                )
            except OperationBlocked as exc:
                row["operation_blockers"] = list(exc.blockers)
                continue
            identity_rows.setdefault(identity.key, []).append(row)

        responses: list[dict] = []
        by_key: dict[tuple[str, str, str, str, str], OSSnapshot] = {}
        for identity_key, related_rows in identity_rows.items():
            identities = [
                str(item.get("technician_login") or item.get("technician") or "").strip()
                for item in related_rows
            ]
            installers = {value for value in identities if value}
            statuses = {str(item.get("status", "")).strip() for item in related_rows}
            if len(installers) != 1 or len(statuses) != 1:
                for row in related_rows:
                    row["operation_blockers"] = ["shared_state_contamination"]
                continue
            identity = OSIdentity(
                project_id=identity_key[0],
                profile_key=identity_key[1],
                city=identity_key[2],
                contract=identity_key[3],
                activity_id=identity_key[4],
            )
            response_version = hashlib.sha256(
                json.dumps(
                    [
                        {
                            "id_os": item.get("id_os"),
                            "num_os": item.get("num_os"),
                            "status": item.get("status"),
                            "service": item.get("service"),
                        }
                        for item in related_rows
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            responses.append(
                {
                    **identity.to_dict(),
                    "status": related_rows[0].get("status"),
                    "current_close_code": None,
                    "materials": (),
                    "equipments": (),
                    "installer_id": next(iter(installers)),
                    "response_timestamp": response_timestamp,
                    "response_version": response_version,
                }
            )
        if not responses:
            continue
        try:
            snapshots = profile.operations.refresh_contract(
                scope,
                contract,
                responses,
            )
            by_key = {snapshot.identity.key: snapshot for snapshot in snapshots}
        except OperationBlocked as exc:
            for row in contract_rows:
                row["operation_blockers"] = list(exc.blockers)
            continue
        for identity_key, related_rows in identity_rows.items():
            snapshot = by_key.get(identity_key)
            if snapshot is None:
                continue
            for row in related_rows:
                row["project_id"] = PROJECT_IDENTITY.project_id
                row["profile_key"] = profile.key
                row["city"] = snapshot.identity.city
                row["operation_identity"] = snapshot.identity.to_dict()
                row["approved_state_hash"] = snapshot.state_hash
                row["import_scope"] = scope.to_dict()
                row["operation_source"] = "toa_import"
                row["operation_blockers"] = []
    with profile.cache_lock:
        cache_generation = profile.cache_generation
        cached_orders = profile.order_cache.copy()
    for row in rows:
        if row.get("operation_source") == "toa_import":
            continue
        try:
            id_os = int(row.get("id_os", 0))
            cached_order = cached_orders.get(id_os)
            if cached_order is None:
                raise OperationBlocked(("stale_snapshot",))
            manual_scope = _manual_close_scope(
                profile,
                cached_order,
                cache_date=date,
                cache_generation=cache_generation,
            )
        except (TypeError, ValueError, OperationBlocked) as exc:
            blockers = (
                list(exc.blockers)
                if isinstance(exc, OperationBlocked)
                else ["stale_snapshot"]
            )
            row["operation_blockers"] = list(dict.fromkeys(blockers))
            continue
        toa_blockers = list(row.get("operation_blockers") or ())
        if toa_blockers:
            row["toa_operation_blockers"] = toa_blockers
        row.setdefault("city", manual_scope["city_scope"])
        row["operation_source"] = "imperium_cache"
        row["manual_scope"] = manual_scope
        row["approved_state_hash"] = manual_scope["state_hash"]
        row["operation_blockers"] = []
    return rows


def _read_only_order_rows(
    profile: ProfileRuntime,
    date: dt.date,
    orders: list[Order],
) -> list[dict]:
    """Enrich historical status views without authorizing close operations."""
    rows = TOA_CONTEXT.enrich(profile.key, date, orders)
    with profile.cache_lock:
        overrides = profile.installer_overrides.copy()
    protected_fields = (
        "operation_identity",
        "approved_state_hash",
        "import_scope",
        "manual_scope",
    )
    for row in rows:
        override = overrides.get(int(row.get("id_os", 0)))
        if override:
            row["technician"] = override
        for field_name in protected_fields:
            row.pop(field_name, None)
        row["operation_source"] = "status_view"
        row["operation_blockers"] = ["read_only_status_view"]
        row["read_only"] = True
    return rows


def _live_capture_iso_date(value: object) -> str:
    normalized = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            continue
    return dt.date.today().isoformat()


def _registry_service_close_code(service: object) -> str:
    """Infer only close codes whose service-to-code mapping is unambiguous."""
    value = unicodedata.normalize("NFD", str(service or "").casefold())
    normalized = "".join(
        character for character in value
        if unicodedata.category(character) != "Mn"
    )
    normalized = re.sub(r"^\s*\d+\s*-\s*", "", normalized).strip()
    if normalized == "envio de chip via tecnico":
        return "706"
    return ""


def _missing_close_code(value: object) -> bool:
    """Treat collector/CSV placeholders as an absent close code."""
    normalized = str(value or "").strip().casefold()
    return normalized in {"", "-", "--", "n/a", "na", "null", "none"}


def _merge_live_capture_registry_tasks(
    capture: dict,
    registry_orders: list[dict],
) -> list[dict]:
    """Complete a live activity with every OS imported for its contract/date."""
    merged: dict[str, dict] = {}
    order: list[str] = []
    for raw_task in capture.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task = dict(raw_task)
        os_number = str(task.get("os_number") or task.get("num_os") or "").strip()
        if not os_number:
            continue
        task["os_number"] = os_number
        merged[os_number] = task
        order.append(os_number)

    for context in registry_orders:
        if not isinstance(context, dict):
            continue
        os_number = str(
            context.get("os_number") or context.get("num_os") or ""
        ).strip()
        if not os_number:
            continue
        task = merged.get(os_number)
        if task is None:
            task = {
                "os_number": os_number,
                "close_code": str(context.get("close_code") or "").strip(),
                "status": str(context.get("os_status") or "").strip(),
                "registry_only": True,
                "source": "toa_csv_registry",
            }
            merged[os_number] = task
            order.append(os_number)
        service = str(context.get("service") or "").strip()
        if service and not str(task.get("service") or "").strip():
            task["service"] = service
        if _missing_close_code(task.get("close_code")):
            task["close_code"] = _registry_service_close_code(
                task.get("service") or service
            )
        task["registry_context"] = {
            "activity_status": str(context.get("activity_status") or "").strip(),
            "date": str(context.get("date") or "").strip(),
            "service_window": str(
                context.get("service_window") or context.get("time_window") or ""
            ).strip(),
            "source_file": str(context.get("source_file") or "").strip(),
        }
    return [merged[os_number] for os_number in order]


def _match_live_capture_to_orders(
    profile: ProfileRuntime,
    result: dict,
) -> dict:
    """Attach current Imperium rows without performing a new server query."""
    with profile.cache_lock:
        cached = list(profile.order_cache.values())
        cache_date = profile.cache_date or dt.date.today()
    cached_rows = _enrich_orders(profile, cache_date, cached)
    for capture in result.get("results", []):
        contract = str(capture.get("contract", "")).strip()
        activity_id = str(capture.get("aid", "")).strip()
        capture_city = str(capture.get("city", "")).strip()
        capture_date = _live_capture_iso_date(capture.get("scheduled_date"))
        registry_records = TOA_CONTRACTS.public_state(
            profile=profile.key,
            date=capture_date,
        ).get("records", [])
        registry_orders = [
            dict(order)
            for record in registry_records
            if isinstance(record, dict)
            and str(record.get("contract") or "").strip() == contract
            for order in record.get("orders", [])
            if isinstance(order, dict)
        ]
        capture["tasks"] = _merge_live_capture_registry_tasks(
            capture,
            registry_orders,
        )
        blockers: list[str] = []
        if not activity_id:
            blockers.append("missing_activity_id")
        task_numbers = {
            str(task.get("os_number", "")).strip()
            for task in capture.get("tasks", [])
            if isinstance(task, dict) and str(task.get("os_number", "")).strip()
        }
        contract_matches = [
            order
            for order in cached_rows
            if order.get("contract") == contract
            and order.get("operation_identity", {}).get("activity_id")
            == activity_id
        ]
        scoped_matches: dict[str, ImportScope] = {}
        for order in contract_matches:
            scope_value = order.get("import_scope")
            if not isinstance(scope_value, dict):
                blockers.append("shared_state_contamination")
                continue
            try:
                scope = ImportScope.from_dict(scope_value)
                scope.validate_target(profile.key, capture_city)
            except OperationBlocked as exc:
                blockers.extend(exc.blockers)
                continue
            scoped_matches[
                json.dumps(scope.to_dict(), sort_keys=True, separators=(",", ":"))
            ] = scope
        if len(scoped_matches) > 1:
            blockers.append("shared_state_contamination")
        if contract_matches and len(scoped_matches) != 1:
            blockers.append("payload_scope_violation")
        exact_matches = [
            order
            for order in contract_matches
            if order.get("num_os") in task_numbers
        ]
        current_contract_matches = [
            order
            for order in cached_rows
            if str(order.get("contract") or "").strip() == contract
            and bool(order.get("approved_state_hash"))
            and not order.get("operation_blockers")
        ]
        current_exact_matches = [
            order
            for order in current_contract_matches
            if order.get("num_os") in task_numbers
        ]
        all_matches_map = {str(o.get("num_os") or ""): o for o in current_contract_matches}
        for o in exact_matches:
            num = str(o.get("num_os") or "")
            if num:
                all_matches_map[num] = o
        selected = list(all_matches_map.values()) if all_matches_map else (exact_matches or current_exact_matches)
        capture["imperium_matches"] = selected
        capture["imperium_match_kind"] = (
            "os_number_and_activity" if exact_matches and selected is exact_matches
            else "os_number_current_imperium" if current_contract_matches
            else "activity_without_exact_os" if contract_matches
            else "not_found"
        )
        matches_by_os = {
            str(order.get("num_os") or "").strip(): order
            for order in selected
            if str(order.get("num_os") or "").strip()
        }

        # Inherit default close code from existing activity tasks
        default_close_code = ""
        for t in capture.get("tasks", []):
            if isinstance(t, dict) and t.get("close_code"):
                default_close_code = str(t["close_code"]).strip()
                break

        existing_task_numbers = {
            str(task.get("os_number") or "").strip()
            for task in capture.get("tasks", [])
            if isinstance(task, dict) and str(task.get("os_number") or "").strip()
        }

        # Include other OSs from the same contract that are active in Imperium
        for order in current_contract_matches:
            num_os = str(order.get("num_os") or "").strip()
            if num_os and num_os not in existing_task_numbers:
                existing_task_numbers.add(num_os)
                capture.setdefault("tasks", []).append({
                    "os_number": num_os,
                    "service": str(order.get("service") or "").strip(),
                    "status": "EM CAMPO",
                    "close_code": default_close_code or "409",
                    "source": "imperium_contract",
                    "imperium_field": True,
                    "imperium_status": str(order.get("status") or "EM CAMPO").strip(),
                })

        for task in capture.get("tasks", []):
            if not isinstance(task, dict):
                continue
            os_number = str(task.get("os_number") or "").strip()
            current_order = matches_by_os.get(os_number)
            task["imperium_field"] = current_order is not None
            task["imperium_status"] = (
                str(current_order.get("status") or "EM CAMPO").strip()
                if current_order is not None
                else "FORA DA LISTA EM CAMPO"
            )
        capture["operation_blockers"] = list(dict.fromkeys(blockers))
    result["profile"] = profile.key
    result["project"] = PROJECT_IDENTITY.to_dict()
    return result
OPERATIONAL_WINDOW_SLOTS = (
    (8 * 60, 11 * 60),
    (11 * 60, 14 * 60),
    (14 * 60, 17 * 60),
    (17 * 60, 20 * 60),
    (20 * 60, 22 * 60),
)


def _window_minutes(value: object) -> tuple[int, int] | None:
    matches = re.findall(r"(?<!\d)([0-2]?\d)(?::([0-5]\d))?", str(value or ""))
    if len(matches) < 2:
        return None
    values = []
    for hour, minute in matches[:2]:
        parsed_hour = int(hour)
        if parsed_hour > 23:
            return None
        values.append(parsed_hour * 60 + int(minute or 0))
    if values[1] <= values[0]:
        return None
    return values[0], values[1]


def _format_operational_window(window: tuple[int, int]) -> str:
    def clock(value: int) -> str:
        return f"{value // 60:02d}:{value % 60:02d}"

    return f"{clock(window[0])} - {clock(window[1])}"


def _current_operational_window(now: dt.datetime | None = None) -> tuple[int, int]:
    current = now or dt.datetime.now().astimezone()
    minute = current.hour * 60 + current.minute
    for window in OPERATIONAL_WINDOW_SLOTS:
        if window[0] <= minute < window[1]:
            return window
    if minute < OPERATIONAL_WINDOW_SLOTS[0][0]:
        return OPERATIONAL_WINDOW_SLOTS[0]
    return OPERATIONAL_WINDOW_SLOTS[-1]


def _is_disconnection_capture(capture: dict) -> bool:
    value = unicodedata.normalize(
        "NFD", str(capture.get("work_type") or "").casefold()
    )
    normalized = "".join(
        character for character in value if unicodedata.category(character) != "Mn"
    )
    return "desconex" in normalized


def _annotate_live_operational_windows(
    result: dict,
    *,
    now: dt.datetime | None = None,
) -> dict:
    current_window = _current_operational_window(now)
    for capture in result.get("results", []):
        if not isinstance(capture, dict):
            continue
        official_text = str(capture.get("service_window") or "").strip()
        official_window = _window_minutes(official_text)
        broad_disconnection = bool(
            _is_disconnection_capture(capture)
            and official_window
            and official_window[0] <= 8 * 60
            and official_window[1] >= 22 * 60
        )
        effective_window = (
            current_window if broad_disconnection else official_window
        )
        capture["official_service_window"] = official_text
        capture["operational_window"] = (
            _format_operational_window(effective_window)
            if effective_window
            else "Sem janela"
        )
        capture["operational_window_source"] = (
            "current_disconnection" if broad_disconnection
            else "official" if official_window
            else "unavailable"
        )
        capture["window_sort"] = list(effective_window or (24 * 60, 24 * 60))
    result["current_operational_window"] = _format_operational_window(current_window)
    result["results"] = sorted(
        result.get("results", []),
        key=lambda capture: (
            tuple(capture.get("window_sort") or (24 * 60, 24 * 60)),
            str(capture.get("scheduled_date") or ""),
            str(capture.get("contract") or ""),
            str(capture.get("aid") or ""),
        ),
    )
    return result


def _resolve_toa_live_reference(
    profile: ProfileRuntime,
    value: object,
) -> tuple[str, str, str]:
    reference = "".join(re.findall(r"\d", str(value or "")))
    if not re.fullmatch(r"\d{5,18}", reference):
        raise ValueError("Informe um contrato ou numero de OS com 5 a 18 digitos")

    with profile.cache_lock:
        matches = [
            order for order in profile.order_cache.values()
            if str(order.num_os).strip() == reference
        ]
    if matches:
        contracts = sorted({str(order.contract).strip() for order in matches if order.contract})
        if len(contracts) != 1:
            raise ValueError(
                "A OS aparece ligada a mais de um contrato; atualize a lista antes de consultar"
            )
        return contracts[0], "os", reference

    # In the current operation contracts are shorter than the 10-digit OS number.
    # Refusing an unresolved OS avoids accidentally searching it as a contract.
    if len(reference) >= 10:
        raise ValueError(
            "OS nao localizada na lista atual do DOMINIUM. Atualize as ordens e tente novamente"
        )
    return reference, "contract", ""


def _prepare_toa_live_lookup(
    profile: ProfileRuntime,
    result: dict,
    *,
    query: str,
    query_type: str,
    requested_os: str,
) -> dict:
    matched = _match_live_capture_to_orders(profile, result)
    annotated = _annotate_live_operational_windows(matched)
    annotated["query"] = query
    annotated["query_type"] = query_type
    annotated["requested_os"] = requested_os
    annotated["resolved_contract"] = str(result.get("contract") or "")
    requested_os_found = False
    for capture in annotated.get("results", []):
        tasks = capture.get("tasks") if isinstance(capture, dict) else []
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task["requested"] = bool(
                requested_os and str(task.get("os_number") or "").strip() == requested_os
            )
            requested_os_found = requested_os_found or task["requested"]
        capture["tasks"] = sorted(
            tasks,
            key=lambda task: (
                not bool(task.get("requested")),
                str(task.get("os_number") or ""),
            ),
        )
    annotated["requested_os_found"] = requested_os_found
    return annotated


def _toa_live_public_state() -> dict:
    """Expose the remote collector as the preferred live TOA source."""
    local = dict(TOA_LIVE.public_state())
    cloud = TOA_CONNECTOR.cloud_client.public_state()
    if not cloud.get("configured"):
        return local
    local.update({
        "connected": True,
        "authenticated": True,
        "busy": False,
        "remote": True,
        "mode": "cloud_bridge",
        "last_error": str(cloud.get("last_error") or ""),
        "last_lookup_at": str(cloud.get("last_success_at") or ""),
    })
    return local


def _cloud_snapshot_to_live_lookup(snapshot: dict, elapsed_seconds: float) -> dict:
    """Adapt the sanitized cloud snapshot to the existing close-workspace UI."""
    equipment = snapshot.get("equipment")
    equipment = equipment if isinstance(equipment, dict) else {}
    technician = snapshot.get("technician")
    technician = technician if isinstance(technician, dict) else {}
    validation = snapshot.get("validation")
    validation = validation if isinstance(validation, dict) else {}
    route = str(snapshot.get("route") or "").strip()
    contract = "".join(re.findall(r"\d", str(snapshot.get("contract") or "")))

    materials_applicable = snapshot.get("materials_applicable") if snapshot.get("materials_applicable") is not None else True
    materials_complete = snapshot.get("materials_complete") if snapshot.get("materials_complete") is not None else True
    captured_audit = [
        dict(item) for item in snapshot.get("captured_materials_for_audit", [])
        if isinstance(item, dict)
    ]
    operational_materials = [
        dict(item) for item in snapshot.get("materials", [])
        if isinstance(item, dict)
    ]
    inventory_diagnostics = snapshot.get("inventory_diagnostics")
    if not isinstance(inventory_diagnostics, dict):
        inventory_diagnostics = {
            "inventory_count": len(equipment.get("installed", [])) + len(equipment.get("removed", [])) + len(equipment.get("customer", [])) + len(operational_materials),
            "materials_count": len(operational_materials),
            "captured_materials_count": len(captured_audit),
            "source": "toa_cloud",
        }

    val_errors = list(validation.get("errors") or ())
    val_warnings = list(validation.get("warnings") or ())
    val_reasons = list(validation.get("reasons") or ())

    if materials_applicable is False:
        val_warnings.append("Miscelâneas não aplicáveis à baixa de desconexão; captura mantida apenas para auditoria.")
    elif materials_complete is False:
        val_errors.append("Captura de materiais incompleta no TOA. Revise os itens antes de prosseguir.")

    diag_inv = inventory_diagnostics.get("inventory_count", 0)
    diag_mat = inventory_diagnostics.get("materials_count", 0)
    diag_audit = inventory_diagnostics.get("captured_materials_count", 0)
    diag_status = "captura completa" if materials_complete else "captura incompleta"
    diagnostics_line = f"TOA: inventário {diag_inv} | miscelâneas operacionais {diag_mat} | auditoria {diag_audit} | {diag_status}"

    decision = (
        "candidate_after_validation"
        if (validation.get("valid") is True and materials_complete is not False)
        else "blocked_manual_review"
    )

    activity = {
        "found": True,
        "aid": str(snapshot.get("activity_id") or "").strip(),
        "contract": contract,
        "scheduled_date": str(snapshot.get("scheduled_date") or "").strip(),
        "service_window": str(snapshot.get("service_window") or "").strip(),
        "city": str(snapshot.get("city") or "").strip(),
        "work_type": str(snapshot.get("activity_type") or "").strip(),
        "activity_status": str(snapshot.get("status") or "").strip(),
        "assigned_technician": {
            "id": str(technician.get("id") or "").strip(),
            "external_id": str(technician.get("login") or "").strip(),
            "name": str(technician.get("name") or "").strip(),
        },
        "route_provider": {
            "id": route,
            "external_id": route,
            "name": route,
        },
        "technician_observation": str(
            snapshot.get("technician_observation") or ""
        ).strip(),
        "tasks": [
            dict(item) for item in snapshot.get("tasks", [])
            if isinstance(item, dict)
        ],
        "installed_equipment": [
            dict(item) for item in equipment.get("installed", [])
            if isinstance(item, dict)
        ],
        "removed_equipment": [
            dict(item) for item in equipment.get("removed", [])
            if isinstance(item, dict)
        ],
        "customer_equipment": [
            dict(item) for item in equipment.get("customer", [])
            if isinstance(item, dict)
        ],
        "materials": operational_materials,
        "captured_materials_for_audit": captured_audit,
        "materials_applicable": materials_applicable,
        "materials_complete": materials_complete,
        "inventory_diagnostics": inventory_diagnostics,
        "inventory_diagnostics_line": diagnostics_line,
        "decision": decision,
        "validation_errors": val_errors,
        "validation_warnings": val_warnings,
        "decision_reasons": val_reasons,
        "source": "toa_cloud",
        "read_only": True,
    }
    return {
        "ok": True,
        "contract": contract,
        "results": [activity],
        "elapsed_seconds": round(float(elapsed_seconds), 2),
        "session": _toa_live_public_state(),
        "source": "toa_cloud",
        "read_only": True,
    }


# =============================================================================
# IMPERIUM | VALIDACAO E EXECUCAO CONTROLADA DE BAIXAS
# =============================================================================
def _validated_close_operation(
    profile: ProfileRuntime,
    order: Order,
    body: dict,
    close_code: str,
) -> tuple[OSIdentity, OSSnapshot, ImportScope, PlannedClose] | dict:
    operation_source = str(body.get("operation_source", "")).strip()
    if operation_source in {"imperium_cache", "toa_live_auto"}:
        return _validate_manual_close_operation(profile, order, body)
    if operation_source not in {"", "toa_import"}:
        raise OperationBlocked(("payload_scope_violation", "operation_blocked"))
    identity_value = body.get("operation_identity")
    scope_value = body.get("import_scope")
    if not isinstance(identity_value, dict):
        raise OperationBlocked(("missing_activity_id", "operation_blocked"))
    if not isinstance(scope_value, dict):
        raise OperationBlocked(("payload_scope_violation", "operation_blocked"))
    identity = OSIdentity.from_mapping(identity_value)
    scope = ImportScope.from_dict(scope_value)
    scope.validate_target(profile.key, identity.city)
    if identity.project_id != PROJECT_IDENTITY.project_id:
        raise OperationBlocked(("wrong_project_identity", "operation_blocked"))
    if identity.contract != order.contract:
        raise OperationBlocked(("contract_identity_mismatch", "operation_blocked"))
    TOA_CONTEXT.validate_scope_source(
        scope,
        profile.cache_date or dt.date.today(),
    )
    profile.operations.validate_exact_scope(identity, scope)
    snapshot = profile.operations.snapshot(identity)
    approved_hash = str(body.get("approved_state_hash", "")).strip()
    if approved_hash != snapshot.state_hash:
        raise OperationBlocked(("stale_snapshot", "operation_blocked"))
    if scope.source_hash != str(body.get("approved_source_hash", "")).strip():
        raise OperationBlocked(("source_file_changed", "operation_blocked"))
    if snapshot.status != "open" or snapshot.current_close_code:
        blockers = ["already_closed"]
        if snapshot.current_close_code:
            blockers.append(
                "already_closed_with_different_code:"
                f"{snapshot.current_close_code}"
            )
        blockers.append("operation_blocked")
        raise OperationBlocked(blockers)
    plan = profile.operations.plan_close(
        scope,
        identity,
        close_code,
    )
    validate_payload_scope(
        scope,
        plan,
        {
            **identity.to_dict(),
            "batch_id": scope.batch_id,
            "source_hash": scope.source_hash,
        },
    )
    return identity, snapshot, scope, plan


def _installer_change_preview(
    profile: ProfileRuntime,
    id_os: int,
    serial: str,
) -> dict:
    if not profile.installer_change_enabled:
        raise ValueError(
            "A alteracao de instalador foi validada somente em Natal"
        )
    requested_serial = str(serial).strip().upper()
    with profile.cache_lock:
        selected = profile.order_cache.get(id_os)
        if selected is None:
            raise ValueError("Atualize a lista antes de mover esta OS")
        affected = sorted(
            (
                order
                for order in profile.order_cache.values()
                if order.contract == selected.contract
            ),
            key=lambda order: (order.num_os, order.id_os),
        )
    ownership = profile.api.find_serial_owner(requested_serial)
    owner = ownership.get("owner") if ownership.get("found") else None
    if not isinstance(owner, dict):
        raise ValueError(
            "O proprietario atual do serial nao foi localizado"
        )
    installer_id = int(owner.get("installer_id", 0))
    installer_name = str(owner.get("technician_name", "")).strip()
    if installer_id <= 0 or not installer_name:
        raise ValueError("O estoque atual nao possui um instalador valido")
    order_ids = [order.id_os for order in affected]
    signature = "|".join(
        (
            profile.key,
            selected.contract,
            requested_serial,
            str(installer_id),
            *(str(value) for value in order_ids),
        )
    )
    token = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "profile": profile.key,
        "contract": selected.contract,
        "serial": requested_serial,
        "installer_id": installer_id,
        "installer_name": installer_name,
        "stock_id": int(owner.get("stock_id", 0)),
        "count": len(affected),
        "orders": [order.to_dict() for order in affected],
        "preview_token": token,
        "equipment_transfer_enabled": False,
        "equipment_transfer_reason": (
            "A transferencia de equipamento serializado ainda aguarda "
            "captura oficial validada em Natal"
        ),
    }


def _serialized_transfer_preview(
    profile: ProfileRuntime,
    id_os: int,
    serial: str,
) -> dict:
    if not profile.serialized_transfer_enabled:
        raise ValueError(
            "A transferencia de equipamento foi validada somente em Natal"
        )
    with profile.cache_lock:
        selected = profile.order_cache.get(id_os)
    if selected is None:
        raise ValueError("Atualize a lista antes de transferir o equipamento")
    preview = profile.api.serialized_transfer_preview(id_os, serial)
    if preview["contract"] != selected.contract:
        raise ValueError(
            "O contrato da OS mudou desde a consulta. Atualize a lista"
        )
    signature_fields = (
        profile.key,
        str(preview["id_os"]),
        preview["contract"],
        preview["requested_serial"],
        preview["serial"],
        str(preview["source"]["stock_id"]),
        str(preview["source"]["installer_id"]),
        str(preview["target"]["stock_id"]),
        str(preview["target"]["installer_id"]),
        str(preview["equipment"]["equipment_id"]),
    )
    token = hashlib.sha256("|".join(signature_fields).encode("utf-8")).hexdigest()
    result = {
        **preview,
        "order": selected.to_dict(),
        "preview_token": token,
        "expires_in_seconds": SERIAL_TRANSFER_PREVIEW_TTL,
    }
    now = time.monotonic()
    with SERIAL_TRANSFER_LOCK:
        expired = [
            key
            for key, value in SERIAL_TRANSFER_PREVIEWS.items()
            if now - float(value.get("created_at", 0))
            > SERIAL_TRANSFER_PREVIEW_TTL
        ]
        for key in expired:
            SERIAL_TRANSFER_PREVIEWS.pop(key, None)
        SERIAL_TRANSFER_PREVIEWS[(profile.key, token)] = {
            "created_at": now,
            "preview": result,
        }
    return result


def _ensure_failure_day(profile: ProfileRuntime) -> None:
    today = dt.date.today()
    if profile.failure_date != today:
        profile.failure_date = today
        profile.failure_cache = _load_failures(profile, today)


def _persist_failures(profile: ProfileRuntime) -> None:
    path = _failure_path(profile, profile.failure_date)
    temporary = path.with_suffix(".tmp")
    values = sorted(
        profile.failure_cache.values(),
        key=lambda value: value.get("last_at", ""),
        reverse=True,
    )
    temporary.write_text(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_import_audit(
    profile: ProfileRuntime,
    target: dict,
    preview: object,
    duration: float,
    *,
    result: dict | None = None,
    error: BaseException | None = None,
) -> None:
    rows = list(result.get("orders", ())) if result else [
        {
            **order.to_dict(),
            "import_status": "RESULTADO NAO CONFIRMADO",
            "imported": False,
        }
        for order in getattr(preview, "orders", ())
    ]
    status_counts = Counter(
        str(row.get("import_status", "SEM STATUS")) or "SEM STATUS"
        for row in rows
        if isinstance(row, dict)
    )
    entry = {
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "profile": profile.key,
        "company": profile.label,
        "target": target.get("key", ""),
        "filename": getattr(preview, "filename", ""),
        "source_rows": getattr(preview, "source_rows", 0),
        "count": len(getattr(preview, "orders", ())),
        "scope_exclusions": list(getattr(preview, "scope_exclusions", ())),
        "excluded_count": len(getattr(preview, "scope_exclusions", ())),
        "duration_seconds": round(duration, 3),
        "ok": error is None,
        "imported": int(result.get("imported", 0)) if result else 0,
        "not_imported": int(result.get("not_imported", 0)) if result else 0,
        "status_counts": dict(status_counts),
        "orders": [
            {
                "os_number": str(row.get("os_number", "")),
                "contract": str(row.get("contract", "")),
                "service": str(row.get("os_type", "")),
                "status": str(row.get("import_status", "")),
                "imported": bool(row.get("imported")),
            }
            for row in rows
            if isinstance(row, dict)
        ],
    }
    if error is not None:
        entry["error"] = _exception_detail(error)
    path = profile.log_root / f"importacoes-{dt.date.today():%Y%m%d}.jsonl"
    with IMPORT_AUDIT_LOCK, path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
        stream.write("\n")


def _safe_append_import_audit(*args, **kwargs) -> None:
    try:
        _append_import_audit(*args, **kwargs)
    except OSError:
        LOGGER.exception("Nao foi possivel gravar a auditoria da importacao")


def _read_import_audit_history(
    profile: ProfileRuntime,
    *,
    audit_date: dt.date | None = None,
    limit: int = 80,
) -> dict:
    day = audit_date or dt.date.today()
    limit = max(1, min(int(limit), 300))
    path = profile.log_root / f"importacoes-{day:%Y%m%d}.jsonl"
    items: list[dict] = []
    malformed = 0
    if path.is_file():
        with IMPORT_AUDIT_LOCK:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            if len(items) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if isinstance(item, dict):
                items.append(item)
    return {
        "ok": True,
        "profile": profile.key,
        "company": profile.label,
        "date": day.isoformat(),
        "count": len(items),
        "malformed": malformed,
        "items": items,
    }


def _safe_record_import_contracts(
    preview: object,
    target: dict,
    profile: ProfileRuntime,
) -> dict:
    try:
        result = TOA_CONTRACTS.record_preview(
            preview,
            profile=profile.key,
            target=str(target.get("key", "")),
            source=str(getattr(preview, "filename", "")),
        )
        LOGGER.info(
            "[%s] Registro por janela atualizado: %s contratos",
            profile.label,
            result["recorded"],
        )
        return result
    except OSError as exc:
        LOGGER.exception("Nao foi possivel atualizar o registro de contratos TOA")
        return {"ok": False, "recorded": 0, "error": str(exc)}


# =============================================================================
# TOA -> IMPERIUM | IMPORTACAO AUTOMATICA DAS ATIVIDADES CAPTURADAS
# =============================================================================
def _automatic_toa_import(route: dict[str, str], path: Path) -> dict:
    target = IMPORT_TARGET_BY_KEY[route["target"]]
    profile = PROFILES[target["profile"]]
    try:
        preview = _scoped_import_preview(
            path.read_bytes(),
            path.name,
            profile,
        )
    except ValueError as exc:
        if "Nenhuma OS foi encontrada" in str(exc):
            LOGGER.info(
                "[%s] TOA automatico: %s sem OS; importacao ignorada",
                profile.label,
                route["route"],
            )
            return {
                "status": "vazia",
                "count": 0,
                "imported": 0,
                "not_imported": 0,
                "requires_human": False,
            }
        raise

    if not profile.close_enabled:
        raise ValueError(f"Importacao ainda nao habilitada para {profile.label}")
    if not OPERATION_GATE.acquire(timeout=300):
        raise RuntimeError(
            "O Imperium permaneceu ocupado por 5 minutos; rota nao importada"
        )
    started = time.monotonic()
    try:
        LOGGER.info(
            "[%s] TOA automatico: importando %s OS de %s",
            profile.label,
            len(preview.orders),
            route["route"],
        )
        try:
            result = profile.api.import_toa(preview)
        except Exception as exc:
            _safe_append_import_audit(
                profile,
                target,
                preview,
                time.monotonic() - started,
                error=exc,
            )
            raise
        _safe_append_import_audit(
            profile,
            target,
            preview,
            time.monotonic() - started,
            result=result,
        )
        _safe_record_import_contracts(preview, target, profile)
        return {
            "status": "concluida",
            "count": int(result.get("count", len(preview.orders))),
            "imported": int(result.get("imported", 0)),
            "not_imported": int(result.get("not_imported", 0)),
            "excluded_count": len(preview.scope_exclusions),
            "scope_exclusions": list(preview.scope_exclusions),
            "requires_human": False,
        }
    finally:
        OPERATION_GATE.release()


TOA_AUTOMATION = TOAAutomation(ROOT, _automatic_toa_import, logger=LOGGER)

REMOTE_TOA_AUTOMATION_BASE = os.getenv(
    "DOMINIUM_TOA_AUTOMATION_REMOTE", "http://192.168.0.6:8787"
).rstrip("/")
REMOTE_TOA_AUTOMATION_CLIENT = socket.gethostname().strip().upper()


def _remote_toa_automation_request(path: str, method: str = "GET") -> dict:
    request = Request(
        f"{REMOTE_TOA_AUTOMATION_BASE}{path}",
        data=b"{}" if method == "POST" else None,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Dominium-Client": REMOTE_TOA_AUTOMATION_CLIENT,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Servidor TOA respondeu HTTP {exc.code}: {detail[:240]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Servidor TOA indisponivel: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Servidor TOA retornou resposta invalida")
    payload["remote_server"] = True
    return payload


def _bulk_preview_rows(preview: object, status: str) -> list[dict]:
    return [
        {
            **order.to_dict(),
            "import_status": status,
            "imported": False,
        }
        for order in getattr(preview, "orders", ())
    ]


def _confirm_bulk_creation(
    profile: ProfileRuntime,
    preview: object,
    delays: tuple[float, ...] = (0.0, 2.0, 5.0),
) -> dict | None:
    expected = {
        (str(order.os_number), str(order.contract)): order
        for order in getattr(preview, "orders", ())
    }
    if not expected:
        return None

    for attempt, delay in enumerate(delays, start=1):
        if delay > 0:
            time.sleep(delay)
        try:
            current_orders = profile.api.list_orders(dt.date.today())
        except (DataSnapError, ImperiumHTTPError, OSError) as exc:
            LOGGER.warning(
                "[%s] Confirmacao da criacao falhou na tentativa %s/%s: %s",
                profile.label,
                attempt,
                len(delays),
                exc,
            )
            continue

        by_key = {
            (str(order.num_os), str(order.contract)): order
            for order in current_orders
        }
        if not expected.keys() <= by_key.keys():
            LOGGER.info(
                "[%s] Criacao ainda nao localizada na tentativa %s/%s: %s de %s OS",
                profile.label,
                attempt,
                len(delays),
                len(expected.keys() & by_key.keys()),
                len(expected),
            )
            continue

        with profile.cache_lock:
            profile.order_cache.clear()
            profile.order_cache.update(
                {order.id_os: order for order in current_orders}
            )
            profile.cache_date = dt.date.today()
            profile.cache_generation = getattr(
                profile,
                "cache_generation",
                0,
            ) + 1
        rows = [
            {
                **order.to_dict(),
                "import_status": "CRIADA; CONFIRMADA APOS RESPOSTA INCOMPLETA",
                "imported": True,
            }
            for order in getattr(preview, "orders", ())
        ]
        LOGGER.info(
            "[%s] Criacao confirmada por consulta: %s OS localizadas",
            profile.label,
            len(rows),
        )
        return {
            "ok": True,
            "count": len(rows),
            "imported": len(rows),
            "not_imported": 0,
            "confirmed_after_incomplete_response": True,
            "orders": rows,
        }
    return None


# =============================================================================
# IMPERIUM | ESTOQUE, MATERIAIS E VINCULOS COM TECNICOS
# =============================================================================
def _material_assignment_path(profile: ProfileRuntime) -> Path:
    return profile.log_root / f"miscelaneas-toa-{dt.date.today():%Y%m%d}.json"


def _load_material_assignments(profile: ProfileRuntime) -> dict[str, dict]:
    try:
        values = json.loads(
            _material_assignment_path(profile).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(values, dict):
        return {}
    return {
        str(key): value
        for key, value in values.items()
        if isinstance(value, dict)
    }


def _material_assignment(profile: ProfileRuntime, paste_key: str) -> dict | None:
    with MATERIAL_ASSIGNMENT_LOCK:
        return _load_material_assignments(profile).get(paste_key)


def _save_material_assignment(
    profile: ProfileRuntime,
    paste_key: str,
    order: Order,
) -> None:
    with MATERIAL_ASSIGNMENT_LOCK:
        values = _load_material_assignments(profile)
        values[paste_key] = {
            "os_number": order.num_os,
            "id_os": order.id_os,
            "at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        path = _material_assignment_path(profile)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(values, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)


def _material_paste_key(text: str) -> str:
    normalized = " ".join(text.upper().split()).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _error_category(message: str) -> tuple[str, str]:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", message)
        if not unicodedata.combining(character)
    ).upper()
    if any(
        marker in normalized
        for marker in (
            "COMPLEMENTO DAS MISCELANEAS",
            "COMPLEMENTO DE MISCELANEAS",
            "TRANSFERENCIA DE MISCELANEAS",
        )
    ):
        return "MATERIAL", "Movimentacao de material"
    if any(
        marker in normalized
        for marker in (
            "NAO CONFIRMOU A BAIXA",
            "APPLYUPDATES",
            "NO RESULT",
            "UNEXPECTED RESULT PACKET",
        )
    ):
        return "BAIXA", "Baixa nao confirmada"
    if any(
        marker in normalized
        for marker in (
            "TIMED OUT",
            "TIMEOUT",
            "WINERROR 10060",
            "GETADDRINFO",
            "CONECTAR AO SERVIDOR",
            "CONNECTION RESET",
            "CONNECTION REFUSED",
            "HOST CONECTADO NAO RESPONDEU",
        )
    ):
        return "CONEXAO", "Conexao"
    if any(
        marker in normalized
        for marker in (
            "SERIAL",
            "EQUIPAMENTO",
            "ESTOQUE DO INSTALADOR",
        )
    ):
        return "EQUIPAMENTO", "Equipamento"
    return "API", "API Imperium"


def _exception_detail(exc: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        message = str(current).strip()
        if message and message not in messages:
            messages.append(message)
        current = current.__cause__
    return " | ".join(messages)[:1000]


def _record_failure(
    profile: ProfileRuntime,
    order: Order,
    exc: BaseException,
    close_code: str,
) -> dict:
    detail = _exception_detail(exc)
    category, category_label = _error_category(detail)
    now = dt.datetime.now().isoformat(timespec="seconds")
    with profile.failure_lock:
        _ensure_failure_day(profile)
        previous = profile.failure_cache.get(order.id_os, {})
        value = {
            **order.to_dict(),
            "close_code": close_code,
            "category": category,
            "category_label": category_label,
            "error": str(exc),
            "detail": detail,
            "attempts": int(previous.get("attempts", 0)) + 1,
            "first_at": previous.get("first_at", now),
            "last_at": now,
        }
        profile.failure_cache[order.id_os] = value
        _persist_failures(profile)
        return value.copy()


def _resolve_failure(profile: ProfileRuntime, id_os: int) -> None:
    with profile.failure_lock:
        _ensure_failure_day(profile)
        if profile.failure_cache.pop(id_os, None) is not None:
            _persist_failures(profile)


def _reconcile_failures(profile: ProfileRuntime, orders: list[Order]) -> None:
    active = {order.id_os: order for order in orders}
    audit_path = profile.log_root / f"baixas-{dt.date.today():%Y%m%d}.csv"
    latest: dict[int, dict] = {}
    attempts: dict[int, int] = {}
    try:
        with audit_path.open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                try:
                    id_os = int(row["IdOS"])
                except (KeyError, TypeError, ValueError):
                    continue
                latest[id_os] = row
                if row.get("Resultado") == "FALHA":
                    attempts[id_os] = attempts.get(id_os, 0) + 1
    except FileNotFoundError:
        pass

    changed = False
    now = dt.datetime.now().isoformat(timespec="seconds")
    with profile.failure_lock:
        _ensure_failure_day(profile)
        for id_os in list(profile.failure_cache):
            if id_os not in active:
                del profile.failure_cache[id_os]
                changed = True
        for id_os, row in latest.items():
            if (
                row.get("Resultado") != "FALHA"
                or id_os not in active
                or id_os in profile.failure_cache
            ):
                continue
            detail = row.get("Detalhe", "") or "Baixa nao confirmada"
            close_code = row.get("Codigo", "106") or "106"
            category, category_label = _error_category(detail)
            order = active[id_os]
            profile.failure_cache[id_os] = {
                **order.to_dict(),
                "close_code": close_code,
                "category": category,
                "category_label": category_label,
                "error": (
                    "O servidor nao confirmou a baixa com o codigo "
                    f"{close_code}"
                ),
                "detail": detail,
                "attempts": attempts.get(id_os, 1),
                "first_at": row.get("DataHora", now),
                "last_at": row.get("DataHora", now),
            }
            changed = True
        if changed:
            _persist_failures(profile)


def _failure_list(profile: ProfileRuntime) -> list[dict]:
    with profile.failure_lock:
        _ensure_failure_day(profile)
        return sorted(
            (value.copy() for value in profile.failure_cache.values()),
            key=lambda value: value.get("last_at", ""),
            reverse=True,
        )


# =============================================================================
# IMPERIUM | CLIENTE HTTP E CANAL OPERACIONAL
# =============================================================================
def _official_http_client(profile_key: str) -> ImperiumHTTPClient:
    with OFFICIAL_HTTP_LOCK:
        if profile_key not in OFFICIAL_HTTP_CLIENTS:
            if not OFFICIAL_HTTP_CREDENTIALS.is_file():
                raise ValueError("Credenciais da integracao IMPERIUM nao configuradas")
            credentials = load_credentials(OFFICIAL_HTTP_CREDENTIALS)
            OFFICIAL_HTTP_CLIENTS[profile_key] = ImperiumHTTPClient(
                credentials["username"],
                credentials["password"],
                tenant=profile_key,
                timeout=45,
            )
        return OFFICIAL_HTTP_CLIENTS[profile_key]


def _clean_operational_technician_name(name: str) -> str:
    norm = normalize_technician(name)
    cleaned = re.sub(
        r"\b(DESC|DESCONEXAO|DESCONEXOES|RETIRADA|RETIRADAS|MDU|FTTH|GPON|PRE|POS|MAN|EQUIPE)\b",
        " ",
        norm,
    )
    return " ".join(cleaned.split())


def _same_technician_name(current_name: str, captured_name: str) -> bool:
    current_key = normalize_technician(current_name)
    captured_key = normalize_technician(captured_name)
    if not current_key or not captured_key:
        return False
    if current_key.startswith(captured_key) or captured_key.startswith(current_key):
        return True

    c_clean = _clean_operational_technician_name(current_name)
    cap_clean = _clean_operational_technician_name(captured_name)
    if c_clean and cap_clean and (c_clean.startswith(cap_clean) or cap_clean.startswith(c_clean)):
        return True

    ignored = {"DA", "DAS", "DE", "DO", "DOS"}
    current_tokens = [item for item in (c_clean or current_key).split() if item not in ignored]
    captured_tokens = [item for item in (cap_clean or captured_key).split() if item not in ignored]
    if not current_tokens or not captured_tokens:
        return False
    first_name_close = difflib.SequenceMatcher(
        None,
        current_tokens[0],
        captured_tokens[0],
    ).ratio() >= 0.88
    shared_surnames = set(current_tokens[1:]) & set(captured_tokens[1:])
    return bool(first_name_close and shared_surnames)


def _technician_by_current_name(name: str) -> dict | None:
    exact = TECHNICIANS.resolve(name)
    if exact is not None:
        return exact

    cleaned_name = _clean_operational_technician_name(name)
    if cleaned_name:
        exact_cleaned = TECHNICIANS.resolve(cleaned_name)
        if exact_cleaned is not None:
            return exact_cleaned

    key = normalize_technician(name)
    cleaned_key = cleaned_name or key
    if not cleaned_key:
        return None

    all_techs = TECHNICIANS.public_dict().get("technicians", [])

    prefix_matches: list[tuple[int, dict]] = []
    for technician in all_techs:
        candidate_name = technician.get("name", "")
        candidate_key = normalize_technician(candidate_name)
        candidate_cleaned = _clean_operational_technician_name(candidate_name)
        if not candidate_key:
            continue
        for k in (cleaned_key, key):
            for ck in (candidate_key, candidate_cleaned):
                if ck.startswith(k) or k.startswith(ck):
                    prefix_matches.append((min(len(k), len(ck)), technician))
                    break

    if prefix_matches:
        best_score = max(score for score, _technician in prefix_matches)
        best_matches = [
            technician
            for score, technician in prefix_matches
            if score == best_score
        ]
        unique_matches = {t["login"]: t for t in best_matches}
        if len(unique_matches) == 1:
            return next(iter(unique_matches.values()))

    ignored = {"DA", "DAS", "DE", "DO", "DOS"}
    current_tokens = [item for item in cleaned_key.split() if item not in ignored]
    if len(current_tokens) >= 2:
        token_matches: list[dict] = []
        for technician in all_techs:
            candidate_tokens = [
                item
                for item in normalize_technician(technician.get("name", "")).split()
                if item not in ignored
            ]
            if not candidate_tokens:
                continue
            if set(current_tokens).issubset(set(candidate_tokens)):
                token_matches.append(technician)
            elif _same_technician_name(cleaned_key, technician.get("name", "")):
                token_matches.append(technician)

        unique_token_matches = {t["login"]: t for t in token_matches}
        if len(unique_token_matches) == 1:
            return next(iter(unique_token_matches.values()))
        elif len(unique_token_matches) > 1:
            best_by_tokens = max(
                unique_token_matches.values(),
                key=lambda t: (
                    1 if "MDU" in t.get("teams", []) else 0,
                    len(set(current_tokens) & set(normalize_technician(t.get("name", "")).split())),
                ),
            )
            return best_by_tokens

    return None


def _cached_stock_technicians(
    profile: ProfileRuntime,
    *,
    max_age: float = 300.0,
) -> list[dict]:
    now = time.monotonic()
    with profile.cache_lock:
        cached = getattr(profile, "_stock_technicians_cache", None)
        if cached is not None and (now - cached[0]) < max_age:
            return cached[1]
    technicians = profile.api.list_stock_technicians()
    with profile.cache_lock:
        profile._stock_technicians_cache = (now, technicians)
    return technicians


TOA_IMPERIUM_INSTALLER_ALIASES: dict[str, tuple[str, ...]] = {
    "ESLI MELQUISEDEQUE DA SILVA": ("MELQUISEDEQUE",),
    "SOMERREGILSON DA SILVA MEDEIROS": ("SONERREGILSON",),
}


def _resolve_imperium_installer_for_toa(
    profile: ProfileRuntime,
    toa_technician: dict,
) -> tuple[dict | None, str]:
    """Resolve a TOA technician dictionary to a single Imperium StockTechnician.

    Returns (stock_tech_dict, match_method) if unambiguously resolved, or
    (None, reason) if not found or ambiguous.
    """
    login = str(
        toa_technician.get("login")
        or toa_technician.get("external_id")
        or ""
    ).strip().upper()
    name = str(toa_technician.get("name") or "").strip()

    canonical_name = ""
    if login and re.fullmatch(r"Z\d+", login):
        resolved = TECHNICIANS.resolve(login)
        if resolved:
            canonical_name = str(resolved.get("name") or "").strip()

    names_to_try = [n for n in [name, canonical_name] if n]
    if not names_to_try and not login:
        return None, "no_technician_info"

    try:
        stock_techs = _cached_stock_technicians(profile)
    except Exception as exc:
        LOGGER.warning(
            "[%s] Falha ao listar estoques de tecnicos: %s",
            profile.label,
            exc,
        )
        return None, f"stock_list_failed: {exc}"

    # Strategy 0: aliases operacionais explicitamente aprovados.
    alias_names = TOA_IMPERIUM_INSTALLER_ALIASES.get(normalize_technician(name), ())
    if alias_names:
        alias_norms = {normalize_technician(alias) for alias in alias_names if alias}
        alias_matches = [
            st for st in stock_techs
            if normalize_technician(st.get("technician_name", "")) in alias_norms
            or normalize_technician(st.get("stock_name", "")) in alias_norms
        ]
        unique_aliases = {c["installer_id"]: c for c in alias_matches if c.get("installer_id")}
        if len(unique_aliases) == 1:
            return next(iter(unique_aliases.values())), "explicit_alias"
        if len(unique_aliases) > 1:
            return None, f"ambiguous_alias_{len(unique_aliases)}"

    # Strategy 1: exact normalized match on technician_name or stock_name
    exact_matches: list[dict] = []
    for st in stock_techs:
        st_norm = normalize_technician(st.get("technician_name", ""))
        st_stock_norm = normalize_technician(st.get("stock_name", ""))
        for n in names_to_try:
            n_norm = normalize_technician(n)
            if n_norm and (st_norm == n_norm or st_stock_norm == n_norm):
                exact_matches.append(st)
                break
    unique_exact = {c["installer_id"]: c for c in exact_matches if c.get("installer_id")}
    if len(unique_exact) == 1:
        return next(iter(unique_exact.values())), "exact"
    elif len(unique_exact) > 1:
        return None, f"ambiguous_exact_{len(unique_exact)}"

    # Strategy 2: _same_technician_name
    same_matches: list[dict] = []
    for st in stock_techs:
        for n in names_to_try:
            if _same_technician_name(st.get("technician_name", ""), n) or _same_technician_name(st.get("stock_name", ""), n):
                same_matches.append(st)
                break
    unique_same = {c["installer_id"]: c for c in same_matches if c.get("installer_id")}
    if len(unique_same) == 1:
        return next(iter(unique_same.values())), "same_name"
    elif len(unique_same) > 1:
        return None, f"ambiguous_same_{len(unique_same)}"

    # Strategy 3: token subset match (at least 2 non-ignored tokens)
    ignored = {"DA", "DAS", "DE", "DO", "DOS"}
    token_matches: list[dict] = []
    for st in stock_techs:
        st_tokens = set(normalize_technician(st.get("technician_name", "")).split()) - ignored
        for n in names_to_try:
            n_tokens = set(normalize_technician(n).split()) - ignored
            if len(n_tokens) >= 2 and n_tokens.issubset(st_tokens):
                token_matches.append(st)
                break
    unique_tokens = {c["installer_id"]: c for c in token_matches if c.get("installer_id")}
    if len(unique_tokens) == 1:
        return next(iter(unique_tokens.values())), "token_subset"
    elif len(unique_tokens) > 1:
        return None, f"ambiguous_tokens_{len(unique_tokens)}"

    return None, "not_found"


def _reconcile_order_installer_with_toa(
    profile: ProfileRuntime,
    order: Order,
    body: dict,
    report_date: dt.date,
    *,
    gate_already_acquired: bool = False,
) -> dict | None:
    """Ensure the order installer in Imperium matches the technician in TOA.

    If TOA diverges from Imperium, reassigns the order in Imperium to the TOA
    technician before stock validation or close dispatch.
    """
    # 1. Extract TOA technician information
    toa_tech: dict | None = None
    candidate_tech = body.get("toa_technician") or body.get("assigned_technician")
    if isinstance(candidate_tech, dict) and (
        candidate_tech.get("name")
        or candidate_tech.get("login")
        or candidate_tech.get("external_id")
        or candidate_tech.get("id")
    ):
        toa_tech = candidate_tech
    if toa_tech is None:
        evidence = _live_technician_evidence(profile, order)
        if evidence:
            toa_tech = {
                "name": evidence.get("technician_name", ""),
                "login": evidence.get("technician_login", ""),
                "external_id": evidence.get("technician_login", ""),
            }

    if toa_tech is None or not (
        toa_tech.get("name")
        or toa_tech.get("login")
        or toa_tech.get("external_id")
    ):
        return None

    # 2. Check authoritative installer in Imperium
    current_installer = profile.api.order_installer(order)
    current_installer_id = int(current_installer.get("installer_id") or 0)
    current_installer_name = str(current_installer.get("installer_name") or "").strip()

    toa_name = str(toa_tech.get("name") or "").strip()
    toa_login = str(
        toa_tech.get("login") or toa_tech.get("external_id") or ""
    ).strip().upper()

    # Check if current Imperium installer already matches TOA
    if toa_name and _same_technician_name(current_installer_name, toa_name):
        return current_installer
    if toa_login and re.fullmatch(r"Z\d+", toa_login):
        resolved_tech = TECHNICIANS.resolve(toa_login)
        if resolved_tech:
            canon_name = str(resolved_tech.get("name") or "").strip()
            if canon_name and _same_technician_name(current_installer_name, canon_name):
                return current_installer

    # 3. Mismatch detected! Check if installer change is enabled
    if not getattr(profile, "installer_change_enabled", False):
        raise InstallerMismatchUnresolvedError(
            f"Divergencia de instalador na OS {order.num_os}: TOA atribui a "
            f"'{toa_name or toa_login}', mas Imperium esta com '{current_installer_name}'; "
            "a alteracao de instalador nao esta habilitada nesta base"
        )

    # 4. Resolve target installer in Imperium
    target_stock_tech, match_method = _resolve_imperium_installer_for_toa(
        profile,
        toa_tech,
    )
    if target_stock_tech is None:
        raise InstallerMismatchUnresolvedError(
            f"Divergencia de instalador na OS {order.num_os}: TOA atribui a "
            f"'{toa_name or toa_login}', mas Imperium esta com '{current_installer_name}'. "
            f"O tecnico do TOA nao foi localizado de forma unica no Imperium ({match_method})"
        )

    target_installer_id = int(target_stock_tech["installer_id"])
    target_installer_name = str(
        target_stock_tech.get("technician_name")
        or target_stock_tech.get("stock_name")
        or ""
    ).strip()

    if target_installer_id == current_installer_id:
        return current_installer

    # 5. Execute reassignment
    LOGGER.warning(
        "[%s] Divergencia na OS %s (contrato %s): Imperium está com %s (ID %s), "
        "mas TOA atribui a %s (ID %s). Alterando instalador no Imperium antes da baixa...",
        profile.label,
        order.num_os,
        order.contract,
        current_installer_name,
        current_installer_id,
        target_installer_name,
        target_installer_id,
    )

    gate_acquired = False
    if not gate_already_acquired:
        if not OPERATION_GATE.acquire(timeout=20.0):
            raise InstallerReassignmentFailedError(
                "Outra operacao DataSnap esta em andamento; "
                "nao foi possivel alterar o instalador no Imperium"
            )
        gate_acquired = True
    try:
        profile.api.change_order_installer(order.id_os, target_installer_id)
    except Exception as exc:
        raise InstallerReassignmentFailedError(
            f"Falha ao alterar instalador da OS {order.num_os} para "
            f"{target_installer_name} (ID {target_installer_id}): {exc}"
        ) from exc
    finally:
        if gate_acquired:
            OPERATION_GATE.release()

    # 6. Verify confirmation
    confirmed = profile.api.order_installer(order)
    confirmed_id = int(confirmed.get("installer_id") or 0)
    if confirmed_id != target_installer_id:
        raise InstallerReassignmentUnconfirmedError(
            f"Alteracao de instalador solicitada para {target_installer_name} "
            f"(ID {target_installer_id}), mas confirmacao retornou "
            f"{confirmed.get('installer_name')} (ID {confirmed_id})"
        )

    # 7. Update cache
    with profile.cache_lock:
        profile.installer_overrides[order.id_os] = target_installer_name

    LOGGER.warning(
        "[%s] Instalador da OS %s alterado com sucesso para %s (ID %s)",
        profile.label,
        order.num_os,
        target_installer_name,
        target_installer_id,
    )
    return confirmed


def _official_technician_code(
    profile: ProfileRuntime,
    order: Order,
    scheduled_date: dt.date,
    body: dict | None = None,
) -> tuple[str, str, int]:
    current = profile.api.order_installer(order)
    current_name = str(current.get("installer_name", "")).strip()
    try:
        installer_id = int(current.get("installer_id", 0))
    except (TypeError, ValueError):
        installer_id = 0
    if installer_id <= 0:
        raise ValueError("O instalador atual da OS nao possui ID valido no Imperium")

    enriched = _enrich_orders(profile, scheduled_date, [order])[0]
    captured_login = str(enriched.get("technician_login", "")).strip().upper()
    captured_name = str(enriched.get("technician", "")).strip()
    if not captured_login:
        live_evidence = _live_technician_evidence(profile, order)
        if live_evidence:
            captured_login = str(
                live_evidence.get("technician_login") or ""
            ).strip().upper()
            captured_name = str(
                live_evidence.get("technician_name") or ""
            ).strip()

    if (not captured_login or not captured_name) and isinstance(body, dict):
        toa_tech = body.get("toa_technician") or body.get("assigned_technician")
        if isinstance(toa_tech, dict):
            body_login = str(
                toa_tech.get("login") or toa_tech.get("external_id") or ""
            ).strip().upper()
            body_name = str(toa_tech.get("name") or "").strip()
            if not captured_login and body_login:
                captured_login = body_login
            if not captured_name and body_name:
                captured_name = body_name

    if captured_login and re.fullmatch(r"Z\d+", captured_login):
        if not captured_name or _same_technician_name(current_name, captured_name):
            return captured_login, current_name or captured_name, installer_id

    technician = _technician_by_current_name(current_name)
    if technician is None:
        fallback = TECHNICIANS.resolve(enriched.get("technician_login", ""))
        fallback_name = str((fallback or {}).get("name", "")).strip()
        current_key = normalize_technician(current_name)
        fallback_key = normalize_technician(fallback_name)
        if fallback and current_key and (
            fallback_key.startswith(current_key) or current_key.startswith(fallback_key)
        ):
            technician = fallback
    if technician is None:
        if captured_login and re.fullmatch(r"Z\d+", captured_login):
            return captured_login, current_name, installer_id
        order_login = str(getattr(order, "technician_login", "") or "").strip().upper()
        if order_login and re.fullmatch(r"Z\d+", order_login):
            return order_login, current_name, installer_id
        raise ValueError(
            f"Nao foi possivel relacionar o instalador atual da OS ({current_name}) a um login Z"
        )
    login = str(technician.get("login", "")).strip().upper()
    if not login:
        if captured_login and re.fullmatch(r"Z\d+", captured_login):
            return captured_login, current_name, installer_id
        raise ValueError("O instalador atual da OS nao possui login cadastrado")
    return login, current_name or str(technician.get("name", "")), installer_id


def _build_official_panel_plan(
    profile: ProfileRuntime,
    order: Order,
    close_definition,
    body: dict,
    scheduled_date: dt.date,
) -> dict:
    if not OFFICIAL_HTTP_CREDENTIALS.is_file():
        raise ValueError("Credenciais da integracao IMPERIUM nao configuradas")
    technician_code, current_installer, installer_id = _official_technician_code(
        profile,
        order,
        scheduled_date,
        body=body,
    )
    removed_type_codes = {
        key: value.code
        for key, value in profile.api.removed_equipment.items()
    }
    plan = build_manual_official_plan(
        order=order,
        scheduled_date=scheduled_date,
        technician_code=technician_code,
        close_code=close_definition.code,
        close_description=close_definition.description,
        productive=close_definition.productive,
        body=body,
        removed_type_codes=removed_type_codes,
    )
    return {
        **plan,
        "technician_code": technician_code,
        "technician_name": current_installer,
        "installer_id": installer_id,
        "scheduled_date": scheduled_date.isoformat(),
    }


def _validate_official_installed_serial_ownership(
    profile: ProfileRuntime,
    plan: dict,
) -> None:
    """Block the official API before enqueueing a serial owned by another stock."""
    payload = plan.get("payload", {}).get("ordemservico", {})
    expected_name = str(plan.get("technician_name", "")).strip()
    try:
        expected_installer_id = int(plan.get("installer_id", 0))
    except (TypeError, ValueError):
        expected_installer_id = 0
    if expected_installer_id <= 0 or not expected_name:
        raise ValueError(
            "Nao foi possivel confirmar o instalador atual antes da baixa"
        )

    for item in payload.get("instaladosserializados", []):
        serial = str(item.get("serialnumber", "")).strip().upper()
        if not serial:
            raise ValueError("O serial instalado nao foi informado")
        ownership = profile.api.find_serial_owner(serial, fresh=True)
        if not ownership.get("found"):
            raise ValueError(
                f"O serial {serial} nao foi localizado em nenhum estoque do "
                f"Imperium; estoque de {expected_name}; confira antes da baixa"
            )
        owner = ownership.get("owner") or {}
        try:
            owner_installer_id = int(owner.get("installer_id", 0))
        except (TypeError, ValueError):
            owner_installer_id = 0
        owner_name = str(
            owner.get("technician_name") or owner.get("stock_name") or ""
        ).strip()
        if owner_installer_id != expected_installer_id:
            raise ValueError(
                f"O serial {serial} nao pertence ao estoque de {expected_name}; "
                f"atualmente esta com {owner_name or 'outro tecnico'}"
            )


def _official_material_preparation_items(
    plan: dict,
    body: dict,
) -> list[dict]:
    """Return only materials that survived the official payload validation."""
    payload_items = (
        plan.get("payload", {})
        .get("ordemservico", {})
        .get("instaladosmiscelaneas", [])
    )
    descriptions: dict[str, str] = {}
    for item in body.get("materials") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if code and code not in descriptions:
            descriptions[code] = str(item.get("description", "")).strip()
    return [
        {
            "code": str(item.get("codigoequipamento", "")).strip(),
            "quantity": item.get("qtd", ""),
            "description": descriptions.get(
                str(item.get("codigoequipamento", "")).strip(),
                "",
            ),
        }
        for item in payload_items
    ]


def _report_base(
    order: Order,
    close_definition,
    *,
    transport: str,
    plan: dict | None = None,
    toa_paste_key: str = "",
    scheduled_date: str = "",
    retry_of_request_id: str = "",
    attempts: int = 1,
    installed_equipment: list | None = None,
    removed_equipment: list | None = None,
    materials: list | None = None,
    observation: str = "",
) -> dict:
    value = plan or {}
    inst_eq = installed_equipment or value.get("installed_equipment") or []
    rem_eq = removed_equipment or value.get("removed_equipment") or []
    mats = materials or value.get("materials") or []
    return {
        **order.to_dict(),
        "close_code": close_definition.code,
        "close_description": close_definition.description,
        "transport": transport,
        "installed_count": int(value.get("installed_count", 0)),
        "removed_count": int(value.get("removed_count", 0)),
        "material_count": int(value.get("material_count", 0)),
        "materials_summary": format_materials_readable(mats),
        "installed_equipment_summary": format_equipment_readable(inst_eq),
        "removed_equipment_summary": format_equipment_readable(rem_eq),
        "materials": mats if isinstance(mats, list) else [],
        "installed_equipment": inst_eq if isinstance(inst_eq, list) else [],
        "removed_equipment": rem_eq if isinstance(rem_eq, list) else [],
        "observation": str(observation or "")[:1000],
        "fingerprint": str(value.get("fingerprint", "")),
        "toa_paste_key": toa_paste_key,
        "scheduled_date": scheduled_date,
        "retry_of_request_id": retry_of_request_id,
        "attempts": max(1, int(attempts)),
    }


def _sanitize_response(response: object) -> str:
    """Return a truncated, safe string representation of an official API response.

    Strips control characters and limits length so the value is safe to store
    in the close report without leaking credentials or bloating the JSON file.
    """
    if response is None:
        return ""
    if isinstance(response, (dict, list)):
        try:
            text = json.dumps(response, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(response)
    else:
        text = str(response)
    # Remove control characters that are not plain whitespace.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text[:2000]



def _confirmation_order(record: dict) -> Order:
    return Order(
        id_os=int(record.get("id_os") or 0),
        num_os=str(record.get("num_os") or ""),
        contract=str(record.get("contract") or ""),
        id_service=int(record.get("id_service") or 0),
        service=str(record.get("service") or ""),
        status="EM CAMPO",
    )


def _start_close_confirmation(
    profile: ProfileRuntime,
    record: dict,
    *,
    initial_delay: float = 6.0,
) -> None:
    request_id = str(record.get("request_id", "")).strip()
    if not request_id:
        return
    key = (profile.key, request_id)
    with CLOSE_CONFIRM_LOCK:
        if key in CLOSE_CONFIRM_RUNNING:
            return
        CLOSE_CONFIRM_RUNNING.add(key)

    def worker() -> None:
        report_date = dt.date.fromisoformat(
            str(record.get("report_date") or dt.date.today().isoformat())
        )
        order = _confirmation_order(record)
        transport = str(record.get("transport") or "datasnap").strip().lower()
        close_code = _resolve_close_definition(
            profile,
            str(record.get("close_code") or "106"),
            transport,
        )
        last_error = ""
        checks = int(record.get("confirmation_checks") or 0)
        try:
            for delay in (initial_delay, 12.0, 20.0, 35.0, 60.0, 90.0, 120.0):
                time.sleep(delay)
                checks += 1
                try:
                    detail = profile.api._fetch_detail(order.id_os, timeout=25.0)
                    if profile.api._is_closed(order, detail, close_code):
                        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                        confirmed_record = profile.close_report.update(
                            request_id,
                            {
                                "state": "confirmed",
                                "category": "OBSERVED_CLOSED",
                                "category_label": "Fechada observada",
                                "message": (
                                    "OS encontrada fechada no Imperium com o codigo "
                                    f"{close_code.code}"
                                ),
                                "detail": (
                                    "O estado final foi lido diretamente na OS, mas "
                                    "essa verificacao nao identifica se a baixa veio "
                                    "do painel ou de uma pessoa."
                                ),
                                "confirmed_at": now,
                                "confirmation_checks": checks,
                                "last_confirmation_error": "",
                                "safe_to_retry": False,
                                "attribution": "unverified",
                            },
                            date=report_date,
                        )
                        with profile.cache_lock:
                            profile.order_cache.pop(order.id_os, None)
                        _resolve_failure(profile, order.id_os)
                        paste_key = str(record.get("toa_paste_key", "")).strip()
                        if paste_key:
                            try:
                                _save_material_assignment(profile, paste_key, order)
                            except OSError:
                                LOGGER.exception(
                                    "[%s] Falha ao salvar atribuicao TOA da OS %s",
                                    profile.label,
                                    order.num_os,
                                )
                        try:
                            profile.api._append_audit(
                                order,
                                close_code,
                                "FECHADA_OBSERVADA",
                            )
                        except OSError:
                            LOGGER.exception(
                                "[%s] Falha ao gravar CSV de auditoria da OS %s",
                                profile.label,
                                order.num_os,
                            )
                        LOGGER.info(
                            "[%s] OS %s encontrada fechada apos %s checagens; "
                            "origem nao atribuida",
                            profile.label,
                            order.num_os,
                            checks,
                        )
                        return
                    last_error = "Codigo ainda nao apareceu nos detalhes da OS"
                except (DataSnapError, OSError) as exc:
                    last_error = _exception_detail(exc)
                profile.close_report.update(
                    request_id,
                    {
                        "state": str(record.get("state") or "pending"),
                        "category": "PROCESSING",
                        "category_label": "Aguardando confirmacao",
                        "message": (
                            "Solicitacao registrada; aguardando o estado final "
                            "no Imperium"
                        ),
                        "detail": last_error,
                        "confirmation_checks": checks,
                        "last_confirmation_error": last_error,
                        "safe_to_retry": False,
                    },
                    date=report_date,
                )

            message = (
                "A solicitacao foi enviada, mas o Imperium nao confirmou a baixa. "
                "Nao repita automaticamente."
            )
            profile.close_report.update(
                request_id,
                {
                    "state": "uncertain",
                    "category": "CONFIRMATION",
                    "category_label": "Nao confirmada",
                    "message": message,
                    "detail": last_error,
                    "confirmation_checks": checks,
                    "last_confirmation_error": last_error,
                    "safe_to_retry": False,
                },
                date=report_date,
            )
            _record_failure(profile, order, DataSnapError(message), close_code.code)
            LOGGER.warning(
                "[%s] OS %s segue sem confirmacao apos %s checagens",
                profile.label,
                order.num_os,
                checks,
            )
        finally:
            with CLOSE_CONFIRM_LOCK:
                CLOSE_CONFIRM_RUNNING.discard(key)

    threading.Thread(
        target=worker,
        name=f"close-confirm-{profile.key}-{order_number(record)}",
        daemon=True,
    ).start()


def order_number(record: dict) -> str:
    return str(record.get("num_os") or record.get("id_os") or "unknown")


def _resume_close_confirmations() -> None:
    for profile in PROFILES.values():
        for record in profile.close_report.unresolved():
            if (
                record.get("transport") in {"official_http", "datasnap"}
                and int(record.get("confirmation_checks") or 0) < 7
            ):
                _start_close_confirmation(profile, record, initial_delay=2.0)


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_EXCLUSIVEADDRUSE,
                1,
            )
        super().server_bind()


# =============================================================================
# DOMINIUM COMPARTILHADO | SERVIDOR HTTP, ROTAS E PONTE ENTRE OS DOMINIOS
# =============================================================================
class PanelHandler(BaseHTTPRequestHandler):
    server_version = "DOMINIUM"
    sys_version = ""

    def version_string(self) -> str:
        return "DOMINIUM"

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        for cookie in getattr(self, "_response_cookies", ()):
            self.send_header("Set-Cookie", cookie)
        self.send_header(
            "X-Request-ID",
            getattr(self, "_request_id", secrets.token_hex(8)),
        )
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        LOGGER.info("HTTP %s", redact_log_text(format % args))

    def _session_token(self) -> str:
        raw_cookie = str(getattr(self, "headers", {}).get("Cookie", ""))
        if not raw_cookie:
            return ""
        parsed = SimpleCookie()
        try:
            parsed.load(raw_cookie)
        except Exception:
            return ""
        for name in ("__Host-dominium_session", "dominium_session"):
            morsel = parsed.get(name)
            if morsel is not None:
                return str(morsel.value)
        return ""

    def _auth_session(self, *, touch: bool = True) -> dict | None:
        cached = getattr(self, "_dominium_auth_session", None)
        if cached is not None:
            return cached
        session = AUTH_STORE.session(self._session_token(), touch=touch)
        self._dominium_auth_session = session
        return session

    def _queue_session_cookie(self, token: str) -> None:
        secure = os.environ.get("DOMINIUM_HTTPS", "").strip() == "1"
        name = "__Host-dominium_session" if secure else "dominium_session"
        attributes = [f"{name}={token}", "Path=/", "HttpOnly", "SameSite=Strict"]
        if secure:
            attributes.append("Secure")
        cookies = list(getattr(self, "_response_cookies", ()))
        cookies.append("; ".join(attributes))
        self._response_cookies = cookies

    def _clear_session_cookie(self) -> None:
        cookies = list(getattr(self, "_response_cookies", ()))
        for name in ("dominium_session", "__Host-dominium_session"):
            attributes = [
                f"{name}=",
                "Path=/",
                "Max-Age=0",
                "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
                "HttpOnly",
                "SameSite=Strict",
            ]
            if name.startswith("__Host-"):
                attributes.append("Secure")
            cookies.append("; ".join(attributes))
        self._response_cookies = cookies

    def _current_user(self) -> dict | None:
        session = self._auth_session()
        return session.get("user") if session else None

    def _auth_audit(
        self,
        action: str,
        result: str,
        *,
        channel: str = "dominium",
        target: str = "",
        technician: str = "",
        external_actor: str = "",
        metadata: dict | None = None,
    ) -> None:
        try:
            AUTH_STORE.audit(
                user=self._current_user(),
                action=action,
                result=result,
                request_id=getattr(self, "_request_id", ""),
                channel=channel,
                target=target,
                technician=technician,
                external_actor=external_actor,
                metadata=metadata,
            )
        except Exception:
            LOGGER.exception("Falha ao gravar auditoria do operador")

    def _security_preflight(self, method: str, path: str) -> bool:
        headers = getattr(self, "headers", None)
        if headers is None:  # Permite os testes unitarios sem um socket HTTP real.
            return True
        self._request_id = secrets.token_hex(8)
        client = getattr(self, "client_address", ("127.0.0.1", 0))[0]
        is_loopback = client in {"127.0.0.1", "::1", "local"}
        datalake_post = path in {
            "/api/toa-datalake/ingest",
            "/api/toa-datalake/detail-queue",
            "/api/toa-datalake/collect-now",
        } and method.upper() == "POST"
        if datalake_post:
            expected = os.environ.get("DOMINIUM_INGEST_TOKEN", "").strip()
            supplied = str(headers.get("Authorization", ""))
            token = supplied[7:].strip() if supplied.lower().startswith("bearer ") else ""
            if expected:
                content_type = str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"ok": False, "error": "A API aceita somente JSON"})
                    return False
                if not hmac.compare_digest(token, expected):
                    self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Token de ingestao invalido"})
                    return False
                return True
            if not is_loopback:
                self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "Ingestao remota desabilitada"})
                return False
        if not is_loopback:
            self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "Acesso remoto restrito ao receptor do datalake"})
            return False
        decision = validate_local_request(headers, method)
        if not decision.allowed:
            LOGGER.warning(
                "HTTP bloqueado request_id=%s path=%s motivo=%s",
                self._request_id,
                redact_log_text(path),
                decision.reason,
            )
            self._json(
                decision.status,
                {"ok": False, "error": decision.reason, "request_id": self._request_id},
            )
            return False
        if method.upper() == "POST":
            limit, window = rate_limit_for(path)
            key = f"{client}:{path}"
            if not LOCAL_RATE_LIMITER.allow(key, limit, window):
                LOGGER.warning(
                    "HTTP limitado request_id=%s path=%s",
                    self._request_id,
                    redact_log_text(path),
                )
                self._json(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    {
                        "ok": False,
                        "error": "Muitas solicitacoes; aguarde um minuto",
                        "request_id": self._request_id,
                    },
                )
                return False
        public_auth = path in {
            "/api/auth/bootstrap",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/session",
        }
        if path.startswith("/api/") and not public_auth:
            session = self._auth_session()
            if session is None:
                self._json(
                    HTTPStatus.UNAUTHORIZED,
                    {
                        "ok": False,
                        "error": "Entre no DOMINIUM para continuar",
                        "authentication_required": True,
                    },
                )
                return False
            user = session["user"]
            admin_path = path.startswith("/api/auth/users") or path == "/api/auth/pending-count"
            if admin_path and user.get("role") != "admin":
                self._json(
                    HTTPStatus.FORBIDDEN,
                    {"ok": False, "error": "Esta acao exige um administrador"},
                )
                return False
            if method.upper() == "POST":
                supplied_csrf = str(headers.get("X-CSRF-Token", ""))
                if not AUTH_STORE.validate_csrf(session, supplied_csrf):
                    self._json(
                        HTTPStatus.FORBIDDEN,
                        {"ok": False, "error": "Sessao invalida; atualize e entre novamente"},
                    )
                    return False
                if user.get("role") not in {"admin", "controller"}:
                    self._json(
                        HTTPStatus.FORBIDDEN,
                        {"ok": False, "error": "Seu perfil permite somente consulta"},
                    )
                    return False
        return True

    def _json(self, status: int, payload: dict | list) -> None:
        data = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            LOGGER.warning("O navegador encerrou a conexao antes da resposta")

    def _binary(
        self,
        status: int,
        data: bytes,
        *,
        content_type: str,
        filename: str,
    ) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            LOGGER.warning("O navegador encerrou o download antes da resposta")

    def _audio(self, data: bytes) -> None:
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", 'inline; filename="alerta-tec1.mp3"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            LOGGER.warning("O navegador encerrou o audio antes da resposta")

    def _body(self, max_length: int = 64 * 1024) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request length") from exc
        if length <= 0 or length > max_length:
            raise ValueError("Invalid request body")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON body") from exc
        if not isinstance(value, dict):
            raise ValueError("The request body must be an object")
        return value

    def _static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        path = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT.resolve() not in path.parents and path != STATIC_ROOT.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{media_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if not self._security_preflight("GET", parsed.path):
            return
        try:
            if parsed.path in (
                "/favicon.ico",
                "/.well-known/appspecific/com.chrome.devtools.json",
            ):
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if parsed.path == "/api/auth/bootstrap":
                self._json(HTTPStatus.OK, {"ok": True, **_auth_public_state()})
                return
            if parsed.path == "/api/auth/session":
                session = self._auth_session()
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "authenticated": session is not None,
                        **_auth_public_state(),
                        "user": session.get("user") if session else None,
                        "csrf_token": session.get("csrf_token") if session else "",
                    },
                )
                return
            if parsed.path == "/api/auth/users":
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "users": AUTH_STORE.list_users()},
                )
                return
            if parsed.path == "/api/auth/pending-count":
                # Admin-only: returns count of accounts awaiting approval.
                # The admin path gate (_security_preflight) already enforces role==admin.
                pending = [u for u in AUTH_STORE.list_users() if u.get("status") == "pending"]
                self._json(HTTPStatus.OK, {"ok": True, "pending_count": len(pending)})
                return
            if parsed.path == "/api/profiles":
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "default": DEFAULT_PROFILE,
                        "profiles": [
                            profile.public_dict() for profile in PROFILES.values()
                        ],
                    },
                )
                return
            if parsed.path == "/api/import-targets":
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "targets": list(IMPORT_TARGETS)},
                )
                return
            if parsed.path == "/api/import-history":
                query = parse_qs(parsed.query)
                profile = _profile_from_query(parsed.query)
                raw_date = str(query.get("date", [""])[0]).strip()
                audit_date = dt.date.fromisoformat(raw_date) if raw_date else dt.date.today()
                raw_limit = str(query.get("limit", ["80"])[0]).strip()
                limit = int(raw_limit or "80")
                self._json(
                    HTTPStatus.OK,
                    _read_import_audit_history(
                        profile,
                        audit_date=audit_date,
                        limit=limit,
                    ),
                )
                return
            if parsed.path == "/api/toa-datalake/status":
                status = TOA_DATALAKE.status()
                if TOA_LOCAL_COLLECTOR is not None:
                    status["local_collector"] = TOA_LOCAL_COLLECTOR.public_state()
                self._json(HTTPStatus.OK, status)
                return
            if parsed.path == "/api/toa-datalake/feed":
                query = parse_qs(parsed.query)
                self._json(
                    HTTPStatus.OK,
                    TOA_DATALAKE.feed(
                        profile=str(query.get("profile", [""])[0]),
                        date=str(query.get("date", [""])[0]),
                    ),
                )
                return
            if parsed.path == "/api/toa-datalake/detail-queue":
                query = parse_qs(parsed.query)
                self._json(
                    HTTPStatus.OK,
                    TOA_DATALAKE.detail_queue(
                        int(str(query.get("limit", ["100"])[0]))
                    ),
                )
                return
            datalake_record_match = re.fullmatch(
                r"/api/toa-datalake/records/(\d{5,18})", parsed.path
            )
            if datalake_record_match:
                self._json(
                    HTTPStatus.OK,
                    TOA_DATALAKE.record(datalake_record_match.group(1)),
                )
                return
            if parsed.path == "/api/voice/status":
                self._json(HTTPStatus.OK, {"ok": True, **EDGE_VOICE.status()})
                return
            if parsed.path == "/api/monitor/snapshot":
                profile = _profile_from_query(parsed.query)
                snapshot = _load_monitor_snapshot(profile)
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "active": snapshot is not None,
                        "snapshot": snapshot,
                    },
                )
                return
            if parsed.path == "/api/technicians":
                self._json(HTTPStatus.OK, TECHNICIANS.public_dict())
                return
            if parsed.path == "/api/toa-automation":
                try:
                    state = _remote_toa_automation_request("/toa/import-status")
                except Exception as exc:
                    state = TOA_AUTOMATION.public_state()
                    state.update({
                        "ok": False,
                        "remote_server": True,
                        "running": False,
                        "error": str(exc),
                    })
                self._json(HTTPStatus.OK, state)
                return
            if parsed.path == "/api/toa-live/status":
                self._json(HTTPStatus.OK, _toa_live_public_state())
                return
            if parsed.path == "/api/toa/v1/status":
                self._json(HTTPStatus.OK, TOA_CONNECTOR.status())
                return
            if parsed.path == "/api/toa/v1/openapi.json":
                self._json(HTTPStatus.OK, TOA_CONNECTOR.openapi_document())
                return
            toa_contract_match = re.fullmatch(
                r"/api/toa/v1/contracts/(\d{5,18})",
                parsed.path,
            )
            if toa_contract_match:
                query = parse_qs(parsed.query)
                refresh = str(query.get("refresh", ["true"])[0]).casefold()
                allow_stale = str(
                    query.get("allow_stale", ["true"])[0]
                ).casefold()
                boolean_values = {"1": True, "true": True, "yes": True,
                                  "0": False, "false": False, "no": False}
                if refresh not in boolean_values or allow_stale not in boolean_values:
                    raise ValueError("Parametro booleano invalido")
                self._json(
                    HTTPStatus.OK,
                    TOA_CONNECTOR.lookup(
                        toa_contract_match.group(1),
                        refresh=boolean_values[refresh],
                        allow_stale=boolean_values[allow_stale],
                    ),
                )
                return
            if parsed.path == "/api/toa-capture/lots":
                self._json(HTTPStatus.OK, TOA_CAPTURE_CATALOG.public_state())
                return
            if parsed.path == "/api/toa-contracts":
                query = parse_qs(parsed.query)
                self._json(
                    HTTPStatus.OK,
                    TOA_CONTRACTS.public_state(
                        profile=str(query.get("profile", [""])[0]),
                        date=str(query.get("date", [""])[0]),
                        slot=str(query.get("slot", [""])[0]),
                    ),
                )
                return
            if parsed.path == "/api/operational/contracts":
                query = parse_qs(parsed.query)
                try:
                    limit = int(query.get("limit", ["200"])[0])
                except ValueError as exc:
                    raise ValueError("Limite da base operacional invalido") from exc
                self._json(
                    HTTPStatus.OK,
                    OPERATIONAL_STORE.list_contracts(
                        profile=str(query.get("profile", [""])[0]).strip().lower(),
                        query=str(query.get("q", [""])[0]),
                        date=str(query.get("date", [""])[0]),
                        limit=limit,
                    ),
                )
                return
            operational_contract_match = re.fullmatch(
                r"/api/operational/contracts/(\d{5,18})",
                parsed.path,
            )
            if operational_contract_match:
                query = parse_qs(parsed.query)
                record = OPERATIONAL_STORE.contract(
                    operational_contract_match.group(1),
                    profile=str(query.get("profile", [""])[0]).strip().lower(),
                )
                if record is None:
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"ok": False, "error": "Contrato nao localizado na base operacional"},
                    )
                else:
                    self._json(HTTPStatus.OK, {"ok": True, "contract": record})
                return
            if parsed.path == "/api/operational/export.json":
                self._binary(
                    HTTPStatus.OK,
                    OPERATIONAL_STORE.export_json().read_bytes(),
                    content_type="application/json; charset=utf-8",
                    filename="dominium_operacional.json",
                )
                return
            if parsed.path == "/api/intelligence":
                query = parse_qs(parsed.query)
                raw_date = str(
                    query.get("date", [dt.date.today().isoformat()])[0]
                ).strip()
                report_date = dt.date.fromisoformat(raw_date)
                if abs((dt.date.today() - report_date).days) > 90:
                    raise ValueError("A inteligencia permite consultar ate 90 dias")
                try:
                    days = int(query.get("days", ["7"])[0])
                except ValueError as exc:
                    raise ValueError("Periodo invalido") from exc
                self._json(
                    HTTPStatus.OK,
                    build_intelligence_snapshot(PROFILES, report_date, days),
                )
                return
            if parsed.path == "/api/intelligence/report.pdf":
                query = parse_qs(parsed.query)
                raw_date = str(
                    query.get("date", [dt.date.today().isoformat()])[0]
                ).strip()
                report_date = dt.date.fromisoformat(raw_date)
                if abs((dt.date.today() - report_date).days) > 90:
                    raise ValueError("O relatorio permite consultar ate 90 dias")
                snapshot = build_intelligence_snapshot(PROFILES, report_date, 1)
                output_path = (
                    ROOT
                    / "output"
                    / "pdf"
                    / f"Relatorio_Diario_DOMINIUM_{report_date:%Y%m%d}.pdf"
                )
                render_daily_pdf(snapshot, output_path)
                self._binary(
                    HTTPStatus.OK,
                    output_path.read_bytes(),
                    content_type="application/pdf",
                    filename=output_path.name,
                )
                return
            if parsed.path == "/api/health-check":
                query = parse_qs(parsed.query)
                fresh = str(query.get("refresh", ["0"])[0]).lower() in {
                    "1", "true", "yes"
                }
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde para testar as bases"
                            ),
                        },
                    )
                    return
                try:
                    self._json(
                        HTTPStatus.OK,
                        HEALTH_CHECK.check(PROFILES, fresh=fresh),
                    )
                finally:
                    OPERATION_GATE.release()
                return
            if parsed.path == "/api/disconnect-automation":
                self._json(
                    HTTPStatus.OK,
                    DISCONNECT_AUTOMATION.public_state(),
                )
                return
            if parsed.path == "/api/logs":
                query = parse_qs(parsed.query)
                try:
                    limit = max(20, min(500, int(query.get("limit", ["160"])[0])))
                except ValueError:
                    limit = 160
                log_path = LOG_ROOT / "painel.log"
                lines: list[str] = []
                if log_path.is_file():
                    with log_path.open("rb") as stream:
                        stream.seek(0, os.SEEK_END)
                        size = stream.tell()
                        stream.seek(max(0, size - 512 * 1024), os.SEEK_SET)
                        text = stream.read().decode("utf-8", errors="replace")
                    noise = (
                        'HTTP "GET /api/toa-automation',
                        'HTTP "GET /favicon.ico',
                        'HTTP "GET /.well-known/',
                        'HTTP "GET /styles.css',
                        'HTTP "GET /app.js',
                    )
                    lines = [
                        line for line in text.splitlines()
                        if line.strip() and not any(item in line for item in noise)
                    ][-limit:]
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "lines": lines,
                        "count": len(lines),
                        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    },
                )
                return

            profile = _profile_from_query(parsed.query)
            if parsed.path.startswith("/api/imperium-official/"):
                operator = self._current_user() or {}
                if operator.get("role") not in {"admin", "controller"}:
                    self._json(
                        HTTPStatus.FORBIDDEN,
                        {"ok": False, "error": "Esta consulta exige perfil operacional"},
                    )
                    return
                client = _official_http_client(profile.key)
                if parsed.path == "/api/imperium-official/session":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "source": "imperium_official_http",
                            "credential_scope": "server_integration",
                            "profile": profile.key,
                            "identity": client.login_metadata(),
                        },
                    )
                    return
                if parsed.path == "/api/imperium-official/stocks":
                    query = parse_qs(parsed.query)
                    raw_installer = str(query.get("installer_id", [""])[0]).strip()
                    data = client.stock_catalog(raw_installer or None)
                    self._json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "source": "imperium_official_http",
                            "credential_scope": "server_integration",
                            "profile": profile.key,
                            "installer_id": int(raw_installer) if raw_installer else None,
                            "count": len(data) if isinstance(data, list) else None,
                            "stocks": data,
                        },
                    )
                    return
                official_stock_match = re.fullmatch(
                    r"/api/imperium-official/stocks/(\d+)/items",
                    parsed.path,
                )
                if official_stock_match:
                    stock_id = int(official_stock_match.group(1))
                    data = client.stock_items(stock_id)
                    self._json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "source": "imperium_official_http",
                            "credential_scope": "server_integration",
                            "profile": profile.key,
                            "stock_id": stock_id,
                            "count": len(data) if isinstance(data, list) else None,
                            "items": data,
                        },
                    )
                    return
            if parsed.path == "/api/status":
                payload = profile.api.status()
                payload["codes"] = _merged_close_code_metadata(profile)
                payload.update(profile.public_dict())
                self._json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/failures":
                failures = _failure_list(profile)
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "count": len(failures), "failures": failures},
                )
                return
            if parsed.path == "/api/close-report":
                query = parse_qs(parsed.query)
                raw_date = str(
                    query.get("date", [dt.date.today().isoformat()])[0]
                ).strip()
                report_date = dt.date.fromisoformat(raw_date)
                if abs((dt.date.today() - report_date).days) > 90:
                    raise ValueError("O relatorio permite consultar ate 90 dias")
                self._json(
                    HTTPStatus.OK,
                    profile.close_report.public_state(report_date),
                )
                return
            if parsed.path in ("/api/close-report/export.xlsx", "/api/close-report.xlsx"):
                query = parse_qs(parsed.query)
                raw_date = str(
                    query.get("date", [dt.date.today().isoformat()])[0]
                ).strip()
                report_date = dt.date.fromisoformat(raw_date)
                if abs((dt.date.today() - report_date).days) > 90:
                    raise ValueError("O relatorio permite consultar ate 90 dias")
                records = profile.close_report.list(report_date)
                xlsx_bytes = build_close_report_xlsx(records, report_date, profile.label)
                filename = f"relatorio-baixas-{profile.key}-{report_date:%Y%m%d}.xlsx"
                self._binary(
                    HTTPStatus.OK,
                    xlsx_bytes,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    filename=filename,
                )
                return
            installer_detail_match = re.fullmatch(
                r"/api/orders/(\d+)/installer",
                parsed.path,
            )
            if installer_detail_match is not None:
                id_os = int(installer_detail_match.group(1))
                with profile.cache_lock:
                    order = profile.order_cache.get(id_os)
                if order is None:
                    raise ValueError("Atualize a lista antes de consultar esta OS")
                if not OPERATION_GATE.acquire(timeout=10.0):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    result = profile.api.order_installer(order)
                    with profile.cache_lock:
                        profile.installer_overrides[id_os] = result[
                            "installer_name"
                        ]
                    self._json(HTTPStatus.OK, result)
                finally:
                    OPERATION_GATE.release()
                return
            installer_preview_match = re.fullmatch(
                r"/api/orders/(\d+)/installer-change-preview",
                parsed.path,
            )
            if installer_preview_match is not None:
                query = parse_qs(parsed.query)
                serial = query.get("serial", [""])[0].strip()
                if not serial:
                    raise ValueError("Informe o serial")
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    preview = _installer_change_preview(
                        profile,
                        int(installer_preview_match.group(1)),
                        serial,
                    )
                    self._json(HTTPStatus.OK, preview)
                finally:
                    OPERATION_GATE.release()
                return
            transfer_preview_match = re.fullmatch(
                r"/api/orders/(\d+)/serialized-transfer-preview",
                parsed.path,
            )
            if transfer_preview_match is not None:
                query = parse_qs(parsed.query)
                serial = query.get("serial", [""])[0].strip()
                if not serial:
                    raise ValueError("Informe o serial")
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    preview = _serialized_transfer_preview(
                        profile,
                        int(transfer_preview_match.group(1)),
                        serial,
                    )
                    self._json(HTTPStatus.OK, preview)
                finally:
                    OPERATION_GATE.release()
                return
            if parsed.path == "/api/stock/technicians":
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    technicians = profile.api.list_stock_technicians()
                    self._json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "count": len(technicians),
                            "technicians": technicians,
                        },
                    )
                finally:
                    OPERATION_GATE.release()
                return
            if parsed.path == "/api/stock/serial-owner":
                query = parse_qs(parsed.query)
                serial = query.get("serial", [""])[0].strip()
                if not serial:
                    raise ValueError("Informe o serial")
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    self._json(
                        HTTPStatus.OK,
                        profile.api.find_serial_owner(serial),
                    )
                finally:
                    OPERATION_GATE.release()
                return
            if parsed.path == "/api/stock":
                query = parse_qs(parsed.query)
                try:
                    stock_id = int(query.get("stock_id", ["0"])[0])
                except ValueError as exc:
                    raise ValueError("Estoque invalido") from exc
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    self._json(
                        HTTPStatus.OK,
                        profile.api.technician_stock(stock_id),
                    )
                finally:
                    OPERATION_GATE.release()
                return
            inventory_match = re.fullmatch(
                r"/api/orders/(\d+)/material-inventory",
                parsed.path,
            )
            if inventory_match is not None:
                id_os = int(inventory_match.group(1))
                with profile.cache_lock:
                    order = profile.order_cache.get(id_os)
                if order is None:
                    raise ValueError("Atualize a lista antes de consultar o estoque")
                if not OPERATION_GATE.acquire(timeout=10.0):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                try:
                    LOGGER.info(
                        "[%s] Consultando estoque para IdOS %s",
                        profile.label,
                        id_os,
                    )
                    query = parse_qs(parsed.query)
                    req_installer_id = query.get("installer_id", [None])[0]
                    resolved_installer_id = (
                        int(req_installer_id)
                        if req_installer_id and req_installer_id.isdigit()
                        else None
                    )
                    if resolved_installer_id is None:
                        req_login = (
                            query.get("login")
                            or query.get("technician_login")
                            or [""]
                        )[0].strip().upper()
                        req_name = (
                            query.get("name")
                            or query.get("technician")
                            or [""]
                        )[0].strip()
                        if not req_login and not req_name:
                            evidence = _live_technician_evidence(profile, order)
                            if evidence:
                                req_login = str(
                                    evidence.get("technician_login") or ""
                                ).strip().upper()
                                req_name = str(
                                    evidence.get("technician_name") or ""
                                ).strip()
                        if req_login or req_name:
                            st, _ = _resolve_imperium_installer_for_toa(
                                profile,
                                {"login": req_login, "name": req_name},
                            )
                            if st and st.get("installer_id"):
                                resolved_installer_id = int(st["installer_id"])
                    inventory = profile.api.list_material_inventory(
                        id_os,
                        installer_id=resolved_installer_id,
                    )
                    self._json(HTTPStatus.OK, inventory)
                finally:
                    OPERATION_GATE.release()
                return
            if parsed.path == "/api/orders":
                query = parse_qs(parsed.query)
                raw_date = query.get("date", [dt.date.today().isoformat()])[0]
                date = dt.date.fromisoformat(raw_date)
                status_filter = str(
                    query.get("status", ["field"])[0]
                ).strip().lower()
                allowed_statuses = {
                    "all",
                    "field",
                    "completed",
                    "canceled",
                    "rescheduled",
                }
                if status_filter not in allowed_statuses:
                    raise ValueError("Filtro de status invalido")
                service_type_filter = str(
                    query.get("service_type", ["all"])[0]
                ).strip().lower()
                allowed_service_types = {
                    "all",
                    "installation",
                    "technical",
                    "disconnection",
                    "stock",
                }
                if service_type_filter not in allowed_service_types:
                    raise ValueError("Filtro de tipo de servico invalido")
                if date != dt.date.today():
                    raise ValueError("O painel permite consultar somente a data de hoje")
                if not OPERATION_GATE.acquire(blocking=False):
                    with profile.cache_lock:
                        cached_orders = list(profile.order_cache.values())
                        cached_date = profile.cache_date
                    if (
                        cached_date == date
                        and status_filter == "field"
                        and service_type_filter == "all"
                    ):
                        LOGGER.info(
                            "[%s] Consulta atendida pelo cache: %s OS",
                            profile.label,
                            len(cached_orders),
                        )
                        cached_response_rows = _enrich_orders(
                            profile,
                            date,
                            cached_orders,
                        )
                        self._json(
                            HTTPStatus.OK,
                            {
                                "date": date.isoformat(),
                                "count": len(cached_orders),
                                "orders": cached_response_rows,
                                "stale": True,
                            },
                        )
                        _record_operational_orders(profile, cached_response_rows)
                        return
                    LOGGER.warning(
                        "[%s] Consulta aguardando outra operacao", profile.label
                    )
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                started = time.monotonic()
                try:
                    LOGGER.info(
                        "[%s] Consultando ordens de %s (status=%s, tipo=%s)",
                        profile.label,
                        date.isoformat(),
                        status_filter,
                        service_type_filter,
                    )
                    if status_filter == "all":
                        by_id: dict[int, Order] = {}
                        for current_status in (
                            "field",
                            "completed",
                            "canceled",
                            "rescheduled",
                        ):
                            for order in profile.api.list_orders(
                                date,
                                status=current_status,
                                service_type=service_type_filter,
                            ):
                                by_id[order.id_os] = order
                        orders = list(by_id.values())
                    else:
                        orders = profile.api.list_orders(
                            date,
                            status=status_filter,
                            service_type=service_type_filter,
                        )
                    operational_view = status_filter == "field"
                    if operational_view and service_type_filter == "all":
                        with profile.cache_lock:
                            profile.order_cache.clear()
                            profile.order_cache.update(
                                {order.id_os: order for order in orders}
                            )
                            profile.cache_date = date
                            profile.cache_generation = getattr(
                                profile,
                                "cache_generation",
                                0,
                            ) + 1
                        _reconcile_failures(profile, orders)
                    LOGGER.info(
                        "[%s] Consulta concluida: %s ordens em %.1fs",
                        profile.label,
                        len(orders),
                        time.monotonic() - started,
                    )
                    response_rows = (
                        _enrich_orders(profile, date, orders)
                        if operational_view
                        else _read_only_order_rows(profile, date, orders)
                    )
                    response_payload = {
                        "date": date.isoformat(),
                        "count": len(orders),
                        "status_filter": status_filter,
                        "service_type_filter": service_type_filter,
                        "read_only": not operational_view,
                        "orders": response_rows,
                    }
                finally:
                    OPERATION_GATE.release()
                self._json(HTTPStatus.OK, response_payload)
                _record_operational_orders(profile, response_rows)
                return
            self._static(parsed.path)
        except ValueError as exc:
            LOGGER.warning("Requisicao GET invalida %s: %s", self.path, exc)
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except (DataSnapError, OSError) as exc:
            LOGGER.exception("Erro ao atender GET %s", self.path)
            self._json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
        except Exception as exc:
            LOGGER.exception("Erro inesperado ao atender GET %s", self.path)
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"Erro interno: {exc}"},
            )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._security_preflight("POST", parsed.path):
            return
        if parsed.path == "/api/auth/register":
            try:
                if not _registration_enabled():
                    self._json(
                        HTTPStatus.FORBIDDEN,
                        {"ok": False, "error": "Novos cadastros estao desabilitados"},
                    )
                    return
                bootstrap_required = not AUTH_STORE.has_users()
                if bootstrap_required and not _bootstrap_enabled():
                    self._json(
                        HTTPStatus.FORBIDDEN,
                        {
                            "ok": False,
                            "error": "O administrador inicial deve ser criado diretamente no servidor",
                        },
                    )
                    return
                body = self._body(max_length=8 * 1024)
                # Build display_name from first_name + last_name;
                # fall back to display_name for backwards compat.
                first = " ".join(str(body.get("first_name") or "").strip().split())
                last = " ".join(str(body.get("last_name") or "").strip().split())
                if first or last:
                    display_name = f"{first} {last}".strip()
                else:
                    display_name = body.get("display_name") or ""
                user = AUTH_STORE.register(
                    body.get("username"),
                    display_name,
                    body.get("password"),
                    allow_bootstrap=_bootstrap_enabled(),
                    contact_email=body.get("contact_email") or None,
                )
                payload = {
                    "ok": True,
                    "user": user,
                    "pending_approval": user["status"] != "active",
                }
                if user["status"] == "active":
                    token, csrf, user = AUTH_STORE.create_session(
                        int(user["id"]),
                        str(self.headers.get("User-Agent", "")),
                    )
                    self._queue_session_cookie(token)
                    self._dominium_auth_session = {
                        "user": user,
                        "csrf_token": csrf,
                        "csrf_hash": hashlib.sha256(csrf.encode("ascii")).hexdigest(),
                    }
                    payload.update(
                        {"authenticated": True, "user": user, "csrf_token": csrf}
                    )
                AUTH_STORE.audit(
                    user=user,
                    action="auth.register",
                    result="active" if user["status"] == "active" else "pending",
                    request_id=getattr(self, "_request_id", ""),
                    target=user["username"],
                )
                self._json(HTTPStatus.CREATED, payload)
            except AuthError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/auth/login":
            try:
                body = self._body(max_length=8 * 1024)
                user = AUTH_STORE.authenticate(body.get("username"), body.get("password"))
                token, csrf, user = AUTH_STORE.create_session(
                    int(user["id"]),
                    str(self.headers.get("User-Agent", "")),
                )
                self._queue_session_cookie(token)
                self._dominium_auth_session = {
                    "user": user,
                    "csrf_token": csrf,
                    "csrf_hash": hashlib.sha256(csrf.encode("ascii")).hexdigest(),
                }
                AUTH_STORE.audit(
                    user=user,
                    action="auth.login",
                    result="success",
                    request_id=getattr(self, "_request_id", ""),
                    target=user["username"],
                )
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "authenticated": True, "user": user, "csrf_token": csrf},
                )
            except AuthError as exc:
                AUTH_STORE.audit(
                    user=None,
                    action="auth.login",
                    result="denied",
                    request_id=getattr(self, "_request_id", ""),
                )
                self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/auth/logout":
            user = self._current_user()
            AUTH_STORE.revoke_session(self._session_token())
            AUTH_STORE.audit(
                user=user,
                action="auth.logout",
                result="success",
                request_id=getattr(self, "_request_id", ""),
            )
            self._clear_session_cookie()
            self._json(HTTPStatus.OK, {"ok": True})
            return
        approve_match = re.fullmatch(r"/api/auth/users/(\d+)/approve", parsed.path)
        if approve_match:
            try:
                body = self._body(max_length=4 * 1024)
                current = self._current_user()
                user = AUTH_STORE.approve(
                    int(approve_match.group(1)),
                    role=str(body.get("role") or "controller"),
                    approved_by=int(current["id"]),
                )
                self._auth_audit(
                    "auth.user.approve",
                    "success",
                    target=user["username"],
                    metadata={"role": user["role"]},
                )
                self._json(HTTPStatus.OK, {"ok": True, "user": user})
            except AuthError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        reject_match = re.fullmatch(r"/api/auth/users/(\d+)/reject", parsed.path)
        if reject_match:
            try:
                body = self._body(max_length=4 * 1024)
                current = self._current_user()
                reason = str(body.get("reason") or "").strip()
                user = AUTH_STORE.reject(
                    int(reject_match.group(1)),
                    rejected_by=int(current["id"]),
                    reason=reason,
                )
                self._auth_audit(
                    "auth.user.reject",
                    "success",
                    target=user["username"],
                    metadata={"reason": reason[:200] if reason else ""},
                )
                self._json(HTTPStatus.OK, {"ok": True, "user": user})
            except AuthError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        identity_match = re.fullmatch(r"/api/auth/users/(\d+)/imperium-identity", parsed.path)
        if identity_match:
            try:
                body = self._body(max_length=4 * 1024)
                current = self._current_user()
                profile_key = str(body.get("profile") or "").strip().lower()
                if profile_key not in PROFILES:
                    raise AuthError("Base Imperium invalida")
                profile = PROFILES[profile_key]
                if not profile.controller_id:
                    raise AuthError("Esta base nao possui controlador DataSnap validado")
                user = AUTH_STORE.set_imperium_identity(
                    int(identity_match.group(1)),
                    profile_key=profile_key,
                    imperium_username=body.get("imperium_username"),
                    controller_id=profile.controller_id,
                    verified_by=int(current["id"]),
                )
                self._auth_audit(
                    "auth.imperium_identity.link",
                    "success",
                    target=user["username"],
                    external_actor=str(body.get("imperium_username") or ""),
                    metadata={"profile": profile_key, "controller_id": profile.controller_id},
                )
                self._json(HTTPStatus.OK, {"ok": True, "user": user})
            except AuthError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/toa-datalake/ingest":
            try:
                body = self._body(max_length=24 * 1024 * 1024)
                result = TOA_DATALAKE.ingest(body)
                _sync_datalake_to_operational(body)
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except Exception as exc:
                LOGGER.exception("Falha ao receber lote do datalake TOA")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        if parsed.path == "/api/toa-datalake/collect-now":
            try:
                if TOA_LOCAL_COLLECTOR is None:
                    raise RuntimeError("Coletor local TOA indisponivel")
                self._json(HTTPStatus.OK, TOA_LOCAL_COLLECTOR.collect_now())
            except (ValueError, RuntimeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except Exception as exc:
                LOGGER.exception("Falha na coleta local imediata do TOA")
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"Erro interno: {exc}"})
            return
        if parsed.path == "/api/toa-datalake/detail-queue":
            try:
                body = self._body(max_length=4 * 1024)
                self._json(
                    HTTPStatus.OK,
                    TOA_DATALAKE.detail_queue(int(body.get("limit") or 100)),
                )
            except (TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/voice/synthesize":
            try:
                body = self._body(max_length=4 * 1024)
                audio = EDGE_VOICE.synthesize(
                    body.get("text"),
                    voice=str(body.get("voice") or "pt-BR-FranciscaNeural"),
                    rate=str(body.get("rate") or "-5%"),
                )
                self._audio(audio)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except EdgeVoiceError as exc:
                LOGGER.warning("Voz neural indisponivel: %s", exc)
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": str(exc), "fallback": "browser"},
                )
            return
        if parsed.path == "/api/monitor/snapshot":
            try:
                requested_profile = _profile_from_query(parsed.query)
                body = self._body(max_length=24 * 1024 * 1024)
                grouped_sources = _route_monitor_sources(
                    _decode_monitor_sources(body)
                )
                snapshots = {
                    profile_key: _build_monitor_snapshot_batch(
                        PROFILES[profile_key], profile_sources, persist=False
                    )
                    for profile_key, profile_sources in grouped_sources.items()
                }
                for profile_key, snapshot_item in snapshots.items():
                    _persist_monitor_snapshot(PROFILES[profile_key], snapshot_item)
                selected_profile = (
                    requested_profile.key
                    if requested_profile.key in snapshots
                    else next(iter(snapshots))
                )
                snapshot = snapshots[selected_profile]
                summaries = {
                    profile_key: {
                        "profile": profile_key,
                        "source_files": item["source_files"],
                        "order_count": item["order_count"],
                        "assignment_count": item["assignment_count"],
                        "timeline_activity_count": item["timeline_activity_count"],
                        "reallocation_count": item["reallocation_count"],
                    }
                    for profile_key, item in snapshots.items()
                }
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "active": True,
                        "snapshot": snapshot,
                        "profiles": summaries,
                        "routed_from": requested_profile.key,
                        "routed_to": selected_profile,
                    },
                )
            except (ValueError, OperationBlocked) as exc:
                LOGGER.warning("CSV rejeitado no Monitor: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Erro ao atualizar Monitor por CSV")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        if parsed.path == "/api/monitor/snapshot/clear":
            try:
                profile = _profile_from_query(parsed.query)
                removed = _clear_monitor_snapshot(profile)
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "active": False, "removed": removed},
                )
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            return
        if parsed.path == "/api/intelligence/serial-audit":
            try:
                profile = _profile_from_query(parsed.query)
                body = self._body()
                report_date = dt.date.fromisoformat(
                    str(body.get("date") or dt.date.today().isoformat())
                )
                if abs((dt.date.today() - report_date).days) > 90:
                    raise ValueError("A auditoria permite consultar ate 90 dias")
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde para auditar os seriais"
                            ),
                        },
                    )
                    return
                try:
                    result = audit_serial_assignments(
                        profile,
                        LOG_ROOT / "toa-captures" / "live",
                        report_date,
                    )
                finally:
                    OPERATION_GATE.release()
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except (DataSnapError, OSError) as exc:
                LOGGER.exception("Falha na auditoria de seriais")
                self._json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
            except Exception as exc:
                LOGGER.exception("Erro inesperado na auditoria de seriais")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        if parsed.path.startswith("/api/disconnect-automation/"):
            try:
                body = self._body()
                operation = parsed.path.rsplit("/", 1)[-1]
                if operation == "prepare":
                    profile_key = str(body.get("profile", "natal")).strip()
                    target = str(body.get("target", "rn")).strip().lower()
                    date = str(
                        body.get("date", dt.date.today().isoformat())
                    ).strip()
                    if date != dt.date.today().isoformat():
                        raise ValueError(
                            "A automacao de desconexao aceita somente a data de hoje"
                        )
                    registry = TOA_CONTRACTS.public_state(
                        profile=profile_key,
                        date=date,
                    )
                    result = DISCONNECT_AUTOMATION.prepare(
                        registry.get("records", ()),
                        date=date,
                        profile=profile_key,
                        target=target,
                    )
                elif operation == "action":
                    result = DISCONNECT_AUTOMATION.action(body.get("action", ""))
                elif operation == "claim":
                    result = DISCONNECT_AUTOMATION.claim()
                elif operation == "update":
                    result = DISCONNECT_AUTOMATION.update(
                        str(body.get("contract", "")),
                        str(body.get("lease_token", "")),
                        str(body.get("status", "")),
                        result=(
                            body.get("result")
                            if isinstance(body.get("result"), dict)
                            else {}
                        ),
                        error=str(body.get("error", "")),
                        reasons=(
                            body.get("reasons")
                            if isinstance(body.get("reasons"), list)
                            else ()
                        ),
                    )
                else:
                    raise ValueError("Operacao de automacao invalida")
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception(
                    "Falha na automacao de desconexao em %s", parsed.path
                )
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        if parsed.path == "/api/toa-live/connect":
            try:
                body = self._body()
                self._json(
                    HTTPStatus.OK,
                    TOA_LIVE.open_session(
                        body.get("username", ""),
                        body.get("password", ""),
                        body.get("access_mode", "direct"),
                    ),
                )
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Falha ao conectar a sessao TOA ao vivo")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": str(exc)},
                )
            return
        if parsed.path == "/api/toa-live/lookup":
            try:
                body = self._body()
                profile = _profile_from_query(parsed.query)
                expected_profile = str(
                    body.get("expected_profile_key", "")
                ).strip().casefold()
                if expected_profile != profile.key:
                    raise OperationBlocked(
                        ("profile_scope_mismatch", "operation_blocked")
                    )
                query = body.get("query", body.get("contract", ""))
                contract, query_type, requested_os = _resolve_toa_live_reference(
                    profile,
                    query,
                )
                lookup_started_at = time.monotonic()
                if TOA_CONNECTOR.cloud_client.configured:
                    snapshot = TOA_CONNECTOR.cloud_client.lookup_contract(contract)
                    result = _cloud_snapshot_to_live_lookup(
                        snapshot,
                        time.monotonic() - lookup_started_at,
                    )
                else:
                    result = TOA_LIVE.lookup_contract(contract)
                _record_live_technician_evidence(profile, result)
                _record_operational_toa_capture(profile, result)
                self._json(
                    HTTPStatus.OK,
                    _prepare_toa_live_lookup(
                        profile,
                        result,
                        query="".join(re.findall(r"\d", str(query or ""))),
                        query_type=query_type,
                        requested_os=requested_os,
                    ),
                )
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except TimeoutError as exc:
                LOGGER.warning("Consulta TOA ao vivo expirou: %s", exc)
                self._json(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Falha na consulta TOA ao vivo")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": str(exc)},
                )
            return
        if parsed.path == "/api/toa-capture/analyze":
            try:
                body = self._body(max_length=512 * 1024)
                contracts = body.get("contracts", "")
                if isinstance(contracts, str):
                    contracts = re.split(r"[\s,;]+", contracts)
                elif not isinstance(contracts, list):
                    raise ValueError("A lista de contratos e invalida")
                result = TOA_CAPTURE_CATALOG.analyze(
                    str(body.get("lot_key", "")), contracts
                )
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc), "dry_run_only": True},
                )
            except Exception as exc:
                LOGGER.exception("Falha no teste de automacao somente leitura")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "ok": False,
                        "error": f"Erro interno: {exc}",
                        "dry_run_only": True,
                    },
                )
            return
        if parsed.path == "/api/toa-automation/run":
            try:
                state = _remote_toa_automation_request("/toa/import", method="POST")
            except Exception as exc:
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "remote_server": True, "error": str(exc)},
                )
                return
            self._json(HTTPStatus.ACCEPTED, state)
            return
        serialized_transfer_match = re.fullmatch(
            r"/api/orders/(\d+)/transfer-serial",
            parsed.path,
        )
        if serialized_transfer_match is not None:
            gate_acquired = False
            request_key: tuple[str, str] | None = None
            try:
                profile = _profile_from_query(parsed.query)
                body = self._body()
                if body.get("confirmed") is not True:
                    raise ValueError("Confirme a transferencia do equipamento")
                preview_token = str(body.get("preview_token", "")).strip()
                if not re.fullmatch(r"[0-9a-f]{64}", preview_token):
                    raise ValueError("A confirmacao da previa e invalida")
                request_key = (profile.key, preview_token)
                with SERIAL_TRANSFER_LOCK:
                    previous = SERIAL_TRANSFER_REQUESTS.get(request_key)
                    if previous and previous.get("state") == "done":
                        result = dict(previous["result"])
                        result["duplicate_request"] = True
                        self._json(HTTPStatus.OK, result)
                        return
                    if previous and previous.get("state") in (
                        "running",
                        "uncertain",
                    ):
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "uncertain": previous.get("state") == "uncertain",
                                "error": previous.get(
                                    "error",
                                    "Esta transferencia ja esta em andamento",
                                ),
                            },
                        )
                        return
                    stored = SERIAL_TRANSFER_PREVIEWS.get(request_key)
                    if stored is None or (
                        time.monotonic() - float(stored.get("created_at", 0))
                        > SERIAL_TRANSFER_PREVIEW_TTL
                    ):
                        SERIAL_TRANSFER_PREVIEWS.pop(request_key, None)
                        raise ValueError(
                            "A previa expirou. Localize o serial novamente"
                        )
                    preview = stored["preview"]
                    if int(preview["id_os"]) != int(
                        serialized_transfer_match.group(1)
                    ):
                        raise ValueError("A previa pertence a outra OS")
                    SERIAL_TRANSFER_REQUESTS[request_key] = {
                        "state": "running"
                    }
                if not OPERATION_GATE.acquire(blocking=False):
                    with SERIAL_TRANSFER_LOCK:
                        SERIAL_TRANSFER_REQUESTS.pop(request_key, None)
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                gate_acquired = True
                result = profile.api.transfer_serialized_equipment(preview)
                with SERIAL_TRANSFER_LOCK:
                    SERIAL_TRANSFER_REQUESTS[request_key] = {
                        "state": "done",
                        "result": result,
                    }
                    SERIAL_TRANSFER_PREVIEWS.pop(request_key, None)
                LOGGER.warning(
                    "[%s] Serial %s transferido de %s para %s",
                    profile.label,
                    result["serial"],
                    result["source"]["technician_name"],
                    result["target"]["technician_name"],
                )
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                if request_key is not None:
                    with SERIAL_TRANSFER_LOCK:
                        if SERIAL_TRANSFER_REQUESTS.get(
                            request_key, {}
                        ).get("state") == "running":
                            SERIAL_TRANSFER_REQUESTS.pop(request_key, None)
                LOGGER.warning("Transferencia serializada invalida: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except SerializedTransferUncertainError as exc:
                error = str(exc)
                if request_key is not None:
                    with SERIAL_TRANSFER_LOCK:
                        SERIAL_TRANSFER_REQUESTS[request_key] = {
                            "state": "uncertain",
                            "error": error,
                        }
                LOGGER.exception("Resultado incerto na transferencia serializada")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "uncertain": True, "error": error},
                )
            except (DataSnapError, OSError) as exc:
                if request_key is not None:
                    with SERIAL_TRANSFER_LOCK:
                        if SERIAL_TRANSFER_REQUESTS.get(
                            request_key, {}
                        ).get("state") == "running":
                            SERIAL_TRANSFER_REQUESTS.pop(request_key, None)
                LOGGER.exception("Falha antes da transferencia serializada")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "uncertain": False, "error": str(exc)},
                )
            except Exception as exc:
                if request_key is not None:
                    with SERIAL_TRANSFER_LOCK:
                        if SERIAL_TRANSFER_REQUESTS.get(
                            request_key, {}
                        ).get("state") == "running":
                            SERIAL_TRANSFER_REQUESTS.pop(request_key, None)
                LOGGER.exception("Erro inesperado na transferencia serializada")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            finally:
                if gate_acquired:
                    OPERATION_GATE.release()
            return
        installer_change_match = re.fullmatch(
            r"/api/orders/(\d+)/move-installer",
            parsed.path,
        )
        if installer_change_match is not None:
            gate_acquired = False
            request_key: tuple[str, str] | None = None
            changed: list[dict] = []
            try:
                profile = _profile_from_query(parsed.query)
                body = self._body()
                if body.get("confirmed") is not True:
                    raise ValueError("Confirme a alteracao do instalador")
                serial = str(body.get("serial", "")).strip().upper()
                preview_token = str(body.get("preview_token", "")).strip()
                if not re.fullmatch(r"[0-9a-f]{64}", preview_token):
                    raise ValueError("A confirmacao da previa e invalida")
                request_key = (profile.key, preview_token)
                with INSTALLER_CHANGE_REQUESTS_LOCK:
                    previous = INSTALLER_CHANGE_REQUESTS.get(request_key)
                    if previous and previous.get("state") == "done":
                        result = dict(previous["result"])
                        result["duplicate_request"] = True
                        self._json(HTTPStatus.OK, result)
                        return
                    if previous and previous.get("state") in (
                        "running",
                        "uncertain",
                    ):
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "uncertain": previous.get("state") == "uncertain",
                                "error": previous.get(
                                    "error",
                                    "Esta movimentacao ja esta em andamento",
                                ),
                            },
                        )
                        return
                    INSTALLER_CHANGE_REQUESTS[request_key] = {
                        "state": "running"
                    }
                if not OPERATION_GATE.acquire(blocking=False):
                    with INSTALLER_CHANGE_REQUESTS_LOCK:
                        INSTALLER_CHANGE_REQUESTS.pop(request_key, None)
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                gate_acquired = True
                preview = _installer_change_preview(
                    profile,
                    int(installer_change_match.group(1)),
                    serial,
                )
                if preview["preview_token"] != preview_token:
                    raise ValueError(
                        "As OS deste contrato mudaram desde a previa. "
                        "Revise a lista e confirme novamente"
                    )
                LOGGER.warning(
                    "[%s] Alterando %s OS do contrato %s para %s",
                    profile.label,
                    preview["count"],
                    preview["contract"],
                    preview["installer_name"],
                )
                for order in preview["orders"]:
                    profile.api.change_order_installer(
                        int(order["id_os"]),
                        int(preview["installer_id"]),
                    )
                    changed.append(order)
                    with profile.cache_lock:
                        profile.installer_overrides[int(order["id_os"])] = (
                            preview["installer_name"]
                        )
                result = {
                    "ok": True,
                    "contract": preview["contract"],
                    "installer_id": preview["installer_id"],
                    "installer_name": preview["installer_name"],
                    "count": len(changed),
                    "orders": changed,
                }
                with INSTALLER_CHANGE_REQUESTS_LOCK:
                    INSTALLER_CHANGE_REQUESTS[request_key] = {
                        "state": "done",
                        "result": result,
                    }
                LOGGER.warning(
                    "[%s] Instalador alterado em %s OS do contrato %s",
                    profile.label,
                    len(changed),
                    preview["contract"],
                )
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                if request_key is not None:
                    with INSTALLER_CHANGE_REQUESTS_LOCK:
                        if (
                            INSTALLER_CHANGE_REQUESTS.get(
                                request_key, {}
                            ).get("state")
                            == "running"
                        ):
                            INSTALLER_CHANGE_REQUESTS.pop(request_key, None)
                LOGGER.warning("Alteracao de instalador invalida: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except (DataSnapError, OSError) as exc:
                error = (
                    "O resultado da alteracao ficou incerto e nao sera "
                    "repetido automaticamente. Confira o contrato no "
                    f"Imperium: {exc}"
                )
                if request_key is not None:
                    with INSTALLER_CHANGE_REQUESTS_LOCK:
                        INSTALLER_CHANGE_REQUESTS[request_key] = {
                            "state": "uncertain",
                            "error": error,
                        }
                LOGGER.exception("Falha na alteracao de instalador")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "uncertain": True,
                        "error": error,
                        "changed": changed,
                    },
                )
            except Exception as exc:
                if request_key is not None:
                    with INSTALLER_CHANGE_REQUESTS_LOCK:
                        INSTALLER_CHANGE_REQUESTS[request_key] = {
                            "state": "uncertain",
                            "error": f"Erro interno: {exc}",
                        }
                LOGGER.exception("Erro inesperado na alteracao de instalador")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            finally:
                if gate_acquired:
                    OPERATION_GATE.release()
            return
        if parsed.path == "/api/orders/bulk-create":
            request_key: tuple[str, str] | None = None
            gate_acquired = False
            profile: ProfileRuntime | None = None
            preview = None
            started = time.monotonic()
            try:
                profile = _profile_from_query(parsed.query)
                if not profile.native_creation_enabled:
                    raise ValueError(
                        f"Criacao nativa de OS ainda nao mapeada para {profile.label}"
                    )
                body = self._body(max_length=256 * 1024)
                if body.get("confirmed") is not True:
                    raise ValueError("Confirme a criacao das ordens de servico")
                try:
                    technician_id = int(body.get("technician_id", 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError("Selecione um tecnico valido") from exc
                if technician_id <= 0:
                    raise ValueError("Selecione um tecnico valido")
                request_id = str(body.get("request_id", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]{12,100}", request_id):
                    raise ValueError("Identificador da operacao invalido")
                request_key = (profile.key, request_id)
                with BULK_CREATE_REQUESTS_LOCK:
                    previous = BULK_CREATE_REQUESTS.get(request_key)
                    if previous and previous.get("state") == "done":
                        payload = dict(previous["result"])
                        payload["repeated_request"] = True
                        self._json(HTTPStatus.OK, payload)
                        return
                    if previous and previous.get("state") == "running":
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "error": "Esta criacao de OS ainda esta em andamento",
                            },
                        )
                        return
                    if previous and previous.get("state") == "uncertain":
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "uncertain": True,
                                "error": previous["error"],
                            },
                        )
                        return
                    BULK_CREATE_REQUESTS[request_key] = {"state": "running"}

                gate_acquired = OPERATION_GATE.acquire(blocking=False)
                if not gate_acquired:
                    with BULK_CREATE_REQUESTS_LOCK:
                        BULK_CREATE_REQUESTS.pop(request_key, None)
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return

                technicians = profile.api.list_stock_technicians()
                technician = next(
                    (
                        item
                        for item in technicians
                        if int(item.get("installer_id", 0)) == technician_id
                    ),
                    None,
                )
                if technician is None:
                    raise ValueError(
                        "O tecnico selecionado nao foi localizado nesta base"
                    )
                technician_name = str(technician["technician_name"]).strip()
                preview = build_bulk_preview(
                    body.get("contracts", ""),
                    technician_name,
                    profile.key,
                    service=str(body.get("service", DEFAULT_SERVICE)),
                )
                client_mode = str(
                    body.get("client_mode", "registered")
                ).strip().lower()
                if client_mode not in {"registered", "fixed_123"}:
                    raise ValueError("Modo de cliente invalido para criacao de OS")

                LOGGER.info(
                    "[%s] Criando %s OS em massa para %s (%s)",
                    profile.label,
                    len(preview.orders),
                    preview.orders[0].technician,
                    client_mode,
                )
                result = profile.api.create_native_orders(
                    preview,
                    technician_id,
                    technician_name,
                    client_mode=client_mode,
                )
                result.update(
                    {
                        "profile": profile.key,
                        "company": profile.label,
                        "technician": preview.orders[0].technician,
                        "service": preview.orders[0].os_type,
                    }
                )
                _safe_append_import_audit(
                    profile,
                    {"key": "criacao-em-massa"},
                    preview,
                    time.monotonic() - started,
                    result=result,
                )
                if result.get("uncertain"):
                    error = str(
                        result.get("error")
                        or "O resultado da criacao precisa ser conferido"
                    )
                    with BULK_CREATE_REQUESTS_LOCK:
                        BULK_CREATE_REQUESTS[request_key] = {
                            "state": "uncertain",
                            "error": error,
                        }
                    LOGGER.error(
                        "[%s] Criacao nativa interrompida com resultado incerto: %s",
                        profile.label,
                        error,
                    )
                    self._json(HTTPStatus.BAD_GATEWAY, result)
                    return
                with BULK_CREATE_REQUESTS_LOCK:
                    BULK_CREATE_REQUESTS[request_key] = {
                        "state": "done",
                        "result": result,
                    }
                LOGGER.info(
                    "[%s] Criacao em massa concluida em %.1fs: %s criadas, "
                    "%s nao criadas",
                    profile.label,
                    time.monotonic() - started,
                    result["imported"],
                    result["not_imported"],
                )
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                if request_key is not None:
                    with BULK_CREATE_REQUESTS_LOCK:
                        current = BULK_CREATE_REQUESTS.get(request_key)
                        if current and current.get("state") == "running":
                            BULK_CREATE_REQUESTS.pop(request_key, None)
                LOGGER.warning("Criacao em massa invalida: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except (DataSnapError, OSError) as exc:
                confirmed = (
                    _confirm_bulk_creation(profile, preview)
                    if profile is not None and preview is not None
                    else None
                )
                if confirmed is not None:
                    confirmed.update(
                        {
                            "profile": profile.key,
                            "company": profile.label,
                            "technician": preview.orders[0].technician,
                            "service": preview.orders[0].os_type,
                        }
                    )
                    _safe_append_import_audit(
                        profile,
                        {"key": "criacao-em-massa"},
                        preview,
                        time.monotonic() - started,
                        result=confirmed,
                    )
                    if request_key is not None:
                        with BULK_CREATE_REQUESTS_LOCK:
                            BULK_CREATE_REQUESTS[request_key] = {
                                "state": "done",
                                "result": confirmed,
                            }
                    self._json(HTTPStatus.OK, confirmed)
                    return
                error = (
                    "O resultado da criacao nao foi confirmado. Consulte as OS "
                    "no Imperium antes de tentar novamente: " + str(exc)
                )
                if request_key is not None:
                    with BULK_CREATE_REQUESTS_LOCK:
                        BULK_CREATE_REQUESTS[request_key] = {
                            "state": "uncertain",
                            "error": error,
                        }
                if profile is not None and preview is not None:
                    _safe_append_import_audit(
                        profile,
                        {"key": "criacao-em-massa"},
                        preview,
                        time.monotonic() - started,
                        error=exc,
                    )
                LOGGER.exception("Falha na criacao de OS em massa")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "uncertain": True,
                        "error": error,
                        "orders": _bulk_preview_rows(
                            preview,
                            "RESULTADO NAO CONFIRMADO",
                        ) if preview is not None else [],
                    },
                )
            except Exception as exc:
                if request_key is not None:
                    with BULK_CREATE_REQUESTS_LOCK:
                        BULK_CREATE_REQUESTS[request_key] = {
                            "state": "uncertain",
                            "error": f"Falha inesperada: {exc}",
                        }
                LOGGER.exception("Erro inesperado na criacao de OS em massa")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            finally:
                if gate_acquired:
                    OPERATION_GATE.release()
            return
        if parsed.path == "/api/stock/writeoff":
            request_key: tuple[str, str] | None = None
            material_key: tuple[str, int, tuple[int, ...]] | None = None
            gate_acquired = False
            started = time.monotonic()
            try:
                profile = _profile_from_query(parsed.query)
                if not profile.material_writeoff_enabled:
                    raise ValueError(
                        "Baixa rapida de material ainda nao validada para "
                        f"{profile.label}"
                    )
                body = self._body(max_length=64 * 1024)
                if body.get("confirmed") is not True:
                    raise ValueError(
                        "Confirme a criacao da OS e a baixa do material"
                    )
                try:
                    stock_id = int(body.get("stock_id", 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError("Estoque invalido") from exc
                materials = body.get("materials", [])
                if not isinstance(materials, list):
                    raise ValueError("A lista de materiais e invalida")
                try:
                    material_ids = tuple(
                        sorted(
                            int(item.get("equipment_id", 0))
                            for item in materials
                        )
                    )
                except (AttributeError, TypeError, ValueError) as exc:
                    raise ValueError("A lista de materiais e invalida") from exc
                if not material_ids or any(value <= 0 for value in material_ids):
                    raise ValueError("Selecione pelo menos um material valido")
                material_key = (profile.key, stock_id, material_ids)
                with WRITE_OFF_REQUESTS_LOCK:
                    uncertain_error = WRITE_OFF_UNCERTAIN.get(material_key)
                if uncertain_error:
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "uncertain": True,
                            "error": uncertain_error,
                        },
                    )
                    return
                request_id = str(body.get("request_id", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]{12,100}", request_id):
                    raise ValueError("Identificador da operacao invalido")
                request_key = (profile.key, request_id)
                with WRITE_OFF_REQUESTS_LOCK:
                    previous = WRITE_OFF_REQUESTS.get(request_key)
                    if previous and previous.get("state") == "done":
                        cached = dict(previous["result"])
                        cached["duplicate_request"] = True
                        self._json(HTTPStatus.OK, cached)
                        return
                    if previous and previous.get("state") == "blocked":
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "uncertain": True,
                                "error": previous.get(
                                    "error",
                                    "Operacao pendente de verificacao no Imperium",
                                ),
                            },
                        )
                        return
                    if previous and previous.get("state") == "running":
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "error": (
                                    "Esta baixa ja esta sendo processada. "
                                    "Aguarde a confirmacao antes de tentar novamente."
                                ),
                            },
                        )
                        return
                    WRITE_OFF_REQUESTS[request_key] = {
                        "state": "running",
                        "created_at": time.monotonic(),
                    }

                if not OPERATION_GATE.acquire(blocking=False):
                    with WRITE_OFF_REQUESTS_LOCK:
                        WRITE_OFF_REQUESTS.pop(request_key, None)
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                gate_acquired = True
                LOGGER.warning(
                    "[%s] Iniciando baixa rapida no estoque %s (%s materiais)",
                    profile.label,
                    stock_id,
                    len(materials),
                )
                result = profile.api.quick_material_writeoff(stock_id, materials)
                with WRITE_OFF_REQUESTS_LOCK:
                    WRITE_OFF_REQUESTS[request_key] = {
                        "state": "done",
                        "created_at": time.monotonic(),
                        "result": result,
                    }
                    if len(WRITE_OFF_REQUESTS) > 200:
                        completed = sorted(
                            (
                                (key, value)
                                for key, value in WRITE_OFF_REQUESTS.items()
                                if value.get("state") == "done"
                                and key != request_key
                            ),
                            key=lambda pair: pair[1].get("created_at", 0),
                        )
                        excess = len(WRITE_OFF_REQUESTS) - 200
                        for key, _ in completed[:excess]:
                            WRITE_OFF_REQUESTS.pop(key, None)
                LOGGER.warning(
                    "[%s] Baixa rapida concluida: OS %s em %.1fs",
                    profile.label,
                    result.get("num_os"),
                    time.monotonic() - started,
                )
                self._json(HTTPStatus.OK, result)
            except (TypeError, ValueError) as exc:
                if request_key is not None:
                    with WRITE_OFF_REQUESTS_LOCK:
                        if (
                            WRITE_OFF_REQUESTS.get(request_key, {}).get("state")
                            == "running"
                        ):
                            WRITE_OFF_REQUESTS.pop(request_key, None)
                LOGGER.warning("Baixa rapida invalida: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except (DataSnapError, OSError) as exc:
                message = str(exc)
                normalized_message = unicodedata.normalize(
                    "NFD", message
                ).encode("ascii", "ignore").decode("ascii").upper()
                uncertain = (
                    "A OS " in normalized_message
                    and "FOI CRIADA" in normalized_message
                )
                if request_key is not None:
                    with WRITE_OFF_REQUESTS_LOCK:
                        if uncertain:
                            WRITE_OFF_REQUESTS[request_key] = {
                                "state": "blocked",
                                "created_at": time.monotonic(),
                                "error": message,
                            }
                            if material_key is not None:
                                WRITE_OFF_UNCERTAIN[material_key] = (
                                    message
                                    + ". Verifique essa OS no Imperium antes "
                                    "de reiniciar o painel e tentar novamente."
                                )
                        elif (
                            WRITE_OFF_REQUESTS.get(request_key, {}).get("state")
                            == "running"
                        ):
                            WRITE_OFF_REQUESTS.pop(request_key, None)
                LOGGER.exception("Falha na baixa rapida de material")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "uncertain": uncertain,
                        "error": message,
                    },
                )
            except Exception as exc:
                if request_key is not None:
                    with WRITE_OFF_REQUESTS_LOCK:
                        if (
                            WRITE_OFF_REQUESTS.get(request_key, {}).get("state")
                            == "running"
                        ):
                            WRITE_OFF_REQUESTS.pop(request_key, None)
                LOGGER.exception("Erro inesperado na baixa rapida de material")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            finally:
                if gate_acquired:
                    OPERATION_GATE.release()
            return
        if parsed.path in ("/api/stock/batch", "/api/stock/pdf/batch"):
            if not OPERATION_GATE.acquire(blocking=False):
                self._json(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": (
                            "Outra operacao esta em andamento; "
                            "aguarde o terminal concluir"
                        ),
                    },
                )
                return
            started = time.monotonic()
            try:
                profile = _profile_from_query(parsed.query)
                body = self._body(max_length=256 * 1024)
                raw_ids = body.get("stock_ids", [])
                if not isinstance(raw_ids, list):
                    raise ValueError("A selecao de tecnicos e invalida")
                stock_ids = [int(value) for value in raw_ids]
                include_zero = bool(body.get("include_zero", False))
                include_serials = bool(body.get("include_serials", True))
                LOGGER.info(
                    "[%s] Consultando lote de estoque para %s tecnicos",
                    profile.label,
                    len(stock_ids),
                )
                stocks = profile.api.technician_stocks(stock_ids)
                if parsed.path == "/api/stock/batch":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "count": len(stocks),
                            "include_zero": include_zero,
                            "include_serials": include_serials,
                            "stocks": stocks,
                        },
                    )
                else:
                    pdf = build_stock_pdf(
                        stocks,
                        company=profile.label,
                        include_zero=include_zero,
                        include_serials=include_serials,
                    )
                    today = dt.date.today().strftime("%Y%m%d")
                    if len(stocks) == 1:
                        name = stocks[0]["technician"].get(
                            "technician_name", "tecnico"
                        )
                        filename = safe_pdf_filename(
                            f"estoque-{name}-{today}"
                        )
                    else:
                        filename = safe_pdf_filename(
                            f"estoques-{profile.key}-{len(stocks)}-"
                            f"tecnicos-{today}"
                        )
                    self._binary(
                        HTTPStatus.OK,
                        pdf,
                        content_type="application/pdf",
                        filename=filename,
                    )
                LOGGER.info(
                    "[%s] Lote de estoque concluido em %.1fs",
                    profile.label,
                    time.monotonic() - started,
                )
            except (TypeError, ValueError) as exc:
                LOGGER.warning("Lote de estoque invalido: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except (DataSnapError, OSError) as exc:
                LOGGER.exception("Falha ao consultar lote de estoque")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Erro inesperado no lote de estoque")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            finally:
                OPERATION_GATE.release()
            return
        if parsed.path == "/api/imports/preview":
            try:
                body = self._body(max_length=12 * 1024 * 1024)
                target, profile, parsed_preview = _parse_import_request(body)
                registry = _safe_record_import_contracts(
                    parsed_preview, target, profile,
                )
                preview = parsed_preview.to_dict()
                preview["target"] = target
                preview["import_enabled"] = profile.close_enabled
                preview["agenda_registry"] = registry
                self._json(HTTPStatus.OK, {"ok": True, **preview})
            except ValueError as exc:
                LOGGER.warning("Previa de importacao invalida: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Erro ao preparar previa de importacao")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        if parsed.path == "/api/toa-agenda/import":
            try:
                body = self._body(max_length=24 * 1024 * 1024)
                profile_key = str(body.get("profile", "natal")).strip().lower()
                date = str(body.get("date", dt.date.today().isoformat())).strip()
                filename = str(body.get("filename", "agenda.csv")).strip()
                encoded = str(body.get("content_base64", "")).strip()
                if profile_key not in PROFILES:
                    raise ValueError("Base operacional invalida")
                try:
                    dt.date.fromisoformat(date)
                except ValueError as exc:
                    raise ValueError("Data da agenda invalida") from exc
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError) as exc:
                    raise ValueError("Conteudo da agenda invalido") from exc
                agenda = parse_agenda(content, filename, fallback_date=date)
                agenda["contracts"] = [
                    item for item in agenda["contracts"]
                    if item.get("date") == date
                ]
                agenda["stats"]["contracts_for_selected_date"] = len(agenda["contracts"])
                registry = TOA_CONTRACTS.replace_agenda(
                    agenda["contracts"],
                    profile=profile_key,
                    target=profile_key,
                    date=date,
                    source=filename,
                )
                self._json(HTTPStatus.OK, {
                    **agenda,
                    "profile": profile_key,
                    "date": date,
                    "registry": registry,
                })
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except Exception as exc:
                LOGGER.exception("Erro ao carregar agenda TOA")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        if parsed.path == "/api/imports/commit":
            if not OPERATION_GATE.acquire(blocking=False):
                self._json(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": (
                            "Outra operacao esta em andamento; "
                            "aguarde o terminal concluir"
                        ),
                    },
                )
                return
            started = time.monotonic()
            target = None
            profile = None
            preview = None
            try:
                body = self._body(max_length=12 * 1024 * 1024)
                target, profile, preview = _parse_import_request(
                    body,
                    require_approval=True,
                )
                if not profile.close_enabled:
                    raise ValueError(
                        f"Importacao ainda nao habilitada para {profile.label}"
                    )
                LOGGER.info(
                    "[%s] Importando %s OS do arquivo %s para %s",
                    profile.label,
                    len(preview.orders),
                    preview.filename,
                    target["label"],
                )
                result = profile.api.import_toa(preview)
                result["target"] = target
                result["filename"] = preview.filename
                result["excluded_count"] = len(preview.scope_exclusions)
                result["scope_exclusions"] = list(preview.scope_exclusions)
                LOGGER.info(
                    "[%s] Importacao concluida em %.1fs: %s importadas, "
                    "%s nao importadas",
                    profile.label,
                    time.monotonic() - started,
                    result["imported"],
                    result["not_imported"],
                )
                status_counts = Counter(
                    str(row.get("import_status", "SEM STATUS")) or "SEM STATUS"
                    for row in result.get("orders", ())
                    if isinstance(row, dict)
                )
                LOGGER.info(
                    "[%s] Resultado por status: %s",
                    profile.label,
                    "; ".join(
                        f"{status}: {count}"
                        for status, count in status_counts.most_common()
                    ),
                )
                _safe_append_import_audit(
                    profile,
                    target,
                    preview,
                    time.monotonic() - started,
                    result=result,
                )
                _safe_record_import_contracts(preview, target, profile)
                self._json(HTTPStatus.OK, result)
            except ValueError as exc:
                LOGGER.warning("Importacao invalida: %s", exc)
                if profile is not None and target is not None and preview is not None:
                    _safe_append_import_audit(
                        profile,
                        target,
                        preview,
                        time.monotonic() - started,
                        error=exc,
                    )
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except (DataSnapError, OSError) as exc:
                LOGGER.exception(
                    "Falha na importacao apos %.1fs",
                    time.monotonic() - started,
                )
                if profile is not None and target is not None and preview is not None:
                    _safe_append_import_audit(
                        profile,
                        target,
                        preview,
                        time.monotonic() - started,
                        error=exc,
                    )
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Erro inesperado durante a importacao")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            finally:
                OPERATION_GATE.release()
            return
        paste_match = re.fullmatch(
            r"/api/orders/(\d+)/material-paste",
            parsed.path,
        )
        if paste_match is not None:
            try:
                profile = _profile_from_query(parsed.query)
                id_os = int(paste_match.group(1))
                body = self._body(max_length=2 * 1024 * 1024)
                paste_text = str(body.get("text", ""))
                inventory = parse_toa_clipboard(paste_text)
                paste_key = _material_paste_key(paste_text)
                with profile.cache_lock:
                    order = profile.order_cache.get(id_os)
                if order is None:
                    raise ValueError("Atualize a lista antes de processar a colagem")
                if not OPERATION_GATE.acquire(blocking=False):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": "Outra operacao esta em andamento; aguarde o terminal concluir",
                        },
                    )
                    return
                try:
                    LOGGER.info(
                        "[%s] Processando colagem TOA para IdOS %s: %s equipamentos, %s miscelaneas",
                        profile.label,
                        id_os,
                        len(inventory.equipment),
                        len(inventory.materials),
                    )
                    if inventory.materials:
                        resolution = profile.api.resolve_toa_materials(
                            id_os,
                            [item.to_dict() for item in inventory.materials],
                        )
                        materials = resolution["materials"]
                    else:
                        materials = []
                    self._json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "id_os": id_os,
                            "paste_key": paste_key,
                            "material_assignment": _material_assignment(
                                profile,
                                paste_key,
                            ),
                            "equipment": [
                                item.to_dict() for item in inventory.equipment
                            ],
                            "materials": materials,
                            "return_stock_name": resolution.get(
                                "return_stock_name", ""
                            ) if inventory.materials else "",
                            "return_stock_error": resolution.get(
                                "return_stock_error", ""
                            ) if inventory.materials else "",
                            "validation": resolution.get("validation", {})
                            if inventory.materials
                            else {},
                        },
                    )
                finally:
                    OPERATION_GATE.release()
            except ValueError as exc:
                LOGGER.warning("Colagem TOA invalida: %s", exc)
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
            except (DataSnapError, OSError) as exc:
                LOGGER.exception("Falha ao processar colagem TOA")
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": str(exc)},
                )
            except Exception as exc:
                LOGGER.exception("Erro inesperado na colagem TOA")
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Erro interno: {exc}"},
                )
            return
        match = re.fullmatch(r"/api/orders/(\d+)/close", parsed.path)
        if match is None:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})
            return
        try:
            profile = _profile_from_query(parsed.query)
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        if not profile.close_enabled:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "ok": False,
                    "error": (
                        "Baixa ainda nao habilitada para esta base: "
                        "controlador do pacote DataSnap nao confirmado"
                    ),
                },
            )
            return

        id_os = int(match.group(1))
        started = time.monotonic()
        close_code = "106"
        order: Order | None = None
        report_record: dict | None = None
        report_date = dt.date.today()
        gate_acquired = False
        try:
            body = self._body()
            close_code = str(body.get("code", "106")).strip()
            transport = str(body.get("transport", "official_http")).strip().lower()
            if transport not in {"datasnap", "official_http"}:
                raise ValueError("Canal de baixa invalido")
            if transport == "datasnap":
                if not OPERATION_GATE.acquire(blocking=False):
                    LOGGER.warning(
                        "[%s] Baixa DataSnap de IdOS %s aguardando outra operacao",
                        profile.label,
                        id_os,
                    )
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": (
                                "Outra operacao DataSnap esta em andamento; "
                                "aguarde o terminal concluir"
                            ),
                        },
                    )
                    return
                gate_acquired = True
            operator = self._current_user() or {}
            datasnap_identity = (operator.get("imperium_identities") or {}).get(
                profile.key
            )
            if transport == "datasnap":
                if not datasnap_identity:
                    raise ValueError(
                        "DataSnap bloqueado: sua conta nao possui uma identidade "
                        f"Imperium validada para {profile.label}. Use a integracao "
                        "IMPERIUM ou solicite o vinculo ao administrador."
                    )
                if int(datasnap_identity.get("controller_id") or 0) != int(
                    profile.controller_id or 0
                ):
                    raise ValueError(
                        "DataSnap bloqueado: o controlador vinculado nao corresponde "
                        "ao pacote validado desta base"
                    )
            close_definition = _resolve_close_definition(
                profile,
                close_code,
                transport,
            )
            LOGGER.info(
                "[%s] Baixa solicitada para IdOS %s com codigo %s via %s",
                profile.label,
                id_os,
                close_code,
                transport,
            )
            with profile.cache_lock:
                order = profile.order_cache.get(id_os)
            if order is None:
                raise ValueError("Atualize a lista antes de baixar esta OS")
            if str(body.get("num_os", "")) != order.num_os:
                raise ValueError("O numero da OS nao corresponde a linha selecionada")
            _validated_close_operation(profile, order, body, close_code)
            paste_key = str(body.get("toa_paste_key", "")).strip().lower()
            materials = body.get("materials")
            if isinstance(materials, list):
                for material in materials:
                    if not isinstance(material, dict):
                        continue
                    if material.get("requires_confirmation") and (
                        material.get("equivalence_confirmed") is not True
                    ):
                        raise ValueError(
                            "Confirme as substituicoes equivalentes antes da baixa"
                        )
            if paste_key and materials:
                if not re.fullmatch(r"[0-9a-f]{8,64}", paste_key):
                    raise ValueError("A chave da colagem TOA e invalida")
                previous = _material_assignment(profile, paste_key)
                if previous and previous.get("os_number") != order.num_os:
                    raise ValueError(
                        "Estas miscelaneas TOA ja foram usadas na OS "
                        f"{previous.get('os_number', '')}"
                    )
            report_date = profile.cache_date or dt.date.today()
            # The official API locates an order by OS number + its current
            # scheduled date in Imperium. The cache date is therefore the source
            # of truth even when the TOA activity originated on an earlier day.
            raw_scheduled = str(body.get("scheduled_date", "")).strip()
            if raw_scheduled:
                try:
                    toa_scheduled_date = dt.date.fromisoformat(raw_scheduled)
                except ValueError:
                    raise ValueError(
                        "scheduled_date deve ser uma data ISO valida (YYYY-MM-DD)"
                    )
                if toa_scheduled_date != report_date:
                    LOGGER.warning(
                        "[%s] OS %s: data TOA %s difere da data atual no "
                        "Imperium %s; usando a data do Imperium",
                        profile.label,
                        order.num_os,
                        toa_scheduled_date,
                        report_date,
                    )
            retry_of_request_id = str(body.get("retry_of_request_id", "")).strip()[:80]
            effective_scheduled_date = report_date.isoformat()
            _reconcile_order_installer_with_toa(
                profile,
                order,
                body,
                report_date,
                gate_already_acquired=gate_acquired,
            )
            official_plan = (
                _build_official_panel_plan(
                    profile,
                    order,
                    close_definition,
                    body,
                    report_date,
                )
                if transport == "official_http"
                else None
            )
            if official_plan is not None:
                _validate_official_installed_serial_ownership(
                    profile,
                    official_plan,
                )
            # ----------------------------------------------------------------
            # Controlled retry gate
            # ----------------------------------------------------------------
            if retry_of_request_id:
                # 1. Confirm the OS is still EM CAMPO in the live cache.
                with profile.cache_lock:
                    live_order = profile.order_cache.get(id_os)
                if live_order is None:
                    raise ValueError(
                        "A OS nao esta na lista atual; atualize antes de repetir"
                    )
                # 2. Validate the previous record and mark it for retry.
                try:
                    profile.close_report.authorize_retry(
                        retry_of_request_id,
                        id_os,
                        date=report_date,
                        close_code=close_definition.code,
                        transport=transport,
                    )
                except ValueError as exc:
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": str(exc),
                            "retry_of_request_id": retry_of_request_id,
                        },
                    )
                    return
            report_payload = _report_base(
                    order,
                    close_definition,
                    transport=transport,
                    plan=official_plan or {
                        "installed_count": len(body.get("installed_equipment") or []),
                        "removed_count": len(body.get("removed_equipment") or []),
                        "material_count": len(materials or []),
                    },
                    toa_paste_key=paste_key if materials else "",
                    scheduled_date=effective_scheduled_date,
                    retry_of_request_id=retry_of_request_id,
                    installed_equipment=body.get("installed_equipment"),
                    removed_equipment=body.get("removed_equipment"),
                    materials=materials,
                    observation=body.get("observation") or body.get("notes") or "",
                )
            with profile.cache_lock:
                report_payload["technician"] = profile.installer_overrides.get(
                    id_os,
                    "",
                )
            if official_plan is not None:
                report_payload["technician_id"] = int(
                    official_plan.get("installer_id") or 0
                )
            report_payload["dominium_operator"] = {
                "id": operator.get("id"),
                "username": operator.get("username", ""),
                "display_name": operator.get("display_name", ""),
            }
            report_payload["external_actor"] = (
                {
                    "type": "technician",
                    "identifier": str(official_plan.get("technician_code") or ""),
                }
                if official_plan is not None
                else {
                    "type": "controller",
                    "identifier": str(datasnap_identity.get("username") or ""),
                    "controller_id": int(datasnap_identity.get("controller_id") or 0),
                }
            )
            report_record, duplicate = profile.close_report.begin(
                report_payload,
                date=report_date,
                block_active_duplicate=True,
            )
            if duplicate:
                self._json(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        "pending_confirmation": True,
                        "duplicate_request": True,
                        "safe_to_retry": False,
                        "request_id": report_record.get("request_id"),
                        "state": report_record.get("state"),
                        "id_os": order.id_os,
                        "num_os": order.num_os,
                        "code": close_code,
                        "message": (
                            "Esta OS ja possui uma solicitacao aguardando "
                            "confirmacao; nenhum novo envio foi feito"
                        ),
                    },
                )
                return
            if transport == "official_http":
                material_preparation = profile.api.prepare_official_materials(
                    order,
                    _official_material_preparation_items(official_plan, body),
                    expected_installer_id=official_plan["installer_id"],
                )
                resolved_materials = material_preparation.get("resolved_materials")
                if resolved_materials is not None:
                    official_plan["payload"]["ordemservico"][
                        "instaladosmiscelaneas"
                    ] = resolved_materials
                    official_plan["material_count"] = len(resolved_materials)
                LOGGER.warning(
                    "[%s] Integracao IMPERIUM: enviando uma unica solicitacao para "
                    "OS %s, codigo %s, tecnico %s",
                    profile.label,
                    order.num_os,
                    close_code,
                    official_plan["technician_code"],
                )
                official_result = _official_http_client(profile.key).close_order(
                    official_plan["payload"]
                )
                self._auth_audit(
                    "imperium.close",
                    "accepted",
                    channel="official_http",
                    target=f"contrato={order.contract};os={order.num_os}",
                    technician=str(official_plan.get("technician_code") or ""),
                    external_actor=str(official_plan.get("technician_code") or ""),
                    metadata={"code": close_code, "profile": profile.key},
                )
                now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                if material_preparation.get("transferred"):
                    preparation_detail = (
                        "Estoque complementado pelo RETORNO para "
                        f"{len(material_preparation.get('shortfalls', []))} "
                        "miscelanea(s). "
                    )
                else:
                    preparation_detail = (
                        "Saldo das miscelaneas validado no estoque do tecnico. "
                    )
                report_record = profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "pending",
                        "category": "QUEUED",
                        "category_label": "Na fila da API",
                        "message": (
                            "Solicitacao recebida pela integracao IMPERIUM; aguardando "
                            "confirmacao no Imperium"
                        ),
                        "detail": (
                            preparation_detail
                            + "HTTP aceito nao confirma a baixa. O painel "
                            "verificara o estado final da OS."
                        ),
                        "official_http_status": official_result.status,
                        "official_http_response": _sanitize_response(
                            official_result.response
                        ),
                        "accepted_at": now,
                        "safe_to_retry": False,
                        "attribution": "pending",
                    },
                    date=report_date,
                ) or report_record
                _start_close_confirmation(profile, report_record)
                self._json(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        "pending_confirmation": True,
                        "safe_to_retry": False,
                        "request_id": report_record.get("request_id"),
                        "state": report_record.get("state"),
                        "id_os": order.id_os,
                        "num_os": order.num_os,
                        "code": close_code,
                        "ignored_material_count": official_plan.get(
                            "ignored_material_count", 0
                        ),
                        "material_preparation": material_preparation,
                        "message": (
                            (
                                "Estoque complementado pelo RETORNO; "
                                if material_preparation.get("transferred")
                                else ""
                            )
                            + "solicitacao enviada uma vez pela integracao IMPERIUM; "
                            "aguardando confirmacao do Imperium"
                        ),
                    },
                )
                return
            if close_definition.productive:
                result = profile.api.close_productive(
                    order,
                    close_code,
                    installed_serial=str(body.get("installed_serial", "")),
                    removed_serial=str(body.get("removed_serial", "")),
                    removed_type=str(body.get("removed_type", "")),
                    installed_equipment=body.get("installed_equipment"),
                    removed_equipment=body.get("removed_equipment"),
                    materials=materials,
                )
            else:
                result = profile.api.close_order(
                    order,
                    close_definition,
                    observation=str(body.get("observation", "")),
                )
            self._auth_audit(
                "imperium.close",
                "confirmed",
                channel="datasnap",
                target=f"contrato={order.contract};os={order.num_os}",
                external_actor=str(datasnap_identity.get("username") or ""),
                metadata={
                    "code": close_code,
                    "profile": profile.key,
                    "controller_id": int(datasnap_identity.get("controller_id") or 0),
                },
            )
            with profile.cache_lock:
                profile.order_cache.pop(id_os, None)
            _resolve_failure(profile, id_os)
            if paste_key and materials:
                try:
                    _save_material_assignment(profile, paste_key, order)
                except OSError:
                    LOGGER.exception(
                        "[%s] Nao foi possivel gravar a atribuicao TOA da OS %s",
                        profile.label,
                        order.num_os,
                    )
            now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
            confirmed_record = profile.close_report.update(
                report_record["request_id"],
                {
                    "state": "confirmed",
                    "category": "SUCCESS",
                    "category_label": "Baixada",
                    "message": f"Baixa confirmada com o codigo {close_code}",
                    "detail": "Confirmacao recebida pelo protocolo DataSnap",
                    "accepted_at": now,
                    "confirmed_at": now,
                    "safe_to_retry": False,
                    "attribution": "panel_confirmed",
                },
                date=report_date,
            )
            LOGGER.info(
                "[%s] Baixa confirmada para IdOS %s em %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            self._json(HTTPStatus.OK, result)
        except (
            InstallerMismatchUnresolvedError,
            InstallerReassignmentFailedError,
            InstallerReassignmentUnconfirmedError,
        ) as exc:
            reason = getattr(exc, "code", "installer_mismatch_unresolved")
            LOGGER.warning(
                "[%s] Baixa de IdOS %s retida para Tratativa Humana: %s (%s)",
                profile.label,
                id_os,
                exc,
                reason,
            )
            if order is not None:
                _record_failure(profile, order, exc, close_code)
            if report_record is not None:
                profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "failed",
                        "category": "HUMAN_REVIEW",
                        "category_label": "Tratativa Humana",
                        "message": str(exc),
                        "detail": _exception_detail(exc),
                        "reason": reason,
                        "safe_to_retry": False,
                    },
                    date=report_date,
                )
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "ok": False,
                    "error": str(exc),
                    "reason": reason,
                    "human_review": True,
                },
            )
        except ValueError as exc:
            LOGGER.exception(
                "[%s] Requisicao de baixa invalida para IdOS %s",
                profile.label,
                id_os,
            )
            if report_record is not None:
                profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "failed",
                        "category": "VALIDATION",
                        "category_label": "Validacao",
                        "message": str(exc),
                        "detail": _exception_detail(exc),
                        "safe_to_retry": True,
                    },
                    date=report_date,
                )
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except ImperiumHTTPUncertainError as exc:
            LOGGER.exception(
                "[%s] Integracao IMPERIUM sem resposta conclusiva para IdOS %s apos %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
            if report_record is not None:
                report_record = profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "uncertain",
                        "category": "OFFICIAL_HTTP_UNCERTAIN",
                        "category_label": "Resposta incerta",
                        "message": str(exc),
                        "detail": _exception_detail(exc),
                        "accepted_at": now,
                        "safe_to_retry": False,
                        "attribution": "pending",
                    },
                    date=report_date,
                ) or report_record
                _start_close_confirmation(profile, report_record)
            self._json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "pending_confirmation": True,
                    "uncertain": True,
                    "safe_to_retry": False,
                    "request_id": (
                        report_record.get("request_id") if report_record else ""
                    ),
                    "state": "uncertain",
                    "id_os": order.id_os if order is not None else id_os,
                    "num_os": order.num_os if order is not None else "",
                    "code": close_code,
                    "message": str(exc),
                },
            )
        except ImperiumHTTPError as exc:
            LOGGER.exception(
                "[%s] Integracao IMPERIUM rejeitou/falhou para IdOS %s apos %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            detail = _sanitize_response(exc.response) or _exception_detail(exc)
            if order is not None:
                _record_failure(profile, order, exc, close_code)
            if report_record is not None:
                profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "failed",
                        "category": "OFFICIAL_HTTP_REJECTED",
                        "category_label": "Rejeitada pela API",
                        "message": str(exc),
                        "detail": detail,
                        "official_http_status": exc.status,
                        "official_http_response": _sanitize_response(exc.response),
                        "safe_to_retry": False,
                        "attribution": "rejected",
                    },
                    date=report_date,
                )
            response_status = (
                HTTPStatus.BAD_REQUEST
                if 400 <= int(exc.status or 0) < 500
                else HTTPStatus.BAD_GATEWAY
            )
            self._json(
                response_status,
                {
                    "ok": False,
                    "error": str(exc),
                    "category": "OFFICIAL_HTTP_REJECTED",
                    "category_label": "Rejeitada pela API",
                    "detail": detail,
                    "safe_to_retry": False,
                },
            )
        except CloseConfirmationUncertainError as exc:
            LOGGER.warning(
                "[%s] Baixa de IdOS %s enviada, mas ainda nao confirmada apos %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            if order is not None:
                _record_failure(profile, order, exc, close_code)
            if report_record is not None:
                now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                report_record = profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "uncertain",
                        "category": "CONFIRMATION",
                        "category_label": "Resultado incerto",
                        "message": str(exc),
                        "detail": _exception_detail(exc),
                        "accepted_at": now,
                        "safe_to_retry": False,
                        "attribution": "pending",
                    },
                    date=report_date,
                ) or report_record
                _start_close_confirmation(profile, report_record)
            self._json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "pending_confirmation": True,
                    "uncertain": True,
                    "safe_to_retry": False,
                    "request_id": (
                        report_record.get("request_id") if report_record else ""
                    ),
                    "state": "uncertain",
                    "id_os": order.id_os if order is not None else id_os,
                    "num_os": order.num_os if order is not None else "",
                    "code": close_code,
                    "message": str(exc),
                },
            )
        except MaterialTransferUncertainError as exc:
            LOGGER.exception(
                "[%s] Complemento de estoque sem confirmacao para IdOS %s "
                "apos %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            if order is not None:
                _record_failure(profile, order, exc, close_code)
            if report_record is not None:
                profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "uncertain",
                        "category": "MATERIAL_TRANSFER_UNCERTAIN",
                        "category_label": "Estoque incerto",
                        "message": str(exc),
                        "detail": _exception_detail(exc),
                        "safe_to_retry": False,
                        "attribution": "stock_preparation",
                    },
                    date=report_date,
                )
            self._json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "ok": False,
                    "error": str(exc),
                    "category": "MATERIAL_TRANSFER_UNCERTAIN",
                    "category_label": "Estoque incerto",
                    "safe_to_retry": False,
                    "close_sent": False,
                },
            )
        except (DataSnapError, OSError) as exc:
            LOGGER.exception(
                "[%s] Falha na baixa de IdOS %s apos %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            failure = (
                _record_failure(profile, order, exc, close_code)
                if order is not None
                else None
            )
            payload = {"ok": False, "error": str(exc)}
            if failure is not None:
                payload.update(
                    {
                        "category": failure["category"],
                        "category_label": failure["category_label"],
                        "detail": failure["detail"],
                    }
                )
                if report_record is not None:
                    profile.close_report.update(
                        report_record["request_id"],
                        {
                            "state": "failed",
                            "category": failure["category"],
                            "category_label": failure["category_label"],
                            "message": str(exc),
                            "detail": failure["detail"],
                            "safe_to_retry": True,
                        },
                        date=report_date,
                    )
            self._json(HTTPStatus.BAD_GATEWAY, payload)
        except Exception as exc:
            LOGGER.exception(
                "[%s] Erro inesperado na baixa de IdOS %s apos %.1fs",
                profile.label,
                id_os,
                time.monotonic() - started,
            )
            if report_record is not None:
                profile.close_report.update(
                    report_record["request_id"],
                    {
                        "state": "failed",
                        "category": "INTERNAL",
                        "category_label": "Erro interno",
                        "message": f"Erro interno: {exc}",
                        "detail": _exception_detail(exc),
                        "safe_to_retry": False,
                    },
                    date=report_date,
                )
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"Erro interno: {exc}"},
            )
        finally:
            _sync_operational_close_reports()
            if gate_acquired:
                OPERATION_GATE.release()

    def do_OPTIONS(self) -> None:
        self._request_id = secrets.token_hex(8)
        self._json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"ok": False, "error": "CORS nao habilitado", "request_id": self._request_id},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="DOMINIUM - painel unificado de OS")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost", "::1"} and not os.environ.get("DOMINIUM_INGEST_TOKEN", "").strip():
        raise SystemExit("Defina DOMINIUM_INGEST_TOKEN antes de expor o receptor na rede.")
    url = f"http://127.0.0.1:{args.port}"
    try:
        server = ExclusiveThreadingHTTPServer(
            (args.host, args.port),
            PanelHandler,
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048:
            webbrowser.open(url)
            return
        raise
    profile_summary = ", ".join(
        f"{profile.label}:{profile.port}" for profile in PROFILES.values()
    )
    LOGGER.info(
        "DOMINIUM iniciado em %s (PID %s, project_id=%s, root=%s, "
        "branch=%s, build=%s, DataSnap %s)",
        url,
        os.getpid(),
        PROJECT_IDENTITY.project_id,
        PROJECT_IDENTITY.root,
        PROJECT_IDENTITY.branch or "unknown",
        PROJECT_IDENTITY.build or "unknown",
        profile_summary,
    )
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    web_mode = os.getenv("DOMINIUM_WEB_MODE", "0") == "1"
    if web_mode:
        LOGGER.info("Modo web ativo; automacoes e navegadores TOA locais nao serao iniciados")
    else:
        if os.getenv("DOMINIUM_LOCAL_TOA_AUTOMATION", "0") == "1":
            TOA_AUTOMATION.start()
        else:
            LOGGER.info("TOA automatico local desativado; servidor remoto e a fonte oficial")
        TOA_LIVE.start()
        if TOA_LOCAL_COLLECTOR is not None:
            TOA_LOCAL_COLLECTOR.start()
        if TOA_BRIDGE_SERVER is not None:
            TOA_BRIDGE_SERVER.start()
    if web_mode:
        def web_startup_tasks() -> None:
            try:
                _sync_operational_close_reports()
                _resume_close_confirmations()
            except Exception:
                LOGGER.exception("Falha nas tarefas de inicializacao do modo web")

        threading.Thread(
            target=web_startup_tasks,
            name="dominium-web-startup",
            daemon=True,
        ).start()
    else:
        def local_startup_tasks() -> None:
            try:
                _bootstrap_operational_store()
                _resume_close_confirmations()
            except Exception:
                LOGGER.exception("Falha nas tarefas de inicializacao do modo local")

        threading.Thread(
            target=local_startup_tasks,
            name="dominium-local-startup",
            daemon=True,
        ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if not web_mode:
            if TOA_BRIDGE_SERVER is not None:
                TOA_BRIDGE_SERVER.stop()
            if TOA_LOCAL_COLLECTOR is not None:
                TOA_LOCAL_COLLECTOR.stop()
            TOA_LIVE.stop()
            TOA_AUTOMATION.stop()
        server.server_close()


if __name__ == "__main__":
    main()
