# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO - este arquivo nao envia operacoes ao Imperium.
#
# TOA
# - SIM - sessao, coleta, importacao, inventario ou monitor do TOA.
#
# DOMINIUM COMPARTILHADO
# - A saida pode alimentar o restante do DOMINIUM em modo leitura.
#
# Categoria deste arquivo: TOA.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import datetime as dt
import logging
import re
import threading
from collections.abc import Callable
from pathlib import Path

from operation_scope import ImportScope, OperationBlocked, normalize_city
from toa_import import parse_toa_csv


LOGGER = logging.getLogger("imperium")

PROFILE_ROUTES = {
    "natal": ("NTL", "PWM"),
    "fortaleza": ("FTZ",),
    "mossoro": ("MRO",),
    "recife": ("JCR",),
}


class TOAContextIndex:
    """Indexes the latest current-day TOA exports without affecting imports."""

    def __init__(
        self,
        root: Path,
        technician_resolver: Callable[[object], dict | None] | None = None,
    ) -> None:
        self.root = root.resolve()
        self._technician_resolver = technician_resolver
        self._lock = threading.RLock()
        self._signature: tuple[tuple[str, int, int], ...] = ()
        self._orders: tuple[dict, ...] = ()

    @staticmethod
    def _route(path: Path) -> str:
        match = re.match(r"(?i)^Atividades-([A-Z0-9]+)-", path.name)
        return match.group(1).upper() if match else ""

    def _candidate_files(self, date: dt.date) -> list[Path]:
        date_marker = date.strftime("_%d_%m_%y.csv").casefold()
        candidates: list[Path] = []
        export_day = self.root / "logs" / "toa-exports" / date.strftime("%Y%m%d")
        if export_day.is_dir():
            run_dirs = sorted(
                (path for path in export_day.iterdir() if path.is_dir()),
                reverse=True,
            )
            if run_dirs:
                candidates.extend(run_dirs[0].glob("*.csv"))

        smoke = self.root / "tmp" / "toa-all-buckets-smoke"
        if smoke.is_dir():
            existing_routes = {self._route(path) for path in candidates}
            candidates.extend(
                path
                for path in smoke.glob("*.csv")
                if self._route(path) not in existing_routes
            )
        return sorted(
            path.resolve()
            for path in candidates
            if path.is_file() and date_marker in path.name.casefold()
        )

    def _public_order(self, order) -> dict:
        technician_login = (
            order.technician_login or order.technician
        ).strip().upper()
        technician = (
            self._technician_resolver(technician_login)
            if self._technician_resolver and technician_login
            else None
        )
        technician_name = (
            order.technician_name
            or (str(technician.get("name", "")) if technician else "")
            or technician_login
        )
        return {
            "technician": technician_name,
            "technician_login": technician_login,
            "technician_source": "toa_export",
            "city": order.city,
            "state": order.state,
            "district": order.district,
            "address": order.address,
            "address_complement": order.address_complement,
            "zip_code": order.zip_code,
            "time_window": order.time_window,
            "service_window": order.service_window,
            "started_at": order.started_at,
            "ended_at": order.ended_at,
            "start_end": order.start_end,
            "sla_start": order.sla_start,
            "sla_end": order.sla_end,
            "duration": order.duration,
            "travel_time": order.travel_time,
            "activity_type": order.activity_type,
            "work_skills": order.work_skills,
            "work_area": order.work_area,
            "assignment_time": order.assignment_time,
            "reservation_time": order.reservation_time,
            "work_order": order.work_order,
            "node": order.node,
            "point": order.point,
            "toa_status": order.activity_status,
            "toa_os_status": order.os_status,
            "coordinate_x": order.coordinate_x,
            "coordinate_y": order.coordinate_y,
            "activity_id": order.activity_id,
        }

    def _refresh(self, date: dt.date) -> None:
        paths = self._candidate_files(date)
        signature = tuple(
            (str(path), path.stat().st_mtime_ns, path.stat().st_size)
            for path in paths
        )
        if signature == self._signature:
            return

        orders: list[dict] = []
        for path in paths:
            try:
                content = path.read_bytes()
                preview = parse_toa_csv(content, path.name)
                scope = ImportScope.from_source(path.name, content)
            except OperationBlocked as exc:
                LOGGER.warning(
                    "Contexto TOA ignorou %s: %s",
                    path.name,
                    ", ".join(exc.blockers),
                )
                continue
            except ValueError as exc:
                if "Nenhuma OS foi encontrada" not in str(exc):
                    LOGGER.warning("Contexto TOA ignorou %s: %s", path.name, exc)
                continue
            except OSError as exc:
                LOGGER.warning("Contexto TOA nao leu %s: %s", path.name, exc)
                continue
            route = self._route(path)
            for order in preview.orders:
                context = self._public_order(order)
                context["route"] = route
                context["source_file"] = path.name
                context["import_scope"] = scope.to_dict()
                context["operational_city"] = normalize_city(order.city)
                context["contract"] = order.contract
                context["os_number"] = order.os_number
                orders.append(context)

        self._signature = signature
        self._orders = tuple(orders)
        LOGGER.info("Contexto TOA indexado: %s OS em %s arquivos", len(orders), len(paths))

    def validate_scope_source(self, scope: ImportScope, date: dt.date) -> None:
        with self._lock:
            matches = [
                path
                for path in self._candidate_files(date)
                if path.name == scope.source_file
            ]
            if len(matches) != 1:
                raise OperationBlocked(
                    ("source_file_changed", "shared_state_contamination")
                )
            try:
                content = matches[0].read_bytes()
            except OSError as exc:
                raise OperationBlocked(("source_file_changed",)) from exc
            scope.validate_source(matches[0].name, content)

    def enrich(self, profile_key: str, date: dt.date, orders: list) -> list[dict]:
        with self._lock:
            self._refresh(date)
            routes = PROFILE_ROUTES.get(profile_key, ())
            result = []
            matched = 0
            for order in orders:
                payload = order.to_dict()
                candidates = [
                    context
                    for context in self._orders
                    if context.get("route") in routes
                    and context.get("os_number") == order.num_os.strip()
                    and context.get("contract") == order.contract
                ]
                if len(candidates) == 1:
                    payload.update(candidates[0])
                    matched += 1
                elif len(candidates) > 1:
                    payload["operation_blockers"] = [
                        "shared_state_contamination"
                    ]
                else:
                    payload["operation_blockers"] = ["missing_activity_id"]
                result.append(payload)
            LOGGER.info(
                "[%s] Contexto TOA aplicado em %s de %s OS",
                profile_key.upper(),
                matched,
                len(result),
            )
            return result
