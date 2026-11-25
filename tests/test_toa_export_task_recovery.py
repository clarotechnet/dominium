import csv
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from toa_export_task_recovery import reconcile_export_tasks


class ToaExportTaskRecoveryTests(unittest.TestCase):
    def test_exact_fresh_export_recovers_only_missing_tasks(self):
        with tempfile.TemporaryDirectory() as root:
            now = dt.datetime(2026, 11, 25, 17, 0).astimezone()
            path = Path(root) / "20261125" / "170000" / "Atividades-NTL-DMV_25_11_26.csv"
            path.parent.mkdir(parents=True)
            row = {"Contrato": "12345678", "ID da Atividade": "123", "Data": "25/11/26",
                   "Login do T\u00e9cnico": "Z12345", "Status da Atividade": "conclu\u00eddo", "Total de tarefas": "3"}
            for i in range(1, 4):
                row[f"N\u00famero da O.S {i}"] = str(2600000000+i)
                row[f"Status da O.S {i}"] = "Executada"
                row[f"C\u00f3d de Baixa {i}"] = "409 - Servi\u00e7o conclu\u00eddo"
            def write(rows, age=1):
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(row))
                    writer.writeheader()
                    writer.writerows(rows)
                os.utime(path, (now.timestamp()-age, now.timestamp()-age))
            cap = {"contract": "12345678", "aid": "123", "route_name": "NTL-DMV", "scheduled_date": "2026-11-25",
                   "activity_status": "complete", "assigned_technician": {"external_id": "Z12345"},
                   "tasks": [{"os_number": "2600000001", "status": "E", "close_code": "409"},
                             {"os_number": "2600000003", "imperium_only": True}]}
            write([row])
            result = reconcile_export_tasks(cap, root, now=now)
            self.assertEqual([t["os_number"] for t in result], ["2600000001","2600000002","2600000003"])
            self.assertTrue(result[2]["registry_only"])
            for bad in [dict(row, **{"Login do T\u00e9cnico": "Z99999"}), dict(row, **{"C\u00f3d de Baixa 1": "125"}),
                        dict(row, **{"Total de tarefas": "4"}), dict(row, **{"ID da Atividade": "999"})]:
                write([bad])
                self.assertEqual(reconcile_export_tasks(cap, root, now=now), cap["tasks"])
            write([row,row])
            self.assertEqual(reconcile_export_tasks(cap, root, now=now), cap["tasks"])
            write([row], age=901)
            self.assertEqual(reconcile_export_tasks(cap, root, now=now), cap["tasks"])
