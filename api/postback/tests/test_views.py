"""
test_views.py – Tests for PostbackDashboardView and PostbackRetryView.
"""
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    FailedPostbackLogFactory,
    RejectedPostbackLogFactory,
    RewardedPostbackLogFactory,
)
from api.postback.choices import PostbackStatus

User = get_user_model()


class PostbackDashboardViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="admin_dash", password="pass", email="dash@test.com"
        )
        self.client.force_login(self.admin)
        self.network = NetworkPostbackConfigFactory()

    def test_dashboard_requires_authentication(self):
        self.client.logout()
        resp = self.client.get("/api/postback/admin/dashboard/")
        self.assertIn(resp.status_code, [401, 403])

    def test_dashboard_requires_admin(self):
        regular = User.objects.create_user(
            username="regular_dash", password="pass", email="reg_dash@test.com"
        )
        self.client.force_login(regular)
        resp = self.client.get("/api/postback/admin/dashboard/")
        self.assertIn(resp.status_code, [401, 403])

    def test_dashboard_returns_200_for_admin(self):
        resp = self.client.get("/api/postback/admin/dashboard/")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_response_has_summary_key(self):
        resp = self.client.get("/api/postback/admin/dashboard/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("summary", data)

    def test_dashboard_response_has_period_hours(self):
        resp = self.client.get("/api/postback/admin/dashboard/")
        data = resp.json()
        self.assertEqual(data.get("period_hours"), 24)

    def test_dashboard_response_has_per_network(self):
        resp = self.client.get("/api/postback/admin/dashboard/")
        data = resp.json()
        self.assertIn("per_network", data)
        self.assertIsInstance(data["per_network"], list)

    def test_dashboard_response_has_active_networks(self):
        resp = self.client.get("/api/postback/admin/dashboard/")
        data = resp.json()
        self.assertIn("active_networks", data)

    def test_dashboard_summary_includes_counts(self):
        PostbackLogFactory(network=self.network, status=PostbackStatus.REWARDED)
        PostbackLogFactory(network=self.network, status=PostbackStatus.REJECTED)
        resp = self.client.get("/api/postback/admin/dashboard/")
        data = resp.json()
        summary = data["summary"]
        for key in ("total", "rewarded", "rejected"):
            self.assertIn(key, summary)

    def test_dashboard_summary_counts_are_non_negative(self):
        resp = self.client.get("/api/postback/admin/dashboard/")
        data = resp.json()
        summary = data["summary"]
        for key, val in summary.items():
            if isinstance(val, int):
                self.assertGreaterEqual(val, 0, f"{key} should be >= 0")

    def test_dashboard_method_not_allowed_for_post(self):
        resp = self.client.post("/api/postback/admin/dashboard/", data={})
        self.assertEqual(resp.status_code, 405)


class PostbackRetryViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="admin_retry", password="pass", email="retry@test.com"
        )
        self.client.force_login(self.admin)
        self.network = NetworkPostbackConfigFactory()

    def _retry_url(self, pk):
        return f"/api/postback/admin/logs/{pk}/retry/"

    def test_retry_requires_authentication(self):
        self.client.logout()
        log = FailedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        self.assertIn(resp.status_code, [401, 403])

    def test_retry_requires_admin(self):
        regular = User.objects.create_user(
            username="regular_retry", password="pass", email="reg_retry@test.com"
        )
        self.client.force_login(regular)
        log = FailedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        self.assertIn(resp.status_code, [401, 403])

    def test_retry_nonexistent_log_returns_404(self):
        import uuid
        resp = self.client.post(self._retry_url(uuid.uuid4()))
        self.assertEqual(resp.status_code, 404)

    @patch("api.postback.tasks.process_postback")
    def test_retry_failed_log_queues_task(self, mock_task):
        mock_task.delay = MagicMock()
        log = FailedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once()

    @patch("api.postback.tasks.process_postback")
    def test_retry_rejected_log_queues_task(self, mock_task):
        mock_task.delay = MagicMock()
        log = RejectedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once()

    @patch("api.postback.tasks.process_postback")
    def test_retry_rewarded_log_returns_400(self, mock_task):
        mock_task.delay = MagicMock()
        log = RewardedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        self.assertEqual(resp.status_code, 400)
        mock_task.delay.assert_not_called()

    @patch("api.postback.tasks.process_postback")
    def test_retry_response_body_has_status_queued(self, mock_task):
        mock_task.delay = MagicMock()
        log = FailedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        data = resp.json()
        self.assertEqual(data.get("status"), "queued")

    @patch("api.postback.tasks.process_postback")
    def test_retry_response_contains_log_id(self, mock_task):
        mock_task.delay = MagicMock()
        log = FailedPostbackLogFactory(network=self.network)
        resp = self.client.post(self._retry_url(log.pk))
        data = resp.json()
        self.assertIn("log_id", data)
        self.assertEqual(data["log_id"], str(log.pk))

    def test_retry_get_not_allowed(self):
        log = FailedPostbackLogFactory(network=self.network)
        resp = self.client.get(self._retry_url(log.pk))
        self.assertEqual(resp.status_code, 405)
