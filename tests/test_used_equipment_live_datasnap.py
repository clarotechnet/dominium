"""Tests for capture-verified, read-only Equipamentos Utilizados adapter.

Golden hashes are non-sensitive digests; no PCAPs, credentials, or customer rows.
"""
import hashlib
import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.serial_consult.used_equipment_live_datasnap import (
    CAPTURED_SHA256, build_query, fetch_read_only,
)
from integrations.serial_consult.used_equipment_report import validate_capture_packet


class CapturedProtocolTests(unittest.TestCase):
    def test_exact_requests_match_original_clientvcl(self):
        for mode, expected in CAPTURED_SHA256.items():
            with self.subTest(mode=mode):
                packet = build_query("2026-11-03", "2026-11-03", mode=mode,
                                     partner_id=1)
                self.assertEqual(hashlib.sha256(packet).hexdigest(), expected)
                self.assertEqual(len(packet), 605 if mode=="consolidado" else 602)
                data = validate_capture_packet(packet, mode)
                self.assertEqual(len(data["parameter_names"]), 6)
                self.assertEqual(data["provider"],"DspConsolidadoEquip" if mode=="consolidado" else "DspConsolidadoOS")

    def test_other_dates_change_packet(self):
        p1 = build_query("2026-11-02","2026-11-02",mode="consolidado",partner_id=1)
        p2 = build_query("2026-11-03","2026-11-03",mode="consolidado",partner_id=1)
        self.assertNotEqual(p1,p2)

    def test_other_partner_requires_explicit_identifier(self):
        with self.assertRaises(TypeError):
            build_query("2026-11-03","2026-11-03",mode="consolidado")
        for partner in (0, -1, True, "1", 10000):
            with self.subTest(partner=partner), self.assertRaises(ValueError):
                build_query("2026-11-03","2026-11-03",mode="consolidado",partner_id=partner)

    def test_rejects_dangerous_filters_and_invalid_periods(self):
        for group in ("", "anything';DELETE", "Test \n", "A"*16, "á"):
            with self.subTest(group=group), self.assertRaises(ValueError):
                build_query("2026-11-03","2026-11-03",
                            mode="consolidado",partner_id=1,group=group)
        for start,end in (("2026-12-03","2026-12-03"),("2026-10-01","2026-11-03"),
                          ("2026-11-04","2026-11-03")):
            with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                build_query(start,end,mode="por_os",partner_id=1,today=__import__("datetime").date(2026,11,5))

    def test_no_data_received_during_packet_generation(self):
        with patch("datasnap_client.DataSnapClient", side_effect=AssertionError("network forbidden")):
            _ = build_query("2026-11-03","2026-11-03",mode="por_os",partner_id=1)

    def test_fetch_is_read_only_and_requires_explicit_call(self):
        from unittest.mock import MagicMock
        class FakeClient:
            def __init__(self,*args,**kwargs): self.credentials_args=args
            def __enter__(self):return self
            def __exit__(self,*args):pass
        consolidated = [{"Grupo":"TEST","CodigoEquipamento":"01","Equipamento":"item","Identificado":"S","Qtd":"5.00"}]
        orders = [{"DataBaixa":"2026-11-03","NumeroWO":"001","NumOs":"1","CodigoEquipamento":"01",
                   "Equipamento":"item","Qtd":"5.00"}]
        with (
            patch("datasnap_client.DataSnapClient", FakeClient),
            patch("datasnap_client.load_credentials",return_value={"username":"test","password":"placeholder"}),
            patch("imperium_api.ImperiumAPI._handle",return_value=123) as prepare,
            patch("imperium_api.ImperiumAPI._dataset_payload",side_effect=[b"fake1",b"fake2"]) as read,
            patch("integrations.serial_consult.midas_reader.decode_dataset",side_effect=[consolidated,orders]) as decode,
        ):
            data=fetch_read_only("2026-11-03","2026-11-03",profile="natal",
                                 partner_id=1,credential_path=Path("unused"))
        self.assertEqual(len(data["consolidado"]),1)
        self.assertEqual(len(data["por_os"]),1)
        self.assertEqual(prepare.call_args.args[1],"TDtmOrdemServico.AS_GetRecords")
        self.assertEqual(read.call_count,2)
        self.assertEqual(decode.call_count,2)
        for call, provider in zip(read.call_args_list,(b"DspConsolidadoEquip",b"DspConsolidadoOS")):
            self.assertEqual(call.args[2][1:1+len(provider)],provider)

    def test_refuses_other_cities_and_unbounded_timeouts(self):
        for profile in ("invalid", "all", "../../"):
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                fetch_read_only("2026-11-03","2026-11-03",profile=profile,
                                partner_id=1,credential_path=Path("unused"))
        for timeout in (0,999):
            with self.subTest(timeout=timeout),self.assertRaises(ValueError):
                fetch_read_only("2026-11-03","2026-11-03",profile="natal",
                                partner_id=1,credential_path=Path("unused"),
                                timeout=timeout)


if __name__=="__main__":
    unittest.main()
