"""
Endpoint smoke test.

Fires real HTTP requests (via DRF's APIClient) at every routed endpoint:
list/retrieve for every ViewSet, GET for every standalone APIView, plus a
couple of representative POSTs. This is deliberately separate from the
unit-level service tests elsewhere in this suite - it catches what those
can't: read_only+write_only on the same field, ordering_fields/
filterset_fields/select_related referencing columns that don't exist,
querysets filtering by a field the model doesn't have, permission_classes
misconfiguration, URL reversal/namespace drift, etc.
"""
import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ..models import WebhookEndpoint, WebhookSubscription

User = get_user_model()


class EndpointSmokeTest(TestCase):
    """GET every list endpoint, GET every retrieve endpoint with a real
    object, and a light POST sanity check on a few. Fails loudly on any
    5xx - 4xx is fine (that's the view doing its job, e.g. permission
    checks), a 5xx means something in the view/serializer/queryset chain
    is broken against the real schema."""

    LIST_ENDPOINTS = [
        "webhook-endpoint-list", "webhook-log-list", "webhook-filter-list",
        "webhook-template-list", "webhook-batch-list", "webhook-secret-list",
        "webhook-replay-list", "webhook-inbound-list", "webhook-inbound-log-list",
        "webhook-analytics-list", "webhook-health-list", "webhook-admin-list",
        "webhook-rate-limit-list", "webhook-retry-analysis-list",
        "aging-endpoint-list", "aging-log-list", "aging-event-list",
    ]

    SIMPLE_GET_PATHS = [
        "/webhooks/event-types/",
        "/webhooks/aging/summary/",
        "/webhooks/aging/policy/",
    ]

    def setUp(self):
        self.user = User.objects.create_user(
            username="smoketest", email="smoke@example.com", password="x", is_staff=True
        )
        self.superuser = User.objects.create_user(
            username="smokeadmin", email="smokeadmin@example.com", password="x", is_staff=True, is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.superuser)
        self.endpoint = WebhookEndpoint.objects.create(
            target_url="https://example.com/hook", owner=self.user
        )

    def test_all_list_endpoints_return_no_5xx(self):
        failures = []
        for name in self.LIST_ENDPOINTS:
            url = reverse(f"webhooks:{name}")
            client = self.admin_client if name == "webhook-admin-list" else self.client
            resp = client.get(url)
            if resp.status_code >= 500:
                failures.append(f"{name} ({url}) -> {resp.status_code}")
        self.assertFalse(failures, "5xx on list endpoint(s): " + "; ".join(failures))

    def test_simple_get_paths_return_no_5xx(self):
        failures = []
        for path in self.SIMPLE_GET_PATHS:
            resp = self.client.get(path)
            if resp.status_code >= 500:
                failures.append(f"{path} -> {resp.status_code}")
        self.assertFalse(failures, "5xx on path(s): " + "; ".join(failures))

    def test_retrieve_endpoints_with_real_objects(self):
        url = reverse("webhooks:webhook-endpoint-detail", kwargs={"pk": self.endpoint.pk})
        resp = self.client.get(url)
        self.assertLess(resp.status_code, 500, f"{url} -> {resp.status_code}")

        WebhookSubscription.objects.create(
            endpoint=self.endpoint, event_type="user.created", is_active=True
        )
        url = reverse("webhooks:webhook-subscription-list", kwargs={"endpoint_pk": self.endpoint.pk})
        resp = self.client.get(url)
        self.assertLess(resp.status_code, 500, f"{url} -> {resp.status_code}")

    def test_admin_endpoint_requires_superuser_not_just_staff(self):
        # is_staff alone -> 403 (AdminWebhookViewSet requires IsSuperUser)
        resp = self.client.get("/webhooks/admin/webhooks/")
        self.assertEqual(resp.status_code, 403)
        # real superuser -> works
        resp = self.admin_client.get("/webhooks/admin/webhooks/")
        self.assertLess(resp.status_code, 500)

    def test_emit_and_event_type_apiviews(self):
        resp = self.client.post(
            "/webhooks/emit/validate/",
            data=json.dumps({"event_type": "user.created", "payload": {"a": 1}}),
            content_type="application/json",
        )
        self.assertLess(resp.status_code, 500)

        resp = self.client.post(
            "/webhooks/emit/preview/",
            data=json.dumps({"endpoint_id": str(self.endpoint.pk), "event_type": "user.created", "payload": {"a": 1}}),
            content_type="application/json",
        )
        self.assertLess(resp.status_code, 500)

    def test_inbound_receive_view(self):
        resp = self.client.post(
            "/webhooks/receive/stripe/",
            data=json.dumps({"event": {"type": "test"}}),
            content_type="application/json",
        )
        self.assertLess(resp.status_code, 500)
