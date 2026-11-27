"""Miscelâneas: verificação analítica de consultas já gravadas no Dominium."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from imperium_supabase_live import LiveSyncError, RUN_PATTERN, SupabasePeriodStore
from material_stock_audit import name_key, parse_time
from technician_stock_snapshots import PORTS, material_code, now, quantity
from used_equipment_report import normalize_range

ROOT = "/api/stock/analyses/misc"
CITY = "(natal|fortaleza|mossoro|recife)"
DATE = r"\d{4}-\d{2}-\d{2}"
LOG = logging.getLogger(__name__)


def route_for(method, target):
    if method == "POST" and target in (ROOT + "/rules", ROOT + "/missing"):
        return target.rsplit("/", 1)[1], ()
    if method == "GET":
        matched = re.fullmatch(
            rf"{ROOT}\?city={CITY}&start=({DATE})&end=({DATE})(?:&run=({RUN_PATTERN}))?", target
        )
        if matched:
            return "report", matched.groups()
    return None


def clean_text(value, limit=140):
    return " ".join(str(value if value is not None else "").split())[:limit]


def identifier(value):
    text = clean_text(value, 100)
    return text if re.fullmatch(r"[0-9A-Za-z_-]{1,40}", text) else ""


def limit_rule(value):
    # Same meaning as the existing quality catalog: bare number is inclusive.
    text = name_key(value)
    expr = re.fullmatch(r"(MENOR QUE\s+|<\s*|<=\s*)?(\d{1,12}(?:[.,]\d{1,6})?)", text)
    if not expr:
        return None, None
    return ("lt" if (expr[1] or "").strip() in {"MENOR QUE", "<"} else "le"), quantity(expr[2])


def code_rules(items):
    return {name_key(rule["service"]): rule["codes"] for rule in items if rule["codes"]}


def analyze_usage(raw_rows, limits, service_rules):
    """Aggregate by OS and material before evaluating a quantity limit."""
    quality = defaultdict(set)
    for row in limits:
        try:
            code = material_code(row.get("material"))
        except ValueError:
            continue
        value = clean_text(row.get("qtd_controle_qualidade"), 64)
        if value:
            quality[code].add(value)
    allowed_by_service = code_rules(service_rules)
    groups = defaultdict(list)
    untreated = 0
    for source in raw_rows:
        if clean_text(source.get("SerialNumber")) or clean_text(source.get("Identificado")).upper() == "S":
            continue
        order = identifier(source.get("NumOs"))
        wo = identifier(source.get("NumeroWO")) if not order else ""
        os = order or ("WO " + wo if wo else "")
        try:
            code = material_code(source.get("CodigoEquipamento"))
        except ValueError:
            code = ""
        if not os or not code:
            untreated += 1
            continue
        closed = parse_time(source.get("DataBaixa"))
        posted = parse_time(source.get("DataBaixaMiscelanea"))
        service = clean_text(source.get("CodigoServico"))
        allowed = allowed_by_service.get(name_key(service), [])
        try:
            value = quantity(source.get("Qtd"))
            if value < 0 or value > 10**12:
                value = None
        except ValueError:
            value = None
        groups[os, code].append({
            "contract": clean_text(source.get("Contrato"), 40),
            "material": clean_text(source.get("Equipamento")),
            "technician": clean_text(source.get("NomeAbreviado")),
            "controller": clean_text(source.get("Controlador")),
            "service": service,
            "unit": name_key(clean_text(source.get("Unidade") or source.get("UnidadeMedida"), 24)),
            "closedDay": closed.date().isoformat() if closed else "",
            "postedAt": posted.isoformat() if posted else "",
            "quantity": value,
            "codeCheck": ("allowed" if code in allowed else "different") if allowed else "no_rule",
        })

    items = []
    for (os, code), rows in groups.items():
        rules = quality.get(code, set())
        rule = next(iter(rules)) if len(rules) == 1 else ""
        op, maximum = limit_rule(rule)
        units = {row["unit"] for row in rows if row["unit"]}
        has_invalid = any(row["quantity"] is None for row in rows) or len(units) > 1
        total = None if has_invalid else sum(row["quantity"] for row in rows)
        if has_invalid or len(rules) > 1 or (rule and maximum is None):
            check = "review"
        elif maximum is None:
            check = "no_rule"
        else:
            excess = total >= maximum if op == "lt" else total > maximum
            check = "above" if excess else "within"
        for row in rows:
            if row["quantity"] is not None:
                row["quantity"] = format(row["quantity"], "f")
        items.append({
            "os": os, "code": code, "material": rows[0]["material"], "quantity": format(total, "f") if total is not None else None,
            "unit": next(iter(units)) if len(units) == 1 else "", "limit": rule,
            "quantityCheck": check, "rows": rows,
        })
    items.sort(key=lambda item: (item["quantityCheck"] != "above", item["os"], item["code"]))
    return items, untreated


class MiscDashboard:
    def __init__(self, connect, repository_factory=SupabasePeriodStore):
        self.connect = connect
        self.repository_factory = repository_factory
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS misc_service_rules (
                    city TEXT NOT NULL, service_key TEXT NOT NULL, service TEXT NOT NULL,
                    codes TEXT NOT NULL, revision INTEGER NOT NULL, actor TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY(city, service_key, revision)
                );
                CREATE TABLE IF NOT EXISTS misc_missing_reports (
                    city TEXT NOT NULL, day TEXT NOT NULL, version INTEGER NOT NULL,
                    filename TEXT NOT NULL, digest TEXT NOT NULL, records TEXT NOT NULL,
                    date_basis TEXT NOT NULL,
                    actor TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(city, day, version)
                );
            """)

    def service_rules(self, city):
        with self.connect() as db:
            rows = db.execute("""
                SELECT service, codes, revision FROM misc_service_rules AS r
                WHERE city=? AND revision=(SELECT max(revision) FROM misc_service_rules
                    WHERE city=r.city AND service_key=r.service_key)
                ORDER BY service_key
            """, (city,)).fetchall()
        return [{"service": row["service"], "codes": json.loads(row["codes"]),
                 "revision": row["revision"]} for row in rows]

    def save_rule(self, city, body, actor):
        service = clean_text(body.get("service"))
        raw = body.get("codes")
        expected = body.get("revision")
        if not service or not isinstance(raw, list) or len(raw) > 100 or type(expected) is not int or expected < 0:
            raise ValueError("Informe o código do serviço e a lista de materiais.")
        codes = sorted({material_code(code) for code in raw})
        key = name_key(service)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("""
                SELECT revision FROM misc_service_rules WHERE city=? AND service_key=?
                ORDER BY revision DESC LIMIT 1
            """, (city, key)).fetchone()
            revision = previous["revision"] if previous else 0
            if revision != expected:
                raise LiveSyncError(409, "rule_conflict", "Regra alterada em outra sessão. Atualize a análise.")
            db.execute("INSERT INTO misc_service_rules VALUES(?,?,?,?,?,?,?)",
                       (city, key, service, json.dumps(codes), revision + 1, actor, timestamp()))
        return {"service": service, "codes": codes, "revision": revision + 1}

    def save_missing(self, city, body, actor):
        day = body.get("day")
        normalize_range(day, day, today=now().date())
        filename = clean_text(body.get("filename"), 180)
        raw = body.get("records")
        expected = body.get("version")
        date_basis = body.get("dateBasis")
        if (not filename.lower().endswith(".xlsx") or not isinstance(raw, list) or len(raw) > 5000
            or type(expected) is not int or expected < 0 or date_basis not in ("scheduled", "execution")):
            raise ValueError("Informe um XLSX de OS sem miscelâneas e sua data.")
        records = {}
        for row in raw:
            if not isinstance(row, dict) or not (os := identifier(row.get("os"))):
                raise ValueError("Há linhas sem uma OS válida no relatório.")
            item = {"os": os, "day": day, "dateBasis": date_basis, **{k: clean_text(row.get(k)) for k in
                    ("contract", "service", "technician", "controller")}}
            if os in records and records[os] != item:
                raise ValueError("A mesma OS aparece com dados diferentes na planilha.")
            records[os] = item
        serialized = json.dumps([records[key] for key in sorted(records)], ensure_ascii=False)
        digest = hashlib.sha256((date_basis + serialized).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("""
                SELECT version, digest FROM misc_missing_reports WHERE city=? AND day=?
                ORDER BY version DESC LIMIT 1
            """, (city, day)).fetchone()
            version = previous["version"] if previous else 0
            if previous and previous["digest"] == digest:
                return {"version": version, "count": len(records), "reused": True}
            if version != expected:
                raise LiveSyncError(409, "missing_conflict", "Relatório alterado em outra sessão. Atualize a análise.")
            db.execute("INSERT INTO misc_missing_reports VALUES(?,?,?,?,?,?,?,?,?)",
                       (city, day, version + 1, filename, digest, serialized, date_basis, actor, timestamp()))
        return {"version": version + 1, "count": len(records), "reused": False}

    def missing_reports(self, city, start, end):
        reports, records = [], []
        with self.connect() as db:
            rows = db.execute("""
                SELECT day, version, filename, date_basis, created_at, records FROM misc_missing_reports AS r
                WHERE city=? AND day BETWEEN ? AND ?
                AND version=(SELECT max(version) FROM misc_missing_reports WHERE city=r.city AND day=r.day)
                ORDER BY day
            """, (city, start, end)).fetchall()
        for row in rows:
            more = json.loads(row["records"])
            records.extend(more)
            reports.append({**{k: row[k] for k in ("day", "version", "filename", "created_at")},
                            "dateBasis": row["date_basis"], "count": len(more)})
        return reports, records

    def handle(self, action, args, actor, body):
        try:
            if action == "report":
                city, start, end, run = args
                first, last = normalize_range(start, end, today=now().date())
                rules = self.service_rules(city)
                reports, missing = self.missing_reports(city, start, end)
                dashboard = {"ok": True, "city": city, "start": start, "end": end,
                             "periodDays": (last - first).days + 1, "rules": rules,
                             "missingReports": reports, "missing": missing,
                             "usage": None, "items": [], "untreated": 0}
                if run:
                    repository = self.repository_factory()
                    meta, rows = repository.read_category(run, city, "por_os", start, end)
                    dashboard["usage"] = meta
                    dashboard["items"], dashboard["untreated"] = analyze_usage(
                        rows, repository.quality_limits(), rules,
                    )
                return 200, dashboard, None
            if not isinstance(body, dict) or body.get("city") not in PORTS:
                raise ValueError("Selecione uma base.")
            city = body["city"]
            saved = self.save_rule(city, body, actor) if action == "rules" else self.save_missing(city, body, actor)
            return 200, {"ok": True, **saved}, None
        except LiveSyncError as error:
            return error.status, {"ok": False, "code": error.code, "error": str(error)}, None
        except ValueError as error:
            return 400, {"ok": False, "error": str(error)}, None
        except Exception as error:
            LOG.warning("Falha no dashboard de miscelâneas: %s", type(error).__name__)
            return 503, {"ok": False, "error": "Dashboard de miscelâneas indisponível."}, None


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
