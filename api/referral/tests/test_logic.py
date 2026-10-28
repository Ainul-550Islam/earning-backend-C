# api/referral/tests/test_logic.py
# Unit tests for pure logic functions — no DB, fast execution
# Run: python manage.py test api.referral.tests.test_logic
# ============================================================

from decimal import Decimal
from django.test import SimpleTestCase
from api.referral.logic import (
    calculate_commission,
    calculate_multilevel_commissions,
    calculate_signup_bonuses,
    calculate_fraud_score,
    determine_fraud_action,
    is_same_ip_fraud,
    is_suspicious_email,
    calculate_ltv,
    categorize_ltv_value,
    estimate_churn_risk,
    calculate_k_factor,
    should_hold_commission,
    get_attribution_source,
)


class TestCalculateCommission(SimpleTestCase):

    def test_basic_10_percent(self):
        result = calculate_commission(Decimal('100'), Decimal('10'))
        self.assertEqual(result, Decimal('10.0000'))

    def test_with_multiplier(self):
        result = calculate_commission(Decimal('100'), Decimal('10'), Decimal('2'))
        self.assertEqual(result, Decimal('20.0000'))

    def test_zero_amount_returns_zero(self):
        result = calculate_commission(Decimal('0'), Decimal('10'))
        self.assertEqual(result, Decimal('0'))

    def test_zero_rate_returns_zero(self):
        result = calculate_commission(Decimal('100'), Decimal('0'))
        self.assertEqual(result, Decimal('0'))

    def test_below_minimum_returns_zero(self):
        # 0.001% of 100 = 0.001, below default min 0.01
        result = calculate_commission(Decimal('100'), Decimal('0.001'))
        self.assertEqual(result, Decimal('0'))

    def test_negative_amount_returns_zero(self):
        result = calculate_commission(Decimal('-50'), Decimal('10'))
        self.assertEqual(result, Decimal('0'))

    def test_fractional_rate(self):
        result = calculate_commission(Decimal('200'), Decimal('5.5'))
        self.assertEqual(result, Decimal('11.0000'))


class TestCalculateMultilevelCommissions(SimpleTestCase):

    def test_three_levels(self):
        levels = [
            {'user_id': 1, 'level': 1, 'rate': Decimal('10')},
            {'user_id': 2, 'level': 2, 'rate': Decimal('5')},
            {'user_id': 3, 'level': 3, 'rate': Decimal('2')},
        ]
        results = calculate_multilevel_commissions(Decimal('100'), levels)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['commission'], Decimal('10.0000'))
        self.assertEqual(results[1]['commission'], Decimal('5.0000'))
        self.assertEqual(results[2]['commission'], Decimal('2.0000'))

    def test_with_multiplier(self):
        levels = [{'user_id': 1, 'level': 1, 'rate': Decimal('10')}]
        results = calculate_multilevel_commissions(
            Decimal('100'), levels, multiplier=Decimal('1.5')
        )
        self.assertEqual(results[0]['commission'], Decimal('15.0000'))

    def test_is_paid_flag(self):
        levels = [
            {'user_id': 1, 'level': 1, 'rate': Decimal('10')},
            {'user_id': 2, 'level': 2, 'rate': Decimal('0')},
        ]
        results = calculate_multilevel_commissions(Decimal('100'), levels)
        self.assertTrue(results[0]['is_paid'])
        self.assertFalse(results[1]['is_paid'])


class TestCalculateSignupBonuses(SimpleTestCase):

    def test_double_sided(self):
        result = calculate_signup_bonuses(Decimal('50'), Decimal('20'))
        self.assertEqual(result['referrer'], Decimal('50.00'))
        self.assertEqual(result['referred'], Decimal('20.00'))
        self.assertEqual(result['total'], Decimal('70.00'))

    def test_with_multiplier(self):
        result = calculate_signup_bonuses(
            Decimal('50'), Decimal('20'), multiplier=Decimal('2')
        )
        self.assertEqual(result['referrer'], Decimal('100.00'))
        self.assertEqual(result['referred'], Decimal('40.00'))


