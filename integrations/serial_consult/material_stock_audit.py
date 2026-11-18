"""Compare Imperium material entries against dated operational and SAP balances."""
from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Lock

from imperium_supabase_live import ALLOWED_PROFILES, SupabasePeriodStore, prepare_snapshot
from order_reports import CREDENTIALS
from technician_stock_snapshots import BRAZIL, PORTS, material_code, quantity
from used_equipment_live_datasnap import fetch_read_only

ROOT = "/api/stock/analyses/material-audit"
LOGGER = logging.getLogger(__name__)
ZERO = Decimal(0)


def route_for(method, target):
    if method == "POST" and target in (ROOT + "/capture", ROOT + "/verify"):
        return target.rsplit("/", 1)[1], None
    if method == "GET":
        match = re.fullmatch(re.escape(ROOT) + r"\?city=(natal|fortaleza|mossoro|recife)", target)
        if match:
            return "status", match[1]
    return None


def sap_day(day, store=None):
    store = store or SupabasePeriodStore()
    imports = store.call("estoque_diario_importacoes", query={
        "select": "id,data_estoque,nome_arquivo,materiais_distintos",
        "data_estoque": "eq." + day,
        "order": "importado_em.desc,id.desc",
        "limit": "1",
    })
    if not imports:
        return None, {}
    entry = imports[0]
    items = {}
    total = int(entry["materiais_distintos"])
    for offset in range(0, total, 500):
        page = store.call("estoque_diario_itens", query={
            "select": "material,quantidade_livre",
            "importacao_id": "eq." + entry["id"],
            "order": "material.asc",
            "offset": str(offset), "limit": "500",
        })
        for item in page:
            items[material_code(item["material"])] = quantity(item["quantidade_livre"])
    if len(items) != total:
        raise ValueError("Importação SAP incompleta")
    return entry, items


def name_key(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).upper().split())


def parse_time(value):
    if not value or len(str(value)) <= 10:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=BRAZIL)).astimezone(BRAZIL)


def location_balances(location):
    balances = defaultdict(Decimal)
    units = defaultdict(set)
    for item in location["inventory"]:
        code = item["code"]
        balances[code] += quantity(item["quantity"])
        if item["unit"]:
            units[code].add(item["unit"])
    return balances, units


def check_company(company_entry, balances, code, amount):
    if company_entry is None or code is None or amount is None:
        return "sem_referencia", None
    if code not in balances:
        return "codigo_ausente", None
    balance = balances[code]
    return ("conferiu" if balance >= amount else "saldo_insuficiente"), balance


