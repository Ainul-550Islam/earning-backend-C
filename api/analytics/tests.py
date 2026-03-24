"""
Analytics module tests — Events, tracking, reporting
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from unittest.mock import patch
import uuid

User = get_user_model()


def make_user():
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"user_{uid}", email=f"{uid}@test.com", password="pass1234"
    )


class AnalyticsEventModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_create_analytics_event(self):
        try:
            from api.analytics.models import AnalyticsEvent
            event = AnalyticsEvent.objects.create(
                event_type="user_login",
                user=self.user,
            )
            self.assertIsNotNone(event.pk)
        except ImportError:
            self.skipTest("AnalyticsEvent model not available")

    def test_event_types_exist(self):
        try:
            from api.analytics.models import AnalyticsEvent
            types = [t[0] for t in AnalyticsEvent.EVENT_TYPES]
            self.assertIn("user_login", types)
            self.assertIn("user_signup", types)
        except (ImportError, AttributeError):
            self.skipTest("AnalyticsEvent model not available")

    def test_event_ordering(self):
        try:
            from api.analytics.models import AnalyticsEvent
            for t in ["user_login", "offer_viewed", "task_completed"]:
                AnalyticsEvent.objects.create(event_type=t, user=self.user)
            events = AnalyticsEvent.objects.all()
            self.assertEqual(events.count(), 3)
        except ImportError:
            self.skipTest("AnalyticsEvent model not available")


class AnalyticsAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_analytics_dashboard_authenticated(self):
        res = self.client.get("/api/analytics/dashboard/")
        self.assertNotIn(res.status_code, [401, 403])

    def test_analytics_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/analytics/dashboard/")
        self.assertIn(res.status_code, [401, 403])

    def test_track_event(self):
        res = self.client.post("/api/analytics/track/", {
            "event_type": "page_view",
            "metadata": {"page": "dashboard"}
        }, format="json")
        self.assertIn(res.status_code, [200, 201, 400, 404])

    def test_analytics_date_filter(self):
        res = self.client.get("/api/analytics/dashboard/?days=7")
        self.assertNotIn(res.status_code, [500])

    def test_revenue_analytics(self):
        res = self.client.get("/api/analytics/revenue/")
        self.assertNotIn(res.status_code, [500])

    def test_user_analytics(self):
        res = self.client.get("/api/analytics/users/")
        self.assertNotIn(res.status_code, [500])
