"""
test_sandbox.py – Tests for the sandbox/test postback endpoint.

Sandbox mode activates when network_key starts with 'test_'.
No DB writes, no Celery tasks, no rewards — just validates the request shape.
"""
import json
from django.test import TestCase, Client
from django.urls import reverse


class SandboxEndpointTests(TestCase):

    def setUp(self):
        self.client = Client()

    def _url(self, network_key):
        return f"/api/postback/receive/{network_key}/"

    def test_sandbox_get_returns_200(self):
        resp = self.client.get(
            self._url("test_cpalead"),
            {"lead_id": "L001", "offer_id": "O001", "payout": "5.00"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_sandbox_post_returns_200(self):
        resp = self.client.post(
            self._url("test_network"),
            data=json.dumps({"lead_id": "L001", "offer_id": "O001"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_sandbox_response_has_sandbox_true(self):
        resp = self.client.get(
            self._url("test_cpalead"),
            {"lead_id": "L001", "offer_id": "O001"},
        )
        data = resp.json()
        self.assertTrue(data.get("sandbox"))

    def test_sandbox_status_is_sandbox_ok(self):
        resp = self.client.get(
            self._url("test_cpalead"),
            {"lead_id": "L001"},
        )
        self.assertEqual(resp.json().get("status"), "sandbox_ok")

    def test_sandbox_returns_received_fields(self):
        resp = self.client.get(
            self._url("test_net"),
            {"lead_id": "L001", "offer_id": "O001", "goal_id": "sale"},
        )
        data = resp.json()
        self.assertIn("received_fields", data)
        self.assertIsInstance(data["received_fields"], list)

    def test_sandbox_returns_simulated_lead_id(self):
        resp = self.client.get(self._url("test_net"), {"lead_id": "L001"})
        data = resp.json()
        self.assertIn("simulated_lead_id", data)

    def test_sandbox_no_db_write(self):
        """Sandbox must not create any PostbackLog records."""
        from api.postback.models import PostbackLog
        before = PostbackLog.objects.count()
        self.client.get(
            self._url("test_cpalead"),
            {"lead_id": "L001", "offer_id": "O001"},
        )
        after = PostbackLog.objects.count()
        self.assertEqual(before, after)

    def test_non_sandbox_network_key_not_sandboxed(self):
        """Normal network_key (no 'test_' prefix) is NOT sandbox mode."""
        # Will attempt real processing (network not found → still 200)
        resp = self.client.get(
            self._url("cpalead_real"),
            {"lead_id": "L001"},
        )
        data = resp.json()
        # Should NOT have sandbox=True
        self.assertNotEqual(data.get("sandbox"), True)

    def test_sandbox_network_key_prefix_variants(self):
        """Any network_key starting with 'test_' is sandboxed."""
        for key in ["test_cpalead", "test_mynetwork", "test_123"]:
            resp = self.client.get(self._url(key), {"lead_id": "L"})
            self.assertTrue(resp.json().get("sandbox"), f"Expected sandbox=True for key={key}")

    def test_sandbox_returns_note_about_live(self):
        """Sandbox response includes guidance to remove test_ prefix for live."""
        resp = self.client.get(self._url("test_cpalead"), {"lead_id": "L"})
        note = resp.json().get("note", "")
        self.assertIn("test_", note.lower() or note)
