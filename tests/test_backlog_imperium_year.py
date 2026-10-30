import datetime as dt
import unittest

from backlog_imperium_year import (
    PROFILES,
    historical_record,
    normalize_city,
    plan_days,
    valid_close_code,
    year_window,
)

class BacklogYearPlannerTests(unittest.TestCase):
    def test_year_to_yesterday(self):
        w = year_window(dt.date(2026, 10, 30))
        self.assertEqual((w.start, w.end, w.days), (dt.date(2025, 10, 30), dt.date(2026, 10, 29), 365))

    def test_leap_day(self):
        w = year_window(dt.date(2024, 2, 29))
        self.assertEqual(w.start, dt.date(2023, 2, 28))
        self.assertEqual(w.end, dt.date(2024, 2, 28))

    def test_initial_run_paced_4_profiles(self):
        tasks = plan_days(today=dt.date(2026, 10, 30), max_days_per_profile=2)
        self.assertEqual(len(tasks), 8)
        self.assertEqual({t.profile for t in tasks}, set(PROFILES))
        self.assertTrue(all(t.date <= dt.date(2026, 10, 29) for t in tasks))

    def test_incremental_resume_after_checkpoint(self):
        checkpoints = {"natal": dt.date(2026, 10, 27), "recife": dt.date(2026, 10, 29)}
        tasks = plan_days(today=dt.date(2026, 10, 30), checkpoints=checkpoints, max_days_per_profile=3)
        self.assertEqual([t.date for t in tasks if t.profile == "natal"], [dt.date(2026,10,28), dt.date(2026,10,29)])
        self.assertEqual([t for t in tasks if t.profile == "recife"], [])

    def test_reject_invalid_code(self):
        for value in (None, "", "0", "000", "OS409", "409.0"):
            self.assertIsNone(valid_close_code(value))
        for value in ("430","106","512"):
            self.assertEqual(valid_close_code(value), value)

    def test_record_keeps_exact_identity(self):
        row = historical_record(profile="natal",activity_day=dt.date(2026,10,29),id_os=123,
          os_number="260100001",contract="12345678",code="430")
        self.assertEqual(row["idempotency_key"],"natal:123:2026-10-29")
        self.assertEqual(row["baixa_code"],"430")

    def test_unknown_close_code_cannot_be_imported(self):
        with self.assertRaises(ValueError):
            historical_record(profile="natal", activity_day=dt.date(2026,10,29), id_os=123,
              os_number="123", contract="456789", code=None)

    def test_city_normalization(self):
        self.assertEqual(normalize_city("MOSSORÓ"),"MOSSORO")
        self.assertEqual(normalize_city("Parnamirim"),"NATAL/PARNAMIRIM")

if __name__=="__main__":
    unittest.main()
