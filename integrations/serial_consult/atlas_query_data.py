"""Parse Atlas analytic equipment report and export read-only CSV/XLSX.

Keeps serials and SAP material codes as TEXT. No Excel executable or macros.
Private report source stays on Windows, outside version control.
"""
from __future__ import annotations
import csv
import io
import json
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape

from atlas_query_report import connect_db
from atlas_query_pipeline import upgrade_db

COLUMNS = [
    ("numero_serie","Número Série"),
    ("codigo_material_sap","Código Material SAP"),
    ("codigo_sap_normalizado","Código SAP sem zeros"),
    ("modelo","Modelo"),
    ("enderecavel_principal","Endereçável Principal"),
    ("operacao","Operação"),
    ("nome_local","Nome do Local"),
    ("estado","Estado"),
    ("data_ultima_alteracao","Data Última Alteração"),
    ("responsavel","Responsável"),
    ("numero_contrato","Número do Contrato")
]
ALIASES = {
 "numero_serie":("NUMERO SERIE","N SERIE","SERIAL","NUM SERIE","SERIE"),
 "codigo_material_sap":("CODIGO MATERIAL SAP","COD MATERIAL SAP","CODIGO SAP"),
 "modelo":("MODELO","MODELO EQUIPAMENTO","MODELO DO EQUIPAMENTO"),
 "enderecavel_principal":("ENDERECAVEL PRINCIPAL","ENDERECAVEL","MAC"),
 "operacao":("OPERACAO","CIDADE","PRACA","MUNICIPIO"),
 "nome_local":("NOME DO LOCAL","LOCALIZACAO","LOCAL","LOCAL DE ESTOQUE"),
 "estado":("ESTADO","STATUS","SITUACAO"),
 "data_ultima_alteracao":("DATA ULTIMA ALTERACAO","DATA ALTERACAO","DT ALTERACAO"),
 "responsavel":("RESPONSAVEL","USUARIO"),
 "numero_contrato":("NUMERO DO CONTRATO","NUMERO CONTRATO","CONTRATO")
}
MAX_SOURCE = 60_000_000
MAX_RECORDS = 100_000
MAX_COLUMNS = 150


def normalized(text):
    return re.sub(r"[^A-Z0-9]+"," ",unicodedata.normalize("NFD",str(text or "")).encode(
        "ascii","ignore").decode("ascii").upper()).strip()


def material_no_zero(value):
    value=str(value or "").strip()
    # Do not cast identifiers to numbers or lose nonnumeric prefixes.
    return (value.lstrip("0") or "0") if value.isdigit() else value


class HTMLTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.level=0;self.row=None;self.cell=None;self.current=[]
    def handle_starttag(self,tag,attrs):
        if tag=="table":
            self.level+=1
            if self.level==1:self.current=[]
        elif tag=="tr" and self.level==1:self.row=[]
        elif tag in ("th","td") and self.row is not None and self.level==1:self.cell=[]
        elif tag=="br" and self.cell is not None:self.cell.append(" ")
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("th","td") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip());self.cell=None
        elif tag=="tr" and self.row is not None:
            if self.row:self.current.append(self.row)
            self.row=None
        elif tag=="table" and self.level:
            if self.level==1:self.tables.append(self.current)
            self.level-=1


def parse_html(raw):
    text=raw.decode("utf-8-sig",errors="replace")
    if text.count("\ufffd")>8:text=raw.decode("windows-1252",errors="replace")
    parser=HTMLTable();parser.feed(text)
    return max(parser.tables,key=score_rows,default=[])


def score_rows(rows):
    return max((sum(normalized(x) in ALIASES["numero_serie"] for x in row)*100+
          sum(normalized(x) in ALIASES["estado"] for x in row)*10
          for row in rows[:35]),default=0)


