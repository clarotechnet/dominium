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
