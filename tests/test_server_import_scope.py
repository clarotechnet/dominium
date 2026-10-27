import datetime as dt
import unittest
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy/server-import-all'))

from toa_import_scope import IMPORT_ALLOWED_ROUTES, filter_import_preview, validate_import_route


@dataclass(frozen=True)
class Order:
    os_number: str = '1234567890'
    contract: str = '9876543'
    import_date: str = '27/10/2026'
    city: str = 'NATAL'
    os_type: str = 'Adesao Ponto Virtua'


@dataclass(frozen=True)
class Preview:
    orders: tuple = ()
    scope_exclusions: tuple = ()


class ImportScopeTests(unittest.TestCase):
    def test_all_thirteen_buckets_are_supported(self):
        self.assertEqual(len(IMPORT_ALLOWED_ROUTES), 13)
        for route in ('NTL-DMV', 'NTL-DMV_VT', 'FTZ-DMV_01_VT', 'PWM-DMV', 'MRO-DMV'):
            validate_import_route(route, dt.date.today().isoformat())

    def test_unknown_route_and_wrong_day_are_blocked(self):
        for route, day in [('OTHER-DMV', dt.date.today().isoformat()),
                           ('NTL-DMV', '2020-01-01'), ('NTL-DMV_EXTRA', dt.date.today().isoformat())]:
            with self.assertRaises(ValueError):
                validate_import_route(route, day)

    def test_adhesion_is_retained(self):
        result = filter_import_preview(Preview((Order(),)), route='NTL-DMV', import_day=dt.date(2026, 10, 27))
        self.assertEqual(result.orders, (Order(),))

    def test_invalid_date_identity_and_duplicates_are_excluded(self):
        rows = (Order(), Order(), Order(os_number='1111', import_date='26/10/2026'), Order(os_number='bad'))
        result = filter_import_preview(Preview(rows, ({'reason': 'city_scope_mismatch'},)), route='NTL-DMV', import_day=dt.date(2026, 10, 27))
        self.assertFalse(result.orders)
        self.assertEqual(len(result.scope_exclusions), 5)

    def test_existing_desc_scope_still_rejects_adhesion(self):
        source = Path('/workspace/scratch/940fb3ab71f6/import_all_source')
        if not (source / 'desc_only_scope.py').exists():
            self.skipTest('Requires the private server DESC policy snapshot')
        sys.path.insert(0, str(source))
        from desc_only_scope import filter_desc_preview, DESC_ALLOWED_ROUTES
        result = filter_desc_preview(Preview((Order(),)), route='NTL-DMV_ADM', import_day=dt.date(2026, 10, 27))
        self.assertFalse(result.orders)
        self.assertNotIn('NTL-DMV', DESC_ALLOWED_ROUTES)


if __name__ == '__main__':
    unittest.main()
