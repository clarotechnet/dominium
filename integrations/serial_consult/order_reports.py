"""Read-only Imperium OS exports matching the native 42-column Excel layout.

DspGetOs/AS_GetRecords only. No order, stock or TOA mutation is available here.
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import re
import struct
import threading
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from .midas_reader import decode_dataset
except ImportError:
    from midas_reader import decode_dataset

PORTS = {"natal": 212, "fortaleza": 596, "mossoro": 579, "recife": 599}
RUNTIME = Path(r"C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA")
CREDENTIALS = Path(r"C:\DominiumMain\config\credentials.dat")
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROUTE = re.compile(
    r"/api/order-reports/export\.xlsx\?profile=(natal|fortaleza|mossoro|recife)"
    r"&start=(\d{4}-\d{2}-\d{2})&end=(\d{4}-\d{2}-\d{2})&type=(all|maintenance)(?:&variant=(treated))?\Z"
)
# Display caption, original DataSnap field, Excel representation.
COLUMNS = (
    ("V.I.", "VendaInterna", "number"), ("Log", "Logretorno", "number"),
    ("Ouv.", "Ouvidoria", "text"), ("Int.", "Interna", "text"),
    ("Retorno", "Retorno", "text"), ("Data", "Data", "date"),
    ("Turno", "Turno", "text"), ("Início", "HoraIni", "time"),
    ("Término", "HoraFim", "time"), ("Núm. Contrato", "NumeroContrato", "number"),
    ("Número W.O", "NumeroWO", "text"), ("Núm. OS", "NumOs", "number"),
    ("Cliente", "Cliente", "text"), ("Endereco", "Endereco", "text"),
    ("Node", "Node", "text"), ("Bairro", "Bairro", "text"),
    ("Cidade", "Cidade", "text"), ("Serviço", "Servico", "text"),
    ("Instalador", "NomeAbreviado", "text"), ("Observacao", "Observacao", "text"),
    ("Parceria", "Parceria", "text"), ("Status", "Status", "number"),
    ("Data da Baixa", "DataBaixa", "datetime"),
    ("Controlador", "NomeControladorBaixa", "text"),
    ("Cód. Baixa", "CodigoBaixa", "code"), ("Desc. Cód. Baixa", "Descricao", "text"),
    ("Observação Baixa", "ObservacaoBaixa", "text"),
    ("Níveis de Sinal", "NiveisDeSinal", "text"), ("Numero", "Numero", "number"),
    ("Complemento", "Complemento", "text"), ("CEP", "CEP", "number"),
    ("TelRes", "TelRes", "text"), ("TelOutros", "TelOutros", "text"),
    ("TelComercial", "TelComercial", "text"), ("TelCelular", "TelCelular", "text"),
    ("Data Receb. OS", "DataRecebimentoOS", "datetime"), ("Produto", "Produto", "text"),
    ("Data Agend. Sistema", "DataAgendamentoActivia", "date"),
    ("Data Baixa Sistema", "DataFinalizadoActivia", "datetime"),
    ("Usuário Baixa Sistema", "UsuarioFinalizadoActivia", "text"),
    ("Usuário Cad. OS", "UsuarioCadastroOS", "text"),
    ("Dt. Importação", "DataImportacao", "datetime"),
)
MAX_BYTES = 32_000_000
MAX_ROWS = 100_000
# Column order in Vistoria_Supervisores after deletes/moves, indexed on the original sheet.
ALL_TREATED_COLUMNS = tuple(COLUMNS[i - 1] for i in (6, 10, 16, 14, 29, 30, 18, 19, 25, 26, 27))
SUPERVISOR_CODES = frozenset({108, 206, 205, 303, 305, 110})
MAINTENANCE_SERVICES = frozenset({
    "MANUTENCAO CORRETIVA - DEGRADACAO MDU",
    "MANUTENCAO CORRETIVA - MDU",
    "MANUTENCAO PREVENTIVA - MDU",
    "MANUTENCAO PREVENTIVA INDOOR",
    "SUBSTITUICAO DE CONTROLE REMOTO ANALOGICA",
    "TROCA DE EQUIPAMENTO STREAMING",
})
EXCEL_EPOCH = dt.datetime(1899, 12, 30)


def parse_route(method, target):
    return ROUTE.fullmatch(target) if method == "GET" and isinstance(target, str) else None


def validate_range(start, end):
    begin, finish = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()
    if begin > finish:
        raise ValueError("A data inicial deve ser anterior ou igual à final")
    if begin.year < 2000 or finish > today:
        raise ValueError("Selecione um período válido até a data de hoje")
    if (finish - begin).days >= 31:
        raise ValueError("Consulte até 31 dias por download")
    return begin, finish


def _automation_date(date, end=False):
    value = (date - EXCEL_EPOCH.date()).days
    return struct.pack("<d", value + (1 - 1 / 86400000 if end else 0))


def build_query(start, end, report_type, templates):
    begin, finish = validate_range(start, end)
    if report_type not in {"all", "maintenance"} or templates.get("version") != 1:
        raise ValueError("Relatório inválido")
    captured = dt.date.fromisoformat(templates["captured_date"])
    packet = base64.b64decode(templates["main_query"], validate=True)
    replacements = [
        (_automation_date(captured), _automation_date(begin)),
        (_automation_date(captured, True), _automation_date(finish, True)),
    ]
    for name, old, new in (
        ("Status", "1", "%"),
        ("IdTipoServico", "3", "%" if report_type == "all" else "2"),
        ("IdParceria", "%", "1"),
    ):
        prefix = name.encode("utf-16le") + struct.pack("<II", 8, 1)
        replacements.append((prefix + old.encode("ascii"), prefix + new.encode("ascii")))
    # Locate all markers in the original packet before replacing: adjacent dates
    # can otherwise collide when a new endpoint equals the old capture date.
    positions = []
    for old, new in replacements:
        if packet.count(old) != 1:
            raise ValueError("Modelo da consulta Imperium divergente")
        positions.append((packet.index(old), old, new))
    for index, old, new in sorted(positions, reverse=True):
        packet = packet[:index] + new + packet[index + len(old):]
    return packet


def fetch_rows(profile, start, end, report_type, *, runtime=RUNTIME,
               credential_path=CREDENTIALS, client_factory=None):
    if profile not in PORTS:
        raise ValueError("Selecione uma cidade")
    templates = json.loads((Path(runtime) / "protocol_templates.json").read_text(encoding="ascii"))
    query = build_query(start, end, report_type, templates)
    from datasnap_client import DataSnapClient, load_credentials
    credentials = load_credentials(Path(credential_path))
    factory = client_factory or DataSnapClient
    with factory("www.sistemaimperium.com.br", PORTS[profile], credentials["username"],
                 credentials["password"], timeout=90) as client:
        prepared = client.request("prepare", [-1, False, "DataSnap.ServerMethod",
                                              "TDtmOrdemServico.AS_GetRecords"])
        handle = int(prepared["result"][0]["handle"][0])
        response = client.request("execute", [{"handle": [handle]}, query])
        payload = bytearray(response["result"][1]["data"][1])
        if len(payload) < 24:
            raise RuntimeError("O Imperium não retornou um relatório completo")
        # The record-count width shifts the entire envelope. Both 1-byte
        # (<256 rows) and 2-byte counts can have multi-part responses.
        count_width = payload[2] - 0x60 if payload[:2] == b"\xc0\xc0" else -1
        signature_at = 26 + count_width
        if count_width not in range(5) or payload[signature_at:signature_at + 4] != bytes.fromhex("9619e0bd"):
            raise RuntimeError("Cabeçalho do relatório inválido")
        expected = (struct.unpack_from("<I", payload, signature_at - 8)[0] + signature_at
                    if count_width else len(payload))
        if not 28 <= expected <= MAX_BYTES:
            raise RuntimeError("Relatório acima do limite; reduza o período")
        for _ in range(512):
            if len(payload) >= expected:
                break
            part = client.request("more_blob", [handle, 1, 0, 7, True, 0])
            chunk = part["result"][0]["data"][1]
            if not chunk or len(payload) + len(chunk) > expected:
                raise RuntimeError("Fragmento incompleto do relatório")
            payload.extend(chunk)
        if len(payload) != expected:
            raise RuntimeError("Relatório incompleto; nenhum arquivo foi gerado")
    rows = decode_dataset(bytes(payload), max_bytes=MAX_BYTES, max_records=MAX_ROWS)
    required = {field for _, field, _ in COLUMNS}
    if rows and any(not required <= row.keys() for row in rows):
        raise RuntimeError("O formato do relatório Imperium mudou")
    ids = [row.get("IdOs") for row in rows]
    if len(set(ids)) != len(ids):
        raise RuntimeError("O Imperium retornou OS duplicadas; consulte novamente")
    return rows


def _column(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _text(value):
    # XML 1.0 excludes some controls present in free-text observations.
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value)))


def excel_value(value, kind):
    if value is None or value == "":
        return None, 0
    if kind == "date":
        # DBI ftDate: day number since 0001-01-01, with 0001-01-01 = 1.
        if isinstance(value, (int, float)):
            return value - EXCEL_EPOCH.date().toordinal(), 1
        date = dt.date.fromisoformat(str(value)[:10])
        return (date - EXCEL_EPOCH.date()).days, 1
    if kind == "time":
        # DBI ftTime: milliseconds since midnight.
        return float(value) / 86400000, 2
    if kind == "datetime":
        date = dt.datetime.fromisoformat(str(value))
        return (date - EXCEL_EPOCH).total_seconds() / 86400, 3
    if kind in {"number", "code"}:
        text = str(int(value)) if isinstance(value, bool) else str(value)
        if kind == "code" and text.isdigit():
            return int(text), 0
        # Preserve IDs beyond Excel\'s 15-digit precision and leading zeros.
        if re.fullmatch(r"-?(?:0|[1-9][0-9]{0,14})(?:\.[0-9]+)?", text):
            return (float(text) if "." in text else int(text)), 0
    # The native grid flattens memo line breaks using this separator.
    return str(value).replace("\r\n", " | ").strip(), 0


def treat_rows(rows, report_type):
    """Apply the functional filters from the recorded Excel macros.

    The supervisor AutoFilter selects visible results. In Rev_Imperium, the
    service AutoFilter selects rows to DELETE (not keep); the final workbook
    resets the filter and retains the other services.
    The fixed row-16 deletion in the maintenance recording is not replicated.
    """
    if report_type == "maintenance":
        # Rev_Imperium selects six service types and deletes the visible rows.
        # The saved VBA workbook therefore EXCLUDES them, retaining other
        # services (including visits) with a nonblank Número W.O.
        return [
            row for row in rows
            if row.get("NumeroWO") is not None and str(row["NumeroWO"]).strip()
            and str(row.get("Servico") or "").strip().upper() not in MAINTENANCE_SERVICES
        ]
    if report_type != "all":
        raise ValueError("Tipo de relatório inválido")
    # VBA RemoveDuplicates Columns:=3 is applied before filtering close code.
    seen_contracts = set()
    distinct = []
    for row in rows:
        contract = str(row.get("NumeroContrato") or "").strip()
        if contract in seen_contracts:
            continue
        seen_contracts.add(contract)
        distinct.append(row)
    result = []
    for row in distinct:
        try:
            code = int(str(row.get("CodigoBaixa") or "").strip())
        except (ValueError, TypeError):
            continue
        if code in SUPERVISOR_CODES:
            result.append(row)
    return result


def export_xlsx(rows, columns=COLUMNS, autofit=False):
    if len(rows) > MAX_ROWS:
        raise ValueError("Relatório acima do limite")
    sheet = io.StringIO()
    sheet.write('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
                'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    if autofit:
        sheet.write('<cols>')
        sample = rows[:500]
        for idx, (caption, field, _) in enumerate(columns, 1):
            width = min(65, max(14, len(caption) + 3,
                                *(min(65, len(str(row.get(field) or "")) + 2) for row in sample)))
            sheet.write(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')
        sheet.write('</cols>')
    sheet.write('<sheetData>')
    for row_number, row in enumerate([None, *rows], 1):
        sheet.write(f'<row r="{row_number}">')
        for index, (caption, field, kind) in enumerate(columns, 1):
            value, style = (caption, 4) if row is None else excel_value(row.get(field), kind)
            if value is None:
                continue
            ref = _column(index) + str(row_number)
            if isinstance(value, (int, float)):
                sheet.write(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
            else:
                # inlineStr is deliberate: observations beginning "=" stay text.
                sheet.write(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
                            f'{_text(value)}</t></is></c>')
        sheet.write('</row>')
    sheet.write(f'</sheetData><autoFilter ref="A1:{_column(len(columns))}{max(1, len(rows) + 1)}"/></worksheet>')
    ns = "http://schemas.openxmlformats.org"
    files = {
        "[Content_Types].xml": f'<Types xmlns="{ns}/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{ns}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{ns}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{ns}/spreadsheetml/2006/main" xmlns:r="{ns}/officeDocument/2006/relationships">'
            '<sheets><sheet name="Ordens de Serviço" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{ns}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{ns}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{ns}/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": f'<styleSheet xmlns="{ns}/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="21" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="22" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        "xl/worksheets/sheet1.xml": sheet.getvalue(),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + text)
    return output.getvalue()


class OrderReportService:
    def __init__(self, fetcher=fetch_rows):
        self.fetcher = fetcher
        self.locks = {key: threading.Lock() for key in PORTS}

    def download(self, route):
        profile, start, end, report_type, treated = route.groups()
        validate_range(start, end)
        lock = self.locks[profile]
        if not lock.acquire(blocking=False):
            raise ValueError("Já há um relatório sendo consultado nesta cidade; aguarde")
        try:
            rows = self.fetcher(profile, start, end, report_type)
            if treated:
                rows = treat_rows(rows, report_type)
            filename = (f"OS_{'Todos' if report_type == 'all' else 'Manutencao'}"
                        f"{'_Tratado' if treated else ''}_{profile}_{start}_{end}.xlsx")
            columns = ALL_TREATED_COLUMNS if treated and report_type == "all" else COLUMNS
            return export_xlsx(rows, columns, autofit=bool(treated)), filename, len(rows)
        finally:
            lock.release()