def audit_rows(day, movements, opening, closing, company_entry, company_balances):
    locations_by_name = defaultdict(set)
    locations = {}
    balances = {}
    newer = {place["stock_id"]: location_balances(place)[0] for place in closing}
    for place in opening:
        stock = place["stock_id"]
        locations[stock] = place
        balances[stock] = location_balances(place)
        for name in (place["technician_name"], place["stock_name"]):
            if name_key(name):
                locations_by_name[name_key(name)].add(stock)

    entries = []
    skipped_other_day = 0
    for row in movements:
        # Serialized equipment has its own reconciliation flow.
        if str(row.get("SerialNumber") or "").strip() or str(row.get("Identificado") or "").strip().upper() == "S":
            continue
        moment = parse_time(row.get("DataBaixaMiscelanea"))
        if moment and moment.date().isoformat() != day:
            skipped_other_day += 1
            continue
        try:
            code = material_code(row.get("CodigoEquipamento"))
            amount = quantity(row.get("Qtd"))
            if amount <= 0:
                amount = None
        except ValueError:
            code = amount = None
        sap_source = str(row.get("CodParceiraSAP") or "").strip()
        try:
            sap_code = material_code(sap_source) if sap_source else code
        except ValueError:
            sap_code = None
        name = str(row.get("NomeAbreviado") or "").strip()
        matches = locations_by_name.get(name_key(name), set())
        stock = next(iter(matches)) if len(matches) == 1 else None
        entries.append((moment, stock, name, code, sap_code, amount, row))

    entries.sort(key=lambda item: item[0] or datetime.max.replace(tzinfo=BRAZIL))
    ties = Counter((moment, stock, code) for moment, stock, _, code, _, amount, _ in entries if amount is not None)
    loaded = defaultdict(Decimal)
    result = []
    for moment, stock, name, code, sap_code, amount, row in entries:
        place = locations.get(stock)
        initial, units = balances.get(stock, ({}, {}))
        before, excess = None, None
        key = (stock, code)
        if place is None:
            status = "local_sem_vinculo"
        elif code is None or amount is None:
            status = "dados_incompletos"
        elif moment is None:
            status = "data_sem_confirmacao"
        elif moment < parse_time(place["captured_at"]):
            status = "anterior_ao_estoque_salvo"
        elif len(units.get(code, ())) > 1:
            status = "unidade_ambigua"
        elif ties[moment, stock, code] > 1:
            status = "ordem_sem_confirmacao"
            loaded[key] += amount
        else:
            before = initial.get(code, ZERO) - loaded[key]
            excess = max(ZERO, amount - max(ZERO, before))
            status = ("codigo_ausente" if code not in initial else
                      "saldo_insuficiente" if excess else "conferiu")
            loaded[key] += amount
        company_status, company_balance = check_company(company_entry, company_balances, sap_code,
                                                       amount if moment else None)
        current = newer.get(stock, {}).get(code, ZERO) if stock in newer and code else None
        result.append({
            "os": str(row.get("NumOs") or row.get("NumeroWO") or ""),
            "technician": place["technician_name"] if place else name,
            "stock_id": stock,
            "material": code,
            "sap_material": sap_code,
            "description": str(row.get("Equipamento") or ""),
            "posted_at": moment.isoformat() if moment else None,
            "quantity": amount,
            "unit": next(iter(units[code])) if code in units and len(units[code]) == 1 else None,
            "opening_balance": initial.get(code, ZERO) if stock is not None and code else None,
            "balance_before": before,
            "current_balance": current,
            "balance_change": current - initial.get(code, ZERO) if current is not None else None,
            "excess": excess,
            "company_balance": company_balance,
            "technician_check": status,
            "company_check": company_status,
        })

    ranking = {}
    known = {"conferiu", "codigo_ausente", "saldo_insuficiente"}
    for item in result:
        if item["stock_id"] is None or not item["os"]:
            continue
        tech = ranking.setdefault(item["stock_id"], {
            "technician": item["technician"], "checked": set(), "divergent": set(),
        })
        checks = (item["technician_check"], item["company_check"])
        if checks[0] in known:
            tech["checked"].add(item["os"])
        if checks[0] in known - {"conferiu"}:
            tech["divergent"].add(item["os"])
    leaders = [{
        "technician": tech["technician"], "checked": len(tech["checked"]),
        "divergent": len(tech["divergent"]),
    } for tech in ranking.values() if tech["checked"]]
    leaders.sort(key=lambda r: (-r["divergent"], -r["divergent"]/r["checked"], r["technician"]))
    for row in result:
        for k, value in row.items():
            if isinstance(value, Decimal):
                row[k] = format(value, "f")
    return {
        "day": day, "company": company_entry, "rows": result, "ranking": leaders,
        "skipped_other_day": skipped_other_day,
    }


class MaterialStockAudit:
    def __init__(self, snapshots, *, fetch=fetch_read_only, company=sap_day):
        self.snapshots = snapshots
        self.fetch = fetch
        self.company = company
        self.busy = Lock()

    def handle(self, action, city, actor, body):
        if action != "status":
            if not isinstance(body, dict) or set(body) != {"city"}:
                return 400, {"ok": False, "error": "Selecione uma cidade"}, None
            city = body["city"]
            if not isinstance(city, str) or city not in PORTS:
                return 400, {"ok": False, "error": "Selecione uma cidade"}, None
        today = self.snapshots.clock().date()
        yesterday = (today - timedelta(days=1)).isoformat()
        try:
            if action == "status":
                return 200, {
                    "ok": True, "date": today.isoformat(), "reference_date": yesterday,
                    "today": self.snapshots.status(city, today.isoformat()),
                    "yesterday": self.snapshots.status(city, yesterday),
                }, None
            if action == "capture":
                return 202, {"ok": True, "capture": self.snapshots.start(city, actor)}, None
            # The SAP Excel history is global. Use it first in the Natal pilot.
            if city != "natal":
                return 409, {"ok": False, "error": "Vistoria disponível inicialmente em Natal/Parnamirim."}, None
            opening = self.snapshots.saved_locations(city, yesterday)
            if not opening:
                return 409, {"ok": False, "error": "Falta o estoque dos técnicos salvo para " + yesterday}, None
            closing = self.snapshots.saved_locations(city, today.isoformat())
            if not closing:
                return 202, {"ok": True, "capture": self.snapshots.start(city, actor)}, None
            if not self.busy.acquire(blocking=False):
                return 409, {"ok": False, "error": "Já existe uma vistoria em andamento."}, None
            try:
                company, balances = self.company(yesterday)
                raw = self.fetch(yesterday, yesterday, profile=city,
                                 partner_id=ALLOWED_PROFILES[city], credential_path=CREDENTIALS)
                movements, _, _ = prepare_snapshot(raw, city)
                report = audit_rows(yesterday, movements["por_os"], opening, closing, company, balances)
            finally:
                self.busy.release()
            return 200, {"ok": True, "report": report}, None
        except Exception as exc:
            LOGGER.warning("Material stock audit unavailable: %s", type(exc).__name__)
            return 502, {"ok": False, "error": "Dados da vistoria indisponíveis. Tente novamente."}, None
