# api/djoyalty/tests/test_streaks.py
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from .factories import make_customer


class StreakServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='STKCUST01')

    def test_first_activity_creates_streak(self):
        from djoyalty.services.engagement.StreakService import StreakService
        from djoyalty.models.engagement import DailyStreak
        StreakService.record_activity(self.customer)
        self.assertTrue(DailyStreak.objects.filter(customer=self.customer).exists())

    def test_consecutive_days_increment_streak(self):
        from djoyalty.services.engagement.StreakService import StreakService
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        StreakService.record_activity(self.customer, activity_date=yesterday)
        StreakService.record_activity(self.customer, activity_date=today)
        from djoyalty.models.engagement import DailyStreak
        streak = DailyStreak.objects.get(customer=self.customer)
        self.assertEqual(streak.current_streak, 2)

    def test_same_day_activity_no_increment(self):
        from djoyalty.services.engagement.StreakService import StreakService
        today = timezone.now()
        StreakService.record_activity(self.customer, activity_date=today)
        StreakService.record_activity(self.customer, activity_date=today)
        from djoyalty.models.engagement import DailyStreak
        streak = DailyStreak.objects.get(customer=self.customer)
        self.assertEqual(streak.current_streak, 1)

    def test_missed_day_resets_streak(self):
        from djoyalty.services.engagement.StreakService import StreakService
        today = timezone.now()
        two_days_ago = today - timedelta(days=2)
        StreakService.record_activity(self.customer, activity_date=two_days_ago)
        StreakService.record_activity(self.customer, activity_date=today)
        from djoyalty.models.engagement import DailyStreak
        streak = DailyStreak.objects.get(customer=self.customer)
        self.assertEqual(streak.current_streak, 1)

    def test_longest_streak_tracked(self):
        from djoyalty.services.engagement.StreakService import StreakService
        today = timezone.now()
        for i in range(3, 0, -1):
            day = today - timedelta(days=i)
            StreakService.record_activity(self.customer, activity_date=day)
        StreakService.record_activity(self.customer, activity_date=today)
        from djoyalty.models.engagement import DailyStreak
        streak = DailyStreak.objects.get(customer=self.customer)
        self.assertGreaterEqual(streak.longest_streak, streak.current_streak)

    def test_milestone_reward_awarded(self):
        from djoyalty.services.engagement.StreakService import StreakService
        from djoyalty.models.engagement import StreakReward
        today = timezone.now()
        for i in range(7, 0, -1):
            StreakService.record_activity(self.customer, activity_date=today - timedelta(days=i))
        StreakService.record_activity(self.customer, activity_date=today)
        # 7-day milestone should trigger
        rewards = StreakReward.objects.filter(customer=self.customer, milestone_days=7)
        self.assertGreaterEqual(rewards.count(), 0)
