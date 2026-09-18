import datetime as dt
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import (
    InstallerMismatchUnresolvedError,
    InstallerReassignmentFailedError,
    InstallerReassignmentUnconfirmedError,
    PanelHandler,
    _reconcile_order_installer_with_toa,
    _resolve_imperium_installer_for_toa,
)
from datasnap_client import DataSnapError
from imperium_api import Order


class InstallerReassignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock_technicians = [
            {
                "stock_id": 304,
                "stock_name": "JANDERSON COSTA",
                "installer_id": 339175,
                "technician_name": "JANDERSON COSTA",
            },
            {
                "stock_id": 306,
                "stock_name": "GUILHERME HENRIQUE",
                "installer_id": 339177,
                "technician_name": "GUILHERME HENRIQUE",
            },
            {
                "stock_id": 310,
                "stock_name": "CARLOS SILVA 1",
                "installer_id": 339180,
                "technician_name": "CARLOS EDUARDO SILVA",
            },
            {
                "stock_id": 311,
                "stock_name": "CARLOS SILVA 2",
                "installer_id": 339181,
                "technician_name": "CARLOS ROBERTO SILVA",
            },
            {
                "stock_id": 312,
                "stock_name": "MELQUISEDEQUE",
                "installer_id": 339182,
                "technician_name": "MELQUISEDEQUE",
            },
            {
                "stock_id": 313,
                "stock_name": "SONERREGILSON",
                "installer_id": 339183,
                "technician_name": "SONERREGILSON",
            },
        ]
        self.order = Order(
            1837422,
            "2652317082",
            "4281242",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        self.api = MagicMock()
        self.api.list_stock_technicians.return_value = list(self.stock_technicians)
        self.api.installer_change_enabled = True
        self.profile = SimpleNamespace(
            key="natal",
            label="NATAL / PARNAMIRIM",
            api=self.api,
            installer_change_enabled=True,
            cache_lock=MagicMock(),
            installer_overrides={},
            _stock_technicians_cache=None,
        )
        self.profile.cache_lock.__enter__ = MagicMock(return_value=None)
        self.profile.cache_lock.__exit__ = MagicMock(return_value=None)

    def test_resolve_exact_match(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"name": "JANDERSON COSTA"},
        )
        self.assertIsNotNone(tech)
        self.assertEqual(tech["installer_id"], 339175)
        self.assertEqual(method, "exact")

    def test_resolve_same_technician_name(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"name": "JANDERSON DA COSTA SILVA"},
        )
        self.assertIsNotNone(tech)
        self.assertEqual(tech["installer_id"], 339175)
        self.assertEqual(method, "same_name")

    def test_resolve_by_login(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"login": "Z657613"},
        )
        self.assertIsNotNone(tech)
        self.assertEqual(tech["installer_id"], 339175)

    def test_resolve_explicit_alias_melquisedeque(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"name": "ESLI MELQUISEDEQUE DA SILVA"},
        )
        self.assertIsNotNone(tech)
        self.assertEqual(tech["installer_id"], 339182)
        self.assertEqual(method, "explicit_alias")

    def test_resolve_explicit_alias_somerregilson(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"name": "SOMERREGILSON DA SILVA MEDEIROS"},
        )
        self.assertIsNotNone(tech)
        self.assertEqual(tech["installer_id"], 339183)
        self.assertEqual(method, "explicit_alias")

    def test_resolve_returns_none_when_technician_not_found(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"name": "TECNICO TOTALMENTE INEXISTENTE NO SISTEMA"},
        )
        self.assertIsNone(tech)
        self.assertEqual(method, "not_found")

    def test_resolve_returns_none_when_ambiguous(self) -> None:
        tech, method = _resolve_imperium_installer_for_toa(
            self.profile,
            {"name": "CARLOS SILVA"},
        )
        self.assertIsNone(tech)
        self.assertTrue(method.startswith("ambiguous_"))

    def test_no_divergence_does_not_call_change_installer(self) -> None:
        self.api.order_installer.return_value = {
            "installer_id": 339175,
            "installer_name": "JANDERSON COSTA",
        }
        body = {
            "toa_technician": {
                "name": "JANDERSON COSTA",
                "login": "Z657613",
            }
        }
        result = _reconcile_order_installer_with_toa(
            self.profile,
            self.order,
            body,
            dt.date.today(),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["installer_id"], 339175)
        self.api.change_order_installer.assert_not_called()

    def test_divergence_reassigns_installer_successfully(self) -> None:
        # Initial call: order in Imperium is with Guilherme
        # After change: order in Imperium is with Janderson
        self.api.order_installer.side_effect = [
            {"installer_id": 339177, "installer_name": "GUILHERME HENRIQUE"},
            {"installer_id": 339175, "installer_name": "JANDERSON COSTA"},
        ]
        body = {
            "toa_technician": {
                "name": "JANDERSON COSTA",
                "login": "Z657613",
            }
        }
        with patch("app.OPERATION_GATE"):
            result = _reconcile_order_installer_with_toa(
                self.profile,
                self.order,
                body,
                dt.date.today(),
            )
        self.assertEqual(result["installer_id"], 339175)
        self.assertEqual(result["installer_name"], "JANDERSON COSTA")
        self.api.change_order_installer.assert_called_once_with(1837422, 339175)
        self.assertEqual(
            self.profile.installer_overrides[1837422],
            "JANDERSON COSTA",
        )

    def test_divergence_raises_unresolved_when_technician_cannot_be_found(self) -> None:
        self.api.order_installer.return_value = {
            "installer_id": 339177,
            "installer_name": "GUILHERME HENRIQUE",
        }
        body = {
            "toa_technician": {
                "name": "TECNICO DESCONHECIDO",
            }
        }
        with self.assertRaises(InstallerMismatchUnresolvedError) as ctx:
            _reconcile_order_installer_with_toa(
                self.profile,
                self.order,
                body,
                dt.date.today(),
            )
        self.assertEqual(ctx.exception.code, "installer_mismatch_unresolved")
        self.api.change_order_installer.assert_not_called()

    def test_divergence_raises_unresolved_when_ambiguous(self) -> None:
        self.api.order_installer.return_value = {
            "installer_id": 339177,
            "installer_name": "GUILHERME HENRIQUE",
        }
        body = {
            "toa_technician": {
                "name": "CARLOS SILVA",
            }
        }
        with self.assertRaises(InstallerMismatchUnresolvedError) as ctx:
            _reconcile_order_installer_with_toa(
                self.profile,
                self.order,
                body,
                dt.date.today(),
            )
        self.assertEqual(ctx.exception.code, "installer_mismatch_unresolved")
        self.api.change_order_installer.assert_not_called()

    def test_divergence_raises_unresolved_when_change_disabled(self) -> None:
        self.profile.installer_change_enabled = False
        self.api.order_installer.return_value = {
            "installer_id": 339177,
            "installer_name": "GUILHERME HENRIQUE",
        }
        body = {
            "toa_technician": {
                "name": "JANDERSON COSTA",
                "login": "Z657613",
            }
        }
        with self.assertRaises(InstallerMismatchUnresolvedError) as ctx:
            _reconcile_order_installer_with_toa(
                self.profile,
                self.order,
                body,
                dt.date.today(),
            )
        self.assertEqual(ctx.exception.code, "installer_mismatch_unresolved")
        self.api.change_order_installer.assert_not_called()

    def test_divergence_raises_reassignment_failed_when_api_fails(self) -> None:
        self.api.order_installer.return_value = {
            "installer_id": 339177,
            "installer_name": "GUILHERME HENRIQUE",
        }
        self.api.change_order_installer.side_effect = DataSnapError("Falha de conexao")
        body = {
            "toa_technician": {
                "name": "JANDERSON COSTA",
                "login": "Z657613",
            }
        }
        with patch("app.OPERATION_GATE"):
            with self.assertRaises(InstallerReassignmentFailedError) as ctx:
                _reconcile_order_installer_with_toa(
                    self.profile,
                    self.order,
                    body,
                    dt.date.today(),
                )
        self.assertEqual(ctx.exception.code, "installer_reassignment_failed")

    def test_divergence_raises_unconfirmed_when_confirmation_diverges(self) -> None:
        # change_order_installer returns, but confirmation still returns Guilherme
        self.api.order_installer.side_effect = [
            {"installer_id": 339177, "installer_name": "GUILHERME HENRIQUE"},
            {"installer_id": 339177, "installer_name": "GUILHERME HENRIQUE"},
        ]
        body = {
            "toa_technician": {
                "name": "JANDERSON COSTA",
                "login": "Z657613",
            }
        }
        with patch("app.OPERATION_GATE"):
            with self.assertRaises(InstallerReassignmentUnconfirmedError) as ctx:
                _reconcile_order_installer_with_toa(
                    self.profile,
                    self.order,
                    body,
                    dt.date.today(),
                )
        self.assertEqual(ctx.exception.code, "installer_reassignment_unconfirmed")


