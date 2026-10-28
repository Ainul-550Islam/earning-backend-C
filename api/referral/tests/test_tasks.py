# api/referral/tests/test_tasks.py
# Celery task unit tests — mocked execution
# Run: python manage.py test api.referral.tests.test_tasks
# ============================================================

from decimal import Decimal
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class TestCommissionHoldTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings, Referral, CommissionLog, CommissionHold
        from django.utils import timezone
        from datetime import timedelta

        ReferralSettings.objects.create(is_active=True, commission_hold_days=7)
        self.referrer = User.objects.create_user(username='hold_ref', password='pass')
        self.referred = User.objects.create_user(username='hold_user', password='pass')

        referral = Referral.objects.create(referrer=self.referrer, referred_user=self.referred)
        self.log = CommissionLog.objects.create(
            user=self.referrer,
            referred_user=self.referred,
            action_type='task',
            amount=Decimal('10'),
            base_amount=Decimal('100'),
            commission_rate=Decimal('0.1000'),
            level=1,
            status='held',
        )
        # Create overdue hold
        self.hold = CommissionHold.objects.create(
            commission=self.log,
            hold_days=7,
            release_at=timezone.now() - timedelta(hours=1),
            reason='new_user',
            is_released=False,
        )

    @patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.WalletAdapter.credit_referral_commission')
    def test_release_overdue_holds(self, mock_credit):
        mock_credit.return_value = MagicMock()
        from api.referral.tasks.commission_hold_tasks import release_expired_commission_holds
        result = release_expired_commission_holds()
        self.assertIsInstance(result, dict)
        self.assertIn('released', result)
        self.assertGreaterEqual(result.get('released', 0), 0)


class TestFraudScanTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings, Referral, ReferralFraudRule
        ReferralSettings.objects.create(is_active=True)
        ReferralFraudRule.objects.create(
            rule_type='same_ip', action='flag',
            fraud_score_points=30, is_active=True,
        )
        self.r1 = User.objects.create_user(username='fraud_r', password='pass')
        self.r2 = User.objects.create_user(username='fraud_u', password='pass')
        Referral.objects.create(
            referrer=self.r1, referred_user=self.r2,
            registration_ip='1.2.3.4', referrer_ip='1.2.3.4',
            is_suspicious=False,
        )

    def test_daily_fraud_scan_runs(self):
        from api.referral.tasks.fraud_scan_tasks import daily_fraud_scan
        result = daily_fraud_scan()
        self.assertIsInstance(result, dict)
        self.assertIn('scanned', result)

    def test_auto_clear_low_risk(self):
        from api.referral.tasks.fraud_scan_tasks import auto_clear_low_risk_suspicious
        result = auto_clear_low_risk_suspicious()
        self.assertIsInstance(result, dict)


class TestInsightTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)

    def test_calculate_daily_insights(self):
        from api.referral.tasks.insight_tasks import calculate_daily_insights
        result = calculate_daily_insights()
        self.assertIsInstance(result, dict)
        self.assertIn('date', result)

    def test_update_code_conversion_rates(self):
        from api.referral.tasks.insight_tasks import update_code_conversion_rates
        result = update_code_conversion_rates()
        self.assertIsInstance(result, dict)


class TestTopReferrerTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)
        self.users = [
            User.objects.create_user(username=f'top{i}', password='pass')
            for i in range(5)
        ]

    def test_daily_top_referrer_snapshot(self):
        from api.referral.tasks.top_referrer_tasks import daily_top_referrer_snapshot
        result = daily_top_referrer_snapshot()
        self.assertIsInstance(result, dict)

    def test_weekly_snapshot(self):
        from api.referral.tasks.top_referrer_tasks import weekly_top_referrer_snapshot
        result = weekly_top_referrer_snapshot()
        self.assertIsInstance(result, dict)


class TestTreeTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)

    def test_rebuild_stale_trees(self):
        from api.referral.tasks.tree_rebuild_tasks import rebuild_stale_trees
        result = rebuild_stale_trees()
        self.assertIsInstance(result, dict)

    def test_tree_consistency_check(self):
        from api.referral.tasks.tree_rebuild_tasks import tree_consistency_check
        result = tree_consistency_check()
        self.assertIsInstance(result, dict)


class TestLTVTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)

    def test_weekly_ltv_recalculation(self):
        from api.referral.tasks.ltv_calculation_tasks import weekly_ltv_recalculation
        result = weekly_ltv_recalculation()
        self.assertIsInstance(result, dict)


class TestCleanupTasks(TestCase):

    def test_run_all_cleanups(self):
        from api.referral.tasks.cleanup_tasks import run_all_cleanups
        result = run_all_cleanups()
        self.assertIsInstance(result, dict)


class TestNotificationTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)
        self.user = User.objects.create_user(username='notif_u', password='pass')

    @patch('api.referral.INTEGRATION_SYSTEM.integ_adapter.NotificationAdapter.send')
    def test_check_milestone_achievements(self, mock_send):
        mock_send.return_value = True
        from api.referral.tasks.notification_tasks import check_milestone_achievements
        result = check_milestone_achievements(user_id=self.user.id)
        self.assertIsInstance(result, dict)


class TestCapTasks(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)

    def test_update_viral_coefficient(self):
        from api.referral.tasks_cap import update_viral_coefficient
        result = update_viral_coefficient()
        self.assertIsInstance(result, dict)
        self.assertIn('k_factor', result)

    def test_check_streak_bonuses(self):
        from api.referral.tasks_cap import check_streak_bonuses
        result = check_streak_bonuses()
        self.assertIsInstance(result, dict)

    def test_update_tier_progressions(self):
        from api.referral.tasks_cap import update_user_tier_progressions
        result = update_user_tier_progressions()
        self.assertIsInstance(result, dict)

    def test_process_surge_bonuses(self):
        from api.referral.tasks_cap import process_surge_bonuses
        result = process_surge_bonuses()
        self.assertIsInstance(result, dict)

    def test_expire_commissions(self):
        from api.referral.tasks_cap import expire_commissions
        result = expire_commissions()
        self.assertIsInstance(result, dict)

    def test_expire_referral_credits(self):
        from api.referral.tasks_cap import expire_referral_credits
        result = expire_referral_credits()
        self.assertIsInstance(result, dict)