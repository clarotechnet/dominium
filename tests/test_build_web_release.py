import unittest
from pathlib import Path

from scripts.build_web_release import release_source_allowed


class WebReleaseBuildTests(unittest.TestCase):
    def test_local_runtime_directories_are_excluded(self) -> None:
        for value in (
            "supabase/.temp/project-ref",
            "deploy/supabase-hosted/supabase/.temp/linked-project.json",
            "static/__pycache__/cache.pyc",
            "data/runtime.sqlite3",
        ):
            with self.subTest(value=value):
                self.assertFalse(release_source_allowed(Path(value)))

    def test_backups_and_temporary_files_are_excluded(self) -> None:
        for value in ("static/app.js.bak", "static/app.js.bak_old", "static/cache.tmp"):
            with self.subTest(value=value):
                self.assertFalse(release_source_allowed(Path(value)))

    def test_production_assets_remain_allowed(self) -> None:
        self.assertTrue(release_source_allowed(Path("static/app.js")))
        self.assertTrue(release_source_allowed(Path("supabase/migrations/001.sql")))


if __name__ == "__main__":
    unittest.main()
