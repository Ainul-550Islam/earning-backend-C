# api/tests/test_analytics.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class AnalyticsTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_analytics_event_page_view(self):
        from api.analytics.models import AnalyticsEvent
        event = AnalyticsEvent.objects.create(
            user=self.user,
            event_type='page_view',
            metadata={'page': 'home'},
        )
        self.assertEqual(event.event_type, 'page_view')

    def test_user_analytics(self):
        from api.analytics.models import UserAnalytics
        now = timezone.now()
        ua = UserAnalytics.objects.create(
            user=self.user,
            period='daily',
            period_start=now,
            period_end=now,
            login_count=5,
        )
        self.assertEqual(ua.login_count, 5)

    def test_revenue_analytics(self):
        from api.analytics.models import RevenueAnalytics
        now = timezone.now()
        ra = RevenueAnalytics.objects.create(
            period='monthly',
            period_start=now,
            period_end=now,
            revenue_total=5000.00,
            cost_total=1000.00,
        )
        self.assertEqual(ra.revenue_total, 5000.00)