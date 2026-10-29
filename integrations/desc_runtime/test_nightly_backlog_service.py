import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from nightly_backlog_service import NightlyBacklogService
from nightly_backlog_106 import BRAZIL


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.current = dt.datetime(2026, 9, 8, 22, 59, tzinfo=BRAZIL)
        self.runner = Mock(return_value={'profiles': {'natal': {'errors': [], 'confirmed': 1}}})
        self.service = NightlyBacklogService(self.temp.name, runner=self.runner, clock=lambda: self.current, rollover_path=self.temp.name + '/capture-rotation.json')

    def test_disabled_by_default_and_never_before_23(self):
        self.service.tick()
        self.service.set_enabled(True)
        self.service.tick()
        self.runner.assert_not_called()
        self.assertFalse((Path(self.temp.name) / 'capture-rotation.json').exists())

    def test_actual_batch_start_rotates_visible_capture_window_once(self):
        self.service.set_enabled(True)
        self.current = self.current.replace(hour=23)
        self.service.tick()
        marker = json.loads((Path(self.temp.name) / 'capture-rotation.json').read_text(encoding='utf-8'))
        self.assertEqual(marker['source'], 'nightly_backlog_start')
        self.assertEqual(marker['date'], '2026-09-08')
        self.assertEqual(marker['retention_days'], 7)
        self.assertEqual(self.runner.call_count, 1)
        self.service.tick()
        self.assertEqual(self.runner.call_count, 1)

    def test_once_daily_across_server_restart(self):
        self.service.set_enabled(True)
        self.current = self.current.replace(hour=23)
        self.service.tick()
        self.service.tick()
        restarted = NightlyBacklogService(self.temp.name, runner=self.runner, clock=lambda: self.current, rollover_path=self.temp.name + '/capture-rotation.json')
        restarted.tick()
        self.assertEqual(self.runner.call_count, 1)
        self.assertEqual(restarted.status()['today']['state'], 'finished')
        self.current = self.current.replace(day=9)
        restarted.tick()
        self.assertEqual(self.runner.call_count, 2)

    def test_pause_persists_and_cancels_remaining_work(self):
        self.service.set_enabled(True)
        self.service.set_enabled(False)
        self.current = self.current.replace(hour=23)
        self.service.tick()
        self.runner.assert_not_called()
        self.assertFalse(self.service.status()['enabled'])
        with self.assertRaises(ValueError):
            self.service.set_enabled('true')

    def test_failure_is_recorded_without_automatic_resubmit(self):
        self.service.set_enabled(True)
        self.runner.side_effect = ValueError('teste simulado')
        self.current = self.current.replace(hour=23)
        self.service.tick()
        self.service.tick()
        self.assertEqual(self.runner.call_count, 1)
        self.assertEqual(self.service.status()['today']['state'], 'review_required')

    def test_no_backfill_after_midnight_and_stop(self):
        self.service.set_enabled(True)
        self.current = self.current.replace(day=9, hour=0)
        self.service.tick()
        self.current = self.current.replace(hour=23)
        self.service.stop()
        self.service.tick()
        self.runner.assert_not_called()

    def test_lifecycle_starts_in_server_and_stops(self):
        self.service.start()
        self.assertTrue(self.service.status()['server_scheduler_active'])
        self.service.stop()
        self.assertFalse(self.service.status()['server_scheduler_active'])


if __name__ == '__main__':
    unittest.main()
