import importlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from toa_pool_monitor_proxy import (
  TOAPoolMonitorError,_origin,read_monitor,sanitize_status
)

class ProxyTests(unittest.TestCase):
 def test_only_local_http_or_https(self):
  for wrong in ['http://192.168.0.2:8792','http://pool.example',
    'file:///etc/passwd','https://user:pass@example.com','https://example.com/some/path',
    'https://example.com?token=test','']:
   with self.subTest(origin=wrong), self.assertRaises(TOAPoolMonitorError):
    _origin(wrong)
  self.assertEqual(_origin('http://127.0.0.1:8792'),'http://127.0.0.1:8792')
  self.assertEqual(_origin('https://pool.example/'),'https://pool.example')
 def test_strips_sensitive_payload_and_unknown_properties(self):
  source={'ok':True,'data':{
   'agents':[{'id':'pc-1','online':True,'busy':False,'buckets':['MRO-DMV','MRO-DMV','NTL-DMV_ADM'],
      'queries':12,'requests_recent':4,'token':'DO_NOT_LEAK',
      'cookie':'DO_NOT_LEAK','contract':'1234567','snapshot':{'phone':'5555555'},'last_seen':123}],
   'queue_by_bucket':{'MRO-DMV':{'queued':10,'in_progress':2,'contract':'SECRET'},
      '../bad':{'queued':4}},
   'dispatch_blocked':True,'leases_today':11,'max_leases_per_day':30,
   'enrollments_pending':3,'db_file':'C:/do/not/reveal',
  }}
  result=sanitize_status(source)
  dumped=json.dumps(result)
  self.assertNotIn('DO_NOT_LEAK',dumped)
  self.assertNotIn('5555555',dumped)
  self.assertNotIn('1234567',dumped)
  self.assertNotIn('db_file',dumped)
  self.assertNotIn('../bad',dumped)
  self.assertEqual(result['agents'][0]['buckets'],['MRO-DMV','NTL-DMV_ADM'])
  self.assertEqual(result['queue_by_bucket']['MRO-DMV'],{'queued':10,'in_progress':2})
 def test_local_proxy_sends_admin_secret_only_to_coordinator(self):
  observed={}
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return json.dumps({'ok':True,'data':{'agents':[],
          'leases_today':0,'max_leases_per_day':0}}).encode()
  def mock_urlopen(req,timeout):
   observed['url']=req.full_url
   observed['authorization']=req.get_header('Authorization')
   observed['timeout']=timeout
   return Response()
  with patch('toa_pool_monitor_proxy.urlopen',side_effect=mock_urlopen):
   result=read_monitor(origin='http://127.0.0.1:8792',token='supersecret-token-sample-12345')
  self.assertEqual(observed['url'],'http://127.0.0.1:8792/admin/status')
  self.assertEqual(observed['authorization'],'Bearer supersecret-token-sample-12345')
  self.assertEqual(result['agents'],[])
  self.assertNotIn('token',json.dumps(result))
 def test_missing_configuration_fails_closed(self):
  with self.assertRaises(TOAPoolMonitorError):
   read_monitor(origin='',token='')
  with self.assertRaises(TOAPoolMonitorError):
   read_monitor(origin='https://pool.example',token='')
 def test_proxy_never_leaks_exception_details(self):
  with patch('toa_pool_monitor_proxy.urlopen',side_effect=RuntimeError('secret-token-leaked')):
   with self.assertRaises(TOAPoolMonitorError) as e:
    read_monitor(origin='https://pool.example',token='supersecret-token-sample-12345')
  self.assertNotIn('secret',str(e.exception))
 def test_api_route_requires_dominium_admin_role(self):
  app=(ROOT/'app.py').read_text(encoding='utf8')
  self.assertIn('or path.startswith("/api/toa-pool/")',app)
  self.assertIn('if admin_path and user.get("role") != "admin":',app)
  self.assertIn('if parsed.path == "/api/toa-pool/monitor":',app)
  self.assertIn('self._json(HTTPStatus.OK, read_monitor())',app)
if __name__=='__main__':
 unittest.main()


class EnrollmentProxyTests(unittest.TestCase):
 def test_admin_enrollments_return_ids_without_secrets(self):
  from toa_pool_monitor_proxy import read_enrollments
  with patch('toa_pool_monitor_proxy._call_admin',return_value=[
    {'id':'ctl-'+'a'*24,'created':1000,'last_seen':2000,'token_hash':'secret'},
    {'id':'bad-id','token':'secret'},
  ]) as mock:
   result=read_enrollments()
  mock.assert_called_once_with('/admin/enrollments')
  self.assertEqual(result['pending'],[{'id':'ctl-'+'a'*24}])
  self.assertNotIn('secret',json.dumps(result))
 def test_review_posts_validated_agent_id_only(self):
  from toa_pool_monitor_proxy import review_enrollment
  identifier='ctl-'+'b'*24
  for approve,state,url_action in [(True,'approved','approve'),(False,'denied','deny')]:
   with patch('toa_pool_monitor_proxy._call_admin',return_value={
      'id':identifier,'state':state,'token':'SHOULD_NOT_RETURN'
    }) as mock:
    result=review_enrollment(identifier,approve)
   self.assertEqual(result,{'ok':True,'id':identifier,'state':state})
   mock.assert_called_once_with('/admin/enrollments/'+identifier+'/'+url_action,method='POST')
  with self.assertRaises(TOAPoolMonitorError):review_enrollment('../other',True)
 def test_admin_review_route_requires_csrf_and_admin(self):
  app=(ROOT/'app.py').read_text(encoding='utf8')
  self.assertIn('match_controller_review = re.fullmatch(',app)
  self.assertIn('self._security_preflight("POST", parsed.path)',app)
  self.assertIn('AUTH_STORE.validate_csrf(session, supplied_csrf)',app)
  self.assertIn('if admin_path and user.get("role") != "admin"',app)
