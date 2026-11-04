"""Read-only Imperium Equipamentos Utilizados: DspConsolidadoEquip/OS.

Provider names, parameters, parent DataSnap module verified in installed
ClientVCL.exe. Query packets are built from captured, audited READ templates.
Do not expose to production until a bounded live smoke and schema pass.
"""
from __future__ import annotations
import base64
import datetime as dt
import json
import re
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
METHOD="TDtmOrdemServico.AS_GetRecords"
PROVIDERS={"consolidado":b"DspConsolidadoEquip","por_os":b"DspConsolidadoOS"}
PARAM=bytes.fromhex("0c20000001000000000000000600000008000000")
END=bytes.fromhex("1000050200000000c0")
FIELDS={
 "consolidado":{"Grupo","CodigoEquipamento","Equipamento","Qtd"},
 "por_os":{"DataBaixa","NumOs","Contrato","CodigoEquipamento","Qtd"},
}

def captured_records(packet):
    size=packet[0]-32
    if size<5 or packet[1+size:6+size]!=b"!\x01\x60a\x01":
        raise ValueError("Envelope DataSnap invalido")
    if not packet.endswith(END):
        raise ValueError("Envelope DataSnap incompleto")
    positions=[m.start() for m in re.finditer(re.escape(PARAM),packet)]
    if not positions:raise ValueError("Parametros DataSnap ausentes")
    result={}
    for i,at in enumerate(positions):
        n=struct.unpack_from("<I",packet,at+len(PARAM))[0]
        first=at+len(PARAM)+4
        name=packet[first:first+n*2].decode("utf-16le")
        stop=positions[i+1] if i+1<len(positions) else len(packet)-len(END)
        result[name]=packet[at:stop]
    return result

def update_param(record,name,value,datatype):
    start=len(PARAM)+4+2*len(name)
    found=struct.unpack_from("<I",record,start)[0]
    if found!=datatype:raise ValueError("Tipo de parametro DataSnap divergente: "+name)
    if datatype==7:
        data=struct.pack("<d",value);stop=start+12
    elif datatype==3:
        data=struct.pack("<I",value);stop=start+8
    elif datatype==8:
        n=struct.unpack_from("<I",record,start+4)[0]
        stop=start+8+n*2
        data=struct.pack("<I",len(value))+value.encode("utf-16le")
    else:raise ValueError("Tipo de parametro nao permitido")
    return record[:start+4]+data+record[stop:]

def replace_name(record,old,new):
    start=len(PARAM)+4
    old_bytes=old.encode("utf-16le")
    if record[start:start+len(old_bytes)]!=old_bytes:
        raise ValueError("Parametro original divergente")
    return (record[:len(PARAM)]+struct.pack("<I",len(new))
      +new.encode("utf-16le")+record[start+len(old_bytes):])

def packet_for(begin,end,*,mode="consolidado",partner_id=1,service="%",group="%",root=ROOT):
    if mode not in PROVIDERS:raise ValueError("Tipo de relatorio invalido")
    if not isinstance(begin,dt.date) or not isinstance(end,dt.date):
        raise ValueError("Datas invalidas")
    if begin>end or (end-begin).days>30 or end>dt.date.today():
        raise ValueError("Periodo invalido ou acima de 31 dias")
    if not 1<=partner_id<=9999:raise ValueError("Parceiro invalido")
    if any(not re.fullmatch("[A-Z0-9%,-]{1,15}",x) for x in (service,group)):
        raise ValueError("Grupo/servico invalido")
    root=Path(root)
    order=json.loads((root/"protocol_templates.json").read_text(encoding="utf-8"))
    stock=json.loads((root/"stock_protocol_templates.json").read_text(encoding="utf-8"))
    orders=captured_records(base64.b64decode(order["main_query"]))
    stocks=captured_records(base64.b64decode(stock["items"]["query"]))
    serial=lambda day,finish:float((day-dt.date(1899,12,30)).days)+(1-1/86400000 if finish else 0)
    items=[
        orders["@RETURN_VALUE"],
        update_param(orders["@DataIni"],"@DataIni",serial(begin,False),7),
        update_param(orders["@DataFim"],"@DataFim",serial(end,True),7),
        update_param(stocks["@IdParceiro"],"@IdParceiro",partner_id,3),
        update_param(orders["@IdTipoServico"],"@IdTipoServico",service,8),
        update_param(replace_name(stocks["@IdGrupoEquipamentos"],
                                  "@IdGrupoEquipamentos","@IdGrupoEquipamento"),
                     "@IdGrupoEquipamento",group,8),
    ]
    body=PARAM[:12]+struct.pack("<I",len(items)-1)+b"".join(items)+END
    n=len(body)-8
    if n>65535:raise ValueError("Pacote DataSnap excessivo")
    provider=PROVIDERS[mode]
    return bytes([32+len(provider)])+provider+b"!\x01\x60a\x01"+b"\x20\x10"+bytes([n//256,n%256,2])+body

def fetch(begin,end,*,profile="natal",mode="consolidado",partner_id=1,root=ROOT):
    """One bounded read of a verified provider, using local protected credentials."""
    import sys
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    from datasnap_client import DataSnapClient,load_credentials
    from imperium_api import HOST,ImperiumAPI
    from midas_reader import decode_dataset,PacketError
    ports={"natal":212,"fortaleza":596,"mossoro":579,"recife":599}
    if profile not in ports:raise ValueError("Praca invalida")
    query=packet_for(begin,end,mode=mode,partner_id=partner_id,root=root)
    credentials=load_credentials(Path(r"C:\DominiumMain\config\credentials.dat"))
    with DataSnapClient(HOST,ports[profile],credentials["username"],
                        credentials["password"],timeout=25) as client:
        handle=ImperiumAPI._handle(client,METHOD)
        raw=ImperiumAPI._dataset_payload(client,handle,query,"Equipamentos Utilizados")
    rows=decode_dataset(raw)
    if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):
        raise PacketError("Dataset DataSnap invalido")
    if rows and not FIELDS[mode].issubset(rows[0]):
        raise PacketError("Colunas inesperadas: consulta nao foi confirmada")
    return rows
