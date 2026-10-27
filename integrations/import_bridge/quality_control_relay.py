"""Private, authenticated Quality Control Supabase bridge (no Imperium writes)."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TABLE = "controle_qualidade_materiais"
FIELDS = "id,material,descricao_material,qtd_controle_qualidade,atualizado_em,atualizado_por"
MATERIAL_CODE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class QualityControlError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class QualityControlService:
    def __init__(self, env_file: str | None = None):
        path = Path(env_file or os.getenv("DOMINIUM_QUALITY_ENV_FILE") or "C:/DominiumMain/.env")
        values = {}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                values[name.strip()] = value.strip().strip(chr(34)).strip(chr(39))
        url = values.get("SUPABASE_URL", "").rstrip("/")
        key = values.get("SUPABASE_SECRET_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY")
        if url != "https://haqzzxpocwzntyudrbch.supabase.co" or not key:
            raise QualityControlError(503, "Conexao privada Supabase indisponivel")
        self.url = url + "/rest/v1/" + TABLE
        self.key = key

    def _request(self, method: str, *, query: dict | None = None, payload: dict | None = None):
        url = self.url + ("?" + urlencode(query) if query else "")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {
            "apikey": self.key,
            "Authorization": "Bearer " + self.key,
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=18) as response:
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise QualityControlError(502, "Resultado grande demais")
                return json.loads(data or b"[]")
        except HTTPError as exc:
            if exc.code == 409:
                raise QualityControlError(409, "Codigo duplicado ou edicao concorrente; atualize a lista") from None
            raise QualityControlError(502, "Falha ao acessar dados de qualidade") from None
        except (URLError, TimeoutError, ValueError) as exc:
            raise QualityControlError(502, "Supabase temporariamente indisponivel") from exc

    def list_items(self) -> dict:
        rows = self._request("GET", query={"select": FIELDS, "order": "descricao_material.asc", "limit": "1000"})
        if not isinstance(rows, list):
            raise QualityControlError(502, "Formato invalido do Supabase")
        return {"ok": True, "items": rows, "count": len(rows)}

    def save_item(self, raw: dict, actor: str) -> dict:
        if not isinstance(raw, dict):
            raise QualityControlError(400, "Material invalido")
        material = str(raw.get("material") or "").strip()
        desc = " ".join(str(raw.get("descricao_material") or "").split())
        value = str(raw.get("qtd_controle_qualidade") if raw.get("qtd_controle_qualidade") is not None else "").strip()
        if not MATERIAL_CODE.fullmatch(material):
            raise QualityControlError(400, "Codigo do material invalido")
        if not (1 <= len(desc) <= 500 and 1 <= len(value) <= 64):
            raise QualityControlError(400, "Descricao ou regra de quantidade invalida")
        if not actor:
            raise QualityControlError(403, "Operador nao identificado")
        payload = {
            "material": material,
            "descricao_material": desc,
            "qtd_controle_qualidade": value,
            "atualizado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds"),
            "atualizado_por": actor[:100],
        }
        existing = raw.get("id")
        if existing is None or existing == "":
            rows = self._request("POST", payload=payload)
        else:
            if isinstance(existing, bool):
                raise QualityControlError(400, "ID invalido")
            try:
                row_id = int(existing)
            except (ValueError, TypeError) as exc:
                raise QualityControlError(400, "ID invalido") from exc
            if row_id <= 0 or row_id > 9223372036854775807:
                raise QualityControlError(400, "ID invalido")
            query = {"id": "eq." + str(row_id)}
            old_version = raw.get("atualizado_em")
            if old_version:
                old_version = str(old_version)
                if len(old_version) > 64 or not re.fullmatch(r"[0-9T:+.Z-]+", old_version):
                    raise QualityControlError(400, "Versao invalida")
                query["atualizado_em"] = "eq." + old_version
            rows = self._request("PATCH", query=query, payload=payload)
        if not isinstance(rows, list) or len(rows) != 1:
            raise QualityControlError(409, "Registro alterado por outra pessoa ou nao encontrado; atualize a lista")
        return {"ok": True, "item": rows[0]}
