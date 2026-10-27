"""Apply a checked, backed-up patch to the legacy server without replacing its tree."""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Source changed; expected exactly one patch anchor: ' + old[:70])
    return source.replace(old, new, 1)


def build_changes(root: Path):
    changes = {}
    source = (root / 'toa_session_gateway.py').read_text(encoding='utf-8-sig')
    source = once(source, 'from desc_only_scope import DESC_ALLOWED_ROUTES',
                  'from desc_only_scope import DESC_ALLOWED_ROUTES\nfrom toa_import_scope import validate_import_route')
    source = once(source, '    if path == "/toa/lookup":', '''    if path == "/toa/import-export":
        route = (query.get("route") or [""])[0]
        day = (query.get("date") or [""])[0]
        validate_import_route(route, day)
        return "globalThis.TNTOAAutoExport.exportRoute(" + json.dumps(route) + "," + json.dumps(day) + ")"
    if path == "/toa/lookup":''')
    source = once(source, 'elif parsed.path == "/toa/export":',
                  'elif parsed.path in {"/toa/export", "/toa/import-export"}:')
    changes['toa_session_gateway.py'] = source

    source = (root / 'toa_secondary_bucket_export.mjs').read_text(encoding='utf-8-sig')
    source = once(source, "['list','export']", "['list','export','import-export']")
    source = once(source, ": '/toa/export?route='", ": (action === 'import-export' ? '/toa/import-export' : '/toa/export') + '?route='")
    changes['toa_secondary_bucket_export.mjs'] = source

    source = (root / 'toa_automation.py').read_text(encoding='utf-8-sig')
    source = once(source, 'from desc_only_scope import DESC_ALLOWED_ROUTES',
                  'from toa_import_scope import IMPORT_ALLOWED_ROUTES')
    source = once(source, "# Conta TOA do servidor: apenas buckets de desconexao.",
                  '# Import all authorized DMV buckets; write-off scopes remain separate.')
    source = once(source, "r.get('route') in DESC_ALLOWED_ROUTES", "r.get('route') in IMPORT_ALLOWED_ROUTES")
    changes['toa_automation.py'] = source

    source = (root / 'toa_bucket_collector.py').read_text(encoding='utf-8-sig')
    source += '''

class TOAImportExporter(TOAExistingSessionExporter):
    """All-bucket same-day export for the importer; DESC collectors keep their adapter."""
    def _call(self, *args, **kwargs):
        if args and args[0] == "export":
            args = ("import-export", *args[1:])
        return super()._call(*args, **kwargs)

    def export_route(self, route, date=None, timeout=300.0):
        from toa_import_scope import validate_import_route
        day = date or dt.date.today()
        validate_import_route(route, day.isoformat())
        return super().export_route(route, day)
'''
    changes['toa_bucket_collector.py'] = source

    source = (root / 'app.py').read_text(encoding='utf-8-sig')
    source = once(source, 'from desc_only_scope import DESC_ALLOWED_ROUTES, filter_desc_preview',
                  'from desc_only_scope import DESC_ALLOWED_ROUTES, filter_desc_preview\nfrom toa_import_scope import IMPORT_ALLOWED_ROUTES, filter_import_preview')
    source = once(source, 'from toa_bucket_collector import TOABucketCollector, TOADisconnectionExporter',
                  'from toa_bucket_collector import TOABucketCollector, TOADisconnectionExporter, TOAImportExporter')
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_automatic_toa_import')
    original = ast.get_source_segment(source, function)
    updated = once(original, 'not in DESC_ALLOWED_ROUTES', 'not in IMPORT_ALLOWED_ROUTES')
    updated = once(updated, 'Conta TOA do servidor restrita a desconexao', 'Bucket fora do escopo de importacao')
    updated = once(updated, 'filter_desc_preview(preview, route=route["route"])', 'filter_import_preview(preview, route=route["route"])')
    updated = once(updated, 'vazia_sem_desc', 'vazia_sem_os_validas')
    source = once(source, original, updated)
    source = once(source, 'TOADisconnectionExporter(ROOT, download_root)', 'TOAImportExporter(ROOT, download_root)')
    changes['app.py'] = source
    changes['toa_import_scope.py'] = Path(__file__).with_name('toa_import_scope.py').read_text(encoding='utf-8')
    for name, text in changes.items():
        if name.endswith('.py'):
            compile(text, name, 'exec')
    return changes


def install(root: Path, apply=False):
    changes = build_changes(root)
    report = {'files': {n: hashlib.sha256(v.encode('utf-8')).hexdigest() for n, v in changes.items()}, 'applied': False}
    if apply:
        backup = root / 'backups' / ('import-all-buckets-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
        backup.mkdir(parents=True, exist_ok=False)
        for name in changes:
            if (root / name).exists():
                shutil.copy2(root / name, backup / name)
        for name in ('config/toa_automation_state.json', 'config/desc_runtime_settings.json'):
            if (root / name).exists():
                shutil.copy2(root / name, backup / Path(name).name)
        for name, text in changes.items():
            temporary = root / (name + '.import-all.tmp')
            temporary.write_bytes(text.encode('utf-8'))
            temporary.replace(root / name)
        report.update(applied=True, backup=str(backup))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(args.root, args.apply)))
