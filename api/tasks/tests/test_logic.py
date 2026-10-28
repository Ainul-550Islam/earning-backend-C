"""api/tasks/tests/test_logic.py — Business logic unit tests."""
import pytest
from decimal import Decimal
from api.tasks.logic import (
    calculate_publisher_share, calculate_xp_for_action,
    calculate_level_for_xp, calculate_streak_bonus,
    calculate_milestone_bonus, compute_fraud_score,
    is_completion_suspicious, compute_offer_quality_score,
    rank_offers, run_second_price_auction, check_payout_eligibility,
    calculate_publisher_tier, get_traffic_tier_from_score,
)


class TestPublisherShare:
    def test_bronze_default(self):
        r = calculate_publisher_share(Decimal('1.00'), 'bronze')
        assert r['publisher'] == Decimal('0.70')
        assert r['platform']  == Decimal('0.30')

    def test_platinum_rate(self):
        r = calculate_publisher_share(Decimal('1.00'), 'platinum')
        assert r['publisher'] >= Decimal('0.85')

    def test_tier1_traffic_bonus(self):
        r_t1 = calculate_publisher_share(Decimal('1.00'), 'bronze', 'tier_1')
        r_t3 = calculate_publisher_share(Decimal('1.00'), 'bronze', 'tier_3')
        assert r_t1['publisher'] > r_t3['publisher']

    def test_vip_bonus(self):
        r_vip    = calculate_publisher_share(Decimal('1.00'), 'bronze', is_vip=True)
        r_normal = calculate_publisher_share(Decimal('1.00'), 'bronze', is_vip=False)
        assert r_vip['publisher'] > r_normal['publisher']

    def test_max_cap_90pct(self):
        r = calculate_publisher_share(Decimal('1.00'), 'platinum',
                                      'tier_1', is_vip=True)
        assert r['publisher'] <= Decimal('0.90')

    def test_gross_unchanged(self):
        gross = Decimal('5.50')
        r = calculate_publisher_share(gross)
        assert r['publisher'] + r['platform'] == gross


class TestXPCalculation:
    def test_task_completion_base(self):
        xp = calculate_xp_for_action('task_completion')
        assert xp == 5

    def test_survey_higher_than_task(self):
        assert calculate_xp_for_action('survey') > calculate_xp_for_action('task_completion')

    def test_streak_multiplier(self):
        xp_no_streak  = calculate_xp_for_action('task_completion', streak=0)
        xp_30d_streak = calculate_xp_for_action('task_completion', streak=30)
        assert xp_30d_streak > xp_no_streak

    def test_vip_bonus(self):
        xp_normal = calculate_xp_for_action('task_completion', is_vip=False)
        xp_vip    = calculate_xp_for_action('task_completion', is_vip=True)
        assert xp_vip > xp_normal

    def test_minimum_xp_is_1(self):
        xp = calculate_xp_for_action('unknown_action')
        assert xp >= 1


class TestLevelCalculation:
    def test_level_1_at_zero_xp(self):
        level, _, _ = calculate_level_for_xp(0)
        assert level == 1

    def test_level_2_at_100_xp(self):
        level, _, _ = calculate_level_for_xp(100)
        assert level == 2

    def test_level_3_at_250_xp(self):
        level, _, _ = calculate_level_for_xp(250)
        assert level == 3

    def test_xp_within_level_non_negative(self):
        for xp in [0, 100, 500, 1000, 5000]:
            _, xp_in, xp_next = calculate_level_for_xp(xp)
            assert xp_in >= 0
            assert xp_next > 0


class TestStreakBonus:
    def test_no_milestone(self):
        r = calculate_streak_bonus(1)
        assert r['is_milestone'] is False
        assert r['xp_bonus'] == 5

    def test_7d_milestone(self):
        r = calculate_streak_bonus(7)
        assert r['is_milestone'] is True
        assert r['xp_bonus'] == 70

    def test_30d_milestone(self):
        r = calculate_streak_bonus(30)
        assert r['xp_bonus'] == 300
        assert r['multiplier'] >= 1.5

    def test_streak_multiplier_increases(self):
        r_low  = calculate_streak_bonus(1)
        r_high = calculate_streak_bonus(30)
        assert r_high['multiplier'] > r_low['multiplier']


