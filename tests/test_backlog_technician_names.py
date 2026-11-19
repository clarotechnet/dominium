import json
import tempfile
import unittest
from pathlib import Path

from backlog_technician_names import enrich_comparison
from technician_directory import TechnicianDirectory


def directory(tmp_path, entries):
    path = tmp_path / "technicians.json"
    path.write_text(json.dumps({"technicians": entries}), encoding="utf-8")
    return TechnicianDirectory(path)


class BacklogTechnicianNameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp_path = Path(self.temp.name)

    def test_known_logins_are_displayed_and_original_payload_is_preserved(self):
        tmp_path = self.tmp_path
        catalog = directory(tmp_path, [{"login": "Z123456", "name": "TECNICO EXEMPLO"}])
        original = {"ok": True, "rows": [{"contract": "1234567", "technician": "z123456",
                                        "classification": "SEGURAR", "historical_code": "430"}],
                    "route_total": 1, "truncated": False}
        result = enrich_comparison(original, catalog)
        assert result["rows"][0]["technician"] == "TECNICO EXEMPLO (Z123456)"
        assert result["rows"][0]["technician_login"] == "Z123456"
        assert original["rows"][0]["technician"] == "z123456"
        assert result["route_total"] == 1 and result["truncated"] is False
        assert result["rows"][0]["historical_code"] == "430"
        assert enrich_comparison(result, catalog) == result


    def test_unknown_logins_and_named_routes_survive_missing_catalog(self):
        tmp_path = self.tmp_path
        catalog = TechnicianDirectory(tmp_path / "absent.json")
        payload = {"rows": [{"technician": "Z999999"}, {"technician": "JOAO MARIA CHIP"},
                            {"technician": None}]}
        assert enrich_comparison(payload, catalog) == payload
        assert enrich_comparison(payload, None) == payload


    def test_same_name_keeps_distinct_route_logins(self):
        tmp_path = self.tmp_path
        catalog = directory(tmp_path, [{"login": key, "name": "TECNICO EXEMPLO"}
                                        for key in ("Z123456", "Z654321")])
        result = enrich_comparison({"rows": [{"technician": key}
                                             for key in ("Z123456", "Z654321")]}, catalog)
        assert len({row["technician"] for row in result["rows"]}) == 2
        assert [row["technician_login"] for row in result["rows"]] == ["Z123456", "Z654321"]


    def test_catalog_changes_are_used_without_restarting(self):
        tmp_path = self.tmp_path
        catalog = directory(tmp_path, [{"login": "Z123456", "name": "NOME ANTIGO"}])
        payload = {"rows": [{"technician": "Z123456"}]}
        assert enrich_comparison(payload, catalog)["rows"][0]["technician_name"] == "NOME ANTIGO"
        catalog.path.write_text(json.dumps({"technicians": [
            {"login": "Z123456", "name": "NOME ATUALIZADO"}]}), encoding="utf-8")
        assert enrich_comparison(payload, catalog)["rows"][0]["technician_name"] == "NOME ATUALIZADO"
