"""Read-only Imperium service commissions (four DataSnap bases).

Replays only the three captured TDtmComissionamentoServicos.AS_GetRecords
datasets. No insert/update/post/ApplyUpdates and no HTTP Natal-only API.
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

from midas_reader import decode_dataset
from order_reports import PORTS, CREDENTIALS, MIME, validate_range, excel_value, _column, _text

TEMPLATES_PATH = Path(__file__).with_name("commission_protocol_templates_20261112.json")
METHOD = "TDtmComissionamentoServicos.AS_GetRecords"
DATASETS = ("DspListaInstaladores", "DspComissInstSint", "DspContratosComissInst")
MAX_BYTES = 30_000_000
MAX_RECORDS = 100_000
ROUTE = re.compile(
    r"/api/commission-reports/export\.xlsx\?profile=(natal|fortaleza|mossoro|recife)"
    r"&start=(\d{4}-\d{2}-\d{2})&end=(\d{4}-\d{2}-\d{2})\Z"
)
SHEETS = (
    ("Comiss.Sintético", "DspListaInstaladores", (
        ("Id", "IdInstalador", "number"),
        ("Instalador", "NomeAbreviado", "text"),
        ("Valor", "Valor", "money"),
        ("Valor Instalador", "ValorInstalador", "money"),
        ("Valor Auxiliar", "ValorAuxiliar", "money"),
        ("Valor Deslocamento", "ValorDeslocamento", "money"),
    )),
    ("Comiss.Analítico", "DspComissInstSint", (
        ("IdInstalador", "IdInstalador", "number"),
        ("NomeAbreviado", "NomeAbreviado", "text"),
        ("IdComissionamento", "IdComissionamento", "number"),
        ("Produto", "Produto", "text"),
        ("QtdContrato", "QtdContrato", "number"),
        ("QtdOs", "QtdOs", "number"),
        ("Valor", "Valor", "money"),
        ("ValorInstalador", "ValorInstalador", "money"),
        ("ValorAuxiliar", "ValorAuxiliar", "money"),
    )),
    ("Contratos", "DspContratosComissInst", (
        ("IdComissionamento", "IdComissionamento", "number"),
        ("Produto", "Produto", "text"),
        ("IdInstalador", "IdInstalador", "number"),
        ("Contrato", "Contrato", "number"),
        ("DataAgendamento", "DataAgendamento", "date"),
        ("DataBaixa", "DataBaixa", "date"),
        ("QtdOS", "QtdOS", "number"),
        ("Valor", "Valor", "money"),
        ("ValorInstalador", "ValorInstalador", "money"),
        ("ValorAuxiliar", "ValorAuxiliar", "money"),
    )),
)

def parse_route(method, target):
    return ROUTE.fullmatch(target) if method == "GET" and isinstance(target, str) else None

def build_query(dataset, start, end, *, templates=None):
    begin, finish = validate_range(start, end)
    bundle = templates if templates is not None else json.loads(
        TEMPLATES_PATH.read_text(encoding="utf-8"))
    if bundle.get("version") != 1 or bundle.get("method") != METHOD:
        raise ValueError("Modelo de comissões desconhecido")
    if dataset not in DATASETS:
        raise ValueError("Dataset não autorizado")
    packet = base64.b64decode(bundle["datasets"][dataset], validate=True)
    captured_begin, captured_end = bundle["captured_period"]
    pairs = (
        (dt.date.fromisoformat(captured_begin).strftime("%d/%m/%Y"),
         begin.strftime("%d/%m/%Y")),
        (dt.date.fromisoformat(captured_end).strftime("%d/%m/%Y") + " 23:59:59",
         finish.strftime("%d/%m/%Y") + " 23:59:59"),
    )
    for old, new in pairs:
        before = old.encode("utf-16le")
        after = new.encode("utf-16le")
        if len(after) != len(before) or packet.count(before) != 1:
            raise ValueError("Formato da consulta DataSnap divergente")
        packet = packet.replace(before, after, 1)
    if len(packet) > 2048:
        raise ValueError("Consulta de comissões acima do limite")
    return packet

def _dataset_bytes(client, handle, response):
    data = response["result"][1]["data"][1]
    payload = bytearray(data)
    if len(payload) < 32 or payload[:2] != b"\xc0\xc0":
        raise RuntimeError("Cabeçalho do relatório de comissões inválido")
    count_width = payload[2] - 0x60
    signature_at = 26 + count_width
    if count_width not in (1, 2, 3, 4) or payload[signature_at:signature_at+4] != bytes.fromhex("9619e0bd"):
        raise RuntimeError("Assinatura MIDAS divergente")
    expected = struct.unpack_from("<I", payload, signature_at - 8)[0] + signature_at
    if expected < 32 or expected > MAX_BYTES:
        raise RuntimeError("Volume acima do limite")
    # Commission datasets continue using blob index 2, not OS report index 1.
    for _ in range(512):
        if len(payload) >= expected:
            break
        remaining = expected - len(payload)
        result = client.request("more_blob", [handle, 2, 0, 7, True, 0])
        chunk = result["result"][0]["data"][1]
        if not chunk or len(chunk) > remaining:
            raise RuntimeError("Fragmento inválido no relatório de comissões")
        payload.extend(chunk)
    if len(payload) != expected:
        raise RuntimeError("Relatório incompleto; exportação interrompida")
    return bytes(payload)

def fetch_datasets(profile, start, end, *, client_factory=None,
                   credential_path=CREDENTIALS, templates=None):
    if profile not in PORTS:
        raise ValueError("Cidade inválida")
    validate_range(start, end)
    # Safe read-only client: authenticate with existing server-side credentials.
    from datasnap_client import DataSnapClient, load_credentials
    factory = client_factory or DataSnapClient
    credentials = load_credentials(Path(credential_path))
    datasets = {}
    with factory("www.sistemaimperium.com.br", PORTS[profile],
                 credentials["username"], credentials["password"], timeout=90) as client:
        for name in DATASETS:
            prepared = client.request("prepare", [-1, False, "DataSnap.ServerMethod", METHOD])
            handle = int(prepared["result"][0]["handle"][0])
            response = client.request("execute", [{"handle": [handle]},
                                                   build_query(name, start, end, templates=templates)])
            raw = _dataset_bytes(client, handle, response)
            rows = decode_dataset(raw, max_bytes=MAX_BYTES, max_records=MAX_RECORDS)
            if not isinstance(rows, list):
                raise RuntimeError("Comissão inválida")
            expected_fields = {
                field for sheet_name, dataset, cols in SHEETS if dataset == name
                for _, field, _ in cols
            }
            if rows and any(not expected_fields.issubset(row.keys()) for row in rows):
                raise RuntimeError("O formato do Imperium mudou")
            datasets[name] = rows
    return datasets

def _worksheet_xml(rows, columns):
    out = io.StringIO()
    out.write('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
              'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    out.write('<cols>')
    for index, (caption, field, kind) in enumerate(columns, 1):
        width = 52 if field in {"NomeAbreviado", "Produto"} else 20 if kind == "date" else 18
        out.write(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
    out.write('</cols><sheetData>')
    for ri, values in enumerate([None, *rows], 1):
        out.write(f'<row r="{ri}">')
        for ci, (caption, field, kind) in enumerate(columns, 1):
            if values is None:
                value, style = caption, 2
            elif kind == "money":
                raw = values.get(field)
                if raw is None or raw == "":
                    continue
                value, style = round(float(raw), 2), 3
            else:
                value, style = excel_value(values.get(field), kind)
                if value is None:
                    continue
            address = _column(ci) + str(ri)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out.write(f'<c r="{address}" s="{style}"><v>{value}</v></c>')
            else:
                out.write(f'<c r="{address}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
                          f'{_text(value)}</t></is></c>')
        out.write('</row>')
    right = _column(len(columns))
    out.write(f'</sheetData><autoFilter ref="A1:{right}{max(1,len(rows)+1)}"/></worksheet>')
    return out.getvalue()

def export_xlsx(datasets):
    if set(datasets) != set(DATASETS):
        raise ValueError("Datasets incompletos")
    ns = "http://schemas.openxmlformats.org"
    xml = {}
    xml["[Content_Types].xml"] = (
        f'<Types xmlns="{ns}/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,4))
        + '</Types>')
    xml["_rels/.rels"] = (
        f'<Relationships xmlns="{ns}/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{ns}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    xml["xl/workbook.xml"] = (
        f'<workbook xmlns="{ns}/spreadsheetml/2006/main" xmlns:r="{ns}/officeDocument/2006/relationships">'
        '<sheets>' + "".join(
            f'<sheet name="{escape(title)}" sheetId="{i}" r:id="rId{i}"/>'
            for i,(title,_,_) in enumerate(SHEETS,1))
        + '</sheets></workbook>')
    xml["xl/_rels/workbook.xml.rels"] = (
        f'<Relationships xmlns="{ns}/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i}" Type="{ns}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,4))
        + f'<Relationship Id="rId4" Type="{ns}/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        + '</Relationships>')
    xml["xl/styles.xml"] = (
        f'<styleSheet xmlns="{ns}/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>')
    for i, (title,name,cols) in enumerate(SHEETS, 1):
        rows = datasets[name]
        if len(rows) > MAX_RECORDS:
            raise ValueError("Número de registros acima do limite")
        xml[f"xl/worksheets/sheet{i}.xml"] = _worksheet_xml(rows, cols)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in xml.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + content)
    if stream.tell() > 35_000_000:
        raise ValueError("O arquivo Excel excedeu o limite")
    return stream.getvalue()

class CommissionReportService:
    def __init__(self, fetcher=fetch_datasets):
        self.fetcher = fetcher
        self.locks = {profile: threading.Lock() for profile in PORTS}

    def download(self, route):
        profile,start,end = route.groups()
        validate_range(start,end)
        lock=self.locks[profile]
        if not lock.acquire(blocking=False):
            raise ValueError("Já existe um relatório de comissão em execução nesta cidade")
        try:
            datasets=self.fetcher(profile,start,end)
            contents=export_xlsx(datasets)
            filename=f"Comissoes_{profile}_{start}_{end}.xlsx"
            return contents,filename,{name:len(rows) for name,rows in datasets.items()}
        finally:
            lock.release()
