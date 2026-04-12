# api/offer_inventory/testing_qa/unit_test_cases.py
"""
Unit Test Cases — Core business logic tests.
Tests: revenue calculation, dedup, fraud scoring, SmartLink AI.
Run: python manage.py test api.offer_inventory.testing_qa.unit_test_cases
"""
from decimal import Decimal
from django.test import TestCase


class RevenueCalculatorTests(TestCase):
    """Tests for 100% Decimal revenue calculation."""

    def setUp(self):
        from api.offer_inventory.finance_payment.revenue_calculator import RevenueCalculator
        self.calc = RevenueCalculator

    def test_no_float_in_output(self):
        """All output values must be Decimal."""
        result = self.calc.calculate(gross=Decimal('1.5000'))
        self.assertIsInstance(result.gross_revenue,  Decimal)
        self.assertIsInstance(result.platform_cut,   Decimal)
        self.assertIsInstance(result.net_to_user,    Decimal)

    def test_gross_equals_platform_plus_user(self):
        """platform_cut + user_gross ≈ gross (within rounding)."""
        result = self.calc.calculate(gross=Decimal('1.0000'))
        diff   = abs(result.platform_cut + result.user_gross - result.gross_revenue)
        self.assertLess(diff, Decimal('0.01'))

    def test_referral_after_fee(self):
        """Referral commission must be on user_gross, not gross."""
        result = self.calc.calculate(
            gross=Decimal('1.0000'), has_referral=True
        )
        # Referral should be ≤ user_gross × 5%
        max_referral = result.user_gross * Decimal('0.05')
        self.assertLessEqual(result.referral_commission, max_referral + Decimal('0.001'))

    def test_net_never_negative(self):
        """net_to_user must never be negative."""
        result = self.calc.calculate(gross=Decimal('0.0001'), has_referral=True)
        self.assertGreaterEqual(result.net_to_user, Decimal('0'))

    def test_zero_gross(self):
        """Zero gross should return all zeros without error."""
        result = self.calc.calculate(gross=Decimal('0'))
        self.assertEqual(result.gross_revenue, Decimal('0'))
        self.assertEqual(result.net_to_user,   Decimal('0'))


class DeduplicationEngineTests(TestCase):
    """Tests for conversion deduplication."""

    def test_make_fingerprint_consistent(self):
        """Same inputs must always produce same fingerprint."""
        from api.offer_inventory.conversion_tracking import DeduplicationEngine
        fp1 = DeduplicationEngine.make_fingerprint('user1', 'offer1', '1.2.3.4')
        fp2 = DeduplicationEngine.make_fingerprint('user1', 'offer1', '1.2.3.4')
        self.assertEqual(fp1, fp2)

    def test_fingerprint_different_users(self):
        """Different users must produce different fingerprints."""
        from api.offer_inventory.conversion_tracking import DeduplicationEngine
        fp1 = DeduplicationEngine.make_fingerprint('user1', 'offer1', '1.2.3.4')
        fp2 = DeduplicationEngine.make_fingerprint('user2', 'offer1', '1.2.3.4')
        self.assertNotEqual(fp1, fp2)

    def test_tx_id_cache_check(self):
        """Known transaction_id returns True (duplicate)."""
        from api.offer_inventory.conversion_tracking import DeduplicationEngine
        from django.core.cache import cache
        tx_id = 'TEST_TX_DEDUP_123'
        cache.set(f'txid_seen:{tx_id}', '1', 60)
        self.assertTrue(DeduplicationEngine.check_transaction_id(tx_id))
        cache.delete(f'txid_seen:{tx_id}')

    def test_unknown_tx_id_not_duplicate(self):
        """Unknown transaction_id returns False (not duplicate)."""
        from api.offer_inventory.conversion_tracking import DeduplicationEngine
        self.assertFalse(DeduplicationEngine.check_transaction_id('UNKNOWN_TX_XYZ_99'))


