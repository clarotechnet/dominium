import datetime as dt
import unittest
from types import SimpleNamespace

from adhesion_technician_evidence import AdhesionTechnicianEvidence, matches_imported_unproductive_alias


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

    def test_signed_unproductive_alias_uses_installer_id_and_exact_order(self):
        approved = self.result()["results"][0]["imperium_matches"][0]
        approved.update(
            approved_state_hash="validated",
            technician_login="Z657807",
            technician="ESLI MELQUISEDEQUE DA SILVA",
        )
        supplied = {"login": "Z657807", "name": "NOME EXIBIDO DIVERGENTE"}

        def match(row=approved, installer_id=338736, tech=supplied, date=self.date, profile="natal"):
            return matches_imported_unproductive_alias(
                profile, self.order, date, tech, installer_id, "ESLI MELQUISEDEQUI D", row,
            )

        self.assertTrue(match())
        self.assertFalse(match(installer_id=20))
        self.assertFalse(match(tech={"login": "Z131558"}))
        self.assertFalse(match(row={**approved, "num_os": "2662222223"}))
        self.assertFalse(match(row={**approved, "approved_state_hash": ""}))
        self.assertFalse(match(date=dt.date(2026, 11, 26)))
        self.assertFalse(match(profile="recife"))

    def test_conflicting_active_login_remains_in_review(self):
        self.reader.record("natal", self.result())
        self.reader.record("natal", self.result("222222", "Outra Técnica"))
        self.assertFalse(self.matches())

    def test_accepts_verified_stock_spelling_only_for_the_bound_installer(self):
        self.assigned.update(name="ESLI MELQUISEDEQUE DA SILVA", external_id="Z657807")
        self.reader.record("natal", self.result())
        roster = [{"installer_id": 338736, "technician_name": "ESLI MELQUISEDEQUI DA SILVA"}]
        self.assertTrue(self.reader.matches("natal", self.order, self.date, self.assigned, 338736, lambda: roster))
        self.assertFalse(self.reader.matches("natal", self.order, self.date, self.assigned, 20,
                                             lambda: [{**roster[0], "installer_id": 20}]))
        roster.append({**roster[0], "technician_name": "OUTRA PESSOA"})
        self.assertFalse(self.reader.matches("natal", self.order, self.date, self.assigned, 338736, lambda: roster))

    def test_records_unproductive_task_with_code_and_no_reported_movements(self):
        result = self.result()
        capture = result["results"][0]
        capture.update(installed_equipment=[], removed_equipment=[], materials=[])
        task = capture["tasks"][0]
        task.update(status="N", close_code="312")
        self.reader.record("natal", result)
        self.assertTrue(self.matches())
        for field in ("installed_equipment", "removed_equipment", "materials"):
            capture[field] = [{}]
            self.reader.record("natal", result)
            self.assertFalse(self.matches())
            capture[field] = []
        task.pop("close_code")
        self.reader.record("natal", result)
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
