import datetime as dt
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import (
    _append_import_audit,
    _build_official_panel_plan,
    _confirm_bulk_creation,
    _installer_change_preview,
    _manual_close_scope,
    _material_assignment,
    _material_paste_key,
    _official_material_preparation_items,
    _record_live_technician_evidence,
    _same_technician_name,
    _technician_by_current_name,
    _official_technician_code,
    _save_material_assignment,
    _validate_official_installed_serial_ownership,
)
from bulk_orders import build_bulk_preview
from close_report import CloseReportStore
from imperium_api import MaterialTransferUncertainError, Order
from imperium_http_api import ImperiumHTTPResult


class AppPersistenceTests(unittest.TestCase):
    def test_technician_name_accepts_imperium_abbreviation_and_toa_typo(self) -> None:
        self.assertTrue(
            _same_technician_name(
                "EDCARLOS DE LIRA",
                "EDICARLOS DE LIRA SILVA",
            )
        )

    def test_technician_name_prefers_the_most_specific_abbreviated_match(
        self,
    ) -> None:
        technicians = [
            {"login": "Z667709", "name": "ALEXANDRE"},
            {
                "login": "Z676784",
                "name": "ALEXANDRE LEVY DE AZEVEDO LIMA",
            },
        ]
        with (
            patch("app.TECHNICIANS.resolve", return_value=None),
            patch(
                "app.TECHNICIANS.public_dict",
                return_value={"technicians": technicians},
            ),
        ):
            result = _technician_by_current_name("ALEXANDRE LEVY")

        self.assertIsNotNone(result)
        self.assertEqual(result["login"], "Z676784")

    def test_technician_name_resolves_operational_suffix_desc(self) -> None:
        technicians = [
            {
                "login": "Z570527",
                "name": "ELVIS AARON FIRMINO DA SILVA",
                "teams": ["MDU"],
            },
            {
                "login": "Z512085",
                "name": "ALLAN JAYVERSON DA COSTA",
                "teams": ["MDU"],
            },
        ]
        with (
            patch("app.TECHNICIANS.resolve", return_value=None),
            patch(
                "app.TECHNICIANS.public_dict",
                return_value={"technicians": technicians},
            ),
        ):
            res_elvis = _technician_by_current_name("ELVIS AARON  DESC")
            res_allan = _technician_by_current_name("ALLAN JAYVERSON DESC")

        self.assertIsNotNone(res_elvis)
        self.assertEqual(res_elvis["login"], "Z570527")
        self.assertIsNotNone(res_allan)
        self.assertEqual(res_allan["login"], "Z512085")

    def test_technician_name_resolves_tokens_and_surnames(self) -> None:
        technicians = [
            {
                "login": "Z674912",
                "name": "FRANCISCO ROMARIO PEREIRA DE CASTRO",
                "teams": ["MDU"],
            },
            {
                "login": "Z529107",
                "name": "GABRIEL DE MORAIS BRITO",
                "teams": ["MDU"],
            },
        ]
        with (
            patch("app.TECHNICIANS.resolve", return_value=None),
            patch(
                "app.TECHNICIANS.public_dict",
                return_value={"technicians": technicians},
            ),
        ):
            res_romario = _technician_by_current_name("ROMARIO PEREIRA DESC")
            res_gabriel = _technician_by_current_name("GABRIEL BRITO DESC")

        self.assertIsNotNone(res_romario)
        self.assertEqual(res_romario["login"], "Z674912")
        self.assertIsNotNone(res_gabriel)
        self.assertEqual(res_gabriel["login"], "Z529107")

    def test_official_technician_preserves_login_captured_for_current_installer(
        self,
    ) -> None:
        order = Order(
            2170777,
            "2647378599",
            "4234309",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        profile = SimpleNamespace(
            api=SimpleNamespace(
                order_installer=lambda _order: {
                    "installer_id": 249803,
                    "installer_name": "SONERREGILSON",
                }
            )
        )

        with (
            patch(
                "app._enrich_orders",
                return_value=[
                    {
                        "technician": "SONERREGILSON DA SILVA MEDEIROS",
                        "technician_login": "Z660888",
                    }
                ],
            ),
            patch("app._technician_by_current_name") as name_lookup,
        ):
            result = _official_technician_code(
                profile,
                order,
                dt.date(2026, 7, 28),
            )

        self.assertEqual(result, ("Z660888", "SONERREGILSON", 249803))
        name_lookup.assert_not_called()

    def test_official_technician_falls_back_when_captured_login_belongs_to_another_person(
        self,
    ) -> None:
        order = Order(
            2170777,
            "2647378599",
            "4234309",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        profile = SimpleNamespace(
            api=SimpleNamespace(
                order_installer=lambda _order: {
                    "installer_id": 249803,
                    "installer_name": "SONERREGILSON",
                }
            )
        )

        with (
            patch(
                "app._enrich_orders",
                return_value=[
                    {
                        "technician": "OUTRO TECNICO",
                        "technician_login": "Z660888",
                    }
                ],
            ),
            patch(
                "app._technician_by_current_name",
                return_value={"name": "SONERREGILSON", "login": "Z111222"},
            ),
        ):
            result = _official_technician_code(
                profile,
                order,
                dt.date(2026, 7, 28),
            )
            self.assertEqual(result, ("Z111222", "SONERREGILSON", 249803))

    def test_official_technician_uses_server_side_live_toa_evidence(self) -> None:
        order = Order(
            2188316,
            "2652317082",
            "4262841",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        profile = SimpleNamespace(
            key="natal",
            api=SimpleNamespace(
                order_installer=lambda _order: {
                    "installer_id": 1308,
                    "installer_name": "EDCARLOS DE LIRA",
                }
            ),
        )
        lookup = {
            "results": [{
                "contract": "4262841",
                "aid": "197582942",
                "route_provider": {"name": "NTL-DMV"},
                "assigned_technician": {
                    "external_id": "Z131568",
                    "name": "EDICARLOS DE LIRA SILVA",
                },
                "tasks": [{"os_number": "2652317082"}],
            }],
        }

        _record_live_technician_evidence(profile, lookup)
        with patch(
            "app._enrich_orders",
            return_value=[{"technician": "", "technician_login": ""}],
        ):
            result = _official_technician_code(
                profile,
                order,
                dt.date(2026, 8, 21),
            )

        self.assertEqual(result, ("Z131568", "EDCARLOS DE LIRA", 1308))

    def test_installer_change_preview_is_scoped_to_one_contract(self) -> None:
        selected = Order(10, "100", "3715664", 1, "RETIRAR EMTA")
        sibling = Order(11, "101", "3715664", 2, "RETIRAR DECODER")
        unrelated = Order(12, "102", "9999999", 3, "RETIRAR EMTA")
        owner = {
            "stock_id": 44,
            "stock_name": "GENIVAL QUIRINO DESC",
            "installer_id": 9876,
            "technician_name": "GENIVAL QUIRINO DESC",
        }
        profile = SimpleNamespace(
            key="natal",
            installer_change_enabled=True,
            api=SimpleNamespace(
                find_serial_owner=lambda _serial: {
                    "ok": True,
                    "found": True,
                    "owner": owner,
                }
            ),
            cache_lock=threading.RLock(),
            order_cache={
                selected.id_os: selected,
                sibling.id_os: sibling,
                unrelated.id_os: unrelated,
            },
        )

        preview = _installer_change_preview(
            profile,
            selected.id_os,
            "241786844144",
        )

        self.assertEqual(preview["contract"], "3715664")
        self.assertEqual(preview["installer_id"], 9876)
        self.assertEqual(
            {row["id_os"] for row in preview["orders"]},
            {selected.id_os, sibling.id_os},
        )
        self.assertEqual(len(preview["preview_token"]), 64)

    def test_toa_material_assignment_survives_a_new_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = SimpleNamespace(log_root=Path(directory))
            order = SimpleNamespace(num_os="2646785556", id_os=2162000)
            key = _material_paste_key("496192015\nHFC\n22026219_CABO\n16")

            _save_material_assignment(profile, key, order)
            assignment = _material_assignment(profile, key)

            self.assertEqual(len(key), 64)
            self.assertEqual(assignment["os_number"], "2646785556")
            self.assertEqual(assignment["id_os"], 2162000)

    def test_import_audit_keeps_every_confirmed_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = SimpleNamespace(
                key="natal",
                label="NATAL / PARNAMIRIM",
                log_root=Path(directory),
            )
            preview = SimpleNamespace(
                filename="Atividades-NTL-DMV_ADM.csv",
                source_rows=129,
                orders=tuple(range(125)),
            )
            rows = [
                {
                    "os_number": str(2_640_000_000 + index),
                    "contract": str(3_000_000 + index),
                    "os_type": "RETIRAR EMTA",
                    "import_status": (
                        "IMPORTADA COM SUCESSO"
                        if index < 80
                        else "DATA/INSTALADOR ATUALIZADO"
                    ),
                    "imported": index < 80,
                }
                for index in range(125)
            ]
            result = {
                "orders": rows,
                "imported": 80,
                "not_imported": 45,
            }

            _append_import_audit(
                profile,
                {"key": "rn"},
                preview,
                23.4,
                result=result,
            )

            audit_path = next(Path(directory).glob("importacoes-*.jsonl"))
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertTrue(audit["ok"])
            self.assertEqual(audit["count"], 125)
            self.assertEqual(audit["imported"], 80)
            self.assertEqual(audit["not_imported"], 45)
            self.assertEqual(len(audit["orders"]), 125)

    def test_import_audit_keeps_attempted_orders_after_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = SimpleNamespace(
                key="natal",
                label="NATAL / PARNAMIRIM",
                log_root=Path(directory),
            )
            preview = build_bulk_preview(
                "3185231",
                "TECNICO TESTE",
                "natal",
                service="CORRECAO ESTOQUE",
            )

            _append_import_audit(
                profile,
                {"key": "criacao-em-massa"},
                preview,
                30.0,
                error=TimeoutError("timed out"),
            )

            audit_path = next(Path(directory).glob("importacoes-*.jsonl"))
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertFalse(audit["ok"])
            self.assertEqual(len(audit["orders"]), 1)
            self.assertEqual(audit["orders"][0]["os_number"], "3185231 3185231")
            self.assertEqual(audit["orders"][0]["service"], "CORRECAO ESTOQUE")

    def test_bulk_creation_can_be_confirmed_by_the_orders_query(self) -> None:
        preview = build_bulk_preview(
            "3185231",
            "TECNICO TESTE",
            "natal",
            service="CORRECAO ESTOQUE",
        )
        created = Order(
            991,
            "3185231 3185231",
            "3185231",
            37,
            "CORRECAO ESTOQUE",
        )
        profile = SimpleNamespace(
            key="natal",
            label="NATAL / PARNAMIRIM",
            api=SimpleNamespace(list_orders=lambda _date: [created]),
            cache_lock=threading.RLock(),
            order_cache={},
            cache_date=None,
        )

        result = _confirm_bulk_creation(profile, preview, delays=(0.0,))

        self.assertIsNotNone(result)
        self.assertEqual(result["imported"], 1)
        self.assertTrue(result["confirmed_after_incomplete_response"])
        self.assertEqual(profile.order_cache, {991: created})



class AppSanitizeResponseTests(unittest.TestCase):
    """Verify the _sanitize_response helper that stores the official API body."""

    def setUp(self) -> None:
        from app import _sanitize_response  # noqa: PLC0415
        self._sanitize = _sanitize_response

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(self._sanitize(None), "")

    def test_dict_is_json_serialised(self) -> None:
        result = self._sanitize({"status": "ok", "message": "Baixa"})
        self.assertIn("status", result)
        self.assertIn("ok", result)

    def test_plain_string_is_returned_as_is(self) -> None:
        self.assertEqual(self._sanitize("HTTP 200 OK"), "HTTP 200 OK")

    def test_control_characters_are_stripped(self) -> None:
        result = self._sanitize("line1\x00\x01line2")
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x01", result)
        self.assertIn("line1", result)
        self.assertIn("line2", result)

    def test_response_truncated_to_2000_chars(self) -> None:
        long_text = "x" * 3000
        result = self._sanitize(long_text)
        self.assertEqual(len(result), 2000)


    def test_build_official_panel_plan_uses_visible_code_and_current_date(self) -> None:
        order = Order(
            1,
            "2648082547",
            "4238665",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        profile = SimpleNamespace(
            api=SimpleNamespace(
                removed_equipment={
                    "emta": SimpleNamespace(code="41001485"),
                }
            )
        )
        definition = SimpleNamespace(
            code="409",
            description="INSTALACAO CONCLUIDA",
            productive=True,
        )
        body = {
            "installed_equipment": [
                {"serial": "2CD8AE5D436F", "type": "emta"},
            ],
            "removed_equipment": [],
            "materials": [
                {"code": "22069613", "quantity": 2},
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            credential_path = Path(directory) / "credentials.dat"
            credential_path.write_bytes(b"configured")
            with (
                patch("app.OFFICIAL_HTTP_CREDENTIALS", credential_path),
                patch(
                    "app._official_technician_code",
                    return_value=("Z637677", "DENIS NUNES", 328898),
                ),
            ):
                plan = _build_official_panel_plan(
                    profile,
                    order,
                    definition,
                    body,
                    dt.date(2026, 7, 28),
                )

        payload = plan["payload"]["ordemservico"]
        self.assertEqual(payload["numero"], "2648082547")
        self.assertEqual(payload["dataagendamento"], "2026-07-28")
        self.assertEqual(payload["codigotecnico"], "Z637677")
        self.assertEqual(payload["codigobaixa"], 409)
        self.assertEqual(plan["technician_name"], "DENIS NUNES")
        self.assertEqual(plan["installer_id"], 328898)

    def test_official_preflight_accepts_serial_in_current_installer_stock(self) -> None:
        calls: list[tuple[str, bool]] = []

        def find_owner(serial: str, *, fresh: bool = False) -> dict:
            calls.append((serial, fresh))
            return {
                "found": True,
                "owner": {
                    "installer_id": 328898,
                    "technician_name": "DENIS NUNES",
                },
            }

        profile = SimpleNamespace(
            api=SimpleNamespace(find_serial_owner=find_owner),
        )
        plan = {
            "installer_id": 328898,
            "technician_name": "DENIS NUNES",
            "payload": {
                "ordemservico": {
                    "instaladosserializados": [
                        {"serialnumber": "2CD8AE5D436F"},
                    ],
                },
            },
        }

        _validate_official_installed_serial_ownership(profile, plan)

        self.assertEqual(calls, [("2CD8AE5D436F", True)])

    def test_official_preflight_blocks_serial_in_another_installer_stock(self) -> None:
        profile = SimpleNamespace(
            api=SimpleNamespace(
                find_serial_owner=lambda _serial, *, fresh=False: {
                    "found": True,
                    "owner": {
                        "installer_id": 249803,
                        "technician_name": "SONERREGILSON",
                    },
                }
            ),
        )
        plan = {
            "installer_id": 4070,
            "technician_name": "PAULO CAVALCANTE",
            "payload": {
                "ordemservico": {
                    "instaladosserializados": [
                        {"serialnumber": "1041212CD510"},
                    ],
                },
            },
        }

        with self.assertRaisesRegex(
            ValueError,
            (
                r"O serial 1041212CD510 nao pertence ao estoque de "
                r"PAULO CAVALCANTE; atualmente esta com SONERREGILSON"
            ),
        ):
            _validate_official_installed_serial_ownership(profile, plan)

    def test_official_preflight_blocks_serial_not_found(self) -> None:
        profile = SimpleNamespace(
            api=SimpleNamespace(
                find_serial_owner=lambda _serial, *, fresh=False: {
                    "found": False,
                    "owner": None,
                }
            ),
        )
        plan = {
            "installer_id": 4070,
            "technician_name": "PAULO CAVALCANTE",
            "payload": {
                "ordemservico": {
                    "instaladosserializados": [
                        {"serialnumber": "1041212CD510"},
                    ],
                },
            },
        }

        with self.assertRaisesRegex(
            ValueError,
            r"O serial 1041212CD510 nao foi localizado",
        ):
            _validate_official_installed_serial_ownership(profile, plan)

    def test_official_material_preparation_uses_only_payload_materials(
        self,
    ) -> None:
        plan = {
            "payload": {
                "ordemservico": {
                    "instaladosmiscelaneas": [
                        {"codigoequipamento": "22069613", "qtd": "2"},
                    ],
                },
            },
        }
        body = {
            "materials": [
                {
                    "code": "22069613",
                    "description": "CONECTOR FO CAMPO FAST SC/APC",
                    "quantity": 2,
                },
                {
                    "code": "22057705",
                    "description": "FONTE CX DIG HD",
                    "quantity": 1,
                },
            ],
        }

        self.assertEqual(
            _official_material_preparation_items(plan, body),
            [
                {
                    "code": "22069613",
                    "quantity": "2",
                    "description": "CONECTOR FO CAMPO FAST SC/APC",
                }
            ],
        )

    def test_official_panel_sends_once_and_keeps_order_pending(self) -> None:
        from app import PanelHandler, PROFILES

        class FakeOfficialClient:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            def close_order(self, payload: dict) -> ImperiumHTTPResult:
                self.calls.append(payload)
                return ImperiumHTTPResult(status=200, response=None)

        profile = PROFILES["natal"]
        order = Order(
            991001,
            "2648082547",
            "4238665",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        report_date = dt.date(2026, 7, 28)
        fake_client = FakeOfficialClient()
        responses: list[tuple[int, dict]] = []

        with tempfile.TemporaryDirectory() as directory:
            credential_path = Path(directory) / "credentials.dat"
            credential_path.write_bytes(b"configured")
            original_report = profile.close_report
            with profile.cache_lock:
                original_cache = profile.order_cache.copy()
                original_date = profile.cache_date
                original_generation = profile.cache_generation
                profile.order_cache = {order.id_os: order}
                profile.cache_date = report_date
                profile.cache_generation = max(1, original_generation + 1)
                manual_scope = _manual_close_scope(profile, order)
            profile.close_report = CloseReportStore(Path(directory), profile.key)
            handler = PanelHandler.__new__(PanelHandler)
            handler.path = f"/api/orders/{order.id_os}/close?profile=natal"
            handler._body = lambda: {
                "code": "409",
                "transport": "official_http",
                "num_os": order.num_os,
                "operation_source": "imperium_cache",
                "manual_scope": manual_scope,
                "approved_state_hash": manual_scope["state_hash"],
                "installed_equipment": [
                    {"serial": "2CD8AE5D436F", "type": "emta"},
                ],
                "removed_equipment": [],
                "materials": [
                    {"code": "22069613", "quantity": 2},
                ],
            }
            handler._json = lambda status, payload: responses.append(
                (int(status), payload)
            )
            try:
                with (
                    patch("app.OFFICIAL_HTTP_CREDENTIALS", credential_path),
                    patch(
                        "app._official_technician_code",
                        return_value=("Z637677", "DENIS NUNES", 328898),
                    ),
                    patch(
                        "app._validate_official_installed_serial_ownership"
                    ) as preflight,
                    patch.object(
                        profile.api,
                        "prepare_official_materials",
                        return_value={
                            "prepared": True,
                            "transferred": True,
                            "source": "RETORNO",
                            "shortfalls": [
                                {
                                    "code": "22069613",
                                    "transfer_quantity": 2,
                                }
                            ],
                            "resolved_materials": [
                                {
                                    "codigoequipamento": "22069613",
                                    "qtd": "1",
                                },
                                {
                                    "codigoequipamento": "22065513",
                                    "qtd": "1",
                                },
                            ],
                            "group_distributions": [
                                {
                                    "requested_code": "22069613",
                                    "group_id": 5290,
                                    "group": "CONECTOR FIBRA",
                                    "allocations": [
                                        {"code": "22069613", "quantity": "1"},
                                        {"code": "22065513", "quantity": "1"},
                                    ],
                                }
                            ],
                        },
                    ) as material_preparation,
                    patch("app._official_http_client", return_value=fake_client),
                    patch("app._start_close_confirmation") as confirmation,
                    patch.object(
                        profile.api,
                        "close_productive",
                        side_effect=AssertionError("DataSnap nao deve ser chamado"),
                    ),
                ):
                    handler.do_POST()
                    handler.do_POST()

                self.assertEqual(len(fake_client.calls), 1)
                self.assertEqual(
                    fake_client.calls[0]["ordemservico"][
                        "instaladosmiscelaneas"
                    ],
                    [
                        {"codigoequipamento": "22069613", "qtd": "1"},
                        {"codigoequipamento": "22065513", "qtd": "1"},
                    ],
                )
                self.assertEqual(preflight.call_count, 2)
                material_preparation.assert_called_once_with(
                    order,
                    [
                        {
                            "code": "22069613",
                            "quantity": "2",
                            "description": "",
                        }
                    ],
                    expected_installer_id=328898,
                )
                self.assertEqual(responses[0][0], 202)
                self.assertTrue(responses[0][1]["pending_confirmation"])
                self.assertTrue(
                    responses[0][1]["material_preparation"]["transferred"]
                )
                self.assertIn(
                    "Estoque complementado pelo RETORNO",
                    responses[0][1]["message"],
                )
                self.assertEqual(responses[1][0], 202)
                self.assertTrue(responses[1][1]["duplicate_request"])
                self.assertEqual(
                    profile.order_cache[order.id_os].status,
                    "EM CAMPO",
                )
                report = profile.close_report.list(report_date)
                self.assertEqual(len(report), 1)
                self.assertEqual(report[0]["state"], "pending")
                self.assertEqual(report[0]["transport"], "official_http")
                confirmation.assert_called_once()
            finally:
                profile.close_report = original_report
                with profile.cache_lock:
                    profile.order_cache = original_cache
                    profile.cache_date = original_date
                    profile.cache_generation = original_generation

    def test_official_panel_never_posts_when_stock_preparation_is_uncertain(
        self,
    ) -> None:
        from app import PanelHandler, PROFILES

        class FakeOfficialClient:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            def close_order(self, payload: dict) -> ImperiumHTTPResult:
                self.calls.append(payload)
                return ImperiumHTTPResult(status=200, response=None)

        profile = PROFILES["natal"]
        order = Order(
            991003,
            "2648082548",
            "4238666",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        report_date = dt.date(2026, 7, 28)
        fake_client = FakeOfficialClient()
        responses: list[tuple[int, dict]] = []

        with tempfile.TemporaryDirectory() as directory:
            credential_path = Path(directory) / "credentials.dat"
            credential_path.write_bytes(b"configured")
            original_report = profile.close_report
            with profile.cache_lock:
                original_cache = profile.order_cache.copy()
                original_date = profile.cache_date
                original_generation = profile.cache_generation
                profile.order_cache = {order.id_os: order}
                profile.cache_date = report_date
                profile.cache_generation = max(1, original_generation + 1)
                manual_scope = _manual_close_scope(profile, order)
            profile.close_report = CloseReportStore(Path(directory), profile.key)
            handler = PanelHandler.__new__(PanelHandler)
            handler.path = f"/api/orders/{order.id_os}/close?profile=natal"
            handler._body = lambda: {
                "code": "409",
                "transport": "official_http",
                "num_os": order.num_os,
                "operation_source": "imperium_cache",
                "manual_scope": manual_scope,
                "approved_state_hash": manual_scope["state_hash"],
                "installed_equipment": [],
                "removed_equipment": [],
                "materials": [
                    {"code": "22069613", "quantity": 2},
                ],
            }
            handler._json = lambda status, payload: responses.append(
                (int(status), payload)
            )
            try:
                with (
                    patch("app.OFFICIAL_HTTP_CREDENTIALS", credential_path),
                    patch(
                        "app._official_technician_code",
                        return_value=("Z637677", "DENIS NUNES", 328898),
                    ),
                    patch(
                        "app._validate_official_installed_serial_ownership"
                    ),
                    patch.object(
                        profile.api,
                        "prepare_official_materials",
                        side_effect=MaterialTransferUncertainError(
                            "A transferencia pode ter sido aplicada; "
                            "nao repita automaticamente"
                        ),
                    ) as preparation,
                    patch("app._official_http_client", return_value=fake_client),
                ):
                    handler.do_POST()

                preparation.assert_called_once()
                self.assertEqual(fake_client.calls, [])
                self.assertEqual(responses[0][0], 502)
                self.assertFalse(responses[0][1]["safe_to_retry"])
                self.assertFalse(responses[0][1]["close_sent"])
                report = profile.close_report.list(report_date)
                self.assertEqual(len(report), 1)
                self.assertEqual(report[0]["state"], "uncertain")
                self.assertFalse(report[0]["safe_to_retry"])
                self.assertEqual(report[0]["attribution"], "stock_preparation")
            finally:
                profile.close_report = original_report
                with profile.cache_lock:
                    profile.order_cache = original_cache
                    profile.cache_date = original_date
                    profile.cache_generation = original_generation

    def test_official_panel_does_not_send_when_serial_preflight_blocks(self) -> None:
        from app import PanelHandler, PROFILES

        class FakeOfficialClient:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            def close_order(self, payload: dict) -> ImperiumHTTPResult:
                self.calls.append(payload)
                return ImperiumHTTPResult(status=200, response=None)

        profile = PROFILES["natal"]
        order = Order(
            991002,
            "2647378599",
            "4234309",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        report_date = dt.date(2026, 7, 28)
        fake_client = FakeOfficialClient()
        responses: list[tuple[int, dict]] = []

        with tempfile.TemporaryDirectory() as directory:
            credential_path = Path(directory) / "credentials.dat"
            credential_path.write_bytes(b"configured")
            original_report = profile.close_report
            with profile.cache_lock:
                original_cache = profile.order_cache.copy()
                original_date = profile.cache_date
                original_generation = profile.cache_generation
                profile.order_cache = {order.id_os: order}
                profile.cache_date = report_date
                profile.cache_generation = max(1, original_generation + 1)
                manual_scope = _manual_close_scope(profile, order)
            profile.close_report = CloseReportStore(Path(directory), profile.key)
            handler = PanelHandler.__new__(PanelHandler)
            handler.path = f"/api/orders/{order.id_os}/close?profile=natal"
            handler._body = lambda: {
                "code": "409",
                "transport": "official_http",
                "num_os": order.num_os,
                "operation_source": "imperium_cache",
                "manual_scope": manual_scope,
                "approved_state_hash": manual_scope["state_hash"],
                "installed_equipment": [
                    {"serial": "1041212CD510", "type": "emta"},
                ],
                "removed_equipment": [],
                "materials": [],
            }
            handler._json = lambda status, payload: responses.append(
                (int(status), payload)
            )
            try:
                with (
                    patch("app.OFFICIAL_HTTP_CREDENTIALS", credential_path),
                    patch(
                        "app._official_technician_code",
                        return_value=("Z418624", "PAULO CAVALCANTE", 4070),
                    ),
                    patch(
                        "app._validate_official_installed_serial_ownership",
                        side_effect=ValueError(
                            "O serial 1041212CD510 nao pertence ao estoque de "
                            "PAULO CAVALCANTE; atualmente esta com SONERREGILSON"
                        ),
                    ),
                    patch("app._official_http_client", return_value=fake_client),
                ):
                    handler.do_POST()

                self.assertEqual(fake_client.calls, [])
                self.assertEqual(responses, [
                    (
                        400,
                        {
                            "ok": False,
                            "error": (
                                "O serial 1041212CD510 nao pertence ao estoque de "
                                "PAULO CAVALCANTE; atualmente esta com SONERREGILSON"
                            ),
                        },
                    ),
                ])
                self.assertEqual(profile.close_report.list(report_date), [])
            finally:
                profile.close_report = original_report
                with profile.cache_lock:
                    profile.order_cache = original_cache
                    profile.cache_date = original_date
                    profile.cache_generation = original_generation




class OfficialImperiumReadApiTests(unittest.TestCase):
    @staticmethod
    def _handler(path: str, role: str = "controller"):
        from app import PanelHandler

        responses = []
        handler = PanelHandler.__new__(PanelHandler)
        handler.path = path
        handler._security_preflight = lambda method, request_path: True
        handler._current_user = lambda: {"id": 1, "username": "teste", "role": role}
        handler._json = lambda status, payload: responses.append((int(status), payload))
        return handler, responses

    def test_official_session_exposes_jader_identity_without_token(self) -> None:
        client = SimpleNamespace(
            login_metadata=lambda: {
                "user_id": 10,
                "stock_id": 77,
                "group": "INSTALADOR",
                "username": "ALAN",
            }
        )
        handler, responses = self._handler(
            "/api/imperium-official/session?profile=natal"
        )
        with patch("app._official_http_client", return_value=client):
            handler.do_GET()

        self.assertEqual(responses[0][0], 200)
        payload = responses[0][1]
        self.assertEqual(payload["identity"]["stock_id"], 77)
        self.assertNotIn("token", json.dumps(payload).casefold())
        self.assertEqual(payload["credential_scope"], "server_integration")

    def test_official_stock_items_use_confirmed_read_endpoint(self) -> None:
        calls = []
        client = SimpleNamespace(
            stock_items=lambda stock_id: calls.append(stock_id) or [
                {"code": "22026189", "quantity": 5}
            ]
        )
        handler, responses = self._handler(
            "/api/imperium-official/stocks/77/items?profile=natal"
        )
        with patch("app._official_http_client", return_value=client):
            handler.do_GET()

        self.assertEqual(calls, [77])
        self.assertEqual(responses[0][0], 200)
        self.assertEqual(responses[0][1]["items"][0]["quantity"], 5)

    def test_official_read_api_rejects_viewer(self) -> None:
        handler, responses = self._handler(
            "/api/imperium-official/stocks?profile=natal",
            role="viewer",
        )
        with patch("app._official_http_client") as client_factory:
            handler.do_GET()

        client_factory.assert_not_called()
        self.assertEqual(responses[0][0], 403)

    def test_material_inventory_without_optional_technician_query(self) -> None:
        from app import PROFILES

        profile = PROFILES["natal"]
        order = Order(2207229, "2656834282", "1295258", 10, "ADESAO - INSTALAR PONTO VIRTUA")
        handler, responses = self._handler(
            "/api/orders/2207229/material-inventory?profile=natal"
        )
        with profile.cache_lock:
            original_cache = profile.order_cache.copy()
            profile.order_cache[order.id_os] = order
        try:
            with (
                patch("app._live_technician_evidence", return_value={}),
                patch.object(
                    profile.api,
                    "list_material_inventory",
                    return_value={"ok": True, "materials": []},
                ) as inventory,
            ):
                handler.do_GET()
            inventory.assert_called_once_with(order.id_os, installer_id=None)
            self.assertEqual(responses[0][0], 200)
        finally:
            with profile.cache_lock:
                profile.order_cache = original_cache


if __name__ == "__main__":
    unittest.main()