class TestFraudScore:
    def test_clean_user_low_score(self):
        score, level = compute_fraud_score(
            velocity_1h=2, ip_diversity=5, account_age_hours=720,
            new_account=False, ip_blocked=False
        )
        assert score <= 20
        assert level in ('clean', 'low')

    def test_ip_blocked_max(self):
        score, level = compute_fraud_score(ip_blocked=True)
        assert score == 100
        assert level == 'critical'

    def test_new_account_raises_score(self):
        score_old, _ = compute_fraud_score(account_age_hours=5000, velocity_1h=1)
        score_new, _ = compute_fraud_score(account_age_hours=1, velocity_1h=1, new_account=True)
        assert score_new > score_old

    def test_high_velocity_raises_score(self):
        score_low, _  = compute_fraud_score(velocity_1h=5)
        score_high, _ = compute_fraud_score(velocity_1h=200)
        assert score_high > score_low


class TestRTBAuction:
    def test_empty_bids_returns_empty(self):
        result = run_second_price_auction([], Decimal('0.01'))
        assert result == []

    def test_all_below_floor_returns_empty(self):
        bids = [{'campaign_id': 1, 'bid_price': '0.001', 'quality_score': 50}]
        result = run_second_price_auction(bids, Decimal('0.05'))
        assert result == []

    def test_single_winner(self):
        bids   = [{'campaign_id': 1, 'bid_price': '0.10', 'quality_score': 50}]
        result = run_second_price_auction(bids, Decimal('0.01'))
        assert len(result) == 1

    def test_second_price_applied(self):
        bids = [
            {'campaign_id': 1, 'bid_price': '0.10', 'quality_score': 50},
            {'campaign_id': 2, 'bid_price': '0.08', 'quality_score': 50},
        ]
        result = run_second_price_auction(bids, Decimal('0.01'), num_winners=2)
        # Winner 1 should pay second price (0.08 + 0.001)
        winner1_price = Decimal(result[0]['clearing_price'])
        assert winner1_price <= Decimal('0.10')

    def test_max_winners_respected(self):
        bids = [
            {'campaign_id': i, 'bid_price': f'0.0{i+1}', 'quality_score': 50}
            for i in range(10)
        ]
        result = run_second_price_auction(bids, Decimal('0.001'), num_winners=3)
        assert len(result) <= 3


class TestPayoutEligibility:
    def test_eligible_user(self):
        ok, reasons = check_payout_eligibility(
            wallet_balance=Decimal('5.00'),
            payment_method='paypal',
            fraud_score=0,
            kyc_tier='basic',
            is_suspended=False,
            payout_method_valid=True,
            already_paid_today=False,
        )
        assert ok is True
        assert reasons == []

    def test_suspended_not_eligible(self):
        ok, reasons = check_payout_eligibility(
            wallet_balance=Decimal('10.00'), payment_method='paypal',
            is_suspended=True, payout_method_valid=True
        )
        assert ok is False
        assert 'account_suspended' in reasons

    def test_below_minimum_not_eligible(self):
        ok, reasons = check_payout_eligibility(
            wallet_balance=Decimal('0.50'),
            payment_method='paypal',   # minimum $1.00
        )
        assert ok is False
        assert any('balance_below_minimum' in r for r in reasons)

    def test_high_fraud_blocks_payout(self):
        ok, reasons = check_payout_eligibility(
            wallet_balance=Decimal('100'),
            payment_method='paypal',
            fraud_score=75,
        )
        assert ok is False
        assert any('fraud' in r for r in reasons)

    def test_already_paid_today_blocks(self):
        ok, reasons = check_payout_eligibility(
            wallet_balance=Decimal('10'),
            payment_method='paypal',
            already_paid_today=True,
        )
        assert ok is False
        assert 'already_paid_today' in reasons


class TestPublisherTier:
    def test_bronze_low_earnings(self):
        assert calculate_publisher_tier(Decimal('50')) == 'bronze'

    def test_silver_at_100(self):
        assert calculate_publisher_tier(Decimal('100')) == 'silver'

    def test_gold_at_500(self):
        assert calculate_publisher_tier(Decimal('500')) == 'gold'

    def test_platinum_at_1000(self):
        assert calculate_publisher_tier(Decimal('1000')) == 'platinum'


class TestTrafficTier:
    def test_tier_1_high_score(self):
        assert get_traffic_tier_from_score(85) == 'tier_1'

    def test_tier_2_mid_score(self):
        assert get_traffic_tier_from_score(65) == 'tier_2'

    def test_tier_3_low_score(self):
        assert get_traffic_tier_from_score(35) == 'tier_3'

    def test_low_quality(self):
        assert get_traffic_tier_from_score(5) == 'low_quality'
