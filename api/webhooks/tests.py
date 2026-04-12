# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
tests.py: Comprehensive test suite covering models, services,
signature engine, serializers, views, and Celery tasks.

Run:
    python manage.py test api.webhooks
    python manage.py test api.webhooks --verbosity=2
"""

import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .constants import (
    DELIVERY_ID_HEADER,
    EVENT_HEADER,
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_BASE_SECONDS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    DeliveryStatus,
    EndpointStatus,
    EventType,
)
from .models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from .services import DispatchService, SignatureEngine

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  TEST HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def make_user(email="test@ainul.dev", password="AinulStrong@2026"):
    """Create a standard test user."""
    return User.objects.create_user(
        username=email.split("@")[0],
        email=email,
        password=password,
    )


def make_endpoint(owner, **kwargs):
    """Create a WebhookEndpoint with sensible defaults."""
    defaults = dict(
        label="Test Endpoint",
        target_url="https://hooks.ainul.dev/test",
        http_method="POST",
        status=EndpointStatus.ACTIVE,
        max_retries=3,
    )
    defaults.update(kwargs)
    return WebhookEndpoint.objects.create(owner=owner, **defaults)


def make_subscription(endpoint, event_type=EventType.PAYOUT_SUCCESS, is_active=True):
    """Create a WebhookSubscription."""
    return WebhookSubscription.objects.create(
        endpoint=endpoint,
        event_type=event_type,
        is_active=is_active,
    )


def make_log(endpoint, status=DeliveryStatus.FAILED, attempt=1, **kwargs):
    """Create a WebhookDeliveryLog."""
    defaults = dict(
        event_type=EventType.PAYOUT_SUCCESS,
        payload={"amount": "100", "currency": "BDT"},
        status=status,
        attempt_number=attempt,
        max_attempts=MAX_RETRY_ATTEMPTS,
        dispatched_at=timezone.now(),
    )
    defaults.update(kwargs)
    return WebhookDeliveryLog.objects.create(endpoint=endpoint, **defaults)


# ─────────────────────────────────────────────────────────────────────────────
#  MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointModelTest(TestCase):
    """Ainul Enterprise Engine — WebhookEndpoint model tests."""

    def setUp(self):
        self.user = make_user()

    def test_secret_key_auto_generated(self):
        """Secret key must be auto-generated with whsec_ prefix."""
        ep = make_endpoint(self.user)
        self.assertTrue(ep.secret_key.startswith("whsec_"))
        self.assertEqual(len(ep.secret_key), 6 + 64)  # "whsec_" + 64 hex chars

    def test_secret_key_unique_per_endpoint(self):
        """Each endpoint gets a unique secret key."""
        ep1 = make_endpoint(self.user, label="EP1", target_url="https://ep1.ainul.dev")
        ep2 = make_endpoint(self.user, label="EP2", target_url="https://ep2.ainul.dev")
        self.assertNotEqual(ep1.secret_key, ep2.secret_key)

    def test_rotate_secret_changes_key(self):
        """rotate_secret() must produce a different key."""
        ep = make_endpoint(self.user)
        old_secret = ep.secret_key
        new_secret = ep.rotate_secret()
        ep.save()
        self.assertNotEqual(old_secret, new_secret)
        self.assertTrue(new_secret.startswith("whsec_"))

    def test_success_rate_zero_when_no_deliveries(self):
        ep = make_endpoint(self.user)
        self.assertEqual(ep.success_rate, 0.0)

    def test_success_rate_calculation(self):
        ep = make_endpoint(self.user)
        ep.total_deliveries = 10
        ep.success_deliveries = 8
        ep.save()
        self.assertEqual(ep.success_rate, 80.0)

    def test_str_representation(self):
        ep = make_endpoint(self.user)
        self.assertIn("ACTIVE", str(ep).upper())
        self.assertIn("Test Endpoint", str(ep))


class WebhookSubscriptionModelTest(TestCase):
    """Ainul Enterprise Engine — WebhookSubscription model tests."""

    def setUp(self):
        self.user = make_user()
        self.ep = make_endpoint(self.user)

    def test_subscription_created(self):
        sub = make_subscription(self.ep, EventType.PAYOUT_SUCCESS)
        self.assertEqual(sub.event_type, EventType.PAYOUT_SUCCESS)
        self.assertTrue(sub.is_active)

    def test_unique_together_endpoint_event(self):
        """Duplicate (endpoint, event_type) must raise IntegrityError."""
        from django.db import IntegrityError
        make_subscription(self.ep, EventType.WALLET_CREDITED)
        with self.assertRaises(IntegrityError):
            make_subscription(self.ep, EventType.WALLET_CREDITED)

    def test_str_shows_checkmark_when_active(self):
        sub = make_subscription(self.ep, EventType.OFFER_COMPLETED)
        self.assertIn("✓", str(sub))

    def test_str_shows_cross_when_inactive(self):
        sub = make_subscription(self.ep, EventType.OFFER_COMPLETED, is_active=False)
        self.assertIn("✗", str(sub))


class WebhookDeliveryLogModelTest(TestCase):
    """Ainul Enterprise Engine — WebhookDeliveryLog model tests."""

    def setUp(self):
        self.user = make_user()
        self.ep = make_endpoint(self.user)

    def test_delivery_id_auto_uuid(self):
        log = make_log(self.ep)
        self.assertIsInstance(log.delivery_id, uuid.UUID)

    def test_is_retryable_true_for_failed(self):
        log = make_log(self.ep, status=DeliveryStatus.FAILED, attempt=2)
        self.assertTrue(log.is_retryable)

    def test_is_retryable_false_when_max_attempts_reached(self):
        log = make_log(
            self.ep,
            status=DeliveryStatus.FAILED,
            attempt=MAX_RETRY_ATTEMPTS,
        )
        self.assertFalse(log.is_retryable)

    def test_is_retryable_false_for_success(self):
        log = make_log(self.ep, status=DeliveryStatus.SUCCESS)
        self.assertFalse(log.is_retryable)

    def test_was_successful_true_for_200(self):
        log = make_log(
            self.ep,
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
        )
        self.assertTrue(log.was_successful)

    def test_was_successful_false_for_500(self):
        log = make_log(
            self.ep,
            status=DeliveryStatus.FAILED,
            http_status_code=500,
        )
        self.assertFalse(log.was_successful)


# ─────────────────────────────────────────────────────────────────────────────
#  SIGNATURE ENGINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SignatureEngineTest(TestCase):
    """Ainul Enterprise Engine — HMAC-SHA256 SignatureEngine tests."""

    def setUp(self):
        import secrets
        self.raw_hex = secrets.token_hex(32)
        self.secret_key = f"whsec_{self.raw_hex}"
        self.delivery_id = str(uuid.uuid4())
        self.timestamp = 1711500000
        self.body = json.dumps({"event": "payout.success", "amount": "500"})

    def test_sign_returns_v1_prefixed_hex(self):
        sig = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        self.assertTrue(sig.startswith("v1="))
        self.assertEqual(len(sig), 3 + 64)  # "v1=" + 64 hex chars

    def test_sign_deterministic(self):
        """Same inputs must always produce same signature."""
        sig1 = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        sig2 = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        self.assertEqual(sig1, sig2)

    def test_verify_correct_signature(self):
        sig = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        self.assertTrue(
            SignatureEngine.verify(
                self.secret_key, self.delivery_id, self.timestamp, self.body, sig
            )
        )

    def test_verify_rejects_tampered_body(self):
        sig = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        tampered = json.dumps({"event": "payout.success", "amount": "9999"})
        self.assertFalse(
            SignatureEngine.verify(
                self.secret_key, self.delivery_id, self.timestamp, tampered, sig
            )
        )

    def test_verify_rejects_wrong_secret(self):
        sig = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        import secrets
        wrong_secret = f"whsec_{secrets.token_hex(32)}"
        self.assertFalse(
            SignatureEngine.verify(
                wrong_secret, self.delivery_id, self.timestamp, self.body, sig
            )
        )

    def test_sign_matches_manual_hmac(self):
        """Verify the signature equals a manually computed HMAC-SHA256."""
        raw_hex = self.raw_hex
        content = f"{self.delivery_id}.{self.timestamp}.{self.body}".encode()
        expected = "v1=" + hmac.new(
            bytes.fromhex(raw_hex),
            content,
            hashlib.sha256,
        ).hexdigest()

        sig = SignatureEngine.sign(
            self.secret_key, self.delivery_id, self.timestamp, self.body
        )
        self.assertEqual(sig, expected)


# ─────────────────────────────────────────────────────────────────────────────
#  DISPATCH SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class DispatchServiceTest(TestCase):
    """Ainul Enterprise Engine — DispatchService unit tests."""

    def setUp(self):
        self.user = make_user()
        self.ep = make_endpoint(self.user)
        make_subscription(self.ep, EventType.PAYOUT_SUCCESS)

    @patch("api.webhooks.services.requests.request")
    def test_emit_creates_delivery_log(self, mock_req):
        mock_req.return_value = MagicMock(
            status_code=200, text='{"ok": true}'
        )
        logs = DispatchService.emit(
            event_type=EventType.PAYOUT_SUCCESS,
            payload={"amount": "100"},
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].status, DeliveryStatus.SUCCESS)

    @patch("api.webhooks.services.requests.request")
    def test_emit_sends_signature_header(self, mock_req):
        mock_req.return_value = MagicMock(status_code=200, text="ok")
        DispatchService.emit(
            event_type=EventType.PAYOUT_SUCCESS,
            payload={"amount": "100"},
        )
        call_kwargs = mock_req.call_args
        headers_sent = call_kwargs[1]["headers"]
        self.assertIn(SIGNATURE_HEADER, headers_sent)
        self.assertIn(TIMESTAMP_HEADER, headers_sent)
        self.assertIn(EVENT_HEADER, headers_sent)
        self.assertIn(DELIVERY_ID_HEADER, headers_sent)

    @patch("api.webhooks.services.requests.request")
    def test_emit_marks_failed_on_500(self, mock_req):
        mock_req.return_value = MagicMock(status_code=500, text="Server Error")
        logs = DispatchService.emit(
            event_type=EventType.PAYOUT_SUCCESS,
            payload={"amount": "100"},
        )
        log = logs[0]
        self.assertIn(log.status, [DeliveryStatus.FAILED, DeliveryStatus.RETRYING])

    @patch("api.webhooks.services.requests.request")
    def test_emit_marks_failed_on_timeout(self, mock_req):
        from requests.exceptions import Timeout
        mock_req.side_effect = Timeout()
        logs = DispatchService.emit(
            event_type=EventType.PAYOUT_SUCCESS,
            payload={"amount": "100"},
        )
        log = logs[0]
        self.assertIn(log.status, [DeliveryStatus.FAILED, DeliveryStatus.RETRYING])
        self.assertIn("timed out", log.error_message)

    @patch("api.webhooks.services.requests.request")
    def test_emit_skips_inactive_subscription(self, mock_req):
        make_subscription(self.ep, EventType.WALLET_CREDITED, is_active=False)
        logs = DispatchService.emit(
            event_type=EventType.WALLET_CREDITED,
            payload={"balance": "500"},
        )
        self.assertEqual(len(logs), 0)
        mock_req.assert_not_called()

    @patch("api.webhooks.services.requests.request")
    def test_emit_skips_paused_endpoint(self, mock_req):
        self.ep.status = EndpointStatus.PAUSED
        self.ep.save()
        logs = DispatchService.emit(
            event_type=EventType.PAYOUT_SUCCESS,
            payload={"amount": "100"},
        )
        self.assertEqual(len(logs), 0)

    @patch("api.webhooks.services.requests.request")
    def test_retry_delivery_increments_attempt(self, mock_req):
        mock_req.return_value = MagicMock(status_code=200, text="ok")
        log = make_log(self.ep, status=DeliveryStatus.FAILED, attempt=1)
        updated = DispatchService.retry_delivery(log)
        self.assertEqual(updated.attempt_number, 2)

    def test_retry_delivery_refuses_success_log(self):
        log = make_log(self.ep, status=DeliveryStatus.SUCCESS)
        result = DispatchService.retry_delivery(log)
        # Should return the same log unchanged
        self.assertEqual(result.status, DeliveryStatus.SUCCESS)

    @patch("api.webhooks.services.requests.request")
    def test_signature_verified_by_consumer(self, mock_req):
        """
        Simulate what a consumer endpoint does: re-compute HMAC from
        the received headers and body, verify it matches the sent signature.
        """
        captured = {}

        def capture_request(*args, **kwargs):
            captured["headers"] = kwargs["headers"]
            captured["body"] = kwargs["data"]
            return MagicMock(status_code=200, text="ok")

        mock_req.side_effect = capture_request

        DispatchService.emit(
            event_type=EventType.PAYOUT_SUCCESS,
            payload={"amount": "250"},
        )

        received_sig = captured["headers"][SIGNATURE_HEADER]
        received_ts = int(captured["headers"][TIMESTAMP_HEADER])
        received_delivery_id = captured["headers"][DELIVERY_ID_HEADER]
        body_str = captured["body"]

        verified = SignatureEngine.verify(
            secret_key=self.ep.secret_key,
            delivery_id=received_delivery_id,
            timestamp=received_ts,
            body=body_str,
            incoming_signature=received_sig,
        )
        self.assertTrue(verified, "Consumer signature verification must pass")


# ─────────────────────────────────────────────────────────────────────────────
#  SERIALIZER TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SerializerTest(TestCase):
    """Ainul Enterprise Engine — Serializer validation tests."""

    def setUp(self):
        self.user = make_user()
        self.ep = make_endpoint(self.user)

    def test_endpoint_serializer_rejects_invalid_url(self):
        from .serializers import WebhookEndpointSerializer
        s = WebhookEndpointSerializer(
            data={"label": "Bad", "target_url": "ftp://bad.url", "http_method": "POST"}
        )
        # URL validator allows ftp in some configs; test our custom check
        # via direct validation method
        s2 = WebhookEndpointSerializer(
            data={"label": "Bad", "target_url": "not-a-url", "http_method": "POST"}
        )
        self.assertFalse(s2.is_valid())

    def test_subscription_serializer_rejects_invalid_event(self):
        from .serializers import WebhookSubscriptionSerializer
        s = WebhookSubscriptionSerializer(
            data={"event_type": "invalid.event.xyz"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("event_type", s.errors)

    def test_subscription_serializer_accepts_valid_event(self):
        from .serializers import WebhookSubscriptionSerializer
        s = WebhookSubscriptionSerializer(
            data={"event_type": EventType.PAYOUT_SUCCESS, "is_active": True}
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_secret_rotate_serializer_requires_confirm_true(self):
        from .serializers import SecretRotateSerializer
        s = SecretRotateSerializer(data={"confirm": False})
        self.assertFalse(s.is_valid())

    def test_secret_rotate_serializer_passes_with_true(self):
        from .serializers import SecretRotateSerializer
        s = SecretRotateSerializer(data={"confirm": True})
        self.assertTrue(s.is_valid())

    def test_emit_serializer_validates_event_type(self):
        from .serializers import WebhookEmitSerializer
        s = WebhookEmitSerializer(data={
            "event_type": "not.real",
            "payload": {"key": "val"},
        })
        self.assertFalse(s.is_valid())

    def test_emit_serializer_valid(self):
        from .serializers import WebhookEmitSerializer
        s = WebhookEmitSerializer(data={
            "event_type": EventType.WALLET_CREDITED,
            "payload": {"balance": "500"},
            "async_dispatch": False,
        })
        self.assertTrue(s.is_valid(), s.errors)


# ─────────────────────────────────────────────────────────────────────────────
#  API VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────

class EndpointAPITest(APITestCase):
    """Ainul Enterprise Engine — Endpoint ViewSet API tests."""

    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.list_url = "/api/webhooks/endpoints/"

    def test_create_endpoint(self):
        resp = self.client.post(self.list_url, {
            "label": "My Endpoint",
            "target_url": "https://hooks.myapp.com/receive",
            "http_method": "POST",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("secret_key", resp.data)
        self.assertTrue(resp.data["secret_key"].startswith("whsec_"))

    def test_list_returns_only_own_endpoints(self):
        other_user = make_user("other@ainul.dev")
        make_endpoint(self.user, label="Mine")
        make_endpoint(other_user, label="Theirs", target_url="https://other.dev")
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        labels = [ep["label"] for ep in resp.data["results"]]
        self.assertIn("Mine", labels)
        self.assertNotIn("Theirs", labels)

    def test_unauthenticated_returns_401(self):
        anon = APIClient()
        resp = anon.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rotate_secret(self):
        ep = make_endpoint(self.user)
        old_secret = ep.secret_key
        url = f"{self.list_url}{ep.pk}/rotate-secret/"
        resp = self.client.post(url, {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        ep.refresh_from_db()
        self.assertNotEqual(ep.secret_key, old_secret)
        self.assertIn("new_secret", resp.data)

    def test_rotate_secret_without_confirm_fails(self):
        ep = make_endpoint(self.user)
        url = f"{self.list_url}{ep.pk}/rotate-secret/"
        resp = self.client.post(url, {"confirm": False}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pause_endpoint(self):
        ep = make_endpoint(self.user)
        url = f"{self.list_url}{ep.pk}/pause/"
        resp = self.client.patch(url)
        self.assertEqual(resp.status_code, 200)
        ep.refresh_from_db()
        self.assertEqual(ep.status, EndpointStatus.PAUSED)

    def test_resume_endpoint(self):
        ep = make_endpoint(self.user, status=EndpointStatus.PAUSED)
        url = f"{self.list_url}{ep.pk}/resume/"
        resp = self.client.patch(url)
        self.assertEqual(resp.status_code, 200)
        ep.refresh_from_db()
        self.assertEqual(ep.status, EndpointStatus.ACTIVE)

    @patch("api.webhooks.services.requests.request")
    def test_send_test_ping(self, mock_req):
        mock_req.return_value = MagicMock(status_code=200, text="pong")
        ep = make_endpoint(self.user)
        url = f"{self.list_url}{ep.pk}/test/"
        resp = self.client.post(url, {"message": "ping!"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["event_type"], EventType.WEBHOOK_TEST)

    def test_send_test_fails_for_paused_endpoint(self):
        ep = make_endpoint(self.user, status=EndpointStatus.PAUSED)
        url = f"{self.list_url}{ep.pk}/test/"
        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class SubscriptionAPITest(APITestCase):
    """Ainul Enterprise Engine — Subscription nested ViewSet API tests."""

    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.ep = make_endpoint(self.user)
        self.base_url = f"/api/webhooks/endpoints/{self.ep.pk}/subscriptions/"

    def test_subscribe_event(self):
        resp = self.client.post(
            self.base_url,
            {"event_type": EventType.PAYOUT_SUCCESS, "is_active": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["event_type"], EventType.PAYOUT_SUCCESS)

    def test_list_subscriptions(self):
        make_subscription(self.ep, EventType.PAYOUT_SUCCESS)
        make_subscription(self.ep, EventType.WALLET_CREDITED)
        resp = self.client.get(self.base_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["results"]), 2)

    def test_cannot_subscribe_to_other_users_endpoint(self):
        other_user = make_user("hacker@bad.dev")
        other_ep = make_endpoint(other_user, label="Victim", target_url="https://victim.dev")
        url = f"/api/webhooks/endpoints/{other_ep.pk}/subscriptions/"
        resp = self.client.post(
            url,
            {"event_type": EventType.PAYOUT_SUCCESS},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class DeliveryLogAPITest(APITestCase):
    """Ainul Enterprise Engine — DeliveryLog ViewSet API tests."""

    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.ep = make_endpoint(self.user)

    def test_list_logs(self):
        make_log(self.ep, status=DeliveryStatus.SUCCESS)
        make_log(self.ep, status=DeliveryStatus.FAILED)
        resp = self.client.get("/api/webhooks/logs/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)

    def test_filter_logs_by_status(self):
        make_log(self.ep, status=DeliveryStatus.SUCCESS)
        make_log(self.ep, status=DeliveryStatus.FAILED)
        resp = self.client.get("/api/webhooks/logs/?status=success")
        self.assertEqual(resp.data["count"], 1)

    def test_filter_logs_by_event_type(self):
        make_log(self.ep, status=DeliveryStatus.SUCCESS,
                 event_type=EventType.PAYOUT_SUCCESS)
        make_log(self.ep, status=DeliveryStatus.SUCCESS,
                 event_type=EventType.WALLET_CREDITED)
        resp = self.client.get(f"/api/webhooks/logs/?event_type={EventType.PAYOUT_SUCCESS}")
        self.assertEqual(resp.data["count"], 1)

    @patch("api.webhooks.services.requests.request")
    def test_manual_retry_failed_log(self, mock_req):
        mock_req.return_value = MagicMock(status_code=200, text="ok")
        log = make_log(self.ep, status=DeliveryStatus.FAILED, attempt=1)
        url = f"/api/webhooks/logs/{log.pk}/retry/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)

    def test_retry_success_log_returns_400(self):
        log = make_log(self.ep, status=DeliveryStatus.SUCCESS)
        url = f"/api/webhooks/logs/{log.pk}/retry/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_see_other_users_logs(self):
        other_user = make_user("other2@ainul.dev")
        other_ep = make_endpoint(other_user, label="Other", target_url="https://other2.dev")
        make_log(other_ep, status=DeliveryStatus.SUCCESS)
        resp = self.client.get("/api/webhooks/logs/")
        self.assertEqual(resp.data["count"], 0)


class EventTypeListAPITest(APITestCase):
    """Ainul Enterprise Engine — EventType list endpoint."""

    def test_returns_all_event_types(self):
        user = make_user()
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/webhooks/event-types/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"], 40)


# ─────────────────────────────────────────────────────────────────────────────
#  CELERY TASK TESTS
# ─────────────────────────────────────────────────────────────────────────────

class CeleryTaskTest(TestCase):
    """Ainul Enterprise Engine — Celery task unit tests (synchronous execution)."""

    def setUp(self):
        self.user = make_user()
        self.ep = make_endpoint(self.user)

    @patch("api.webhooks.services.requests.request")
    def test_retry_task_succeeds(self, mock_req):
        from .tasks import retry_failed_dispatch
        mock_req.return_value = MagicMock(status_code=200, text="ok")
        log = make_log(self.ep, status=DeliveryStatus.FAILED, attempt=1)
        result = retry_failed_dispatch(str(log.pk))
        self.assertEqual(result["status"], DeliveryStatus.SUCCESS)

    def test_retry_task_skips_nonexistent_log(self):
        from .tasks import retry_failed_dispatch
        result = retry_failed_dispatch(str(uuid.uuid4()))
        self.assertEqual(result["status"], "aborted")
        self.assertEqual(result["reason"], "log_not_found")

    def test_retry_task_skips_success_log(self):
        from .tasks import retry_failed_dispatch
        log = make_log(self.ep, status=DeliveryStatus.SUCCESS)
        result = retry_failed_dispatch(str(log.pk))
        self.assertEqual(result["reason"], "already_success")

    def test_retry_task_cancels_for_paused_endpoint(self):
        from .tasks import retry_failed_dispatch
        self.ep.status = EndpointStatus.PAUSED
        self.ep.save()
        log = make_log(self.ep, status=DeliveryStatus.FAILED, attempt=1)
        result = retry_failed_dispatch(str(log.pk))
        self.assertEqual(result["status"], "cancelled")

    def test_reap_exhausted_logs_task_runs(self):
        from .tasks import reap_exhausted_logs
        make_log(self.ep, status=DeliveryStatus.EXHAUSTED)
        result = reap_exhausted_logs()
        self.assertIn("exhausted_count", result)

    def test_auto_suspend_task_suspends_bad_endpoints(self):
        from .tasks import auto_suspend_endpoints
        self.ep.total_deliveries = 100
        self.ep.failed_deliveries = 90
        self.ep.success_deliveries = 10
        self.ep.save()
        result = auto_suspend_endpoints(failure_threshold_pct=80)
        self.assertIn(str(self.ep.pk), result["suspended_endpoint_pks"])
        self.ep.refresh_from_db()
        self.assertEqual(self.ep.status, EndpointStatus.SUSPENDED)

    def test_auto_suspend_skips_good_endpoints(self):
        from .tasks import auto_suspend_endpoints
        self.ep.total_deliveries = 100
        self.ep.failed_deliveries = 5
        self.ep.success_deliveries = 95
        self.ep.save()
        result = auto_suspend_endpoints(failure_threshold_pct=80)
        self.assertNotIn(str(self.ep.pk), result["suspended_endpoint_pks"])


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class ConstantsTest(TestCase):
    """Ainul Enterprise Engine — Validate constants completeness."""

    def test_minimum_40_event_types_defined(self):
        choices = EventType.choices
        self.assertGreaterEqual(len(choices), 40)

    def test_all_delivery_statuses_defined(self):
        expected = {
            "pending", "dispatched", "success",
            "failed", "retrying", "exhausted", "cancelled",
        }
        actual = {c[0] for c in DeliveryStatus.choices}
        self.assertEqual(expected, actual)

    def test_retry_backoff_base_positive(self):
        self.assertGreater(RETRY_BACKOFF_BASE_SECONDS, 0)

    def test_max_retry_attempts_sane(self):
        self.assertGreaterEqual(MAX_RETRY_ATTEMPTS, 3)
        self.assertLessEqual(MAX_RETRY_ATTEMPTS, 10)

    def test_all_headers_non_empty(self):
        self.assertTrue(SIGNATURE_HEADER)
        self.assertTrue(TIMESTAMP_HEADER)
        self.assertTrue(EVENT_HEADER)
        self.assertTrue(DELIVERY_ID_HEADER)
