import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backlog_imperium_service import BacklogHistoryService


class AllStatusesContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []
        class Api:
            def list_orders(api_self, day, *, status, service_type):
                self.calls.append(("list", status, service_type))
                records = {
                    "field": [(100, "1000001", "104")],
                    "completed": [(101, "1000001", "430")],
                    "canceled": [(102, "2000002", "404")],
                    "rescheduled": [(103, "3000003", "306")],
                }
                return [SimpleNamespace(
                    id_os=identifier,num_os=str(identifier),
                    contract=contract,service="DESCONEXAO",
                    status={"field":"EM CAMPO","completed":"CONCLUIDA",
                            "canceled":"CANCELADA","rescheduled":"REAGENDADA"}[status],
                    code=code,
                ) for identifier,contract,code in records.get(status,[])]
            def _fetch_main_payload(api_self, day, *, status, service_type):
                self.calls.append(("raw_all", status, service_type))
                assert status=="all" and service_type=="all"
                return "raw_records"
            def _parse_orders(api_self, payload):
                assert payload=="raw_records"
                known={}
                before=len(self.calls)
                for status_name in ("field","completed","canceled","rescheduled"):
                    for order in api_self.list_orders(dt.date(2026,10,29),status=status_name,service_type="all"):
                        known[order.id_os]=order
                del self.calls[before:]
                known[104]=SimpleNamespace(id_os=104,num_os="104",contract="4000004",
                    service="ADESAO",status=None)
                return list(known.values())
            def _fetch_detail(api_self, identifier, timeout):
                self.calls.append(("detail",identifier))
                return {100:"104",101:"430",102:"404",103:"306",104:"106"}[identifier]
            def _detail_close_code(api_self, detail):
                return detail
        self.api=Api()
        self.svc=BacklogHistoryService(Path(self.tmp.name)/"backlog.db",
            {"natal":SimpleNamespace(api=self.api)},
            clock=lambda:dt.date(2026,10,30),sleep=lambda value:None)

    def _run(self,mode):
        self.svc.start(mode=mode,only_profile="natal",days_per_profile=1)
        self.svc._runner.join(timeout=10)
        self.assertFalse(self.svc._runner.is_alive())
        self.assertEqual(self.svc.snapshot()["run"]["status"],"completed")

    def test_batch_reads_all_status_filters_and_preserves_status(self):
        self._run("batch")
        self.assertEqual([call[1:] for call in self.calls if call[0]=="list"],
                         [(s,"all") for s in ("field","completed","canceled","rescheduled")])
        with self.svc._connect() as conn:
            stored=conn.execute("SELECT contract,status,code FROM history ORDER BY id_os").fetchall()
            self.assertEqual([(r[0],r[1],r[2]) for r in stored],
                         [("1000001","EM CAMPO","104"),("1000001","CONCLUIDA","430"),
                          ("2000002","CANCELADA","404"),("3000003","REAGENDADA","306"),
                          ("4000004","DESCONHECIDO","106")])
        self.assertEqual(self.svc.snapshot()["history"]["confirmed"],5)
        self.assertEqual([x[1:] for x in self.calls if x[0]=="raw_all"],[("all","all")])

    def test_comparison_uses_any_selected_history_not_just_latest(self):
        self._run("batch")
        with self.svc._connect() as conn:
            conn.execute("INSERT INTO route_rows(route_hash,row_num,contract,city) VALUES('demo',1,'1000001','NATAL/PARNAMIRIM')")
            conn.commit()
        result=self.svc.compare()
        self.assertEqual(result["rows"][0]["classification"],"SEGURAR")
        self.assertEqual(result["rows"][0]["historical_code"],"430")
        self.assertEqual(result["rows"][0]["historical_status"],"CONCLUIDA")

    def test_probe_does_not_persist_even_when_querying_all_statuses(self):
        self._run("probe")
        self.assertEqual(self.svc.snapshot()["history"],{})
        self.assertEqual(self.svc.snapshot()["checkpoints"],{})
        self.assertEqual([c[1] for c in self.calls if c[0]=="list"],
                         ["field","completed","canceled","rescheduled"])

if __name__=="__main__":unittest.main()
