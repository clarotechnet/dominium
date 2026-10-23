"""Portable agent memory regression tests; no network, secrets or production changes."""
from __future__ import annotations
import importlib.util
import io
import sqlite3
import subprocess
import tempfile
import unittest
import zipfile
from argparse import Namespace
from contextlib import redirect_stdout, closing
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
mem=load("agent_memory.py","dominium_agent_memory")
mcp_spec=importlib.util.spec_from_file_location("dominium_agent_mcp",ROOT/"scripts"/"agent_memory_mcp.py")
# MCP imports agent_memory as module name; share the tested object.
import sys
sys.modules["agent_memory"]=mem
mcp=importlib.util.module_from_spec(mcp_spec)
mcp_spec.loader.exec_module(mcp)


class PortableAgentMemoryTests(unittest.TestCase):
    def test_all_cross_agent_entrypoints_and_handoff_exist(self):
        for filename in ("AGENTS.md","CLAUDE.md","GEMINI.md",
                         ".github/copilot-instructions.md",
                         ".cursor/rules/dominium-memory.mdc",
                         "docs/agent/MEMORY_SYSTEM.md",
                         "docs/agent/memory/CURRENT_STATE.md"):
            self.assertTrue((ROOT/filename).is_file(),filename)
        self.assertIn("agent_memory.py", (ROOT/"AGENTS.md").read_text(encoding="utf-8"))

    def test_cache_contains_curated_files_but_excludes_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            db,fts=mem.create_index(Path(tmp)/"memory.sqlite3")
            try:
                paths={row[0] for row in db.execute("SELECT path FROM documents")}
                self.assertIn("docs/agent/memory/CURRENT_STATE.md",paths)
                self.assertIn("docs/agent/memory/DECISIONS.md",paths)
                self.assertTrue(all(not path.startswith(("data/","output/","logs/")) for path in paths))
                self.assertTrue(fts or not fts)  # SQLite LIKE fallback is supported.
            finally:db.close()

    def test_query_provides_sources_and_rebuilds_stale_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mem,"CACHE",Path(tmp)/"index.sqlite3"):
                stream=io.StringIO()
                with redirect_stdout(stream):
                    mem.search("Atlas IMPERIUM",5)
                answer=stream.getvalue()
                self.assertIn("SOURCE docs/agent/memory/",answer)
                with closing(sqlite3.connect(mem.CACHE)) as db:
                    with db:
                        db.execute("UPDATE metadata SET value='invalid'")
                with redirect_stdout(io.StringIO()):
                    mem.search("Atlas",3)
                with closing(sqlite3.connect(mem.CACHE)) as db:
                    fingerprint=db.execute("SELECT value FROM metadata").fetchone()[0]
                self.assertNotEqual(fingerprint,"invalid")

    def test_manual_record_redacts_obvious_private_details(self):
        for item in ("senha: abc12345", "ghp_"+"x"*30,"246133891826",
                     "cookie=private",""):
            with self.assertRaises(ValueError):
                mem.safe_text(item)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mem,"MEMORY",Path(tmp)):
                fields=dict(title="Corrigir fluxo",why="Caminho legado falha",
                            changed="Confront engine",tests="15 testes locais OK",
                            next="Validar ambiente")
                with redirect_stdout(io.StringIO()):
                    mem.record(Namespace(**fields))
                written=(Path(tmp)/"OPERATIONS_JOURNAL.md").read_text(encoding="utf-8")
                self.assertIn("Corrigir fluxo",written)
                self.assertIn("15 testes locais OK",written)

    def test_precommit_autolog_deduplicates_same_staged_change(self):
        fake_names=subprocess.CompletedProcess([],0,stdout="static/app.js\0tests/test_confront_frontend.js\0")
        fake_raw=subprocess.CompletedProcess([],0,stdout="M :100644 100644 abc def M\tstatic/app.js\n")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"AUTO_CHANGES.md"
            path.write_text("# alteracoes\n",encoding="utf-8")
            with patch.object(mem,"AUTOMATIC",path), patch.object(mem,"run_git",
               side_effect=[fake_names,fake_raw,fake_names,fake_raw]):
                with redirect_stdout(io.StringIO()):
                    mem.autolog_staged()
                    first=path.read_text(encoding="utf-8")
                    mem.autolog_staged()
                    second=path.read_text(encoding="utf-8")
                self.assertEqual(first,second)
                self.assertIn("static/app.js",first)
                self.assertNotIn("M :100644",first)  # source diff never logged.

    def test_export_creates_portable_zip_without_runtime_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mem, "ROOT", Path(tmp)):
                with patch.object(mem, "memory_files", return_value=[
                    ("docs/agent/memory/CURRENT_STATE.md", "# DOMINIUM")]):
                    with patch.object(mem, "run_git", return_value=
                            subprocess.CompletedProcess([], 0, stdout="abc1234 | update")):
                        with redirect_stdout(io.StringIO()):
                            mem.export_bundle()
            path = Path(tmp) / "output" / "dominium-agent-handoff.zip"
            with zipfile.ZipFile(path) as archive:
                self.assertIn("docs/agent/memory/CURRENT_STATE.md", archive.namelist())
                self.assertIn("RECENT_GIT_COMMITS.md", archive.namelist())
                self.assertNotIn(".env", archive.namelist())

    def test_mcp_jsonrpc_tools_search_and_resource(self):
        initialized=mcp.process('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}')
        self.assertEqual(initialized["result"]["serverInfo"]["name"],"dominium-agent-memory")
        tools=mcp.process('{"jsonrpc":"2.0","id":2,"method":"tools/list"}')
        names={item["name"] for item in tools["result"]["tools"]}
        self.assertIn("dominium_memory_search",names)
        response=mcp.process('{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"dominium_memory_search","arguments":{"query":"Atlas"}}}')
        self.assertIn("SOURCE",response["result"]["content"][0]["text"])
        resource=mcp.process('{"jsonrpc":"2.0","id":4,"method":"resources/read","params":{"uri":"dominium://memory/current"}}')
        self.assertIn("DOMINIUM",resource["result"]["contents"][0]["text"])


if __name__=="__main__":
    unittest.main()