class CloseEndpointReassignmentIntegrationTests(unittest.TestCase):
    def test_close_endpoint_returns_422_on_unresolved_installer(self) -> None:
        responses = []
        handler = PanelHandler.__new__(PanelHandler)
        handler.path = "/api/orders/1837422/close?profile=natal"
        handler._json = lambda status, payload: responses.append((int(status), payload))
        handler._body = lambda: {
            "num_os": "2652317082",
            "code": "409",
            "transport": "official_http",
            "toa_technician": {"name": "TECNICO INEXISTENTE"},
        }
        handler._current_user = lambda: {"id": 1, "username": "admin"}
        order = Order(
            1837422,
            "2652317082",
            "4281242",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        api = MagicMock()
        api.order_installer.return_value = {
            "installer_id": 339177,
            "installer_name": "GUILHERME HENRIQUE",
        }
        api.list_stock_technicians.return_value = []
        profile = SimpleNamespace(
            key="natal",
            label="NATAL / PARNAMIRIM",
            close_enabled=True,
            installer_change_enabled=True,
            api=api,
            order_cache={1837422: order},
            cache_lock=MagicMock(),
            cache_date=dt.date.today(),
            close_report=MagicMock(),
            failure_cache={},
            installer_overrides={},
            _stock_technicians_cache=None,
        )
        profile.cache_lock.__enter__ = MagicMock(return_value=None)
        profile.cache_lock.__exit__ = MagicMock(return_value=None)

        with (
            patch("app._profile_from_query", return_value=profile),
            patch("app._validated_close_operation"),
            patch("app._resolve_close_definition", return_value=SimpleNamespace(code="409", description="INSTALACAO", productive=True)),
            patch("app._record_failure"),
            patch("app._sync_operational_close_reports"),
        ):
            handler.do_POST()

        self.assertEqual(len(responses), 1)
        status, payload = responses[0]
        self.assertEqual(status, 422)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["reason"], "installer_mismatch_unresolved")
        self.assertTrue(payload["human_review"])

    def test_close_endpoint_reassigns_and_successfully_closes_reference_case(self) -> None:
        responses = []
        handler = PanelHandler.__new__(PanelHandler)
        handler.path = "/api/orders/1837422/close?profile=natal"
        handler._json = lambda status, payload: responses.append((int(status), payload))
        handler._body = lambda: {
            "num_os": "2652317082",
            "code": "409",
            "transport": "official_http",
            "toa_technician": {
                "name": "JANDERSON COSTA",
                "login": "Z657613",
            },
            "installed_equipment": [
                {"serial": "1041212CD510", "type": "emta"},
            ],
            "removed_equipment": [],
            "materials": [],
        }
        handler._current_user = lambda: {"id": 1, "username": "admin"}
        order = Order(
            1837422,
            "2652317082",
            "4281242",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
            status="EM CAMPO",
        )
        api = MagicMock()
        # First call before reassignment: Guilherme
        # Second call in confirmation: Janderson
        # Third call in _official_technician_code: Janderson
        api.order_installer.side_effect = [
            {"installer_id": 339177, "installer_name": "GUILHERME HENRIQUE"},
            {"installer_id": 339175, "installer_name": "JANDERSON COSTA"},
            {"installer_id": 339175, "installer_name": "JANDERSON COSTA"},
        ]
        api.list_stock_technicians.return_value = [
            {
                "stock_id": 304,
                "stock_name": "JANDERSON COSTA",
                "installer_id": 339175,
                "technician_name": "JANDERSON COSTA",
            },
            {
                "stock_id": 306,
                "stock_name": "GUILHERME HENRIQUE",
                "installer_id": 339177,
                "technician_name": "GUILHERME HENRIQUE",
            },
        ]
        api.find_serial_owner.return_value = {
            "found": True,
            "owner": {
                "stock_id": 304,
                "stock_name": "JANDERSON COSTA",
                "installer_id": 339175,
                "technician_name": "JANDERSON COSTA",
            },
        }
        api.removed_equipment = {}
        api.prepare_official_materials.return_value = {"prepared": True, "resolved_materials": []}
        api.installer_change_enabled = True

        profile = SimpleNamespace(
            key="natal",
            label="NATAL / PARNAMIRIM",
            close_enabled=True,
            installer_change_enabled=True,
            api=api,
            order_cache={1837422: order},
            cache_lock=MagicMock(),
            cache_date=dt.date.today(),
            cache_generation=1,
            operations=MagicMock(),
            close_report=MagicMock(),
            failure_cache={},
            installer_overrides={},
            _stock_technicians_cache=None,
        )
        profile.cache_lock.__enter__ = MagicMock(return_value=None)
        profile.cache_lock.__exit__ = MagicMock(return_value=None)
        profile.close_report.begin.return_value = ({"request_id": "req-1", "state": "running"}, False)

        fake_client = MagicMock()
        fake_client.close_order.return_value = SimpleNamespace(
            status=200, response={"status": "ok"}
        )

        with (
            patch("app._profile_from_query", return_value=profile),
            patch("app._validated_close_operation"),
            patch(
                "app._resolve_close_definition",
                return_value=SimpleNamespace(
                    code="409",
                    description="INSTALACAO",
                    productive=True,
                ),
            ),
            patch("app.OFFICIAL_HTTP_CREDENTIALS") as cred_mock,
            patch("app._official_http_client", return_value=fake_client),
            patch("app.OPERATION_GATE"),
            patch("app._sync_operational_close_reports"),
        ):
            cred_mock.is_file.return_value = True
            handler.do_POST()

        api.change_order_installer.assert_called_once_with(1837422, 339175)
        self.assertEqual(len(fake_client.close_order.call_args_list), 1)
        self.assertEqual(len(responses), 1)
        status, payload = responses[0]
        self.assertEqual(status, 202)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
