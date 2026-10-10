"""Fail-closed, read-only Imperium order/installer checks for the DESC relay.

The caller compares the returned installer IDs with its WhatsApp technician
directory. This module never reads TOA identities or executes order operations.
"""
from __future__ import annotations

import datetime as dt
import inspect
import re
import threading
from pathlib import Path

from imperium_api import ImperiumAPI, STATUS


DEFAULT_RUNTIME_ROOT = Path(r'C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA')
# Mirrors app.PROFILE_SPECS without importing the application and its workers.
PROFILE_SPECS = {
    'natal': ('NATAL / PARNAMIRIM', 212, 362032),
    'fortaleza': ('FORTALEZA', 596, 90321),
    'mossoro': ('MOSSORÓ', 579, 22722),
    'recife': ('RECIFE', 599, 15787),
}


class OrderCheckError(ValueError):
    code = 'imperium_unconfirmed'
    status = 409


class OrderCheckUnavailableError(OrderCheckError):
    code = 'imperium_unavailable'
    status = 503


def validate_order_check(payload: dict) -> tuple[str, str, dt.date, list[str]]:
    """Validate the internal JSON schema before opening any Imperium session."""
    required = {'profile_key', 'contract', 'os_numbers'}
    if not isinstance(payload, dict) or not required <= payload.keys() or payload.keys() - required - {'date'}:
        raise ValueError('Consulta de OS inválida')
    profile = payload['profile_key']
    contract = payload['contract']
    numbers = payload['os_numbers']
    date_text = payload.get('date', dt.date.today().isoformat())
    if not isinstance(profile, str) or profile not in PROFILE_SPECS:
        raise ValueError('Perfil Imperium inválido')
    if not isinstance(contract, str) or not re.fullmatch(r'[0-9]{7}', contract):
        raise ValueError('Contrato inválido')
    if not isinstance(date_text, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', date_text):
        raise ValueError('Data de consulta inválida')
    try:
        date = dt.date.fromisoformat(date_text)
    except ValueError as error:
        raise ValueError('Data de consulta inválida') from error
    if not isinstance(numbers, list) or len(numbers) > 10:
        raise ValueError('Lista de OS inválida')
    if any(not isinstance(number, str) or not re.fullmatch(r'[0-9]{1,10}', number) for number in numbers):
        raise ValueError('Número de OS inválido')
    if len(set(numbers)) != len(numbers):
        raise ValueError('Lista de OS ambígua')
    return profile, contract, date, numbers


class DescOrderVerifier:
    def __init__(self, runtime_root: Path = DEFAULT_RUNTIME_ROOT, *, api_factory=ImperiumAPI):
        self.runtime_root = Path(runtime_root)
        self._api_factory = api_factory
        self._apis = {}
        self._locks = {key: threading.Lock() for key in PROFILE_SPECS}

    def _api(self, profile: str):
        if profile not in self._apis:
            company, port, controller_id = PROFILE_SPECS[profile]
            log_root = self.runtime_root / 'logs'
            if profile != 'natal':
                log_root /= profile
            options = dict(port=port, company=company, profile_key=profile,
                           controller_id=controller_id, log_root=log_root)
            parameters = inspect.signature(self._api_factory).parameters
            if 'expected_username' in parameters or any(
                    value.kind == inspect.Parameter.VAR_KEYWORD for value in parameters.values()):
                options['expected_username'] = 'DOMINIUM'
            self._apis[profile] = self._api_factory(self.runtime_root, **options)
        return self._apis[profile]

    def check(self, payload: dict) -> dict:
        """Confirm requested details, or search the contract's open candidates.

        ``open_orders_no_match`` confirms completion of the date/status search;
        it supplies no installer confirmation and authorizes no order creation.
        """
        profile, contract, date, requested = validate_order_check(payload)
        with self._locks[profile]:
            try:
                api = self._api(profile)
                open_orders = api.list_orders(date, status='field', service_type='all')
                if not isinstance(open_orders, list):
                    raise OrderCheckError('Consulta Imperium não confirmada')
                if requested:
                    candidates = []
                    for number in requested:
                        matches = [order for order in open_orders if order.num_os == number]
                        if len(matches) != 1 or matches[0].contract != contract:
                            raise OrderCheckError('OS solicitada ausente ou ambígua no contrato aberto')
                        candidates.append(matches[0])
                else:
                    candidates = [order for order in open_orders if order.contract == contract]
                if len({order.num_os for order in candidates}) != len(candidates) or len({order.id_os for order in candidates}) != len(candidates):
                    raise OrderCheckError('Consulta de OS ambígua')
                orders = []
                for order in candidates:
                    if (order.status != STATUS or type(order.id_os) is not int or order.id_os <= 0
                            or not isinstance(order.num_os, str) or not re.fullmatch(r'[0-9]{1,10}', order.num_os)):
                        raise OrderCheckError('OS aberta não confirmada')
                    detail = api.order_installer(order)
                    if (not isinstance(detail, dict) or detail.get('ok') is not True
                            or detail.get('source') != 'imperium_detail'
                            or type(detail.get('id_os')) is not int or detail['id_os'] != order.id_os
                            or detail.get('contract') != contract
                            or type(detail.get('installer_id')) is not int or detail['installer_id'] <= 0
                            or not isinstance(detail.get('installer_name'), str)):
                        raise OrderCheckError('Identidade ou instalador da OS não confirmado')
                    orders.append({
                        'num_os': order.num_os, 'id_os': order.id_os, 'contract': contract,
                        'installer_id': detail['installer_id'], 'installer_name': detail['installer_name'],
                        'status': order.status, 'service': order.service,
                    })
            except OrderCheckError:
                raise
            except Exception as error:
                # Never propagate DataSnap messages, paths or credential contents.
                raise OrderCheckUnavailableError('Consulta Imperium indisponível; OS não confirmadas') from error
        return {
            'confirmed': True, 'searched': True,
            'source': 'imperium_detail' if orders else 'open_orders_no_match',
            'profile_key': profile, 'contract': contract,
            'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'orders': orders,
        }
