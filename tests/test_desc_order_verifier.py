import datetime as dt
import importlib
import unittest
from pathlib import Path

from imperium_api import Order


class ReadOnlyAPI:
    def __init__(self, orders):
        self.orders = orders
        self.reads = []
        self.details = {}
        self.error = None

    def list_orders(self, date, *, status, service_type):
        self.reads.append(('list_orders', date, status, service_type))
        if self.error:
            raise self.error
        return self.orders

    def order_installer(self, order):
        self.reads.append(('order_installer', order.num_os))
        return self.details.get(order.num_os, {
            'ok': True, 'source': 'imperium_detail', 'id_os': order.id_os,
            'contract': order.contract, 'installer_id': 892,
            'installer_name': 'Técnico de teste',
        })

    def __getattr__(self, name):
        raise AssertionError(f'Unexpected API operation: {name}')


class DescOrderVerifierTests(unittest.TestCase):
    def setUp(self):
        self.api = ReadOnlyAPI([
            Order(11, '123456', '1234567', 7, 'DESC'),
            Order(12, '123457', '1234567', 7, 'DESC'),
            Order(13, '123458', '7654321', 7, 'DESC'),
        ])
        self.factory_calls = []

    def verifier(self):
        self.assertIsNotNone(importlib.util.find_spec('desc_order_verifier'),
                             'Read-only verifier module must exist')
        module = importlib.import_module('desc_order_verifier')

        def factory(root, **kwargs):
            self.factory_calls.append((root, kwargs))
            return self.api

        return module.DescOrderVerifier(Path('/fixture/runtime'), api_factory=factory)

    def test_legacy_runtime_constructor_can_perform_same_read_only_check(self):
        from desc_order_verifier import DescOrderVerifier
        def factory(root, *, port, company, profile_key, controller_id, log_root):
            return self.api
        result = DescOrderVerifier(Path('/fixture/runtime'), api_factory=factory).check(self.payload())
        self.assertTrue(result['confirmed'])

    def payload(self, **overrides):
        return {'profile_key': 'natal', 'contract': '1234567',
                'date': '2026-10-10', 'os_numbers': ['123456'], **overrides}

    def test_reads_only_requested_open_order_and_confirms_detail_identity(self):
        result = self.verifier().check(self.payload())
        self.assertTrue(result['confirmed'])
        self.assertTrue(result['searched'])
        self.assertEqual(result['source'], 'imperium_detail')
        self.assertEqual(result['profile_key'], 'natal')
        self.assertEqual(result['contract'], '1234567')
        self.assertIsNotNone(dt.datetime.fromisoformat(result['checked_at']).tzinfo)
        self.assertEqual(result['orders'], [{
            'num_os': '123456', 'id_os': 11, 'contract': '1234567',
            'installer_id': 892, 'installer_name': 'Técnico de teste',
            'status': 'EM CAMPO', 'service': 'DESC',
        }])
        self.assertEqual(self.api.reads, [
            ('list_orders', dt.date(2026, 10, 10), 'field', 'all'),
            ('order_installer', '123456'),
        ])
        root, options = self.factory_calls[0]
        self.assertEqual(root, Path('/fixture/runtime'))
        self.assertEqual(options['port'], 212)
        self.assertEqual(options['company'], 'NATAL / PARNAMIRIM')
        self.assertEqual(options['controller_id'], 362032)
        self.assertEqual(options['expected_username'], 'DOMINIUM')

    def test_all_profiles_use_same_runtime_identity_as_app(self):
        for profile, port, controller in [('natal', 212, 362032),
                                          ('fortaleza', 596, 90321),
                                          ('mossoro', 579, 22722),
                                          ('recife', 599, 15787)]:
            with self.subTest(profile=profile):
                self.verifier().check(self.payload(profile_key=profile))
                self.assertEqual(self.factory_calls[-1][1]['port'], port)
                self.assertEqual(self.factory_calls[-1][1]['controller_id'], controller)
                self.assertEqual(self.factory_calls[-1][1]['profile_key'], profile)

    def test_multiple_requested_orders_preserve_request_order(self):
        result = self.verifier().check(self.payload(os_numbers=['123457', '123456']))
        self.assertEqual([item['num_os'] for item in result['orders']], ['123457', '123456'])

    def test_empty_requested_list_searches_all_contract_candidates(self):
        result = self.verifier().check(self.payload(os_numbers=[]))
        self.assertEqual([item['num_os'] for item in result['orders']], ['123456', '123457'])
        self.assertTrue(result['searched'])
        self.assertEqual(self.api.reads[-2:], [('order_installer', '123456'),
                                             ('order_installer', '123457')])

    def test_empty_list_with_no_candidates_is_completed_search_not_installer_confirmation(self):
        result = self.verifier().check(self.payload(contract='1111111', os_numbers=[]))
        self.assertTrue(result['searched'])
        self.assertTrue(result['confirmed'])
        self.assertEqual(result['source'], 'open_orders_no_match')
        self.assertEqual(result['orders'], [])

    def test_missing_requested_order_fails_without_confirming_other_orders(self):
        with self.assertRaises(ValueError):
            self.verifier().check(self.payload(os_numbers=['123456', '999999']))
        self.assertEqual(len(self.api.reads), 1)

    def test_other_contract_is_not_confirmed(self):
        with self.assertRaises(ValueError):
            self.verifier().check(self.payload(os_numbers=['123458']))
        self.assertEqual(len(self.api.reads), 1)

    def test_ambiguous_number_is_not_confirmed(self):
        self.api.orders.append(Order(14, '123456', '1234567', 7, 'DESC'))
        with self.assertRaises(ValueError):
            self.verifier().check(self.payload())
        self.assertEqual(len(self.api.reads), 1)

    def test_wrong_open_status_is_not_confirmed(self):
        self.api.orders[0] = Order(11, '123456', '1234567', 7, 'DESC', 'FECHADA')
        with self.assertRaises(ValueError):
            self.verifier().check(self.payload())

    def test_details_must_confirm_identity_source_and_installer(self):
        for override in [{'ok': False}, {'id_os': 12}, {'contract': '7654321'},
                         {'source': 'toa'}, {'installer_id': 0},
                         {'installer_id': True}, {'installer_id': '892'}]:
            with self.subTest(override=override):
                self.api.details['123456'] = {
                    'ok': True, 'source': 'imperium_detail', 'id_os': 11,
                    'contract': '1234567', 'installer_id': 892,
                    'installer_name': 'Técnico de teste', **override,
                }
                with self.assertRaises(ValueError):
                    self.verifier().check(self.payload())

    def test_invalid_schema_is_rejected_before_api_construction(self):
        invalid = [self.payload(profile_key='invalid'), self.payload(contract='123'),
                   self.payload(contract=1234567), self.payload(contract='１２３４５６７'),
                   self.payload(date='2026-02-30'), self.payload(date='20261010'),
                   self.payload(date='2026-10-10T12:00:00Z'), self.payload(os_numbers='123456'),
                   self.payload(os_numbers=['123456', '123456']),
                   self.payload(os_numbers=['１２３']), self.payload(os_numbers=[123456]),
                   self.payload(os_numbers=['12345678901']), self.payload(os_numbers=['']),
                   self.payload(os_numbers=[str(item) for item in range(11)]),
                   self.payload(actor='forged'), [], None]
        verifier = self.verifier()
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                verifier.check(payload)
        self.assertEqual(self.factory_calls, [])

    def test_missing_date_defaults_to_today(self):
        payload = self.payload()
        del payload['date']
        self.verifier().check(payload)
        self.assertEqual(self.api.reads[0][1], dt.date.today())

    def test_backend_failure_is_sanitized_without_assumed_success(self):
        self.api.error = OSError('credential=private-fixture-secret')
        with self.assertRaises(ValueError) as error:
            self.verifier().check(self.payload())
        self.assertNotIn('private-fixture-secret', str(error.exception))
        self.assertEqual(error.exception.code, 'imperium_unavailable')

    def test_backend_connection_is_reused_per_profile(self):
        verifier = self.verifier()
        verifier.check(self.payload())
        verifier.check(self.payload(os_numbers=['123457']))
        self.assertEqual(len(self.factory_calls), 1)


if __name__ == '__main__':
    unittest.main()
