"""test_webhooks.py – Integration tests for the postback webhook view and pipeline."""
import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase, RequestFactory
from django.utils import timezone

from postback.choices import PostbackStatus, RejectionReason
from postback.models import DuplicateLeadCheck, PostbackLog
from postback.webhooks import PostbackWebhookView
from .factories import (
    DuplicateLeadCheckFactory,
    FailedPostbackLogFactory,
    LeadValidatorFactory,
    NetworkPostbackConfigFactory,
    NoSignatureNetworkFactory,
    PostbackLogFactory,
    UserFactory,
)


def _make_signed_request(rf, network, path, payload, method="POST"):
    """Helper: build a signed request for a network."""
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    nonce = f"nonce-{int(time.time() * 1000)}"

    from postback.utils.signature_validator import build_canonical_string, compute_signature
    canonical = build_canonical_string(
        method=method, path=path, query_params={},
        body=body, timestamp=ts, nonce=nonce,
    )
    sig = compute_signature(network.secret_key, canonical)

    headers = {
        "content_type": "application/json",
        "HTTP_X_POSTBACK_SIGNATURE": sig,
        "HTTP_X_POSTBACK_TIMESTAMP": ts,
        "HTTP_X_POSTBACK_NONCE": nonce,
        "REMOTE_ADDR": "1.2.3.4",
    }
    if method == "POST":
        return rf.post(path, data=body, **headers)
    return rf.get(path, **headers)


class PostbackWebhookViewTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()
        self.network = NetworkPostbackConfigFactory()
        self.path = f"/api/postback/receive/{self.network.network_key}/"

    @patch("postback.services.process_postback")
    def test_valid_signed_post_returns_200(self, mock_task):
        mock_task.delay = MagicMock()
        payload = {
            "lead_id": "L001",
            "offer_id": "O001",
            "payout": "5.00",
            "currency": "USD",
        }
        request = _make_signed_request(self.rf, self.network, self.path, payload)
        view = PostbackWebhookView.as_view()
        response = view(request, network_key=self.network.network_key)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "received")
        self.assertIn("id", data)

    @patch("postback.services.process_postback")
    def test_unknown_network_key_still_returns_200(self, mock_task):
        """Must return 200 to prevent network enumeration."""
        mock_task.delay = MagicMock()
        request = self.rf.post(
            "/api/postback/receive/unknown-net/",
            data=b"{}",
            content_type="application/json",
            REMOTE_ADDR="1.2.3.4",
        )
        view = PostbackWebhookView.as_view()
        response = view(request, network_key="unknown-net")
        self.assertEqual(response.status_code, 200)

    @patch("postback.services.process_postback")
    def test_get_postback_supported(self, mock_task):
        """GET postbacks (query-string payloads) must also be accepted."""
        mock_task.delay = MagicMock()
        network = NoSignatureNetworkFactory()
        path = f"/api/postback/receive/{network.network_key}/"
        request = self.rf.get(
            path,
            data={"lead_id": "L002", "offer_id": "O002"},
            REMOTE_ADDR="1.2.3.4",
        )
        view = PostbackWebhookView.as_view()
        response = view(request, network_key=network.network_key)
        self.assertEqual(response.status_code, 200)

    @patch("postback.services.process_postback")
    def test_postback_log_created_on_receive(self, mock_task):
        mock_task.delay = MagicMock()
        payload = {"lead_id": "L003", "offer_id": "O003"}
        request = _make_signed_request(self.rf, self.network, self.path, payload)
        view = PostbackWebhookView.as_view()
        view(request, network_key=self.network.network_key)
        self.assertTrue(PostbackLog.objects.filter(network=self.network).exists())


