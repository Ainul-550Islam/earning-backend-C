# api/djoyalty/tests/test_tasks.py
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_loyalty_points


class TasksTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='TSKCUST01')

    def test_expire_vouchers_task(self):
        from djoyalty.tasks.voucher_expiry_tasks import expire_vouchers_task
        from djoyalty.models.redemption import Voucher
        Voucher.objects.create(
            customer=self.customer,
            code='EXPVOUCHER01',
            voucher_type='percent',
            discount_value=Decimal('10'),
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
        )
        count = expire_vouchers_task()
        self.assertGreaterEqual(count, 1)
        v = Voucher.objects.get(code='EXPVOUCHER01')
        self.assertEqual(v.status, 'expired')

    def test_activate_due_campaigns_task(self):
        from djoyalty.tasks.campaign_tasks import activate_due_campaigns_task
        from djoyalty.models.campaigns import LoyaltyCampaign
        LoyaltyCampaign.objects.create(
            name='Due Campaign',
            campaign_type='bonus_points',
            status='draft',
            multiplier=Decimal('1'),
            bonus_points=Decimal('50'),
            start_date=timezone.now() - timedelta(hours=1),
        )
        result = activate_due_campaigns_task()
        self.assertGreaterEqual(result['activated'], 1)

    def test_expire_points_task(self):
        from djoyalty.tasks.points_expiry_tasks import expire_points_task
        from djoyalty.models.points import PointsExpiry
        lp = make_loyalty_points(self.customer, balance=Decimal('200'))
        PointsExpiry.objects.create(
            customer=self.customer,
            points=Decimal('50'),
            expires_at=timezone.now() - timedelta(hours=1),
            is_processed=False,
        )
        count = expire_points_task()
        self.assertGreaterEqual(count, 1)

    def test_evaluate_all_tiers_task(self):
        from djoyalty.tasks.tier_evaluation_tasks import evaluate_all_tiers_task
        count = evaluate_all_tiers_task()
        self.assertGreaterEqual(count, 0)

    def test_check_broken_streaks_task(self):
        from djoyalty.tasks.streak_reset_tasks import check_broken_streaks_task
        from djoyalty.models.engagement import DailyStreak
        DailyStreak.objects.create(
            customer=self.customer,
            current_streak=5,
            longest_streak=5,
            last_activity_date=(timezone.now() - timedelta(days=3)).date(),
            is_active=True,
        )
        count = check_broken_streaks_task()
        self.assertGreaterEqual(count, 1)

    def test_deactivate_expired_earn_rules_task(self):
        from djoyalty.tasks.earn_rule_tasks import deactivate_expired_earn_rules_task
        from djoyalty.models.earn_rules import EarnRule
        EarnRule.objects.create(
            name='Expired Rule',
            rule_type='fixed',
            trigger='purchase',
            points_value=Decimal('10'),
            multiplier=Decimal('1'),
            is_active=True,
            valid_until=timezone.now() - timedelta(days=1),
        )
        count = deactivate_expired_earn_rules_task()
        self.assertGreaterEqual(count, 1)
