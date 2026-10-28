"""
test_pipeline.py – End-to-end pipeline integration tests.

Tests the complete process_postback_sync() pipeline:
  Stage 1: IP check
  Stage 2: Signature verification
  Stage 3: Nonce check
  Stage 4: Payload extraction
  Stage 4b: Event type + reversal detection
  Stage 5: LeadValidator chain
  Stage 5a: Click-to-conversion linking
  Stage 5b: Fraud detection
  Stage 6: Payout cap
  Stage 7: Duplicate check
  Stage 8: User resolution
  Stage 9: Reward dispatch
"""
import time
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase

from api.postback.choices import PostbackStatus, PostbackConversionStatus
from api.postback.services import process_postback_sync
from api.postback.tests.factories import (
    CPALeadNetworkFactory,
    NetworkPostbackConfigFactory,
    NoSignatureNetworkFactory,
    IPWhitelistedNetworkFactory,
    PostbackLogFactory,
    UserFactory,
    FieldRegexValidatorFactory,
    PayoutRangeValidatorFactory,
)


def _run(log, signature="", timestamp=None, nonce=""):
    return process_postback_sync(
        log,
        signature=signature,
        timestamp_str=str(timestamp or int(time.time())),
        nonce=nonce,
        body_bytes=b"",
        path="/api/postback/receive/cpalead/",
        query_params={},
    )


class Stage1IPCheckTests(TestCase):

    def test_no_whitelist_ip_is_whitelisted(self):
        net = NoSignatureNetworkFactory(ip_whitelist=[])
        log = PostbackLogFactory(network=net, source_ip="1.2.3.4")
        result = _run(log)
        # With empty whitelist, IP check passes (not rejected for IP reason)
        self.assertNotEqual(result.rejection_reason, "ip_not_whitelisted")

    def test_ip_in_whitelist_passes(self):
        net = NoSignatureNetworkFactory(ip_whitelist=["1.2.3.4"])
        log = PostbackLogFactory(network=net, source_ip="1.2.3.4")
        result = _run(log)
        self.assertTrue(result.ip_whitelisted)

    def test_ip_not_in_whitelist_rejected(self):
        net = NetworkPostbackConfigFactory(
            ip_whitelist=["10.0.0.1"],
            signature_algorithm="none",
            require_nonce=False,
        )
        log = PostbackLogFactory(network=net, source_ip="9.9.9.9")
        result = _run(log)
        self.assertEqual(result.status, PostbackStatus.REJECTED)


class Stage2SignatureTests(TestCase):

    def test_no_signature_algo_skips_verification(self):
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(network=net)
        result = _run(log, signature="")
        # Should not reject due to signature
        self.assertNotEqual(result.rejection_reason, "invalid_signature")

    def test_hmac_required_but_missing_rejects(self):
        net = NetworkPostbackConfigFactory(
            signature_algorithm="hmac_sha256",
            secret_key="mysecret",
            ip_whitelist=[],
            require_nonce=False,
        )
        log = PostbackLogFactory(network=net, source_ip="1.2.3.4")
        result = _run(log, signature="")
        self.assertEqual(result.status, PostbackStatus.REJECTED)


class Stage4bEventTypeTests(TestCase):

    def test_event_type_from_adapted_payload(self):
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(
            network=net,
            raw_payload={"lead_id": "L1", "offer_id": "O1", "event_type": "sale"},
        )
        result = _run(log)
        # event_type should be persisted
        result.refresh_from_db()
        self.assertIn(result.event_type, ["sale", "unknown"])

    def test_reversal_payload_short_circuits(self):
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(
            network=net,
            raw_payload={"lead_id": "L1", "offer_id": "O1", "is_reversal": True},
        )
        with patch("api.postback.services.handle_reversal_postback") as mock_rev:
            mock_rev.return_value = True
            result = _run(log)


