import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from operation_scope import (
    PROJECT_ID,
    ImportScope,
    MovementRecord,
    OperationBlocked,
    OperationCoordinator,
    OSIdentity,
    OSSnapshot,
    PlannedClose,
    ProjectIdentity,
    evaluate_preflight,
    guard_before_write,
    reconcile_execution,
    validate_payload_scope,
)


class OperationScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = ProjectIdentity(PROJECT_ID, "offline-test-root")
        self.coordinator = OperationCoordinator(self.project)

    @staticmethod
    def scope(origin: str, marker: str = "A") -> ImportScope:
        return ImportScope.from_source(
            f"Atividades-{origin}-DMV_ADM_23_07_26.csv",
            f"{origin}:{marker}".encode("ascii"),
        )

    @staticmethod
    def identity(
        profile: str = "natal",
        city: str = "NATAL",
        contract: str = "100",
        activity: str = "A1",
    ) -> OSIdentity:
        return OSIdentity(PROJECT_ID, profile, city, contract, activity)

    @staticmethod
    def snapshot(
        identity: OSIdentity,
        *,
        status: str = "EM CAMPO",
        close_code: str | None = None,
        materials: tuple[object, ...] = (),
        equipments: tuple[object, ...] = (),
        installer: str = "328898",
        timestamp: str = "2026-07-23T09:00:00-03:00",
        version: str = "v1",
    ) -> OSSnapshot:
        return OSSnapshot.create(
            identity=identity,
            status=status,
            current_close_code=close_code,
            materials=materials,
            equipments=equipments,
            installer_id=installer,
            response_timestamp=timestamp,
            response_version=version,
        )

    @classmethod
    def response(cls, identity: OSIdentity, **overrides: object) -> dict:
        value = {
            **identity.to_dict(),
            "status": "EM CAMPO",
            "current_close_code": None,
            "materials": [],
            "equipments": [],
            "installer_id": "328898",
            "response_timestamp": "2026-07-23T09:00:00-03:00",
            "response_version": "v1",
        }
        value.update(overrides)
        return value

    def approved_plan(
        self,
        scope: ImportScope,
        identity: OSIdentity,
        code: str = "106",
    ) -> tuple[OSSnapshot, PlannedClose]:
        approved = self.snapshot(identity)
        self.coordinator.refresh_contract(
            scope,
            identity.contract,
            (self.response(identity),),
        )
        return approved, self.coordinator.plan_close(scope, identity, code)

    def test_01_old_project_identity_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".imperium-project.json").write_text(
                json.dumps({"project_id": "IMPERIUM_ANTIGO"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                OperationBlocked,
                "wrong_project_identity",
            ):
                ProjectIdentity.load(root, allow_test_root=True)

    def test_02_wrong_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".imperium-project.json").write_text(
                json.dumps({"project_id": PROJECT_ID}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                OperationBlocked,
                "wrong_project_root",
            ):
                ProjectIdentity.load(root)

    def test_configured_production_root_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".imperium-project.json").write_text(
                json.dumps({"project_id": PROJECT_ID}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DOMINIUM_PROJECT_ROOT": str(root)}):
                identity = ProjectIdentity.load(root)
            self.assertEqual(Path(identity.root), root.resolve())

    def test_03_ntl_cannot_process_recife(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            self.scope("NTL").validate_target("natal", "RECIFE")

    def test_04_pwm_cannot_process_recife(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            self.scope("PWM").validate_target("natal", "RECIFE")

    def test_05_jcr_cannot_process_natal(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            self.scope("JCR").validate_target("recife", "NATAL")

    def test_06_ftz_cannot_process_natal(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            self.scope("FTZ").validate_target("fortaleza", "NATAL")

    def test_07_mro_cannot_process_fortaleza(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            self.scope("MRO").validate_target("mossoro", "FORTALEZA")

    def test_08_unknown_import_prefix_is_blocked(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "unknown_import_origin"):
            self.scope("XYZ")

    def test_09_same_contract_in_different_profiles_is_isolated(self) -> None:
        natal = self.identity("natal", "NATAL", "777", "A-NATAL")
        recife = self.identity("recife", "RECIFE", "777", "A-RECIFE")
        self.coordinator.refresh_contract(
            self.scope("NTL"),
            "777",
            (self.response(natal),),
        )
        self.coordinator.refresh_contract(
            self.scope("JCR"),
            "777",
            (self.response(recife),),
        )
        self.assertEqual(self.coordinator.snapshot(natal).identity, natal)
        self.assertEqual(self.coordinator.snapshot(recife).identity, recife)

    def test_10_same_contract_with_different_activities_is_isolated(self) -> None:
        first = self.identity(contract="777", activity="A1")
        second = self.identity(contract="777", activity="A2")
        snapshots = self.coordinator.refresh_contract(
            self.scope("NTL"),
            "777",
            (self.response(first), self.response(second)),
        )
        self.assertEqual({item.identity for item in snapshots}, {first, second})

    def test_11_natal_cache_cannot_be_reused_as_recife(self) -> None:
        natal = self.identity("natal", "NATAL", "777", "A1")
        recife = self.identity("recife", "RECIFE", "777", "A1")
        self.coordinator.refresh_contract(
            self.scope("NTL"),
            "777",
            (self.response(natal),),
        )
        with self.assertRaisesRegex(
            OperationBlocked,
            "activity_identity_mismatch",
        ):
            self.coordinator.snapshot(recife)

    def test_12_recife_list_with_natal_profile_is_blocked(self) -> None:
        invalid = self.identity("natal", "RECIFE", "777", "A1")
        with self.assertRaisesRegex(
            OperationBlocked,
            "profile_scope_mismatch",
        ):
            self.coordinator.refresh_contract(
                self.scope("JCR"),
                "777",
                (self.response(invalid),),
            )

    def test_13_natal_recife_natal_refresh_keeps_exact_context(self) -> None:
        natal = self.identity("natal", "NATAL", "777", "A-N")
        recife = self.identity("recife", "RECIFE", "777", "A-R")
        self.coordinator.refresh_contract(
            self.scope("NTL", "1"),
            "777",
            (self.response(natal, response_version="n1"),),
        )
        self.coordinator.refresh_contract(
            self.scope("JCR", "1"),
            "777",
            (self.response(recife, response_version="r1"),),
        )
        self.coordinator.refresh_contract(
            self.scope("NTL", "2"),
            "777",
            (self.response(natal, response_version="n2"),),
        )
        self.assertEqual(
            self.coordinator.snapshot(natal).response_version,
            "n2",
        )
        self.assertEqual(
            self.coordinator.snapshot(recife).response_version,
            "r1",
        )

    def test_14_open_order_closed_with_430_before_preflight_is_blocked(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        approved, plan = self.approved_plan(scope, identity, "106")
        current = self.snapshot(
            identity,
            status="FECHADA",
            close_code="430",
            version="v2",
        )
        result = evaluate_preflight(
            scope=scope,
            plan=plan,
            approved=approved,
            current=current,
        )
        self.assertFalse(result.allowed)
        self.assertIn("already_closed", result.blockers)
        self.assertIn(
            "already_closed_with_different_code:430",
            result.blockers,
        )
        self.assertIn("remote_state_changed", result.blockers)
        self.assertIn("operation_blocked", result.blockers)

    def test_15_closed_430_never_reaches_106_writer(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        approved, plan = self.approved_plan(scope, identity, "106")
        current = self.snapshot(
            identity,
            status="FECHADA",
            close_code="430",
            version="v2",
        )
        result = evaluate_preflight(
            scope=scope,
            plan=plan,
            approved=approved,
            current=current,
        )
        calls = []

        def forbidden_writer() -> None:
            calls.append("called")
            raise AssertionError("real write path reached")

        with self.assertRaises(OperationBlocked):
            guard_before_write(result, forbidden_writer)
        self.assertEqual(calls, [])

    def test_16_imperium_closed_dominium_open_requires_reconciliation(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        approved, plan = self.approved_plan(scope, identity, "106")
        current = self.snapshot(
            identity,
            status="FECHADA",
            close_code="430",
            version="v2",
        )
        result = evaluate_preflight(
            scope=scope,
            plan=plan,
            approved=approved,
            current=current,
            dominium_snapshot=approved,
        )
        self.assertIn("cross_system_status_conflict", result.blockers)
        self.assertIn(
            "already_closed_with_different_code:430",
            result.blockers,
        )

    def test_17_changed_snapshot_is_stale(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        approved, plan = self.approved_plan(scope, identity)
        current = self.snapshot(
            identity,
            materials=({"code": "22069613", "quantity": "1"},),
            version="v2",
        )
        result = evaluate_preflight(
            scope=scope,
            plan=plan,
            approved=approved,
            current=current,
        )
        self.assertIn("remote_state_changed", result.blockers)
        self.assertIn("stale_snapshot", result.blockers)

    def test_18_missing_activity_id_is_blocked(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "missing_activity_id"):
            self.identity(activity="")

    def test_19_update_by_contract_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            OperationBlocked,
            "contract_identity_mismatch",
        ):
            self.coordinator.update_by_contract("100", {})

    def test_20_update_by_table_index_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            OperationBlocked,
            "activity_identity_mismatch",
        ):
            self.coordinator.update_by_index(0, {})

    def test_21_movement_with_different_final_code_is_inconsistent(self) -> None:
        identity = self.identity()
        plan = PlannedClose(
            identity,
            self.scope("NTL").batch_key,
            "430",
            "approved",
            "source",
            "now",
        )
        final = self.snapshot(
            identity,
            status="FECHADA",
            close_code="106",
            version="v2",
        )
        issues = reconcile_execution(
            plan=plan,
            final_snapshot=final,
            movements=(MovementRecord(identity, "removed", "SERIAL", "430"),),
        )
        self.assertTrue(
            any(
                issue.code == "material_close_code_inconsistency"
                for issue in issues
            )
        )

    def test_22_reexecution_of_finalized_identity_is_reconciled(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        _approved, plan = self.approved_plan(scope, identity, "430")
        final = self.snapshot(
            identity,
            status="FECHADA",
            close_code="430",
            version="v2",
        )
        first = self.coordinator.audit_execution("OP-1", plan, final, ())
        second = self.coordinator.audit_execution("OP-2", plan, final, ())
        self.assertEqual(first.state, "consistent")
        self.assertEqual(second.state, "reconciliation_required")
        self.assertIn("already_closed", {issue.code for issue in second.issues})

    def test_23_simultaneous_city_batches_remain_distinct(self) -> None:
        scopes = (self.scope("NTL"), self.scope("JCR"))
        self.assertNotEqual(scopes[0].batch_key, scopes[1].batch_key)
        self.coordinator.register_scope(scopes[0])
        self.coordinator.register_scope(scopes[1])

    def test_24_state_does_not_leak_between_coordinators(self) -> None:
        identity = self.identity()
        self.coordinator.refresh_contract(
            self.scope("NTL"),
            identity.contract,
            (self.response(identity),),
        )
        isolated = OperationCoordinator(self.project)
        with self.assertRaisesRegex(
            OperationBlocked,
            "activity_identity_mismatch",
        ):
            isolated.snapshot(identity)

    def test_25_payload_with_another_city_is_rejected(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        _approved, plan = self.approved_plan(scope, identity)
        metadata = {
            **identity.to_dict(),
            "city": "RECIFE",
            "batch_id": scope.batch_id,
            "source_hash": scope.source_hash,
        }
        with self.assertRaisesRegex(
            OperationBlocked,
            "payload_scope_violation",
        ):
            validate_payload_scope(scope, plan, metadata)

    def test_26_failed_preflight_prevents_all_write_calls(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        approved, plan = self.approved_plan(scope, identity)
        changed = self.snapshot(identity, installer="999", version="v2")
        result = evaluate_preflight(
            scope=scope,
            plan=plan,
            approved=approved,
            current=changed,
        )
        writer_calls = 0

        def fail_on_write() -> None:
            nonlocal writer_calls
            writer_calls += 1
            raise AssertionError("write called")

        with self.assertRaises(OperationBlocked):
            guard_before_write(result, fail_on_write)
        self.assertEqual(writer_calls, 0)

    def test_27_changed_import_file_is_blocked(self) -> None:
        scope = self.scope("NTL")
        with self.assertRaisesRegex(OperationBlocked, "source_file_changed"):
            scope.validate_source(scope.source_file, b"changed")

    def test_28_ntl_cannot_dynamically_switch_to_recife(self) -> None:
        scope = self.scope("NTL")
        with self.assertRaises(OperationBlocked) as raised:
            scope.validate_target("recife", "RECIFE")
        self.assertEqual(
            set(raised.exception.blockers),
            {"profile_scope_mismatch", "city_scope_mismatch"},
        )

    def test_29_plan_from_another_batch_is_blocked(self) -> None:
        original_scope = self.scope("NTL", "one")
        other_scope = self.scope("NTL", "two")
        identity = self.identity()
        approved, plan = self.approved_plan(original_scope, identity)
        result = evaluate_preflight(
            scope=other_scope,
            plan=plan,
            approved=approved,
            current=approved,
        )
        self.assertIn("shared_state_contamination", result.blockers)
        self.assertIn("payload_scope_violation", result.blockers)

    def test_30_interleaving_natal_recife_fortaleza_is_isolated(self) -> None:
        contexts = (
            (self.scope("NTL"), self.identity("natal", "NATAL", "999", "AN")),
            (self.scope("JCR"), self.identity("recife", "RECIFE", "999", "AR")),
            (
                self.scope("FTZ"),
                self.identity("fortaleza", "FORTALEZA", "999", "AF"),
            ),
        )

        def refresh(context: tuple[ImportScope, OSIdentity]) -> tuple[str, ...]:
            scope, identity = context
            result = self.coordinator.refresh_contract(
                scope,
                identity.contract,
                (self.response(identity, response_version=identity.activity_id),),
            )
            return result[0].identity.key

        with ThreadPoolExecutor(max_workers=3) as executor:
            keys = tuple(executor.map(refresh, contexts))

        self.assertEqual(
            set(keys),
            {identity.key for _scope, identity in contexts},
        )
        for _scope, identity in contexts:
            self.assertEqual(
                self.coordinator.snapshot(identity).identity,
                identity,
            )

    def test_state_hash_is_deterministic_for_collection_order(self) -> None:
        identity = self.identity()
        left = self.snapshot(
            identity,
            materials=({"code": "2"}, {"code": "1"}),
        )
        right = self.snapshot(
            identity,
            materials=({"code": "1"}, {"code": "2"}),
        )
        self.assertEqual(left.state_hash, right.state_hash)
        self.assertEqual(
            len(bytes.fromhex(left.state_hash)),
            hashlib.sha256().digest_size,
        )

    def test_forged_import_scope_mapping_is_rejected(self) -> None:
        scope = self.scope("JCR")
        forged = {**scope.to_dict(), "expected_city": "NATAL"}
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            ImportScope.from_dict(forged)

    def test_snapshot_cannot_be_used_with_an_unrelated_registered_batch(self) -> None:
        original = self.scope("NTL", "one")
        unrelated = self.scope("NTL", "two")
        identity = self.identity()
        self.coordinator.refresh_contract(
            original,
            identity.contract,
            (self.response(identity),),
        )
        self.coordinator.register_scope(unrelated)
        with self.assertRaisesRegex(
            OperationBlocked,
            "payload_scope_violation",
        ):
            self.coordinator.validate_exact_scope(identity, unrelated)

    def test_plan_with_another_approved_hash_is_stale(self) -> None:
        scope = self.scope("NTL")
        identity = self.identity()
        approved, plan = self.approved_plan(scope, identity)
        forged = PlannedClose(
            plan.identity,
            plan.batch_key,
            plan.close_code,
            "0" * 64,
            plan.source_hash,
            plan.planned_at,
        )
        result = evaluate_preflight(
            scope=scope,
            plan=forged,
            approved=approved,
            current=approved,
        )
        self.assertIn("stale_snapshot", result.blockers)


if __name__ == "__main__":
    unittest.main()
