"""Initial XLSX bootstrap for DOMINIUM's read-only DESC history.

Keeps one immutable row per Imperium export line, without importing customer
names, addresses, phone numbers or other unnecessary personal information.
Never executes a DataSnap write method.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from backlog_imperium_service import SCHEMA, utcnow

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = {
    "DATA": "activity_date",
    "NUM CONTRATO": "contract",
    "NUM OS": "os_number",
    "SERVICO": "service",
    "INSTALADOR": "technician",
    "CIDADE": "city",
    "STATUS": "status",
    "DATA DA BAIXA": "baixa_date",
    "COD BAIXA": "code",
    "DESC COD BAIXA": "code_description",
}
PROFILES = {"ntl": "natal", "mro": "mossoro", "ftz": "fortaleza", "jcr": "recife"}
STATUS = {"1": "EM CAMPO", "2": "CONCLUIDA", "3": "CANCELADA", "4": "REAGENDADA"}
SEED_SCHEMA = """
CREATE TABLE IF NOT EXISTS history_seed_rows (
 profile TEXT NOT NULL, file_sha256 TEXT NOT NULL, sheet TEXT NOT NULL,
 source_row INTEGER NOT NULL, activity_date TEXT NOT NULL, baixa_date TEXT,
 os_number TEXT NOT NULL, contract TEXT NOT NULL, service TEXT NOT NULL,
 technician TEXT, city TEXT, status TEXT NOT NULL, code TEXT,
 code_description TEXT, imported_at TEXT NOT NULL,
 PRIMARY KEY(file_sha256, sheet, source_row)
);
CREATE INDEX IF NOT EXISTS idx_history_seed_contract
 ON history_seed_rows(profile, contract, activity_date DESC);
