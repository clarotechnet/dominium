"""SQLite materialized, paged views of completed stock-analysis XLSX reports."""
from __future__ import annotations
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from xml.etree import ElementTree as ET

M='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def snapshot_page(database:Path,workbook:Path,job_id:str,*,page:int=1,page_size:int=100)->dict:
    if not 1<=page<=10000 or page_size!=100:
        raise ValueError('Pagina invalida')
    database=Path(database);workbook=Path(workbook)
    with closing(sqlite3.connect(database,timeout=30)) as db:
        db.execute('PRAGMA busy_timeout=30000')
        db.execute('''CREATE TABLE IF NOT EXISTS analysis_sheet_snapshots(
          job_id TEXT PRIMARY KEY,header_json TEXT NOT NULL,
          total INTEGER NOT NULL,workbook_mtime_ns INTEGER NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS analysis_sheet_records(
          job_id TEXT NOT NULL,position INTEGER NOT NULL,row_json TEXT NOT NULL,
          PRIMARY KEY(job_id,position))''')
        db.commit()
        mtime=workbook.stat().st_mtime_ns
        stored=db.execute('SELECT header_json,total,workbook_mtime_ns FROM analysis_sheet_snapshots WHERE job_id=?',(job_id,)).fetchone()
        if not stored or stored[2]!=mtime:
            with zipfile.ZipFile(workbook) as z:
                name='xl/worksheets/sheet1.xml'
                with z.open(name) as stream:
                    header=[];position=0
                    db.execute('DELETE FROM analysis_sheet_records WHERE job_id=?',(job_id,))
                    for _,element in ET.iterparse(stream,events=('end',)):
                        if element.tag!=M+'row':continue
                        row=[]
                        for c in element.findall(M+'c'):
                            address=c.attrib.get('r','')
                            letters=''.join(x for x in address if x.isalpha())
                            idx=0
                            for letter in letters:idx=idx*26+(ord(letter)-64)
                            idx-=1
                            if idx<0 or idx>=60:continue
                            value=''.join(t.text or '' for t in c.iter(M+'t'))
                            if not value:
                                raw=c.find(M+'v')
                                value=raw.text or '' if raw is not None else ''
                            if len(row)<=idx:row.extend(['']*(idx+1-len(row)))
                            row[idx]=value[:800]
                        if position==0:header=row
                        else:
                            db.execute('INSERT INTO analysis_sheet_records VALUES(?,?,?)',
                                       (job_id,position-1,json.dumps(row,ensure_ascii=False)))
                        position+=1;element.clear()
                    if not header:raise ValueError('Relatorio sem colunas')
                    total=position-1
                    db.execute('INSERT OR REPLACE INTO analysis_sheet_snapshots VALUES(?,?,?,?)',
                               (job_id,json.dumps(header,ensure_ascii=False),total,mtime))
                    db.commit()
                    stored=(json.dumps(header,ensure_ascii=False),total,mtime)
        rows=db.execute('SELECT row_json FROM analysis_sheet_records WHERE job_id=? AND position>=? AND position<? ORDER BY position',
                        (job_id,(page-1)*page_size,page*page_size)).fetchall()
        return {'ok':True,'header':json.loads(stored[0]),'rows':[json.loads(x[0]) for x in rows],
                'total':stored[1],'page':page,'pages':max(1,(stored[1]+page_size-1)//page_size)}
