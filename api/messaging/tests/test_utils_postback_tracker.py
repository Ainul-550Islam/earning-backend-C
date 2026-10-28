"""
test_utils_postback_tracker.py
=================================
Tests for messaging/utils/postback_tracker.py against its ACTUAL public API:
  notify_conversion_via_ws, fire_conversion_signal,
  send_postback_failed_alert, inject_conversion_context_to_chat

Place in: messaging/tests/test_utils_postback_tracker.py
"""
from __future__ import annotations
from unittest.mock import patch

from django.test import TestCase

from .factories import InternalChatFactory, UserFactory
from ..utils.postback_tracker import (
    notify_conversion_via_ws,
    fire_conversion_signal,
    send_postback_failed_alert,
    inject_conversion_context_to_chat,
)


class TestNotifyConversionViaWs(TestCase):
    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_to_correct_group_with_full_payload(self, mock_send):
        mock_send.return_value = True
        result = notify_conversion_via_ws(
            affiliate_id=7, conversion_id="conv1", offer_id=42,
            offer_name="Gaming App", payout_amount="$3.00", click_id="click1",
        )
        self.assertTrue(result)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["group_name"], "user_devices_7")
        self.assertEqual(kwargs["event_type"], "cpa.conversion")
        self.assertEqual(kwargs["data"]["conversion_id"], "conv1")
        self.assertEqual(kwargs["data"]["offer_id"], "42")
        self.assertEqual(kwargs["data"]["payout_amount"], "$3.00")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_merges_extra_metadata_into_payload(self, mock_send):
        mock_send.return_value = True
        notify_conversion_via_ws(
            affiliate_id=7, conversion_id="conv1", offer_id=42,
            offer_name="x", payout_amount="$1.00",
            metadata={"vertical": "finance"},
        )
        data = mock_send.call_args.kwargs["data"]
        self.assertEqual(data["vertical"], "finance")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_returns_false_on_exception(self, mock_send):
        mock_send.side_effect = Exception("boom")
        result = notify_conversion_via_ws(
            affiliate_id=7, conversion_id="conv1", offer_id=42,
            offer_name="x", payout_amount="$1.00",
        )
        self.assertFalse(result)


class TestFireConversionSignal(TestCase):
    @patch("messaging.signals_cpa.conversion_received.send")
    def test_sends_signal_with_correct_kwargs(self, mock_send):
        fire_conversion_signal(
            affiliate_id=7, conversion_id="conv1", offer_id=42,
            offer_name="Gaming App", payout_amount="$3.00",
        )
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["affiliate_id"], 7)
        self.assertEqual(kwargs["conversion_id"], "conv1")
        self.assertEqual(kwargs["offer_id"], 42)
        self.assertEqual(kwargs["payout_amount"], "$3.00")

    @patch("messaging.signals_cpa.conversion_received.send")
    def test_does_not_raise_when_signal_send_fails(self, mock_send):
        mock_send.side_effect = Exception("boom")
        try:
            fire_conversion_signal(
                affiliate_id=7, conversion_id="conv1", offer_id=42,
                offer_name="x", payout_amount="$1.00",
            )
        except Exception as exc:
            self.fail(f"fire_conversion_signal raised unexpectedly: {exc}")

    def test_triggers_real_receiver_and_creates_notification(self):
        from ..models import CPANotification
        affiliate = UserFactory()
        fire_conversion_signal(
            affiliate_id=affiliate.pk, conversion_id="conv1", offer_id=42,
            offer_name="Gaming App", payout_amount="$3.00",
        )
        self.assertTrue(
            CPANotification.objects.filter(recipient=affiliate).exists()
        )


class TestSendPostbackFailedAlert(TestCase):
    @patch("messaging.signals_cpa.postback_failed.send")
    def test_sends_signal_with_correct_kwargs(self, mock_send):
        send_postback_failed_alert(
            affiliate_id=7, offer_id=42, offer_name="Gaming App",
            error_detail="Timeout connecting to network",
        )
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["affiliate_id"], 7)
        self.assertEqual(kwargs["offer_id"], 42)
        self.assertEqual(kwargs["error_detail"], "Timeout connecting to network")

    @patch("messaging.signals_cpa.postback_failed.send")
    def test_does_not_raise_when_signal_send_fails(self, mock_send):
        mock_send.side_effect = Exception("boom")
        try:
            send_postback_failed_alert(affiliate_id=7, offer_id=42, offer_name="x")
        except Exception as exc:
            self.fail(f"send_postback_failed_alert raised unexpectedly: {exc}")


class TestInjectConversionContextToChat(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()
        self.manager = UserFactory()
        self.chat = InternalChatFactory()

    def _make_thread(self):
        from ..models import AffiliateConversationThread
        return AffiliateConversationThread.objects.create(
            affiliate=self.affiliate, manager=self.manager, chat=self.chat,
        )

    def test_creates_system_message_when_thread_exists(self):
        from ..models import ChatMessage
        self._make_thread()
        inject_conversion_context_to_chat(
            affiliate_id=self.affiliate.pk, conversion_id="conv1",
            offer_id=42, offer_name="Gaming App", payout_amount="$3.00",
        )
        msg = ChatMessage.objects.filter(chat=self.chat, message_type="SYSTEM").first()
        self.assertIsNotNone(msg)
        self.assertIn("Gaming App", msg.content)
        self.assertIn("$3.00", msg.content)
        self.assertEqual(msg.metadata["event"], "conversion")
        self.assertEqual(msg.metadata["conversion_id"], "conv1")

    def test_does_nothing_when_no_thread_exists(self):
        from ..models import ChatMessage
        before = ChatMessage.objects.count()
        inject_conversion_context_to_chat(
            affiliate_id=self.affiliate.pk, conversion_id="conv1",
            offer_id=42, offer_name="x", payout_amount="$1.00",
        )
        self.assertEqual(ChatMessage.objects.count(), before)

    def test_does_not_raise_on_unexpected_error(self):
        with patch(
            "messaging.models.AffiliateConversationThread.objects.get",
            side_effect=Exception("db error"),
        ):
            try:
                inject_conversion_context_to_chat(
                    affiliate_id=self.affiliate.pk, conversion_id="conv1",
                    offer_id=42, offer_name="x", payout_amount="$1.00",
                )
            except Exception as exc:
                self.fail(f"inject_conversion_context_to_chat raised unexpectedly: {exc}")
