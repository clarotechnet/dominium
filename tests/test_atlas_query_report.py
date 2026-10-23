"""Safe report generator: no duplicate Atlas task after uncertainty."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"integrations"/"serial_consult"/"atlas_query_report.py"
spec=importlib.util.spec_from_file_location("atlas_query_report",FILE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeBrowser:
    submissions=0
    closed=0
    fail=False

    def open(self):pass
    def inspect_parameters(self,city,location):
        return {"form":True,"cityMatch":True,"localMatch":True,
                "generator":True,"reportService":True}
    def submit_once(self,city,location):
        FakeBrowser.submissions+=1
        if FakeBrowser.fail:raise RuntimeError("Connection timed out after POST")
        return "2577663211"
    def close(self):FakeBrowser.closed+=1


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"state.sqlite3"
        FakeBrowser.submissions=0
        FakeBrowser.closed=0
        FakeBrowser.fail=False

    def test_city_atlas_codes(self):
        self.assertEqual(mod.CITY,{"natal":"179","mossoro":"592",
                                   "fortaleza":"198","recife":"57"})
        self.assertEqual(mod.LOCATION["empreiteira"],"5")

    def test_dry_run_does_not_create_job(self):
        answer=mod.generate("mossoro","empreiteira",dry_run=True,
                           db_path=self.db,chrome_factory=FakeBrowser)
        self.assertTrue(answer["dry_run"])
        self.assertFalse(self.db.exists())
        self.assertEqual(FakeBrowser.submissions,0)
        self.assertEqual(FakeBrowser.closed,1)

    def test_submit_persists_id_and_does_not_resubmit(self):
        first=mod.generate("mossoro","empreiteira",db_path=self.db,
                           chrome_factory=FakeBrowser)
        self.assertEqual(first["state"],"queued")
        self.assertEqual(first["remote_queue_id"],"2577663211")
        second=mod.generate("mossoro","empreiteira",db_path=self.db,
                            chrome_factory=FakeBrowser)
        self.assertTrue(second["reused"])
        self.assertEqual(second["id"],first["id"])
        self.assertEqual(FakeBrowser.submissions,1)

    def test_uncertain_submission_will_not_requeue(self):
        FakeBrowser.fail=True
        with self.assertRaises(RuntimeError):
            mod.generate("mossoro","empreiteira",db_path=self.db,
                         chrome_factory=FakeBrowser)
        FakeBrowser.fail=False
        answer=mod.generate("mossoro","empreiteira",db_path=self.db,
                            chrome_factory=FakeBrowser)
        self.assertTrue(answer["reused"])
        self.assertEqual(answer["state"],"submission_uncertain")
        self.assertEqual(FakeBrowser.submissions,1)

    def test_unconfirmed_job_remains_locked_after_eight_hours(self):
        created,yes=mod.claim_job("natal","empreiteira",self.db,
                                  timestamp=100000,created_by="user-1")
        self.assertTrue(yes)
        previous,again=mod.claim_job("natal","empreiteira",self.db,
                                     timestamp=100000+9*3600,created_by="user-1")
        self.assertEqual(previous,created)
        self.assertFalse(again)
        self.assertEqual(mod.read_job(created,self.db)["state"],"submission_uncertain")
        with mod.connect_db(self.db) as db:
            db.execute("UPDATE query_jobs SET state='failed',error_code='manually_closed_unconfirmed' WHERE id=?",
                       (created,))
        newer,ok=mod.claim_job("natal","empreiteira",self.db,
                               timestamp=100000+9*3600,created_by="user-1")
        self.assertTrue(ok)
        self.assertNotEqual(newer,created)

    def test_invalid_inputs_never_contact_atlas(self):
        for city,location in [("no_city","empreiteira"),("natal","technical"),("","")]:
            with self.assertRaises(ValueError):
                mod.generate(city,location,db_path=self.db,chrome_factory=FakeBrowser)
        self.assertEqual(FakeBrowser.submissions,0)


if __name__=="__main__":
    unittest.main()
