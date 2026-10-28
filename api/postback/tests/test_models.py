"""
test_models.py – Tests for PostbackLog, NetworkPostbackConfig, PostbackS2SLog models.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from api.postback.choices import (
    ConversionEventType,
    PostbackConversionStatus,
    PostbackStatus,
    RejectionReason,
)
from api.postback.tests.factories import (
    CPALeadNetworkFactory,
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    PostbackS2SLogFactory,
    RewardedPostbackLogFactory,
    RejectedPostbackLogFactory,
    ReversalPostbackLogFactory,
    UserFactory,
)


class NetworkPostbackConfigModelTests(TestCase):

    def test_create_basic_config(self):
        net = NetworkPostbackConfigFactory(name="Test Net")
        self.assertEqual(net.name, "Test Net")
        self.assertIsNotNone(net.pk)

    def test_network_key_is_unique(self):
        from django.db import IntegrityError
        net1 = NetworkPostbackConfigFactory(network_key="unique_net_001")
        with self.assertRaises(Exception):
            NetworkPostbackConfigFactory(network_key="unique_net_001")

    def test_callback_url_defaults_empty(self):
        net = NetworkPostbackConfigFactory()
        self.assertEqual(net.callback_url, "")

    def test_callback_method_defaults_get(self):
        net = NetworkPostbackConfigFactory()
        self.assertEqual(net.callback_method, "GET")

    def test_cpalead_factory_has_correct_key(self):
        net = CPALeadNetworkFactory()
        self.assertIn("cpalead", net.network_key)

    def test_s2s_factory_has_callback_url(self):
        from api.postback.tests.factories import S2SNetworkFactory
        net = S2SNetworkFactory()
        self.assertNotEqual(net.callback_url, "")
        self.assertTrue(net.callback_url.startswith("https://"))


class PostbackLogModelTests(TestCase):

    def test_create_basic_log(self):
        log = PostbackLogFactory()
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.status, PostbackStatus.RECEIVED)

    def test_uuid_primary_key(self):
        log = PostbackLogFactory()
        self.assertIsInstance(log.pk, uuid.UUID)

    def test_event_type_default_unknown(self):
        log = PostbackLogFactory()
        self.assertEqual(log.event_type, ConversionEventType.UNKNOWN)

    def test_conversion_status_default_approved(self):
        log = PostbackLogFactory()
        self.assertEqual(log.conversion_status, PostbackConversionStatus.APPROVED)

    def test_is_reversal_default_false(self):
        log = PostbackLogFactory()
        self.assertFalse(log.is_reversal)

    def test_click_id_default_empty(self):
        log = PostbackLogFactory()
        self.assertEqual(log.click_id, "")

    def test_fire_delay_ms_default_zero(self):
        log = PostbackLogFactory()
        self.assertEqual(log.fire_delay_ms, 0)

    def test_rewarded_log_has_user(self):
        log = RewardedPostbackLogFactory()
        self.assertIsNotNone(log.resolved_user)
        self.assertEqual(log.points_awarded, 100)

    def test_rejected_log_has_rejection_reason(self):
        log = RejectedPostbackLogFactory()
        self.assertEqual(log.status, PostbackStatus.REJECTED)
        self.assertIsNotNone(log.rejection_reason)

    def test_reversal_log_has_is_reversal_true(self):
        log = ReversalPostbackLogFactory()
        self.assertTrue(log.is_reversal)
        self.assertEqual(log.conversion_status, PostbackConversionStatus.REVERSED)

    def test_payout_is_decimal(self):
        log = PostbackLogFactory()
        from decimal import Decimal
        # payout is stored as DecimalField — value should be Decimal-compatible
        self.assertIsNotNone(log.payout)
        float(log.payout)  # Should be numeric

    def test_str_representation(self):
        log = PostbackLogFactory(lead_id="TEST_LEAD")
        # __str__ should not raise
        str(log)

    def test_reversal_negative_payout(self):
        log = ReversalPostbackLogFactory()
        self.assertTrue(Decimal(log.payout) < 0 or log.payout == Decimal("-2.50"))


class PostbackS2SLogModelTests(TestCase):

    def test_create_s2s_log(self):
        log = PostbackS2SLogFactory()
        self.assertIsNotNone(log.pk)
        self.assertTrue(log.success)

    def test_uuid_primary_key(self):
        log = PostbackS2SLogFactory()
        self.assertIsInstance(log.pk, uuid.UUID)

    def test_failed_s2s_log(self):
        log = PostbackS2SLogFactory(
            success=False,
            http_status=500,
            error_message="Connection refused",
        )
        self.assertFalse(log.success)
        self.assertEqual(log.http_status, 500)

    def test_multiple_attempts(self):
        log = PostbackS2SLogFactory(attempt_number=3, success=True)
        self.assertEqual(log.attempt_number, 3)

    def test_callback_url_stored(self):
        log = PostbackS2SLogFactory(
            callback_url="https://adv.example.com/postback?lead=L1"
        )
        self.assertIn("https://", log.callback_url)


class ChoicesTests(TestCase):

    def test_conversion_event_type_choices(self):
        expected = ["install","lead","sale","registration","trial",
                    "subscription","deposit","survey","video","click","custom","unknown"]
        for val in expected:
            self.assertIn(val, [c[0] for c in ConversionEventType.choices])

    def test_postback_conversion_status_choices(self):
        expected = ["approved","pending","reversed","rejected","fraud"]
        for val in expected:
            self.assertIn(val, [c[0] for c in PostbackConversionStatus.choices])

    def test_postback_status_choices_exist(self):
        self.assertGreater(len(PostbackStatus.choices), 0)