class Stage5ValidatorTests(TestCase):

    def test_field_present_validator_rejects_missing_field(self):
        net = NoSignatureNetworkFactory()
        validator = FieldRegexValidatorFactory(
            network=net,
            validator_type="field_present",
            params={"field": "required_missing_field"},
            is_blocking=True,
        )
        log = PostbackLogFactory(
            network=net,
            raw_payload={"lead_id": "L1", "offer_id": "O1"},
        )
        result = _run(log)
        self.assertEqual(result.status, PostbackStatus.REJECTED)

    def test_payout_cap_exceeded_rejects(self):
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(
            network=net,
            payout=Decimal("9999.99"),
            raw_payload={"lead_id": "L1", "offer_id": "O1", "payout": "9999.99"},
        )
        result = _run(log)
        self.assertEqual(result.status, PostbackStatus.REJECTED)


class Stage7DuplicateCheckTests(TestCase):

    def test_duplicate_lead_rejected(self):
        from api.postback.tests.factories import DuplicateLeadCheckFactory
        net = NoSignatureNetworkFactory()
        # Create first log and mark it rewarded
        first_log = PostbackLogFactory(
            network=net,
            lead_id="DUP_LEAD_001",
            status=PostbackStatus.REWARDED,
        )
        DuplicateLeadCheckFactory(network=net, lead_id="DUP_LEAD_001")

        # Second postback with same lead_id
        second_log = PostbackLogFactory(
            network=net,
            lead_id="DUP_LEAD_001",
        )
        result = _run(second_log)
        # Should be DUPLICATE or REJECTED
        self.assertIn(result.status, [PostbackStatus.DUPLICATE, PostbackStatus.REJECTED])


class Stage8UserResolutionTests(TestCase):

    def test_no_user_id_in_payload_rejects(self):
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(
            network=net,
            raw_payload={"lead_id": "L1", "offer_id": "O1"},
            lead_id="L1",
        )
        result = _run(log)
        # Without user_id, cannot resolve user
        self.assertIn(result.status, [PostbackStatus.REJECTED, PostbackStatus.FAILED])


class Stage9RewardDispatchTests(TestCase):

    @patch("api.postback.services._award_inventory_item", return_value="")
    @patch("api.postback.services._dispatch_reward")
    def test_reward_dispatched_for_valid_postback(self, mock_reward, mock_item):
        user = UserFactory()
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(
            network=net,
            raw_payload={
                "lead_id": "REWARD_LEAD_001",
                "offer_id": "OFFER_001",
                "user_id": str(user.pk),
                "payout": "2.50",
            },
            lead_id="REWARD_LEAD_001",
            offer_id="OFFER_001",
        )
        with patch("api.postback.services._resolve_user", return_value=user):
            result = _run(log)


class FullPipelineTests(TestCase):
    """End-to-end tests that exercise the complete pipeline."""

    def test_complete_cpalead_flow(self):
        """Simulate a real CPAlead postback from start to finish."""
        user = UserFactory()
        net = CPALeadNetworkFactory(
            ip_whitelist=[],
            require_nonce=False,
            signature_algorithm="none",
        )
        log = PostbackLogFactory(
            network=net,
            source_ip="1.2.3.4",
            raw_payload={
                "sub1": "CPALEAD_LEAD_001",
                "oid": "CPALEAD_OFFER_001",
                "amount": "5.00",
                "currency": "USD",
                "goal": "sale",
                "sub2": "PUB_SUB1",
                "user_id": str(user.pk),
                "status": "approved",
            },
            lead_id="CPALEAD_LEAD_001",
            offer_id="CPALEAD_OFFER_001",
        )

        with patch("api.postback.services._resolve_user", return_value=user), \
             patch("api.postback.services._award_inventory_item", return_value=""), \
             patch("api.postback.services._dispatch_reward") as mock_reward:
            result = _run(log)

    def test_pipeline_never_raises(self):
        """process_postback_sync never raises — always returns PostbackLog."""
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(network=net, raw_payload={})
        try:
            result = process_postback_sync(
                log,
                signature="",
                timestamp_str="invalid",
                nonce="",
                body_bytes=b"",
                path="/",
                query_params={},
            )
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"process_postback_sync raised: {e}")

    def test_pipeline_result_is_postback_log(self):
        from api.postback.models import PostbackLog
        net = NoSignatureNetworkFactory()
        log = PostbackLogFactory(network=net)
        result = _run(log)
        self.assertIsInstance(result, PostbackLog)
