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
from __future__ import annotations

import datetime as dt
import json
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping

from toa_capture import CaptureSchemaError, normalize_entry


FINAL_STATES = {"confirmed", "failed", "uncertain"}


def _text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized(value: object) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", _text(value)).upper()
        if unicodedata.category(character) != "Mn"
    )


def _parse_timestamp(value: object) -> dt.datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_seconds(record: Mapping[str, Any]) -> float | None:
    started = _parse_timestamp(record.get("created_at"))
    ended = _parse_timestamp(
        record.get("confirmed_at") or record.get("updated_at")
    )
    if started is None or ended is None:
        return None
    if started.tzinfo is None and ended.tzinfo is not None:
        started = started.replace(tzinfo=ended.tzinfo)
    if ended.tzinfo is None and started.tzinfo is not None:
        ended = ended.replace(tzinfo=started.tzinfo)
    return max(0.0, (ended - started).total_seconds())


def _report_technician(record: Mapping[str, Any], profile: object) -> tuple[str, int]:
    name = _text(record.get("technician"))
    identifier = int(record.get("technician_id") or 0)
    if name:
        return name, identifier
    try:
        id_os = int(record.get("id_os") or 0)
        with profile.cache_lock:
            order = profile.order_cache.get(id_os)
            override = profile.installer_overrides.get(id_os, "")
        if override:
            return _text(override), identifier
        if order is not None:
            value = order.to_dict()
            return _text(value.get("technician") or value.get("installer")), identifier
    except (AttributeError, TypeError, ValueError):
        pass
    return "Nao identificado", identifier


def build_intelligence_snapshot(
    profiles: Mapping[str, object],
    end_date: dt.date,
    days: int = 7,
) -> dict[str, Any]:
    days = max(1, min(int(days), 31))
    start_date = end_date - dt.timedelta(days=days - 1)
    base_rows: list[dict[str, Any]] = []
    technician_data: dict[tuple[str, int], dict[str, Any]] = {}
    daily: dict[str, Counter] = defaultdict(Counter)
    all_codes: Counter = Counter()
    all_failures: Counter = Counter()
    totals: Counter = Counter()
    durations: list[float] = []

    for profile_key, profile in profiles.items():
        base = Counter()
        base_durations: list[float] = []
        for offset in range(days):
            report_date = start_date + dt.timedelta(days=offset)
            for record in profile.close_report.list(report_date):
                state = _text(record.get("state")).lower()
                state_key = "pending" if state in {"sending", "pending"} else state
                if state_key not in {"confirmed", "failed", "uncertain", "pending"}:
                    continue
                base[state_key] += 1
                totals[state_key] += 1
                daily[report_date.isoformat()][state_key] += 1
                code = _text(record.get("close_code")) or "-"
                all_codes[code] += 1
                if state_key in {"failed", "uncertain"}:
                    all_failures[
                        _text(record.get("category_label")) or "Falha nao classificada"
                    ] += 1
                duration = _duration_seconds(record)
                if state_key == "confirmed" and duration is not None:
                    base_durations.append(duration)
                    durations.append(duration)

                technician_name, technician_id = _report_technician(record, profile)
                technician_key = (_normalized(technician_name), technician_id)
                technician = technician_data.setdefault(
                    technician_key,
                    {
                        "technician": technician_name,
                        "technician_id": technician_id,
                        "confirmed": 0,
                        "failed": 0,
                        "uncertain": 0,
                        "pending": 0,
                        "bases": set(),
                        "codes": Counter(),
                        "durations": [],
                    },
                )
                technician[state_key] += 1
                technician["bases"].add(profile_key)
                technician["codes"][code] += 1
                if state_key == "confirmed" and duration is not None:
                    technician["durations"].append(duration)

        final = base["confirmed"] + base["failed"] + base["uncertain"]
        base_rows.append(
            {
                "key": profile_key,
                "label": _text(profile.label),
                "confirmed": base["confirmed"],
                "failed": base["failed"],
                "uncertain": base["uncertain"],
                "pending": base["pending"],
                "total": sum(base.values()),
                "success_rate": round(base["confirmed"] / final * 100, 1) if final else 0.0,
                "average_confirmation_seconds": round(sum(base_durations) / len(base_durations), 1)
                if base_durations
                else 0.0,
            }
        )

    technicians = []
    for value in technician_data.values():
        final = value["confirmed"] + value["failed"] + value["uncertain"]
        tech_durations = value.pop("durations")
        value["bases"] = sorted(value["bases"])
        value["top_code"] = value.pop("codes").most_common(1)[0][0]
        value["total"] = final + value["pending"]
        value["success_rate"] = round(value["confirmed"] / final * 100, 1) if final else 0.0
        value["average_confirmation_seconds"] = (
            round(sum(tech_durations) / len(tech_durations), 1) if tech_durations else 0.0
        )
        technicians.append(value)
    technicians.sort(
        key=lambda item: (-item["confirmed"], -item["success_rate"], item["technician"])
    )

    final_total = totals["confirmed"] + totals["failed"] + totals["uncertain"]
    daily_rows = []
    for offset in range(days):
        value_date = start_date + dt.timedelta(days=offset)
        value = daily[value_date.isoformat()]
        daily_rows.append({"date": value_date.isoformat(), **dict(value)})
    return {
        "ok": True,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
        "summary": {
            "confirmed": totals["confirmed"],
            "failed": totals["failed"],
            "uncertain": totals["uncertain"],
            "pending": totals["pending"],
            "total": sum(totals.values()),
            "success_rate": round(totals["confirmed"] / final_total * 100, 1)
            if final_total
            else 0.0,
            "average_confirmation_seconds": round(sum(durations) / len(durations), 1)
            if durations
            else 0.0,
        },
        "bases": base_rows,
        "technicians": technicians,
        "daily": daily_rows,
        "close_codes": [
            {"code": code, "count": count} for code, count in all_codes.most_common()
        ],
        "failure_categories": [
            {"label": label, "count": count}
            for label, count in all_failures.most_common(8)
        ],
    }