class TestFraudScoring(SimpleTestCase):

    def test_no_flags_zero_score(self):
        score = calculate_fraud_score(
            {'same_ip': False, 'vpn': False},
            {'same_ip': 30, 'vpn': 15}
        )
        self.assertEqual(score, 0)

    def test_single_flag(self):
        score = calculate_fraud_score(
            {'same_ip': True, 'vpn': False},
            {'same_ip': 30, 'vpn': 15}
        )
        self.assertEqual(score, 30)

    def test_multiple_flags(self):
        score = calculate_fraud_score(
            {'same_ip': True, 'vpn': True, 'same_device': True},
            {'same_ip': 30, 'vpn': 15, 'same_device': 25}
        )
        self.assertEqual(score, 70)

    def test_max_100(self):
        score = calculate_fraud_score(
            {'a': True, 'b': True, 'c': True},
            {'a': 50, 'b': 50, 'c': 50}
        )
        self.assertEqual(score, 100)  # Capped at 100

    def test_determine_action_block(self):
        self.assertEqual(determine_fraud_action(85), 'block')

    def test_determine_action_hold(self):
        self.assertEqual(determine_fraud_action(60), 'hold_commission')

    def test_determine_action_flag(self):
        self.assertEqual(determine_fraud_action(35), 'flag')

    def test_determine_action_allow(self):
        self.assertEqual(determine_fraud_action(10), 'allow')

    def test_same_ip_fraud(self):
        self.assertTrue(is_same_ip_fraud('192.168.1.1', '192.168.1.1'))
        self.assertFalse(is_same_ip_fraud('192.168.1.1', '192.168.1.2'))
        self.assertFalse(is_same_ip_fraud('', '192.168.1.1'))

    def test_suspicious_email(self):
        self.assertTrue(is_suspicious_email('user@mailinator.com'))
        self.assertTrue(is_suspicious_email('user+spam@gmail.com'))
        self.assertFalse(is_suspicious_email('user@gmail.com'))
        self.assertFalse(is_suspicious_email(''))


class TestLTVCalculations(SimpleTestCase):

    def test_basic_ltv(self):
        ltv = calculate_ltv(
            total_earnings=Decimal('500'),
            days_active=30,
            task_count=10,
            offer_count=5,
        )
        self.assertGreater(ltv, Decimal('500'))

    def test_zero_ltv(self):
        ltv = calculate_ltv(Decimal('0'), 0, 0, 0)
        self.assertEqual(ltv, Decimal('0'))

    def test_categorize_high_value(self):
        self.assertEqual(categorize_ltv_value(Decimal('2000')), 'high_value')

    def test_categorize_mid_value(self):
        self.assertEqual(categorize_ltv_value(Decimal('500')), 'mid_value')

    def test_categorize_low_value(self):
        self.assertEqual(categorize_ltv_value(Decimal('50')), 'low_value')

    def test_categorize_inactive(self):
        self.assertEqual(categorize_ltv_value(Decimal('0')), 'inactive')

    def test_churn_risk_low(self):
        self.assertEqual(estimate_churn_risk(3), 'low')

    def test_churn_risk_medium(self):
        self.assertEqual(estimate_churn_risk(20), 'medium')

    def test_churn_risk_high(self):
        self.assertEqual(estimate_churn_risk(60), 'high')

    def test_churn_risk_churned(self):
        self.assertEqual(estimate_churn_risk(120), 'churned')


class TestViralCoefficient(SimpleTestCase):

    def test_viral_k_factor(self):
        k = calculate_k_factor(
            total_invites_sent=200,
            total_users=100,
            total_conversions=100,
        )
        self.assertEqual(k, Decimal('1.0000'))

    def test_non_viral_k_factor(self):
        k = calculate_k_factor(
            total_invites_sent=100,
            total_users=100,
            total_conversions=10,
        )
        self.assertEqual(k, Decimal('0.1000'))

    def test_zero_users(self):
        k = calculate_k_factor(0, 0, 0)
        self.assertEqual(k, Decimal('0'))


class TestCommissionHold(SimpleTestCase):

    def test_new_user_hold(self):
        held, reason = should_hold_commission(
            is_new_user=True, user_age_days=3,
            fraud_score=0
        )
        self.assertTrue(held)
        self.assertIn('new_user', reason)

    def test_no_hold_old_user(self):
        held, reason = should_hold_commission(
            is_new_user=False, user_age_days=30,
            fraud_score=0
        )
        self.assertFalse(held)
        self.assertEqual(reason, '')

    def test_fraud_hold(self):
        held, reason = should_hold_commission(
            is_new_user=False, user_age_days=30,
            fraud_score=40
        )
        self.assertTrue(held)
        self.assertIn('fraud', reason)


class TestAttribution(SimpleTestCase):

    def test_url_param_wins_last_click(self):
        code = get_attribution_source(
            referral_code='NEW_CODE',
            cookie_code='OLD_CODE',
            last_click_wins=True,
        )
        self.assertEqual(code, 'NEW_CODE')

    def test_cookie_wins_first_click(self):
        code = get_attribution_source(
            referral_code='NEW_CODE',
            cookie_code='OLD_CODE',
            last_click_wins=False,
        )
        self.assertEqual(code, 'OLD_CODE')

    def test_no_code_returns_none(self):
        code = get_attribution_source()
        self.assertIsNone(code)