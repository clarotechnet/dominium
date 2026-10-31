"""Offline tests: no DataSnap, Supabase connections, secrets or O.S. writes."""
import contextlib
from contextlib import closing
import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

from supabase_datasnap_sync import (
    IncompleteDay,
    map_history_row,
    read_verified_day,
    write_verified_day,
    sync_verified_day,
)

def valid_row(**changes):
    row = {
        "profile": "natal",
        "id_os": 1234567,
        "activity_date": "2026-10-29",
        "os_number": "2663679928",
        "contract": "4324960",
        "service": "ADESAO - PONTO VIRTUA",
        "code": "409",
        "verification": "confirmed",
        "status": "CONCLUIDA",
        "captured_at": "2026-10-30T18:00:00+00:00",
    }
    row.update(changes)
    return row

class FakeCursor:
    def __init__(self, count):
        self.count = count
        self.calls = []
    def execute(self, sql, params):
        self.calls.append((sql, params))
    def fetchone(self):
        return (self.count,)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

class FakeConnection:
    def __init__(self, count):
        self.cursor_obj = FakeCursor(count)
        self.transaction_exited_ok = None
    @contextlib.contextmanager
    def transaction(self):
        try:
            yield
            self.transaction_exited_ok = True
        except Exception:
            self.transaction_exited_ok = False
            raise
    def cursor(self):
        return self.cursor_obj

class MappingTests(unittest.TestCase):
    def test_confirmed_code_uses_actual_detail(self):
        p = map_history_row(valid_row())
        self.assertEqual(p["legacy_id"], "natal:1234567:2026-10-29")
        self.assertEqual(p["baixa_code"], "409")
        self.assertEqual(p["source_verification"], "confirmed")
        self.assertEqual(p["source_status"], "CONCLUIDA")
        self.assertEqual(p["cidade"], "NATAL/PARNAMIRIM")
        self.assertNotIn("baixa_date", p)

    def test_missing_code_stays_missing(self):
        p = map_history_row(valid_row(code=None, verification="missing_code", status="EM CAMPO"))
        self.assertEqual(p["baixa_code"], "")
        self.assertEqual(p["source_verification"], "missing_code")
        self.assertEqual(p["source_status"], "EM CAMPO")

    def test_reject_unconfirmed_code_injection(self):
        with self.assertRaises(ValueError):
            map_history_row(valid_row(code="409", verification="missing_code"))

    def test_reject_invalid_code(self):
        for code in ("000", "40", "409X", "409;DROP", ""):
            with self.subTest(code=code), self.assertRaises(ValueError):
                map_history_row(valid_row(code=code))

    def test_reject_bad_identity(self):
        for changes in (
            {"profile": "unknown"},
            {"id_os": 0},
            {"activity_date": "2026-02-30"},
            {"contract": "123x"},
            {"os_number": "X"},
            {"captured_at": "2026-10-29T12:00:00"},
            {"status": "???"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                map_history_row(valid_row(**changes))

    def test_all_four_profiles_use_distinct_identifiers(self):
        keys = set()
        for profile in ("natal","fortaleza","mossoro","recife"):
            p = map_history_row(valid_row(profile=profile))
            keys.add(p["legacy_id"])
        self.assertEqual(len(keys), 4)

class SQLiteCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "backlog.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript("""
                CREATE TABLE history(
                  profile text,id_os integer,activity_date text,os_number text,
                  contract text,service text,code text,verification text,
                  status text,captured_at text,
                  PRIMARY KEY(profile,id_os,activity_date));
                CREATE TABLE checkpoint(profile text PRIMARY KEY,date text);
            """)
            row = valid_row()
            conn.execute(
                "INSERT INTO history VALUES(?,?,?,?,?,?,?,?,?,?)",
                tuple(row[k] for k in ("profile","id_os","activity_date","os_number",
                                        "contract","service","code","verification",
                                        "status","captured_at"))
            )
    def tearDown(self):
        self.temp.cleanup()

    def test_refuse_day_without_checkpoint(self):
        with self.assertRaises(IncompleteDay):
            read_verified_day(self.db, "natal", "2026-10-29")

    def test_refuse_future_day_when_checkpoint_old(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO checkpoint VALUES(?,?)",("natal","2026-10-28"))
        with self.assertRaises(IncompleteDay):
            read_verified_day(self.db, "natal", "2026-10-29")

    def test_unverified_day_never_reaches_postgres(self):
        connection = FakeConnection(1)
        with self.assertRaises(IncompleteDay):
            sync_verified_day(connection, self.db, "natal", "2026-10-29")
        self.assertEqual(connection.cursor_obj.calls, [])

    def test_verified_day_sync_commits_after_source_checkpoint(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO checkpoint VALUES(?,?)",("natal","2026-10-29"))
        connection = FakeConnection(1)
        self.assertEqual(sync_verified_day(connection,self.db,"natal","2026-10-29"),1)
        self.assertTrue(connection.transaction_exited_ok)

    def test_only_checkpointed_day_is_readable(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO checkpoint VALUES(?,?)",("natal","2026-10-29"))
        r = read_verified_day(self.db, "natal", "2026-10-29")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["source_id_os"], 1234567)
        self.assertEqual(r[0]["baixa_code"], "409")

    def test_empty_checkpointed_day_is_valid(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO checkpoint VALUES(?,?)",("recife","2026-10-29"))
        r = read_verified_day(self.db, "recife", "2026-10-29")
        self.assertEqual(r, [])

class PostgreSQLWriteTests(unittest.TestCase):
    def test_checkpoint_is_after_all_rows_and_verification(self):
        row = map_history_row(valid_row())
        connection = FakeConnection(1)
        n = write_verified_day(connection,"natal","2026-10-29",[row])
        self.assertEqual(n, 1)
        ops = connection.cursor_obj.calls
        self.assertEqual(len(ops),3)
        self.assertIn("INSERT INTO backlog_lab.history",ops[0][0])
        self.assertIn("ON CONFLICT (legacy_id)",ops[0][0])
        self.assertEqual(ops[0][1]["source_id_os"],1234567)
        self.assertIn("SELECT count(*)",ops[1][0])
        self.assertIn("INSERT INTO backlog_lab.datasnap_checkpoints",ops[2][0])
        self.assertTrue(connection.transaction_exited_ok)

    def test_count_mismatch_aborts_without_checkpoint(self):
        row = map_history_row(valid_row())
        connection = FakeConnection(0)
        with self.assertRaises(IncompleteDay):
            write_verified_day(connection,"natal","2026-10-29",[row])
        self.assertFalse(connection.transaction_exited_ok)
        self.assertEqual(len(connection.cursor_obj.calls),2)

    def test_mixed_profiles_cannot_be_committed(self):
        row = map_history_row(valid_row(profile="fortaleza"))
        connection = FakeConnection(1)
        with self.assertRaises(ValueError):
            write_verified_day(connection,"natal","2026-10-29",[row])
        self.assertEqual(connection.cursor_obj.calls,[])

    def test_invalid_payload_fields_cannot_be_added(self):
        row = map_history_row(valid_row())
        row["unexpected"]="DROP TABLE"
        with self.assertRaises(ValueError):
            write_verified_day(FakeConnection(1),"natal","2026-10-29",[row])

    def test_empty_day_commits_zero_row_checkpoint(self):
        connection = FakeConnection(0)
        n = write_verified_day(connection,"mossoro","2026-10-29",[])
        self.assertEqual(n,0)
        self.assertEqual(len(connection.cursor_obj.calls),2)
        self.assertTrue(connection.transaction_exited_ok)

if __name__=="__main__":
    unittest.main()
