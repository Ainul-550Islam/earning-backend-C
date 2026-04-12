"""
testing/unit_test.py
─────────────────────
Unit tests for individual PostbackEngine components.
"""
from django.test import TestCase
from decimal import Decimal

class TestUtils(TestCase):
    def test_safe_decimal_valid(self):
        from api.postback_engine.utils import safe_decimal
        self.assertEqual(safe_decimal("1.50"), Decimal("1.50"))

    def test_safe_decimal_invalid_returns_default(self):
        from api.postback_engine.utils import safe_decimal
        self.assertEqual(safe_decimal("invalid"), Decimal("0"))

    def test_mask_secret(self):
        from api.postback_engine.utils import mask_secret
        masked = mask_secret("my_secret_key_12345")
        self.assertIn("...", masked)
        self.assertNotIn("secret", masked)

    def test_expand_url_macros(self):
        from api.postback_engine.utils import expand_url_macros
        url = expand_url_macros("https://x.com/?c={click_id}&p={payout}", {"click_id": "abc", "payout": "0.50"})
        self.assertEqual(url, "https://x.com/?c=abc&p=0.50")

    def test_seconds_to_human(self):
        from api.postback_engine.utils import seconds_to_human
        self.assertIn("m", seconds_to_human(90))
        self.assertIn("h", seconds_to_human(3700))
        self.assertIn("d", seconds_to_human(90000))

    def test_sha256_hex_deterministic(self):
        from api.postback_engine.utils import sha256_hex
        self.assertEqual(sha256_hex("hello"), sha256_hex("hello"))
        self.assertNotEqual(sha256_hex("hello"), sha256_hex("world"))

class TestFingerprinter(TestCase):
    def test_fingerprint_deterministic(self):
        from api.postback_engine.click_tracking.click_fingerprint import click_fingerprinter
        fp1 = click_fingerprinter.generate(ip="1.2.3.4", user_agent="Mozilla/5.0")
        fp2 = click_fingerprinter.generate(ip="1.2.3.4", user_agent="Mozilla/5.0")
        self.assertEqual(fp1, fp2)

    def test_different_ips_different_fingerprint(self):
        from api.postback_engine.click_tracking.click_fingerprint import click_fingerprinter
        fp1 = click_fingerprinter.generate(ip="1.2.3.4", user_agent="Mozilla/5.0")
        fp2 = click_fingerprinter.generate(ip="9.9.9.9", user_agent="Mozilla/5.0")
        self.assertNotEqual(fp1, fp2)
