import hashlib
import struct
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from datasnap_client import DataSnapError
from imperium_api import (
    _MaterialTransferReconnectRequired,
    CloseConfirmationUncertainError,
    CloseStateConflictError,
    DetailContext,
    Equipment,
    ImperiumAPI,
    MAIN_FRAGMENT_TIMEOUT,
    MAIN_QUERY_TIMEOUT,
    MaterialTransferUncertainError,
    Order,
    SERVICE_TYPE,
    StockMaterial,
    STATUS,
)


class ApplyPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = ImperiumAPI()

    def test_installer_context_keeps_open_order_layout(self) -> None:
        record = struct.pack("<I", 313363) + self.api._short_text(
            "ADRIANO COSTA"
        )

        self.assertEqual(
            self.api._installer_context_from_record(record, 0),
            (313363, "ADRIANO COSTA"),
        )

    def test_installer_context_skips_close_code_on_completed_order(self) -> None:
        record = (
            struct.pack("<I", 44)
            + self.api._short_text("409")
            + self.api._short_text("INSTALAÇÃO CONCLUIDA")
            + bytes(12)
            + struct.pack("<I", 287)
            + struct.pack("<I", 284992)
            + self.api._short_text("ALMIR FAUSTINO")
        )

        self.assertEqual(
            self.api._installer_context_from_record(record, 0),
            (284992, "ALMIR FAUSTINO"),
        )

    def test_named_virtual_stock_id_finds_retorno_without_installer(self) -> None:
        payload = (
            b"prefix"
            + struct.pack("<I", 2)
            + b"\x07RETORNO\x01N\x01N"
            + b"suffix"
        )

        self.assertEqual(
            self.api._named_virtual_stock_id(payload, "RETORNO"),
            2,
        )

    def test_named_virtual_stock_id_blocks_when_retorno_is_missing(self) -> None:
        with self.assertRaisesRegex(
            DataSnapError,
            "RETORNO nao foi localizado",
        ):
            self.api._named_virtual_stock_id(b"sem estoque virtual", "RETORNO")

    def test_named_virtual_stock_id_blocks_ambiguous_retorno(self) -> None:
        payload = (
            struct.pack("<I", 2)
            + b"\x07RETORNO"
            + struct.pack("<I", 204)
            + b"\x07RETORNO"
        )

        with self.assertRaisesRegex(DataSnapError, "RETORNO ficou ambiguo"):
            self.api._named_virtual_stock_id(payload, "RETORNO")

    def test_toa_correlated_material_receives_retorno_balance(self) -> None:
        materials = [
            {
                "code": "22057657",
                "name": "CABO DROP 1FO LOW F FIG8 CINZA",
                "stock_quantity": 0,
                "quantity": 89,
            }
        ]

        self.api._attach_return_stock_preview(
            materials,
            {"22057657": Decimal("120")},
        )

        self.assertEqual(materials[0]["return_stock_name"], "RETORNO")
        self.assertEqual(materials[0]["return_stock_quantity"], "120")

    def test_dynamic_header_and_detail_mask_for_all_close_packets(self) -> None:
        record = b"record:" + self.api.old_mask + b":end"
        record_mask = bytes(range(19))

        for close_code in self.api.close_codes.values():
            for suffix in close_code.suffixes:
                with self.subTest(
                    code=close_code.code,
                    suffix_length=len(suffix),
                ):
                    blob = self.api._assemble_apply_blob(
                        record,
                        record_mask,
                        suffix,
                    )
                    packet = blob[4:]
                    prefix_length = len(self.api.apply_packet_prefix)

                    self.assertEqual(blob[:4], b"#Dsp")
                    self.assertEqual(
                        packet[prefix_length - 19 : prefix_length],
                        record_mask,
                    )
                    page_delta = (
                        packet[1] - self.api.apply_packet_prefix[1]
                    )
                    self.assertEqual(
                        struct.unpack_from("<H", packet, 2)[0]
                        + page_delta * 256,
                        len(packet) - 7182,
                    )
                    self.assertEqual(
                        struct.unpack_from("<I", packet, 4)[0],
                        len(packet) - 23,
                    )
                    self.assertEqual(packet.count(self.api.old_mask), 0)
                    self.assertEqual(packet.count(self.api.new_mask), 1)
                    self.assertTrue(packet.endswith(suffix))

    def test_close_packet_accepts_detail_without_optional_empty_dataset(self) -> None:
        record = b"record:" + self.api.old_mask[:18] + b"\x01\x00\x00\x00:next"
        record_mask = bytes(range(19))
        suffix = self.api.close_code("0").suffixes[0]

        blob = self.api._assemble_apply_blob(record, record_mask, suffix)
        packet = blob[4:]

        self.assertNotIn(self.api.old_mask[:18], packet)
        self.assertIn(self.api.new_mask[:18] + b"\x01\x00\x00\x00:next", packet)

    def test_company_connection_profile(self) -> None:
        api = ImperiumAPI(
            port=596,
            company="fortaleza",
            controller_id=49127,
        )

        self.assertEqual(api.company, "FORTALEZA")
        self.assertEqual(api.port, 596)
        self.assertEqual(api.controller_id, 49127)
        profile_controller = struct.pack("<I", 49127)
        captured_controller = struct.pack("<I", 313101)
        for close_code in api.close_codes.values():
            for suffix in close_code.suffixes:
                self.assertEqual(suffix.count(profile_controller), 1)
                self.assertNotIn(captured_controller, suffix)

    def test_main_query_uses_official_all_services_filter(self) -> None:
        field = "IdTipoServico".encode("utf-16le")
        captured_filter = field + struct.pack("<II", 8, 1) + b"3"
        all_services_filter = field + struct.pack("<II", 8, 1) + b"%"

        query = self.api._main_query_for(self.api.captured_date)

        self.assertNotIn(captured_filter, query)
        self.assertEqual(query.count(all_services_filter), 1)
        self.assertEqual(SERVICE_TYPE, "TODOS")
        self.assertEqual(STATUS, "EM CAMPO")

    def test_main_query_combines_status_and_service_type_filters(self) -> None:
        status_field = "Status".encode("utf-16le")
        service_field = "IdTipoServico".encode("utf-16le")
        query = self.api._main_query_for(
            self.api.captured_date,
            status="completed",
            service_type="disconnection",
        )

        self.assertIn(status_field + struct.pack("<II", 8, 1) + b"2", query)
        self.assertIn(service_field + struct.pack("<II", 8, 1) + b"3", query)

    def test_main_query_rejects_unknown_filter(self) -> None:
        with self.assertRaisesRegex(ValueError, "status"):
            self.api._main_query_for(
                self.api.captured_date,
                status="desconhecido",
            )

    def test_main_dataset_accepts_more_than_sixteen_fragments(self) -> None:
        initial = bytearray(28)
        struct.pack_into("<I", initial, 20, 172)
        fragments = [b"x" * 10 for _ in range(17)] + [b"xx"]
        responses = [
            {"result": [None, {"data": [None, bytes(initial)]}]},
            *(
                {"result": [{"data": [None, fragment]}]}
                for fragment in fragments
            ),
        ]
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.side_effect = responses

        with (
            patch.object(self.api, "_client", return_value=client) as factory,
            patch.object(self.api, "_handle", return_value=123),
        ):
            payload = self.api._fetch_main_payload(self.api.captured_date)

        self.assertEqual(len(payload), 200)
        factory.assert_called_once_with(timeout=MAIN_QUERY_TIMEOUT)
        self.assertEqual(client.set_timeout.call_count, len(fragments))
        client.set_timeout.assert_called_with(MAIN_FRAGMENT_TIMEOUT)

    def test_single_import_chunk_uses_the_final_processing_timeout(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.return_value = {
            "result": [None, {"data": [None, b"resultado"]}],
        }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_handle", return_value=123),
        ):
            result = self.api._send_import_packet((b"pacote",), 120.0)

        self.assertEqual(result, b"resultado")
        client.set_timeout.assert_called_once_with(120.0)

    def test_cancel_code_matches_official_fortaleza_suffix(self) -> None:
        api = ImperiumAPI(controller_id=49127)
        cancel = api.close_code("0")
        expected = bytes.fromhex(
            "08aaaa0aa8aaaa8aaaa8aaaaaaaaaaaaaaaaaaaaaa"
            "023d010000033030300c43414e43454c414d454e544f"
            "0300e7bf000060601000050200000000c0"
        )

        self.assertEqual(cancel.wire_code, "000")
        self.assertEqual(cancel.description, "CANCELAMENTO")
        self.assertEqual(cancel.id_code, 317)
        self.assertEqual(cancel.suffixes, (expected,))

    def test_unknown_close_code_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "nao permitido"):
            self.api.close_code("999")

    def test_close_codes_301_and_125_supported(self) -> None:
        c301 = self.api.close_code("301")
        self.assertEqual(c301.code, "301")
        self.assertEqual(c301.description, "TIPO DE OS INCORRETO")
        self.assertEqual(c301.id_code, 7)
        self.assertTrue(len(c301.suffixes) > 0)

        c125 = self.api.close_code("125")
        self.assertEqual(c125.code, "125")
        self.assertEqual(c125.description, "CLIENTE DESISTE DA AGENDA")
        self.assertEqual(c125.id_code, 7)

    def test_suffix_with_observation_preserves_suffix_when_marker_absent(self) -> None:
        c106 = self.api.close_code("106")
        dummy_suffix = b"raw_suffix_bytes"
        result = self.api._suffix_with_observation(dummy_suffix, c106, "Observacao qualquer")
        self.assertEqual(result, dummy_suffix)

    def test_close_code_lookup_query_uses_service_and_wire_code(self) -> None:
        close_code = self.api.close_code("0")

        query = self.api._close_code_lookup_query(118, close_code)

        self.assertIn("0%".encode("utf-16le"), query)
        self.assertNotIn("409%".encode("utf-16le"), query)
        marker = "pIdServico".encode("utf-16le")
        marker_end = query.index(marker) + len(marker)
        value_position = query.index(bytes.fromhex("03000000"), marker_end) + 4
        self.assertEqual(struct.unpack_from("<I", query, value_position)[0], 118)

    def test_parses_service_specific_close_code_id(self) -> None:
        close_code = self.api.close_code("0")
        payload = (
            b"metadata"
            + struct.pack("<I", 318)
            + b"\x03" + b"000"
            + b"\x0c" + b"CANCELAMENTO"
            + b"flags"
        )

        self.assertEqual(
            self.api._parse_close_code_id(payload, close_code),
            318,
        )

    def test_replaces_captured_close_code_id_in_suffix(self) -> None:
        close_code = self.api.close_code("0")

        suffix = self.api._suffix_with_close_code_id(
            close_code.suffixes[0],
            close_code,
            318,
        )

        self.assertIn(struct.pack("<I", 318), suffix)
        self.assertNotIn(struct.pack("<I", 317), suffix)

    def test_extracts_sql_server_message_from_apply_error(self) -> None:
        payload = (
            b"metadata\x00"
            b"[FireDAC][Phys][ODBC][Microsoft][ODBC Driver 17 for SQL Server]"
            b"[SQL Server]Viola\xe7\xe3o da restri\xe7\xe3o PRIMARY KEY"
            b"\x01\x00tail"
        )

        self.assertEqual(
            self.api._apply_error_message(payload),
            "Viola\u00e7\u00e3o da restri\u00e7\u00e3o PRIMARY KEY",
        )

    def test_productive_codes_are_not_available_without_equipment(self) -> None:
        for code in ("409", "430", "706"):
            with self.subTest(code=code):
                self.assertTrue(self.api.close_code(code).productive)

    def test_captured_nonproductive_codes_do_not_require_equipment(self) -> None:
        expected = {
            "306": "N\u00c3O RESIDE NO ENDERE\u00c7O",
            "312": "N\u00c3O SOLICITOU SERVI\u00c7O",
            "512": "CONTROLE REMOTO COM DEFEITO - TROCA",
        }

        for code, description in expected.items():
            with self.subTest(code=code):
                close_code = self.api.close_code(code)
                self.assertFalse(close_code.productive)
                self.assertEqual(close_code.description, description)
                self.assertTrue(close_code.suffixes[0])

    def test_status_exposes_manual_close_codes_to_the_workspace(self) -> None:
        with (
            patch.object(self.api, "_client") as client_factory,
            patch.object(self.api, "_handle"),
        ):
            client_factory.return_value.__enter__.return_value = MagicMock()
            payload = self.api.status()

        definitions = {item["code"]: item for item in payload["codes"]}
        self.assertIn("306", definitions)
        self.assertIn("312", definitions)
        self.assertIn("404", definitions)
        self.assertIn("512", definitions)
        self.assertTrue(definitions["404"]["requires_observation"])

    def test_partial_import_confirmation_only_retries_missing_orders(self) -> None:
        present = SimpleNamespace(
            os_number="100",
            contract="123",
            to_dict=lambda: {"os_number": "100", "contract": "123"},
        )
        missing = SimpleNamespace(
            os_number="101",
            contract="123",
            to_dict=lambda: {"os_number": "101", "contract": "123"},
        )
        preview = SimpleNamespace(orders=(present, missing))
        current = [Order(1, "100", "123", 10, "SERVICO")]

        with patch.object(self.api, "list_orders", return_value=current):
            result = self.api._confirm_import_after_timeout(
                preview,
                delays=(0.0,),
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["not_imported"], 1)
        self.assertTrue(result["partial"])
        self.assertEqual(result["retry_os_numbers"], ["101"])
        self.assertTrue(result["orders"][0]["imported"])
        self.assertFalse(result["orders"][1]["imported"])

    def test_confirm_import_after_timeout_returns_none_when_no_orders_found(self) -> None:
        missing = SimpleNamespace(
            os_number="101",
            contract="123",
            to_dict=lambda: {"os_number": "101", "contract": "123"},
        )
        preview = SimpleNamespace(orders=(missing,))

        with patch.object(self.api, "list_orders", return_value=[]):
            result = self.api._confirm_import_after_timeout(
                preview,
                delays=(0.0,),
            )

        self.assertIsNone(result)

    def test_chip_close_code_uses_the_profile_specific_id(self) -> None:
        natal = ImperiumAPI(port=212, controller_id=313101)
        mossoro = ImperiumAPI(port=579, controller_id=20857)
        fortaleza = ImperiumAPI(port=596, controller_id=49127)

        self.assertEqual(natal.close_code("706").id_code, 324)
        self.assertEqual(mossoro.close_code("706").id_code, 321)
        self.assertNotIn("706", fortaleza.close_codes)
        for suffix in mossoro.close_code("706").suffixes:
            self.assertIn(struct.pack("<I", 321), suffix)
            self.assertIn(struct.pack("<I", 20857), suffix)

    def test_installed_lookup_query_replaces_only_runtime_fields(self) -> None:
        query = self.api._installed_lookup_query(
            "123456789012",
            "1234567",
            123456,
        )

        self.assertIn("123456789012".encode("utf-16le"), query)
        self.assertIn("1234567".encode("utf-16le"), query)
        self.assertEqual(
            struct.unpack_from(
                "<I", query, self.api.installed_lookup_installer_offset
            )[0],
            123456,
        )

    def test_installed_lookup_accepts_the_captured_partial_chip_serial(self) -> None:
        query = self.api._installed_lookup_query(
            "6893",
            "1283241",
            122029,
        )
        byte_delta = 2 * (len("6893") - 12)

        self.assertEqual(len(query), len(self.api.installed_lookup_template) + byte_delta)
        self.assertIn("6893".encode("utf-16le"), query)
        self.assertIn("1283241".encode("utf-16le"), query)
        self.assertEqual(
            struct.unpack_from(
                "<I",
                query,
                self.api.installed_lookup_installer_offset + byte_delta,
            )[0],
            122029,
        )
        self.assertEqual(
            query[self.api.installed_lookup_query_length_offset],
            self.api.installed_lookup_template[
                self.api.installed_lookup_query_length_offset
            ] + byte_delta,
        )

    def test_installed_lookup_accepts_a_nine_digit_recife_contract(self) -> None:
        contract = "412774867"
        query = self.api._installed_lookup_query(
            "8493B2E280AF",
            contract,
            63746,
        )
        contract_delta = 2 * (len(contract) - 7)

        self.assertEqual(
            len(query),
            len(self.api.installed_lookup_template) + contract_delta,
        )
        self.assertIn(contract.encode("utf-16le"), query)
        self.assertEqual(
            struct.unpack_from(
                "<I",
                query,
                self.api.installed_lookup_contract_offset - 4,
            )[0],
            len(contract),
        )
        self.assertEqual(
            struct.unpack_from(
                "<I",
                query,
                self.api.installed_lookup_installer_offset,
            )[0],
            63746,
        )
        self.assertEqual(
            query[self.api.installed_lookup_query_length_offset],
            self.api.installed_lookup_template[
                self.api.installed_lookup_query_length_offset
            ] + contract_delta,
        )

    def test_serial_owner_lookup_finds_the_technician_and_equipment(self) -> None:
        def short(value: str) -> bytes:
            encoded = value.encode("cp1252")
            return bytes((len(encoded),)) + encoded

        def technician_row(stock_id: int, installer_id: int, name: str) -> bytes:
            return b"".join(
                (
                    b"\x01",
                    struct.pack("<I", stock_id),
                    short(name),
                    struct.pack("<I", installer_id),
                    short(name),
                    short("N"),
                    short("N"),
                    short("N"),
                    short("N"),
                    short(""),
                    b"\x00\x00",
                )
            )

        technician_payload = b"HEADER PRIMARY_KEY" + b"\x00" * 8 + b"".join(
            (
                technician_row(10, 100, "TECNICO UM"),
                technician_row(20, 200, "TECNICO DOIS"),
            )
        )
        empty_serial_payload = b"\xc0\xc0\x60"
        serial_payload = b"".join(
            (
                struct.pack("<III", 5241, 10005, 1),
                short("241786844144"),
                short(""),
                short("N"),
            )
        )
        item_payload = b"".join(
            (
                struct.pack("<II", 5241, 10005),
                short("DECODER"),
                short("41001621"),
                short("DECODER 4K UHD"),
                struct.pack("<I", 6),
                short("DIVERSOS"),
                struct.pack("<I", 2),
                short("UN"),
                short("S"),
                b"\x00" * 24,
                short("1.00 UN"),
                b"\x00" * 40,
            )
        )
        client_context = MagicMock()
        client_context.__enter__.return_value = MagicMock()
        with (
            patch.object(self.api, "_client", return_value=client_context),
            patch.object(self.api, "_handle", return_value=1),
            patch.object(
                self.api,
                "_dataset_payload",
                side_effect=(
                    technician_payload,
                    empty_serial_payload,
                    serial_payload,
                    item_payload,
                ),
            ),
        ):
            result = self.api.find_serial_owner("241786844144")

        self.assertTrue(result["found"])
        # parse_technicians sorts by name, so DOIS is scanned before UM.
        self.assertEqual(result["owner"]["technician_name"], "TECNICO UM")
        self.assertEqual(result["equipment"]["name"], "DECODER 4K UHD")
        self.assertEqual(result["scanned"], 2)

    def test_installed_parser_expands_a_partial_chip_serial(self) -> None:
        full_serial = "89550531860007296893"
        payload = b"".join(
            (
                struct.pack("<I", 5274),
                b"\x0523107",
                self.api._short_text("SC BOPP 8NP NE 128KB AAC005 TRIPLE"),
                struct.pack("<I", 6),
                self.api._short_text("DIVERSOS"),
                struct.pack("<I", 2),
                self.api._short_text("UN"),
                b"\x01S",
                struct.pack("<I", 174),
                full_serial.encode("ascii"),
                struct.pack("<I", 10005),
            )
        )

        equipment = self.api._parse_installed_equipment(payload, "6893")

        self.assertEqual(equipment.serial, full_serial)
        self.assertTrue(self.api._equipment_matches_type(equipment, "chip"))

    def test_terminal_docsis_and_gpon_are_accepted_as_emta(self) -> None:
        for name in (
            "TERMINAL DOCSIS 3.1 WIFI HI3120",
            "TERMINAL GPON WIFI6 SG0006D2VA",
        ):
            equipment = Equipment(1, "41001518", name, "S", 6, "DIVERSOS", 2, "UN", "ABC")
            with self.subTest(name=name):
                self.assertTrue(self.api._equipment_matches_type(equipment, "emta"))

    def test_equipment_delta_parts_keep_serial_and_model(self) -> None:
        context = DetailContext(
            id_os=2160605,
            contract="1234567",
            installer_id=123456,
            installer_name="GABRIEL SENA DESC",
        )
        installed = Equipment(
            id_equipment=5274,
            code="41001621",
            name="DECODER 4K UHD FULL IP Z4KW6",
            identified="S",
            id_brand=6,
            brand="DIVERSOS",
            id_unit=2,
            unit="UN",
            serial="123456789012",
            id_stock=174,
            id_group=10005,
        )
        removed = self.api.removed_equipment["decoder"]
        removed = Equipment(**{**removed.__dict__, "serial": "ABCDEFGHIJKL"})

        installed_parts = self.api._installed_parts(context, installed)
        removed_parts = self.api._removed_parts(context, removed)

        self.assertIn(b"123456789012", b"".join(installed_parts))
        self.assertIn(b"DECODER 4K UHD FULL IP Z4KW6", installed_parts[0])
        self.assertIn(b"ABCDEFGHIJKL", b"".join(removed_parts))
        self.assertIn(b"DECODER DIG. HD DCR7121 - PACE", removed_parts[0])

    def test_material_row_matches_the_official_natal_capture(self) -> None:
        context = DetailContext(
            id_os=2161959,
            contract="4229550",
            installer_id=328895,
            installer_name="FERNANDO ANTONIO",
        )
        material = StockMaterial(
            id_equipment=358,
            code="22056366",
            name="ISOLADOR COAXIAL QUADRADO - CISP-HR",
            stock_quantity=20,
            id_stock=273,
            unit="UN",
            id_unit=1,
            identified="N",
            requested_quantity=1,
        )
        expected = bytes.fromhex(
            "0400a8a00aa00227fd20006601000011010000feffffff"
            "2349534f4c41444f5220434f415849414c20515541445241444f202d20434953502d4852"
            "02554e014e100200000000000001001002000000000000"
            "08323230353633363601000000014e00000000"
        )

        self.assertEqual(
            self.api._material_row(context, material, -2, True),
            expected,
        )

    def test_material_stock_templates_rebuild_the_captured_requests(self) -> None:
        context = DetailContext(
            id_os=2161959,
            contract="4229550",
            installer_id=328895,
            installer_name="FERNANDO ANTONIO",
        )
        material = StockMaterial(
            id_equipment=4981,
            code="22065727",
            name="MARCADOR CASA PRETO NR 9",
            stock_quantity=0,
            id_stock=273,
            unit="UN",
            id_unit=1,
            identified="N",
            requested_quantity=1,
        )

        self.assertEqual(
            self.api._material_catalog_query(context.installer_id),
            self.api.material_catalog_template,
        )
        self.assertEqual(
            self.api.material_stock_method,
            "TDtmOrdemServico.AS_GetRecords",
        )
        self.assertEqual(
            self.api._toa_material_lookup_query(
                context.installer_id,
                "22065727_MARCADOR CASA PRETO NR 9",
            ),
            self.api.toa_material_lookup_template,
        )
        self.assertEqual(
            hashlib.sha256(
                self.api._provider_close_query(
                    self.api.toa_material_lookup_template
                )
            ).hexdigest(),
            "b07dd7f762258b0e048098d144d4b88d53a8d035feedf817f395b4d1a47a7721",
        )
        self.assertEqual(
            self.api._material_transfer_query(context, [material]),
            self.api.material_transfer_template,
        )
        self.assertEqual(
            hashlib.sha256(
                self.api._provider_close_query(self.api.material_catalog_template)
            ).hexdigest(),
            "2fdd0fc7ec332dc0d27006d5b15e03fbdfe22c7fd64619d6041d9cde862952ea",
        )
        self.assertEqual(
            hashlib.sha256(
                self.api._provider_close_query(self.api.material_transfer_template)
            ).hexdigest(),
            "bbeab0e1961b2e73b2926f9fb0a58494a60a2d8a9a00bfb6fb65c0fd13466cf9",
        )

    def test_material_catalog_parser_keeps_stock_fields(self) -> None:
        quantity = bytes.fromhex("1002") + (20).to_bytes(6, "big") + bytes(10)
        payload = b"".join(
            (
                b"metadata",
                struct.pack("<I", 358),
                b"\x0822056366",
                b"\x23ISOLADOR COAXIAL QUADRADO - CISP-HR",
                quantity,
                struct.pack("<I", 273),
                b"\x02UN",
                struct.pack("<I", 1),
                b"\x01N",
            )
        )

        materials = self.api._parse_material_catalog(payload)

        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0].code, "22056366")
        self.assertEqual(materials[0].stock_quantity, 20)
        self.assertEqual(materials[0].id_stock, 273)

    def test_stock_inventory_catalog_keeps_six_digit_material_code(self) -> None:
        context = DetailContext(2170777, "4234309", 313363, "ADRIANO")
        technician = SimpleNamespace(
            installer_id=context.installer_id,
            stock_id=260,
            technician_name=context.installer_name,
            stock_name=context.installer_name,
        )
        stock_item = SimpleNamespace(
            equipment_id=4950,
            code="433135",
            equipment="SAPATILHA DESCARTAVEL ELAS",
            quantity_number=2,
            unit="UN",
            unit_id=2,
            identified="N",
        )

        with (
            patch.object(self.api, "_handle", side_effect=(101, 102)),
            patch.object(
                self.api,
                "_dataset_payload",
                side_effect=(b"technicians", b"items"),
            ),
            patch("imperium_api.parse_technicians", return_value=[technician]),
            patch("imperium_api.parse_stock_items", return_value=[stock_item]),
        ):
            materials = self.api._stock_inventory_material_catalog_on(
                MagicMock(),
                context,
            )

        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0].code, "433135")
        self.assertEqual(materials[0].stock_quantity, 2)

    def test_toa_material_lookup_terms_strip_code_and_normalize_punctuation(self) -> None:
        terms = self.api._toa_material_lookup_terms(
            "22069613",
            "22069613_CONECTOR FO CAMPO FAST SC/APC",
        )

        self.assertEqual(terms[0], "CONECTOR FO CAMPO FAST SC/APC")
        self.assertIn("CONECTOR FO CAMPO FAST SC APC", terms)
        self.assertNotIn(
            "22069613_22069613_CONECTOR FO CAMPO FAST SC/APC",
            terms,
        )

    def test_manual_material_catalog_overrides_incomplete_order_catalog(self) -> None:
        context = DetailContext(2163650, "4231440", 52299, "ACTON")
        incomplete = StockMaterial(
            1, "22069613", "CONECTOR", 0, 1, "UN", 2, "N"
        )
        manual = StockMaterial(
            5290,
            "22069613",
            "CONECTOR FO CAMPO FAST SC APC",
            14,
            116,
            "UN",
            2,
            "N",
        )

        with (
            patch.object(self.api, "_material_catalog_on", return_value=[incomplete]),
            patch.object(self.api, "_manual_material_catalog_on", return_value=[manual]),
        ):
            materials = self.api._combined_material_catalog_on(MagicMock(), context)

        self.assertEqual(materials, [manual])

    def test_combined_catalog_uses_complete_stock_when_order_catalog_is_invalid(
        self,
    ) -> None:
        context = DetailContext(2163650, "4231440", 52299, "ACTON")
        fallback = StockMaterial(
            5290,
            "22069613",
            "CONECTOR FO CAMPO FAST SC APC",
            14,
            116,
            "UN",
            2,
            "N",
        )

        with (
            patch.object(
                self.api,
                "_material_catalog_on",
                side_effect=DataSnapError(
                    "O estoque do instalador retornou dados invalidos"
                ),
            ),
            patch.object(
                self.api,
                "_manual_material_catalog_on",
                return_value=[fallback],
            ),
        ):
            materials = self.api._combined_material_catalog_on(MagicMock(), context)

        self.assertEqual(materials, [fallback])

    def test_combined_catalog_reports_when_both_stock_sources_fail(self) -> None:
        context = DetailContext(2163650, "4231440", 52299, "ACTON")

        with (
            patch.object(
                self.api,
                "_material_catalog_on",
                side_effect=DataSnapError(
                    "O estoque do instalador retornou dados invalidos"
                ),
            ),
            patch.object(
                self.api,
                "_manual_material_catalog_on",
                side_effect=DataSnapError("estoque completo indisponivel"),
            ),
            self.assertRaisesRegex(DataSnapError, "estoque completo"),
        ):
            self.api._combined_material_catalog_on(MagicMock(), context)

    def test_material_inventory_retries_on_a_clean_connection(self) -> None:
        context = DetailContext(2161959, "4229550", 328895, "FERNANDO ANTONIO")
        material = StockMaterial(358, "22056366", "ISOLADOR", 20, 273, "UN", 1, "N")
        client = MagicMock()
        client.__enter__.return_value = client
        with (
            patch.object(self.api, "_client", return_value=client) as client_factory,
            patch.object(self.api, "_fetch_detail_on", return_value=b"detail"),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_material_catalog_on",
                side_effect=(TimeoutError("timed out"), [material]),
            ) as catalog,
            patch("imperium_api.time.sleep"),
        ):
            result = self.api.list_material_inventory(context.id_os)

        self.assertEqual(result["count"], 1)
        self.assertEqual(catalog.call_count, 2)
        self.assertEqual(client_factory.call_count, 2)

    def test_official_material_preparation_uses_existing_technician_stock(
        self,
    ) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        context = DetailContext(order.id_os, order.contract, 313363, "ADRIANO")
        material = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA",
            5,
            260,
            "UN",
            2,
            "N",
        )
        client = MagicMock()
        client.__enter__.return_value = client

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[material],
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [
                    {
                        "code": "22023400",
                        "description": "ABRACADEIRA",
                        "quantity": "2",
                    }
                ],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(result["source"], "technician_stock")
        transfer.assert_not_called()

    def test_official_material_preparation_distributes_group_as_concrete_codes(
        self,
    ) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "CORRECAO ESTOQUE",
        )
        context = DetailContext(order.id_os, order.contract, 313363, "EDCARLOS")
        catalog = [
            StockMaterial(
                5269,
                "22024800",
                "ANEL DE VEDACAO WEATHER SEAL 1/2 CONEC F",
                4,
                260,
                "UN",
                2,
                "N",
                id_group=309,
                group="ANEL DE VEDACAO",
            ),
            StockMaterial(
                309,
                "22025321",
                "ANEL VEDACAO PLASTICA P PORTA F",
                6,
                260,
                "UN",
                2,
                "N",
                id_group=309,
                group="ANEL DE VEDACAO",
            ),
        ]
        client = MagicMock()
        client.__enter__.return_value = client

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=catalog,
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [
                    {
                        "code": "22024800",
                        "description": catalog[0].name,
                        "quantity": "10",
                    }
                ],
                expected_installer_id=context.installer_id,
            )

        self.assertEqual(
            result["resolved_materials"],
            [
                {"codigoequipamento": "22024800", "qtd": "4"},
                {"codigoequipamento": "22025321", "qtd": "6"},
            ],
        )
        self.assertEqual(
            result["group_distributions"][0]["allocations"],
            [
                {"code": "22024800", "quantity": "4"},
                {"code": "22025321", "quantity": "6"},
            ],
        )
        self.assertFalse(result["transferred"])
        transfer.assert_not_called()

    def test_official_material_preparation_accepts_six_digit_code(self) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        context = DetailContext(order.id_os, order.contract, 313363, "ADRIANO")
        material = StockMaterial(
            4950,
            "433135",
            "SAPATILHA DESCARTAVEL ELAS",
            2,
            260,
            "UN",
            2,
            "N",
        )
        client = MagicMock()
        client.__enter__.return_value = client

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[material],
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [
                    {
                        "code": "433135",
                        "description": "SAPATILHA DESCARTAVEL ELAS",
                        "quantity": "1",
                    }
                ],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(result["material_count"], 1)
        transfer.assert_not_called()

    def test_official_material_preparation_blocks_invalid_code_format(
        self,
    ) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )

        with (
            patch.object(self.api, "_client") as client_factory,
            self.assertRaisesRegex(
                ValueError,
                "formato do codigo da miscelanea 433135 / X e invalido",
            ),
        ):
            self.api.prepare_official_materials(
                order,
                [{"code": "433135 / X", "quantity": "1"}],
                expected_installer_id=313363,
            )

        client_factory.assert_not_called()

    def test_direct_productive_close_accepts_six_digit_material_code(self) -> None:
        order = Order(
            2170777,
            "2647378599",
            "4234309",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )

        with patch.object(
            self.api,
            "_close_order_with_builder",
            return_value={"ok": True},
        ) as close:
            result = self.api.close_productive(
                order,
                "409",
                installed_equipment=[
                    {"serial": "1041212CD510", "type": "emta"}
                ],
                materials=[
                    {
                        "code": "433135",
                        "description": "SAPATILHA DESCARTAVEL ELAS",
                        "quantity": 1,
                    }
                ],
            )

        self.assertTrue(result["ok"])
        close.assert_called_once()

    def test_official_material_preparation_transfers_only_shortfall(self) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        context = DetailContext(order.id_os, order.contract, 313363, "ADRIANO")
        material = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA",
            1,
            260,
            "UN",
            2,
            "N",
        )
        client = MagicMock()
        client.__enter__.return_value = client

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[material],
            ),
            patch.object(
                self.api,
                "_material_virtual_stock_quantities_on",
                return_value={"22023400": Decimal("3")},
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [
                    {
                        "code": "22023400",
                        "description": "ABRACADEIRA",
                        "quantity": "4",
                    }
                ],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["transferred"])
        self.assertEqual(result["source"], "RETORNO")
        self.assertEqual(
            result["shortfalls"],
            [
                {
                    "code": "22023400",
                    "requested_code": "22023400",
                    "requested_quantity": "4",
                    "technician_available": 1,
                    "transfer_quantity": 3,
                    "group": "Abracadeira Hellermann T50R / T30R",
                }
            ],
        )
        transferred = transfer.call_args.args[2]
        self.assertEqual(len(transferred), 1)
        self.assertEqual(transferred[0].requested_quantity, 3)

    def test_official_material_preparation_blocks_installer_change(self) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        context = DetailContext(order.id_os, order.contract, 999999, "OUTRO")
        client = MagicMock()
        client.__enter__.return_value = client

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
            ) as catalog,
            self.assertRaisesRegex(ValueError, "instalador da OS mudou"),
        ):
            self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "quantity": "1"}],
                expected_installer_id=313363,
            )

        catalog.assert_not_called()

    def test_official_material_preparation_blocks_unknown_material(self) -> None:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        context = DetailContext(order.id_os, order.contract, 313363, "ADRIANO")
        client = MagicMock()
        client.__enter__.return_value = client

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[],
            ),
            patch.object(
                self.api,
                "_lookup_material_by_code_on",
                return_value=None,
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
            self.assertRaisesRegex(ValueError, "ABRACADEIRA.*22023400"),
        ):
            self.api.prepare_official_materials(
                order,
                [
                    {
                        "code": "22023400",
                        "description": "ABRACADEIRA",
                        "quantity": "1",
                    }
                ],
                expected_installer_id=context.installer_id,
            )

        transfer.assert_not_called()

    def test_material_transfer_timeout_is_never_repeated_automatically(self) -> None:
        context = DetailContext(2162769, "4231016", 313363, "ADRIANO COSTA")
        material = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA",
            0,
            260,
            "UN",
            2,
            "N",
            requested_quantity=4,
        )
        client = MagicMock()
        client.request.side_effect = TimeoutError("timed out")

        with (
            patch.object(self.api, "_handle", return_value=123),
            patch.object(self.api, "_material_transfer_query", return_value=b"query"),
            patch.object(
                self.api,
                "_material_source_shortages_on",
                return_value={},
            ),
            patch.object(
                self.api,
                "_material_shortfalls_confirmed",
                return_value=False,
            ),
            self.assertRaises(MaterialTransferUncertainError),
        ):
            self.api._transfer_material_shortfalls(client, context, [material])

        self.assertEqual(client.request.call_count, 1)
        client.set_timeout.assert_called_once_with(180.0)

    def test_material_transfer_timeout_continues_when_fresh_stock_confirms(self) -> None:
        context = DetailContext(2162769, "4231016", 313363, "ADRIANO COSTA")
        material = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA",
            0,
            260,
            "UN",
            2,
            "N",
            requested_quantity=4,
        )
        client = MagicMock()
        client.request.side_effect = TimeoutError("timed out")

        with (
            patch.object(self.api, "_handle", return_value=123),
            patch.object(self.api, "_material_transfer_query", return_value=b"query"),
            patch.object(
                self.api,
                "_material_source_shortages_on",
                return_value={},
            ),
            patch.object(
                self.api,
                "_material_shortfalls_confirmed",
                return_value=True,
            ),
        ):
            reusable = self.api._transfer_material_shortfalls(
                client,
                context,
                [material],
            )

        self.assertFalse(reusable)
        client.close.assert_called_once_with()
        client.set_timeout.assert_called_once_with(180.0)

    def test_confirmed_material_transfer_reconnects_without_repeating_write(self) -> None:
        context = DetailContext(2162769, "4231016", 313363, "ADRIANO COSTA")
        material = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA",
            0,
            260,
            "UN",
            2,
            "N",
            requested_quantity=4,
        )
        client = MagicMock()
        client.request.side_effect = ({"result": []}, TimeoutError("timed out"))

        with (
            patch.object(self.api, "_handle", return_value=123),
            patch.object(self.api, "_material_transfer_query", return_value=b"query"),
            patch.object(self.api, "_provider_close_query", return_value=b"close"),
            patch.object(
                self.api,
                "_material_source_shortages_on",
                return_value={},
            ),
        ):
            reusable = self.api._transfer_material_shortfalls(client, context, [material])

        self.assertFalse(reusable)
        self.assertEqual(client.request.call_count, 2)

    def test_material_transfer_stops_before_write_when_source_has_no_stock(self) -> None:
        context = DetailContext(2162769, "4231016", 313363, "ADRIANO COSTA")
        material = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA",
            0,
            260,
            "UN",
            2,
            "N",
            requested_quantity=4,
        )
        client = MagicMock()

        with (
            patch.object(
                self.api,
                "_material_source_shortages_on",
                return_value={"22023400": (4, 0)},
            ),
            self.assertRaisesRegex(ValueError, "22023400"),
        ):
            self.api._transfer_material_shortfalls(client, context, [material])

        client.request.assert_not_called()

    def test_productive_packet_accepts_multiple_equipment_and_smart(self) -> None:
        context = DetailContext(
            id_os=2160605,
            contract="1234567",
            installer_id=123456,
            installer_name="GABRIEL SENA DESC",
        )
        installed = [
            Equipment(
                id_equipment=5274 + index,
                code="41001621" if index == 0 else "41001234",
                name=(
                    "DECODER 4K UHD FULL IP Z4KW6"
                    if index == 0
                    else "SMART CARD AVULSO PRETO NOVO"
                ),
                identified="S",
                id_brand=6,
                brand="DIVERSOS",
                id_unit=2,
                unit="UN",
                serial=serial,
                id_stock=174,
                id_group=10005,
            )
            for index, serial in enumerate(("123456789012", "210987654321"))
        ]
        removed = [
            Equipment(
                **{
                    **self.api.removed_equipment[equipment_type].__dict__,
                    "serial": serial,
                }
            )
            for equipment_type, serial in (
                ("decoder", "111111111111"),
                ("emta", "222222222222"),
                ("smart", "333333333333"),
            )
        ]
        record = b"record:" + self.api.old_mask + b"\x00" * 8

        with (
            patch.object(
                self.api,
                "_detail_parts",
                return_value=(record, bytes(range(19))),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
        ):
            blob = self.api._build_productive_apply_blob(
                b"detail",
                self.api.close_code("409").suffixes[0],
                installed,
                removed,
            )

        for equipment in installed + removed:
            self.assertIn(equipment.serial.encode("ascii"), blob)
        self.assertIn(b"SMART CARD AVULSO PRETO NOVO", blob)
        self.assertEqual(self.api.removed_equipment["smart"].code, "41001234")

    def test_productive_rules_reject_incomplete_movements(self) -> None:
        swap = Order(1, "123", "1234567", 10, "TROCA DE EQUIPAMENTO")
        change = Order(2, "456", "1234567", 11, "MUDANCA DE PACOTE")
        subscription = Order(3, "789", "1234567", 12, "ADESAO DE ASSINATURA")

        with self.assertRaisesRegex(ValueError, "serial instalado e um retirado"):
            self.api.close_productive(
                swap,
                "409",
                installed_serial="123456789012",
            )

        with self.assertRaisesRegex(ValueError, "somente equipamento retirado"):
            self.api.close_productive(
                swap,
                "430",
                installed_serial="123456789012",
                removed_serial="ABCDEFGHIJKL",
                removed_type="decoder",
            )
        with self.assertRaisesRegex(ValueError, "somente com equipamento instalado"):
            self.api.close_productive(
                change,
                "409",
                installed_serial="123456789012",
                removed_serial="ABCDEFGHIJKL",
                removed_type="decoder",
            )
        with self.assertRaisesRegex(ValueError, "nao permite equipamento"):
            self.api.close_productive(
                subscription,
                "409",
                installed_serial="123456789012",
            )

        with patch.object(
            self.api,
            "_close_order_with_builder",
            return_value={"ok": True},
        ) as close_order:
            result = self.api.close_productive(subscription, "409")

        self.assertTrue(result["ok"])
        close_order.assert_called_once()

    def test_chip_close_accepts_a_partial_serial_and_rejects_other_movements(self) -> None:
        order = Order(1, "2646521330", "4229178", 10, "ENVIO DE CHIP VIA TECNICO")
        with patch.object(
            self.api,
            "_close_order_with_builder",
            return_value={"ok": True},
        ) as close_order:
            result = self.api.close_productive(
                order,
                "706",
                installed_equipment=[{"serial": "6471", "type": "chip"}],
            )

        self.assertTrue(result["ok"])
        close_order.assert_called_once()
        self.assertEqual(close_order.call_args.kwargs["apply_timeout"], 10.0)
        with self.assertRaisesRegex(ValueError, "somente o chip instalado"):
            self.api.close_productive(
                order,
                "706",
                installed_equipment=[{"serial": "6471", "type": "chip"}],
                removed_equipment=[{"serial": "12345678", "type": "decoder"}],
            )

    def test_productive_close_accepts_toa_material_description(self) -> None:
        order = Order(1, "2646355414", "1234567", 10, "INSTALACAO")

        with patch.object(
            self.api,
            "_close_order_with_builder",
            return_value={"ok": True},
        ) as close_order:
            result = self.api.close_productive(
                order,
                "409",
                installed_serial="123456789012",
                materials=[
                    {
                        "code": "22024800",
                        "description": "ANEL DE VEDACAO",
                        "quantity": 1,
                    }
                ],
            )

        self.assertTrue(result["ok"])
        close_order.assert_called_once()
        self.assertEqual(close_order.call_args.kwargs["apply_timeout"], 180.0)
        self.assertEqual(
            close_order.call_args.kwargs["confirmation_delays"],
            (0.0, 5.0, 10.0, 20.0, 30.0, 45.0),
        )

    def test_productive_material_close_reconnects_before_apply(self) -> None:
        order = Order(2163650, "2646844394", "4231440", 10, "INSTALACAO")
        context = DetailContext(2163650, "4231440", 52299, "ACTON")
        equipment = Equipment(
            5286,
            "41001602",
            "TERMINAL GPON WIFI6 SG0006D2VA",
            "S",
            1,
            "MARCA",
            1,
            "UN",
            "2CD8AE5D4EDD",
            116,
            10079,
        )
        material = StockMaterial(
            5290,
            "22069613",
            "CONECTOR FO CAMPO FAST SC APC",
            14,
            116,
            "UN",
            2,
            "N",
        )
        first_client = MagicMock(name="preparation_client")
        clean_client = MagicMock(name="apply_client")

        def exercise_builder(_order, _code, builder, **_kwargs):
            with self.assertRaises(_MaterialTransferReconnectRequired):
                builder(first_client, b"detail", b"suffix")
            self.assertEqual(
                builder(clean_client, b"detail", b"suffix"),
                b"apply-blob",
            )
            return {"ok": True}

        with (
            patch.object(
                self.api,
                "_close_order_with_builder",
                side_effect=exercise_builder,
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_lookup_installed_equipment",
                return_value=equipment,
            ) as lookup_equipment,
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[material],
            ) as lookup_materials,
            patch.object(
                self.api,
                "_transfer_material_shortfalls",
                return_value=True,
            ) as transfer_materials,
            patch.object(
                self.api,
                "_build_productive_apply_blob",
                return_value=b"apply-blob",
            ) as build_blob,
        ):
            result = self.api.close_productive(
                order,
                "409",
                installed_equipment=[
                    {"serial": "2CD8AE5D4EDD", "type": "emta"}
                ],
                materials=[
                    {
                        "code": "22069613",
                        "description": "CONECTOR FO CAMPO FAST SC/APC",
                        "quantity": 2,
                    }
                ],
            )

        self.assertTrue(result["ok"])
        lookup_equipment.assert_called_once_with(
            first_client,
            context,
            "2CD8AE5D4EDD",
        )
        lookup_materials.assert_called_once_with(first_client, context)
        transfer_materials.assert_called_once()
        build_blob.assert_called_once()

    def test_material_timeout_uses_extended_confirmation_without_resending(self) -> None:
        order = Order(2163650, "2646844394", "4231440", 10, "INSTALACAO")
        close_code = self.api.close_code("409")
        open_detail = b"detail-2646844394-open"
        closed_detail = b"".join(
            (
                b"detail-2646844394-",
                close_code.wire_code.encode("ascii"),
                b"-",
                close_code.description.encode("cp1252"),
            )
        )
        apply_client = MagicMock(name="apply_client")
        confirmation_client = MagicMock(name="confirmation_client")
        apply_client.request.side_effect = TimeoutError("timed out")

        with (
            patch.object(
                self.api,
                "_client",
                side_effect=(apply_client, confirmation_client),
            ),
            patch.object(
                self.api,
                "_fetch_detail_on",
                side_effect=(
                    open_detail,
                    open_detail,
                    open_detail,
                    open_detail,
                    open_detail,
                    open_detail,
                    closed_detail,
                ),
            ),
            patch.object(self.api, "_lookup_close_code_id", return_value=44),
            patch.object(self.api, "_handle", return_value=1),
            patch.object(self.api, "_append_audit"),
            patch("imperium_api.time.sleep") as sleep,
        ):
            result = self.api._close_order_with_builder(
                order,
                close_code,
                lambda _client, _detail, _suffix: b"apply-blob",
                apply_timeout=180.0,
                confirmation_delays=(0.0, 5.0, 10.0, 20.0, 30.0, 45.0),
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "409")
        apply_client.request.assert_called_once()
        apply_client.set_timeout.assert_called_once_with(180.0)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [5.0, 10.0, 20.0, 30.0, 45.0],
        )

    def test_sent_close_without_confirmation_is_uncertain(self) -> None:
        order = Order(2163650, "2646844394", "4231440", 10, "INSTALACAO")
        close_code = self.api.close_code("409")
        open_detail = b"detail-2646844394-open"
        apply_client = MagicMock(name="apply_client")
        confirmation_client = MagicMock(name="confirmation_client")
        apply_client.request.side_effect = TimeoutError("timed out")

        with (
            patch.object(
                self.api,
                "_client",
                side_effect=(apply_client, confirmation_client),
            ),
            patch.object(
                self.api,
                "_fetch_detail_on",
                side_effect=(open_detail, open_detail, open_detail),
            ),
            patch.object(self.api, "_lookup_close_code_id", return_value=44),
            patch.object(self.api, "_handle", return_value=1),
            patch.object(self.api, "_append_audit") as append_audit,
            patch("imperium_api.time.sleep"),
            self.assertRaises(CloseConfirmationUncertainError),
        ):
            self.api._close_order_with_builder(
                order,
                close_code,
                lambda _client, _detail, _suffix: b"apply-blob",
                confirmation_delays=(0.0, 0.0),
            )

        apply_client.request.assert_called_once()
        append_audit.assert_called_with(
            order,
            close_code,
            "INCERTO",
            "timed out",
        )

    def test_closed_430_blocks_later_106_before_any_write_preparation(self) -> None:
        order = Order(2163650, "2646844394", "4231440", 10, "DESCONEXAO")
        requested = self.api.close_code("106")
        current = self.api.close_code("430")
        detail = b"|".join(
            (
                order.num_os.encode("ascii"),
                current.wire_code.encode("ascii"),
                current.description.encode("cp1252"),
            )
        )
        client = MagicMock(name="read_only_client")
        blob_builder = MagicMock(name="blob_builder")

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_fetch_detail_on", return_value=detail),
            patch.object(self.api, "_lookup_close_code_id") as lookup_close_code,
            patch.object(self.api, "_handle") as lookup_handle,
            self.assertRaisesRegex(
                CloseStateConflictError,
                (
                    "already_closed; "
                    "already_closed_with_different_code:430; "
                    "remote_state_changed; operation_blocked"
                ),
            ),
        ):
            self.api._close_order_with_builder(
                order,
                requested,
                blob_builder,
            )

        client.connect.assert_called_once_with()
        client.close.assert_called_once_with()
        client.request.assert_not_called()
        lookup_close_code.assert_not_called()
        lookup_handle.assert_not_called()
        blob_builder.assert_not_called()

    def test_multiple_remote_close_codes_block_as_shared_state(self) -> None:
        order = Order(2163650, "2646844394", "4231440", 10, "DESCONEXAO")
        requested = self.api.close_code("106")
        current = self.api.close_code("430")
        detail = b"|".join(
            (
                order.num_os.encode("ascii"),
                requested.wire_code.encode("ascii"),
                requested.description.encode("cp1252"),
                current.wire_code.encode("ascii"),
                current.description.encode("cp1252"),
            )
        )
        client = MagicMock(name="read_only_client")
        blob_builder = MagicMock(name="blob_builder")

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_fetch_detail_on", return_value=detail),
            self.assertRaisesRegex(
                CloseStateConflictError,
                "shared_state_contamination",
            ),
        ):
            self.api._close_order_with_builder(
                order,
                requested,
                blob_builder,
            )

        client.request.assert_not_called()
        blob_builder.assert_not_called()

    def test_import_never_repeats_an_ambiguous_timed_out_lot(self) -> None:
        preview = SimpleNamespace(orders=(object(),))
        with (
            patch.object(
                self.api.import_protocol,
                "build_packet",
                return_value=b"packet",
            ),
            patch.object(
                self.api.import_protocol,
                "chunks",
                return_value=(b"packet",),
            ),
            patch.object(
                self.api,
                "_send_import_packet",
                side_effect=TimeoutError("timed out"),
            ) as sender,
            patch.object(
                self.api,
                "_confirm_import_after_timeout",
                return_value=None,
            ),
        ):
            with self.assertRaisesRegex(
                DataSnapError,
                "nao sera repetido automaticamente",
            ):
                self.api.import_toa(preview)

        self.assertEqual(sender.call_count, 1)

    def test_dataset_sequence_byte_is_not_treated_as_row_count(self) -> None:
        payload = bytearray(80)
        payload[:4] = b"\xc0\xc0\x61\xff"
        row = (
            struct.pack("<I", 12345)
            + b"\x03106"
            + b"\x03456"
            + struct.pack("<I", 73)
            + b"\x0dRETIRAR PONTO"
        )
        payload[40 : 40 + len(row)] = row

        orders = self.api._parse_orders(bytes(payload))

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].id_os, 12345)

    def test_two_byte_row_count_marker_accepts_large_dataset(self) -> None:
        payload = bytearray(80)
        payload[:5] = b"\xc0\xc0\x62\x02\xda"
        row = (
            struct.pack("<I", 54321)
            + b"\x03999"
            + b"\x03789"
            + struct.pack("<I", 74)
            + b"\x0dRETIRAR PONTO"
        )
        payload[40 : 40 + len(row)] = row

        orders = self.api._parse_orders(bytes(payload))

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].id_os, 54321)

    def test_empty_dataset_marker_returns_no_orders(self) -> None:
        payload = b"\xc0\xc0\x60" + bytes(77)

        self.assertEqual(self.api._parse_orders(payload), [])

    def test_only_first_main_record_mask_is_changed(self) -> None:
        record = self.api.old_mask + b"nested:" + self.api.old_mask
        blob = self.api._assemble_apply_blob(
            record,
            bytes(range(19)),
            self.api.close_code("0").suffixes[0],
        )
        packet = blob[4:]

        self.assertEqual(packet.count(self.api.new_mask), 1)
        self.assertEqual(packet.count(self.api.old_mask), 1)


if __name__ == "__main__":
    unittest.main()
