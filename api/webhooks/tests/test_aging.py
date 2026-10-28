# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Aging System Test Suite

Tests every public method of AgingService plus the aging API viewsets.

Coverage:
    AgingService.run_full_sweep()
    AgingService.evaluate_endpoint()
    AgingService.evaluate_delivery_log()
    AgingService.archive_due_records()
    AgingService.purge_due_records(dry_run=True/False)
    AgingService.get_aging_summary()
    WebhookEndpointAgingViewSet  (list, detail, evaluate action)
    WebhookDeliveryAgingViewSet  (list, detail, bucket filter)
    WebhookAgingEventViewSet     (list)
    WebhookAgingSummaryAPIView   (GET)
    WebhookAgingPolicyAPIView    (GET, PUT)
    WebhookAgingArchiveAPIView   (POST — staff)
    WebhookAgingPurgeAPIView     (POST — staff, dry_run)
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from ..models.aging import (
    AgeTier,
    AgingEventType,
    WebhookAgingEvent,
    WebhookAgingPolicy,
    WebhookDeliveryAging,
    WebhookEndpointAging,
)
from ..models.core import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from ..services.analytics.AgingService import AgingService

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS / FACTORIES
# ─────────────────────────────────────────────────────────────────────────────

def make_user(username="aging_user", email="aging@test.com", is_staff=False):
    return User.objects.create_user(
        username=username, email=email, password="testpass",
        is_staff=is_staff,
    )


def make_endpoint(owner, label="Test EP", days_inactive=0):
    last = timezone.now() - timedelta(days=days_inactive) if days_inactive else timezone.now()
    ep = WebhookEndpoint.objects.create(
        owner=owner,
        label=label,
        target_url="https://example.com/webhook",
        last_triggered_at=last if days_inactive else None,
    )
    return ep


def make_delivery_log(endpoint, days_old=0, event_type="payment.created"):
    from ..constants import DeliveryStatus
    created = timezone.now() - timedelta(days=days_old)
    log = WebhookDeliveryLog.objects.create(
        endpoint=endpoint,
        event_type=event_type,
        delivery_id=uuid.uuid4(),
        status=DeliveryStatus.SUCCESS,
        attempt_number=1,
        max_attempts=3,
    )
    # Manually backdate created_at for age tests
    WebhookDeliveryLog.objects.filter(pk=log.pk).update(created_at=created)
    log.refresh_from_db()
    return log


def make_policy(owner=None, **kwargs):
    defaults = dict(
        log_warm_after_days=7,
        log_cooling_after_days=30,
        log_stale_after_days=90,
        log_archive_after_days=180,
        log_purge_after_days=365,
        endpoint_warm_after_days=7,
        endpoint_cooling_after_days=30,
        endpoint_stale_after_days=90,
        endpoint_dormant_after_days=180,
    )
    defaults.update(kwargs)
    return WebhookAgingPolicy.objects.create(owner=owner, **defaults)


# ─────────────────────────────────────────────────────────────────────────────
#  MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingPolicyModelTest(TestCase):
    """Tests for WebhookAgingPolicy model."""

    def setUp(self):
        self.user   = make_user()
        self.policy = make_policy(owner=self.user)

    def test_global_policy_returned_when_no_user_policy(self):
        other_user = make_user("other", "other@test.com")
        global_pol = make_policy(owner=None)   # global
        result = WebhookAgingPolicy.get_for_owner(other_user)
        self.assertEqual(result.pk, global_pol.pk)

    def test_user_policy_takes_priority_over_global(self):
        make_policy(owner=None)                # global
        result = WebhookAgingPolicy.get_for_owner(self.user)
        self.assertEqual(result.pk, self.policy.pk)

    def test_str(self):
        self.assertIn(self.user.email, str(self.policy))

    def test_global_str(self):
        gp = make_policy(owner=None)
        self.assertIn("Global Default", str(gp))

    def test_clean_raises_on_invalid_threshold_order(self):
        from django.core.exceptions import ValidationError
        p = WebhookAgingPolicy(
            owner=None,
            log_warm_after_days=90,
            log_cooling_after_days=7,   # wrong: must be > warm
            log_stale_after_days=180,
            log_archive_after_days=365,
            log_purge_after_days=730,
        )
        with self.assertRaises(ValidationError):
            p.clean()


