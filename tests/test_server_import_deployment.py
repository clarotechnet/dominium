import importlib.util
from pathlib import Path
import socket
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1] / 'deploy/server-import-all'
sys.path.insert(0, str(PACKAGE))
spec = importlib.util.spec_from_file_location('server_import_deploy', PACKAGE / 'deploy.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OfflineDeploymentTests(unittest.TestCase):
    def test_a_live_listener_prevents_installation(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with self.assertRaisesRegex(RuntimeError, 'Stop the idle panel'):
                module.ensure_offline((listener.getsockname()[1],))

    def test_closed_port_allows_offline_preflight(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        module.ensure_offline((port,))
