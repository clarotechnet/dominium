"""Strict status interpretation for daily TOA route treatment.

Pendente means an unfinished activity. A close code alone is insufficient
when status still says pending/in-route/started.
"""
from __future__ import annotations
import re
import unicodedata

IMPRODUCTIVE_CODES = frozenset({"101","106","306","404"})
PRODUCTIVE_CODES = frozenset({"409","430","512"})


def plain(value):
    s=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).upper().strip()


def parsed_close_code(value):
    raw=plain(value)
    match=re.fullmatch(r"([0-9]{3})(?:\s*-\s*.*)?",raw)
    if not match:
        return None
    return match.group(1)


def classify_route_activity(status,raw_code):
    st=plain(status)
    code=parsed_close_code(raw_code)
    completed=st.startswith(("CONCLUID","FINALIZAD","COMPLETED"))
    if not completed:
        if code:
            return "DIVERGENCIA: CODIGO COM STATUS EM ABERTO",code
        if st.startswith("PENDENT"):
            return "PENDENTE",None
        if st.startswith("EM ROTA"):
            return "EM ROTA",None
        if st.startswith("INICIAD"):
            return "INICIADA",None
        if st.startswith("CANCELAD"):
            return "CANCELADA",None
        if st.startswith("SUSPENS"):
            return "SUSPENSA",None
        return "EM ABERTO / STATUS A REVISAR",None
    if not code:
        return "CONCLUIDA SEM CODIGO",None
    if code in IMPRODUCTIVE_CODES:
        return "IMPRODUTIVA CONFIRMADA",code
    if code in PRODUCTIVE_CODES:
        return "PRODUTIVA CONFIRMADA",code
    return "BAIXADA - VALIDAR CODIGO",code
