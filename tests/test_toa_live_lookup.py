import datetime as dt
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import (
    _annotate_live_operational_windows,
    _merge_live_capture_registry_tasks,
    _match_live_capture_to_orders,
    _refresh_live_lookup_imperium_cache,
    _resolve_toa_live_reference,
)
from imperium_api import Order
from toa_live import TOALiveSession


class TOALiveLookupTests(unittest.TestCase):
    def test_registry_completes_all_contract_os_without_duplicating_live_tasks(self) -> None:
        capture = {
            "tasks": [
                {"os_number": "2652246779", "close_code": "409"},
                {"os_number": "2652246780", "close_code": "409"},
            ],
        }
        registry_orders = [
            {"os_number": "2652246779", "service": "516 - ADESAO ENTREGA STREAMING"},
            {"os_number": "2652246780", "service": "43 - ADESAO - INSTALAR PONTO VIRTUA"},
            {"os_number": "2652246791", "service": "208 - ENVIO DE CHIP VIA TECNICO"},
        ]

        tasks = _merge_live_capture_registry_tasks(capture, registry_orders)

        self.assertEqual(
            [task["os_number"] for task in tasks],
            ["2652246779", "2652246780", "2652246791"],
        )
        self.assertEqual(tasks[0]["close_code"], "409")
        self.assertEqual(tasks[2]["service"], "208 - ENVIO DE CHIP VIA TECNICO")
        self.assertEqual(tasks[2]["close_code"], "706")
        self.assertTrue(tasks[2]["registry_only"])

    def test_registry_does_not_infer_706_for_another_service(self) -> None:
        tasks = _merge_live_capture_registry_tasks(
            {"tasks": []},
            [{"os_number": "2652246780", "service": "ADESAO - INSTALAR PONTO VIRTUA"}],
        )

        self.assertEqual(tasks[0]["close_code"], "")

    def test_registry_replaces_collector_dash_with_chip_close_code(self) -> None:
        tasks = _merge_live_capture_registry_tasks(
            {
                "tasks": [{
                    "os_number": "2652246791",
                    "service": "ENVIO DE CHIP VIA TECNICO",
                    "close_code": "-",
                }],
            },
            [{
                "os_number": "2652246791",
                "service": "208 - ENVIO DE CHIP VIA TECNICO",
            }],
        )

        self.assertEqual(tasks[0]["close_code"], "706")

    def test_live_lookup_lists_three_contract_os_and_marks_only_active_rows(self) -> None:
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            cache_date=dt.date(2026, 8, 25),
            cache_generation=4,
            installer_overrides={},
            order_cache={
                1: Order(1, "2652246779", "4262531", 10, "ADESAO ENTREGA STREAMING"),
                2: Order(2, "2652246791", "4262531", 11, "ENVIO DE CHIP VIA TECNICO"),
            },
        )
        result = {
            "results": [{
                "aid": "198063337",
                "contract": "4262531",
                "scheduled_date": "2026-08-25",
                "city": "NATAL",
                "tasks": [
                    {"os_number": "2652246779", "close_code": "409"},
                    {"os_number": "2652246780", "close_code": "409"},
                ],
            }],
        }
        registry = {
            "records": [{
                "contract": "4262531",
                "orders": [
                    {"os_number": "2652246779", "service": "516 - ADESAO ENTREGA STREAMING"},
                    {"os_number": "2652246780", "service": "43 - ADESAO - INSTALAR PONTO VIRTUA"},
                    {"os_number": "2652246791", "service": "208 - ENVIO DE CHIP VIA TECNICO"},
                ],
            }],
        }

        with patch("app.TOA_CONTRACTS.public_state", return_value=registry):
            matched = _match_live_capture_to_orders(profile, result)

        capture = matched["results"][0]
        self.assertEqual(
            [task["os_number"] for task in capture["tasks"]],
            ["2652246779", "2652246780", "2652246791"],
        )
        task_state = {
            task["os_number"]: task["imperium_field"] for task in capture["tasks"]
        }
        self.assertEqual(task_state, {
            "2652246779": True,
            "2652246780": False,
            "2652246791": True,
        })
        self.assertEqual(
            {order["num_os"] for order in capture["imperium_matches"]},
            {"2652246779", "2652246791"},
        )
        chip_task = next(
            task for task in capture["tasks"]
            if task["os_number"] == "2652246791"
        )
        self.assertEqual(chip_task["close_code"], "706")

    def test_live_lookup_refreshes_field_cache_when_toa_os_is_missing(self) -> None:
        order = Order(
            2214730,
            "2658396041",
            "4296304",
            43,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        profile = SimpleNamespace(
            key="natal",
            label="Natal",
            cache_lock=threading.RLock(),
            order_cache={},
            cache_date=None,
            cache_generation=0,
            api=SimpleNamespace(
                list_orders=lambda *_args, **_kwargs: [order],
            ),
        )
        result = {
            "results": [{
                "contract": "4296304",
                "tasks": [{"os_number": "2658396041"}],
            }],
        }
        gate = SimpleNamespace(
            acquire=lambda **_kwargs: True,
            release=lambda: None,
        )

        with (
            patch("app.OPERATION_GATE", gate),
            patch("app._reconcile_failures"),
            patch("app._enrich_orders", return_value=[order.to_dict()]),
            patch("app._record_operational_orders"),
        ):
            info = _refresh_live_lookup_imperium_cache(profile, result)

        self.assertTrue(info["attempted"])
        self.assertTrue(info["refreshed"])
        self.assertFalse(info["busy"])
        self.assertEqual(info["missing_after"], [])
        self.assertEqual(profile.order_cache[2214730], order)
        self.assertEqual(profile.cache_date, dt.date.today())
        self.assertEqual(profile.cache_generation, 1)

    def test_live_lookup_does_not_use_stale_cache_when_imperium_is_busy(self) -> None:
        profile = SimpleNamespace(
            key="natal",
            label="Natal",
            cache_lock=threading.RLock(),
            order_cache={},
            cache_date=dt.date.today(),
            cache_generation=2,
            api=SimpleNamespace(
                list_orders=lambda *_args, **_kwargs: self.fail(
                    "DataSnap must not run while gate is busy"
                ),
            ),
        )
        result = {
            "results": [{
                "contract": "4296304",
                "tasks": [{"os_number": "2658396041", "close_code": "409"}],
            }],
        }
        gate = SimpleNamespace(
            acquire=lambda **_kwargs: False,
            release=lambda: self.fail("busy gate must not be released"),
        )

        with patch("app.OPERATION_GATE", gate):
            info = _refresh_live_lookup_imperium_cache(profile, result)
        result["imperium_refresh"] = info

        with (
            patch("app._enrich_orders", return_value=[]),
            patch("app.TOA_CONTRACTS.public_state", return_value={"records": []}),
            patch(
                "app.OPERATIONAL_STORE.contract",
                return_value={
                    "orders": [{
                        "os_number": "2658396041",
                        "imperium_status": "EM CAMPO",
                        "source": "imperium",
                        "updated_at": "2026-09-28T08:26:15-03:00",
                    }],
                },
            ),
        ):
            matched = _match_live_capture_to_orders(profile, result)

        task = matched["results"][0]["tasks"][0]
        self.assertFalse(task["imperium_field"])
        self.assertEqual(
            task["imperium_status"],
            "NAO CONFIRMADA - IMPERIUM OCUPADO",
        )
        self.assertEqual(task["imperium_status_source"], "refresh_busy")
        self.assertIn(
            "Imperium ocupado",
            matched["results"][0]["validation_warnings"][0],
        )

    def test_resolves_os_to_contract_from_current_profile(self) -> None:
        profile = SimpleNamespace(
            cache_lock=threading.RLock(),
            order_cache={
                1: Order(1, "2650569933", "4252617", 10, "ADESAO"),
                2: Order(2, "2650569934", "4252617", 10, "ADESAO"),
            },
        )

        result = _resolve_toa_live_reference(profile, "OS 2650569933")

        self.assertEqual(result, ("4252617", "os", "2650569933"))

    def test_accepts_contract_when_it_is_not_an_os(self) -> None:
        profile = SimpleNamespace(
            cache_lock=threading.RLock(),
            order_cache={},
        )

        result = _resolve_toa_live_reference(profile, "4252617")

        self.assertEqual(result, ("4252617", "contract", ""))

    def test_rejects_unresolved_os_instead_of_searching_it_as_contract(self) -> None:
        profile = SimpleNamespace(
            cache_lock=threading.RLock(),
            order_cache={},
        )

        with self.assertRaisesRegex(ValueError, "OS nao localizada"):
            _resolve_toa_live_reference(profile, "2650569933")

    def test_broad_disconnection_uses_current_operational_window(self) -> None:
        result = {
            "results": [
                {
                    "aid": "2",
                    "contract": "2",
                    "work_type": "DESCONEXAO OPCAO",
                    "service_window": "08:00 - 22:00",
                },
                {
                    "aid": "1",
                    "contract": "1",
                    "work_type": "INSTALACAO",
                    "service_window": "11:00 - 14:00",
                },
            ]
        }

        annotated = _annotate_live_operational_windows(
            result,
            now=dt.datetime(2026, 8, 12, 10, 30),
        )

        self.assertEqual(annotated["current_operational_window"], "08:00 - 11:00")
        self.assertEqual(
            [row["contract"] for row in annotated["results"]],
            ["2", "1"],
        )
        disconnection = annotated["results"][0]
        self.assertEqual(disconnection["official_service_window"], "08:00 - 22:00")
        self.assertEqual(disconnection["operational_window"], "08:00 - 11:00")
        self.assertEqual(
            disconnection["operational_window_source"],
            "current_disconnection",
        )

    def test_exact_contract_and_os_uses_current_imperium_manual_scope(self) -> None:
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            cache_date=dt.date(2026, 8, 20),
            cache_generation=3,
            installer_overrides={},
            order_cache={
                1: Order(1, "2652343799", "1290752", 10, "ADESAO ASSINATURA"),
                2: Order(2, "2652343801", "1290752", 11, "ADESAO VIRTUA"),
            },
        )
        result = {
            "results": [{
                "aid": "197594773",
                "contract": "1290752",
                "city": "PARNAMIRIM",
                "tasks": [
                    {"os_number": "2652343799", "close_code": "409"},
                    {"os_number": "2652343801", "close_code": "409"},
                ],
            }],
        }

        matched = _match_live_capture_to_orders(profile, result)
        capture = matched["results"][0]

        self.assertEqual(capture["imperium_match_kind"], "os_number_current_imperium")
        self.assertEqual(
            {row["num_os"] for row in capture["imperium_matches"]},
            {"2652343799", "2652343801"},
        )
        self.assertTrue(all(
            row["operation_source"] == "imperium_cache"
            and row["manual_scope"]["state_hash"] == row["approved_state_hash"]
            for row in capture["imperium_matches"]
        ))

    def test_inventory_ledger_upserts_activity_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            session = TOALiveSession(Path(temporary))
            capture = {
                "aid": "194000001",
                "contract": "4252617",
                "scheduled_date": "2026-08-12",
                "service_window": "08:00 - 11:00",
                "work_type": "ADESAO",
                "activity_status": "complete",
                "technician_observation": "OK TECNICO",
                "tasks": [{"os_number": "2650569933", "close_code": "409"}],
                "installed_equipment": [{"serial": "ABC123", "kind": "equipment"}],
                "removed_equipment": [{"serial": "OLD123", "kind": "equipment"}],
                "materials": [{"material_code": "22056332", "quantity": 1}],
                "customer_name": "NAO DEVE SER SALVO",
                "address": "NAO DEVE SER SALVO",
            }

            path = session._persist_inventory_ledger("4252617", [capture])
            capture["materials"][0]["quantity"] = 2
            session._persist_inventory_ledger("4252617", [capture])

            ledger = json.loads(path.read_text(encoding="utf-8"))
            activities = ledger["contracts"]["4252617"]["activities"]
            self.assertEqual(list(activities), ["194000001"])
            self.assertEqual(activities["194000001"]["materials"][0]["quantity"], 2)
            serialized = json.dumps(ledger, ensure_ascii=False)
            self.assertNotIn("NAO DEVE SER SALVO", serialized)


    def test_historical_imperium_order_becomes_scoped_manual_match(self) -> None:
        profile = SimpleNamespace(
            key="natal",
            cache_lock=threading.RLock(),
            cache_date=dt.date(2026, 9, 28),
            cache_generation=4,
            installer_overrides={},
            order_cache={},
            api=SimpleNamespace(
                native_order_protocol=SimpleNamespace(
                    service=lambda _name: SimpleNamespace(id_service=43)
                )
            ),
        )
        history = {
            "profile": "natal",
            "contract": "4296304",
            "os_number": "2658396041",
            "id_os": 2214730,
            "service": "ADESAO - INSTALAR PONTO VIRTUA",
            "imperium_status": "EM CAMPO",
            "source": "imperium",
            "updated_at": "2026-09-28T08:26:15-03:00",
        }
        result = {
            "results": [{
                "aid": "201021791",
                "contract": "4296304",
                "city": "NATAL",
                "tasks": [{"os_number": "2658396041", "close_code": "409"}],
            }],
        }

        with (
            patch("app.OPERATIONAL_STORE.contract", return_value={
                "orders": [history],
            }),
            patch("app.TOA_CONTRACTS.public_state", return_value={"records": []}),
        ):
            matched = _match_live_capture_to_orders(profile, result)

        capture = matched["results"][0]
        self.assertEqual(capture["imperium_match_kind"], "os_number_operational_history")
        self.assertEqual(len(capture["imperium_matches"]), 1)
        order = capture["imperium_matches"][0]
        self.assertEqual(order["id_os"], 2214730)
        self.assertEqual(order["id_service"], 43)
        self.assertEqual(order["operation_source"], "imperium_history")
        self.assertEqual(order["manual_scope"]["source"], "imperium_history_v1")
        self.assertEqual(
            order["approved_state_hash"],
            order["manual_scope"]["state_hash"],
        )
        self.assertFalse(capture["tasks"][0]["imperium_field"])
        self.assertEqual(
            capture["tasks"][0]["imperium_status_source"],
            "operational_history",
        )

if __name__ == "__main__":
    unittest.main()
