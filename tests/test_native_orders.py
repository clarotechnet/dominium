import base64
import datetime as dt
import json
import struct
import threading
import unittest
from pathlib import Path
from unittest import mock

from bulk_orders import build_bulk_preview
from imperium_api import ImperiumAPI
from manual_orders import ManualOrderProtocol
from native_orders import (
    NativeContractContext,
    NativeOrderProtocol,
    nullable_text,
    short_text,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "native_order_protocol_templates.json"
MANUAL_TEMPLATE_PATH = ROOT / "manual_order_protocol_templates.json"


class NativeOrderProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.templates = json.loads(TEMPLATE_PATH.read_text(encoding="ascii"))

    def _captured_context(self, captured: dict) -> NativeContractContext:
        return NativeContractContext(
            contract=captured["contract"],
            os_numbers=(),
            client=captured["client"],
            address=captured["address"],
            city=captured["city"],
            person_id=captured["person_id"],
            number=captured["number"],
            complement=captured["complement"],
            district=captured["district"],
            state=captured["state"],
            zip_code=captured["zip_code"],
            address_type=captured["address_type"],
        )

    def test_reconstructs_every_captured_native_packet(self) -> None:
        captured_date = dt.date.fromisoformat(self.templates["captured_date"])
        for profile_key, values in self.templates["profiles"].items():
            with self.subTest(profile=profile_key):
                captured = values["captured"]
                protocol = NativeOrderProtocol(
                    TEMPLATE_PATH,
                    profile_key,
                    captured["controller_id"],
                )
                packet = protocol.build_packet(
                    self._captured_context(captured),
                    captured["num_os"],
                    captured["service_name"],
                    captured["technician_id"],
                    captured["technician_name"],
                    captured_date,
                )
                expected = bytearray(
                    b"#Dsp"
                    + base64.b64decode(values["prefix"])
                    + base64.b64decode(values["record"])
                    + base64.b64decode(values["suffix"])
                )
                record_position = 4 + len(base64.b64decode(values["prefix"]))
                expected[record_position : record_position + 4] = struct.pack(
                    "<i", -1
                )
                self.assertEqual(packet, bytes(expected))

    def test_updates_dynamic_packet_lengths(self) -> None:
        values = self.templates["profiles"]["natal"]
        captured = values["captured"]
        protocol = NativeOrderProtocol(
            TEMPLATE_PATH,
            "natal",
            captured["controller_id"],
        )
        context = self._captured_context(captured)
        context = NativeContractContext(
            **{
                **context.__dict__,
                "client": "CLIENTE COM NOME MAIOR",
                "address": "AVENIDA DE TESTE COM NOME MAIOR",
                "complement": "APARTAMENTO 1201",
            }
        )
        packet = protocol.build_packet(
            context,
            captured["num_os"],
            captured["service_name"],
            captured["technician_id"],
            "TECNICO COM NOME DIFERENTE",
            dt.date(2026, 7, 18),
        )
        self.assertEqual(struct.unpack_from("<I", packet, 8)[0], len(packet) - 27)
        self.assertIn(short_text("CLIENTE COM NOME MAIOR"), packet)
        self.assertIn(short_text("APARTAMENTO 1201"), packet)

    def test_parses_contract_context_and_existing_orders(self) -> None:
        contract = "4229178"
        os_number = "2646521329"
        row = b"".join(
            (
                short_text(os_number),
                short_text(contract),
                short_text("NET"),
                short_text(""),
                b"\x01\x00",
                short_text("NTL01A"),
                short_text("CLIENTE - 42"),
                short_text("RUA TESTE"),
                short_text("C"),
                struct.pack("<I", 313101),
                short_text("DALTON"),
                b"\x00" * 6,
                short_text("NATAL"),
                b"\x00\x00",
                struct.pack("<I", 42),
                short_text("100"),
                nullable_text("APTO 12"),
                short_text("CENTRO"),
                short_text("RN"),
                short_text("59000000"),
            )
        )
        context = NativeOrderProtocol.parse_contract(row, contract)
        self.assertEqual(context.os_numbers, (os_number,))
        self.assertEqual(context.client, "CLIENTE - 42")
        self.assertEqual(context.address_type, "CASA")
        self.assertEqual(context.complement, "APTO 12")
        self.assertTrue(NativeOrderProtocol.contains_os(row, os_number))

    def test_parses_manual_order_with_optional_contract_fields(self) -> None:
        contract = "3297200"
        compact_os_number = "32972003297200"
        row = b"".join(
            (
                short_text(compact_os_number),
                short_text(contract),
                struct.pack("<I", 72),
                short_text("CORRECAO DE ESTOQUE"),
                b"\x00" * 120,
                short_text("NET"),
                short_text("VERMELHO"),
                b"\x02\x00",
                short_text("HERICA SHEYLA DA SILVA SANTOS"),
                short_text("RIO PITIMB"),
                struct.pack("<I", 336639),
                short_text("LUIZ F."),
                short_text("N"),
                short_text("N"),
                b"\x03\x00\x00\x00\x00\x00",
                short_text("PARNAMIRIM"),
                short_text("400"),
                short_text("CORRECAO DE CADASTRO"),
                struct.pack("<I", 1284),
                short_text("547"),
                short_text("CASA B"),
                short_text("EMAUS"),
                short_text("RN"),
                short_text("09070404460"),
                short_text("59149120"),
            )
        )

        context = NativeOrderProtocol.parse_contract(row, contract)

        self.assertEqual(context.client, "HERICA SHEYLA DA SILVA SANTOS")
        self.assertEqual(context.city, "PARNAMIRIM")
        self.assertEqual(context.zip_code, "59149120")
        self.assertEqual(context.address_type, "CASA")
        self.assertTrue(
            NativeOrderProtocol.contains_os(row, f"{contract} {contract}")
        )

    def test_exposes_only_captured_profiles_and_services(self) -> None:
        natal = NativeOrderProtocol(TEMPLATE_PATH, "natal", 313101)
        mossoro = NativeOrderProtocol(TEMPLATE_PATH, "mossoro", 20857)
        recife = NativeOrderProtocol(TEMPLATE_PATH, "recife", 1766)
        self.assertTrue(natal.enabled)
        self.assertIn("CORRECAO ESTOQUE", natal.services)
        self.assertEqual(
            list(mossoro.services),
            ["ENVIO DE CHIP VIA TECNICO"],
        )
        self.assertFalse(recife.enabled)
        self.assertEqual(recife.services, {})

    def test_contract_query_requires_exactly_seven_digits(self) -> None:
        protocol = NativeOrderProtocol(TEMPLATE_PATH, "natal", 313101)
        with self.assertRaisesRegex(ValueError, "7 digitos"):
            protocol.contract_query("1234")

    def test_fixed_client_123_context_keeps_informed_contract(self) -> None:
        api = object.__new__(ImperiumAPI)
        api.profile_key = "natal"

        context = api._native_contract_context(b"", "1234566", "fixed_123")

        self.assertEqual(context.contract, "1234566")
        self.assertEqual(context.client, "CLIENTE 123")
        self.assertEqual(context.person_id, 189368)
        self.assertEqual(context.address, "BUMBA-MEU-BOI")
        self.assertEqual(context.city, "NATAL")

    def test_fixed_client_123_is_rejected_outside_natal(self) -> None:
        api = object.__new__(ImperiumAPI)
        api.profile_key = "fortaleza"

        with self.assertRaisesRegex(ValueError, "somente para Natal"):
            api._native_contract_context(b"", "1234566", "fixed_123")

    def test_fixed_client_123_builds_every_natal_service_packet(self) -> None:
        protocol = NativeOrderProtocol(TEMPLATE_PATH, "natal", 313101)
        manual = ManualOrderProtocol(MANUAL_TEMPLATE_PATH)

        for service in protocol.services:
            with self.subTest(service=service):
                mapped_service = protocol.service(service)
                packet = manual.build_packet(
                    "1234566 1234566",
                    "1234566",
                    mapped_service,
                    3857,
                    "TECNICO TESTE",
                    dt.date.today(),
                )
                self.assertIn(short_text("cliente 123"), packet)
                self.assertIn(short_text("BUMBA-MEU-BOI"), packet)
                self.assertIn(short_text("1234566"), packet)
                self.assertIn(short_text(mapped_service.code), packet)
                self.assertIn(short_text(mapped_service.name), packet)

    def test_manual_packet_reconstructs_validated_capture_exactly(self) -> None:
        native = NativeOrderProtocol(TEMPLATE_PATH, "natal", 313101)
        manual = ManualOrderProtocol(MANUAL_TEMPLATE_PATH)
        captured = manual.captured

        packet = manual.build_packet(
            captured["os_number"],
            captured["contract"],
            native.service("CORRECAO ESTOQUE"),
            captured["installer_id"],
            captured["installer_name"],
            dt.date.fromisoformat(captured["execution_date"]),
        )

        self.assertEqual(packet, manual.template)

    def test_manual_packet_preserves_informed_contract(self) -> None:
        native = NativeOrderProtocol(TEMPLATE_PATH, "natal", 313101)
        manual = ManualOrderProtocol(MANUAL_TEMPLATE_PATH)

        packet = manual.build_packet(
            "3121233 3121233",
            "3121233",
            native.service("RETIRADA FORA TOA"),
            3857,
            "GABRIEL SENA DESC",
            dt.date.today(),
        )

        self.assertIn(short_text("3121233 3121233"), packet)
        self.assertIn(short_text("3121233"), packet)
        self.assertIn(short_text("RETFORATOA"), packet)
        self.assertNotIn(short_text("CORRECAO ESTOQUE"), packet)

    def test_manual_packet_rejects_invalid_contract(self) -> None:
        native = NativeOrderProtocol(TEMPLATE_PATH, "natal", 313101)
        manual = ManualOrderProtocol(MANUAL_TEMPLATE_PATH)

        with self.assertRaisesRegex(ValueError, "Contrato invalido"):
            manual.build_packet(
                "1234 1234",
                "1234",
                native.service("CORRECAO ESTOQUE"),
                3857,
                "TECNICO TESTE",
                dt.date.today(),
            )

    def test_native_creation_uses_complete_manual_packet_for_client_123(self) -> None:
        captured = {}

        class NativeProtocol:
            enabled = True
            services = {"CORRECAO ESTOQUE": object()}

            @staticmethod
            def service(_value):
                return object()

            @staticmethod
            def contains_os(_payload, _os_number):
                return False

        class ManualProtocol:
            apply_method = "TDtmOrdemServico.AS_ApplyUpdates"

            @staticmethod
            def build_packet(
                os_number,
                contract,
                _service,
                _technician_id,
                _technician_name,
                _order_date,
            ):
                captured["os_number"] = os_number
                captured["contract"] = contract
                raise ValueError("interromper antes da escrita")

        api = object.__new__(ImperiumAPI)
        api.profile_key = "natal"
        api.native_order_protocol = NativeProtocol()
        api.manual_order_protocol = ManualProtocol()
        api._operation_lock = threading.Lock()
        api._native_contract_payload = lambda _contract: self.fail(
            "O modo CLIENTE 123 nao deve consultar o cadastro do contrato"
        )
        api.list_orders = lambda _date: []
        preview = build_bulk_preview(
            "1234566",
            "TECNICO TESTE",
            "natal",
            service="CORRECAO ESTOQUE",
        )

        result = api.create_native_orders(
            preview,
            123,
            "TECNICO TESTE",
            client_mode="fixed_123",
        )

        self.assertEqual(captured["contract"], "1234566")
        self.assertEqual(captured["os_number"], "1234566 1234566")
        self.assertEqual(result["not_imported"], 1)
        self.assertIn(
            "interromper antes da escrita",
            result["orders"][0]["import_status"],
        )

    def test_native_confirmation_matches_number_and_contract_from_daily_list(self) -> None:
        api = object.__new__(ImperiumAPI)
        api.list_orders = lambda _date: [
            type(
                "OrderStub",
                (),
                {"num_os": "31212333121233", "contract": "3121233"},
            )()
        ]

        confirmed, error = api._confirm_native_order(
            "3121233",
            "3121233 3121233",
            delays=(0.0,),
        )

        self.assertTrue(confirmed)
        self.assertIsNone(error)

    def test_native_confirmation_waits_for_late_server_visibility(self) -> None:
        api = object.__new__(ImperiumAPI)
        calls = 0
        expected_date = dt.date(2026, 7, 27)

        def list_orders(query_date):
            nonlocal calls
            self.assertEqual(query_date, expected_date)
            calls += 1
            if calls < 3:
                return []
            return [
                type(
                    "OrderStub",
                    (),
                    {"num_os": "12312221231222", "contract": "1231222"},
                )()
            ]

        api.list_orders = list_orders
        with mock.patch("imperium_api.time.sleep") as sleep:
            confirmed, error = api._confirm_native_order(
                "1231222",
                "1231222 1231222",
                query_date=expected_date,
                delays=(0.5, 1.5, 3.0),
            )

        self.assertTrue(confirmed)
        self.assertIsNone(error)
        self.assertEqual(calls, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [0.5, 1.5, 3.0],
        )

    def test_native_confirmation_recovers_from_intermediate_read_error(self) -> None:
        api = object.__new__(ImperiumAPI)
        responses = iter(
            [
                OSError("consulta temporariamente indisponivel"),
                [
                    type(
                        "OrderStub",
                        (),
                        {"num_os": "76543217654321", "contract": "7654321"},
                    )()
                ],
            ]
        )

        def list_orders(_query_date):
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return response

        api.list_orders = list_orders
        with mock.patch("imperium_api.time.sleep"):
            confirmed, error = api._confirm_native_order(
                "7654321",
                "7654321 7654321",
                delays=(0.0, 0.0),
            )

        self.assertTrue(confirmed)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