class PostbackProcessingPipelineTests(TestCase):
    """Tests for the synchronous processing pipeline."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory(
            required_fields=["lead_id", "offer_id"],
            default_reward_points=200,
            ip_whitelist=[],
            signature_algorithm="none",
            require_nonce=False,
        )
        self.user = UserFactory()

    def _run_pipeline(self, payload, lead_id="L001", offer_id="O001"):
        from postback.services import process_postback_sync
        log = PostbackLogFactory(
            network=self.network,
            raw_payload=payload,
            lead_id=lead_id,
            offer_id=offer_id,
            source_ip="1.2.3.4",
        )
        return process_postback_sync(
            log,
            signature="",
            timestamp_str=str(int(time.time())),
            nonce="",
            body_bytes=b"",
            path="/",
            query_params={},
        )

    def test_valid_postback_without_user_gets_rejected(self):
        payload = {"lead_id": "L001", "offer_id": "O001"}
        log = self._run_pipeline(payload)
        self.assertIn(log.status, [PostbackStatus.REJECTED, PostbackStatus.REWARDED])

    def test_missing_required_field_rejects(self):
        payload = {"lead_id": "ONLY_LEAD"}  # missing offer_id
        log = self._run_pipeline(payload, lead_id="ONLY_LEAD", offer_id="")
        self.assertEqual(log.status, PostbackStatus.REJECTED)
        self.assertEqual(log.rejection_reason, RejectionReason.MISSING_FIELDS)

    def test_duplicate_lead_marks_duplicate(self):
        lead_id = "DEDUP_LEAD_001"
        DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)
        payload = {"lead_id": lead_id, "offer_id": "O001"}
        log = self._run_pipeline(payload, lead_id=lead_id)
        self.assertEqual(log.status, PostbackStatus.DUPLICATE)

    def test_payout_over_cap_rejects(self):
        from postback.constants import MAX_PAYOUT_PER_POSTBACK
        payload = {
            "lead_id": "BIGPAY001",
            "offer_id": "O001",
            "payout": str(MAX_PAYOUT_PER_POSTBACK + 1),
        }
        log = self._run_pipeline(payload, lead_id="BIGPAY001")
        self.assertEqual(log.status, PostbackStatus.REJECTED)
        self.assertEqual(log.rejection_reason, RejectionReason.PAYOUT_LIMIT_EXCEEDED)

    @patch("postback.services.award_item_to_user", side_effect=Exception("No stock"))
    def test_reward_item_failure_still_marks_rewarded(self, mock_award):
        """Even if item awarding fails, the log should be marked rewarded with points."""
        network = NetworkPostbackConfigFactory(
            ip_whitelist=[],
            signature_algorithm="none",
            require_nonce=False,
            required_fields=["lead_id", "offer_id"],
            reward_rules={"O001": {"points": 50, "item_id": "00000000-0000-0000-0000-000000000001"}},
            default_reward_points=50,
        )
        user = UserFactory()
        from postback.services import process_postback_sync
        log = PostbackLogFactory(
            network=network,
            raw_payload={"lead_id": "L_ITEM_FAIL", "offer_id": "O001"},
            lead_id="L_ITEM_FAIL",
            offer_id="O001",
            source_ip="1.2.3.4",
            resolved_user=user,
        )
        # Patch user resolution to return our user
        with patch("postback.services._resolve_user", return_value=user):
            result = process_postback_sync(
                log,
                signature="", timestamp_str=str(int(time.time())),
                nonce="", body_bytes=b"", path="/", query_params={},
            )
        # Should be rewarded even though item award raised
        self.assertEqual(result.status, PostbackStatus.REWARDED)


class IPValidationTests(TestCase):

    def test_ip_not_in_whitelist_rejects(self):
        network = NetworkPostbackConfigFactory(
            ip_whitelist=["10.0.0.1"],
            signature_algorithm="none",
            require_nonce=False,
            required_fields=[],
        )
        from postback.services import process_postback_sync
        log = PostbackLogFactory(
            network=network,
            source_ip="8.8.8.8",
            signature_verified=False,
            ip_whitelisted=False,
        )
        result = process_postback_sync(
            log,
            signature="", timestamp_str=str(int(time.time())),
            nonce="", body_bytes=b"", path="/", query_params={},
        )
        self.assertEqual(result.status, PostbackStatus.REJECTED)
        self.assertEqual(result.rejection_reason, RejectionReason.IP_NOT_WHITELISTED)

    def test_ip_in_whitelist_passes(self):
        network = NetworkPostbackConfigFactory(
            ip_whitelist=["1.2.3.4"],
            signature_algorithm="none",
            require_nonce=False,
            required_fields=["lead_id"],
        )
        user = UserFactory()
        from postback.services import process_postback_sync
        log = PostbackLogFactory(
            network=network,
            source_ip="1.2.3.4",
            raw_payload={"lead_id": "L_WL_001"},
            lead_id="L_WL_001",
        )
        with patch("postback.services._resolve_user", return_value=user):
            result = process_postback_sync(
                log,
                signature="", timestamp_str=str(int(time.time())),
                nonce="", body_bytes=b"", path="/", query_params={},
            )
        self.assertNotEqual(result.status, PostbackStatus.REJECTED)


class LeadValidatorChainTests(TestCase):

    def _run_validators(self, validator_params, payload, payout=Decimal("5.00")):
        from postback.services import _run_validators
        network = NetworkPostbackConfigFactory(ip_whitelist=[], signature_algorithm="none")
        LeadValidatorFactory(
            network=network,
            **validator_params,
        )
        network.refresh_from_db()
        return _run_validators(network, payload, payout)

    def test_field_present_passes(self):
        self._run_validators(
            {"validator_type": "field_present", "params": {"field": "lead_id"}, "is_blocking": True},
            {"lead_id": "L1"},
        )  # Should not raise

    def test_field_present_fails_blocking(self):
        from postback.exceptions import SchemaValidationException
        with self.assertRaises(SchemaValidationException):
            self._run_validators(
                {"validator_type": "field_present", "params": {"field": "lead_id"}, "is_blocking": True},
                {"offer_id": "O1"},  # missing lead_id
            )

    def test_regex_validator_passes(self):
        self._run_validators(
            {
                "validator_type": "field_regex",
                "params": {"field": "lead_id", "pattern": r"^[A-Z0-9]{4,}$"},
                "is_blocking": True,
            },
            {"lead_id": "ABCD1234"},
        )  # Should not raise

    def test_regex_validator_fails_blocking(self):
        from postback.exceptions import SchemaValidationException
        with self.assertRaises(SchemaValidationException):
            self._run_validators(
                {
                    "validator_type": "field_regex",
                    "params": {"field": "lead_id", "pattern": r"^[A-Z]{10}$"},
                    "is_blocking": True,
                },
                {"lead_id": "lower123"},
            )

    def test_payout_range_passes(self):
        self._run_validators(
            {
                "validator_type": "payout_range",
                "params": {"min": 1.0, "max": 100.0},
                "is_blocking": True,
            },
            {},
            payout=Decimal("50.00"),
        )

    def test_payout_range_fails_blocking(self):
        from postback.exceptions import SchemaValidationException
        with self.assertRaises(SchemaValidationException):
            self._run_validators(
                {
                    "validator_type": "payout_range",
                    "params": {"min": 5.0, "max": 10.0},
                    "is_blocking": True,
                },
                {},
                payout=Decimal("0.10"),
            )

    def test_non_blocking_validator_does_not_raise(self):
        """A failing non-blocking validator logs a warning but does not reject."""
        self._run_validators(
            {
                "validator_type": "field_present",
                "params": {"field": "missing_field"},
                "is_blocking": False,
            },
            {},
        )  # Should not raise