class HealthCheckService:
    def __init__(self, ttl_seconds: float = 45.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._cached_at = 0.0
        self._cached: dict[str, Any] | None = None

    @staticmethod
    def _check(profile: object) -> dict[str, Any]:
        started = time.monotonic()
        try:
            profile.api.status()
            online = True
            error = ""
        except Exception as exc:  # Health endpoint must report, not propagate.
            online = False
            error = _text(exc)[:300]
        return {
            "key": profile.key,
            "label": _text(profile.label),
            "host": _text(profile.api.host),
            "port": int(profile.port),
            "online": online,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": error,
            "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    def check(self, profiles: Mapping[str, object], *, fresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if (
                not fresh
                and self._cached is not None
                and time.monotonic() - self._cached_at < self.ttl_seconds
            ):
                return {**self._cached, "cached": True}
        results = []
        with ThreadPoolExecutor(max_workers=max(1, len(profiles))) as executor:
            futures = {executor.submit(self._check, profile): key for key, profile in profiles.items()}
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: list(profiles).index(item["key"]))
        online = sum(1 for item in results if item["online"])
        payload = {
            "ok": online == len(results),
            "cached": False,
            "online": online,
            "offline": len(results) - online,
            "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "bases": results,
        }
        with self._lock:
            self._cached = payload
            self._cached_at = time.monotonic()
        return payload


def _latest_captures(capture_root: Path, report_date: dt.date) -> list[object]:
    folder = capture_root / f"{report_date:%Y%m%d}"
    latest: dict[str, tuple[str, object]] = {}
    for path in folder.glob("*.json") if folder.is_dir() else ():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for raw in document.get("os_list", []):
            if not isinstance(raw, dict):
                continue
            try:
                capture = normalize_entry(raw)
            except (CaptureSchemaError, TypeError, ValueError):
                continue
            stamp = _text(raw.get("lastSeenAt") or document.get("metadata", {}).get("exportedAt"))
            previous = latest.get(capture.aid)
            if previous is None or stamp > previous[0]:
                latest[capture.aid] = (stamp, capture)
    return [item[1] for item in latest.values()]


