import csv
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from imperium_api import Order
from operation_scope import ImportScope, OperationBlocked
from toa_context import TOAContextIndex
from toa_export_task_recovery import reconcile_export_tasks, recover_tasks_with_refresh


class ToaExportTaskRecoveryTests(unittest.TestCase):
    def test_recovery_csv_cannot_replace_import_scope_between_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            day = dt.date(2026, 11, 26)
            export_root = root / "logs" / "toa-exports"
            day_root = export_root / "20261126"
            name = "Atividades-NTL-DMV_26_11_26.csv"
            original = day_root / "090000" / name
            recovery = day_root / "adhesion-readonly-093903-535586" / name
            original.parent.mkdir(parents=True)
            header = ["Data", "Login do Técnico", "Status da Atividade", "Cidade", "UF",
                      "Contrato", "Numero da WO", "ID da Atividade", "Total de tarefas"]
            row = ["26/11/26", "Z12345", "concluído", "NATAL", "RN", "12345678", "01695|1", "123", "3"]
            for i in range(1, 4):
                header.extend([f"Número da O.S {i}", f"Tipo O.S {i}", f"Status da O.S {i}", f"Cód de Baixa {i}"])
                row.extend([str(2600000000 + i), "ADESAO - INSTALAR PONTO VIRTUA", "Executada", "409"])

            def write(path, fields, values):
                with path.open("w", encoding="utf-8", newline="") as stream:
                    csv.writer(stream).writerows([fields, values])

            write(original, header, row)
            ctx = TOAContextIndex(root)
            orders = [Order(1, "2600000001", "12345678", 10, "ADESAO - INSTALAR PONTO VIRTUA")]
            scope = ImportScope.from_dict(ctx.enrich("natal", day, orders)[0]["import_scope"])
            recovery.parent.mkdir()
            write(recovery, header + ["Observação"], row + ["Consulta auxiliar"])
            now = dt.datetime(2026, 11, 26, 9, 39, 4).astimezone()
            os.utime(original, (now.timestamp() - 1800,) * 2)
            os.utime(recovery, (now.timestamp() - 1,) * 2)
            capture = {"contract": "12345678", "aid": "123", "route_name": "NTL-DMV", "scheduled_date": day.isoformat(),
                       "activity_status": "complete", "assigned_technician": {"external_id": "Z12345"},
                       "tasks": [{"os_number": "2600000001", "status": "E", "close_code": "409"}]}
            self.assertEqual(len(reconcile_export_tasks(capture, export_root, now=now)), 3)
            self.assertEqual(ctx.enrich("natal", day, orders)[0]["import_scope"]["source_hash"], scope.source_hash)
            ctx.validate_scope_source(scope, day)

            latest = day_root / "100000" / name
            latest.parent.mkdir()
            write(latest, header + ["Observação"], row + ["Nova coleta regular"])
            self.assertNotEqual(ctx.enrich("natal", day, orders)[0]["import_scope"]["source_hash"], scope.source_hash)
            with self.assertRaises(OperationBlocked):
                ctx.validate_scope_source(scope, day)

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

            calls = []
            orders = [{"contract": "12345678", "num_os": "2600000003", "status": "EM CAMPO"}]
            def refresh(route, day):
                calls.append((route, day))
                write([row])
            self.assertEqual(len(recover_tasks_with_refresh(cap, root, orders, refresh, now=now)), 3)
            self.assertEqual(calls, [("NTL-DMV", now.date())])
            self.assertEqual(len(recover_tasks_with_refresh(cap, root, orders, refresh, now=now)), 3)
            self.assertEqual(len(calls), 1)
            write([row], age=901)
            self.assertEqual(recover_tasks_with_refresh(dict(cap, route_name="NTL-DMV_ADM"), root, orders, refresh, now=now), cap["tasks"])
            self.assertEqual(recover_tasks_with_refresh(cap, root, [], refresh, now=now), cap["tasks"])
            self.assertEqual(len(calls), 1)

    def test_runtime_patch_is_scoped_and_idempotent(self):
        from integrations.desc_runtime.patch_runtime_safety import patch_adhesion_fresh_export_runtime
        source = ('def match(profile, result):\n'
                  '    all_status_rows = result.get("imperium_all_orders")\n'
                  '    for capture in result.get("results", []):\n'
                  '        if profile.key == "natal":\n'
                  '            from toa_export_task_recovery import reconcile_export_tasks\n'
                  '            capture["tasks"] = reconcile_export_tasks(capture, ROOT / "logs" / "toa-exports")\n')
        patched = patch_adhesion_fresh_export_runtime(source)
        self.assertIn("TOA_AUTOMATION.running or TOA_BUCKET_COLLECTOR.running", patched)
        self.assertEqual(patch_adhesion_fresh_export_runtime(patched), patched)
        with self.assertRaises(ValueError):
            patch_adhesion_fresh_export_runtime("def match(): pass")
