from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from toa_adm_task_splitter import find_latest_adm_tasks, parse_adm_tasks


class TOAADMTaskSplitterTests(unittest.TestCase):
    def test_shared_serial_same_code_is_preserved_for_one_time_allocation(self):
        tasks = parse_adm_tasks({
            "Número da O.S 1": "2663000001", "Cód de Baixa 1": "430",
            "Número da O.S 2": "2663000002", "Cód de Baixa 2": "430",
            "Validação Baixa": "Tarefa 1 : Desinstalação do equipamento de serial: SHARED1. "
                               "Tarefa 2 : Desinstalação do equipamento de serial: SHARED1.",
        })
        self.assertEqual(len(tasks),2)
        self.assertEqual(tasks[0].removed_serials,tasks[1].removed_serials)

    def test_shared_serial_different_codes_blocks(self):
        with self.assertRaisesRegex(ValueError,'adm_task_equipment_overlap'):
            parse_adm_tasks({
                "Número da O.S 1": "2663000001", "Cód de Baixa 1": "430",
                "Número da O.S 2": "2663000002", "Cód de Baixa 2": "409",
                "Validação Baixa": "Tarefa 1 : Desinstalação do equipamento de serial: SHARED1. "
                                   "Tarefa 2 : Instalação do equipamento de serial: SHARED1.",
            })
    def test_seven_430_tasks_keep_exact_serial_groups(self) -> None:
        row = {
            "Contrato": "9339303",
            **{
                f"Número da O.S {index}": os_number
                for index, os_number in enumerate(
                    (
                        "2658828434",
                        "2658828445",
                        "2659149756",
                        "2659149767",
                        "2659149778",
                        "2659149789",
                        "2659149790",
                    ),
                    start=1,
                )
            },
            **{f"Cód de Baixa {index}": "430" for index in range(1, 8)},
            "Validação Baixa": (
                "Tarefa 1 : Desinstalação do equipamento de serial: 24E4CEEE3B29. "
                "Tarefa 2 : Desinstalação do equipamento de serial: 24E4CEEDF57E. "
                "Tarefa 3 : Desinstalação do equipamento de serial: 215614081325. "
                "Desinstalação do equipamento de serial: 216358443454. "
                "Tarefa 4 : Desinstalação do equipamento de serial: 3C82C066F120. "
                "Tarefa 5 : Desinstalação do equipamento de serial: 229818199709. "
                "Desinstalação do equipamento de serial: 246619043046. "
                "Tarefa 6 : Desinstalação do equipamento de serial: 216831713851. "
                "Desinstalação do equipamento de serial: 246259372344. "
                "Tarefa 7 : Desinstalação do equipamento de serial: 229803539109. "
                "Desinstalação do equipamento de serial: 246608854352."
            ),
        }
        tasks = parse_adm_tasks(row, source_file="fixture.csv")

        self.assertEqual(
            [
                (task.os_number, task.close_code, task.removed_serials)
                for task in tasks
            ],
            [
                ("2658828434", "430", ("24E4CEEE3B29",)),
                ("2658828445", "430", ("24E4CEEDF57E",)),
                ("2659149756", "430", ("215614081325", "216358443454")),
                ("2659149767", "430", ("3C82C066F120",)),
                ("2659149778", "430", ("229818199709", "246619043046")),
                ("2659149789", "430", ("216831713851", "246259372344")),
                ("2659149790", "430", ("229803539109", "246608854352")),
            ],
        )

    def test_requested_activity_rejects_contract_row_without_activity_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "logs" / "toa-exports" / "20261001" / "130000"
            target.mkdir(parents=True)
            (target / "Atividades-NTL-DMV_ADM_01_10_26.csv").write_text(
                "Contrato;ID da Atividade;Número da O.S 1;Cód de Baixa 1;"
                "Validação Baixa\n"
                "1654196;;2659124344;430;"
                "Tarefa 1 : Desinstalação do equipamento de serial: "
                "216464005675.\n",
                encoding="utf-8",
            )

            tasks = find_latest_adm_tasks(
                root,
                contract="1654196",
                activity_id="201435324",
                when=dt.date(2026, 10, 1),
            )

        self.assertEqual(tasks, ())

    def test_lookup_uses_only_natal_or_parnamirim_adm_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            day = root / "logs" / "toa-exports" / "20261001"
            natal = day / "120000"
            foreign = day / "130000"
            natal.mkdir(parents=True)
            foreign.mkdir(parents=True)
            header = (
                "Contrato;ID da Atividade;Número da O.S 1;Cód de Baixa 1;"
                "Validação Baixa\n"
            )
            (natal / "Atividades-PWM-DMV_ADM_01_10_26.csv").write_text(
                header
                + "1654196;201435324;2659124344;430;"
                + "Tarefa 1 : Desinstalação do equipamento de serial: "
                + "216464005675.\n",
                encoding="utf-8",
            )
            (foreign / "Atividades-FTZ-DMV_ADM_01_10_26.csv").write_text(
                header + "1654196;201435324;9999999999;409;Tarefa 1 : .\n",
                encoding="utf-8",
            )

            tasks = find_latest_adm_tasks(
                root,
                contract="1654196",
                activity_id="201435324",
                when=dt.date(2026, 10, 1),
                allowed_routes=("PWM",),
            )

        self.assertEqual([task.os_number for task in tasks], ["2659124344"])
        self.assertEqual([task.close_code for task in tasks], ["430"])
        self.assertIn("PWM-DMV_ADM", tasks[0].source_file)

    def test_409_swap_is_split_from_neighbor_430(self) -> None:
        row = {
            "Contrato": "1654196",
            "Número da O.S 1": "2659124344",
            "Cód de Baixa 1": "430",
            "Tipo O.S 1": "4 - RETIRAR PONTO",
            "Número da O.S 2": "2659125761",
            "Cód de Baixa 2": "409",
            "Tipo O.S 2": "511 - MUD PACOTE ENTREGA STREAMING",
            "Validação Baixa": (
                "Tarefa 1 : Desinstalação do equipamento de serial: 216464005675. "
                "Desinstalação do equipamento de serial: 226034302342. "
                "Tarefa 2 : Troca do equipamento de serial: 216429264159 "
                "pelo de serial: 241786079210. "
                "Desinstalação do equipamento de serial: 226410748901."
            ),
        }

        tasks = parse_adm_tasks(row, source_file="fixture.csv")

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].close_code, "430")
        self.assertEqual(
            tasks[0].removed_serials,
            ("216464005675", "226034302342"),
        )
        self.assertEqual(tasks[1].close_code, "409")
        self.assertEqual(tasks[1].installed_serials, ("241786079210",))
        self.assertEqual(
            tasks[1].removed_serials,
            ("216429264159", "226410748901"),
        )


if __name__ == "__main__":
    unittest.main()
