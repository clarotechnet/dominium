import datetime as dt
import tempfile
import unittest
from pathlib import Path

from close_report import CloseReportStore


class CloseReportStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.date = dt.date(2026, 7, 20)
        self.store = CloseReportStore(Path(self.temporary.name), "natal")
        self.base = {
            "id_os": 2164088,
            "id_service": 10,
            "num_os": "2646800969",
            "contract": "4231199",
            "service": "ADESAO - INSTALAR PONTO VIRTUA",
            "close_code": "409",
            "close_description": "INSTALACAO CONCLUIDA",
            "transport": "official_http",
            "installed_count": 1,
            "material_count": 6,
            "fingerprint": "abc123",
        }

    def test_active_official_request_blocks_duplicate(self) -> None:
        first, duplicate = self.store.begin(
            self.base,
            date=self.date,
            block_active_duplicate=True,
        )
        self.assertFalse(duplicate)
        self.store.update(
            first["request_id"],
            {"state": "pending", "message": "Aguardando confirmacao"},
            date=self.date,
        )

        repeated, duplicate = self.store.begin(
            self.base,
            date=self.date,
            block_active_duplicate=True,
        )

        self.assertTrue(duplicate)
        self.assertEqual(repeated["request_id"], first["request_id"])
        self.assertEqual(len(self.store.list(self.date)), 1)

    def test_public_report_removes_internal_values(self) -> None:
        record, _ = self.store.begin(
            {**self.base, "toa_paste_key": "private-assignment-key"},
            date=self.date,
        )
        self.store.update(
            record["request_id"],
            {
                "state": "confirmed",
                "category": "SUCCESS",
                "category_label": "Baixada",
                "confirmed_at": "2026-07-20T15:00:00-03:00",
            },
            date=self.date,
        )

        payload = self.store.public_state(self.date)

        self.assertEqual(payload["summary"]["confirmed"], 1)
        self.assertNotIn("fingerprint", payload["records"][0])
        self.assertNotIn("toa_paste_key", payload["records"][0])

    def test_uncertain_is_counted_and_not_safe_to_retry(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {
                "state": "uncertain",
                "category": "CONFIRMATION",
                "category_label": "Nao confirmada",
                "safe_to_retry": False,
            },
            date=self.date,
        )

        payload = self.store.public_state(self.date)

        self.assertEqual(payload["summary"]["uncertain"], 1)
        self.assertFalse(payload["records"][0]["safe_to_retry"])

    def test_observed_close_keeps_attribution_unverified(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.assertEqual(record["attribution"], "pending")

        self.store.update(
            record["request_id"],
            {
                "state": "confirmed",
                "category": "OBSERVED_CLOSED",
                "category_label": "Fechada observada",
                "attribution": "unverified",
            },
            date=self.date,
        )

        stored = self.store.list(self.date)[0]
        self.assertEqual(stored["attribution"], "unverified")

    def test_authorize_retry_rejects_pending_state(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {"state": "pending", "confirmation_checks": 7},
            date=self.date,
        )

        with self.assertRaises(ValueError, msg="Deve rejeitar tentativa pending"):
            self.store.authorize_retry(record["request_id"], self.base["id_os"], date=self.date)

    def test_authorize_retry_rejects_fewer_than_seven_checks(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {"state": "uncertain", "confirmation_checks": 6},
            date=self.date,
        )

        with self.assertRaises(ValueError, msg="Deve rejeitar menos de 7 checagens"):
            self.store.authorize_retry(record["request_id"], self.base["id_os"], date=self.date)

    def test_authorize_retry_rejects_wrong_id_os(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {"state": "uncertain", "confirmation_checks": 7},
            date=self.date,
        )

        with self.assertRaises(ValueError, msg="Deve rejeitar outro id_os"):
            self.store.authorize_retry(record["request_id"], 9999999, date=self.date)

    def test_authorize_retry_releases_uncertain_with_seven_checks(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {"state": "uncertain", "confirmation_checks": 7},
            date=self.date,
        )

        updated = self.store.authorize_retry(
            record["request_id"], self.base["id_os"], date=self.date
        )

        self.assertEqual(updated["state"], "failed")
        self.assertEqual(updated["category"], "CONFIRMED_OPEN")
        self.assertTrue(updated["safe_to_retry"])

    def test_authorize_retry_rejects_changed_close_code(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {"state": "uncertain", "confirmation_checks": 7},
            date=self.date,
        )

        with self.assertRaisesRegex(ValueError, "mesmo codigo"):
            self.store.authorize_retry(
                record["request_id"],
                self.base["id_os"],
                date=self.date,
                close_code="430",
                transport="official_http",
            )

    def test_authorize_retry_allows_official_to_datasnap_fallback(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {"state": "uncertain", "confirmation_checks": 7},
            date=self.date,
        )

        updated = self.store.authorize_retry(
            record["request_id"],
            self.base["id_os"],
            date=self.date,
            close_code="409",
            transport="datasnap",
        )

        self.assertEqual(updated["state"], "failed")
        self.assertEqual(updated["category"], "CONFIRMED_OPEN")
        self.assertTrue(updated["safe_to_retry"])

    def test_authorize_retry_allows_datasnap_to_official_change(self) -> None:
        record, _ = self.store.begin(
            {**self.base, "transport": "datasnap"},
            date=self.date,
        )
        self.store.update(
            record["request_id"],
            {"state": "uncertain", "confirmation_checks": 7},
            date=self.date,
        )

        updated = self.store.authorize_retry(
            record["request_id"],
            self.base["id_os"],
            date=self.date,
            close_code="409",
            transport="official_http",
        )

        self.assertEqual(updated["state"], "failed")
        self.assertEqual(updated["category"], "CONFIRMED_OPEN")
        self.assertTrue(updated["safe_to_retry"])

    def test_update_stores_official_http_response(self) -> None:
        record, _ = self.store.begin(self.base, date=self.date)
        self.store.update(
            record["request_id"],
            {
                "state": "pending",
                "official_http_status": 200,
                "official_http_response": '{"status":"ok","message":"Baixa registrada"}',
            },
            date=self.date,
        )

        stored = self.store.list(self.date)[0]
        self.assertEqual(
            stored["official_http_response"],
            '{"status":"ok","message":"Baixa registrada"}',
        )

    def test_begin_stores_scheduled_date_and_retry_fields(self) -> None:
        record, _ = self.store.begin(
            {
                **self.base,
                "scheduled_date": "2026-07-20",
                "retry_of_request_id": "abc123",
                "attempts": 2,
            },
            date=self.date,
        )

        self.assertEqual(record["scheduled_date"], "2026-07-20")
        self.assertEqual(record["retry_of_request_id"], "abc123")
        self.assertEqual(record["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
