"""QUERY Atlas authenticated API contract without contacting real Atlas."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations'/'serial_consult'))
from atlas_query_http import parse_query_route,AtlasQueryService
from atlas_query_pipeline import update_job
from atlas_query_data import store_records


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc=AtlasQueryService(db_path=Path(self.tmp.name)/'state.sqlite3',start_worker=False)
        self.addCleanup(self.svc.close)
    def test_route_policy_does_not_allow_query_or_mutations(self):
        identifier='a'*32
        self.assertEqual(parse_query_route('GET','/api/atlas-query/jobs/'+identifier+'/rows/100'),
                         ('rows',identifier,100))
        self.assertEqual(parse_query_route('GET','/api/atlas-query/jobs/'+identifier+'/export.xlsx'),
                         ('export',identifier,'xlsx'))
        for method,url in [
            ('GET','/api/atlas-query/jobs?user=other'),
            ('POST','/api/atlas-query/jobs/'+identifier+'/export.xlsx'),
            ('GET','/api/atlas-query/jobs/'+identifier+'/../../.env'),
            ('GET','/api/atlas-query/jobs/'+identifier+'/rows/-1'),
        ]:
            self.assertIsNone(parse_query_route(method,url))

    def test_create_is_idempotent_and_actor_isolated(self):
        body={'city':'mossoro','location':'empreiteira'}
        first=self.svc.handle('POST','/api/atlas-query/jobs','user-1',body)
        again=self.svc.handle('POST','/api/atlas-query/jobs','user-1',body)
        self.assertEqual(first[0],202)
        self.assertEqual(again[0],200)
        self.assertEqual(first[1]['job']['id'],again[1]['job']['id'])
        job_id=first[1]['job']['id']
        self.assertEqual(self.svc.handle('GET','/api/atlas-query/jobs/'+job_id,'user-2')[0],404)
        self.assertEqual(self.svc.handle('POST','/api/atlas-query/jobs','viewer',body)[0],403)

    def test_confirmed_404_spawns_exactly_one_backup_for_all_cities(self):
        from atlas_query_report import read_job,save_queue
        for city in ('natal','mossoro','fortaleza','recife'):
            with self.subTest(city=city):
                created=self.svc.handle('POST','/api/atlas-query/jobs','user-77',
                    {'city':city,'location':'empreiteira'})
                self.assertEqual(created[0],202)
                primary=created[1]['job']['id']
                self.assertEqual(read_job(primary,self.svc.db_path)['fallback_enabled'],1)
                self.assertIsNone(self.svc._ensure_fallback(primary))
                save_queue(primary,'276855582',self.svc.db_path)
                self.assertIsNone(self.svc._ensure_fallback(primary))
                update_job(primary,self.svc.db_path,state='attachment_wait',
                    attachment_failures=1,error_code='attachment_http_404')
                reserve=self.svc._ensure_fallback(primary)
                self.assertRegex(reserve,r'^[a-f0-9]{32}
        from atlas_query_report import AtlasAuthRequired, claim_job, read_job
        class LoginRequiredChrome:
            submissions=0
            def open(self):
                raise AtlasAuthRequired("Atlas login required")
            def submit_once(self,*args,**kwargs):
                LoginRequiredChrome.submissions+=1
            def close(self):pass
        job,_=claim_job('mossoro','empreiteira',self.svc.db_path,
                        created_by='user-123')
        self.svc.browser_factory=LoginRequiredChrome
        self.svc._submit_existing(job)
        updated=read_job(job,self.svc.db_path)
        self.assertEqual(updated['state'],'atlas_auth_required')
        self.assertEqual(updated['error_code'],'atlas_auth_required')
        self.assertIsNone(updated['remote_queue_id'])
        self.assertEqual(LoginRequiredChrome.submissions,0)

    def test_stale_submission_marks_error_without_another_atlas_post(self):
        import time
        from atlas_query_report import claim_job,read_job,connect_db
        job_id,_=claim_job('natal','empreiteira',self.svc.db_path,created_by='user-333')
        with connect_db(self.svc.db_path) as db:
            db.execute("UPDATE query_jobs SET created_at=? WHERE id=?",
                       (time.time()-400,job_id))
        svc2=AtlasQueryService(db_path=self.svc.db_path,start_worker=False)
        self.addCleanup(svc2.close)
        saved=read_job(job_id,self.svc.db_path)
        self.assertEqual(saved['state'],'submission_uncertain')
        self.assertEqual(saved['error_code'],'atlas_submit_unconfirmed')
        self.assertIsNone(saved['remote_queue_id'])
        status,payload,_=svc2.handle('GET','/api/atlas-query/jobs/'+job_id,'user-333')
        self.assertEqual(status,200)
        self.assertEqual(payload['job']['error_code'],'atlas_submit_unconfirmed')
        self.assertEqual(len(svc2._new_jobs),0)

    def test_expired_nettask_session_preserves_remote_id_without_retrying_post(self):
        import time
        from unittest.mock import patch
        from atlas_query_report import AtlasAuthRequired,save_queue,read_job
        created=self.svc.handle('POST','/api/atlas-query/jobs','user-17',
            {'city':'mossoro','location':'empreiteira'})
        job_id=created[1]['job']['id']
        save_queue(job_id,'276850938',self.svc.db_path)
        with patch('atlas_query_http.poll_report',side_effect=AtlasAuthRequired('session expired')) as lookup:
            worker=AtlasQueryService(db_path=self.svc.db_path,start_worker=True)
            try:
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    if read_job(job_id,self.svc.db_path)['error_code']=='atlas_auth_required':break
                    time.sleep(.03)
                saved=read_job(job_id,self.svc.db_path)
                self.assertEqual(saved['state'],'queued')
                self.assertEqual(saved['error_code'],'atlas_auth_required')
                self.assertEqual(saved['remote_queue_id'],'276850938')
                time.sleep(.15)
                self.assertEqual(lookup.call_count,1)
            finally:worker.close()

    def test_ready_report_can_page_and_export_only_to_owner(self):
        job=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
                            {'city':'natal','location':'empreiteira'})[1]['job']['id']
        store_records(job,[{'numero_serie':'000123456789',
                            'codigo_material_sap':'00001111',
                            'codigo_sap_normalizado':'1111'}],self.svc.db_path)
        update_job(job,self.svc.db_path,state='ready')
        endpoint='/api/atlas-query/jobs/'+job
        self.assertEqual(self.svc.handle('GET',endpoint+'/rows/0','user-1')[1]['total'],1)
        for extension in ('csv','xlsx'):
            status,payload,mime=self.svc.handle('GET',endpoint+'/export.'+extension,'user-1')
            self.assertEqual(status,200)
            self.assertIsInstance(payload,bytes)
            self.assertTrue(mime)
        self.assertEqual(self.svc.handle('GET',endpoint+'/rows/0','user-2')[0],404)
        self.assertEqual(self.svc.handle('GET',endpoint+'/export.csv','user-2')[0],404)

if __name__=='__main__':unittest.main()
)
                self.assertNotEqual(reserve,primary)
                self.assertIsNone(self.svc._ensure_fallback(primary))
                child=read_job(reserve,self.svc.db_path)
                self.assertEqual(child['fallback_of'],primary)
                self.assertEqual(child['fallback_enabled'],0)
                self.assertEqual(child['state'],'submission_uncertain')
                self.assertIsNone(child['remote_queue_id'])
                self.assertEqual(child['created_by'],'user-77')
                save_queue(reserve,'276855583',self.svc.db_path)
                self.assertEqual(read_job(reserve,self.svc.db_path)['remote_queue_id'],'276855583')
                self.assertEqual(read_job(primary,self.svc.db_path)['remote_queue_id'],'276855582')
                self.assertIsNone(self.svc._ensure_fallback(reserve))
                status,info,_=self.svc.handle('GET','/api/atlas-query/jobs','user-77')
                self.assertEqual(status,200)
                self.assertTrue(any(x['id']==reserve and x['fallback_of']==primary for x in info['jobs']))

    def test_historical_404_does_not_automatically_generate_backup(self):
        from atlas_query_report import claim_job,save_queue,read_job
        primary,_=claim_job('recife','empreiteira',self.svc.db_path,created_by='user-78')
        save_queue(primary,'276855585',self.svc.db_path)
        update_job(primary,self.svc.db_path,state='attachment_wait',attachment_failures=11,
                   error_code='attachment_http_404')
        self.assertEqual(read_job(primary,self.svc.db_path)['fallback_enabled'],0)
        self.assertIsNone(self.svc._ensure_fallback(primary))

    def test_uncertain_or_ready_primary_cannot_generate_backup(self):
        from atlas_query_report import read_job,save_queue
        primary=self.svc.handle('POST','/api/atlas-query/jobs','user-82',
            {'city':'mossoro','location':'empreiteira'})[1]['job']['id']
        update_job(primary,self.svc.db_path,error_code='atlas_submit_unconfirmed')
        self.assertIsNone(self.svc._ensure_fallback(primary))
        save_queue(primary,'276855586',self.svc.db_path)
        update_job(primary,self.svc.db_path,state='ready',error_code='')
        self.assertIsNone(self.svc._ensure_fallback(primary))

    def test_fallback_singleton_with_concurrent_threads(self):
        from concurrent.futures import ThreadPoolExecutor
        from atlas_query_report import save_queue,connect_db
        primary=self.svc.handle('POST','/api/atlas-query/jobs','user-83',
            {'city':'fortaleza','location':'empreiteira'})[1]['job']['id']
        save_queue(primary,'276855587',self.svc.db_path)
        update_job(primary,self.svc.db_path,state='attachment_wait',
                   attachment_failures=4,error_code='attachment_http_404')
        with ThreadPoolExecutor(max_workers=5) as pool:
            created=list(pool.map(self.svc._ensure_fallback,[primary]*5))
        self.assertEqual(len([x for x in created if x]),1)
        with connect_db(self.svc.db_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM query_jobs WHERE fallback_of=?',
                                        (primary,)).fetchone()[0],1)

    def test_auth_required_records_failure_without_submitting_report(self):
        from atlas_query_report import AtlasAuthRequired, claim_job, read_job
        class LoginRequiredChrome:
            submissions=0
            def open(self):
                raise AtlasAuthRequired("Atlas login required")
            def submit_once(self,*args,**kwargs):
                LoginRequiredChrome.submissions+=1
            def close(self):pass
        job,_=claim_job('mossoro','empreiteira',self.svc.db_path,
                        created_by='user-123')
        self.svc.browser_factory=LoginRequiredChrome
        self.svc._submit_existing(job)
        updated=read_job(job,self.svc.db_path)
        self.assertEqual(updated['state'],'atlas_auth_required')
        self.assertEqual(updated['error_code'],'atlas_auth_required')
        self.assertIsNone(updated['remote_queue_id'])
        self.assertEqual(LoginRequiredChrome.submissions,0)

    def test_stale_submission_marks_error_without_another_atlas_post(self):
        import time
        from atlas_query_report import claim_job,read_job,connect_db
        job_id,_=claim_job('natal','empreiteira',self.svc.db_path,created_by='user-333')
        with connect_db(self.svc.db_path) as db:
            db.execute("UPDATE query_jobs SET created_at=? WHERE id=?",
                       (time.time()-400,job_id))
        svc2=AtlasQueryService(db_path=self.svc.db_path,start_worker=False)
        self.addCleanup(svc2.close)
        saved=read_job(job_id,self.svc.db_path)
        self.assertEqual(saved['state'],'submission_uncertain')
        self.assertEqual(saved['error_code'],'atlas_submit_unconfirmed')
        self.assertIsNone(saved['remote_queue_id'])
        status,payload,_=svc2.handle('GET','/api/atlas-query/jobs/'+job_id,'user-333')
        self.assertEqual(status,200)
        self.assertEqual(payload['job']['error_code'],'atlas_submit_unconfirmed')
        self.assertEqual(len(svc2._new_jobs),0)

    def test_expired_nettask_session_preserves_remote_id_without_retrying_post(self):
        import time
        from unittest.mock import patch
        from atlas_query_report import AtlasAuthRequired,save_queue,read_job
        created=self.svc.handle('POST','/api/atlas-query/jobs','user-17',
            {'city':'mossoro','location':'empreiteira'})
        job_id=created[1]['job']['id']
        save_queue(job_id,'276850938',self.svc.db_path)
        with patch('atlas_query_http.poll_report',side_effect=AtlasAuthRequired('session expired')) as lookup:
            worker=AtlasQueryService(db_path=self.svc.db_path,start_worker=True)
            try:
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    if read_job(job_id,self.svc.db_path)['error_code']=='atlas_auth_required':break
                    time.sleep(.03)
                saved=read_job(job_id,self.svc.db_path)
                self.assertEqual(saved['state'],'queued')
                self.assertEqual(saved['error_code'],'atlas_auth_required')
                self.assertEqual(saved['remote_queue_id'],'276850938')
                time.sleep(.15)
                self.assertEqual(lookup.call_count,1)
            finally:worker.close()

    def test_ready_report_can_page_and_export_only_to_owner(self):
        job=self.svc.handle('POST','/api/atlas-query/jobs','user-1',
                            {'city':'natal','location':'empreiteira'})[1]['job']['id']
        store_records(job,[{'numero_serie':'000123456789',
                            'codigo_material_sap':'00001111',
                            'codigo_sap_normalizado':'1111'}],self.svc.db_path)
        update_job(job,self.svc.db_path,state='ready')
        endpoint='/api/atlas-query/jobs/'+job
        self.assertEqual(self.svc.handle('GET',endpoint+'/rows/0','user-1')[1]['total'],1)
        for extension in ('csv','xlsx'):
            status,payload,mime=self.svc.handle('GET',endpoint+'/export.'+extension,'user-1')
            self.assertEqual(status,200)
            self.assertIsInstance(payload,bytes)
            self.assertTrue(mime)
        self.assertEqual(self.svc.handle('GET',endpoint+'/rows/0','user-2')[0],404)
        self.assertEqual(self.svc.handle('GET',endpoint+'/export.csv','user-2')[0],404)

if __name__=='__main__':unittest.main()
