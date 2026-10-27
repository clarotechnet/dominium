"""Restart only idle panel/gateway after a backed-up, syntax-checked installation."""
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from install import install

ROOT = Path(r'C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA')
BASE = 'http://127.0.0.1:8765'
STATE = Path(__file__).with_name('deployment.json')


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.load(response)


def start_panel():
    logs = ROOT / 'logs'
    with (logs / 'import-all-panel.stdout.log').open('ab') as out, (logs / 'import-all-panel.stderr.log').open('ab') as err:
        subprocess.Popen([sys.executable, '-u', 'app.py', '--port', '8765', '--panel-only'],
                         cwd=ROOT, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)


def wait_panel():
    for _ in range(30):
        try:
            return request('/api/toa-automation')
        except Exception:
            time.sleep(1)
    raise RuntimeError('Panel did not become available')


if __name__ == '__main__':
    automation = request('/api/toa-automation')
    runtime = request('/api/auto-improductive-close')
    if automation.get('running') or runtime.get('running') or runtime.get('bucket_collection', {}).get('running'):
        raise RuntimeError('Active operation; defer deployment until idle')
    previous_enabled = bool(runtime.get('enabled'))
    record = {'started_at': dt.datetime.now().isoformat(), 'previous_runtime_enabled': previous_enabled}
    STATE.write_text(json.dumps(record), encoding='utf-8')
    previous_desc = hashlib.sha256((ROOT / 'desc_only_scope.py').read_bytes()).hexdigest()
    report = None
    try:
        if previous_enabled:
            request('/api/auto-improductive-close/toggle', {'enabled': False})
        runtime = request('/api/auto-improductive-close')
        if runtime.get('running') or request('/api/toa-automation').get('running'):
            raise RuntimeError('Operation started during preflight; abort')
        report = install(ROOT, apply=True)
        record.update(report)
        STATE.write_text(json.dumps(record), encoding='utf-8')
        stop = '''$ErrorActionPreference='Stop'
foreach ($port in @(8765,9341)) {
 $listener=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
 foreach ($item in $listener) {
  $process=Get-CimInstance Win32_Process -Filter ("ProcessId="+$item.OwningProcess)
  $expected=if($port -eq 8765){'app.py.*--port 8765.*--panel-only'}else{'toa_session_gateway.py'}
  if($process.Name -ne 'python.exe' -or $process.CommandLine -notmatch $expected){throw 'Unexpected listener; abort'}
  Stop-Process -Id $item.OwningProcess -ErrorAction Stop
 }
}'''
        subprocess.run(['powershell', '-NoProfile', '-Command', stop], check=True, capture_output=True)
        start_panel()
        state = wait_panel()
        if not state.get('browser_session_available'):
            raise RuntimeError('TOA session not available after restart')
        if hashlib.sha256((ROOT / 'desc_only_scope.py').read_bytes()).hexdigest() != previous_desc:
            raise RuntimeError('Unexpected DESC scope change')
        record.update(healthy=True, desc_scope_unchanged=True, hashes_verified=all(
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
            for name, digest in report['files'].items()))
        if not record['hashes_verified']:
            raise RuntimeError('Installed hash mismatch')
        STATE.write_text(json.dumps(record), encoding='utf-8')
        print(json.dumps(record), flush=True)
    finally:
        if previous_enabled:
            try:
                request('/api/auto-improductive-close/toggle', {'enabled': True})
            except Exception:
                record['runtime_restore_pending'] = True
                STATE.write_text(json.dumps(record), encoding='utf-8')
