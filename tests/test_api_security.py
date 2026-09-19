import json
import os
import re
import unittest
from unittest.mock import patch
from pathlib import Path

from api_security import (
    API_INVENTORY,
    SECURITY_HEADERS,
    LocalRateLimiter,
    redact_log_text,
    validate_local_request,
)


class APISecurityTests(unittest.TestCase):
    def test_inventory_covers_every_integration_without_secrets(self) -> None:
        names = {item["name"] for item in API_INVENTORY}
        self.assertTrue(any("Official" in name for name in names))
        self.assertTrue(any("DataSnap" in name for name in names))
        self.assertTrue(any("TOA" in name for name in names))
        rendered = json.dumps(API_INVENTORY).lower()
        self.assertNotIn("password", rendered)
        self.assertNotIn("bearer ", rendered)

    def test_loopback_same_origin_json_is_allowed(self) -> None:
        decision = validate_local_request(
            {
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "Sec-Fetch-Site": "same-origin",
                "Content-Type": "application/json; charset=utf-8",
            },
            "POST",
        )
        self.assertTrue(decision.allowed)

    def test_configured_public_https_origin_is_allowed(self) -> None:
        with patch.dict(os.environ, {"DOMINIUM_PUBLIC_ORIGIN": "https://dominium.example"}):
            decision = validate_local_request(
                {
                    "Host": "dominium.example",
                    "Origin": "https://dominium.example",
                    "Sec-Fetch-Site": "same-origin",
                    "Content-Type": "application/json",
                },
                "POST",
            )
            self.assertTrue(decision.allowed)
            evil = validate_local_request(
                {"Host": "dominium.example", "Origin": "https://evil.example", "Content-Type": "application/json"},
                "POST",
            )
            self.assertEqual(evil.status, 403)

    def test_dns_rebinding_and_cross_site_posts_are_blocked(self) -> None:
        rebound = validate_local_request({"Host": "evil.example:8765"}, "GET")
        cross_site = validate_local_request(
            {
                "Host": "127.0.0.1:8765",
                "Origin": "https://evil.example",
                "Sec-Fetch-Site": "cross-site",
                "Content-Type": "application/json",
            },
            "POST",
        )
        self.assertEqual(rebound.status, 403)
        self.assertEqual(cross_site.status, 403)
        wrong_port = validate_local_request(
            {
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:9999",
                "Content-Type": "application/json",
            },
            "POST",
        )
        self.assertEqual(wrong_port.status, 403)

    def test_simple_post_content_type_is_blocked(self) -> None:
        decision = validate_local_request(
            {"Host": "localhost:8765", "Content-Type": "text/plain"},
            "POST",
        )
        self.assertEqual(decision.status, 415)

    def test_security_headers_cover_browser_boundaries(self) -> None:
        self.assertIn("frame-ancestors 'none'", SECURITY_HEADERS["Content-Security-Policy"])
        self.assertEqual(SECURITY_HEADERS["X-Frame-Options"], "DENY")
        self.assertEqual(SECURITY_HEADERS["X-Content-Type-Options"], "nosniff")

    def test_main_page_has_no_inline_script_blocked_by_csp(self) -> None:
        html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        inline_scripts = re.findall(
            r"<script(?![^>]+\bsrc=)[^>]*>",
            html,
            flags=re.IGNORECASE,
        )
        self.assertEqual(inline_scripts, [])
        self.assertIn('<script src="/theme-init.js"></script>', html)

    def test_rate_limiter_is_bounded(self) -> None:
        limiter = LocalRateLimiter()
        self.assertTrue(limiter.allow("local:test", 2, 60, now=100))
        self.assertTrue(limiter.allow("local:test", 2, 60, now=101))
        self.assertFalse(limiter.allow("local:test", 2, 60, now=102))
        self.assertTrue(limiter.allow("local:test", 2, 60, now=161))

    def test_sensitive_query_values_are_redacted_from_logs(self) -> None:
        rendered = redact_log_text('GET /api/stock?serial=ABC123&contract=9988 HTTP/1.1')
        self.assertNotIn("ABC123", rendered)
        self.assertNotIn("9988", rendered)
        self.assertEqual(rendered.count("[redacted]"), 2)

    def test_unexpected_exception_details_are_not_returned_to_browser(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"error": f"Erro interno: {exc}"', source)
        self.assertIn('"error": "Erro interno; consulte o suporte"', source)


if __name__ == "__main__":
    unittest.main()
