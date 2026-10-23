"""Prevent Node startup failure due to missing relative require() files in release."""
import re
import tempfile
import unittest
import zipfile
from pathlib import PurePosixPath,Path
from scripts.build_hostinger_node_release import build

REQUIRE = re.compile(r"\brequire\(\s*['\"](\.[^'\"]+)['\"]\s*\)")


class HostingerRuntimeDependencyTests(unittest.TestCase):
    def test_all_local_commonjs_dependencies_present_in_release(self):
        with tempfile.TemporaryDirectory() as directory:
            _, archive=build(Path(directory)/"release")
            with zipfile.ZipFile(archive) as z:
                names=set(z.namelist())
                server_scripts=[n for n in names if n.endswith(".js")
                                and "/" not in n and n != "lucide.min.js"]
                self.assertIn("atlas-query-policy.js",names)
                self.assertIn("static/atlas-query-ui.js",names)
                self.assertIn("operational-relay.js",names)
                for script in server_scripts:
                    raw=z.read(script).decode("utf-8")
                    for ref in REQUIRE.findall(raw):
                        target=(PurePosixPath(script).parent/ref).as_posix()
                        parts=[]
                        for item in target.split("/"):
                            if item=="..":
                                if parts:parts.pop()
                            elif item!=".":parts.append(item)
                        normalized="/".join(parts)
                        if not normalized.endswith(".js"):
                            normalized+=".js"
                        self.assertIn(normalized,names,
                            f"{script} requires {ref}, absent from Hostinger release")

if __name__=="__main__":
    unittest.main()
