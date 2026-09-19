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
import datetime as dt
import hashlib
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


PROJECT_ID = "IMPERIUM_OLLAMA"
PROJECT_MARKER = ".imperium-project.json"
EXPECTED_PROJECT_ROOT = Path(
    r"C:\Users\Public\Documents\Dominium_Technet\DOMINIUM_APP"
)

IMPORT_ORIGINS = {
    "NTL": ("NATAL", "natal"),
    "PWM": ("NATAL", "natal"),
    "MRO": ("MOSSORO", "mossoro"),
    "JCR": ("RECIFE", "recife"),
    "FTZ": ("FORTALEZA", "fortaleza"),
}

OPEN_STATUSES = {
    "ABERTO",
    "EM CAMPO",
    "OPEN",
    "PENDENTE",
    "REAGENDADA",
}
CLOSED_STATUSES = {
    "BAIXADA",
    "CANCELADA",
    "CLOSED",
    "CONCLUIDA",
    "EXECUTADA",
    "FINALIZADA",
    "FECHADA",
}


class OperationBlocked(ValueError):
    def __init__(self, blockers: Iterable[str], message: str = "") -> None:
        self.blockers = _unique(blockers)
        detail = message or ", ".join(self.blockers) or "operation_blocked"
        super().__init__(detail)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized(value: object) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", _text(value))
        if not unicodedata.combining(character)
    ).upper()


def normalize_city(value: object) -> str:
    city = _normalized(value)
    if city == "PARNAMIRIM":
        return "NATAL"
    return city


def normalize_status(value: object) -> str:
    status = _normalized(value)
    if status in OPEN_STATUSES:
        return "open"
    if status in CLOSED_STATUSES:
        return "closed"
    return status.casefold() or "unknown"


