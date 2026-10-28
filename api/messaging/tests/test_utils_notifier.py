"""
test_utils_notifier.py
========================
Tests for messaging/utils/notifier.py against its ACTUAL public API:
  notify_user_new_message, notify_user_support_reply, notify_broadcast_sent,
  notify_incoming_call, notify_reaction, notify_mention,
  send_websocket_event, _send_push_to_user (internal dispatcher)

Place in: messaging/tests/test_utils_notifier.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock

from django.test import TestCase

from .factories import DeviceTokenFactory, UserFactory
from ..utils.notifier import (
    notify_user_new_message,
    notify_user_support_reply,
    notify_broadcast_sent,
    notify_incoming_call,
    notify_reaction,
    notify_mention,
    send_websocket_event,
    _send_push_to_user,
)


class TestNotifyUserNewMessage(TestCase):
    def test_returns_false_when_user_id_is_none(self):
        self.assertFalse(
            notify_user_new_message(user_id=None, chat_id="c1", sender_name="Bob", preview="hi")
        )

    def test_returns_false_when_chat_id_is_none(self):
        self.assertFalse(
            notify_user_new_message(user_id=1, chat_id=None, sender_name="Bob", preview="hi")
        )

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_dispatches_push_with_correct_payload(self, mock_send):
        mock_send.return_value = True
        result = notify_user_new_message(
            user_id=5, chat_id="c1", sender_name="Bob", preview="hello there"
        )
        self.assertTrue(result)
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 5)
        self.assertEqual(kwargs["title"], "New message from Bob")
        self.assertEqual(kwargs["data"]["type"], "chat_message")
        self.assertEqual(kwargs["data"]["chat_id"], "c1")

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_truncates_long_preview(self, mock_send):
        mock_send.return_value = True
        notify_user_new_message(user_id=5, chat_id="c1", sender_name="Bob", preview="x" * 200)
        body = mock_send.call_args.kwargs["body"]
        self.assertLessEqual(len(body), 80)

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_coerces_non_string_sender_name(self, mock_send):
        mock_send.return_value = True
        notify_user_new_message(user_id=5, chat_id="c1", sender_name=12345, preview="hi")
        self.assertIn("12345", mock_send.call_args.kwargs["title"])

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_coerces_non_string_preview(self, mock_send):
        mock_send.return_value = True
        notify_user_new_message(user_id=5, chat_id="c1", sender_name="Bob", preview=42)
        self.assertEqual(mock_send.call_args.kwargs["body"], "42")

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_returns_false_and_swallows_exception(self, mock_send):
        mock_send.side_effect = Exception("boom")
        result = notify_user_new_message(user_id=5, chat_id="c1", sender_name="Bob", preview="hi")
        self.assertFalse(result)


class TestNotifyUserSupportReply(TestCase):
    def test_returns_false_when_user_id_is_none(self):
        self.assertFalse(
            notify_user_support_reply(user_id=None, thread_id="t1", preview="hi")
        )

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_dispatches_with_thread_id(self, mock_send):
        mock_send.return_value = True
        result = notify_user_support_reply(user_id=5, thread_id="t1", preview="we fixed it")
        self.assertTrue(result)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["title"], "Support team replied")
        self.assertEqual(kwargs["data"]["thread_id"], "t1")

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_handles_none_preview(self, mock_send):
        mock_send.return_value = True
        notify_user_support_reply(user_id=5, thread_id="t1", preview=None)
        self.assertEqual(mock_send.call_args.kwargs["body"], "")

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_returns_false_and_swallows_exception(self, mock_send):
        mock_send.side_effect = Exception("boom")
        result = notify_user_support_reply(user_id=5, thread_id="t1", preview="hi")
        self.assertFalse(result)


class TestNotifyBroadcastSent(TestCase):
    def test_always_returns_true(self):
        self.assertTrue(notify_broadcast_sent(broadcast_id="b1", title="Promo"))


class TestNotifyIncomingCall(TestCase):
    def test_returns_false_when_user_id_is_none(self):
        self.assertFalse(
            notify_incoming_call(user_id=None, call_id="c1", caller_name="Bob", call_type="VOICE")
        )

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_dispatches_with_voip_push_type_and_high_priority(self, mock_send):
        mock_send.return_value = True
        result = notify_incoming_call(
            user_id=5, call_id="c1", caller_name="Bob", call_type="VIDEO"
        )
        self.assertTrue(result)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["priority"], "high")
        self.assertEqual(kwargs["apns_push_type"], "voip")
        self.assertIn("Bob", kwargs["body"])
        self.assertIn("video", kwargs["title"].lower())

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_returns_false_on_exception(self, mock_send):
        mock_send.side_effect = Exception("boom")
        result = notify_incoming_call(
            user_id=5, call_id="c1", caller_name="Bob", call_type="VOICE"
        )
        self.assertFalse(result)


class TestNotifyReaction(TestCase):
    def test_returns_false_when_user_id_is_none(self):
        self.assertFalse(
            notify_reaction(user_id=None, reactor_name="Bob", emoji="\U0001F44D", message_preview="hi")
        )

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_dispatches_with_emoji_in_title(self, mock_send):
        mock_send.return_value = True
        notify_reaction(user_id=5, reactor_name="Bob", emoji="\U0001F525", message_preview="nice")
        title = mock_send.call_args.kwargs["title"]
        self.assertIn("Bob", title)
        self.assertIn("\U0001F525", title)

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_returns_false_and_swallows_exception(self, mock_send):
        mock_send.side_effect = Exception("boom")
        result = notify_reaction(user_id=5, reactor_name="Bob", emoji="\U0001F44D", message_preview="hi")
        self.assertFalse(result)


class TestNotifyMention(TestCase):
    def test_returns_false_when_user_id_is_none(self):
        self.assertFalse(
            notify_mention(user_id=None, mentioner_name="Bob", chat_id="c1", preview="hi")
        )

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_dispatches_with_chat_id(self, mock_send):
        mock_send.return_value = True
        notify_mention(user_id=5, mentioner_name="Bob", chat_id="c1", preview="@you check this")
        kwargs = mock_send.call_args.kwargs
        self.assertIn("Bob", kwargs["title"])
        self.assertEqual(kwargs["data"]["chat_id"], "c1")

    @patch("messaging.utils.notifier._send_push_to_user")
    def test_returns_false_and_swallows_exception(self, mock_send):
        mock_send.side_effect = Exception("boom")
        result = notify_mention(user_id=5, mentioner_name="Bob", chat_id="c1", preview="hi")
        self.assertFalse(result)


class TestSendWebsocketEvent(TestCase):
    def test_returns_false_for_empty_group_name(self):
        self.assertFalse(send_websocket_event(group_name="", event_type="x", data={}))

    def test_returns_false_for_empty_event_type(self):
        self.assertFalse(send_websocket_event(group_name="g1", event_type="", data={}))

    def test_returns_false_when_channel_layer_not_configured(self):
        with patch("channels.layers.get_channel_layer", return_value=None):
            result = send_websocket_event(group_name="g1", event_type="chat.message", data={"a": 1})
        self.assertFalse(result)

    def test_sends_to_channel_layer_with_dotted_type_converted(self):
        mock_layer = MagicMock()
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_group_send = MagicMock()
                mock_a2s.return_value = mock_group_send
                result = send_websocket_event(
                    group_name="chat_1", event_type="chat.message", data={"text": "hi"}
                )
        self.assertTrue(result)
        mock_group_send.assert_called_once()
        args = mock_group_send.call_args[0]
        self.assertEqual(args[0], "chat_1")
        self.assertEqual(args[1]["type"], "chat_message")

    def test_returns_false_on_exception(self):
        with patch("channels.layers.get_channel_layer", side_effect=Exception("boom")):
            result = send_websocket_event(group_name="g1", event_type="x", data={})
        self.assertFalse(result)


class TestSendPushToUser(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_returns_false_when_no_active_tokens(self):
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertFalse(result)

    def test_ignores_inactive_tokens(self):
        DeviceTokenFactory(user=self.user, platform="android", is_active=False)
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertFalse(result)

    @patch("messaging.utils.device_push.send_fcm")
    def test_dispatches_to_android_via_fcm(self, mock_fcm):
        mock_fcm.return_value = True
        DeviceTokenFactory(user=self.user, platform="android")
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertTrue(result)
        mock_fcm.assert_called_once()

    @patch("messaging.utils.device_push.send_apns")
    def test_dispatches_to_ios_via_apns(self, mock_apns):
        mock_apns.return_value = True
        DeviceTokenFactory(user=self.user, platform="ios")
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertTrue(result)
        mock_apns.assert_called_once()

    @patch("messaging.utils.device_push.send_webpush")
    def test_dispatches_to_web_via_webpush(self, mock_webpush):
        mock_webpush.return_value = True
        DeviceTokenFactory(user=self.user, platform="web")
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertTrue(result)
        mock_webpush.assert_called_once()

    @patch("messaging.utils.device_push.send_expo_push")
    def test_dispatches_to_expo(self, mock_expo):
        mock_expo.return_value = True
        DeviceTokenFactory(user=self.user, platform="expo")
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertTrue(result)
        mock_expo.assert_called_once()

    @patch("messaging.utils.device_push.send_fcm")
    def test_updates_last_used_at_on_success(self, mock_fcm):
        mock_fcm.return_value = True
        token = DeviceTokenFactory(user=self.user, platform="android")
        self.assertIsNone(token.last_used_at)
        _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        token.refresh_from_db()
        self.assertIsNotNone(token.last_used_at)

    @patch("messaging.utils.device_push.send_fcm")
    def test_one_token_failing_does_not_block_others(self, mock_fcm):
        DeviceTokenFactory(user=self.user, platform="android")
        DeviceTokenFactory(user=self.user, platform="android")
        mock_fcm.side_effect = [False, True]
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertTrue(result)

    @patch("messaging.utils.device_push.send_fcm")
    def test_returns_false_when_all_tokens_fail(self, mock_fcm):
        mock_fcm.return_value = False
        DeviceTokenFactory(user=self.user, platform="android")
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertFalse(result)

    @patch("messaging.utils.device_push.send_fcm")
    def test_one_token_raising_does_not_block_others(self, mock_fcm):
        DeviceTokenFactory(user=self.user, platform="android")
        DeviceTokenFactory(user=self.user, platform="android")
        mock_fcm.side_effect = [Exception("boom"), True]
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertTrue(result)

    def test_unknown_platform_does_not_crash(self):
        DeviceTokenFactory(user=self.user, platform="blackberry")
        result = _send_push_to_user(user_id=self.user.pk, title="t", body="b")
        self.assertFalse(result)