class FraudDetectionTests(TestCase):
    """Tests for fraud detection engine."""

    def test_empty_ua_is_high_risk(self):
        """Empty user agent should score high for bot."""
        from api.offer_inventory.security_fraud.bot_detection import BotDetector
        score = BotDetector._score_user_agent('')
        self.assertGreaterEqual(score, 80.0)

    def test_known_bot_ua_scores_100(self):
        """Known bot UA strings should score 100."""
        from api.offer_inventory.security_fraud.bot_detection import BotDetector
        bot_uas = [
            'Googlebot/2.1 (+http://www.google.com/bot.html)',
            'python-requests/2.28.0',
            'HeadlessChrome/91.0',
        ]
        for ua in bot_uas:
            score = BotDetector._score_user_agent(ua)
            self.assertGreaterEqual(score, 80.0, f'UA should score ≥80: {ua}')

    def test_real_browser_scores_zero(self):
        """Normal browser UA should score 0."""
        from api.offer_inventory.security_fraud.bot_detection import BotDetector
        ua = 'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/100.0.4896.58'
        score = BotDetector._score_user_agent(ua)
        self.assertEqual(score, 0.0)

    def test_fraud_result_structure(self):
        """FraudEvalResult must have all required fields."""
        from api.offer_inventory.fraud_detection import FraudEvalResult
        result = FraudEvalResult(score=50.0, blocked=False, action='flag')
        d = result.as_dict()
        for key in ['score', 'blocked', 'reason', 'signals', 'risk_level', 'action']:
            self.assertIn(key, d)


class SmartLinkScoringTests(TestCase):
    """Tests for SmartLink AI scoring logic."""

    def test_capped_offer_scores_zero(self):
        """Offer with availability=0 must score 0."""
        from unittest.mock import patch, MagicMock
        from api.offer_inventory.ai_optimization.smart_link_logic import OfferScorer

        mock_offer = MagicMock()
        mock_offer.id             = 'test-offer-id'
        mock_offer.conversion_rate = 5.0
        mock_offer.payout_amount  = Decimal('1.00')

        with patch.object(OfferScorer, '_get_epc', return_value=Decimal('0.5')):
            with patch.object(OfferScorer, '_get_availability', return_value=Decimal('0')):
                score = OfferScorer.compute_score(mock_offer)
                self.assertEqual(score, Decimal('0'))

    def test_higher_epc_scores_higher(self):
        """Offer with higher EPC should score higher."""
        from unittest.mock import patch, MagicMock
        from api.offer_inventory.ai_optimization.smart_link_logic import OfferScorer

        def make_offer(epc_val):
            m = MagicMock()
            m.id = 'test-id'
            m.conversion_rate = 5.0
            m.payout_amount   = Decimal('1.00')
            m.visibility_rules.filter.return_value = []
            return m

        offer_low  = make_offer(Decimal('0.1'))
        offer_high = make_offer(Decimal('1.0'))

        with patch.object(OfferScorer, '_get_availability', return_value=Decimal('1.0')):
            with patch.object(OfferScorer, '_get_geo_bonus', return_value=Decimal('1.0')):
                with patch.object(OfferScorer, '_get_loyalty_multiplier', return_value=Decimal('1.0')):
                    with patch.object(OfferScorer, '_get_epc') as mock_epc:
                        mock_epc.side_effect = lambda o: Decimal('0.1') if o is offer_low else Decimal('1.0')
                        score_low  = OfferScorer.compute_score(offer_low)
                        score_high = OfferScorer.compute_score(offer_high)
                        self.assertGreater(score_high, score_low)


class ValidatorTests(TestCase):
    """Tests for input validators."""

    def test_withdrawal_amount_min(self):
        """Amount below minimum raises ValidationError."""
        from api.offer_inventory.validators import validate_withdrawal_amount
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_withdrawal_amount(Decimal('10'))

    def test_withdrawal_amount_valid(self):
        """Valid amount passes without error."""
        from api.offer_inventory.validators import validate_withdrawal_amount
        result = validate_withdrawal_amount(Decimal('100'))
        self.assertEqual(result, Decimal('100'))

    def test_nid_valid_10_digit(self):
        """10-digit NID passes validation."""
        from api.offer_inventory.validators import validate_nid
        result = validate_nid('1234567890')
        self.assertEqual(result, '1234567890')

    def test_nid_invalid(self):
        """Invalid NID raises ValidationError."""
        from api.offer_inventory.validators import validate_nid
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_nid('123')

    def test_bd_phone_valid(self):
        """Valid BD phone number passes."""
        from api.offer_inventory.validators import validate_bd_phone
        result = validate_bd_phone('01712345678')
        self.assertIsNotNone(result)

    def test_bd_phone_invalid(self):
        """Invalid BD phone raises ValidationError."""
        from api.offer_inventory.validators import validate_bd_phone
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_bd_phone('12345')
