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
"""Geracao de relatorios PDF de estoque sem dependencias externas.

O modulo usa apenas a biblioteca padrao para que o painel continue portatil.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Sequence


PAGE_WIDTH = 841.89  # A4 landscape, points
PAGE_HEIGHT = 595.28
MARGIN_X = 30.0
BOTTOM = 30.0
TOP = 28.0


def _pdf_text(value: object) -> bytes:
    text = str(value or "-")
    encoded = text.encode("cp1252", errors="replace")
    escaped = bytearray()
    for byte in encoded:
        if byte in (0x28, 0x29, 0x5C):
            escaped.append(0x5C)
        escaped.append(byte)
    return bytes(escaped)


def _text_width(text: str, size: float, bold: bool = False) -> float:
    total = 0.0
    for character in str(text):
        if character == " ":
            factor = 0.28
        elif character in "ilI.,:;'|!":
            factor = 0.26
        elif character in "mwMW@%&":
            factor = 0.82
        elif character.isupper():
            factor = 0.69
        elif character.isdigit():
            factor = 0.58
        else:
            factor = 0.53
        total += factor
    if bold:
        total *= 1.035
    return total * size


def _wrap(text: object, width: float, size: float, *, bold: bool = False) -> list[str]:
    value = " ".join(str(text or "-").replace("\r", " ").split())
    if not value:
        return ["-"]
    words = value.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_width(candidate, size, bold) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if _text_width(word, size, bold) <= width:
            current = word
            continue
        fragment = ""
        for character in word:
            candidate = fragment + character
            if fragment and _text_width(candidate, size, bold) > width:
                lines.append(fragment)
                fragment = character
            else:
                fragment = candidate
        current = fragment
    if current:
        lines.append(current)
    return lines or ["-"]


class _Canvas:
    def __init__(self) -> None:
        self.commands: list[bytes] = []

    def text(
        self,
        x: float,
        y: float,
        text: object,
        *,
        size: float = 8.0,
        bold: bool = False,
    ) -> None:
        font = b"F2" if bold else b"F1"
        self.commands.append(
            b"0 g BT /" + font + b" " + f"{size:.2f}".encode("ascii")
            + b" Tf " + f"{x:.2f} {y:.2f}".encode("ascii")
            + b" Td (" + _pdf_text(text) + b") Tj ET\n"
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, *, gray: float = 0.72) -> None:
        self.commands.append(
            f"{gray:.3f} G {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S\n".encode("ascii")
        )

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill_gray: float | None = None,
        stroke_gray: float = 0.72,
    ) -> None:
        if fill_gray is None:
            command = f"{stroke_gray:.3f} G {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S\n"
        else:
            command = (
                f"{fill_gray:.3f} g {stroke_gray:.3f} G "
                f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B\n"
            )
        self.commands.append(command.encode("ascii"))

    def bytes(self) -> bytes:
        return b"".join(self.commands)


class _PDF:
    def __init__(self) -> None:
        self.pages: list[bytes] = []

    def add_page(self, canvas: _Canvas) -> None:
        self.pages.append(canvas.bytes())

    def build(self, title: str) -> bytes:
        objects: list[bytes] = [b"", b"", b"", b""]
        objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objects[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        page_ids: list[int] = []
        for content in self.pages:
            content_id = len(objects) + 1
            objects.append(
                b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
                + content + b"endstream"
            )
            page_id = len(objects) + 1
            objects.append(
                (
                    "<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}] "
                    "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode("ascii")
            )
            page_ids.append(page_id)
        objects[1] = (
            "<< /Type /Pages /Count " + str(len(page_ids)) + " /Kids ["
            + " ".join(f"{page_id} 0 R" for page_id in page_ids)
            + "] >>"
        ).encode("ascii")

        info_id = len(objects) + 1
        creation = dt.datetime.now().strftime("D:%Y%m%d%H%M%S")
        objects.append(
            b"<< /Title (" + _pdf_text(title) + b") /Creator (DOMINIUM) "
            + b"/CreationDate (" + creation.encode("ascii") + b") >>"
        )

        result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_id, payload in enumerate(objects, start=1):
            offsets.append(len(result))
            result.extend(f"{object_id} 0 obj\n".encode("ascii"))
            result.extend(payload)
            result.extend(b"\nendobj\n")
        xref = len(result)
        result.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        result.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        result.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(result)


@dataclass(frozen=True)
class _Column:
    key: str
    label: str
    width: float
    align: str = "left"


class StockPDFReport:
    def __init__(
        self,
        *,
        company: str,
        include_zero: bool = False,
        include_serials: bool = True,
        generated_at: dt.datetime | None = None,
    ) -> None:
        self.company = company
        self.include_zero = include_zero
        self.include_serials = include_serials
        self.generated_at = generated_at or dt.datetime.now()
        self.pdf = _PDF()
        self.page_number = 0
        self.current: _Canvas | None = None
        self.y = 0.0
        self.current_stock: dict | None = None
        serial_width = 177.0 if include_serials else 0.0
        equipment_width = 264.0 + (177.0 if not include_serials else 0.0)
        self.columns = [
            _Column("group", "Grupo", 98.0),
            _Column("code", "Código", 80.0),
            _Column("equipment", "Equipamento", equipment_width),
            _Column("brand", "Marca", 100.0),
            _Column("quantity_label", "Saldo", 58.0, "center"),
        ]
        if include_serials:
            self.columns.append(_Column("serials_text", "Seriais", serial_width))

    @property
    def table_width(self) -> float:
        return sum(column.width for column in self.columns)

    def _new_page(self, stock: dict, *, continuation: bool = False) -> None:
        if self.current is not None:
            self._footer()
            self.pdf.add_page(self.current)
        self.page_number += 1
        self.current = _Canvas()
        self.current_stock = stock
        self.y = PAGE_HEIGHT - TOP
        technician = stock.get("technician", {})
        technician_name = technician.get("technician_name") or technician.get("stock_name") or "Tecnico"
        suffix = " - continuação" if continuation else ""
        self.current.text(MARGIN_X, self.y, "RELATÓRIO DE ESTOQUE DO TÉCNICO", size=14, bold=True)
        self.current.text(PAGE_WIDTH - MARGIN_X - 175, self.y + 1, self.company, size=9, bold=True)
        self.y -= 21
        self.current.text(MARGIN_X, self.y, f"Técnico: {technician_name}{suffix}", size=11, bold=True)
        self.y -= 14
        self.current.text(
            MARGIN_X,
            self.y,
            f"Estoque: {technician.get('stock_name', '-')}  |  ID do estoque: {technician.get('stock_id', '-')}",
            size=8.5,
        )
        self.current.text(
            PAGE_WIDTH - MARGIN_X - 205,
            self.y,
            f"Gerado em {self.generated_at:%d/%m/%Y %H:%M}",
            size=8.5,
        )
        self.y -= 19
        if not continuation:
            summary = stock.get("summary", {})
            summaries = [
                ("Itens com saldo", summary.get("positive_item_count", 0)),
                ("Quantidade total", summary.get("quantity_total", 0)),
                ("Seriais", summary.get("serial_count", 0)),
                ("Grupos", summary.get("group_count", 0)),
            ]
            gap = 6.0
            width = (self.table_width - gap * 3) / 4
            x = MARGIN_X
            for label, value in summaries:
                self.current.rect(x, self.y - 29, width, 29, fill_gray=0.955, stroke_gray=0.78)
                self.current.text(x + 7, self.y - 11, label, size=7.2)
                self.current.text(x + 7, self.y - 24, value, size=11, bold=True)
                x += width + gap
            self.y -= 42
        self._table_header()

    def _table_header(self) -> None:
        assert self.current is not None
        height = 22.0
        x = MARGIN_X
        for column in self.columns:
            self.current.rect(x, self.y - height, column.width, height, fill_gray=0.89, stroke_gray=0.62)
            self.current.text(x + 5, self.y - 14, column.label, size=7.7, bold=True)
            x += column.width
        self.y -= height

    def _footer(self) -> None:
        assert self.current is not None
        self.current.line(MARGIN_X, 24, PAGE_WIDTH - MARGIN_X, 24, gray=0.78)
        self.current.text(MARGIN_X, 13, "Consulta somente leitura - DOMINIUM", size=7)
        self.current.text(PAGE_WIDTH - MARGIN_X - 55, 13, f"Página {self.page_number}", size=7)

    @staticmethod
    def _quantity_positive(item: dict) -> bool:
        try:
            return Decimal(str(item.get("quantity", "0"))) > 0
        except (InvalidOperation, ValueError):
            return False

    def _item_values(self, item: dict) -> dict[str, str]:
        serial_values = []
        for serial in item.get("serials", []) or []:
            value = str(serial.get("serial") or "-")
            smart = str(serial.get("smart") or "").strip()
            if smart:
                value += f" / SMART {smart}"
            serial_values.append(value)
        return {
            "group": str(item.get("group") or "-"),
            "code": str(item.get("code") or "-"),
            "equipment": str(item.get("equipment") or "-"),
            "brand": str(item.get("brand") or "-"),
            "quantity_label": str(item.get("quantity_label") or item.get("quantity") or "0"),
            "serials_text": "; ".join(serial_values) if serial_values else "-",
        }

    def _draw_row_chunk(
        self,
        stock: dict,
        values: dict[str, str],
        line_sets: dict[str, list[str]],
        start_line: int,
        take_lines: int,
        *,
        continuation: bool,
    ) -> None:
        assert self.current is not None
        line_height = 9.0
        row_height = max(20.0, take_lines * line_height + 8.0)
        x = MARGIN_X
        for column in self.columns:
            self.current.rect(x, self.y - row_height, column.width, row_height, stroke_gray=0.80)
            lines = line_sets[column.key]
            if continuation and column.key != "serials_text":
                visible_lines = lines[: max(1, min(len(lines), take_lines))]
            else:
                visible_lines = lines[start_line : start_line + take_lines]
            if not visible_lines and column.key != "serials_text":
                visible_lines = lines[:1]
            if column.align == "center" and visible_lines:
                for index, line in enumerate(visible_lines):
                    text_width = _text_width(line, 7.4, column.key == "quantity_label")
                    self.current.text(
                        x + max(4.0, (column.width - text_width) / 2),
                        self.y - 13 - index * line_height,
                        line,
                        size=7.4,
                        bold=column.key == "quantity_label",
                    )
            else:
                for index, line in enumerate(visible_lines):
                    self.current.text(
                        x + 4,
                        self.y - 13 - index * line_height,
                        line,
                        size=7.2,
                        bold=column.key in {"code", "quantity_label"},
                    )
            x += column.width
        self.y -= row_height

    def _draw_item(self, stock: dict, item: dict) -> None:
        values = self._item_values(item)
        line_sets = {
            column.key: _wrap(
                values.get(column.key, "-"),
                column.width - 8,
                7.2,
                bold=column.key in {"code", "quantity_label"},
            )
            for column in self.columns
        }
        total_lines = max(len(lines) for lines in line_sets.values())
        start_line = 0
        continuation = False
        while start_line < total_lines:
            available_lines = int(max(0, self.y - BOTTOM - 10) // 9.0)
            if available_lines < 2:
                self._new_page(stock, continuation=True)
                available_lines = int(max(0, self.y - BOTTOM - 10) // 9.0)
            take = min(total_lines - start_line, max(2, available_lines - 1))
            estimated_height = max(20.0, take * 9.0 + 8.0)
            if estimated_height > self.y - BOTTOM:
                self._new_page(stock, continuation=True)
                continue
            self._draw_row_chunk(
                stock,
                values,
                line_sets,
                start_line,
                take,
                continuation=continuation,
            )
            start_line += take
            continuation = True

    def add_stock(self, stock: dict) -> None:
        self._new_page(stock)
        items = [
            item
            for item in stock.get("items", [])
            if self.include_zero or self._quantity_positive(item)
        ]
        if not items:
            assert self.current is not None
            self.current.text(MARGIN_X + 6, self.y - 24, "Nenhum item encontrado para este estoque.", size=9)
            self.y -= 40
            return
        for item in items:
            self._draw_item(stock, item)

    def build(self, stocks: Sequence[dict]) -> bytes:
        for stock in stocks:
            self.add_stock(stock)
        if self.current is not None:
            self._footer()
            self.pdf.add_page(self.current)
            self.current = None
        title = "Relatório de estoque"
        if len(stocks) == 1:
            technician = stocks[0].get("technician", {})
            title = f"Estoque - {technician.get('technician_name', 'Tecnico')}"
        return self.pdf.build(title)


def build_stock_pdf(
    stocks: Iterable[dict],
    *,
    company: str,
    include_zero: bool = False,
    include_serials: bool = True,
) -> bytes:
    values = list(stocks)
    if not values:
        raise ValueError("Selecione pelo menos um tecnico")
    report = StockPDFReport(
        company=company,
        include_zero=include_zero,
        include_serials=include_serials,
    )
    return report.build(values)


def safe_pdf_filename(name: str, *, fallback: str = "estoque-tecnicos") -> str:
    ascii_name = "".join(
        character
        for character in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name.strip())
    normalized = re.sub(r"[-_.]{2,}", "-", normalized)
    normalized = normalized.strip("-._") or fallback
    return normalized[:100] + ".pdf"
