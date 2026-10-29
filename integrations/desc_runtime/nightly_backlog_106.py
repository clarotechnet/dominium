"""Operator-authorized 23h backlog batch. Default is read-only preview.

Uses the existing panel API and its DataSnap validation/audit, not a new close protocol.
Never backfills another day, creates an OS, retries an uncertain write, or moves stock.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import unicodedata
import urllib.parse
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8765'
BRAZIL = dt.timezone(dt.timedelta(hours=-3))
PROFILES = ('natal', 'fortaleza', 'mossoro', 'recife')


def now():
    return dt.datetime.now(BRAZIL)


def execution_window(day, current):
    return current.date().isoformat() == day and current.hour == 23


def request(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


def orders(profile, day, service, api=request):
    query = urllib.parse.urlencode(dict(profile=profile, date=day,
                                       status='field', service_type=service))
    result = api('/api/orders?' + query)
    if (result.get('date') != day or result.get('stale') or result.get('read_only')
            or result.get('status_filter') != 'field'
            or result.get('service_type_filter') != service
            or not isinstance(result.get('orders'), list)):
        raise ValueError('Consulta incompleta, antiga ou fora dos filtros autorizados')
    rows = result['orders']
    if len({row['id_os'] for row in rows}) != len(rows):
        raise ValueError('IdOS duplicado na consulta')
    return rows


def identity(row):
    return tuple(str(row.get(key, '')) for key in ('id_os', 'num_os', 'contract', 'id_service', 'service'))


def close_payload(row, expected, profile, day):
    status = unicodedata.normalize('NFD', str(row.get('status', ''))).upper().strip()
    if status != 'EM CAMPO' or identity(row) != identity(expected):
        raise ValueError('OS mudou de identidade ou nao esta mais Em campo')
    if row.get('operation_blockers') or not row.get('approved_state_hash'):
        raise ValueError('OS bloqueada pela validacao do painel')
    source = row.get('operation_source')
    scope = row.get('manual_scope') if source == 'imperium_cache' else row.get('import_scope')
    if source not in ('imperium_cache', 'toa_import') or not isinstance(scope, dict):
        raise ValueError('Escopo de baixa ausente')
    if source == 'imperium_cache':
        if scope.get('profile_key') != profile or scope.get('cache_date') != day:
            raise ValueError('Regional ou data divergente')
        if scope.get('state_hash') != row['approved_state_hash']:
            raise ValueError('Estado de aprovacao divergente')
    else:
        ident = row.get('operation_identity') or {}
        if ident.get('profile_key') != profile or not ident.get('activity_id') or not scope.get('source_hash'):
            raise ValueError('Identidade TOA divergente')
    return dict(num_os=row['num_os'], code='106', observation='', transport='datasnap',
                operation_source=source, operation_identity=row.get('operation_identity'),
                approved_state_hash=row['approved_state_hash'], import_scope=row.get('import_scope'),
                approved_source_hash=scope.get('source_hash'), manual_scope=row.get('manual_scope'),
                scheduled_date=day, technician=row.get('technician') or row.get('installer') or '',
                technician_id=row.get('technician_id') or row.get('installer_id') or 0,
                city=row.get('city') or '')


def run(execute=False, api=request, clock=now, pause=time.sleep, state_dir=None, should_stop=lambda: False):
    day = clock().date().isoformat()
    if execute and not execution_window(day, clock()):
        raise ValueError('Baixas automaticas permitidas somente entre 23:00 e 23:59, horario de Brasilia')
    def read_api(path):
        # The gate can be busy during imports. Retry only GETs within the
        # authorized hour; a POST is always sent once and reconciled separately.
        for attempt in range(12):
            if execute and (should_stop() or not execution_window(day, clock())):
                raise ValueError('Janela das 23h terminou ou rotina pausada')
            try:
                return api(path)
            except urllib.error.HTTPError as exc:
                if (exc.code != 409 or attempt == 11 or not execute
                        or should_stop() or not execution_window(day, clock())):
                    raise
                pause(15)

    profiles = read_api('/api/profiles')
    available = {p['key']: p for p in profiles.get('profiles', [])}
    if not profiles.get('ok') or any(available.get(p, {}).get('project', {}).get('project_id') != 'IMPERIUM_OLLAMA' for p in PROFILES):
        raise ValueError('Servidor nao corresponde ao Dominium primario esperado')
    folder = Path(state_dir or ROOT / 'config' / 'nightly_backlog_106')
    report = {'date': day, 'mode': 'execute' if execute else 'preview', 'profiles': {}}
    for profile in PROFILES:
        summary = {'eligible': 0, 'confirmed': 0, 'skipped': 0, 'errors': []}
        report['profiles'][profile] = summary
        try:
            if should_stop():
                raise ValueError('Rotina pausada ou servidor encerrando')
            if not available[profile].get('close_enabled'):
                raise ValueError('Baixa DataSnap desabilitada na regional')
            selected = orders(profile, day, 'disconnection', read_api)
            summary['eligible'] = len(selected)
            if not execute:
                # all refreshes the same cache used by the panel's close validation.
                current = {r['id_os']: r for r in orders(profile, day, 'all', read_api)}
                for row in selected:
                    if row['id_os'] not in current:
                        summary['skipped'] += 1
                        continue
                    close_payload(current[row['id_os']], row, profile, day)
                continue
            folder.mkdir(parents=True, exist_ok=True)
            for expected in selected:
                if should_stop() or not execution_window(day, clock()):
                    raise ValueError('Janela das 23h terminou; nenhuma baixa retroativa sera feita')
                key = f"{day}_{profile}_{int(expected['id_os'])}.json"
                receipt = folder / key
                if receipt.exists():
                    summary['skipped'] += 1
                    continue
                current = {r['id_os']: r for r in orders(profile, day, 'all', read_api)}
                row = current.get(expected['id_os'])
                if row is None:
                    summary['skipped'] += 1
                    continue
                payload = close_payload(row, expected, profile, day)
                if should_stop() or not execution_window(day, clock()):
                    raise ValueError('Janela das 23h terminou durante a consulta')
                audit = dict(date=day, profile=profile, id_os=row['id_os'], num_os=row['num_os'],
                             contract=row['contract'], code='106', observation='', transport='datasnap',
                             state='submitting', at=clock().isoformat())
                # Exclusive durable receipt before POST also prevents concurrent sends.
                try:
                    with receipt.open('x', encoding='utf-8') as file:
                        json.dump(audit, file, ensure_ascii=False)
                        file.flush()
                        os.fsync(file.fileno())
                except FileExistsError:
                    summary['skipped'] += 1
                    continue
                try:
                    result = api(f"/api/orders/{int(row['id_os'])}/close?profile={profile}", payload)
                    if (result.get('ok') is not True or str(result.get('code')) != '106'
                            or str(result.get('id_os')) != str(row['id_os'])
                            or str(result.get('num_os')) != str(row['num_os'])
                            or result.get('pending_confirmation')):
                        raise ValueError('Resposta nao confirma a baixa 106; nao repetir automaticamente')
                    audit['state'] = 'confirmed'
                    summary['confirmed'] += 1
                except Exception as exc:
                    audit.update(state='review_required', error=str(exc))
                    raise
                finally:
                    receipt.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
                pause(2)
        except Exception as exc:
            summary['errors'].append(str(exc))
        print(json.dumps({'profile': profile, **summary}, ensure_ascii=False), flush=True)
    if execute:
        folder.mkdir(parents=True, exist_ok=True)
        report_path = folder / f"report_{day}_{clock().strftime('%H%M%S')}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Executa o lote autorizado somente durante as 23h')
    args = parser.parse_args()
    result = run(execute=args.execute)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if any(p['errors'] for p in result['profiles'].values()) else 0)
