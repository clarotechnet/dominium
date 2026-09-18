import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from imperium_api import Order
from technician_directory import TechnicianDirectory
from toa_context import TOAContextIndex
from toa_import import parse_toa_csv


class TechnicianDirectoryTests(unittest.TestCase):
    def test_resolves_login_and_enriches_preview_without_changing_protocol_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "technicians.json"
            path.write_text(
                json.dumps(
                    {
                        "source": {"filename": "cadastro.xlsx"},
                        "technicians": [
                            {
                                "login": "Z631400",
                                "name": "ROSA TESTE",
                                "plate": "ABC1D23",
                                "teams": ["Adesao e Servico"],
                                "profiles": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            directory_index = TechnicianDirectory(path)
            content = (
                "Data,Login do Tecnico,Status da Atividade,Cidade,UF,Contrato,"
                "Numero da WO,Numero da O.S 1,Tipo O.S 1\n"
                "18/07/26,z631400,pendente,NATAL,RN,4224699,01695|1,2646000000,"
                "RETIRAR EMTA\n"
            ).encode("utf-8")

            preview = directory_index.enrich_preview(parse_toa_csv(content))
            order = preview.orders[0]

            self.assertEqual(order.technician, "z631400")
            self.assertEqual(order.technician_login, "Z631400")
            self.assertEqual(order.technician_name, "ROSA TESTE")
            self.assertEqual(directory_index.resolve("rosa teste")["plate"], "ABC1D23")

    def test_public_payload_never_contains_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "technicians.json"
            path.write_text(
                json.dumps(
                    {
                        "technicians": [
                            {
                                "login": "Z1",
                                "name": "TECNICO TESTE",
                                "plate": "",
                                "teams": [],
                                "profiles": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = TechnicianDirectory(path).public_dict()

            serialized = json.dumps(payload).lower()
            self.assertNotIn("senha", serialized)
            self.assertNotIn("password", serialized)
            self.assertEqual(payload["count"], 1)

    def test_exposes_sanitized_toa_identity_for_new_technicians(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "technicians.json"
            path.write_text(
                json.dumps(
                    {
                        "technicians": [
                            {
                                "login": "T7963665",
                                "name": "TECNICO TOA",
                                "plate": "",
                                "teams": ["NTL-DMV"],
                                "profiles": ["natal"],
                                "toa": {
                                    "resource_id": "1180",
                                    "user_id": "2450",
                                    "city": "Natal",
                                    "bucket": "NTL-DMV",
                                    "city_status": "identified",
                                    "password": "nao deve sair",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = TechnicianDirectory(path).public_dict()
            technician = payload["technicians"][0]

            self.assertEqual(technician["login"], "T7963665")
            self.assertEqual(technician["city"], "NATAL")
            self.assertEqual(technician["bucket"], "NTL-DMV")
            self.assertEqual(technician["toa"]["resource_id"], "1180")
            self.assertNotIn("password", json.dumps(payload).lower())

    def test_toa_context_resolves_login_but_marks_its_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "technicians.json"
            config.write_text(
                json.dumps(
                    {
                        "technicians": [
                            {
                                "login": "Z595403",
                                "name": "ADRIANO COSTA DA SILVA",
                                "plate": "",
                                "teams": [],
                                "profiles": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            export_dir = root / "logs" / "toa-exports" / "20260718" / "130000"
            export_dir.mkdir(parents=True)
            (export_dir / "Atividades-NTL-DMV_18_07_26.csv").write_text(
                "Data,Login do Tecnico,Status da Atividade,Cidade,UF,Contrato,"
                "Numero da WO,Numero da O.S 1,Tipo O.S 1\n"
                "18/07/26,Z595403,pendente,NATAL,RN,4231016,01695|1,"
                "2646770729,ADESAO - INSTALAR PONTO VIRTUA\n",
                encoding="utf-8",
            )
            directory_index = TechnicianDirectory(config)
            context = TOAContextIndex(root, directory_index.resolve)

            rows = context.enrich(
                "natal",
                dt.date(2026, 7, 18),
                [Order(2162769, "2646770729", "4231016", 10, "SERVICO")],
            )

            self.assertEqual(rows[0]["technician"], "ADRIANO COSTA DA SILVA")
            self.assertEqual(rows[0]["technician_login"], "Z595403")
            self.assertEqual(rows[0]["technician_source"], "toa_export")


if __name__ == "__main__":
    unittest.main()
