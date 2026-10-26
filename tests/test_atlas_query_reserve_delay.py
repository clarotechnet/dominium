"""The user's two-ID policy is durable and never depends on an open browser UI."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations'/'serial_consult'))
from atlas_query_http import AtlasQueryService
from atlas_query_report import connect_db,read_job
from atlas_query_pipeline import update_job

class Chrome:
    def open(self): pass
    def close(self): pass
    def submit_once(self,city,location): return '276930001'

class ReserveDelayTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.now=1000
        self.svc=AtlasQueryService(db_path=Path(tmp.name)/'test.sqlite3',start_worker=False,
            clock=lambda:self.now,browser_factory=Chrome)
        self.addCleanup(self.svc.close)
    def primary(self):
        job=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'city':'natal','location':'empreiteira'})[1]['job']['id']
        self.svc._submit_existing(job)
        return job
    def test_reserve_is_due_45_seconds_after_id_confirmation_not_request_creation(self):
        job=self.primary()
        self.assertEqual(read_job(job,self.svc.db_path).get('fallback_due_at'),1045)
        self.now=1044.99
        self.assertIsNone(self.svc._ensure_fallback(job))
        self.now=1045
        self.assertIsNotNone(self.svc._ensure_fallback(job))
    def test_timer_runs_for_processing_failed_and_ready_without_waiting_for_404(self):
        for state,error in [('processing',''),('failed','remote_queue_failed'),('ready','')]:
            with self.subTest(state=state):
                job=self.primary()
                update_job(job,self.svc.db_path,state=state,error_code=error)
                self.now+=45
                child=self.svc._ensure_fallback(job)
                self.assertIsNotNone(child)
                self.assertIsNone(self.svc._ensure_fallback(child))
                # Isolate next city's cycle without resetting production policy.
                with connect_db(self.svc.db_path) as db:db.execute('DELETE FROM query_jobs')
    def test_confirmed_remote_failure_anticipates_the_reserve_before_45_seconds(self):
        job=self.primary()
        update_job(job,self.svc.db_path,state='failed',error_code='remote_queue_failed')
        child=self.svc._ensure_fallback(job)
        self.assertIsNotNone(child)
        self.assertIsNone(self.svc._ensure_fallback(job))

    def test_scheduler_observes_confirmed_failure_before_deadline(self):
        job=self.primary()
        update_job(job,self.svc.db_path,state='failed',error_code='remote_queue_failed')
        self.svc._schedule_reserves()
        with connect_db(self.svc.db_path) as db:
            child=db.execute('SELECT remote_queue_id FROM query_jobs WHERE fallback_of=?',(job,)).fetchone()
        self.assertIsNotNone(child)
        self.assertEqual(child['remote_queue_id'],'276930001')

    def test_read_error_or_timeout_does_not_anticipate_reserve(self):
        job=self.primary()
        for error in ['atlas_auth_required','attachment_transport_timeout','process_status_unconfirmed']:
            update_job(job,self.svc.db_path,state='processing',error_code=error)
            self.assertIsNone(self.svc._ensure_fallback(job))

    def test_404_does_not_bypass_45_seconds(self):
        job=self.primary()
        update_job(job,self.svc.db_path,state='attachment_wait',attachment_failures=1,
            error_code='attachment_http_404')
        self.assertIsNone(self.svc._ensure_fallback(job))
    def test_restart_and_concurrent_schedulers_create_only_one_reserve(self):
        job=self.primary();self.now+=45
        def reserve(_):
            svc=AtlasQueryService(db_path=self.svc.db_path,start_worker=False,clock=lambda:self.now)
            try:return svc._ensure_fallback(job)
            finally:svc.close()
        with ThreadPoolExecutor(max_workers=4) as pool:children=list(pool.map(reserve,range(4)))
        self.assertEqual(len([c for c in children if c]),1)
    def test_uncertain_id_does_not_start_timer(self):
        job=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'city':'recife','location':'empreiteira'})[1]['job']['id']
        self.now+=500
        self.assertIsNone(self.svc._ensure_fallback(job))
    def test_due_scheduler_still_submits_reserve_when_primary_is_ready(self):
        job=self.primary();update_job(job,self.svc.db_path,state='ready')
        self.now+=45
        with patch.object(self.svc,'_submit_existing',wraps=self.svc._submit_existing) as send:
            self.svc._schedule_reserves()
        self.assertEqual(send.call_count,1)
        child=read_job(send.call_args.args[0],self.svc.db_path)
        self.assertEqual(child['remote_queue_id'],'276930001')
        self.assertEqual(child['fallback_of'],job)
        self.svc._schedule_reserves()
        with connect_db(self.svc.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM query_jobs').fetchone()[0],2)

class ExplicitCycleTests(ReserveDelayTests):
    def test_ready_report_can_start_one_new_explicit_cycle_without_losing_old_data(self):
        job=self.primary();self.now+=45
        child=self.svc._ensure_fallback(job);self.svc._submit_existing(child)
        update_job(child,self.svc.db_path,state='failed',error_code='remote_queue_failed')
        update_job(job,self.svc.db_path,state='ready')
        from atlas_query_data import store_records
        store_records(job,[{'serial':'EXAMPLE'}],self.svc.db_path)
        body={'city':'natal','location':'empreiteira','refresh_job_id':job}
        result=self.svc.handle('POST','/api/atlas-query/jobs','user-1',body)
        self.assertEqual(result[0],202)
        next_id=result[1]['job']['id']
        self.assertNotEqual(next_id,job)
        again=self.svc.handle('POST','/api/atlas-query/jobs','user-1',body)
        self.assertEqual(again[1]['job']['id'],next_id)
        self.assertEqual(read_job(job,self.svc.db_path)['state'],'ready')
    def test_default_post_cannot_create_third_id_when_primary_failed_before_reserve(self):
        job=self.primary()
        update_job(job,self.svc.db_path,state='failed',error_code='remote_queue_failed')
        response=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'city':'natal','location':'empreiteira'})
        self.assertEqual(response[1]['job']['id'],job)
        self.assertTrue(response[1]['reused'])

    def test_other_operator_cannot_start_pair_while_failed_primary_awaits_reserve(self):
        job=self.primary()
        update_job(job,self.svc.db_path,state='failed',error_code='remote_queue_failed')
        response=self.svc.handle('POST','/api/atlas-query/jobs','user-2',
            {'city':'natal','location':'empreiteira'})
        self.assertEqual(response[0],409)

    def test_audited_reconciliation_of_timed_primary_allows_explicit_replacement(self):
        from atlas_query_report import claim_job
        job=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'city':'natal','location':'empreiteira'})[1]['job']['id']
        with connect_db(self.svc.db_path) as db:
            db.execute("UPDATE query_jobs SET created_at=0,error_code='atlas_submit_unconfirmed' WHERE id=?",(job,))
        closed=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'reconcile_job_id':job,'atlas_checked_no_queue':True})
        self.assertEqual(closed[0],200)
        result=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'city':'natal','location':'empreiteira'})
        self.assertEqual(result[0],202)
        self.assertNotEqual(result[1]['job']['id'],job)

    def test_two_definitive_failures_allow_explicit_recovery(self):
        job=self.primary();self.now+=45
        child=self.svc._ensure_fallback(job);self.svc._submit_existing(child)
        for member in (job,child):
            update_job(member,self.svc.db_path,state='failed',error_code='remote_queue_failed')
        result=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
            {'city':'natal','location':'empreiteira','retry_job_id':job})
        self.assertEqual(result[0],202)


if __name__=='__main__':unittest.main()
