# api/djoyalty/tests/test_integration.py
"""End-to-end integration tests।"""
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_txn, make_loyalty_points, make_tier


class FullLoyaltyJourneyTest(TestCase):
    """
    Complete customer loyalty journey:
    Register → Earn → Tier Upgrade → Redeem → Badge
    """

    def setUp(self):
        self.bronze = make_tier('bronze', min_points=Decimal('0'), rank=1)
        self.silver = make_tier('silver', min_points=Decimal('500'), rank=2)
        self.customer = make_customer(code='JRNCUST01', firstname='Journey', lastname='Test')

    def test_full_earn_journey(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import LoyaltyPoints

        # Step 1: Earn points
        PointsEngine.process_earn(self.customer, Decimal('200'))
        PointsEngine.process_earn(self.customer, Decimal('300'))

        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertGreater(lp.balance, 0)
        self.assertGreater(lp.lifetime_earned, 0)

    def test_earn_then_redeem_journey(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.models.points import LoyaltyPoints

        # Earn
        PointsEngine.process_earn(self.customer, Decimal('500'))
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        initial_balance = lp.balance

        # Redeem
        if initial_balance >= Decimal('100'):
            req = RedemptionService.create_request(self.customer, Decimal('100'), 'cashback')
            self.assertEqual(req.status, 'pending')
            lp.refresh_from_db()
            self.assertEqual(lp.balance, initial_balance - Decimal('100'))

    def test_bonus_then_transfer_journey(self):
        from djoyalty.services.earn.BonusEventService import BonusEventService
        from djoyalty.services.points.PointsTransferService import PointsTransferService
        from djoyalty.models.points import LoyaltyPoints

        receiver = make_customer(code='JRNRCV01')
        BonusEventService.award_bonus(self.customer, Decimal('300'), 'Integration test bonus')
        PointsTransferService.transfer(self.customer, receiver, Decimal('100'))

        sender_lp = LoyaltyPoints.objects.get(customer=self.customer)
        receiver_lp = LoyaltyPoints.objects.get(customer=receiver)

        self.assertEqual(sender_lp.balance, Decimal('200'))
        self.assertEqual(receiver_lp.balance, Decimal('100'))

    def test_streak_and_badge_journey(self):
        from djoyalty.services.engagement.StreakService import StreakService
        from djoyalty.services.engagement.BadgeService import BadgeService
        from djoyalty.models.engagement import Badge
        from django.utils import timezone
        from datetime import timedelta

        badge = Badge.objects.create(
            name='Week Warrior',
            icon='🔥',
            trigger='streak_days',
            threshold=Decimal('3'),
            points_reward=Decimal('50'),
            is_active=True,
            is_unique=True,
        )

        today = timezone.now()
        for i in range(3, 0, -1):
            StreakService.record_activity(self.customer, activity_date=today - timedelta(days=i))
        StreakService.record_activity(self.customer, activity_date=today)

        from djoyalty.models.engagement import DailyStreak
        streak = DailyStreak.objects.get(customer=self.customer)
        BadgeService.check_and_award(self.customer, 'streak_days', current_value=Decimal(streak.current_streak))
        # Journey completed successfully

    def test_voucher_generation_and_use_journey(self):
        from djoyalty.services.redemption.VoucherService import VoucherService

        voucher = VoucherService.generate_voucher(
            self.customer, 'percent', Decimal('15'),
        )
        self.assertEqual(voucher.status, 'active')

        redemption = VoucherService.use_voucher(voucher.code, self.customer, order_reference='ORDER-001')
        self.assertIsNotNone(redemption)

        voucher.refresh_from_db()
        self.assertEqual(voucher.status, 'used')