def parse_xlsx(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        if len(names)>100 or any(n.startswith("/") or ".." in n.split("/") for n in names):
            raise ValueError("Arquivo XLSX invalido")
        def read(n):
            info=archive.getinfo(n)
            if info.file_size>40_000_000:raise ValueError("XML Excel excessivo")
            return archive.read(n)
        shared=[]
        if "xl/sharedStrings.xml" in names:
            root=ET.fromstring(read("xl/sharedStrings.xml"))
            shared=["".join(s.itertext()) for s in root]
        sheets=[n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",n)]
        if not sheets:raise ValueError("Planilha sem abas")
        output=[]
        ns={"x":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for sheet in sheets[:15]:
            root=ET.fromstring(read(sheet))
            rows=[]
            for row in root.findall(".//x:sheetData/x:row",ns):
                values=[]
                for c in row.findall("x:c",ns):
                    ref=c.attrib.get("r","")
                    letters=re.match(r"[A-Z]+",ref)
                    if not letters:continue
                    col=0
                    for letter in letters.group():col=col*26+ord(letter)-64
                    if col>MAX_COLUMNS:continue
                    value=c.find("x:v",ns)
                    text=(value.text or "") if value is not None else ""
                    if c.attrib.get("t")=="s" and text.isdigit():
                        text=shared[int(text)] if int(text)<len(shared) else ""
                    elif c.attrib.get("t")=="inlineStr":
                        node=c.find("x:is",ns);text="".join(node.itertext()) if node is not None else ""
                    while len(values)<col:values.append("")
                    values[col-1]=text
                if values:rows.append(values)
                if len(rows)>MAX_RECORDS+50:raise ValueError("Muitas linhas")
            if score_rows(rows)>score_rows(output):output=rows
        return output


def parse_xls(raw):
    try:
        import xlrd
    except ImportError as error:
        raise ValueError("Leitor XLS legado xlrd ainda nao instalado") from error
    book=xlrd.open_workbook(file_contents=raw)
    best=[]
    for sheet in book.sheets()[:15]:
        rows=[[str(v).strip() if not isinstance(v,str) else v.strip() for v in sheet.row_values(i)]
              for i in range(min(sheet.nrows,MAX_RECORDS+50))]
        if score_rows(rows)>score_rows(best):best=rows
    return best


def parse_report(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>MAX_SOURCE:
        raise ValueError("Relatorio ausente ou excessivo")
    raw=path.read_bytes()
    if raw.startswith(bytes.fromhex("d0cf11e0")):rows=parse_xls(raw)
    elif raw.startswith(b"PK"):rows=parse_xlsx(raw)
    elif b"<table" in raw[:50000].lower():rows=parse_html(raw)
    else:raise ValueError("Formato Atlas nao suportado")
    ix=-1;mapping={}
    for i,row in enumerate(rows[:40]):
        keys={normalized(v):j for j,v in enumerate(row[:MAX_COLUMNS])}
        if any(alias in keys for alias in ALIASES["numero_serie"]):
            ix=i
            for key,names in ALIASES.items():
                mapping[key]=next((keys[name] for name in names if name in keys),-1)
            break
    if ix<0:raise ValueError("Cabecalho de equipamentos nao encontrado")
    records=[]
    for row in rows[ix+1:]:
        item={}
        for key,_ in COLUMNS:
            if key=="codigo_sap_normalizado":continue
            col=mapping.get(key,-1)
            item[key]=str(row[col]).strip()[:500] if col>=0 and col<len(row) else ""
        serial=item["numero_serie"]
        if not serial or not re.fullmatch(r"[A-Za-z0-9._/-]{4,50}",serial):
            continue
        item["codigo_sap_normalizado"]=material_no_zero(item.get("codigo_material_sap"))
        records.append(item)
        if len(records)>MAX_RECORDS:raise ValueError("Limite de linhas excedido")
    if not records:raise ValueError("Nenhum serial identificado no relatorio")
    return records


def store_records(job_id,records,db_path):
    upgrade_db(db_path)
    with connect_db(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS query_rows
          (job_id TEXT NOT NULL, position INTEGER NOT NULL,
           data TEXT NOT NULL,PRIMARY KEY (job_id,position))""")
        db.execute("DELETE FROM query_rows WHERE job_id=?",(job_id,))
        db.executemany("INSERT INTO query_rows(job_id,position,data) VALUES (?,?,?)",
            ((job_id,i,json.dumps(record,ensure_ascii=False)) for i,record in enumerate(records)))


def page(job_id,db_path,offset=0,limit=100,status=""):
    if not 0<=offset<=100000 or not 1<=limit<=500 or len(status)>80:
        raise ValueError("Paginacao invalida")
    with connect_db(db_path) as db:
        if status:
            # JSON extraction avoids unsafe SQL interpolation.
            clause=" AND json_extract(data,'$.estado')=?"
            values=(job_id,status)
        else:
            clause="";values=(job_id,)
        total=db.execute("SELECT COUNT(*) FROM query_rows WHERE job_id=?"+clause,values).fetchone()[0]
        rows=db.execute("SELECT data FROM query_rows WHERE job_id=?"+clause+
            " ORDER BY position LIMIT ? OFFSET ?",(*values,limit,offset)).fetchall()
    return {"total":total,"offset":offset,"limit":limit,
            "columns":[{"id":key,"title":label} for key,label in COLUMNS],
            "rows":[json.loads(row[0]) for row in rows]}


def export_csv(rows):
    output=io.StringIO(newline="")
    output.write("\ufeff")
    writer=csv.writer(output,delimiter=";",lineterminator="\r\n")
    writer.writerow([label for _,label in COLUMNS])
    for record in rows:
        cells=[]
        for key,_ in COLUMNS:
            value=str(record.get(key) or "")
            if value.lstrip().startswith(("=","+","-","@","\t","\r")):value="'"+value
            cells.append(value)
        writer.writerow(cells)
    return output.getvalue().encode("utf-8")


def xml_chars(value):
    value="".join(c for c in str(value)[:32767] if ord(c) in (9,10,13) or ord(c)>=32)
    return escape(value,{"\"":"&quot;","'":"&apos;"})


def export_xlsx(rows):
    def line(index,values):
        cells=[]
        for n,value in enumerate(values):
            col="";x=n+1
            while x: x,r=divmod(x-1,26);col=chr(65+r)+col
            cells.append(f'<c r="{col}{index}" t="inlineStr"><is><t xml:space="preserve">{xml_chars(value)}</t></is></c>')
        return f'<row r="{index}">{"".join(cells)}</row>'
    src=io.BytesIO()
    with zipfile.ZipFile(src,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("_rels/.rels",'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/_rels/workbook.xml.rels",'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="QUERY Atlas" sheetId="1" r:id="rId1"/></sheets></workbook>')
        sheet=['<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>']
        sheet.append(line(1,[label for _,label in COLUMNS]))
        for number,record in enumerate(rows,start=2):
            sheet.append(line(number,[record.get(key,"") for key,_ in COLUMNS]))
        sheet.append('</sheetData><autoFilter ref="A1:K'+str(len(rows)+1)+'"/></worksheet>')
        z.writestr("xl/worksheets/sheet1.xml","".join(sheet))
    return src.getvalue()
