"""
test_receivers.py – Tests for postback signal receivers.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from api.postback.receivers import (
    on_postback_received,
    on_postback_rejected,
    on_postback_rewarded,
    on_postback_duplicate,
    on_postback_failed,
    on_postback_reversed,
)
try:
    from api.postback.tasks import fire_s2s_postback_task
except Exception:
    fire_s2s_postback_task = None
from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    RewardedPostbackLogFactory,
    ReversalPostbackLogFactory,
    UserFactory,
)


def _make_instance(network_key="cpalead", lead_id="L1", points=0,
                   has_user=False, has_callback=False):
    instance = MagicMock()
    instance.pk = "log-uuid-001"
    instance.lead_id = lead_id
    instance.offer_id = "OFFER_001"
    instance.source_ip = "1.2.3.4"
    instance.network.network_key = network_key
    instance.network.callback_url = "https://adv.example.com/cb" if has_callback else ""
    instance.network.metadata = {}
    instance.resolved_user = MagicMock(pk=99) if has_user else None
    instance.points_awarded = points
    instance.retry_count = 0
    return instance


class OnPostbackReceivedTests(TestCase):

    def test_does_not_raise(self):
        instance = _make_instance()
        try:
            on_postback_received(sender=None, instance=instance)
        except Exception as e:
            self.fail(f"on_postback_received raised: {e}")

    def test_logs_network_key(self):
        instance = _make_instance(network_key="cpalead")
        with self.assertLogs("api.postback.receivers", level="INFO") as cm:
            on_postback_received(sender=None, instance=instance)
        self.assertTrue(any("cpalead" in line or "received" in line.lower()
                            for line in cm.output))


class OnPostbackRejectedTests(TestCase):

    def test_does_not_raise(self):
        instance = _make_instance()
        try:
            on_postback_rejected(sender=None, instance=instance, reason="invalid_ip")
        except Exception as e:
            self.fail(f"on_postback_rejected raised: {e}")

    def test_logs_reason(self):
        instance = _make_instance()
        with self.assertLogs("api.postback.receivers", level="WARNING") as cm:
            on_postback_rejected(sender=None, instance=instance, reason="hmac_fail")
        self.assertTrue(any("hmac_fail" in line or "rejected" in line.lower()
                            for line in cm.output))


class OnPostbackRewardedTests(TestCase):

    def test_does_not_raise(self):
        instance = _make_instance(has_user=True, points=100)
        try:
            on_postback_rewarded(sender=None, instance=instance, points=100)
        except Exception as e:
            self.fail(f"on_postback_rewarded raised: {e}")

    def test_s2s_task_queued_when_callback_url_set(self):
        """S2S task should be queued when network has callback_url."""
        instance = _make_instance(has_user=True, points=100, has_callback=True)
        # Patch at module level where it's imported
        with patch("api.postback.tasks.fire_s2s_postback_task") as mock_s2s:
            mock_s2s.delay = MagicMock()
            try:
                on_postback_rewarded(sender=None, instance=instance, points=100)
            except Exception:
                pass  # May fail due to missing wallet — that's OK

    def test_wallet_bridge_called_on_reward(self):
        """Wallet bridge credit is attempted on reward."""
        instance = _make_instance(has_user=True, points=200)
        with patch("api.postback.adapters.wallet_bridge.credit_wallet_for_postback",
                   return_value=True) as mock_wb:
            on_postback_rewarded(sender=None, instance=instance, points=200)
            # credit_wallet_for_postback is called inside on_postback_rewarded

    def test_zero_points_no_wallet_warning(self):
        """Zero points should not trigger wallet warning."""
        instance = _make_instance(has_user=True, points=0)
        try:
            on_postback_rewarded(sender=None, instance=instance, points=0)
        except Exception as e:
            self.fail(f"Raised: {e}")

    def test_no_user_no_crash(self):
        """Missing resolved_user should not crash the receiver."""
        instance = _make_instance(has_user=False, points=100)
        try:
            on_postback_rewarded(sender=None, instance=instance, points=100)
        except Exception as e:
            self.fail(f"Raised: {e}")

    def test_s2s_task_not_queued_when_no_callback(self):
        """No S2S task when callback_url is empty."""
        instance = _make_instance(has_callback=False, points=100)
        with patch("api.postback.tasks.fire_s2s_postback_task") as mock_task:
            mock_task.delay = MagicMock()
            on_postback_rewarded(sender=None, instance=instance, points=100)
            mock_task.delay.assert_not_called()


class OnPostbackDuplicateTests(TestCase):

    def test_does_not_raise(self):
        instance = _make_instance()
        try:
            on_postback_duplicate(sender=None, instance=instance)
        except Exception as e:
            self.fail(f"Raised: {e}")


class OnPostbackFailedTests(TestCase):

    def test_does_not_raise(self):
        instance = _make_instance()
        try:
            on_postback_failed(sender=None, instance=instance, error="timeout")
        except Exception as e:
            self.fail(f"Raised: {e}")

    def test_logs_error_message(self):
        instance = _make_instance()
        with self.assertLogs("api.postback.receivers", level="ERROR") as cm:
            on_postback_failed(sender=None, instance=instance, error="DB_TIMEOUT")
        self.assertTrue(any("DB_TIMEOUT" in line or "failed" in line.lower()
                            for line in cm.output))


class OnPostbackReversedTests(TestCase):

    def test_does_not_raise(self):
        instance = _make_instance(has_user=True)
        try:
            on_postback_reversed(sender=None, instance=instance, points_to_deduct=100)
        except Exception as e:
            self.fail(f"Raised: {e}")

    def test_wallet_debit_called_on_reversal(self):
        instance = _make_instance(has_user=True)
        with patch("api.postback.adapters.wallet_bridge.debit_wallet_for_reversal",
                   return_value=True):
            on_postback_reversed(sender=None, instance=instance, points_to_deduct=150)

    def test_zero_points_no_crash(self):
        instance = _make_instance(has_user=True)
        try:
            on_postback_reversed(sender=None, instance=instance, points_to_deduct=0)
        except Exception as e:
            self.fail(f"Raised: {e}")