class WebhookEndpointAgingModelTest(TestCase):
    """Tests for WebhookEndpointAging model."""

    def setUp(self):
        self.user     = make_user()
        self.policy   = make_policy(owner=self.user)
        self.endpoint = make_endpoint(self.user, days_inactive=100)
        self.aging    = WebhookEndpointAging.objects.create(
            endpoint=self.endpoint,
            days_inactive=100,
            last_delivery_at=timezone.now() - timedelta(days=100),
        )

    def test_is_stale_true_for_stale_tier(self):
        self.aging.tier = AgeTier.STALE
        self.assertTrue(self.aging.is_stale)

    def test_is_stale_true_for_dormant_tier(self):
        self.aging.tier = AgeTier.DORMANT
        self.assertTrue(self.aging.is_stale)

    def test_is_stale_false_for_fresh(self):
        self.aging.tier = AgeTier.FRESH
        self.assertFalse(self.aging.is_stale)

    def test_compute_days_inactive(self):
        self.aging.last_delivery_at = timezone.now() - timedelta(days=45)
        days = self.aging.compute_days_inactive()
        self.assertAlmostEqual(days, 45, delta=1)

    def test_compute_tier_fresh(self):
        self.aging.days_inactive = 3
        self.assertEqual(self.aging.compute_tier(self.policy), AgeTier.FRESH)

    def test_compute_tier_warm(self):
        self.aging.days_inactive = 15
        self.assertEqual(self.aging.compute_tier(self.policy), AgeTier.WARM)

    def test_compute_tier_cooling(self):
        self.aging.days_inactive = 45
        self.assertEqual(self.aging.compute_tier(self.policy), AgeTier.COOLING)

    def test_compute_tier_stale(self):
        self.aging.days_inactive = 95
        self.assertEqual(self.aging.compute_tier(self.policy), AgeTier.STALE)

    def test_compute_tier_dormant(self):
        self.aging.days_inactive = 200
        self.assertEqual(self.aging.compute_tier(self.policy), AgeTier.DORMANT)

    def test_needs_purge_warning_when_within_window(self):
        self.aging.purge_after   = timezone.now() + timedelta(days=3)
        self.aging.purge_warned_at = None
        self.assertTrue(self.aging.needs_purge_warning)

    def test_needs_purge_warning_false_when_already_warned(self):
        self.aging.purge_after     = timezone.now() + timedelta(days=3)
        self.aging.purge_warned_at = timezone.now() - timedelta(hours=1)
        self.assertFalse(self.aging.needs_purge_warning)

    def test_str(self):
        self.aging.tier = AgeTier.STALE
        self.assertIn("STALE", str(self.aging))


