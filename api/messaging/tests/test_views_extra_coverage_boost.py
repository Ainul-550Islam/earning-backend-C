"""
test_views_extra_coverage_boost.py
=====================================
Comprehensive coverage for views_extra.py's ~33 view classes. Uses real
(mostly unmocked) calls into the underlying utils/services functions
wherever those are safe/local (crypto, spam detection, rate limiting,
call_manager, translator stub, offer_context) so that any parameter-name
mismatch between a view and its target function is caught by simply
running these tests -- this is how the bugs fixed in this session's audit
log were confirmed.

Place in: messaging/tests/test_views_extra_coverage_boost.py
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory, ChatMessageFactory,
    DeviceTokenFactory, AdminBroadcastFactory,
)
from ..models import (
    ChatMessage, ScheduledMessage, MessagingWebhook, VoiceMessageTranscription,
    AffiliateConversationThread, AdminBroadcast,
)


def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def _admin():
    return UserFactory(is_staff=True, is_superuser=True)


class TestE2EEncryptionViews(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_generate_identity_key(self):
        r = _api(self.user).post("/messaging/e2e/keys/", {}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("public_key", r.data)
        self.assertIn("encoded_public_key", r.data)

    def test_session_init_missing_fields(self):
        r = _api(self.user).post("/messaging/e2e/session/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_session_init_success(self):
        from ..utils.e2e_encryption import generate_identity_key_pair, encode_key
        s_priv, s_pub = generate_identity_key_pair()
        r_priv, r_pub = generate_identity_key_pair()
        _, r_signed_pub = generate_identity_key_pair()
        r = _api(self.user).post("/messaging/e2e/session/", {
            "sender_identity_priv": encode_key(s_priv),
            "sender_identity_pub": encode_key(s_pub),
            "recipient_identity_pub": encode_key(r_pub),
            "recipient_signed_prekey_pub": encode_key(r_signed_pub),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("shared_secret_encoded", r.data)


class TestModerationViews(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_spam_check_clean_message(self):
        r = _api(self.user).post("/messaging/moderation/spam-check/", {
            "message": "Hey, how are you doing today?",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_spam"])

    def test_spam_check_flags_keywords(self):
        r = _api(self.user).post("/messaging/moderation/spam-check/", {
            "message": "CLICK HERE NOW!!!! FREE MONEY GUARANTEED WIN CASH PRIZE",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spam_score", r.data)

    def test_toxicity_check_no_api_key_returns_not_toxic(self):
        r = _api(self.user).post("/messaging/moderation/toxicity/", {
            "message": "you are the worst",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_toxic"])

    def test_duplicate_check_first_time_not_duplicate(self):
        r = _api(self.user).post("/messaging/moderation/duplicate/", {
            "message": "unique message " + str(id(self)),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_duplicate"])

    def test_duplicate_check_requires_message(self):
        r = _api(self.user).post("/messaging/moderation/duplicate/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_auto_moderate_requires_message_id(self):
        admin = _admin()
        r = _api(admin).post("/messaging/moderation/auto-moderate/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_auto_moderate_not_found(self):
        admin = _admin()
        r = _api(admin).post("/messaging/moderation/auto-moderate/", {
            "message_id": "00000000-0000-0000-0000-000000000000",
        }, format="json")
        self.assertEqual(r.status_code, 404)

    def test_auto_moderate_clean_message_allowed(self):
        admin = _admin()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=admin)
        msg = ChatMessageFactory(chat=chat, sender=admin, content="hello there")
        r = _api(admin).post("/messaging/moderation/auto-moderate/", {
            "message_id": str(msg.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["action"], "allow")


class TestLanguageDetectView(TestCase):
    def test_requires_text(self):
        user = UserFactory()
        r = _api(user).post("/messaging/translate/detect/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_detects_language(self):
        user = UserFactory()
        r = _api(user).post("/messaging/translate/detect/", {"text": "Hello world"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("language_code", r.data)


class TestOfferContextViews(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.admin = _admin()

    def test_offer_card_requires_offer(self):
        r = _api(self.user).post("/messaging/offers/card/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_offer_card_success(self):
        r = _api(self.user).post("/messaging/offers/card/", {
            "offer": {"id": "off-1", "name": "Survey Offer", "payout_rate": "$5.00"},
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("card", r.data)

    def test_offer_stats_summary(self):
        r = _api(self.user).get("/messaging/offers/stats/")
        self.assertEqual(r.status_code, 200)

    def test_payout_card_requires_fields(self):
        r = _api(self.user).get("/messaging/offers/payout/")
        self.assertEqual(r.status_code, 400)

    def test_payout_card_success(self):
        r = _api(self.user).get("/messaging/offers/payout/?payout_id=p-1&amount=25.00")
        self.assertEqual(r.status_code, 200)
        self.assertIn("payout_card", r.data)

    def test_offer_recommend_requires_fields(self):
        r = _api(self.admin).post("/messaging/offers/recommend/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_offer_recommend_success(self):
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=self.admin)
        r = _api(self.admin).post("/messaging/offers/recommend/", {
            "offer_id": "off-2", "offer_name": "Cashback App", "chat_id": str(chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["sent"])


class TestPostbackViews(TestCase):
    def setUp(self):
        self.admin = _admin()

    def test_conversion_requires_all_fields(self):
        r = _api(self.admin).post("/messaging/postback/conversion/", {
            "affiliate_id": 1, "offer_id": "o1",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_conversion_success(self):
        affiliate = UserFactory()
        r = _api(self.admin).post("/messaging/postback/conversion/", {
            "affiliate_id": affiliate.pk, "offer_id": "o1", "offer_name": "Test Offer",
            "payout_amount": "3.50", "conversion_id": "conv-1",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("notified", r.data)

    def test_alert_requires_fields(self):
        r = _api(self.admin).get("/messaging/postback/alerts/?affiliate_id=1")
        self.assertEqual(r.status_code, 400)

    def test_alert_success(self):
        affiliate = UserFactory()
        r = _api(self.admin).get(
            f"/messaging/postback/alerts/?affiliate_id={affiliate.pk}&offer_id=o1&offer_name=Test"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["alert_fired"])

    def test_inject_requires_fields(self):
        r = _api(self.admin).post("/messaging/postback/inject/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_inject_success_with_existing_thread(self):
        affiliate = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=affiliate)
        AffiliateConversationThread.objects.create(affiliate=affiliate, chat=chat)
        r = _api(self.admin).post("/messaging/postback/inject/", {
            "affiliate_id": affiliate.pk,
            "conversion_data": {
                "conversion_id": "conv-2", "offer_id": "o2",
                "offer_name": "Another Offer", "payout_amount": "1.25",
            },
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["injected"])

    def test_fire_conversion_signal(self):
        affiliate = UserFactory()
        r = _api(self.admin).post("/messaging/postback/fire-signal/", {
            "affiliate_id": affiliate.pk, "offer_id": "o3", "offer_name": "Sig Offer",
            "payout_amount": "2.00", "conversion_id": "conv-3",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("receivers_count", r.data)


class TestRateLimitViews(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.admin = _admin()

    def test_status_returns_usage(self):
        r = _api(self.user).get("/messaging/rate-limit/status/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("used", r.data)
        self.assertIn("remaining", r.data)

    def test_block_requires_user_id(self):
        r = _api(self.admin).post("/messaging/rate-limit/block/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_block_success_returns_until(self):
        target = UserFactory()
        r = _api(self.admin).post("/messaging/rate-limit/block/", {
            "user_id": target.pk, "duration_seconds": 1800,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["blocked"])
        self.assertIsNotNone(r.data["until"])

    def test_unblock(self):
        target = UserFactory()
        r = _api(self.admin).post("/messaging/rate-limit/block/", {
            "user_id": target.pk, "unblock": True,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["blocked"])


class TestDeliveryUnreadViews(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_mark_delivered(self):
        r = _api(self.user).post("/messaging/delivery/mark/", {
            "message_ids": [str(self.msg.id)], "status": "delivered",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["updated"], 1)

    def test_mark_requires_message_ids(self):
        r = _api(self.user).post("/messaging/delivery/mark/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_mark_invalid_status(self):
        r = _api(self.user).post("/messaging/delivery/mark/", {
            "message_ids": [str(self.msg.id)], "status": "bogus",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_clear_unread_requires_chat_id(self):
        r = _api(self.user).post("/messaging/delivery/clear-unread/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_clear_unread_success(self):
        r = _api(self.user).post("/messaging/delivery/clear-unread/", {
            "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["cleared"])


class TestPollViews(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_create_poll_requires_fields(self):
        r = _api(self.user).post("/messaging/polls/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_create_poll_success(self):
        r = _api(self.user).post("/messaging/polls/", {
            "chat_id": str(self.chat.id), "question": "Best day for the call?",
            "options": ["Mon", "Tue", "Wed"],
        }, format="json")
        self.assertEqual(r.status_code, 201)

    def test_vote_requires_fields(self):
        r = _api(self.user).post("/messaging/polls/vote/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_vote_success(self):
        poll_resp = _api(self.user).post("/messaging/polls/", {
            "chat_id": str(self.chat.id), "question": "Pick one", "options": ["A", "B"],
        }, format="json")
        message_id = poll_resp.data["message_id"]
        r = _api(self.user).post("/messaging/polls/vote/", {
            "message_id": message_id, "option_id": "0",
        }, format="json")
        self.assertEqual(r.status_code, 200)


class TestBroadcastAndScheduledSendViews(TestCase):
    def setUp(self):
        self.admin = _admin()

    def test_broadcast_send_not_found(self):
        r = _api(self.admin).post("/messaging/broadcasts/00000000-0000-0000-0000-000000000000/send/")
        self.assertEqual(r.status_code, 404)

    def test_broadcast_create(self):
        r = _api(self.admin).post("/messaging/broadcasts/create/", {
            "title": "Update", "body": "New features live!",
        }, format="json")
        self.assertEqual(r.status_code, 201)

    def test_scheduled_send_now_not_found(self):
        r = _api(self.admin).post("/messaging/scheduled/00000000-0000-0000-0000-000000000000/send-now/")
        self.assertEqual(r.status_code, 404)

    def test_scheduled_send_now_success(self):
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=self.admin)
        sched = ScheduledMessage.objects.create(
            chat=chat, sender=self.admin, content="go",
            scheduled_for=timezone.now() + timedelta(hours=1), status="PENDING",
        )
        r = _api(self.admin).post(f"/messaging/scheduled/{sched.id}/send-now/")
        self.assertEqual(r.status_code, 200)


class TestPushTestView(TestCase):
    def setUp(self):
        self.admin = _admin()

    def test_requires_user_id(self):
        r = _api(self.admin).post("/messaging/push/test/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_no_active_tokens(self):
        target = UserFactory()
        r = _api(self.admin).post("/messaging/push/test/", {"user_id": target.pk}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data["sent"], 0)

    def test_sends_to_ios_and_android(self):
        target = UserFactory()
        DeviceTokenFactory(user=target, platform="ios", is_active=True)
        DeviceTokenFactory(user=target, platform="android", is_active=True)
        with patch("messaging.utils.device_push.send_apns", return_value=True), \
             patch("messaging.utils.device_push.send_fcm", return_value=True):
            r = _api(self.admin).post("/messaging/push/test/", {"user_id": target.pk}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["sent"], 2)


class TestVoiceTranscriptionStatusView(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, message_type="AUDIO")

    def test_message_not_found(self):
        r = _api(self.user).get(
            "/messaging/voice/00000000-0000-0000-0000-000000000000/transcription/"
        )
        self.assertEqual(r.status_code, 404)

    def test_no_transcription_yet_reports_processing(self):
        r = _api(self.user).get(f"/messaging/voice/{self.msg.id}/transcription/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "processing")

    def test_completed_transcription(self):
        VoiceMessageTranscription.objects.create(
            message=self.msg, transcribed_text="hello", is_processing=False,
        )
        r = _api(self.user).get(f"/messaging/voice/{self.msg.id}/transcription/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "done")

    def test_failed_transcription_is_reported_as_failed(self):
        # Regression test for the error/error_message field-name bug: a
        # transcription that failed must surface as "failed", not loop
        # forever as "processing".
        VoiceMessageTranscription.objects.create(
            message=self.msg, transcribed_text="", is_processing=False,
            error="download timed out",
        )
        r = _api(self.user).get(f"/messaging/voice/{self.msg.id}/transcription/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "failed")
        self.assertIn("timed out", r.data["error"])


class TestWebRTCViews(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_room_id(self):
        r = _api(self.user).get("/messaging/calls/room/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("room_id", r.data)

    def test_offer_requires_fields(self):
        r = _api(self.user).post("/messaging/calls/webrtc/offer/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_offer_success(self):
        callee = UserFactory()
        r = _api(self.user).post("/messaging/calls/webrtc/offer/", {
            "room_id": "room-1", "callee_id": str(callee.pk),
        }, format="json")
        self.assertEqual(r.status_code, 200)

    def test_answer_success(self):
        r = _api(self.user).post("/messaging/calls/webrtc/answer/", {
            "room_id": "room-1", "sdp": "fake-sdp-answer",
        }, format="json")
        self.assertEqual(r.status_code, 200)

    def test_ice_candidate_success(self):
        r = _api(self.user).post("/messaging/calls/webrtc/ice/", {
            "room_id": "room-1", "candidate": "fake-candidate",
        }, format="json")
        self.assertEqual(r.status_code, 200)


class TestDeviceSyncViews(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_broadcast_requires_event_type(self):
        r = _api(self.user).post("/messaging/devices/broadcast/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_broadcast_to_own_devices(self):
        # Audit fix (Part 19): was event_type="message.read", never a real
        # dispatchable handler name (see DeviceBroadcastView / Part 19 fix).
        DeviceTokenFactory(user=self.user, is_active=True)
        r = _api(self.user).post("/messaging/devices/broadcast/", {
            "event_type": "chat.cross_device.read", "data": {"chat_id": "x"},
        }, format="json")
        self.assertEqual(r.status_code, 200)

    def test_broadcast_to_others_denied_for_non_staff(self):
        other = UserFactory()
        r = _api(self.user).post("/messaging/devices/broadcast/", {
            "user_id": other.pk, "event_type": "chat.cross_device.read",
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_aggregated_presence(self):
        r = _api(self.user).get("/messaging/devices/presence/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("status", r.data)


class TestTranslateTextView(TestCase):
    def test_requires_fields(self):
        user = UserFactory()
        r = _api(user).post("/messaging/translate/text/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_translates_arbitrary_text(self):
        user = UserFactory()
        r = _api(user).post("/messaging/translate/text/", {
            "text": "Good morning", "target_lang": "bn",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("translated_text", r.data)
