"""Tests for the package supplied on 2026-11-04. Network is NEVER used."""
import datetime as dt
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"integrations"/"serial_consult"))
import used_equipment_report as report


class ContractTests(unittest.TestCase):
    def test_contract_matches_only_consolidado_and_por_os(self):
        data=report.load_contract()
        self.assertEqual(set(data["dataset_modes"]),{"consolidado","por_os"})
        self.assertEqual(data["server_class"],"TDtmOrdemServico")
        self.assertEqual(data["prepare_only_method"],report.PREPARE_METHOD)
        self.assertNotIn("Dspsp_EquipamentosUtilizadosParceiro",str(data))

    def test_contract_refuses_provider_substitution(self):
        data=report.load_contract()
        data["dataset_modes"]["consolidado"]["provider"]="Dspsp_EquipamentosUtilizadosParceiro"
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"bad.json"
            file.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):
                report.load_contract(file)

    def test_dates_are_bounded(self):
        today=dt.date(2026,11,4)
        self.assertEqual(report.normalize_range("2026-10-05","2026-11-04",today=today),
                         (dt.date(2026,10,5),today))
        for start,end in (("2026-11-03","2026-11-05"),("2026-11-03","2026-11-02"),
                          ("2026-09-01","2026-11-04"),("03/11/2026","2026-11-04")):
            with self.subTest(start=start,end=end),self.assertRaises(ValueError):
                report.normalize_range(start,end,today=today)

    @staticmethod
    def packet(mode):
        provider=report.PROVIDERS[mode].encode("ascii")
        records=[]
        for name in report.PARAM_NAMES:
            raw=name.encode("utf-16le")
            kind=report.EXPECTED_TYPES[name]
            records.append(report.PARAM_MARKER+struct.pack("<I",len(name))+raw+struct.pack("<I",kind)+b"\0"*8)
        return (bytes([32+len(provider)])+provider+b"!\x01\x60a\x01"+
                b"\x20\x10\x00\x00\x02"+b"".join(records)+report.END_MARKER)

    def test_validates_only_captured_envelope_not_live_result(self):
        for mode in report.PROVIDERS:
            result=report.validate_capture_packet(self.packet(mode),mode)
            self.assertEqual(result["status"],"offline_envelope_only")
            self.assertEqual(result["provider"],report.PROVIDERS[mode])
        with self.assertRaises(ValueError):
            report.validate_capture_packet(self.packet("consolidado"),"por_os")

    def test_never_treats_other_report_as_same_report(self):
        packet=self.packet("consolidado").replace(b"DspConsolidadoEquip",b"OtherDatasetProvider")
        with self.assertRaises(ValueError):
            report.validate_capture_packet(packet,"consolidado")

    def test_no_live_report_without_real_capture(self):
        with self.assertRaises(report.LiveReportNotValidated):
            report.require_live_report_capture()

    def test_prepare_only_never_executes(self):
        calls=[]
        class Fake:
            def __init__(self,host,port,username,password,timeout):
                calls.append(("init",port,timeout))
            def __enter__(self):
                calls.append(("connect",))
                return self
            def __exit__(self,*args):
                calls.append(("close",))
            def prepare(self,name):
                calls.append(("prepare",name))
                return {"result":[{"handle":[101]}]}
            def request(self,*args):
                raise AssertionError("The probe must never issue execute")
        result=report.probe_prepare_only("natal","test-user","test-secret",client_factory=Fake)
        self.assertTrue(result["method_prepared"])
        self.assertFalse(result["query_executed"])
        self.assertFalse(result["report_downloaded"])
        self.assertEqual([v[0] for v in calls],["init","connect","prepare","close"])
        self.assertEqual(calls[2],("prepare","TDtmOrdemServico.AS_GetRecords"))
        with self.assertRaises(ValueError):
            report.probe_prepare_only("arbitrary","u","p",client_factory=Fake)

    def test_executable_version_mismatch_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ClientVCL.exe"
            path.write_bytes(b"MZ"+b" ".join((b"TFrmConEquipUtilizados",b"CdsConsolidadoEquip",
                    b"CdsConsolidadoOS",b"DspConsolidadoEquip",b"DspConsolidadoOS")))
            info=report.check_executable(path)
            self.assertTrue(info["required_markers_present"])
            self.assertFalse(info["same_version_as_zip"])


if __name__=="__main__":
    unittest.main()
