"""testing/test_conversion_tracking.py — Conversion tracking tests."""
from django.test import TestCase
from decimal import Decimal
from unittest.mock import patch, MagicMock

class TestConversionDeduplicatorHashing(TestCase):
    def test_hash_is_deterministic(self):
        from api.postback_engine.conversion_tracking.conversion_deduplicator import ConversionDeduplicator
        d = ConversionDeduplicator()
        self.assertEqual(d._hash("test"), d._hash("test"))

    def test_different_inputs_different_hash(self):
        from api.postback_engine.conversion_tracking.conversion_deduplicator import ConversionDeduplicator
        d = ConversionDeduplicator()
        self.assertNotEqual(d._hash("a"), d._hash("b"))

class TestConversionValidatorPayoutCap(TestCase):
    def test_excessive_payout_raises(self):
        from api.postback_engine.conversion_tracking.conversion_validator import ConversionValidator
        from api.postback_engine.exceptions import PayoutLimitExceededException
        v = ConversionValidator()
        with self.assertRaises(PayoutLimitExceededException):
            v.validate_payout_cap(Decimal("9999"))

    def test_valid_payout_passes(self):
        from api.postback_engine.conversion_tracking.conversion_validator import ConversionValidator
        v = ConversionValidator()
        v.validate_payout_cap(Decimal("0.01"))  # should not raise

class TestConversionWindow(TestCase):
    def test_zero_window_always_valid(self):
        from api.postback_engine.conversion_tracking.conversion_window import ConversionWindowChecker
        checker = ConversionWindowChecker()
        click_log = MagicMock()
        network = MagicMock(conversion_window_hours=0)
        self.assertTrue(checker.is_within_window(click_log, network))
