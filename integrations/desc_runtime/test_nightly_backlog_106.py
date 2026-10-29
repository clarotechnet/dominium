import contextlib
import copy
import datetime as dt
import io
import tempfile
import unittest
from urllib.parse import urlparse, parse_qs
from urllib.error import HTTPError
import nightly_backlog_106 as batch

DAY = '2026-09-08'
NOW = dt.datetime(2026, 9, 8, 23, 0, tzinfo=batch.BRAZIL)


class API:
    def __init__(self, fail=False, removed=False):
        self.posts = []
        self.fail = fail
        self.removed = removed

    def row(self, profile):
        return dict(id_os=123, num_os='456', contract='1234567', id_service=3,
                    service='DESCONEXAO', status='EM CAMPO', operation_source='imperium_cache',
                    approved_state_hash='abc', manual_scope=dict(profile_key=profile, cache_date=DAY, state_hash='abc'))

    def __call__(self, path, payload=None):
        if path == '/api/profiles':
            return {'ok': True, 'profiles': [dict(key=p, close_enabled=True, project={'project_id': 'IMPERIUM_OLLAMA'}) for p in batch.PROFILES]}
        q = parse_qs(urlparse(path).query)
        profile = q['profile'][0]
        if payload is not None:
            self.posts.append((profile, payload))
            if self.fail:
                raise TimeoutError('uncertain')
            return dict(ok=True, code='106', id_os=123, num_os='456')
        service = q['service_type'][0]
        return dict(date=DAY, status_filter='field', service_type_filter=service,
                    orders=[] if self.removed and service == 'all' else [self.row(profile)])


class Tests(unittest.TestCase):
    def test_busy_read_retries_but_never_repeats_post(self):
        api = API()
        reads = []
        pauses = []
        def busy_once(path, payload=None):
            if payload is None and 'service_type=disconnection' in path:
                reads.append(path)
                if len(reads) == 1:
                    raise HTTPError(path,409,'Busy',{},None)
            return api(path,payload)
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            report = batch.run(True,api=busy_once,clock=lambda:NOW,pause=pauses.append,state_dir=folder)
        self.assertEqual(len(api.posts),4)
        self.assertEqual(sum(v['confirmed'] for v in report['profiles'].values()),4)
        self.assertIn(15,pauses)

    def invoke(self, api, folder, execute=True, clock=lambda: NOW):
        with contextlib.redirect_stdout(io.StringIO()):
            return batch.run(execute, api=api, clock=clock, pause=lambda _: None, state_dir=folder)

    def test_window_never_backfills(self):
        self.assertTrue(batch.execution_window(DAY, NOW))
        self.assertFalse(batch.execution_window(DAY, NOW.replace(hour=22)))
        self.assertFalse(batch.execution_window(DAY, NOW.replace(day=9)))
        with tempfile.TemporaryDirectory() as folder:
            api = API()
            with self.assertRaises(ValueError):
                self.invoke(api, folder, clock=lambda: NOW.replace(hour=16))
            self.assertEqual(api.posts, [])

    def test_preview_has_no_posts(self):
        with tempfile.TemporaryDirectory() as folder:
            api = API()
            report = self.invoke(api, folder, execute=False)
            self.assertEqual(api.posts, [])
            self.assertEqual(sum(x['eligible'] for x in report['profiles'].values()), 4)

    def test_all_profiles_datasnap_empty_observation_and_idempotency(self):
        with tempfile.TemporaryDirectory() as folder:
            api = API()
            self.invoke(api, folder)
            self.invoke(api, folder)
            self.assertEqual(len(api.posts), 4)
            for _, payload in api.posts:
                self.assertEqual(payload['transport'], 'datasnap')
                self.assertEqual(payload['code'], '106')
                self.assertEqual(payload['observation'], '')
                self.assertNotIn('materials', payload)

    def test_uncertain_write_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            api = API(fail=True)
            report = self.invoke(api, folder)
            self.invoke(api, folder)
            self.assertEqual(len(api.posts), 4)
            self.assertTrue(all(x['errors'] for x in report['profiles'].values()))

    def test_closed_during_batch_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            api = API(removed=True)
            self.invoke(api, folder)
            self.assertEqual(api.posts, [])

    def test_scope_status_and_identity_guards(self):
        expected = API().row('natal')
        for change in [{'status': 'CONCLUIDA'}, {'contract': '7654321'}, {'operation_blockers': ['stale_snapshot']},
                       {'manual_scope': {'profile_key': 'recife', 'cache_date': DAY, 'state_hash': 'abc'}},
                       {'manual_scope': {'profile_key': 'natal', 'cache_date': '2026-09-07', 'state_hash': 'abc'}}]:
            row = copy.deepcopy(expected)
            row.update(change)
            with self.assertRaises(ValueError):
                batch.close_payload(row, expected, 'natal', DAY)


if __name__ == '__main__':
    unittest.main()
