"""Split a completed TOA DMV_ADM CSV row into exact per-task evidence."""

from __future__ import annotations

import csv
import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

_SERIAL = r"[A-Za-z0-9._/\-]{4,50}"


@dataclass(frozen=True)
class ADMTaskEvidence:
    index: int
    os_number: str
    close_code: str
    service: str
    point: str
    installed_serials: tuple[str, ...]
    removed_serials: tuple[str, ...]
    source_file: str


def _unique(values):
    cleaned = (
        str(value).strip().upper().rstrip(".,;:")
        for value in values
        if str(value).strip()
    )
    return tuple(dict.fromkeys(value for value in cleaned if value))
def normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).strip().upper()
    return " ".join(text.split())


def _decode_csv(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _rows(path: Path) -> list[dict[str, str]]:
    text = _decode_csv(path)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    return [dict(row) for row in csv.DictReader(text.splitlines(), dialect=dialect)]


def _value(row: Mapping[str, object], header: str) -> str:
    expected = normalize_header(header)
    for key, value in row.items():
        if normalize_header(key) == expected:
            return str(value or "").strip()
    return ""


def _task_sections(validation: str) -> dict[int, str]:
    matches = list(re.finditer(r"\bTarefa\s+(\d+)\s*:", validation, flags=re.I))
    sections: dict[int, str] = {}
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(validation)
        index = int(match.group(1))
        if index in sections:
            raise ValueError(f"source_conflict:task={index}:duplicate_section")
        sections[index] = validation[match.end():end]
    return sections


def _movement_serials(section: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    swaps = re.findall(
        rf"Troca\s+do\s+equipamento\s+de\s+serial:\s*({_SERIAL})\s+"
        rf"pelo\s+de\s+serial:\s*({_SERIAL})",
        section,
        flags=re.I,
    )
    removed = [old for old, _new in swaps]
    installed = [new for _old, new in swaps]
    removed.extend(
        re.findall(
            rf"Desinstala.{{0,24}}?equipamento\s+de\s+serial:\s*({_SERIAL})",
            section,
            flags=re.I,
        )
    )
    installed.extend(
        re.findall(
            rf"(?<![A-Za-z])Instala.{{0,24}}?equipamento\s+de\s+serial:\s*({_SERIAL})",
            section,
            flags=re.I,
        )
    )
    return _unique(installed), _unique(removed)


def parse_adm_tasks(row: Mapping[str, object], *, source_file: str = "") -> tuple[ADMTaskEvidence, ...]:
    validation = _value(row, "Validacao Baixa")
    sections = _task_sections(validation)
    tasks: list[ADMTaskEvidence] = []
    for index in range(1, 11):
        os_number = re.sub(r"\D", "", _value(row, f"Numero da O.S {index}"))
        close_code = re.sub(r"\D", "", _value(row, f"Cod de Baixa {index}"))
        if not os_number:
            continue
        installed, removed = _movement_serials(sections.get(index, ""))
        tasks.append(
            ADMTaskEvidence(
                index=index,
                os_number=os_number,
                close_code=close_code,
                service=_value(row, f"Tipo O.S {index}"),
                point=_value(row, f"Ponto {index}"),
                installed_serials=installed,
                removed_serials=removed,
                source_file=source_file,
            )
        )
    validate_adm_task_identity(tuple(tasks))
    return tuple(tasks)


def validate_adm_task_identity(tasks: tuple[ADMTaskEvidence, ...]) -> None:
    """Repeated stock evidence is allowed only within one code and direction.

    The allocation planner deduplicates shared serials before any execution.
    """
    seen_os: set[str] = set()
    seen_index: set[int] = set()
    serial_owner: dict[str, tuple[str, str]] = {}
    for task in tasks:
        if task.os_number in seen_os or task.index in seen_index:
            raise ValueError(f"source_conflict:{task.os_number}:duplicate_task")
        seen_os.add(task.os_number)
        seen_index.add(task.index)
        for direction, serials in (("install", task.installed_serials),
                                   ("remove", task.removed_serials)):
            for serial in serials:
                serial = str(serial).strip().upper()
                identity = (task.close_code, direction)
                if serial in serial_owner and serial_owner[serial] != identity:
                    raise ValueError("adm_task_equipment_overlap")
                serial_owner[serial] = identity


def find_latest_adm_tasks(
    root: Path,
    *,
    contract: str,
    activity_id: str = "",
    when: dt.date | None = None,
    allowed_routes: Iterable[str] = ("NTL", "PWM"),
) -> tuple[ADMTaskEvidence, ...]:
    day = when or dt.date.today()
    routes = {
        str(value).strip().upper()
        for value in allowed_routes
        if str(value).strip().upper() in {"NTL", "PWM"}
    }
    export_roots = tuple(
        root / "logs" / source / day.strftime("%Y%m%d")
        for source in ("toa-exports", "toa-bucket-exports")
    )
    files = sorted(
        (
            path
            for export_root in export_roots
            for path in export_root.glob("*/*DMV_ADM_*.csv")
            if any(
                re.search(
                    rf"(?:^|[-_]){re.escape(route)}(?:[-_.]|$)",
                    path.name,
                    flags=re.I,
                )
                for route in routes
            )
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    requested_contract = re.sub(r"\D", "", str(contract or ""))
    requested_activity = re.sub(r"\D", "", str(activity_id or ""))
    merged: dict[str, ADMTaskEvidence] = {}
    matched_activity = requested_activity
    for path in files:
        for row in _rows(path):
            row_contract = re.sub(r"\D", "", _value(row, "Contrato"))
            if row_contract != requested_contract:
                continue
            row_activity = re.sub(r"\D", "", _value(row, "ID da Atividade"))
            if requested_activity and row_activity != requested_activity:
                continue
            tasks = parse_adm_tasks(row, source_file=str(path))
            if not tasks:
                continue
            # Without an explicit activity, ownership probing may select only
            # one activity, never combine different activities of a contract.
            if not matched_activity:
                matched_activity = row_activity
            if row_activity != matched_activity:
                continue
            for task in tasks:
                old = merged.get(task.os_number)
                if old is None:
                    merged[task.os_number] = task
                    continue
                values = {}
                for field in ("index", "close_code", "service", "point",
                              "installed_serials", "removed_serials"):
                    current_value = getattr(old, field)
                    older_value = getattr(task, field)
                    disagree = (
                        set(current_value) != set(older_value)
                        if field.endswith("_serials") else current_value != older_value
                    )
                    if current_value and older_value and disagree:
                        raise ValueError(f"source_conflict:{task.os_number}:csv_windows:{field}")
                    values[field] = current_value or older_value
                merged[task.os_number] = ADMTaskEvidence(
                    os_number=old.os_number, source_file=old.source_file, **values
                )
    result = tuple(sorted(merged.values(), key=lambda task: task.index))
    validate_adm_task_identity(result)
    return result
