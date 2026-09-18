import tempfile
import threading
import unittest
from pathlib import Path

from app import _automatic_toa_import
from toa_automation import DEFAULT_TIMES, TOAAutomation


class FakeExporter:
    def __init__(self, _credentials_path, download_root, *, headless=True):
        self.download_root = Path(download_root)
        self.headless = headless

    def __enter__(self):
        self.download_root.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *_args):
        return None

    def export_route(self, route):
        path = self.download_root / f"Atividades-{route}-teste.csv"
        path.write_text("arquivo de teste", encoding="utf-8")
        return path


class TOAAutomationScheduleTests(unittest.TestCase):
    def test_daily_schedule_uses_the_current_operational_times(self) -> None:
        self.assertEqual(DEFAULT_TIMES, ("08:20", "09:00", "11:00", "13:00", "15:00", "17:20"))


class BlockingExporter(FakeExporter):
    release = threading.Event()

    def export_route(self, route):
        self.release.wait(2)
        return super().export_route(route)


class TOAAutomationTests(unittest.TestCase):
    def test_route_error_does_not_stop_the_remaining_routes(self):
        routes = (
            {"route": "NTL-DMV_ADM", "target": "rn", "label": "Natal"},
            {"route": "FTZ-DMV_ADM", "target": "ftz", "label": "Fortaleza"},
            {"route": "MRO-DMV", "target": "mro", "label": "Mossoro"},
        )
        visited = []

        def callback(route, _path):
            visited.append(route["route"])
            if route["route"] == "FTZ-DMV_ADM":
                raise TimeoutError("servidor indisponivel")
            if route["route"] == "MRO-DMV":
                return {"status": "vazia", "imported": 0, "not_imported": 0}
            return {"status": "concluida", "imported": 8, "not_imported": 1}

        with tempfile.TemporaryDirectory() as directory:
            automation = TOAAutomation(
                Path(directory),
                callback,
                routes=routes,
                exporter_factory=FakeExporter,
            )

            self.assertTrue(automation.trigger("manual"))
            automation.worker_thread.join(timeout=3)
            state = automation.public_state()

            self.assertEqual(visited, [item["route"] for item in routes])
            self.assertFalse(state["running"])
            self.assertFalse(state["last_run"]["ok"])
            self.assertEqual(
                [item["status"] for item in state["last_run"]["routes"]],
                ["concluida", "erro", "vazia"],
            )
            self.assertTrue(automation.history_path.is_file())

    def test_second_trigger_is_rejected_while_worker_is_running(self):
        BlockingExporter.release.clear()
        routes = ({"route": "NTL-DMV_ADM", "target": "rn", "label": "Natal"},)
        with tempfile.TemporaryDirectory() as directory:
            automation = TOAAutomation(
                Path(directory),
                lambda _route, _path: {"status": "vazia"},
                routes=routes,
                exporter_factory=BlockingExporter,
            )

            self.assertTrue(automation.trigger("manual"))
            self.assertFalse(automation.trigger("manual"))
            BlockingExporter.release.set()
            automation.worker_thread.join(timeout=3)
            self.assertFalse(automation.public_state()["running"])

    def test_header_only_csv_is_valid_empty_route_and_never_reaches_imperium(self):
        headers = (
            "Data,Login do Tecnico,Status da Atividade,Cidade,UF,Contrato,"
            "Numero da WO,Numero da OS 1,Tipo OS 1\r\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Atividades-NTL-DMV_ADM.csv"
            path.write_text(headers, encoding="utf-8")

            result = _automatic_toa_import(
                {"route": "NTL-DMV_ADM", "target": "rn"},
                path,
            )

            self.assertEqual(result["status"], "vazia")
            self.assertEqual(result["imported"], 0)
            self.assertFalse(result["requires_human"])


if __name__ == "__main__":
    unittest.main()
