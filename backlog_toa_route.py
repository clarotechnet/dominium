"""Read-only capture of the five DMV daily routes using the existing TOA session.

The helper calls GET /toa/buckets and GET /toa/export only. This module never
invokes the Imperium import, DataSnap writes, or OS close endpoints.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

TOA_ROUTES = ("NTL-DMV_ADM", "PWM-DMV_ADM", "FTZ-DMV_ADM",
              "JCR-DMV_ADM", "MRO-DMV")
_FILENAME = re.compile(r"^Atividades-[A-Z0-9_-]+_\d{2}_\d{2}_\d{2}\.(csv|xlsx)$")


class TOADailyRouteExporter:
    def __init__(self, helper: str | Path, *, runner=None):
        self.helper = Path(helper)
        self.runner = runner or subprocess.run

    def _invoke(self, *arguments, timeout=90):
        if not self.helper.is_file():
            raise RuntimeError("Exportador existente do TOA nao encontrado no servidor")
        response = self.runner(
            ["node", str(self.helper), *arguments],
            cwd=str(self.helper.parent),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False)
        if response.returncode:
            raise RuntimeError("Exportacao TOA indisponivel ou sessao expirada")
        try:
            payload = json.loads(response.stdout)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Resposta TOA invalida") from exc
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise RuntimeError("Falha de leitura da sessao TOA")
        return payload

    def fetch(self, day: dt.date, *, guard=None, progress=None):
        if not isinstance(day, dt.date) or day != dt.date.today():
            raise ValueError("Somente a rota da data corrente pode ser capturada")
        if guard:
            guard()
        registry = self._invoke("list", timeout=20)
        available = {str(x.get("name") or "").upper()
                     for x in registry.get("buckets", []) if isinstance(x, dict)}
        missing = [route for route in TOA_ROUTES if route not in available]
        if missing:
            raise RuntimeError("Buckets DMV indisponiveis no TOA: "+", ".join(missing))
        items = []
        for route in TOA_ROUTES:
            if guard:
                guard()
            if progress:
                progress(route, len(items), len(TOA_ROUTES))
            payload = self._invoke("export", route, day.isoformat(), timeout=180)
            result = payload.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("TOA nao retornou arquivo da rota: "+route)
            kind = str(result.get("format") or "").lower()
            if kind == "csv":
                csv_text = result.get("csv")
                if not isinstance(csv_text, str) or not csv_text.strip():
                    raise RuntimeError("CSV da rota vazio: "+route)
                raw = csv_text.encode("utf-8-sig")
            elif kind == "xlsx":
                try:
                    raw = base64.b64decode(result["base64"], validate=True)
                except (ValueError, KeyError, TypeError) as exc:
                    raise RuntimeError("XLSX da rota invalido: "+route) from exc
            else:
                raise RuntimeError("Formato inesperado na rota: "+route)
            if not 0 < len(raw) <= 3*1024*1024:
                raise RuntimeError("Tamanho invalido na rota: "+route)
            filename = f"Atividades-{route}_{day:%d_%m_%y}.{kind}"
            if not _FILENAME.fullmatch(filename):
                raise RuntimeError("Nome TOA invalido")
            items.append({"name": filename, "base64": base64.b64encode(raw).decode("ascii")})
        if progress:
            progress("concluido",len(items),len(TOA_ROUTES))
        return items
