# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO - este arquivo nao consulta nem altera o Imperium.
#
# TOA
# - SIM - le a agenda exportada do TOA para ordenar consultas posteriores.
#
# Categoria deste arquivo: TOA.
# =============================================================================
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


_WINDOW_RE = re.compile(
    r"(?<!\d)(\d{1,2})(?::(\d{2}))?(?:h)?\s*(?:[-–—]|(?:[aàá]s?)|ate|at[eé])\s*(\d{1,2})(?::(\d{2}))?(?:h)?(?!\d)",
    re.IGNORECASE,
)


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", text.encode("ascii", "ignore").decode().lower()).split()
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, dt.date):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


def _contract(value: object) -> str:
    text = _text(value)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    return digits if 5 <= len(digits) <= 18 else ""


def _iso_date(value: object, fallback: str) -> str:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.date().isoformat() if isinstance(value, dt.datetime) else value.isoformat()
    text = _text(value).split(" ", 1)[0]
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return fallback


def normalize_window(value: object) -> dict[str, Any] | None:
    match = _WINDOW_RE.search(_text(value))
    if not match:
        return None
    start_hour, start_minute, end_hour, end_minute = (
        int(match.group(1)), int(match.group(2) or 0),
        int(match.group(3)), int(match.group(4) or 0),
    )
    if start_hour > 23 or end_hour > 23 or start_minute > 59 or end_minute > 59:
        return None
    start = start_hour * 60 + start_minute
    end = end_hour * 60 + end_minute
    if end <= start:
        return None
    return {
        "label": f"{start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d}",
        "start": start,
        "end": end,
    }


def _decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Nao foi possivel identificar a codificacao do CSV")


def _csv_rows(content: bytes) -> list[list[object]]:
    text = _decode_csv(content)
    sample = text[:65536]
    delimiter = max((";", ",", "\t"), key=lambda item: sample.count(item))
    return [list(row) for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _xlsx_rows(content: bytes) -> list[list[object]]:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - depende do pacote instalado
        raise ValueError("Leitura XLSX indisponivel; instale openpyxl") from exc
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"XLSX invalido: {exc}") from exc
    try:
        sheet = workbook.active
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _header_indexes(rows: list[list[object]]) -> tuple[int, int, int, int]:
    """Return header row, interval, contract and date indexes.

    Column J/W remain a guarded fallback for exports whose labels arrive with
    broken encoding, but rows are never selected by a fixed line number.
    """
    for row_index, row in enumerate(rows[:30]):
        labels = [_plain(value) for value in row]
        contract_index = next((
            i for i, label in enumerate(labels)
            if label in {
                "contrato", "nr contrato", "num contrato", "numero contrato",
                "contract", "contract id", "contrato id",
            }
        ), -1)
        interval_index = next((
            i for i, label in enumerate(labels)
            if label in {
                "intervalo de tempo", "intervalo tempo", "janela",
                "janela de atendimento", "janela atendimento", "faixa horaria",
                "faixa horario", "horario", "time window", "service window", "window",
            }
        ), -1)
        if contract_index >= 0 and interval_index >= 0:
            date_index = next((
                i for i, label in enumerate(labels)
                if label in {"data", "date", "data agendamento", "data agendada", "dt agendamento"}
            ), 1)
            return row_index, interval_index, contract_index, date_index
    if rows and len(rows[0]) >= 23:
        return 0, 9, 22, 1
    raise ValueError("Colunas 'Intervalo de Tempo' e 'Contrato' nao foram encontradas")


def _value(row: list[object], index: int) -> object:
    return row[index] if 0 <= index < len(row) else None


def parse_agenda(
    content: bytes,
    filename: str,
    *,
    fallback_date: str,
) -> dict[str, Any]:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".csv":
        rows = _csv_rows(content)
    elif suffix == ".xlsx":
        rows = _xlsx_rows(content)
    else:
        raise ValueError("Use um arquivo .csv ou .xlsx exportado do TOA")
    if not rows:
        raise ValueError("O arquivo de agenda esta vazio")

    header_row, interval_index, contract_index, date_index = _header_indexes(rows)
    stats = Counter()
    grouped: dict[str, dict[str, Any]] = {}
    for source_row, row in enumerate(rows[header_row + 1:], start=header_row + 2):
        stats["data_rows"] += 1
        contract = _contract(_value(row, contract_index))
        if not contract:
            stats["blank_or_invalid_contract"] += 1
            continue
        window = normalize_window(_value(row, interval_index))
        if window is None:
            stats["missing_or_invalid_window"] += 1
            continue
        date = _iso_date(_value(row, date_index), fallback_date)
        key = f"{date}:{contract}"
        current = grouped.get(key)
        record = {
            "contract": contract,
            "date": date,
            "window": window["label"],
            "window_start": window["start"],
            "window_end": window["end"],
            "source_rows": [source_row],
        }
        if current is None:
            grouped[key] = record
            continue
        stats["duplicate_contract_rows"] += 1
        current["source_rows"].append(source_row)
        if (window["end"], window["start"]) < (
            current["window_end"], current["window_start"]
        ):
            current.update(
                window=window["label"],
                window_start=window["start"],
                window_end=window["end"],
            )

    contracts = sorted(
        grouped.values(),
        key=lambda item: (
            item["date"], item["window_end"], item["window_start"], int(item["contract"])
        ),
    )
    stats["contracts"] = len(contracts)
    return {
        "ok": True,
        "filename": Path(filename).name,
        "header_row": header_row + 1,
        "columns": {
            "interval": interval_index + 1,
            "contract": contract_index + 1,
            "date": date_index + 1,
        },
        "stats": dict(stats),
        "contracts": contracts,
    }
