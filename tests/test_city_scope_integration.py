import datetime as dt
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
from imperium_api import Order
from operation_scope import (
    PROJECT_ID,
    ImportScope,
    OperationBlocked,
    OperationCoordinator,
    OSIdentity,
    ProjectIdentity,
)
from toa_context import TOAContextIndex


class CityScopeIntegrationTests(unittest.TestCase):
    @staticmethod
    def csv(
        activity_id: str = "194000001",
        city: str = "NATAL",
        os_number: str = "100",
        login: str = "Z1",
    ) -> bytes:
        return (
            '"Data","Login do Tecnico","Status da Atividade","Endereco",'
            '"Cidade","UF","Numero da WO","Contrato","Node",'
            '"Id da Atividade","Cod de Baixa 1","Numero da O.S 1",'
            '"Ponto 1","Status da O.S 1","Tipo O.S 1"\n'
            f'"23/07/26","{login}","pendente","R TESTE","{city}","RN",'
            f'"01695|1","123","NTL01","{activity_id}","106","{os_number}",'
            f'"1","Pendente","DESCONEXAO"\n'
        ).encode("utf-8")

    def test_monitor_routes_official_toa_origins_to_their_profiles(self) -> None:
        routes = {
            "Atividades-NTL-DMV_08_08_26.csv": "natal",
            "Atividades-PWM-DMV_08_08_26.csv": "natal",
            "Atividades-FTZ-DMV_01_08_08_26.csv": "fortaleza",
            "Atividades-MRO-DMV_08_08_26.csv": "mossoro",
            "Atividades-JCR-DMV_08_08_26.csv": "recife",
        }
        for filename, expected_profile in routes.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    app._monitor_profile_for_source(filename, b"toa").key,
                    expected_profile,
                )

    def test_monitor_batch_consolidates_natal_and_parnamirim(self) -> None:
        ntl = self.csv(activity_id="194000001", os_number="100", login="Z1")
        pwm = self.csv(
            activity_id="194000002",
            city="PARNAMIRIM",
            os_number="200",
            login="Z2",
        )
        with tempfile.TemporaryDirectory() as temporary:
            snapshot_path = Path(temporary) / "natal.json"
            with patch.object(app, "_monitor_snapshot_path", return_value=snapshot_path):
                snapshot = app._build_monitor_snapshot_batch(
                    app.PROFILES["natal"],
                    [
                        ("Atividades-NTL-DMV_08_08_26.csv", ntl),
                        ("Atividades-PWM-DMV_08_08_26.csv", pwm),
                    ],
                )

        self.assertEqual(snapshot["profile"], "natal")
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(snapshot["order_count"], 2)
        self.assertEqual(snapshot["assignment_count"], 2)
        self.assertEqual(len(snapshot["source_files"]), 2)
        self.assertEqual(
            {order["city"] for order in snapshot["orders"]},
            {"NATAL", "PARNAMIRIM"},
        )

    def test_monitor_batch_deduplicates_the_same_assignment(self) -> None:
        content = self.csv()
        filename = "Atividades-NTL-DMV_08_08_26.csv"
        with tempfile.TemporaryDirectory() as temporary:
            snapshot_path = Path(temporary) / "natal.json"
            with patch.object(app, "_monitor_snapshot_path", return_value=snapshot_path):
                snapshot = app._build_monitor_snapshot_batch(
                    app.PROFILES["natal"],
                    [(filename, content), (filename, content)],
                )

        self.assertEqual(snapshot["order_count"], 1)
        self.assertEqual(snapshot["assignment_count"], 1)
        self.assertEqual(snapshot["source_files"], [filename])

    def test_import_preview_keeps_origin_city_profile_hash_and_activity(self) -> None:
        preview = app._scoped_import_preview(
            self.csv(),
            "Atividades-NTL-DMV_ADM_23_07_26.csv",
            SimpleNamespace(key="natal"),
        )
        self.assertEqual(preview.orders[0].activity_id, "194000001")
        self.assertEqual(preview.import_scope.import_origin, "NTL")
        self.assertEqual(preview.import_scope.expected_city, "NATAL")
        self.assertEqual(preview.import_scope.expected_profile_key, "natal")
        self.assertEqual(len(preview.import_scope.source_hash), 64)
        self.assertTrue(preview.import_scope.batch_id.startswith("NTL-"))

    def test_import_preview_refuses_target_selected_in_another_profile(self) -> None:
        with self.assertRaisesRegex(
            OperationBlocked,
            "profile_scope_mismatch",
        ):
            app._scoped_import_preview(
                self.csv(city="RECIFE"),
                "Atividades-JCR-DMV_ADM_23_07_26.csv",
                SimpleNamespace(key="natal"),
            )

    def test_import_preview_excludes_only_foreign_city_rows(self) -> None:
        content = self.csv(city="RECIFE") + self.csv(city="NATAL").split(
            b"\n", 1
        )[1]

        preview = app._scoped_import_preview(
            content,
            "Atividades-JCR-DMV_ADM_23_07_26.csv",
            SimpleNamespace(key="recife", label="RECIFE"),
        )

        self.assertEqual([order.city for order in preview.orders], ["RECIFE"])
        self.assertEqual(len(preview.scope_exclusions), 1)
        self.assertEqual(
            preview.scope_exclusions[0],
            {
                "os_number": "100",
                "contract": "123",
                "city": "NATAL",
                "state": "RN",
                "service": "DESCONEXAO",
                "reason": "city_scope_mismatch",
            },
        )

    def test_import_preview_blocks_file_with_only_foreign_cities(self) -> None:
        with self.assertRaisesRegex(OperationBlocked, "city_scope_mismatch"):
            app._scoped_import_preview(
                self.csv(city="NATAL"),
                "Atividades-JCR-DMV_ADM_23_07_26.csv",
                SimpleNamespace(key="recife", label="RECIFE"),
            )

    def test_import_preview_accepts_official_csv_without_activity_id(self) -> None:
        content = (
            '"Data","Login do Tecnico","Status da Atividade","Endereco",'
            '"Cidade","UF","Numero da WO","Contrato","Node",'
            '"Cod de Baixa 1","Numero da O.S 1","Ponto 1",'
            '"Status da O.S 1","Tipo O.S 1"\n'
            '"23/07/26","Z1","pendente","R TESTE","NATAL","RN",'
            '"01695|1","123","NTL01","106","100","1","Pendente",'
            '"DESCONEXAO"\n'
        ).encode("utf-8")
        preview = app._scoped_import_preview(
            content,
            "Atividades-NTL-DMV_ADM_23_07_26.csv",
            SimpleNamespace(key="natal"),
        )

        self.assertEqual(preview.orders[0].activity_id, "")
        self.assertEqual(preview.import_scope.import_origin, "NTL")
        self.assertEqual(preview.import_scope.expected_profile_key, "natal")

    def test_live_match_never_falls_back_to_contract_only(self) -> None:
        scope = ImportScope.from_source(
            "Atividades-NTL-DMV_ADM_23_07_26.csv",
            b"scope",
        )
        row = {
            "id_os": 1,
            "num_os": "100",
            "contract": "123",
            "city": "NATAL",
            "import_scope": scope.to_dict(),
            "operation_identity": {
                "project_id": PROJECT_ID,
                "profile_key": "natal",
                "city": "NATAL",
                "contract": "123",
                "activity_id": "194000001",
            },
        }
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            order_cache={1: Order(1, "100", "123", 1, "DESCONEXAO")},
            cache_date=dt.date(2026, 7, 23),
        )
        result = {
            "results": [
                {
                    "contract": "123",
                    "aid": "194000001",
                    "city": "NATAL",
                    "tasks": [{"os_number": "999"}],
                }
            ]
        }
        with patch.object(app, "_enrich_orders", return_value=[row]):
            matched = app._match_live_capture_to_orders(profile, result)
        capture = matched["results"][0]
        self.assertEqual(capture["imperium_matches"], [])
        self.assertEqual(
            capture["imperium_match_kind"],
            "activity_without_exact_os",
        )

    def test_live_match_derives_scope_from_exact_activity_not_first_contract(self) -> None:
        natal_scope = ImportScope.from_source(
            "Atividades-NTL-DMV_ADM_23_07_26.csv",
            b"natal",
        )
        recife_scope = ImportScope.from_source(
            "Atividades-JCR-DMV_ADM_23_07_26.csv",
            b"recife",
        )
        rows = [
            {
                "id_os": 2,
                "num_os": "200",
                "contract": "123",
                "city": "RECIFE",
                "import_scope": recife_scope.to_dict(),
                "operation_identity": {
                    "project_id": PROJECT_ID,
                    "profile_key": "recife",
                    "city": "RECIFE",
                    "contract": "123",
                    "activity_id": "A-RECIFE",
                },
            },
            {
                "id_os": 1,
                "num_os": "100",
                "contract": "123",
                "city": "NATAL",
                "import_scope": natal_scope.to_dict(),
                "operation_identity": {
                    "project_id": PROJECT_ID,
                    "profile_key": "natal",
                    "city": "NATAL",
                    "contract": "123",
                    "activity_id": "A-NATAL",
                },
            },
        ]
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            order_cache={1: Order(1, "100", "123", 1, "DESCONEXAO")},
            cache_date=dt.date(2026, 7, 23),
        )
        result = {
            "results": [
                {
                    "contract": "123",
                    "aid": "A-NATAL",
                    "city": "NATAL",
                    "tasks": [{"os_number": "100"}],
                }
            ]
        }
        with patch.object(app, "_enrich_orders", return_value=rows):
            matched = app._match_live_capture_to_orders(profile, result)
        capture = matched["results"][0]
        self.assertEqual(
            [item["num_os"] for item in capture["imperium_matches"]],
            ["100"],
        )
        self.assertEqual(capture["operation_blockers"], [])

    def test_close_validation_uses_server_registered_batch_scope(self) -> None:
        scope = ImportScope.from_source(
            "Atividades-NTL-DMV_ADM_23_07_26.csv",
            b"approved",
        )
        identity = OSIdentity(PROJECT_ID, "natal", "NATAL", "123", "A1")
        coordinator = OperationCoordinator(
            ProjectIdentity(PROJECT_ID, "offline-test-root")
        )
        snapshots = coordinator.refresh_contract(
            scope,
            "123",
            (
                {
                    **identity.to_dict(),
                    "status": "EM CAMPO",
                    "current_close_code": None,
                    "materials": [],
                    "equipments": [],
                    "installer_id": "328898",
                    "response_timestamp": "2026-07-23T09:00:00-03:00",
                    "response_version": "v1",
                },
            ),
        )
        profile = SimpleNamespace(
            key="natal",
            operations=coordinator,
            cache_date=dt.date(2026, 7, 23),
        )
        order = Order(1, "100", "123", 1, "DESCONEXAO")
        body = {
            "operation_identity": identity.to_dict(),
            "import_scope": scope.to_dict(),
            "approved_state_hash": snapshots[0].state_hash,
            "approved_source_hash": scope.source_hash,
        }
        with patch.object(app.TOA_CONTEXT, "validate_scope_source"):
            _identity, _snapshot, _scope, plan = app._validated_close_operation(
                profile,
                order,
                body,
                "106",
            )
        self.assertEqual(plan.close_code, "106")
        self.assertEqual(plan.batch_key, scope.batch_key)

        unrelated = ImportScope.from_source(
            "Atividades-NTL-DMV_ADM_23_07_26.csv",
            b"another-batch",
        )
        forged_body = {
            **body,
            "import_scope": unrelated.to_dict(),
            "approved_source_hash": unrelated.source_hash,
        }
        with (
            patch.object(app.TOA_CONTEXT, "validate_scope_source"),
            self.assertRaisesRegex(
                OperationBlocked,
                "payload_scope_violation",
            ),
        ):
            app._validated_close_operation(profile, order, forged_body, "106")

    def test_manual_close_uses_exact_current_imperium_cache_row(self) -> None:
        order = Order(41, "9001", "123", 7, "RETIRAR EQUIPAMENTO")
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            order_cache={order.id_os: order},
            cache_date=dt.date(2026, 7, 25),
            cache_generation=3,
        )
        scope = app._manual_close_scope(profile, order)
        body = {
            "operation_source": "imperium_cache",
            "manual_scope": scope,
            "approved_state_hash": scope["state_hash"],
        }

        validated = app._validated_close_operation(
            profile,
            order,
            body,
            "430",
        )

        self.assertEqual(validated, scope)
        self.assertNotIn("operation_identity", body)
        self.assertNotIn("import_scope", body)

    def test_manual_close_rejects_stale_cache_generation(self) -> None:
        order = Order(41, "9001", "123", 7, "RETIRAR EQUIPAMENTO")
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            order_cache={order.id_os: order},
            cache_date=dt.date(2026, 7, 25),
            cache_generation=3,
        )
        scope = app._manual_close_scope(profile, order)
        profile.cache_generation = 4
        body = {
            "operation_source": "imperium_cache",
            "manual_scope": scope,
            "approved_state_hash": scope["state_hash"],
        }

        with self.assertRaisesRegex(OperationBlocked, "stale_snapshot"):
            app._validated_close_operation(profile, order, body, "430")

    def test_manual_close_rejects_cross_profile_city_and_os_forgery(self) -> None:
        order = Order(41, "9001", "123", 7, "RETIRAR EQUIPAMENTO")
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            order_cache={order.id_os: order},
            cache_date=dt.date(2026, 7, 25),
            cache_generation=3,
        )
        scope = app._manual_close_scope(profile, order)
        scope.update(
            {
                "profile_key": "fortaleza",
                "city_scope": "FORTALEZA",
                "id_os": 99,
                "num_os": "OTHER",
            }
        )
        body = {
            "operation_source": "imperium_cache",
            "manual_scope": scope,
            "approved_state_hash": scope["state_hash"],
        }

        with self.assertRaises(OperationBlocked) as raised:
            app._validated_close_operation(profile, order, body, "430")
        self.assertIn("profile_scope_mismatch", raised.exception.blockers)
        self.assertIn("city_scope_mismatch", raised.exception.blockers)
        self.assertIn("stale_snapshot", raised.exception.blockers)

    def test_rows_without_toa_context_receive_manual_cache_snapshot(self) -> None:
        order = Order(41, "9001", "123", 7, "RETIRAR EQUIPAMENTO")
        coordinator = OperationCoordinator(
            ProjectIdentity(PROJECT_ID, "offline-test-root")
        )
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            order_cache={order.id_os: order},
            installer_overrides={},
            cache_date=dt.date(2026, 7, 25),
            cache_generation=3,
            operations=coordinator,
        )
        raw_row = {
            **order.to_dict(),
            "operation_blockers": ["missing_activity_id"],
        }

        with patch.object(app.TOA_CONTEXT, "enrich", return_value=[raw_row]):
            rows = app._enrich_orders(
                profile,
                dt.date(2026, 7, 25),
                [order],
            )

        self.assertEqual(rows[0]["operation_source"], "imperium_cache")
        self.assertEqual(rows[0]["manual_scope"]["id_os"], order.id_os)
        self.assertEqual(rows[0]["manual_scope"]["num_os"], order.num_os)
        self.assertEqual(rows[0]["operation_blockers"], [])
        self.assertEqual(
            rows[0]["toa_operation_blockers"],
            ["missing_activity_id"],
        )

    def test_changed_context_file_is_rejected_before_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Atividades-NTL-DMV_ADM_23_07_26.csv"
            source.write_bytes(b"approved")
            scope = ImportScope.from_source(source.name, source.read_bytes())
            context = TOAContextIndex(root)
            with patch.object(context, "_candidate_files", return_value=[source]):
                context.validate_scope_source(scope, dt.date(2026, 7, 23))
                source.write_bytes(b"changed")
                with self.assertRaisesRegex(
                    OperationBlocked,
                    "source_file_changed",
                ):
                    context.validate_scope_source(scope, dt.date(2026, 7, 23))


if __name__ == "__main__":
    unittest.main()
