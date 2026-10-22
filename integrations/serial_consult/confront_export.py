"""CSV exporter for read-only Atlas x Imperium confrontation results."""
from __future__ import annotations

import csv
import io
from collections.abc import Mapping


FIELDS = (
    "Serial", "Situacao", "Motivos", "Alertas", "Estado Atlas", "Localizacao Atlas",
    "Contrato Atlas (historico)", "Data Atlas", "Movimentacoes Imperium",
    "Ultimo destino (nao confirmado)", "Posse atual confirmada",
    "Tecnico (posse confirmada)", "Campos confirmados em confronto",
    "Tipo de localizacao Atlas", "Operacao Atlas",
    "Ultima movimentacao Imperium (historica)", "Data da ultima movimentacao",
)


def _cell(value: object) -> str:
    text = str(value if value is not None else "")
    # Neutralize spreadsheet formula injection from untrusted external fields.
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def confront_csv(report: Mapping) -> str:
    rows = report.get("resultados")
    if not isinstance(rows, list):
        raise ValueError("Relatorio invalido")
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(FIELDS)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Linha invalida")
        atlas = row.get("atlas") or {}
        imperium = row.get("imperium") or {}
        if not isinstance(atlas, dict) or not isinstance(imperium, dict):
            raise ValueError("Fontes invalidas")
        writer.writerow([_cell(x) for x in (
            row.get("serial", ""), row.get("situacao", ""),
            ", ".join(row.get("motivos") or []), ", ".join(row.get("alertas") or []),
            atlas.get("estado"), atlas.get("localizacao"), atlas.get("contrato_historico"),
            atlas.get("ultima_alteracao"), imperium.get("movimentacoes"),
            imperium.get("ultima_localizacao_nao_confirmada"),
            "Sim" if imperium.get("posse_atual_confirmada") is True else "Nao",
            imperium.get("tecnico") if imperium.get("posse_atual_confirmada") is True else "",
            ", ".join(ev.get("campo", "") for ev in row.get("evidencias", []) if isinstance(ev, dict)),
            atlas.get("tipo_localizacao"), atlas.get("operacao"),
            imperium.get("ultima_movimentacao_historica"),
            imperium.get("data_ultima_movimentacao"),
        )])
    return "\ufeff" + out.getvalue()
