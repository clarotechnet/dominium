"""Same-day import scope, independent from disconnection write-off rules."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import replace

IMPORT_ALLOWED_ROUTES = frozenset({
    'NTL-DMV', 'NTL-DMV_ADM', 'NTL-DMV_VT',
    'PWM-DMV', 'PWM-DMV_ADM', 'PWM-DMV_VT',
    'FTZ-DMV_01', 'FTZ-DMV_01_VT', 'FTZ-DMV_ADM',
    'JCR-DMV', 'JCR-DMV_ADM', 'JCR-DMV_VT', 'MRO-DMV',
})


def validate_import_route(route: str, day: str) -> None:
    if route not in IMPORT_ALLOWED_ROUTES or day != dt.date.today().isoformat():
        raise ValueError('import_route_or_date_scope_mismatch')


def filter_import_preview(preview, *, route: str, import_day: dt.date | None = None):
    if route not in IMPORT_ALLOWED_ROUTES:
        raise ValueError('import_route_scope_mismatch')
    today = import_day or dt.date.today()
    candidates, blocked = [], []
    for order in preview.orders:
        try:
            valid_date = dt.datetime.strptime(order.import_date, '%d/%m/%Y').date() == today
        except (AttributeError, ValueError, TypeError):
            valid_date = False
        reason = ''
        if not valid_date:
            reason = 'date_scope_mismatch'
        elif not str(order.os_number).strip().isdigit() or not str(order.contract).strip().isdigit():
            reason = 'invalid_order_identity'
        if reason:
            blocked.append({'os_number': order.os_number, 'contract': order.contract,
                            'city': order.city, 'service': order.os_type, 'reason': reason})
        else:
            candidates.append(order)
    counts = Counter(str(order.os_number).strip() for order in candidates)
    safe = []
    for order in candidates:
        if counts[str(order.os_number).strip()] > 1:
            blocked.append({'os_number': order.os_number, 'contract': order.contract,
                            'city': order.city, 'service': order.os_type,
                            'reason': 'duplicate_os_identity'})
        else:
            safe.append(order)
    return replace(preview, orders=tuple(safe),
                   scope_exclusions=tuple(preview.scope_exclusions) + tuple(blocked))
