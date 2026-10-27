"""Regras de controle de qualidade, independentes do saldo do Imperium.

A tabela Supabase e acessada somente pelo backend com chave de servidor;
nunca enviar SUPABASE_SECRET_KEY ao navegador.
"""
from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache

TABLE = "controle_qualidade_materiais"
COLUMNS = "id,material,descricao_material,qtd_controle_qualidade,atualizado_em,atualizado_por"


def validate_quality_item(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("Dados de controle de qualidade invalidos")
    material = str(raw.get("material") or "").strip()
    descricao = " ".join(str(raw.get("descricao_material") or "").split())
    regra = str(raw.get("qtd_controle_qualidade") if raw.get("qtd_controle_qualidade") is not None else "").strip()
    if not material or len(material) > 32 or not all(ch.isalnum() or ch in "-_./" for ch in material):
        raise ValueError("Informe um codigo de material valido (ate 32 caracteres)")
    if not descricao or len(descricao) > 500:
        raise ValueError("Informe a descricao do material (ate 500 caracteres)")
    if not regra or len(regra) > 64:
        raise ValueError("Informe a regra ou quantidade de controle de qualidade (ate 64 caracteres)")
    return {
        "material": material,
        "descricao_material": descricao,
        "qtd_controle_qualidade": regra,
    }


class QualityControlStore:
    def __init__(self, client):
        self.client = client

    def list_items(self) -> list[dict]:
        result = []
        page_size = 500
        while True:
            response = (
                self.client.table(TABLE).select(COLUMNS)
                .order("descricao_material").range(len(result), len(result) + page_size - 1)
                .execute()
            )
            chunk = response.data or []
            result.extend(dict(row) for row in chunk)
            if len(chunk) < page_size:
                break
        return result

    def save_item(self, raw: object, *, user: str) -> dict:
        item = validate_quality_item(raw)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        item.update({"atualizado_em": now, "atualizado_por": str(user)[:100]})
        raw_id = raw.get("id")
        query = self.client.table(TABLE)
        if raw_id is not None and raw_id != "":
            try:
                row_id = int(raw_id)
                if row_id <= 0:
                    raise ValueError()
            except (TypeError, ValueError) as exc:
                raise ValueError("Registro de controle de qualidade invalido") from exc
            response = query.update(item).eq("id", row_id).execute()
        else:
            response = query.insert(item).execute()
        rows = response.data or []
        if not rows:
            raise ValueError("Registro nao encontrado para atualizacao")
        return dict(rows[0])


@lru_cache(maxsize=1)
def get_quality_control_store() -> QualityControlStore:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url.startswith("https://") or not key:
        raise RuntimeError("A conexao Supabase do controle de qualidade nao esta configurada")
    from supabase import create_client
    try:
        from supabase.lib.client_options import SyncClientOptions as ClientOptions
    except ImportError:
        from supabase.lib.client_options import ClientOptions
    client = create_client(url, key, options=ClientOptions(auto_refresh_token=False, persist_session=False))
    return QualityControlStore(client)
