# api/tests/test_engagement.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class EngagementTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_daily_checkin(self):
        from api.engagement.models import DailyCheckIn
        from datetime import date
        checkin = DailyCheckIn.objects.create(
            user=self.user,
            date=date.today(),
            coins_earned=5,
            consecutive_days=1,
        )
        self.assertEqual(checkin.coins_earned, 5)

    def test_spin_wheel(self):
        from api.engagement.models import SpinWheel
        spin = SpinWheel.objects.create(
            user=self.user,
            coins_won=50,
        )
        self.assertEqual(spin.coins_won, 50)