# ─────────────────────────────────────────────────────────────────────────────
#  AGING SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class AgingServiceEvaluateEndpointTest(TestCase):
    """Tests for AgingService.evaluate_endpoint()."""

    def setUp(self):
        self.user     = make_user()
        self.policy   = make_policy(owner=self.user)
        self.svc      = AgingService()

    def test_fresh_endpoint_gets_fresh_tier(self):
        ep = make_endpoint(self.user, days_inactive=2)
        result = self.svc.evaluate_endpoint(ep)
        self.assertEqual(result["tier"], AgeTier.FRESH)

    def test_warm_endpoint(self):
        ep = make_endpoint(self.user, days_inactive=10)
        result = self.svc.evaluate_endpoint(ep)
        self.assertEqual(result["tier"], AgeTier.WARM)

    def test_cooling_endpoint(self):
        ep = make_endpoint(self.user, days_inactive=45)
        result = self.svc.evaluate_endpoint(ep)
        self.assertEqual(result["tier"], AgeTier.COOLING)

    def test_stale_endpoint(self):
        ep = make_endpoint(self.user, days_inactive=95)
        result = self.svc.evaluate_endpoint(ep)
        self.assertEqual(result["tier"], AgeTier.STALE)

    def test_dormant_endpoint(self):
        ep = make_endpoint(self.user, days_inactive=200)
        result = self.svc.evaluate_endpoint(ep)
        self.assertEqual(result["tier"], AgeTier.DORMANT)

    def test_tier_change_flag_set_on_first_evaluation(self):
        ep = make_endpoint(self.user, days_inactive=10)
        result = self.svc.evaluate_endpoint(ep)
        # Fresh → Warm is a change (default record starts as FRESH)
        self.assertTrue(result["tier_changed"])

    def test_no_tier_change_when_same_tier(self):
        ep    = make_endpoint(self.user, days_inactive=2)
        aging = WebhookEndpointAging.objects.create(
            endpoint=ep, tier=AgeTier.FRESH, days_inactive=2
        )
        result = self.svc.evaluate_endpoint(ep)
        self.assertFalse(result["tier_changed"])

    def test_aging_record_created_on_evaluate(self):
        ep = make_endpoint(self.user)
        self.assertFalse(WebhookEndpointAging.objects.filter(endpoint=ep).exists())
        self.svc.evaluate_endpoint(ep)
        self.assertTrue(WebhookEndpointAging.objects.filter(endpoint=ep).exists())

    def test_tier_change_creates_aging_event(self):
        ep = make_endpoint(self.user, days_inactive=10)
        self.svc.evaluate_endpoint(ep)
        self.assertTrue(
            WebhookAgingEvent.objects.filter(
                event_type=AgingEventType.TIER_CHANGE,
                endpoint_aging__endpoint=ep,
            ).exists()
        )

    def test_stale_notification_set_once(self):
        ep = make_endpoint(self.user, days_inactive=95)
        self.svc.evaluate_endpoint(ep)
        aging = WebhookEndpointAging.objects.get(endpoint=ep)
        self.assertIsNotNone(aging.stale_notified_at)
        # Second call should NOT update stale_notified_at
        first_notified = aging.stale_notified_at
        self.svc.evaluate_endpoint(ep)
        aging.refresh_from_db()
        self.assertEqual(aging.stale_notified_at, first_notified)

    def test_archive_after_scheduled(self):
        ep = make_endpoint(self.user)
        self.svc.evaluate_endpoint(ep)
        aging = WebhookEndpointAging.objects.get(endpoint=ep)
        self.assertIsNotNone(aging.archive_after)
        self.assertIsNotNone(aging.purge_after)
        self.assertGreater(aging.purge_after, aging.archive_after)

    def test_endpoint_archived_when_past_archive_after(self):
        ep    = make_endpoint(self.user, days_inactive=200)
        aging = WebhookEndpointAging.objects.create(
            endpoint=ep,
            tier=AgeTier.DORMANT,
            days_inactive=200,
            archive_after=timezone.now() - timedelta(hours=1),
        )
        result = self.svc.evaluate_endpoint(ep)
        self.assertTrue(result["archived"])
        aging.refresh_from_db()
        self.assertTrue(aging.is_archived)
        self.assertEqual(aging.tier, AgeTier.ARCHIVED)


class AgingServiceEvaluateDeliveryLogTest(TestCase):
    """Tests for AgingService.evaluate_delivery_log()."""

    def setUp(self):
        self.user   = make_user()
        self.policy = make_policy(owner=self.user)
        self.svc    = AgingService()
        self.ep     = make_endpoint(self.user)

    def test_fresh_log(self):
        log    = make_delivery_log(self.ep, days_old=2)
        result = self.svc.evaluate_delivery_log(log)
        self.assertEqual(result["bucket"], AgeTier.FRESH)

    def test_warm_log(self):
        log    = make_delivery_log(self.ep, days_old=15)
        result = self.svc.evaluate_delivery_log(log)
        self.assertEqual(result["bucket"], AgeTier.WARM)

    def test_cooling_log(self):
        log    = make_delivery_log(self.ep, days_old=45)
        result = self.svc.evaluate_delivery_log(log)
        self.assertEqual(result["bucket"], AgeTier.COOLING)

    def test_stale_log(self):
        log    = make_delivery_log(self.ep, days_old=100)
        result = self.svc.evaluate_delivery_log(log)
        self.assertEqual(result["bucket"], AgeTier.STALE)

    def test_archive_after_set_correctly(self):
        log = make_delivery_log(self.ep, days_old=5)
        self.svc.evaluate_delivery_log(log)
        aging = WebhookDeliveryAging.objects.get(delivery_log=log)
        expected = log.created_at + timedelta(days=self.policy.log_archive_after_days)
        self.assertAlmostEqual(
            aging.archive_after.timestamp(), expected.timestamp(), delta=5
        )

    def test_delivery_aging_record_created(self):
        log = make_delivery_log(self.ep)
        self.svc.evaluate_delivery_log(log)
        self.assertTrue(WebhookDeliveryAging.objects.filter(delivery_log=log).exists())

    def test_log_archived_when_past_archive_after(self):
        log   = make_delivery_log(self.ep, days_old=185)
        aging = WebhookDeliveryAging.objects.create(
            delivery_log=log,
            age_days=185,
            archive_after=timezone.now() - timedelta(hours=1),
        )
        result = self.svc.evaluate_delivery_log(log)
        self.assertTrue(result["archived"])
        aging.refresh_from_db()
        self.assertTrue(aging.is_archived)
        self.assertEqual(aging.bucket, AgeTier.ARCHIVED)


