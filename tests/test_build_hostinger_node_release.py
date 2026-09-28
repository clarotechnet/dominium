import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_hostinger_node_release import build


class HostingerNodeReleaseTests(unittest.TestCase):
    def test_release_contains_runtime_and_current_frontend(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release"
            _release, archive = build(output)
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())

        for required in (
            "server.js",
            "package.json",
            "package-lock.json",
            "protocol_templates.json",
            "static/index.html",
            "static/app.js",
            "static/styles.css",
            "RELEASE_MANIFEST.json",
        ):
            self.assertIn(required, names)

    def test_release_does_not_contain_backup_or_secret_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release"
            _release, archive = build(output)
            with zipfile.ZipFile(archive) as bundle:
                names = [name.casefold() for name in bundle.namelist()]

        self.assertFalse(any(".bak" in name for name in names))
        self.assertFalse(any(name.endswith(".tmp") for name in names))
        self.assertFalse(any("/.env" in name or name == ".env" for name in names))


if __name__ == "__main__":
    unittest.main()
