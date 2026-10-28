"""
test_views_extra_exception_paths.py
======================================
Targets the generic `except Exception as exc: return _err(exc, 500)` tail
present in nearly every view in views_extra.py. Each test mocks the one
external call that view makes to raise, confirming the view degrades to a
clean 500 instead of leaking a traceback.

Place in: messaging/tests/test_views_extra_exception_paths.py
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import InternalChatFactory, ChatParticipantFactory, ChatMessageFactory, UserFactory
from ..models import ScheduledMessage, AffiliateConversationThread, MessageLinkPreview
from django.utils import timezone
from datetime import timedelta


def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def _admin():
    return UserFactory(is_staff=True, is_superuser=True)


class TestViewsExtraExceptionPaths(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.admin = _admin()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.admin)

    def _assert_500(self, target, method, url, data=None, user=None):
        with patch(target, side_effect=RuntimeError("boom")):
            client = _api(user or self.user)
            resp = getattr(client, method)(url, data or {}, format="json")
        self.assertEqual(resp.status_code, 500)

    def test_spam_check(self):
        self._assert_500(
            "messaging.utils.spam_detector.analyze_message", "post",
            "/messaging/moderation/spam-check/", {"message": "hi"},
        )

    def test_toxicity_check(self):
        self._assert_500(
            "messaging.utils.spam_detector.check_toxicity", "post",
            "/messaging/moderation/toxicity/", {"message": "hi"},
        )

    def test_duplicate_check(self):
        self._assert_500(
            "messaging.utils.spam_detector.check_duplicate_message", "post",
            "/messaging/moderation/duplicate/", {"message": "hi"},
        )

    def test_language_detect(self):
        self._assert_500(
            "messaging.utils.translator.detect_language", "post",
            "/messaging/translate/detect/", {"text": "hi"},
        )

    def test_auto_moderate(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="hi")
        self._assert_500(
            "messaging.utils.spam_detector.should_auto_moderate", "post",
            "/messaging/moderation/auto-moderate/", {"message_id": str(msg.id)},
            user=self.admin,
        )

    def test_offer_card(self):
        self._assert_500(
            "messaging.utils.offer_context.build_offer_card_message", "post",
            "/messaging/offers/card/", {"offer": {"id": "1", "name": "N"}},
        )

    def test_offer_stats_summary(self):
        self._assert_500(
            "messaging.utils.offer_context.build_stats_summary_message", "get",
            "/messaging/offers/stats/",
        )

    def test_payout_card(self):
        self._assert_500(
            "messaging.utils.offer_context.build_payout_card_message", "get",
            "/messaging/offers/payout/?payout_id=p1&amount=1",
        )

    def test_offer_recommend(self):
        self._assert_500(
            "messaging.utils.offer_context.send_offer_recommendation_message", "post",
            "/messaging/offers/recommend/",
            {"offer_id": "o1", "offer_name": "N", "chat_id": str(self.chat.id)},
            user=self.admin,
        )

    def test_postback_conversion(self):
        self._assert_500(
            "messaging.utils.postback_tracker.notify_conversion_via_ws", "post",
            "/messaging/postback/conversion/",
            {"affiliate_id": self.user.pk, "offer_id": "o1", "offer_name": "N",
             "payout_amount": "1", "conversion_id": "c1"},
            user=self.admin,
        )

    def test_postback_alert(self):
        with patch(
            "messaging.utils.postback_tracker.send_postback_failed_alert",
            side_effect=RuntimeError("boom"),
        ):
            resp = _api(self.admin).get(
                f"/messaging/postback/alerts/?affiliate_id={self.user.pk}"
                "&offer_id=o1&offer_name=N"
            )
        self.assertEqual(resp.status_code, 500)

    def test_postback_inject(self):
        AffiliateConversationThread.objects.create(affiliate=self.user, chat=self.chat)
        self._assert_500(
            "messaging.utils.postback_tracker.inject_conversion_context_to_chat", "post",
            "/messaging/postback/inject/",
            {"affiliate_id": self.user.pk, "conversion_data": {
                "conversion_id": "c1", "offer_id": "o1", "offer_name": "N", "payout_amount": "1",
            }},
            user=self.admin,
        )

    def test_rate_limit_status(self):
        self._assert_500(
            "messaging.utils.rate_limiter.sliding_window_check", "get",
            "/messaging/rate-limit/status/",
        )

    def test_rate_limit_block(self):
        self._assert_500(
            "messaging.utils.rate_limiter.block_user_rate_limit", "post",
            "/messaging/rate-limit/block/", {"user_id": self.user.pk},
            user=self.admin,
        )

    def test_delivery_mark(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        with patch("messaging.utils.delivery_manager.mark_delivered", side_effect=RuntimeError("boom")):
            resp = _api(self.user).post("/messaging/delivery/mark/", {
                "message_ids": [str(msg.id)], "status": "delivered",
            }, format="json")
        # Per-message-id failures are caught individually; the bulk endpoint
        # still returns 200 with that id simply not counted as updated.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated"], 0)

    def test_unread_clear(self):
        self._assert_500(
            "messaging.utils.delivery_manager.clear_unread_cache", "post",
            "/messaging/delivery/clear-unread/", {"chat_id": str(self.chat.id)},
        )

    def test_poll_create(self):
        self._assert_500(
            "messaging.services.create_poll", "post",
            "/messaging/polls/",
            {"chat_id": str(self.chat.id), "question": "Q", "options": ["A", "B"]},
        )

    def test_poll_vote(self):
        self._assert_500(
            "messaging.services.vote_on_poll", "post",
            "/messaging/polls/vote/", {"message_id": "00000000-0000-0000-0000-000000000000", "option_id": "0"},
        )

    def test_broadcast_send(self):
        from .factories import AdminBroadcastFactory
        b = AdminBroadcastFactory(created_by=self.admin, status="DRAFT")
        self._assert_500(
            "messaging.services.send_broadcast", "post",
            f"/messaging/broadcasts/{b.pk}/send/", user=self.admin,
        )

    def test_broadcast_create(self):
        with patch("messaging.services.create_broadcast", side_effect=RuntimeError("boom")):
            resp = _api(self.admin).post(
                "/messaging/broadcasts/create/", {"title": "T", "body": "B"}, format="json"
            )
        self.assertEqual(resp.status_code, 400)

    def test_scheduled_send_now(self):
        sched = ScheduledMessage.objects.create(
            chat=self.chat, sender=self.admin, content="x",
            scheduled_for=timezone.now() + timedelta(hours=1), status="PENDING",
        )
        self._assert_500(
            "messaging.services.send_scheduled_message_now", "post",
            f"/messaging/scheduled/{sched.id}/send-now/",
            user=self.admin,
        )

    def test_push_test(self):
        from .factories import DeviceTokenFactory
        DeviceTokenFactory(user=self.user, platform="android", is_active=True)
        with patch("messaging.utils.device_push.send_fcm", side_effect=RuntimeError("boom")):
            resp = _api(self.admin).post(
                "/messaging/push/test/", {"user_id": self.user.pk}, format="json"
            )
        # Per-token send failures are caught individually and counted as
        # "failed" rather than crashing the whole request.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["failed"], 1)

    def test_fire_conversion_signal(self):
        self._assert_500(
            "messaging.utils.postback_tracker.fire_conversion_signal", "post",
            "/messaging/postback/fire-signal/",
            {"affiliate_id": self.user.pk, "offer_id": "o1", "offer_name": "N",
             "payout_amount": "1", "conversion_id": "c1"},
            user=self.admin,
        )

    def test_voice_transcription_status(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, message_type="AUDIO")
        self._assert_500(
            "messaging.models.VoiceMessageTranscription.objects.filter", "get",
            f"/messaging/voice/{msg.id}/transcription/",
        )

    def test_webrtc_room_id(self):
        self._assert_500(
            "messaging.utils.call_manager.generate_room_id", "get",
            "/messaging/calls/room/",
        )

    def test_webrtc_offer(self):
        callee = UserFactory()
        self._assert_500(
            "messaging.utils.call_manager.build_sdp_offer_payload", "post",
            "/messaging/calls/webrtc/offer/",
            {"room_id": "r1", "callee_id": str(callee.pk)},
        )

    def test_device_broadcast(self):
        # Audit fix (Part 19): was event_type="x" - DeviceBroadcastView
        # now allowlists event_type (see views_extra.py), so a fictional
        # value gets rejected with 400 before ever reaching the mocked
        # function below, which is what this test means to exercise.
        self._assert_500(
            "messaging.utils.device_sync.broadcast_to_all_user_devices", "post",
            "/messaging/devices/broadcast/", {"event_type": "chat.cross_device.read"},
        )

    def test_aggregated_presence(self):
        self._assert_500(
            "messaging.utils.device_sync.get_aggregated_presence", "get",
            "/messaging/devices/presence/",
        )

    def test_translate_text(self):
        self._assert_500(
            "messaging.utils.translator.translate_text", "post",
            "/messaging/translate/text/", {"text": "hi", "target_lang": "bn"},
        )