def _canonical_item(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_item(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_item(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_collection(values: Iterable[object]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise OperationBlocked(("shared_state_contamination",))
    encoded = (
        json.dumps(
            _canonical_item(value),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        for value in values
    )
    return tuple(sorted(encoded))


def _state_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        _canonical_item(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(
        str(right.resolve())
    )


def _git_metadata(root: Path) -> tuple[str, str]:
    git_dir = root / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "", ""
    if not head.startswith("ref: "):
        return "", head[:40]
    reference = head[5:].strip()
    branch = (
        reference[len("refs/heads/") :]
        if reference.startswith("refs/heads/")
        else reference
    )
    try:
        build = (git_dir / reference).read_text(encoding="utf-8").strip()[:40]
    except OSError:
        build = ""
    return branch, build


@dataclass(frozen=True)
class ProjectIdentity:
    project_id: str
    root: str
    branch: str = ""
    build: str = ""

    @classmethod
    def load(
        cls,
        root: Path | str,
        *,
        expected_root: Path | str | None = None,
        allow_test_root: bool = False,
    ) -> "ProjectIdentity":
        resolved = Path(root).resolve()
        configured_root = (
            expected_root
            if expected_root is not None
            else os.environ.get("DOMINIUM_PROJECT_ROOT", "").strip()
            or EXPECTED_PROJECT_ROOT
        )
        expected = Path(configured_root).resolve()
        if not allow_test_root and not _same_path(resolved, expected):
            raise OperationBlocked(("wrong_project_root",))
        marker_path = resolved / PROJECT_MARKER
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise OperationBlocked(("wrong_project_identity",)) from exc
        if marker != {"project_id": PROJECT_ID}:
            raise OperationBlocked(("wrong_project_identity",))
        branch, build = _git_metadata(resolved)
        return cls(PROJECT_ID, str(resolved), branch, build)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "root": self.root,
            "branch": self.branch,
            "build": self.build,
        }


@dataclass(frozen=True)
class ImportScope:
    import_origin: str
    expected_city: str
    expected_profile_key: str
    source_file: str
    source_hash: str
    batch_id: str

    def __post_init__(self) -> None:
        origin = _text(self.import_origin).upper()
        city = normalize_city(self.expected_city)
        profile = _text(self.expected_profile_key).casefold()
        source_file = Path(_text(self.source_file)).name
        source_hash = _text(self.source_hash).casefold()
        batch_id = _text(self.batch_id)
        object.__setattr__(self, "import_origin", origin)
        object.__setattr__(self, "expected_city", city)
        object.__setattr__(self, "expected_profile_key", profile)
        object.__setattr__(self, "source_file", source_file)
        object.__setattr__(self, "source_hash", source_hash)
        object.__setattr__(self, "batch_id", batch_id)
        try:
            mapped_city, mapped_profile = IMPORT_ORIGINS[origin]
        except KeyError as exc:
            raise OperationBlocked(("unknown_import_origin",)) from exc
        blockers: list[str] = []
        if city != mapped_city:
            blockers.append("city_scope_mismatch")
        if profile != mapped_profile:
            blockers.append("profile_scope_mismatch")
        if not source_file or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            blockers.append("source_file_changed")
        if not batch_id:
            blockers.append("shared_state_contamination")
        if blockers:
            raise OperationBlocked(blockers)

    @classmethod
    def from_source(
        cls,
        filename: str,
        content: bytes,
        *,
        batch_id: str = "",
    ) -> "ImportScope":
        source_file = Path(str(filename)).name
        match = re.match(r"(?i)^Atividades-([A-Z0-9]+)-", source_file)
        origin = match.group(1).upper() if match else ""
        try:
            city, profile = IMPORT_ORIGINS[origin]
        except KeyError as exc:
            raise OperationBlocked(("unknown_import_origin",)) from exc
        source_hash = hashlib.sha256(bytes(content)).hexdigest()
        resolved_batch = _text(batch_id) or f"{origin}-{source_hash[:20]}"
        return cls(
            import_origin=origin,
            expected_city=city,
            expected_profile_key=profile,
            source_file=source_file,
            source_hash=source_hash,
            batch_id=resolved_batch,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ImportScope":
        return cls(
            import_origin=_text(value.get("import_origin")).upper(),
            expected_city=normalize_city(value.get("expected_city")),
            expected_profile_key=_text(
                value.get("expected_profile_key")
            ).casefold(),
            source_file=Path(_text(value.get("source_file"))).name,
            source_hash=_text(value.get("source_hash")).casefold(),
            batch_id=_text(value.get("batch_id")),
        )

    @property
    def batch_key(self) -> tuple[str, str, str, str]:
        return (
            self.import_origin,
            self.expected_profile_key,
            self.expected_city,
            self.batch_id,
        )

    def validate_target(self, profile_key: object, city: object) -> None:
        blockers: list[str] = []
        if _text(profile_key).casefold() != self.expected_profile_key:
            blockers.append("profile_scope_mismatch")
        if normalize_city(city) != self.expected_city:
            blockers.append("city_scope_mismatch")
        if blockers:
            raise OperationBlocked(blockers)

    def validate_source(self, filename: str, content: bytes) -> None:
        blockers: list[str] = []
        if Path(str(filename)).name != self.source_file:
            blockers.append("source_file_changed")
        if hashlib.sha256(bytes(content)).hexdigest() != self.source_hash:
            blockers.append("source_file_changed")
        if blockers:
            raise OperationBlocked(blockers)

    def to_dict(self) -> dict:
        return {
            "import_origin": self.import_origin,
            "expected_city": self.expected_city,
            "expected_profile_key": self.expected_profile_key,
            "source_file": self.source_file,
            "source_hash": self.source_hash,
            "batch_id": self.batch_id,
        }


@dataclass(frozen=True)
class OSIdentity:
    project_id: str
    profile_key: str
    city: str
    contract: str
    activity_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", _text(self.project_id))
        object.__setattr__(self, "profile_key", _text(self.profile_key).casefold())
        object.__setattr__(self, "city", normalize_city(self.city))
        object.__setattr__(self, "contract", _text(self.contract))
        object.__setattr__(self, "activity_id", _text(self.activity_id))
        if not self.activity_id:
            raise OperationBlocked(("missing_activity_id",))
        if self.project_id != PROJECT_ID:
            raise OperationBlocked(("wrong_project_identity",))
        if not self.profile_key:
            raise OperationBlocked(("profile_scope_mismatch",))
        if not self.city:
            raise OperationBlocked(("city_scope_mismatch",))
        if not self.contract:
            raise OperationBlocked(("contract_identity_mismatch",))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "OSIdentity":
        return cls(
            project_id=_text(value.get("project_id")),
            profile_key=_text(value.get("profile_key")),
            city=_text(value.get("city")),
            contract=_text(value.get("contract")),
            activity_id=_text(value.get("activity_id")),
        )

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.project_id,
            self.profile_key,
            self.city,
            self.contract,
            self.activity_id,
        )

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "profile_key": self.profile_key,
            "city": self.city,
            "contract": self.contract,
            "activity_id": self.activity_id,
        }


@dataclass(frozen=True)
class OSSnapshot:
    identity: OSIdentity
    status: str
    current_close_code: str | None
    materials: tuple[str, ...]
    equipments: tuple[str, ...]
    installer_id: str
    response_timestamp: str
    response_version: str
    state_hash: str

    @classmethod
    def create(
        cls,
        *,
        identity: OSIdentity,
        status: object,
        current_close_code: object = None,
        materials: Iterable[object] = (),
        equipments: Iterable[object] = (),
        installer_id: object,
        response_timestamp: object,
        response_version: object,
    ) -> "OSSnapshot":
        normalized_status = normalize_status(status)
        close_code = _text(current_close_code) or None
        frozen_materials = _canonical_collection(materials)
        frozen_equipments = _canonical_collection(equipments)
        installer = _text(installer_id)
        timestamp = _text(response_timestamp)
        version = _text(response_version)
        if not installer:
            raise OperationBlocked(("shared_state_contamination",))
        if not timestamp or not version:
            raise OperationBlocked(("stale_snapshot",))
        payload = {
            "identity": identity.to_dict(),
            "status": normalized_status,
            "current_close_code": close_code,
            "materials": frozen_materials,
            "equipments": frozen_equipments,
            "installer_id": installer,
            "response_version": version,
        }
        return cls(
            identity=identity,
            status=normalized_status,
            current_close_code=close_code,
            materials=frozen_materials,
            equipments=frozen_equipments,
            installer_id=installer,
            response_timestamp=timestamp,
            response_version=version,
            state_hash=_state_hash(payload),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "OSSnapshot":
        identity = OSIdentity.from_mapping(value)
        return cls.create(
            identity=identity,
            status=value.get("status"),
            current_close_code=value.get("current_close_code"),
            materials=value.get("materials") or (),
            equipments=value.get("equipments") or (),
            installer_id=value.get("installer_id"),
            response_timestamp=value.get("response_timestamp"),
            response_version=value.get("response_version"),
        )

    def to_dict(self) -> dict:
        return {
            "identity": self.identity.to_dict(),
            "status": self.status,
            "current_close_code": self.current_close_code,
            "materials": list(self.materials),
            "equipments": list(self.equipments),
            "installer_id": self.installer_id,
            "response_timestamp": self.response_timestamp,
            "response_version": self.response_version,
            "state_hash": self.state_hash,
        }


@dataclass(frozen=True)
class PlannedClose:
    identity: OSIdentity
    batch_key: tuple[str, str, str, str]
    close_code: str
    approved_state_hash: str
    source_hash: str
    planned_at: str


@dataclass(frozen=True)
class PreflightResult:
    allowed: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    approved_state_hash: str
    current_state_hash: str


@dataclass(frozen=True)
class ReconciliationIssue:
    code: str
    detail: str
    identity: OSIdentity


@dataclass(frozen=True)
class ExecutionAudit:
    operation_id: str
    identity: OSIdentity
    batch_key: tuple[str, str, str, str]
    planned_close_code: str
    state: str
    movement_hash: str
    issues: tuple[ReconciliationIssue, ...]
    created_at: str


@dataclass(frozen=True)
class MovementRecord:
    identity: OSIdentity
    kind: str
    item_key: str
    close_code: str


def _identity_blockers(
    expected: OSIdentity,
    actual: OSIdentity,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if actual.project_id != expected.project_id:
        blockers.append("wrong_project_identity")
    if actual.profile_key != expected.profile_key:
        blockers.append("profile_scope_mismatch")
    if actual.city != expected.city:
        blockers.append("city_scope_mismatch")
    if actual.contract != expected.contract:
        blockers.append("contract_identity_mismatch")
    if actual.activity_id != expected.activity_id:
        blockers.append("activity_identity_mismatch")
    return _unique(blockers)


def evaluate_preflight(
    *,
    scope: ImportScope,
    plan: PlannedClose,
    approved: OSSnapshot,
    current: OSSnapshot,
    dominium_snapshot: OSSnapshot | None = None,
    current_source_hash: str | None = None,
) -> PreflightResult:
    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(_identity_blockers(plan.identity, approved.identity))
    identity_changes = _identity_blockers(approved.identity, current.identity)
    blockers.extend(identity_changes)
    if plan.identity.profile_key != scope.expected_profile_key:
        blockers.append("profile_scope_mismatch")
    if plan.identity.city != scope.expected_city:
        blockers.append("city_scope_mismatch")
    if plan.batch_key != scope.batch_key:
        blockers.extend(("shared_state_contamination", "payload_scope_violation"))
    if plan.approved_state_hash != approved.state_hash:
        blockers.append("stale_snapshot")
    if plan.source_hash != scope.source_hash:
        blockers.append("source_file_changed")
    if current_source_hash is not None and current_source_hash != scope.source_hash:
        blockers.append("source_file_changed")
    if current.response_timestamp < approved.response_timestamp:
        blockers.append("stale_snapshot")
    if current.state_hash != approved.state_hash:
        blockers.extend(("remote_state_changed", "stale_snapshot"))
    if current.status != "open":
        blockers.append("already_closed")
    if current.current_close_code:
        blockers.append("already_closed")
        if current.current_close_code != plan.close_code:
            blockers.append(
                "already_closed_with_different_code:"
                f"{current.current_close_code}"
            )
    if (
        dominium_snapshot is not None
        and dominium_snapshot.status == "open"
        and (
            current.status == "closed"
            or current.current_close_code is not None
        )
    ):
        blockers.append("cross_system_status_conflict")
    if identity_changes:
        blockers.append("shared_state_contamination")
    blockers = list(_unique(blockers))
    if blockers:
        blockers.append("operation_blocked")
    return PreflightResult(
        allowed=not blockers,
        blockers=_unique(blockers),
        warnings=_unique(warnings),
        approved_state_hash=approved.state_hash,
        current_state_hash=current.state_hash,
    )


def validate_payload_scope(
    scope: ImportScope,
    plan: PlannedClose,
    metadata: Mapping[str, object],
) -> None:
    expected = {
        **plan.identity.to_dict(),
        "batch_id": scope.batch_id,
        "source_hash": scope.source_hash,
    }
    if any(_text(metadata.get(key)) != _text(value) for key, value in expected.items()):
        raise OperationBlocked(("payload_scope_violation",))


def reconcile_execution(
    *,
    plan: PlannedClose,
    final_snapshot: OSSnapshot,
    movements: Sequence[MovementRecord],
    previously_finalized: bool = False,
) -> tuple[ReconciliationIssue, ...]:
    issues: list[ReconciliationIssue] = []

    def issue(code: str, detail: str) -> None:
        issues.append(ReconciliationIssue(code, detail, plan.identity))

    if previously_finalized:
        issue("already_closed", "A identidade ja possui execucao finalizada")
    identity_changes = _identity_blockers(plan.identity, final_snapshot.identity)
    if identity_changes:
        issue(
            "shared_state_contamination",
            ", ".join(identity_changes),
        )
    for movement in movements:
        if movement.identity != plan.identity:
            issue(
                "shared_state_contamination",
                f"Movimento {movement.item_key} pertence a outra OS",
            )
        if movement.close_code != plan.close_code:
            issue(
                "material_close_code_inconsistency",
                f"Movimento {movement.item_key} usa codigo {movement.close_code}",
            )
    if movements and final_snapshot.status != "closed":
        issue(
            "material_close_code_inconsistency",
            "Ha movimento sem baixa final confirmada",
        )
    if (
        final_snapshot.current_close_code
        and final_snapshot.current_close_code != plan.close_code
    ):
        issue(
            "material_close_code_inconsistency",
            "Codigo final diverge do codigo associado aos movimentos",
        )
    return tuple(issues)


class OperationCoordinator:
    """Owns isolated in-memory state; callers must keep one explicit instance."""

    def __init__(self, project: ProjectIdentity) -> None:
        if project.project_id != PROJECT_ID:
            raise OperationBlocked(("wrong_project_identity",))
        self.project = project
        self._lock = threading.RLock()
        self._scopes: dict[tuple[str, str, str, str], ImportScope] = {}
        self._snapshots: dict[
            tuple[str, str, str, str, str], OSSnapshot
        ] = {}
        self._snapshot_batches: dict[
            tuple[str, str, str, str, str], tuple[str, str, str, str]
        ] = {}
        self._plans: dict[tuple[str, str, str, str, str], PlannedClose] = {}
        self._audits: dict[str, ExecutionAudit] = {}
        self._finalized: set[tuple[str, str, str, str, str]] = set()

    def register_scope(self, scope: ImportScope) -> None:
        with self._lock:
            previous = self._scopes.get(scope.batch_key)
            if previous is not None and previous != scope:
                raise OperationBlocked(("shared_state_contamination",))
            self._scopes[scope.batch_key] = scope

    def refresh_contract(
        self,
        scope: ImportScope,
        contract: object,
        responses: Sequence[Mapping[str, object]],
    ) -> tuple[OSSnapshot, ...]:
        self.register_scope(scope)
        expected_contract = _text(contract)
        if not expected_contract:
            raise OperationBlocked(("contract_identity_mismatch",))
        pending: dict[tuple[str, str, str, str, str], OSSnapshot] = {}
        for response in responses:
            snapshot = OSSnapshot.from_mapping(response)
            scope.validate_target(
                snapshot.identity.profile_key,
                snapshot.identity.city,
            )
            if snapshot.identity.project_id != self.project.project_id:
                raise OperationBlocked(("wrong_project_identity",))
            if snapshot.identity.contract != expected_contract:
                raise OperationBlocked(("contract_identity_mismatch",))
            if snapshot.identity.key in pending:
                raise OperationBlocked(("shared_state_contamination",))
            pending[snapshot.identity.key] = snapshot
        if not pending:
            raise OperationBlocked(("activity_identity_mismatch",))
        with self._lock:
            stale_keys = [
                key
                for key, snapshot in self._snapshots.items()
                if snapshot.identity.profile_key == scope.expected_profile_key
                and snapshot.identity.city == scope.expected_city
                and snapshot.identity.contract == expected_contract
            ]
            for key in stale_keys:
                self._snapshots.pop(key, None)
                self._snapshot_batches.pop(key, None)
                self._plans.pop(key, None)
            self._snapshots.update(pending)
            self._snapshot_batches.update(
                {key: scope.batch_key for key in pending}
            )
        return tuple(pending.values())

    def snapshot(self, identity: OSIdentity) -> OSSnapshot:
        with self._lock:
            try:
                return self._snapshots[identity.key]
            except KeyError as exc:
                raise OperationBlocked(("activity_identity_mismatch",)) from exc

    def update_exact(
        self,
        identity: OSIdentity,
        snapshot: OSSnapshot,
    ) -> None:
        if snapshot.identity != identity:
            raise OperationBlocked(("shared_state_contamination",))
        with self._lock:
            if identity.key not in self._snapshots:
                raise OperationBlocked(("activity_identity_mismatch",))
            self._snapshots[identity.key] = snapshot

    def validate_exact_scope(
        self,
        identity: OSIdentity,
        scope: ImportScope,
    ) -> None:
        with self._lock:
            registered = self._scopes.get(scope.batch_key)
            snapshot_batch = self._snapshot_batches.get(identity.key)
        blockers: list[str] = []
        if registered != scope:
            blockers.append("shared_state_contamination")
        if snapshot_batch != scope.batch_key:
            blockers.extend(("shared_state_contamination", "payload_scope_violation"))
        if blockers:
            raise OperationBlocked(blockers)

    def update_by_contract(self, _contract: str, _value: object) -> None:
        raise OperationBlocked(("contract_identity_mismatch",))

    def update_by_index(self, _index: int, _value: object) -> None:
        raise OperationBlocked(("activity_identity_mismatch",))

    def plan_close(
        self,
        scope: ImportScope,
        identity: OSIdentity,
        close_code: object,
        *,
        planned_at: str = "",
    ) -> PlannedClose:
        self.register_scope(scope)
        scope.validate_target(identity.profile_key, identity.city)
        self.validate_exact_scope(identity, scope)
        approved = self.snapshot(identity)
        code = _text(close_code)
        if not code:
            raise OperationBlocked(("payload_scope_violation",))
        plan = PlannedClose(
            identity=identity,
            batch_key=scope.batch_key,
            close_code=code,
            approved_state_hash=approved.state_hash,
            source_hash=scope.source_hash,
            planned_at=planned_at
            or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        )
        with self._lock:
            self._plans[identity.key] = plan
        return plan

    def preflight(
        self,
        scope: ImportScope,
        plan: PlannedClose,
        current: OSSnapshot,
        *,
        dominium_snapshot: OSSnapshot | None = None,
        current_source_hash: str | None = None,
    ) -> PreflightResult:
        approved = self.snapshot(plan.identity)
        return evaluate_preflight(
            scope=scope,
            plan=plan,
            approved=approved,
            current=current,
            dominium_snapshot=dominium_snapshot,
            current_source_hash=current_source_hash,
        )

    def audit_execution(
        self,
        operation_id: str,
        plan: PlannedClose,
        final_snapshot: OSSnapshot,
        movements: Sequence[MovementRecord],
    ) -> ExecutionAudit:
        operation = _text(operation_id)
        if not operation:
            raise OperationBlocked(("payload_scope_violation",))
        with self._lock:
            if operation in self._audits:
                raise OperationBlocked(("already_closed", "operation_blocked"))
            issues = reconcile_execution(
                plan=plan,
                final_snapshot=final_snapshot,
                movements=movements,
                previously_finalized=plan.identity.key in self._finalized,
            )
            movement_hash = _state_hash(
                {
                    "movements": [
                        {
                            "identity": movement.identity.to_dict(),
                            "kind": movement.kind,
                            "item_key": movement.item_key,
                            "close_code": movement.close_code,
                        }
                        for movement in movements
                    ]
                }
            )
            audit = ExecutionAudit(
                operation_id=operation,
                identity=plan.identity,
                batch_key=plan.batch_key,
                planned_close_code=plan.close_code,
                state="reconciliation_required" if issues else "consistent",
                movement_hash=movement_hash,
                issues=issues,
                created_at=dt.datetime.now(dt.timezone.utc).isoformat(
                    timespec="seconds"
                ),
            )
            self._audits[operation] = audit
            if not issues:
                self._finalized.add(plan.identity.key)
            return audit


def guard_before_write(
    result: PreflightResult,
    writer: Callable[[], object],
) -> object:
    if not result.allowed:
        raise OperationBlocked(result.blockers)
    return writer()


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate DOMINIUM project identity")
    parser.add_argument("--check-project", action="store_true")
    args = parser.parse_args()
    if not args.check_project:
        parser.error("use --check-project")
    try:
        identity = ProjectIdentity.load(Path(__file__).resolve().parent)
    except OperationBlocked as exc:
        print(json.dumps({"ok": False, "blockers": exc.blockers}))
        return 2
    print(json.dumps({"ok": True, **identity.to_dict()}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
