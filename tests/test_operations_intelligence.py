import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from close_report import CloseReportStore
from operations_intelligence import (
    HealthCheckService,
    audit_serial_assignments,
    build_intelligence_snapshot,
)


class FakeAPI:
    host = "127.0.0.1"

    def __init__(self, *, online=True):
        self.online = online

    def status(self):
        if not self.online:
            raise OSError("sem resposta")
        return {"ok": True}

    def list_stock_technicians(self):
        return [
            {
                "stock_id": 10,
                "stock_name": "ESTOQUE TECNICO A",
                "installer_id": 100,
                "technician_name": "TECNICO A",
            },
            {
                "stock_id": 20,
                "stock_name": "ESTOQUE TECNICO B",
                "installer_id": 200,
                "technician_name": "TECNICO B",
            },
        ]

    def technician_stocks(self, _stock_ids):
        return [
            {
                "technician": self.list_stock_technicians()[0],
                "items": [
                    {
                        "code": "DEC01",
                        "equipment": "DECODER HD",
                        "serials": [{"serial": "SERIAL123", "smart": ""}],
                    }
                ],
            },
            {"technician": self.list_stock_technicians()[1], "items": []},
        ]


class OperationsIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.date = dt.date(2026, 8, 4)

    def profile(self, key="natal", label="NATAL", *, online=True):
        root = Path(self.temporary.name) / key
        store = CloseReportStore(root, key)
        return SimpleNamespace(
            key=key,
            label=label,
            port=212,
            api=FakeAPI(online=online),
            close_report=store,
            cache_lock=__import__("threading").RLock(),
            order_cache={},
            installer_overrides={},
        )

    def test_snapshot_consolidates_bases_and_technicians(self):
        natal = self.profile()
        fortaleza = self.profile("fortaleza", "FORTALEZA")
        confirmed, _ = natal.close_report.begin(
            {
                "id_os": 1,
                "num_os": "1001",
                "contract": "3001",
                "service": "INSTALACAO",
                "technician": "TECNICO A",
                "technician_id": 100,
                "close_code": "409",
            },
            date=self.date,
        )
        natal.close_report.update(
            confirmed["request_id"],
            {
                "state": "confirmed",
                "confirmed_at": confirmed["created_at"],
                "category": "SUCCESS",
                "category_label": "Baixada",
            },
            date=self.date,
        )
        failed, _ = fortaleza.close_report.begin(
            {
                "id_os": 2,
                "num_os": "1002",
                "contract": "3002",
                "service": "RETIRADA",
                "technician": "TECNICO B",
                "technician_id": 200,
                "close_code": "430",
            },
            date=self.date,
        )
        fortaleza.close_report.update(
            failed["request_id"],
            {
                "state": "failed",
                "category": "TIMEOUT",
                "category_label": "Tempo esgotado",
            },
            date=self.date,
        )

        result = build_intelligence_snapshot(
            {"natal": natal, "fortaleza": fortaleza}, self.date, 1
        )

        self.assertEqual(result["summary"]["confirmed"], 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["summary"]["success_rate"], 50.0)
        self.assertEqual(len(result["bases"]), 2)
        self.assertEqual(result["technicians"][0]["technician"], "TECNICO A")
        self.assertEqual(result["failure_categories"][0]["label"], "Tempo esgotado")

    def test_health_check_reports_each_base_without_raising(self):
        service = HealthCheckService(ttl_seconds=60)
        result = service.check(
            {
                "natal": self.profile(),
                "fortaleza": self.profile("fortaleza", "FORTALEZA", online=False),
            },
            fresh=True,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["online"], 1)
        self.assertEqual(result["offline"], 1)
        self.assertTrue(next(item for item in result["bases"] if item["key"] == "natal")["online"])

    def test_serial_audit_flags_owner_different_from_assigned_technician(self):
        capture = SimpleNamespace(
            aid="A1",
            contract="3001",
            assigned_technician={"id": "200", "name": "TECNICO B"},
            installed_equipment=[{"serial": "SERIAL123", "description": "DECODER HD"}],
            tasks=[{"os_number": "1001"}],
            work_type="INSTALACAO",
        )
        with patch("operations_intelligence._latest_captures", return_value=[capture]):
            result = audit_serial_assignments(
                self.profile(), Path(self.temporary.name), self.date
            )

        self.assertEqual(result["summary"]["mismatch"], 1)
        self.assertEqual(result["rows"][0]["owner_technician"], "TECNICO A")
        self.assertEqual(result["rows"][0]["expected_technician"], "TECNICO B")


if __name__ == "__main__":
    unittest.main()
