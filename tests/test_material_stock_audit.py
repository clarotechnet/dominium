from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))

from material_stock_audit import MaterialStockAudit, audit_rows, sap_day
from technician_stock_snapshots import TechnicianStockSnapshots, operational_stock_client

OPENED = datetime.fromisoformat("2026-11-18T06:00:00-03:00")
CLOSED = datetime.fromisoformat("2026-11-19T06:00:00-03:00")
OWNER = {"stock_id": 21, "installer_id": 41, "stock_name": "Equipe 21", "technician_name": "João Lima"}


class StockSource:
    def list_stock_technicians(self):
        return [OWNER]

    def technician_stocks(self, stock_ids):
        self.requested = stock_ids
        return [{"ok": True, "technician": OWNER, "items": [{
            "code": "0022026219", "equipment": "Cabo", "quantity": "127", "unit": "M",
        }]}]


def writeoff(os, qty, hour, **extra):
    return {"NumOs": os, "Qtd": qty, "DataBaixaMiscelanea": f"2026-11-18T{hour}:00:00",
            "NomeAbreviado": "JOAO LIMA", "CodigoEquipamento": "22026219", **extra}


class MaterialStockAuditTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.clock = OPENED
        self.source = StockSource()
        self.snapshots = TechnicianStockSnapshots(
            folder.name, client_factory=lambda city: self.source, clock=lambda: self.clock,
        )

    def test_snapshot_client_supports_the_operational_runtime_constructor(self):
        class OperationalImperiumAPI:
            def __init__(self, root, *, port, company, profile_key):
                self.scope = port, company, profile_key

        with patch("imperium_api.ImperiumAPI", OperationalImperiumAPI):
            client = operational_stock_client("natal")
        self.assertEqual(client.scope, (212, "natal", "natal"))

    def test_snapshot_is_versioned_by_day_and_never_replaces_opening_balance(self):
        first = self.snapshots.start("natal", "user-1", background=False)
        self.assertEqual(first["state"], "complete")
        self.assertEqual(first["collected"], 1)
        self.assertEqual(self.source.requested, [21])
        self.assertEqual(self.snapshots.start("natal", "user-2", background=False)["id"], first["id"])
        self.assertIsNone(self.snapshots.status("recife", first["day"]))
        saved = self.snapshots.saved_locations("natal", first["day"])
        self.assertEqual(saved[0]["inventory"][0]["quantity"], "127")
        self.assertEqual(saved[0]["inventory"][0]["code"], "22026219")
        self.clock = CLOSED
        current = self.snapshots.start("natal", "user-1", background=False)
        self.assertNotEqual(current["id"], first["id"])

    def test_partial_capture_cannot_be_used_as_stock(self):
        self.source.technician_stocks = lambda ids: []
        failed = self.snapshots.start("natal", "user-1", background=False)
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(self.snapshots.saved_locations("natal", failed["day"]), [])
        self.source.technician_stocks = StockSource().technician_stocks
        self.assertEqual(self.snapshots.start("natal", "user-1", background=False)["state"], "complete")

    def test_running_balance_and_independent_company_checks(self):
        self.snapshots.start("natal", "user-1", background=False)
        opening = self.snapshots.saved_locations("natal", "2026-11-18")
        closing = [dict(opening[0], inventory=[])]
        wrong = dict(writeoff("003", 5, "14"), CodigoEquipamento="22026218")
        rows = [writeoff("002", 60, "13"), wrong, writeoff("001", 80, "08"),
                writeoff("000", 10, "05"), writeoff("004", 3, "14", SerialNumber="AB123")]
        result = audit_rows("2026-11-18", rows, opening, closing,
                            {"id": "sap"}, {"22026219": Decimal(250), "22026218": Decimal(10)})
        first, second, third, fourth = result["rows"]
        self.assertEqual(first["technician_check"], "anterior_ao_estoque_salvo")
        self.assertEqual(second["balance_before"], "127")
        self.assertEqual(third["balance_before"], "47")
        self.assertEqual(third["excess"], "13")
        self.assertEqual(third["balance_change"], "-127")
        self.assertEqual(third["technician_check"], "saldo_insuficiente")
        self.assertEqual(fourth["technician_check"], "codigo_ausente")
        self.assertEqual(fourth["company_check"], "conferiu")
        self.assertEqual(result["ranking"], [{"technician": "João Lima", "checked": 3, "divergent": 2}])

    def test_only_sap_import_for_reference_date_is_requested(self):
        class Company:
            def call(self, table, *, query):
                if table == "estoque_diario_importacoes":
                    self.day = query["data_estoque"]
                    return [{"id": "day-import", "materiais_distintos": 1}]
                assert query["importacao_id"] == "eq.day-import"
                return [{"material": "0022026219", "quantidade_livre": 100}]
        company = Company()
        _, balances = sap_day("2026-11-18", company)
        self.assertEqual(company.day, "eq.2026-11-18")
        self.assertEqual(balances, {"22026219": Decimal(100)})

    def test_verify_uses_only_yesterday_and_preserves_missing_company_reference(self):
        self.snapshots.start("natal", "user-1", background=False)
        self.clock = CLOSED
        self.snapshots.start("natal", "user-1", background=False)
        day_rows = [{"Cidade": "NATAL", **writeoff("100", 140, "08")}]
        def report(start, end, **kwargs):
            self.assertEqual((start, end, kwargs["profile"]), ("2026-11-18", "2026-11-18", "natal"))
            return {"por_os": day_rows, "consolidado": []}
        service = MaterialStockAudit(self.snapshots, fetch=report, company=lambda day: (None, {}))
        status, result, _ = service.handle("verify", None, "user-1", {"city": "natal"})
        self.assertEqual(status, 200)
        row = result["report"]["rows"][0]
        self.assertEqual(row["excess"], "13")
        self.assertEqual(row["company_check"], "sem_referencia")
