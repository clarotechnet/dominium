# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO DIRETO - infraestrutura comum, sem regra de negocio Imperium.
#
# TOA
# - NAO DIRETO - infraestrutura comum, sem regra de negocio TOA.
#
# DOMINIUM COMPARTILHADO
# - SIM - seguranca, interface, voz, empacotamento ou inicializacao.
#
# Categoria deste arquivo: COMPARTILHADO.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


TEAM_LABELS = {
    "MOSSORO": "Mossoro",
    "FORTALEZA": "Fortaleza",
    "RECIFE": "Recife",
    "VT MANUTENCAO NAO SEI QUE ESTADO E": "VT Manutencao",
    "ADESAO E SERVICO": "Adesao e Servico",
    "MDU": "MDU",
}
TEAM_PROFILES = {
    "Mossoro": "mossoro",
    "Fortaleza": "fortaleza",
    "Recife": "recife",
}


def normalize(value: object) -> str:
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(character)
    ).upper()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in text)
        .split()
    )


def team_label(value: str) -> str:
    normalized = normalize(value)
    if normalized in TEAM_LABELS:
        return TEAM_LABELS[normalized]
    if normalized.startswith("VT MANUTENCAO"):
        return "VT Manutencao"
    return " ".join(value.split())


def import_directory(source: Path, destination: Path) -> dict:
    frame = pd.read_excel(source, sheet_name=0, header=None, dtype=str).fillna("")
    technicians: dict[str, dict] = {}
    current_team = ""
    raw_records = 0

    for values in frame.itertuples(index=False, name=None):
        row = [str(value).strip() for value in values]
        name = row[0] if row else ""
        login = row[1].upper() if len(row) > 1 else ""
        plate = row[4].upper() if len(row) > 4 else ""

        if name and not login and normalize(name) not in {"NOME", "NOMES"}:
            current_team = team_label(name)
            continue
        if not re.fullmatch(r"Z\d+", login, re.IGNORECASE):
            continue

        raw_records += 1
        normalized_name = " ".join(name.split()).upper()
        item = technicians.setdefault(
            login,
            {
                "login": login,
                "name": normalized_name,
                "plate": "",
                "teams": set(),
                "profiles": set(),
            },
        )
        if item["name"] != normalized_name:
            raise ValueError(f"O login {login} possui nomes diferentes na planilha")
        if plate and item["plate"] and item["plate"] != plate:
            raise ValueError(f"O login {login} possui placas diferentes na planilha")
        if plate:
            item["plate"] = plate
        if current_team:
            item["teams"].add(current_team)
            profile = TEAM_PROFILES.get(current_team)
            if profile:
                item["profiles"].add(profile)

    rows = []
    for item in technicians.values():
        rows.append(
            {
                "login": item["login"],
                "name": item["name"],
                "plate": item["plate"],
                "teams": sorted(item["teams"]),
                "profiles": sorted(item["profiles"]),
            }
        )
    rows.sort(key=lambda item: (normalize(item["name"]), item["login"]))

    payload = {
        "version": 1,
        "source": {
            "filename": source.name,
            "imported_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "raw_records": raw_records,
            "duplicates_merged": raw_records - len(rows),
        },
        "technicians": rows,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai somente nome, login, placa e equipe da planilha de tecnicos."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "config" / "technicians.json",
    )
    args = parser.parse_args()
    payload = import_directory(args.source, args.output)
    with_plate = sum(bool(item["plate"]) for item in payload["technicians"])
    print(
        f"Cadastro sanitizado: {len(payload['technicians'])} tecnicos; "
        f"{with_plate} com placa."
    )


if __name__ == "__main__":
    main()
