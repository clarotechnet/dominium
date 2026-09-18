"""Comprehensive test suite for frontend block, candidate locator, and material resolver."""

import unittest
from decimal import Decimal
from official_candidate_locator import evaluate_candidate, generate_candidate_report
from official_material_resolver import (
    VERIFIED_GROUPS_REGISTRY,
    audit_equivalence_groups,
    resolve_materials_offline,
)


class CandidateLocatorTests(unittest.TestCase):
    def test_closed_fixture_contract_or_os_is_not_eligible(self) -> None:
        eval1 = evaluate_candidate({"contract": "2221170", "num_os": "2600000000"})
        self.assertEqual(eval1.eligibility_status, "closed_fixture_not_eligible")

        eval2 = evaluate_candidate({"contract": "1111111", "num_os": "2646508672"})
        self.assertEqual(eval2.eligibility_status, "closed_fixture_not_eligible")

    def test_missing_activity_id_blocks_candidate(self) -> None:
        cand = {
            "project_id": "IMPERIUM_OLLAMA",
            "profile_key": "natal",
            "city": "NATAL",
            "contract": "123456",
            "activity_id": "",
            "num_os": "2600000001",
            "toa_status": "complete",
            "imperium_status": "EM CAMPO",
            "tech_login": "Z637677",
            "installer_id": 328898,
            "stock_id": 276,
            "source_hash": "hash1",
            "state_hash": "hash2",
        }
        res = evaluate_candidate(cand)
        self.assertEqual(res.eligibility_status, "blocked")
        self.assertIn("missing_activity_id", res.blockers)

    def test_divergent_city_or_profile_blocks_candidate(self) -> None:
        cand = {
            "project_id": "IMPERIUM_OLLAMA",
            "profile_key": "recife",
            "city": "RECIFE",
            "contract": "123456",
            "activity_id": "ACT1",
            "num_os": "2600000001",
            "toa_status": "complete",
            "imperium_status": "EM CAMPO",
            "tech_login": "Z637677",
            "installer_id": 328898,
            "stock_id": 276,
            "source_hash": "hash1",
            "state_hash": "hash2",
        }
        res = evaluate_candidate(cand)
        self.assertEqual(res.eligibility_status, "blocked")
        self.assertIn("wrong_profile_key", res.blockers)
        self.assertIn("wrong_city", res.blockers)

    def test_eligible_candidate_offline(self) -> None:
        cand = {
            "project_id": "IMPERIUM_OLLAMA",
            "profile_key": "natal",
            "city": "NATAL",
            "contract": "999888",
            "activity_id": "ACT_OK",
            "num_os": "2600000099",
            "service": "ADESAO - INSTALACAO",
            "toa_status": "complete",
            "imperium_status": "EM CAMPO",
            "tech_login": "Z637677",
            "installer_id": 328898,
            "stock_id": 276,
            "source_hash": "hash_src",
            "state_hash": "hash_state",
        }
        res = evaluate_candidate(cand)
        self.assertEqual(res.eligibility_status, "eligible")
        self.assertEqual(len(res.blockers), 0)

    def test_candidate_report_generation(self) -> None:
        c1 = {"contract": "2221170", "num_os": "1"}
        c2 = {
            "project_id": "IMPERIUM_OLLAMA",
            "profile_key": "natal",
            "city": "NATAL",
            "contract": "999888",
            "activity_id": "ACT_OK",
            "num_os": "2600000099",
            "toa_status": "complete",
            "imperium_status": "EM CAMPO",
            "tech_login": "Z637677",
            "installer_id": 328898,
            "stock_id": 276,
            "source_hash": "h1",
            "state_hash": "h2",
        }
        json_path, txt_path = generate_candidate_report([c1, c2])
        self.assertTrue(json_path.is_file())
        self.assertTrue(txt_path.is_file())


class MaterialResolverTests(unittest.TestCase):
    def test_exact_code_with_stock_succeeds(self) -> None:
        toa_act = {"materials": [{"code": "22069613", "description": "FAST SC APC", "quantity": "10", "unit": "UN"}]}
        cat = {"items": {"22069613": {"description": "FAST SC APC"}}}
        stock = {"items": {"22069613": {"balance": "12", "unit": "UN"}}, "timestamp": "2026-07-24T10:00:00Z"}
        plan = resolve_materials_offline(toa_act, cat, stock, 328898, 276, "natal", "NATAL", "TECHNET")
        self.assertTrue(plan.success)
        self.assertEqual(plan.resolved_items[0].chosen_code, "22069613")
        self.assertEqual(plan.resolved_items[0].quantity, "10")

    def test_zero_stock_blocks(self) -> None:
        toa_act = {"materials": [{"code": "22025072", "description": "FITA ISOLANTE", "quantity": "1", "unit": "UN"}]}
        cat = {"items": {"22025072": {"description": "FITA ISOLANTE"}}}
        stock = {"items": {"22025072": {"balance": "0", "unit": "UN"}}}
        plan = resolve_materials_offline(toa_act, cat, stock, 328898, 276, "natal", "NATAL", "TECHNET")
        self.assertFalse(plan.success)
        self.assertIn("insufficient_stock_22025072", plan.blockers)

    def test_22056408_never_treated_as_tape(self) -> None:
        toa_act = {"materials": [{"code": "22056408", "description": "FITA ISOLANTE 3M", "quantity": "1", "unit": "UN"}]}
        cat = {"items": {"22056408": {"description": "CONECTOR ATENUADOR 06DB"}}}
        stock = {"items": {"22056408": {"balance": "10", "unit": "UN"}}}
        plan = resolve_materials_offline(toa_act, cat, stock, 328898, 276, "natal", "NATAL", "TECHNET")
        self.assertFalse(plan.success)
        self.assertIn("22056408_is_attenuator_not_tape", plan.blockers)

    def test_verified_group_substitution(self) -> None:
        toa_act = {"materials": [{"code": "22057620", "description": "FAST SC APC", "quantity": "2", "unit": "UN"}]}
        cat = {"items": {"22057620": {"description": "FAST SC APC"}}}
        stock = {"items": {"22069613": {"balance": "10", "unit": "UN"}}}  # Alternative in same group
        approved_groups = [{"key": "fiber_connector_sc_apc"}]
        plan = resolve_materials_offline(toa_act, cat, stock, 328898, 276, "natal", "NATAL", "TECHNET", approved_groups=approved_groups)
        self.assertTrue(plan.success)
        self.assertEqual(plan.resolved_items[0].chosen_code, "22069613")

    def test_audit_equivalence_groups_unverified(self) -> None:
        table = audit_equivalence_groups()
        unverified = [g for g in table if g["status"] == "unverified_equivalence_group"]
        self.assertTrue(len(unverified) >= 4)


if __name__ == "__main__":
    unittest.main()