class AgingServiceSweepTest(TestCase):
    """Tests for AgingService.run_full_sweep(), archive, purge."""

    def setUp(self):
        self.user   = make_user()
        self.policy = make_policy(owner=self.user)
        self.svc    = AgingService()

    def test_run_full_sweep_returns_summary_keys(self):
        make_endpoint(self.user)
        result = self.svc.run_full_sweep()
        for key in [
            "swept_at",
            "endpoints_evaluated",
            "endpoints_tier_changed",
            "logs_evaluated",
        ]:
            self.assertIn(key, result)

    def test_run_full_sweep_evaluates_all_endpoints(self):
        make_endpoint(self.user, label="EP1")
        make_endpoint(self.user, label="EP2")
        result = self.svc.run_full_sweep()
        self.assertEqual(result["endpoints_evaluated"], 2)

    def test_archive_due_records_archives_endpoint_aging(self):
        ep    = make_endpoint(self.user)
        aging = WebhookEndpointAging.objects.create(
            endpoint=ep,
            archive_after=timezone.now() - timedelta(hours=1),
        )
        result = self.svc.archive_due_records()
        self.assertGreaterEqual(result["archived_endpoints"], 1)
        aging.refresh_from_db()
        self.assertTrue(aging.is_archived)

    def test_archive_due_records_archives_delivery_log_aging(self):
        ep    = make_endpoint(self.user)
        log   = make_delivery_log(ep)
        aging = WebhookDeliveryAging.objects.create(
            delivery_log=log,
            archive_after=timezone.now() - timedelta(hours=1),
        )
        result = self.svc.archive_due_records()
        self.assertGreaterEqual(result["archived_delivery_logs"], 1)
        aging.refresh_from_db()
        self.assertTrue(aging.is_archived)

    def test_purge_dry_run_returns_counts_without_deleting(self):
        ep    = make_endpoint(self.user)
        log   = make_delivery_log(ep)
        WebhookDeliveryAging.objects.create(
            delivery_log=log,
            purge_after=timezone.now() - timedelta(hours=1),
        )
        result = self.svc.purge_due_records(dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertGreaterEqual(result["delivery_logs_to_purge"], 1)
        # Log should NOT be deleted
        self.assertTrue(WebhookDeliveryLog.objects.filter(pk=log.pk).exists())

    def test_purge_execute_deletes_delivery_logs(self):
        ep    = make_endpoint(self.user)
        log   = make_delivery_log(ep)
        WebhookDeliveryAging.objects.create(
            delivery_log=log,
            purge_after=timezone.now() - timedelta(hours=1),
        )
        result = self.svc.purge_due_records(dry_run=False)
        self.assertFalse(result["dry_run"])
        self.assertGreaterEqual(result["delivery_logs_purged"], 1)
        self.assertFalse(WebhookDeliveryLog.objects.filter(pk=log.pk).exists())

    def test_get_aging_summary_structure(self):
        ep = make_endpoint(self.user)
        self.svc.evaluate_endpoint(ep)
        summary = self.svc.get_aging_summary(owner=self.user)
        self.assertIn("endpoints",     summary)
        self.assertIn("delivery_logs", summary)
        self.assertIn("total",    summary["endpoints"])
        self.assertIn("by_tier",  summary["endpoints"])
        self.assertIn("archived", summary["endpoints"])
        self.assertIn("purged",   summary["endpoints"])

    def test_get_aging_summary_scoped_to_owner(self):
        other = make_user("other2", "other2@test.com")
        make_policy(owner=other)
        ep1   = make_endpoint(self.user,  label="Mine")
        ep2   = make_endpoint(other,      label="Theirs")
        self.svc.run_full_sweep()
        summary = self.svc.get_aging_summary(owner=self.user)
        # Only our endpoint should appear
        self.assertEqual(summary["endpoints"]["total"], 1)


# ─────────────────────────────────────────────────────────────────────────────
#  API VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────

class AgingAPISetupMixin:
    """Shared setup for API tests."""

    def setUp(self):
        self.client   = APIClient()
        self.user     = make_user()
        self.staff    = make_user("staff", "staff@test.com", is_staff=True)
        self.policy   = make_policy(owner=self.user)
        self.endpoint = make_endpoint(self.user, days_inactive=10)
        self.client.force_authenticate(user=self.user)

        # Bootstrap aging record
        svc = AgingService()
        svc.evaluate_endpoint(self.endpoint)
        self.aging = WebhookEndpointAging.objects.get(endpoint=self.endpoint)


class WebhookEndpointAgingViewSetTest(AgingAPISetupMixin, TestCase):
    """Tests for WebhookEndpointAgingViewSet."""

    def test_list_returns_own_records(self):
        resp = self.client.get("/webhooks/aging/endpoints/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"] if "count" in resp.data else len(resp.data), 1)

    def test_detail_returns_aging_record(self):
        resp = self.client.get(f"/webhooks/aging/endpoints/{self.aging.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], str(self.aging.pk))

    def test_cannot_see_other_users_records(self):
        other       = make_user("other3", "other3@test.com")
        make_policy(owner=other)
        other_ep    = make_endpoint(other, label="Other")
        svc         = AgingService()
        svc.evaluate_endpoint(other_ep)
        other_aging = WebhookEndpointAging.objects.get(endpoint=other_ep)
        resp        = self.client.get(f"/webhooks/aging/endpoints/{other_aging.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_evaluate_action_re_evaluates_and_returns_result(self):
        resp = self.client.post(f"/webhooks/aging/endpoints/{self.aging.pk}/evaluate/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("result", resp.data)
        self.assertIn("aging", resp.data)

    def test_list_filtered_by_tier(self):
        resp = self.client.get("/webhooks/aging/endpoints/", {"tier": AgeTier.WARM})
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/webhooks/aging/endpoints/")
        self.assertEqual(resp.status_code, 401)


class WebhookDeliveryAgingViewSetTest(AgingAPISetupMixin, TestCase):
    """Tests for WebhookDeliveryAgingViewSet."""

    def setUp(self):
        super().setUp()
        self.log   = make_delivery_log(self.endpoint, days_old=15)
        svc        = AgingService()
        svc.evaluate_delivery_log(self.log)
        self.delivery_aging = WebhookDeliveryAging.objects.get(delivery_log=self.log)

    def test_list_delivery_aging(self):
        resp = self.client.get("/webhooks/aging/logs/")
        self.assertEqual(resp.status_code, 200)

    def test_detail_delivery_aging(self):
        resp = self.client.get(f"/webhooks/aging/logs/{self.delivery_aging.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], str(self.delivery_aging.pk))

    def test_bucket_filter(self):
        resp = self.client.get("/webhooks/aging/logs/", {"bucket": AgeTier.WARM})
        self.assertEqual(resp.status_code, 200)


class WebhookAgingSummaryViewTest(AgingAPISetupMixin, TestCase):
    """Tests for WebhookAgingSummaryAPIView."""

    def test_summary_returns_structure(self):
        resp = self.client.get("/webhooks/aging/summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("endpoints",     resp.data)
        self.assertIn("delivery_logs", resp.data)

    def test_summary_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/webhooks/aging/summary/")
        self.assertEqual(resp.status_code, 401)


class WebhookAgingPolicyViewTest(AgingAPISetupMixin, TestCase):
    """Tests for WebhookAgingPolicyAPIView."""

    def test_get_policy_returns_current(self):
        resp = self.client.get("/webhooks/aging/policy/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["log_warm_after_days"], 7)

    def test_put_policy_updates_thresholds(self):
        resp = self.client.put(
            "/webhooks/aging/policy/",
            {"log_warm_after_days": 14,
             "log_cooling_after_days": 45,
             "log_stale_after_days": 120,
             "log_archive_after_days": 240,
             "log_purge_after_days": 480},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.log_warm_after_days, 14)

    def test_put_policy_rejects_invalid_threshold_order(self):
        resp = self.client.put(
            "/webhooks/aging/policy/",
            {"log_warm_after_days": 90, "log_cooling_after_days": 7,
             "log_stale_after_days": 180, "log_archive_after_days": 365,
             "log_purge_after_days": 730},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


class WebhookAgingStaffActionsTest(AgingAPISetupMixin, TestCase):
    """Tests for archive and purge admin endpoints."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.staff)
        make_policy(owner=None)   # global policy for staff sweep

    def test_archive_endpoint_returns_200(self):
        resp = self.client.post("/webhooks/aging/archive/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("archived_endpoints", resp.data)

    def test_purge_dry_run_returns_counts(self):
        resp = self.client.post(
            "/webhooks/aging/purge/",
            {"confirm": True, "dry_run": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["dry_run"])

    def test_purge_requires_confirm_true(self):
        resp = self.client.post(
            "/webhooks/aging/purge/",
            {"confirm": False, "dry_run": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_archive_requires_staff(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post("/webhooks/aging/archive/")
        self.assertEqual(resp.status_code, 403)

    def test_purge_requires_staff(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            "/webhooks/aging/purge/",
            {"confirm": True, "dry_run": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
#  CELERY TASK TESTS
# ─────────────────────────────────────────────────────────────────────────────

class AgingCeleryTasksTest(TestCase):
    """Tests for aging Celery tasks."""

    def setUp(self):
        self.user   = make_user("task_user", "task@test.com")
        self.policy = make_policy(owner=self.user)
        self.ep     = make_endpoint(self.user)

    @patch("api.webhooks.tasks.aging_tasks.AgingService")
    def test_aging_full_sweep_calls_service(self, mock_cls):
        from ..tasks.aging_tasks import aging_full_sweep
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.run_full_sweep.return_value = {"endpoints_evaluated": 1}
        result = aging_full_sweep()
        mock_svc.run_full_sweep.assert_called_once()
        self.assertEqual(result["endpoints_evaluated"], 1)

    @patch("api.webhooks.tasks.aging_tasks.AgingService")
    def test_aging_archive_due_calls_service(self, mock_cls):
        from ..tasks.aging_tasks import aging_archive_due
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.archive_due_records.return_value = {"archived_endpoints": 0}
        result = aging_archive_due()
        mock_svc.archive_due_records.assert_called_once()

    @patch("api.webhooks.tasks.aging_tasks.AgingService")
    def test_aging_purge_dry_run_calls_dry_run(self, mock_cls):
        from ..tasks.aging_tasks import aging_purge_dry_run
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.purge_due_records.return_value = {"dry_run": True, "delivery_logs_to_purge": 0}
        aging_purge_dry_run()
        mock_svc.purge_due_records.assert_called_once_with(dry_run=True)

    @patch("api.webhooks.tasks.aging_tasks.AgingService")
    def test_aging_purge_execute_calls_with_dry_run_false(self, mock_cls):
        from ..tasks.aging_tasks import aging_purge_execute
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.purge_due_records.return_value = {"dry_run": False, "delivery_logs_purged": 0}
        aging_purge_execute()
        mock_svc.purge_due_records.assert_called_once_with(dry_run=False)

    def test_aging_evaluate_endpoint_task_not_found(self):
        from ..tasks.aging_tasks import aging_evaluate_endpoint
        result = aging_evaluate_endpoint(str(uuid.uuid4()))
        self.assertIn("error", result)

    @patch("api.webhooks.tasks.aging_tasks.AgingService")
    def test_aging_evaluate_endpoint_task_found(self, mock_cls):
        from ..tasks.aging_tasks import aging_evaluate_endpoint
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        mock_svc.evaluate_endpoint.return_value = {"tier": AgeTier.FRESH}
        result = aging_evaluate_endpoint(str(self.ep.pk))
        mock_svc.evaluate_endpoint.assert_called_once()
        self.assertEqual(result["tier"], AgeTier.FRESH)