CREATE TABLE IF NOT EXISTS history_seed_files (
 file_sha256 TEXT PRIMARY KEY, filename TEXT NOT NULL, profile TEXT NOT NULL,
 row_count INTEGER NOT NULL, date_min TEXT, date_max TEXT,
 imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history_seed_rejections (
 file_sha256 TEXT NOT NULL, sheet TEXT NOT NULL, source_row INTEGER NOT NULL,
 reason TEXT NOT NULL,
 PRIMARY KEY(file_sha256,sheet,source_row)
);
"""
def normalize(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").strip().upper())
    return re.sub(r"[^A-Z0-9]+", " ", "".join(c for c in value if not unicodedata.combining(c))).strip()

def date_iso(value: object) -> str | None:
    value = str(value or "").strip()
    if not value:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        serial = float(value)
        if 20000 <= serial < 100000:
            return (dt.date(1899, 12, 30) + dt.timedelta(days=int(serial))).isoformat()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    items: list[str] = []
    with z.open("xl/sharedStrings.xml") as handle:
        for _event, elem in ET.iterparse(handle, events=("end",)):
            if elem.tag == MAIN + "si":
                items.append("".join(node.text or "" for node in elem.iter(MAIN + "t")))
                elem.clear()
    return items

def stream_rows(z: zipfile.ZipFile, path: str, strings: list[str]):
    with z.open(path) as handle:
        for _event, element in ET.iterparse(handle, events=("end",)):
            if element.tag != MAIN + "row":
                continue
            cells: dict[int, str] = {}
            for cell in element.iter(MAIN + "c"):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                col = 0
                for char in match.group(1):
                    col = col * 26 + ord(char) - 64
                value_elem = cell.find(MAIN + "v")
                raw = value_elem.text if value_elem is not None else ""
                if cell.attrib.get("t") == "s" and raw:
                    try:
                        raw = strings[int(raw)]
                    except (IndexError, ValueError):
                        raise ValueError("SharedStrings XLSX invalido")
                elif cell.attrib.get("t") == "inlineStr":
                    raw = "".join(t.text or "" for t in cell.iter(MAIN + "t"))
                cells[col - 1] = str(raw or "").strip()
            yield int(element.attrib.get("r", "0")), cells
            element.clear()

def profile_from_filename(path: Path) -> str:
    filename = path.name.upper()
    for key, profile in PROFILES.items():
        if re.search(r"(?:^|[^A-Z])" + key.upper() + r"(?:[^A-Z]|$)", filename):
            return profile
    raise ValueError("Nome nao identifica NTL, MRO, FTZ ou JCR: " + path.name)

def event_id(profile: str, row: dict[str, str]) -> int:
    # Negative signed ID range is reserved for spreadsheet-derived records.
    source = "\x1f".join([profile, row["activity_date"], row["os_number"],
                          row["contract"], row["status"], row["code"],
                          row["service"], row["technician"], row["baixa_date"]])
    return -(int.from_bytes(hashlib.sha256(source.encode("utf-8")).digest()[:8], "big") & ((1 << 61) - 1)) - 1

def ingest(db_path: Path, xlsx_path: Path) -> dict:
    if xlsx_path.suffix.lower() != ".xlsx" or not xlsx_path.is_file():
        raise ValueError("Arquivo XLSX necessario: " + str(xlsx_path))
    if xlsx_path.stat().st_size > 24 * 1024 * 1024:
        raise ValueError("Arquivo excede 24 MiB")
    profile = profile_from_filename(xlsx_path)
    digest = hashlib.sha256(xlsx_path.read_bytes()).hexdigest()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    try:
        connection.executescript(SCHEMA)
        connection.executescript(SEED_SCHEMA)
        connection.execute("PRAGMA busy_timeout=30000")
        if connection.execute("SELECT 1 FROM history_seed_files WHERE file_sha256=?", (digest,)).fetchone():
            return {"file": xlsx_path.name, "profile": profile, "already_imported": True}
        imported_at = utcnow()
        count, skipped, earliest, latest = 0, 0, None, None
        seen = set()
        connection.execute("BEGIN IMMEDIATE")
        with zipfile.ZipFile(xlsx_path) as z:
            strings = shared_strings(z)
            sheets = sorted(p for p in z.namelist()
                            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", p))
            if not sheets:
                raise ValueError("Planilha XLSX sem abas")
            for sheet_path in sheets:
                mapping = None
                for source_row, cells in stream_rows(z, sheet_path, strings):
                    detected = {HEADERS[normalize(v)]: k for k, v in cells.items()
                                if normalize(v) in HEADERS}
                    if {"contract", "os_number", "activity_date", "code"} <= set(detected):
                        mapping = detected
                        continue
                    if not mapping:
                        continue
                    def col(key):
                        return cells.get(mapping.get(key, -1), "")
                    activity_date = date_iso(col("activity_date"))
                    contract = re.sub(r"\D", "", col("contract").removesuffix(".0"))
                    os_number = col("os_number").removesuffix(".0").strip()
                    if not activity_date or not (4 <= len(contract) <= 20) or not os_number:
                        # No personal data from rejected rows is persisted.
                        reason = ("invalid_date" if not activity_date else
                                  "invalid_contract" if not (4 <= len(contract) <= 20) else
                                  "invalid_os")
                        connection.execute("""INSERT INTO history_seed_rejections
                            (file_sha256,sheet,source_row,reason) VALUES(?,?,?,?)""",
                            (digest,sheet_path,source_row,reason))
                        skipped += 1
                        continue
                    raw_code = col("code")
                    code = raw_code.zfill(3) if re.fullmatch(r"\d{1,3}", raw_code) and raw_code not in ("", "0", "00", "000") else ""
                    row = {
                        "activity_date": activity_date, "baixa_date": date_iso(col("baixa_date")) or "",
                        "os_number": os_number, "contract": contract,
                        "service": col("service")[:180], "technician": col("technician")[:180],
                        "city": col("city")[:120], "status": STATUS.get(col("status"), col("status")[:35]),
                        "code": code, "code_description": col("code_description")[:160],
                    }
                    key = (sheet_path, source_row)
                    if key in seen:
                        raise ValueError("Linha duplicada no XLSX")
                    seen.add(key)
                    connection.execute("""INSERT INTO history_seed_rows
                      (profile,file_sha256,sheet,source_row,activity_date,baixa_date,
                       os_number,contract,service,technician,city,status,code,
                       code_description,imported_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (profile,digest,sheet_path,source_row,row["activity_date"],row["baixa_date"],
                       row["os_number"],row["contract"],row["service"],row["technician"],
                       row["city"],row["status"],row["code"],row["code_description"],imported_at))
                    # The existing Backlog endpoints already read the history table.
                    # Preserve true DataSnap records in the extremely unlikely event of a key collision.
                    connection.execute("""INSERT OR IGNORE INTO history
                      (profile,id_os,activity_date,os_number,contract,service,code,
                       verification,status,captured_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                      (profile,event_id(profile,row),activity_date,os_number,contract,
                       row["service"],code or None,
                       "xlsx_seed" if re.fullmatch(r"\d+(?: \d+)*",os_number) else "xlsx_seed_ambiguous_os",
                       row["status"],imported_at))
                    earliest = min(earliest, activity_date) if earliest else activity_date
                    latest = max(latest, activity_date) if latest else activity_date
                    count += 1
        if not count:
            raise ValueError("Nenhuma linha de desconexao importavel")
        connection.execute("""INSERT INTO history_seed_files
          (file_sha256,filename,profile,row_count,date_min,date_max,imported_at)
          VALUES(?,?,?,?,?,?,?)""",
          (digest,xlsx_path.name,profile,count,earliest,latest,imported_at))
        # Only advance the daily-sync cursor after the whole file committed.
        # A missing historical month remains visible in coverage/date_min.
        old = connection.execute("SELECT date FROM checkpoint WHERE profile=?", (profile,)).fetchone()
        if not old or old[0] < latest:
            connection.execute("""INSERT INTO checkpoint(profile,date,updated_at) VALUES(?,?,?)
              ON CONFLICT(profile) DO UPDATE SET date=excluded.date,updated_at=excluded.updated_at""",
              (profile,latest,imported_at))
        connection.commit()
        return {"file": xlsx_path.name, "profile": profile, "rows": count,
                "date_min": earliest, "date_max": latest, "skipped": skipped, "sha256": digest}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="Carga inicial XLSX DESC, somente leitura")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    if len(args.files) > 4 or len({profile_from_filename(p) for p in args.files}) != len(args.files):
        parser.error("Informe no maximo 4 arquivos, um para cada cidade")
    import json
    for path in args.files:
        print(json.dumps(ingest(args.db, path), ensure_ascii=False))

if __name__ == "__main__":
    main()
