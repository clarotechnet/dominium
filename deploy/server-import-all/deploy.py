"""Offline installation only: never terminate a panel that may start an import."""
import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from install import install


def ensure_offline(ports=(8765, 9341)):
    for port in ports:
        try:
            connection = socket.create_connection(('127.0.0.1', port), timeout=1)
        except ConnectionRefusedError:
            continue
        except OSError as exc:
            raise RuntimeError('Cannot confirm that services are offline') from exc
        else:
            connection.close()
            raise RuntimeError('Stop the idle panel and gateway before offline installation')


def start_panel(root):
    with (root / 'logs/import-all-panel.stdout.log').open('ab') as out, \
            (root / 'logs/import-all-panel.stderr.log').open('ab') as err:
        subprocess.Popen([sys.executable, '-u', 'app.py', '--port', '8765', '--panel-only'],
                         cwd=root, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)


def deploy(root, *, restart=False):
    # Operator must stop both idle services and their supervisors first.
    # This entry point deliberately has no online stop/restart sequence.
    ensure_offline()
    report = install(root, apply=True)
    report['hashes_verified'] = all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
                                    for name, digest in report['files'].items())
    if not report['hashes_verified']:
        raise RuntimeError('Installed hash mismatch')
    if restart:
        start_panel(root)
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8765/api/toa-automation', timeout=3) as response:
                    state = json.load(response)
                if not state.get('browser_session_available'):
                    raise RuntimeError('TOA session unavailable after restart')
                report['healthy'] = True
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError('Panel did not become available; restore backup before retrying')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    print(json.dumps(deploy(args.root, restart=args.restart)))
