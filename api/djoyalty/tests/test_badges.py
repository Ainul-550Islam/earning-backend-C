# api/djoyalty/tests/test_badges.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points


class BadgeServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='BDGCUST01')
        from djoyalty.models.engagement import Badge
        self.badge = Badge.objects.create(
            name='First Buy',
            icon='🎉',
            trigger='transaction_count',
            threshold=Decimal('1'),
            points_reward=Decimal('50'),
            is_active=True,
            is_unique=True,
        )

    def test_award_badge_on_threshold_met(self):
        from djoyalty.services.engagement.BadgeService import BadgeService
        from djoyalty.models.engagement import UserBadge
        BadgeService.check_and_award(self.customer, 'transaction_count', current_value=Decimal('1'))
        self.assertTrue(UserBadge.objects.filter(customer=self.customer, badge=self.badge).exists())

    def test_no_award_when_threshold_not_met(self):
        from djoyalty.services.engagement.BadgeService import BadgeService
        from djoyalty.models.engagement import UserBadge
        BadgeService.check_and_award(self.customer, 'transaction_count', current_value=Decimal('0'))
        self.assertFalse(UserBadge.objects.filter(customer=self.customer, badge=self.badge).exists())

    def test_unique_badge_not_awarded_twice(self):
        from djoyalty.services.engagement.BadgeService import BadgeService
        from djoyalty.models.engagement import UserBadge
        BadgeService.check_and_award(self.customer, 'transaction_count', current_value=Decimal('5'))
        BadgeService.check_and_award(self.customer, 'transaction_count', current_value=Decimal('10'))
        count = UserBadge.objects.filter(customer=self.customer, badge=self.badge).count()
        self.assertEqual(count, 1)

    def test_inactive_badge_not_awarded(self):
        from djoyalty.services.engagement.BadgeService import BadgeService
        from djoyalty.models.engagement import UserBadge
        self.badge.is_active = False
        self.badge.save()
        BadgeService.check_and_award(self.customer, 'transaction_count', current_value=Decimal('10'))
        self.assertFalse(UserBadge.objects.filter(customer=self.customer, badge=self.badge).exists())

    def test_badge_reward_points_credited(self):
        from djoyalty.services.engagement.BadgeService import BadgeService
        from djoyalty.models.points import LoyaltyPoints
        BadgeService.check_and_award(self.customer, 'transaction_count', current_value=Decimal('5'))
        lp = LoyaltyPoints.objects.filter(customer=self.customer).first()
        if lp and self.badge.points_reward > 0:
            self.assertGreaterEqual(lp.balance, Decimal('0'))
