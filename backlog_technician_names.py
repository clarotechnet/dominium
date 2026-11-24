"""Display enrichment for the read-only backlog comparison; no operational writes."""
from __future__ import annotations

import re


def enrich_comparison(payload: dict, directory) -> dict:
    """Retain the route login and use name (login) for existing report clients."""
    rows = []
    for source in payload.get("rows", []):
        row = dict(source)
        login = str(row.get("technician_login") or row.get("technician") or "").strip()
        if directory is not None and re.fullmatch(r"Z[0-9]+", login, re.IGNORECASE):
            technician = directory.resolve(login)
            if technician and str(technician.get("login", "")).upper() == login.upper():
                name = str(technician.get("name") or "").strip()
                if name:
                    row.update(technician_login=login.upper(), technician_name=name,
                               technician=f"{name} ({login.upper()})")
        rows.append(row)
    return {**payload, "rows": rows}
