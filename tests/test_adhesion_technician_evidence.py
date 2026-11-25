import datetime as dt
import unittest
from types import SimpleNamespace

from adhesion_technician_evidence import AdhesionTechnicianEvidence


class AdhesionTechnicianEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 10
        self.reader = AdhesionTechnicianEvidence(clock=lambda: self.now)
        self.date = dt.date(2026, 11, 25)
        self.order = SimpleNamespace(contract="111111", num_os="2662222222", id_os=123)
        self.assigned = {"id": "50", "external_id": "Z123456", "name": "Maria Teste Técnica"}

    def result(self, contract="111111", name=None):
        return {
            "source": "toa_secondary_chrome_cdp", "contract": contract,
            "results": [{
                "contract": contract, "aid": "321", "route_name": "NTL-DMV",
                "scheduled_date": self.date.isoformat(), "activity_status": "complete",
                "route_provider": {"id": "50"},
                "assigned_technician": {**self.assigned, "name": name or self.assigned["name"]},
                "tasks": [{"os_number": self.order.num_os, "status": "E"}],
                "imperium_matches": [{
                    "id_os": self.order.id_os, "contract": contract, "num_os": self.order.num_os,
                    "operation_source": "toa_import",
                    "operation_identity": {"profile_key": "natal", "contract": contract, "activity_id": "321"},
                    "import_scope": {"source_file": "Atividades-NTL-DMV_25_11_26.csv",
                                     "expected_profile_key": "natal", "source_hash": "fixture"},
                }],
            }],
        }

    def matches(self, installer_name="MARIA TESTE TECNICA", supplied=None):
        return self.reader.matches("natal", self.order, self.date, supplied or self.assigned, 20,
                                   lambda: [{"installer_id": 20, "technician_name": installer_name}])

    def test_uses_live_toa_login_only_with_exact_imperium_installer(self):
        self.reader.record("natal", self.result())
        self.assertTrue(self.matches())
        self.assertFalse(self.matches("OUTRA PESSOA"))
        self.assertFalse(self.matches(supplied={**self.assigned, "external_id": "Z123455"}))
        self.now += 301
        self.assertFalse(self.matches())

    def test_conflicting_active_login_remains_in_review(self):
        self.reader.record("natal", self.result())
        self.reader.record("natal", self.result("222222", "Outra Técnica"))
        self.assertFalse(self.matches())

    def test_ignores_cached_or_unscoped_evidence(self):
        cached = {**self.result(), "source": "productive_cache"}
        self.reader.record("natal", cached)
        self.assertFalse(self.matches())
        wrong = self.result()
        wrong["results"][0]["route_name"] = "NTL-DMV_ADM"
        self.reader.record("natal", wrong)
        self.assertFalse(self.matches())

    def test_drops_old_evidence_after_an_inconclusive_live_lookup(self):
        self.reader.record("natal", self.result())
        refreshed = self.result()
        refreshed["results"][0]["tasks"][0]["imperium_only"] = True
        self.reader.record("natal", refreshed)
        self.assertFalse(self.matches())
