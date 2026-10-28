"""Leitura e snapshots de estoque diario no Supabase operacional do Dominium."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EXPECTED_SUPABASE = "https://haqzzxpocwzntyudrbch.supabase.co"
UUID_RE = re.compile(r"^[a-f0-9-]{36}$",re.I)
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")

class DailyStockError(Exception):
    def __init__(self,status,message):
        super().__init__(message)
        self.status=status

class DailyStockService:
    def __init__(self,env_file=None):
        env={}
        path=Path(env_file or os.getenv("DOMINIUM_QUALITY_ENV_FILE")
                  or "C:/DominiumMain/.env")
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" not in line or line.lstrip().startswith("#"): continue
            k,v=line.split("=",1)
            env[k.strip()]=v.strip().strip(chr(34)).strip(chr(39))
        url=env.get("SUPABASE_URL","").rstrip("/")
        key=env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
        if url != EXPECTED_SUPABASE or not key:
            raise DailyStockError(503,"Supabase privado do Dominium indisponivel")
        self.base=url+"/rest/v1/"
        self.key=key

    def _call(self,route,method="GET",query=None,body=None):
        uri=self.base+route+("?" + urlencode(query) if query else "")
        encoded=json.dumps(body,ensure_ascii=False).encode("utf-8") if body is not None else None
        headers={"apikey":self.key,"Authorization":"Bearer "+self.key,
                 "Accept":"application/json","Prefer":"return=representation"}
        if encoded is not None: headers["Content-Type"]="application/json"
        request=Request(uri,headers=headers,data=encoded,method=method)
        try:
            with urlopen(request,timeout=30) as response:
                data=response.read(3_000_001)
                if len(data)>3_000_000: raise DailyStockError(502,"Resposta muito grande")
                return json.loads(data or b"null")
        except HTTPError as exc:
            if exc.code==404:
                raise DailyStockError(503,"Tabelas de Estoque Diario ainda nao instaladas no Supabase") from None
            if exc.code==409:
                raise DailyStockError(409,"Importacao duplicada ou alterada") from None
            raise DailyStockError(502,"Nao foi possivel processar os dados do Estoque Diario") from None
        except (URLError,TimeoutError,ValueError) as exc:
            raise DailyStockError(502,"Conexao ao Supabase temporariamente indisponivel") from exc

    def view(self,import_id=None):
        history=self._call("estoque_diario_importacoes",query={
            "select":"id,data_estoque,nome_arquivo,linhas_origem,materiais_distintos,quantidade_total,importado_por,importado_em",
            "order":"data_estoque.desc,importado_em.desc,id.desc","limit":30
        })
        if not isinstance(history,list): raise DailyStockError(502,"Historico invalido")
        if import_id:
            if not UUID_RE.fullmatch(import_id): raise DailyStockError(400,"Identificador invalido")
            chosen=next((r for r in history if r["id"]==import_id),None)
            if not chosen: raise DailyStockError(404,"Importacao nao encontrada nas ultimas 30 versoes")
        else:
            chosen=history[0] if history else None
        items=[]
        if chosen:
            items=self._call("estoque_diario_itens",query={
                "select":"material,descricao_material,quantidade_livre",
                "importacao_id":"eq."+chosen["id"],"order":"material.asc","limit":10000
            })
            if not isinstance(items,list): raise DailyStockError(502,"Lista de materiais invalida")
        return {"ok":True,"historico":history,"snapshot":chosen,"items":items,
                "total":len(items)}

    def store(self,payload,actor):
        if not isinstance(payload,dict) or not actor or len(actor)>100:
            raise DailyStockError(400,"Operador ou arquivo invalidos")
        data=str(payload.get("data_estoque",""))
        filename=str(payload.get("nome_arquivo",""))
        digest=str(payload.get("hash_arquivo",""))
        rows=payload.get("items")
        try: original=int(payload.get("linhas_origem",0))
        except (ValueError,TypeError): original=0
        if not DAY_RE.fullmatch(data) or len(filename) not in range(1,181) or not HASH_RE.fullmatch(digest):
            raise DailyStockError(400,"Data, nome ou hash do arquivo invalidos")
        if not isinstance(rows,list) or not (1<=len(rows)<=10000) or not 1<=original<=20000:
            raise DailyStockError(400,"Quantidade de linhas invalida")
        seen=set()
        for r in rows:
            if not isinstance(r,dict): raise DailyStockError(400,"Registro invalido")
            mat=str(r.get("material",""))
            desc=str(r.get("descricao_material",""))
            qty=str(r.get("quantidade_livre",""))
            if not re.fullmatch(r"[0-9]{1,32}",mat) or not (1<=len(desc)<=500) or not re.fullmatch(r"\d+(?:\.\d{1,3})?",qty):
                raise DailyStockError(400,"Colunas de material invalidas")
            if mat in seen: raise DailyStockError(400,"Material duplicado no lote")
            seen.add(mat)
        value=self._call("rpc/registrar_estoque_diario",method="POST",body={
            "p_data":data,"p_arquivo":filename,"p_hash":digest,
            "p_linhas":original,"p_itens":rows,"p_operador":actor
        })
        if not isinstance(value,dict) or value.get("ok") is not True:
            raise DailyStockError(502,"Resposta de importacao nao confirmada")
        return value