def audit_serial_assignments(
    profile: object,
    capture_root: Path,
    report_date: dt.date,
) -> dict[str, Any]:
    captures = _latest_captures(capture_root, report_date)
    candidates = []
    for capture in captures:
        expected_id = int(capture.assigned_technician.get("id") or 0)
        expected_name = _text(capture.assigned_technician.get("name"))
        for item in capture.installed_equipment:
            serial = _text(item.get("serial")).upper()
            if serial:
                candidates.append(
                    {
                        "serial": serial,
                        "contract": capture.contract,
                        "activity_id": capture.aid,
                        "os_numbers": [
                            _text(task.get("os_number")) for task in capture.tasks
                            if _text(task.get("os_number"))
                        ],
                        "service": capture.work_type,
                        "equipment": _text(item.get("description") or item.get("type")),
                        "expected_technician_id": expected_id,
                        "expected_technician": expected_name,
                    }
                )
    unique = {item["serial"]: item for item in candidates}
    technicians = profile.api.list_stock_technicians()
    stock_ids = [int(item["stock_id"]) for item in technicians]
    stocks = profile.api.technician_stocks(stock_ids) if stock_ids and unique else []
    serial_index: dict[str, tuple[dict, dict]] = {}
    expected_stock_ids = {int(item["installer_id"]): int(item["stock_id"]) for item in technicians}
    for stock in stocks:
        owner = stock.get("technician") or {}
        for item in stock.get("items") or []:
            for serial in item.get("serials") or []:
                for identity in (serial.get("serial"), serial.get("smart")):
                    key = _text(identity).upper()
                    if key:
                        serial_index[key] = (owner, item)

    rows = []
    counts = Counter()
    for candidate in unique.values():
        match = serial_index.get(candidate["serial"])
        if match is None:
            status = "not_found"
            owner, equipment = {}, {}
        else:
            owner, equipment = match
            owner_id = int(owner.get("installer_id") or 0)
            expected_id = candidate["expected_technician_id"]
            if not expected_id or expected_id not in expected_stock_ids:
                status = "expected_stock_missing"
            elif owner_id == expected_id:
                status = "ok"
            else:
                status = "mismatch"
        counts[status] += 1
        rows.append(
            {
                **candidate,
                "status": status,
                "owner_technician_id": int(owner.get("installer_id") or 0),
                "owner_technician": _text(owner.get("technician_name")),
                "owner_stock_id": int(owner.get("stock_id") or 0),
                "owner_stock": _text(owner.get("stock_name")),
                "equipment": candidate["equipment"] or _text(equipment.get("equipment")),
                "equipment_code": _text(equipment.get("code")),
            }
        )
    priority = {"mismatch": 0, "not_found": 1, "expected_stock_missing": 2, "ok": 3}
    rows.sort(key=lambda item: (priority[item["status"]], item["expected_technician"], item["serial"]))
    return {
        "ok": True,
        "profile": profile.key,
        "base": _text(profile.label),
        "date": report_date.isoformat(),
        "capture_count": len(captures),
        "serial_count": len(rows),
        "summary": {
            "mismatch": counts["mismatch"],
            "not_found": counts["not_found"],
            "expected_stock_missing": counts["expected_stock_missing"],
            "ok": counts["ok"],
        },
        "rows": rows,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def render_daily_pdf(snapshot: Mapping[str, Any], output_path: Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    navy = colors.HexColor("#132238")
    blue = colors.HexColor("#2374E1")
    green = colors.HexColor("#1F9D68")
    red = colors.HexColor("#D95050")
    muted = colors.HexColor("#637083")
    pale = colors.HexColor("#F3F6FA")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("DominumTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=navy, spaceAfter=3 * mm)
    subtitle = ParagraphStyle("DominumSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=muted, spaceAfter=6 * mm)
    section = ParagraphStyle("DominumSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=navy, spaceBefore=4 * mm, spaceAfter=2.5 * mm)
    cell = ParagraphStyle("DominumCell", parent=styles["Normal"], fontName="Helvetica", fontSize=7.4, leading=9.2, textColor=navy)
    cell_center = ParagraphStyle("DominumCellCenter", parent=cell, alignment=TA_CENTER)
    cell_right = ParagraphStyle("DominumCellRight", parent=cell, alignment=TA_RIGHT)
    head_cell = ParagraphStyle(
        "DominumHeadCell",
        parent=cell,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    def p(value: object, style=cell) -> Paragraph:
        raw = "" if value is None else " ".join(str(value).strip().split())
        safe = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe or "-", style)

    report_date = dt.date.fromisoformat(str(snapshot["end_date"]))
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title=f"Relatorio diario DOMINIUM - {report_date:%d/%m/%Y}",
        author="TECHNET - DOMINIUM",
    )

    def page(canvas, document) -> None:
        canvas.saveState()
        width, height = landscape(A4)
        canvas.setFillColor(navy)
        canvas.rect(0, height - 7 * mm, width, 7 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(14 * mm, height - 4.7 * mm, "TECHNET  |  DOMINIUM")
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(14 * mm, 7 * mm, f"Gerado em {dt.datetime.now():%d/%m/%Y %H:%M}")
        canvas.drawRightString(width - 14 * mm, 7 * mm, f"Pagina {document.page}")
        canvas.restoreState()

    summary = snapshot["summary"]
    story = [
        Paragraph("Relatorio diario de fechamento", title),
        Paragraph(
            f"Consolidado das bases em {report_date:%d/%m/%Y} - baixas confirmadas, pendencias e desempenho operacional.",
            subtitle,
        ),
    ]
    cards = [
        ("CONFIRMADAS", summary["confirmed"], green),
        ("FALHAS", summary["failed"], red),
        ("INCERTAS", summary["uncertain"], colors.HexColor("#D68A18")),
        ("PENDENTES", summary["pending"], blue),
        ("TAXA DE SUCESSO", f'{summary["success_rate"]:.1f}%', navy),
    ]
    card_table = Table(
        [[p(label, cell_center) for label, _, _ in cards], [p(value, ParagraphStyle(f"metric-{index}", parent=cell_center, fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=color)) for index, (_, value, color) in enumerate(cards)]],
        colWidths=[51 * mm] * 5,
        rowHeights=[8 * mm, 12 * mm],
    )
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pale),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E0E8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E0E8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([card_table, Spacer(1, 4 * mm), Paragraph("Resultado por base", section)])

    base_data = [[p("BASE", head_cell), p("CONF.", head_cell), p("FALHAS", head_cell), p("INCERTAS", head_cell), p("PEND.", head_cell), p("TOTAL", head_cell), p("SUCESSO", head_cell), p("TEMPO MEDIO", head_cell)]]
    for base in snapshot["bases"]:
        base_data.append([
            p(base["label"]), p(base["confirmed"], cell_right), p(base["failed"], cell_right),
            p(base["uncertain"], cell_right), p(base["pending"], cell_right), p(base["total"], cell_right),
            p(f'{base["success_rate"]:.1f}%', cell_right), p(f'{base["average_confirmation_seconds"]:.0f}s', cell_right),
        ])
    base_table = Table(base_data, colWidths=[68 * mm, 24 * mm, 24 * mm, 25 * mm, 24 * mm, 24 * mm, 28 * mm, 33 * mm], repeatRows=1)
    base_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E0E8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(base_table)

    story.append(Paragraph("Produtividade por tecnico", section))
    tech_data = [[p("TECNICO", head_cell), p("BASE(S)", head_cell), p("CONF.", head_cell), p("FALHAS", head_cell), p("INC.", head_cell), p("TOTAL", head_cell), p("SUCESSO", head_cell), p("CODIGO MAIS USADO", head_cell)]]
    for technician in list(snapshot["technicians"])[:28]:
        tech_data.append([
            p(technician["technician"]), p(" / ".join(value.upper() for value in technician["bases"])),
            p(technician["confirmed"], cell_right), p(technician["failed"], cell_right), p(technician["uncertain"], cell_right),
            p(technician["total"], cell_right), p(f'{technician["success_rate"]:.1f}%', cell_right), p(technician["top_code"], cell_center),
        ])
    if len(tech_data) == 1:
        tech_data.append([p("Sem baixas registradas no periodo")]+[p("-") for _ in range(7)])
    tech_table = Table(tech_data, colWidths=[65 * mm, 35 * mm, 22 * mm, 23 * mm, 20 * mm, 21 * mm, 28 * mm, 38 * mm], repeatRows=1)
    tech_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E0E8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story.append(tech_table)

    if snapshot["failure_categories"]:
        failure_rows = [[p("CATEGORIA", head_cell), p("OCORRENCIAS", head_cell)]] + [
            [p(item["label"]), p(item["count"], cell_right)] for item in snapshot["failure_categories"]
        ]
        failure_table = Table(failure_rows, colWidths=[110 * mm, 35 * mm], repeatRows=1)
        failure_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E0E8")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(KeepTogether([Paragraph("Principais falhas", section), failure_table]))

    doc.build(story, onFirstPage=page, onLaterPages=page)
    return output_path
