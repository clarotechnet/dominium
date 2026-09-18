import unittest
import struct
from dataclasses import replace
from pathlib import Path

from toa_import import (
    TOAImportProtocol,
    build_toa_xml,
    parse_toa_csv,
    parse_toa_timeline_activities,
)


class TOAImportTests(unittest.TestCase):
    @staticmethod
    def _complete_csv() -> bytes:
        return (
            '"Data","Login do Tecnico","Status da Atividade","Endereco",'
            '"Complemento Endereco","Bairro","CEP Codigo Postal",'
            '"Intervalo de Tempo","Cidade","UF","Numero da WO",'
            '"Contrato","Node","Numero da O.S 1","Tipo O.S 1"\n'
            '"16/07/26","Z1","pendente","R TESTE, 10 - CENTRO",'
            '",APT 2","CENTRO","59000-000","08:00 - 11:00",'
            '"NATAL","RN","01695|1","123","NTL01","100",'
            '"87 - RETIRAR EMTA"\n'
        ).encode("utf-8")

    def test_expands_repeated_os_columns_and_ignores_control_rows(self) -> None:
        content = (
            '"Data","Login do Tecnico","Status da Atividade","Endereco",'
            '"Cidade","UF","Numero da WO","Contrato","Node",'
            '"Cod de Baixa 1","Cod de Baixa 2","Numero da O.S 1",'
            '"Numero da O.S 2","Ponto 1","Ponto 2","Status da O.S 1",'
            '"Status da O.S 2","Tipo O.S 1","Tipo O.S 2","Workzone key"\n'
            '"16/07/26","","concluido","","","","","","",'
            '"","","","","","","","","","",""\n'
            '"16/07/26","Z1","pendente","R TESTE","NATAL","RN",'
            '"01695|1","123","NTL01","430","409","100","101",'
            '"1","2","Pendente","Pendente","RETIRAR EMTA",'
            '"INSTALAR DECODER","01695NTL01"\n'
        ).encode("utf-8")

        preview = parse_toa_csv(content, "rota.csv")

        self.assertEqual(preview.source_rows, 2)
        self.assertEqual(len(preview.orders), 2)
        self.assertEqual(preview.orders[0].os_number, "100")
        self.assertEqual(preview.orders[1].os_number, "101")
        self.assertEqual(preview.orders[1].os_type, "INSTALAR DECODER")
        self.assertEqual(preview.orders[1].close_code, "409")

    def test_rejects_non_toa_csv(self) -> None:
        with self.assertRaisesRegex(ValueError, "colunas ausentes"):
            parse_toa_csv(b"a,b\n1,2\n")

    def test_reads_meal_timeline_and_inherits_previous_technician(self) -> None:
        content = (
            '"Login do Tecnico","Data","Status da Atividade","Intervalo de Tempo",'
            '"Inicio","Fim","Inicio - Fim","Duracao","Tipo de Atividade",'
            '"Tipo de Atividade","Cidade","UF","Contrato","Numero da WO",'
            '"Numero da O.S 1","Tipo O.S 1"\n'
            '"Z1","08/08/26","pendente","08:00 - 12:00","08:10","09:00",'
            '"08:10 - 09:00","00:50","Normal","Instalacao","NATAL","RN",'
            '"123","WO1","100","INSTALACAO"\n'
            '"","08/08/26","pendente","12:00 - 14:00","12:15","14:15",'
            '"12:15 - 14:15","02:00","Normal","Refeicao","","","","","",""\n'
            '"","08/08/26","pendente","","","","","","Normal",'
            '"Refeicao","","","","","",""\n'
        ).encode("utf-8")

        activities = parse_toa_timeline_activities(content)

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].technician, "Z1")
        self.assertEqual(activities[0].label, "REFEICAO")
        self.assertEqual(activities[0].started_at, "12:15")
        self.assertEqual(activities[0].ended_at, "14:15")

    def test_builds_the_same_xml_shape_used_by_the_official_client(self) -> None:
        preview = parse_toa_csv(self._complete_csv(), "rota.csv")

        xml = build_toa_xml(preview)

        self.assertIn("<CodigoServico>RETIRAR EMTA</CodigoServico>", xml)
        self.assertIn("<Endereco>R TESTE</Endereco>", xml)
        self.assertIn("<Numero>10</Numero>", xml)
        self.assertIn("<Complemento>,APT 2</Complemento>", xml)
        self.assertIn("<DataAgendamento>16/07/2026</DataAgendamento>", xml)
        self.assertTrue(xml.endswith("</OrdensDeServico>\r\n"))

    def test_protocol_packet_chunks_and_parses_row_status(self) -> None:
        root = Path(__file__).resolve().parents[1]
        preview = parse_toa_csv(self._complete_csv(), "rota.csv")
        protocol = TOAImportProtocol(
            root / "import_protocol_templates.json",
            49127,
        )

        packet = protocol.build_packet(preview)
        self.assertIn(build_toa_xml(preview).encode("utf-16le"), packet)
        self.assertIn((49127).to_bytes(4, "little"), packet)
        self.assertNotIn((313101).to_bytes(4, "little"), protocol.suffix)

        def short(value: str) -> bytes:
            encoded = value.encode("cp1252")
            return bytes((len(encoded),)) + encoded

        order = preview.orders[0]
        result_row = b"".join(
            (
                short(order.os_number),
                short("NATAL"),
                short("NTL01"),
                short("CLIENTE"),
                short("R TESTE"),
                short("RETIRAR EMTA"),
                b"\x00" * 4,
                short("08:00 - 11:00"),
                short("Z1"),
                short("OS JA CADASTRADA"),
            )
        )
        result = protocol.parse_result(result_row, preview)

        self.assertEqual(result["imported"], 0)
        self.assertEqual(result["not_imported"], 1)
        self.assertEqual(result["orders"][0]["import_status"], "OS JA CADASTRADA")

    def test_packet_uses_a_captured_official_datasnap_chunk_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        preview = parse_toa_csv(self._complete_csv(), "rota.csv")
        preview = type(preview)(
            filename=preview.filename,
            source_rows=24,
            orders=preview.orders * 24,
        )
        protocol = TOAImportProtocol(
            root / "import_protocol_templates.json",
            313101,
        )

        packet = protocol.build_packet(preview)
        chunks = protocol.chunks(packet)

        self.assertEqual(protocol.chunk_size, 30_720)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 30_729)
        self.assertEqual(chunks[0][-9:], protocol.transport_trailer)
        self.assertEqual(
            struct.unpack_from(">H", packet, protocol.chunk_length_offset)[0],
            30_720 - 23,
        )
        rebuilt = chunks[0][: -len(protocol.transport_trailer)] + b"".join(
            chunks[1:]
        )
        self.assertEqual(rebuilt, packet)

    def test_result_length_is_only_enforced_for_a_short_fragment(self) -> None:
        complete = bytearray(23_424)
        struct.pack_into("<I", complete, 20, 91)
        self.assertIsNone(TOAImportProtocol.incomplete_result_length(complete))

        incomplete = bytearray(100)
        struct.pack_into("<I", incomplete, 20, 1_000)
        self.assertEqual(
            TOAImportProtocol.incomplete_result_length(incomplete),
            1_028,
        )

    def test_parses_the_observed_125_row_result_without_losing_orders(self) -> None:
        root = Path(__file__).resolve().parents[1]
        original = parse_toa_csv(self._complete_csv(), "rota.csv").orders[0]
        orders = tuple(
            replace(original, os_number=str(2_640_000_000 + index))
            for index in range(125)
        )
        preview = type(parse_toa_csv(self._complete_csv(), "rota.csv"))(
            filename="Atividades-NTL-DMV_ADM.csv",
            source_rows=129,
            orders=orders,
        )

        def short(value: str) -> bytes:
            encoded = value.encode("cp1252")
            return bytes((len(encoded),)) + encoded

        payload = bytearray()
        for index, order in enumerate(orders):
            status = (
                "IMPORTADA COM SUCESSO"
                if index < 80
                else "DATA/INSTALADOR ATUALIZADO"
            )
            payload.extend(
                b"".join(
                    (
                        short(order.os_number),
                        short("NATAL"),
                        short("NTL01"),
                        short("CLIENTE"),
                        short("R TESTE"),
                        short("RETIRAR EMTA"),
                        b"\x00" * 4,
                        short("08:00 - 11:00"),
                        short("Z1"),
                        short(status),
                    )
                )
            )

        protocol = TOAImportProtocol(
            root / "import_protocol_templates.json",
            313101,
        )
        result = protocol.parse_result(bytes(payload), preview)

        self.assertEqual(result["count"], 125)
        self.assertEqual(result["imported"], 80)
        self.assertEqual(result["not_imported"], 45)
        self.assertEqual(len(result["orders"]), 125)

    def test_single_chunk_includes_transport_trailer_and_valid_prefix(self) -> None:
        root = Path(__file__).resolve().parents[1]
        preview = parse_toa_csv(self._complete_csv(), "rota.csv")
        protocol = TOAImportProtocol(
            root / "import_protocol_templates.json",
            313101,
        )
        packet = protocol.build_packet(preview)
        chunks = protocol.chunks(packet)
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].endswith(protocol.transport_trailer))
        self.assertEqual(chunks[0][20], 0x10)

    def test_ignores_cancelled_and_suspended_activities_and_records_exclusions(self) -> None:
        content = (
            '"Data","Login do Tecnico","Status da Atividade","Endereco",'
            '"Complemento Endereco","Bairro","CEP Codigo Postal",'
            '"Intervalo de Tempo","Cidade","UF","Numero da WO",'
            '"Contrato","Node","Numero da O.S 1","Tipo O.S 1","Status da O.S 1"\n'
            '"16/07/26","Z1","pendente","R TESTE, 10","","CENTRO","59000-000",'
            '"08:00 - 11:00","NATAL","RN","01695|1","123","NTL01","100","87 - RETIRAR EMTA","Pendente"\n'
            '"16/07/26","Z1","cancelado","R TESTE, 20","","CENTRO","59000-000",'
            '"08:00 - 11:00","NATAL","RN","01695|2","124","NTL01","101","87 - RETIRAR EMTA","Cancelado"\n'
            '"16/07/26","Z1","suspenso","R TESTE, 30","","CENTRO","59000-000",'
            '"08:00 - 11:00","NATAL","RN","01695|3","125","NTL01","102","87 - RETIRAR EMTA","Pendente"\n'
        ).encode("utf-8")

        preview = parse_toa_csv(content, "rota.csv")

        self.assertEqual(len(preview.orders), 1)
        self.assertEqual(preview.orders[0].os_number, "100")
        self.assertEqual(len(preview.scope_exclusions), 2)
        excluded_os = {item["os_number"] for item in preview.scope_exclusions}
        self.assertEqual(excluded_os, {"101", "102"})

    def test_unpacks_valid_zip_containing_csv(self) -> None:
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Atividades-NTL-DMV_08_08_26.csv", self._complete_csv())
        zip_bytes = buf.getvalue()

        preview = parse_toa_csv(zip_bytes, "export.zip")
        self.assertEqual(preview.filename, "Atividades-NTL-DMV_08_08_26.csv")
        self.assertEqual(len(preview.orders), 1)
        self.assertEqual(preview.orders[0].os_number, "100")

    def test_rejects_gravador_imperium_capture_zip_with_clear_message(self) -> None:
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("gravador.pcapng", b"dummy pcapng content")
            z.writestr("INFORMACOES.txt", b"captura do gravador imperium")
        zip_bytes = buf.getvalue()

        with self.assertRaisesRegex(ValueError, "captura do Gravador Imperium"):
            parse_toa_csv(zip_bytes, "gravador.zip")

    def test_raises_when_all_orders_are_cancelled(self) -> None:
        content = (
            '"Data","Login do Tecnico","Status da Atividade","Endereco",'
            '"Complemento Endereco","Bairro","CEP Codigo Postal",'
            '"Intervalo de Tempo","Cidade","UF","Numero da WO",'
            '"Contrato","Node","Numero da O.S 1","Tipo O.S 1"\n'
            '"16/07/26","Z1","cancelado","R TESTE, 10","","CENTRO","59000-000",'
            '"08:00 - 11:00","NATAL","RN","01695|1","123","NTL01","100","87 - RETIRAR EMTA"\n'
        ).encode("utf-8")

        with self.assertRaisesRegex(ValueError, "estao canceladas ou suspensas"):
            parse_toa_csv(content, "rota.csv")


if __name__ == "__main__":
    unittest.main()
