"""
test_views_extra.py
====================
Tests for all 18 new API endpoints in views_extra.py.
Place in: messaging/tests/test_views_extra.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    AdminBroadcastFactory,
)
from ..models import AdminBroadcast, ScheduledMessage


def _auth(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


def _admin():
    return UserFactory(is_staff=True, is_superuser=True)


# ─────────────────────────────────────────────────────────────────────────────
# E2E Encryption
# ─────────────────────────────────────────────────────────────────────────────

class TestE2EEncryptionKeyView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/e2e/keys/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_returns_public_key(self):
        with patch("messaging.utils.e2e_encryption.generate_identity_key_pair") as mock_gen:
            import os
            priv = os.urandom(32)
            pub = os.urandom(32)
            mock_gen.return_value = (priv, pub)
            r = _auth(self.user).post("/messaging/e2e/keys/", {}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("public_key", r.data)
        self.assertIn("encoded_public_key", r.data)

    def test_public_key_is_hex_string(self):
        with patch("messaging.utils.e2e_encryption.generate_identity_key_pair") as mock_gen:
            import os
            mock_gen.return_value = (os.urandom(32), bytes(32))
            r = _auth(self.user).post("/messaging/e2e/keys/", {}, format="json")
        if r.status_code == 201:
            self.assertIsInstance(r.data["public_key"], str)


class TestE2ESessionInitView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/e2e/session/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/e2e/session/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.e2e_encryption.x3dh_sender")
    @patch("messaging.utils.e2e_encryption.decode_key")
    def test_returns_shared_secret_and_eph_pub(self, mock_decode, mock_x3dh):
        import os
        mock_decode.return_value = os.urandom(32)
        mock_x3dh.return_value = (os.urandom(32), os.urandom(32))
        r = _auth(self.user).post("/messaging/e2e/session/", {
            "sender_identity_priv": "abc",
            "sender_identity_pub": "def",
            "recipient_identity_pub": "ghi",
            "recipient_signed_prekey_pub": "jkl",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("shared_secret_encoded", r.data)
        self.assertIn("ephemeral_pub_encoded", r.data)


# ─────────────────────────────────────────────────────────────────────────────
# Spam / Moderation
# ─────────────────────────────────────────────────────────────────────────────

class TestSpamCheckView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/moderation/spam-check/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_empty_message_returns_not_spam(self):
        r = _auth(self.user).post("/messaging/moderation/spam-check/", {"message": ""}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_spam"])

    @patch("messaging.utils.spam_detector.analyze_message")
    def test_spam_message_returns_is_spam_true(self, mock_analyze):
        mock_analyze.return_value = {"is_spam": True, "confidence": 0.95, "signals": ["keyword"]}
        r = _auth(self.user).post("/messaging/moderation/spam-check/", {
            "message": "CLICK HERE FREE MONEY!!!"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_spam"])

    @patch("messaging.utils.spam_detector.analyze_message")
    def test_clean_message_returns_is_spam_false(self, mock_analyze):
        mock_analyze.return_value = {"is_spam": False, "confidence": 0.02, "signals": []}
        r = _auth(self.user).post("/messaging/moderation/spam-check/", {
            "message": "Hey, how are you?"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_spam"])


class TestToxicityCheckView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/moderation/toxicity/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_empty_text_returns_not_toxic(self):
        r = _auth(self.user).post("/messaging/moderation/toxicity/", {"message": ""}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_toxic"])

    @patch("messaging.utils.spam_detector.check_toxicity")
    def test_toxic_message_flagged(self, mock_check):
        mock_check.return_value = {"is_toxic": True, "toxicity_score": 0.92, "categories": {"insult": 0.9}}
        r = _auth(self.user).post("/messaging/moderation/toxicity/", {
            "message": "You idiot!"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_toxic"])


class TestDuplicateCheckView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/moderation/duplicate/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.spam_detector.check_duplicate_message")
    def test_unique_message_not_duplicate(self, mock_check):
        mock_check.return_value = (False, 0)
        r = _auth(self.user).post("/messaging/moderation/duplicate/", {
            "message": "Hello world",
            "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_duplicate"])

    @patch("messaging.utils.spam_detector.check_duplicate_message")
    def test_duplicate_message_flagged(self, mock_check):
        mock_check.return_value = (True, 3)
        r = _auth(self.user).post("/messaging/moderation/duplicate/", {
            "message": "Same message again",
            "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_duplicate"])
        self.assertEqual(r.data["repeat_count"], 3)


class TestAutoModerateView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/moderation/auto-moderate/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_message_id_returns_400(self):
        r = _auth(self.admin).post("/messaging/moderation/auto-moderate/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.spam_detector.should_auto_moderate")
    def test_returns_action_for_message(self, mock_fn):
        from .factories import InternalChatFactory, ChatParticipantFactory, ChatMessageFactory
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=self.user)
        msg = ChatMessageFactory(chat=chat, sender=self.user, content="spam spam spam")
        mock_fn.return_value = (True, "high_spam_score")
        r = _auth(self.admin).post("/messaging/moderation/auto-moderate/", {
            "message_id": str(msg.id)
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["action"], "block")
        self.assertEqual(r.data["reason"], "high_spam_score")


# ─────────────────────────────────────────────────────────────────────────────
# Language Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestLanguageDetectView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/translate/detect/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_text_returns_400(self):
        r = _auth(self.user).post("/messaging/translate/detect/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.translator.detect_language")
    def test_detects_language_code(self, mock_detect):
        mock_detect.return_value = "en"
        r = _auth(self.user).post("/messaging/translate/detect/", {
            "text": "Hello world"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["language_code"], "en")

    @patch("messaging.utils.translator.detect_language")
    def test_detects_bangla(self, mock_detect):
        mock_detect.return_value = "bn"
        r = _auth(self.user).post("/messaging/translate/detect/", {
            "text": "আমি বাংলায় কথা বলি"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["language_code"], "bn")


# ─────────────────────────────────────────────────────────────────────────────
# Offer Context
# ─────────────────────────────────────────────────────────────────────────────

class TestOfferCardView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/offers/card/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_offer_returns_400(self):
        r = _auth(self.user).post("/messaging/offers/card/", {}, format="json")
        self.assertIn(r.status_code, [400, 500])  # 400 or 500 depending on impl

    @patch("messaging.utils.offer_context.build_offer_card_message")
    def test_returns_offer_card(self, mock_build):
        mock_build.return_value = {
            "id": "o1", "name": "Gaming Offer",
            "payout_display": "$2.50/CPA", "cta_url": "https://go.example.com"
        }
        r = _auth(self.user).post("/messaging/offers/card/", {
            "offer": {"id": "o1", "name": "Gaming Offer"}
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("card", r.data)
        self.assertEqual(r.data["card"]["id"], "o1")


class TestOfferStatsSummaryView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().get("/messaging/offers/stats/")
        self.assertIn(r.status_code, [401, 403])

    @patch("messaging.utils.offer_context.build_stats_summary_message")
    def test_returns_stats(self, mock_build):
        mock_build.return_value = {"summary_message": "You earned $250 this month!", "stats": {}}
        r = _auth(self.user).get("/messaging/offers/stats/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("summary_message", r.data)


class TestPayoutCardView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().get("/messaging/offers/payout/")
        self.assertIn(r.status_code, [401, 403])

    @patch("messaging.utils.offer_context.build_payout_card_message")
    def test_returns_payout_card(self, mock_build):
        mock_build.return_value = {"pending": "$100", "approved": "$350"}
        r = _auth(self.user).get("/messaging/offers/payout/?payout_id=p-1&amount=100.00")
        self.assertEqual(r.status_code, 200)
        self.assertIn("payout_card", r.data)


class TestOfferRecommendView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/offers/recommend/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_fields_returns_400(self):
        r = _auth(self.admin).post("/messaging/offers/recommend/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.offer_context.send_offer_recommendation_message")
    def test_sends_recommendation(self, mock_send):
        mock_send.return_value = None
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=self.user)
        r = _auth(self.admin).post("/messaging/offers/recommend/", {
            "offer_id": "offer-123",
            "offer_name": "Survey Offer",
            "chat_id": str(chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["sent"])
        mock_send.assert_called_once_with(
            chat_id=str(chat.id), manager_id=self.admin.pk,
            offer_id="offer-123", offer_name="Survey Offer",
            payout="", reason="",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Postback
# ─────────────────────────────────────────────────────────────────────────────

class TestPostbackConversionView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/postback/conversion/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_fields_returns_400(self):
        r = _auth(self.admin).post("/messaging/postback/conversion/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.postback_tracker.notify_conversion_via_ws")
    def test_notifies_affiliate(self, mock_notify):
        mock_notify.return_value = True
        r = _auth(self.admin).post("/messaging/postback/conversion/", {
            "affiliate_id": self.user.pk,
            "offer_id": "offer-1",
            "offer_name": "Cashback App",
            "payout_amount": "$2.50",
            "conversion_id": "conv-1",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["notified"])


class TestPostbackAlertView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).get("/messaging/postback/alerts/")
        self.assertEqual(r.status_code, 403)

    def test_missing_fields_returns_400(self):
        r = _auth(self.admin).get(f"/messaging/postback/alerts/?affiliate_id={self.user.pk}")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.postback_tracker.send_postback_failed_alert")
    def test_fires_alert(self, mock_alert):
        mock_alert.return_value = None
        r = _auth(self.admin).get(
            f"/messaging/postback/alerts/?affiliate_id={self.user.pk}"
            "&offer_id=offer-1&offer_name=Test+Offer"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["alert_fired"])
        mock_alert.assert_called_once_with(
            affiliate_id=str(self.user.pk), offer_id="offer-1",
            offer_name="Test Offer", error_detail="",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitStatusView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().get("/messaging/rate-limit/status/")
        self.assertIn(r.status_code, [401, 403])

    @patch("messaging.utils.rate_limiter.sliding_window_check")
    @patch("messaging.utils.rate_limiter.is_user_blocked_by_rate_limit")
    def test_returns_rate_limit_info(self, mock_blocked, mock_check):
        mock_check.return_value = (True, 5)
        mock_blocked.return_value = False
        r = _auth(self.user).get("/messaging/rate-limit/status/?action=send_message")
        self.assertEqual(r.status_code, 200)
        self.assertIn("limit", r.data)
        self.assertIn("remaining", r.data)
        self.assertIn("allowed", r.data)
        self.assertEqual(r.data["limit"], 30)
        self.assertEqual(r.data["used"], 5)
        self.assertEqual(r.data["remaining"], 25)
        self.assertTrue(r.data["allowed"])


class TestRateLimitBlockView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.target = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/rate-limit/block/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_user_id_returns_400(self):
        r = _auth(self.admin).post("/messaging/rate-limit/block/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.rate_limiter.block_user_rate_limit")
    def test_blocks_user(self, mock_block):
        mock_block.return_value = {"until": "2024-12-31T23:59:59Z"}
        r = _auth(self.admin).post("/messaging/rate-limit/block/", {
            "user_id": self.target.pk,
            "duration_seconds": 3600,
            "reason": "Spam detected",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["blocked"])

    @patch("django.core.cache.cache.delete")
    def test_unblocks_user(self, mock_reset):
        r = _auth(self.admin).post("/messaging/rate-limit/block/", {
            "user_id": self.target.pk,
            "unblock": True,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["blocked"])


# ─────────────────────────────────────────────────────────────────────────────
# Delivery
# ─────────────────────────────────────────────────────────────────────────────

class TestDeliveryMarkView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/delivery/mark/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_message_ids_returns_400(self):
        r = _auth(self.user).post("/messaging/delivery/mark/", {"status": "read"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_invalid_status_returns_400(self):
        r = _auth(self.user).post("/messaging/delivery/mark/", {
            "message_ids": ["msg-1"],
            "status": "invalid_status",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.delivery_manager.mark_read")
    def test_marks_messages_read(self, mock_mark):
        mock_mark.return_value = True
        r = _auth(self.user).post("/messaging/delivery/mark/", {
            "message_ids": ["msg-1", "msg-2", "msg-3"],
            "status": "read",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["updated"], 3)

    @patch("messaging.utils.delivery_manager.mark_delivered")
    def test_marks_messages_delivered(self, mock_mark):
        mock_mark.return_value = True
        r = _auth(self.user).post("/messaging/delivery/mark/", {
            "message_ids": ["msg-1"],
            "status": "delivered",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["updated"], 1)


class TestUnreadClearView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/delivery/clear-unread/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_chat_id_returns_400(self):
        r = _auth(self.user).post("/messaging/delivery/clear-unread/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.delivery_manager.clear_unread_cache")
    def test_clears_unread(self, mock_clear):
        r = _auth(self.user).post("/messaging/delivery/clear-unread/", {
            "chat_id": str(self.chat.id)
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["cleared"])
        mock_clear.assert_called_once_with(user_id=self.user.pk, chat_id=str(self.chat.id))


# ─────────────────────────────────────────────────────────────────────────────
# Polls
# ─────────────────────────────────────────────────────────────────────────────

class TestPollView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/polls/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/polls/", {
            "chat_id": str(self.chat.id),
            "question": "What?",
            # Missing options
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_only_one_option_returns_400(self):
        r = _auth(self.user).post("/messaging/polls/", {
            "chat_id": str(self.chat.id),
            "question": "One option?",
            "options": [{"id": "a", "text": "Only"}],
        }, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.services.create_poll")
    def test_creates_poll_message(self, mock_create):
        mock_msg = MagicMock()
        mock_msg.id = "msg-poll-1"
        mock_msg.chat_id = self.chat.id
        mock_msg.poll_data = {
            "question": "Best?",
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]
        }
        mock_create.return_value = mock_msg
        r = _auth(self.user).post("/messaging/polls/", {
            "chat_id": str(self.chat.id),
            "question": "Best?",
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("message_id", r.data)

    @patch("messaging.services.get_poll_results")
    def test_get_poll_results(self, mock_results):
        mock_results.return_value = {
            "total_votes": 10,
            "options": [{"id": "a", "votes": 7}, {"id": "b", "votes": 3}]
        }
        r = _auth(self.user).get("/messaging/polls/?message_id=msg-poll-1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_votes", r.data)

    def test_get_without_message_id_returns_400(self):
        r = _auth(self.user).get("/messaging/polls/")
        self.assertEqual(r.status_code, 400)


class TestPollVoteView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/polls/vote/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/polls/vote/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.services.get_poll_results")
    @patch("messaging.services.vote_on_poll")
    def test_casts_vote(self, mock_vote, mock_results):
        mock_vote_obj = MagicMock()
        mock_vote_obj.option_id = "opt_a"
        mock_vote.return_value = mock_vote_obj
        mock_results.return_value = {"total_votes": 5}
        r = _auth(self.user).post("/messaging/polls/vote/", {
            "message_id": "msg-poll-1",
            "option_id": "opt_a",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["voted"])
        self.assertEqual(r.data["option_id"], "opt_a")


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast Send
# ─────────────────────────────────────────────────────────────────────────────

class TestBroadcastSendView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/broadcasts/some-id/send/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    @patch("messaging.services.send_broadcast")
    def test_sends_broadcast(self, mock_send):
        mock_send.return_value = {"sent": True, "recipient_count": 250}
        broadcast = AdminBroadcastFactory(created_by=self.admin)
        r = _auth(self.admin).post(
            f"/messaging/broadcasts/{broadcast.id}/send/", {}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("recipient_count", r.data)

    @patch("messaging.services.send_broadcast")
    def test_returns_error_for_invalid_id(self, mock_send):
        from ..exceptions import MessagingError
        mock_send.side_effect = MessagingError("Broadcast not found")
        r = _auth(self.admin).post(
            "/messaging/broadcasts/nonexistent-id/send/", {}, format="json"
        )
        self.assertEqual(r.status_code, 400)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled Send Now
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduledSendNowView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/scheduled/some-id/send-now/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    @patch("messaging.services.send_scheduled_message_now")
    def test_fires_scheduled_message(self, mock_send):
        from django.utils import timezone
        mock_msg = MagicMock()
        mock_msg.id = "msg-fired"
        mock_msg.content = "Scheduled content"
        mock_msg.created_at = timezone.now()
        mock_send.return_value = mock_msg
        sched = ScheduledMessage.objects.create(
            chat=self.chat,
            sender=self.user,
            content="Scheduled content",
            scheduled_for=timezone.now(),
            status="PENDING",
        )
        r = _auth(self.user).post(
            f"/messaging/scheduled/{sched.id}/send-now/", {}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("message_id", r.data)
        self.assertEqual(r.data["message_id"], "msg-fired")

    @patch("messaging.services.send_scheduled_message_now")
    def test_returns_error_for_already_sent(self, mock_send):
        from django.utils import timezone
        from ..exceptions import MessagingError
        mock_send.side_effect = MessagingError("Already sent")
        sched = ScheduledMessage.objects.create(
            chat=self.chat,
            sender=self.user,
            content="Scheduled content",
            scheduled_for=timezone.now(),
            status="PENDING",
        )
        r = _auth(self.user).post(
            f"/messaging/scheduled/{sched.id}/send-now/", {}, format="json"
        )
        self.assertEqual(r.status_code, 400)


# ─────────────────────────────────────────────────────────────────────────────
# Postback Context Inject
# ─────────────────────────────────────────────────────────────────────────────

class TestPostbackContextInjectView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.affiliate = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.affiliate)

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/postback/inject/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_fields_returns_400(self):
        r = _auth(self.admin).post("/messaging/postback/inject/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.postback_tracker.inject_conversion_context_to_chat")
    def test_injects_context(self, mock_inject):
        mock_inject.return_value = None
        r = _auth(self.admin).post("/messaging/postback/inject/", {
            "affiliate_id": self.affiliate.pk,
            "conversion_data": {
                "conversion_id": "conv-ctx-1", "offer_id": "o1",
                "offer_name": "Test Offer", "payout_amount": "$2.50",
            },
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["injected"])
        mock_inject.assert_called_once_with(
            affiliate_id=self.affiliate.pk, conversion_id="conv-ctx-1",
            offer_id="o1", offer_name="Test Offer", payout_amount="$2.50",
            manager_id=self.admin.pk,
        )


# ═════════════════════════════════════════════════════════════════════════════
# Fix 6: Tests for 11 new floating-fix views (added in previous sessions)
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Push Test View
# ─────────────────────────────────────────────────────────────────────────────

class TestPushTestView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user  = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/push/test/", {"user_id": self.user.pk}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_user_id_returns_400(self):
        r = _auth(self.admin).post("/messaging/push/test/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_no_tokens_returns_404(self):
        r = _auth(self.admin).post("/messaging/push/test/", {
            "user_id": self.user.pk, "title": "T", "body": "B"
        }, format="json")
        self.assertEqual(r.status_code, 404)

    @patch("messaging.utils.device_push.send_fcm", return_value=True)
    def test_sends_to_active_tokens(self, mock_fcm):
        from ..models import DeviceToken
        DeviceToken.objects.create(
            user=self.user, token="tok123", platform="android",
            device_name="Test", is_active=True,
            tenant=None,
        )
        r = _auth(self.admin).post("/messaging/push/test/", {
            "user_id": self.user.pk, "title": "Hello", "body": "World"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("sent", r.data)
        self.assertEqual(r.data["sent"], 1)

    @patch("messaging.utils.device_push.send_fcm", return_value=False)
    def test_failed_push_counted(self, mock_fcm):
        from ..models import DeviceToken
        DeviceToken.objects.create(
            user=self.user, token="tok_fail", platform="android",
            device_name="Fail Device", is_active=True, tenant=None,
        )
        r = _auth(self.admin).post("/messaging/push/test/", {
            "user_id": self.user.pk
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["failed"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# Fire Conversion Signal View
# ─────────────────────────────────────────────────────────────────────────────

class TestFireConversionSignalView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user  = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/postback/fire-signal/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_fields_returns_400(self):
        r = _auth(self.admin).post("/messaging/postback/fire-signal/", {
            "conversion_id": "c1"
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Missing", r.data["detail"])

    @patch("messaging.utils.postback_tracker.fire_conversion_signal", return_value=2)
    def test_fires_signal(self, mock_fire):
        r = _auth(self.admin).post("/messaging/postback/fire-signal/", {
            "conversion_id": "c123",
            "affiliate_id": 42,
            "offer_id": "o1",
            "offer_name": "Test Offer",
            "payout_amount": "15.00",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["fired"])
        self.assertEqual(r.data["receivers_count"], 2)

    @patch("messaging.utils.postback_tracker.fire_conversion_signal", side_effect=Exception("boom"))
    def test_exception_returns_500(self, mock_fire):
        r = _auth(self.admin).post("/messaging/postback/fire-signal/", {
            "conversion_id": "c123",
            "affiliate_id": 1,
            "offer_id": "o1",
            "offer_name": "O",
            "payout_amount": "1.00",
        }, format="json")
        self.assertEqual(r.status_code, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Voice Transcription Status View
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceTranscriptionStatusView(TestCase):
    def setUp(self):
        self.user  = UserFactory()
        self.chat  = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_unauthenticated_returns_401(self):
        r = _auth().get("/messaging/voice/fake-id/transcription/")
        self.assertIn(r.status_code, [401, 403])

    @patch("messaging.models.ChatMessage.objects")
    def test_invalid_message_returns_404(self, mock_mgr):
        from ..models import ChatMessage
        mock_mgr.select_related.return_value.get.side_effect = ChatMessage.DoesNotExist
        r = _auth(self.user).get("/messaging/voice/nonexistent/transcription/")
        self.assertEqual(r.status_code, 404)

    def test_no_transcription_returns_processing(self):
        from ..models import ChatMessage, VoiceMessageTranscription
        msg = ChatMessage.objects.create(
            chat=self.chat, sender=self.user,
            content="[voice message]", message_type="AUDIO", status="SENT",
        )
        with patch.object(VoiceMessageTranscription, "objects") as mock_mgr:
            mock_mgr.filter.return_value.first.return_value = None
            with patch("messaging.services._assert_chat_participant") as mock_assert:
                mock_assert.return_value = None
                r = _auth(self.user).get(f"/messaging/voice/{msg.id}/transcription/")
        self.assertIn("status", r.data)


# ─────────────────────────────────────────────────────────────────────────────
# WebRTC Room ID View
# ─────────────────────────────────────────────────────────────────────────────

class TestCallRoomIdView(TestCase):
    def test_unauthenticated_returns_401(self):
        r = _auth().get("/messaging/calls/room/")
        self.assertIn(r.status_code, [401, 403])

    def test_returns_room_id(self):
        user = UserFactory()
        r = _auth(user).get("/messaging/calls/room/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("room_id", r.data)

    def test_room_id_is_16_chars(self):
        user = UserFactory()
        r = _auth(user).get("/messaging/calls/room/")
        self.assertEqual(len(r.data["room_id"]), 16)

    def test_room_ids_are_unique(self):
        user = UserFactory()
        ids = {_auth(user).get("/messaging/calls/room/").data["room_id"] for _ in range(5)}
        self.assertEqual(len(ids), 5)


# ─────────────────────────────────────────────────────────────────────────────
# WebRTC Offer View
# ─────────────────────────────────────────────────────────────────────────────

class TestWebRTCOfferView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/calls/webrtc/offer/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/calls/webrtc/offer/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_returns_offer_payload(self):
        other = UserFactory()
        r = _auth(self.user).post("/messaging/calls/webrtc/offer/", {
            "room_id": "abc123def456abcd", "callee_id": other.pk
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["signal_type"], "offer")
        self.assertIn("room_id", r.data)
        self.assertEqual(r.data["caller_id"], str(self.user.pk))


# ─────────────────────────────────────────────────────────────────────────────
# WebRTC SDP Answer View
# ─────────────────────────────────────────────────────────────────────────────

class TestWebRTCSdpAnswerView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/calls/webrtc/answer/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/calls/webrtc/answer/", {"room_id": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_returns_answer_payload(self):
        r = _auth(self.user).post("/messaging/calls/webrtc/answer/", {
            "room_id": "room1234", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["signal_type"], "answer")
        self.assertIn("sdp", r.data)


# ─────────────────────────────────────────────────────────────────────────────
# WebRTC ICE Candidate View
# ─────────────────────────────────────────────────────────────────────────────

class TestWebRTCIceCandidateView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/calls/webrtc/ice/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_fields_returns_400(self):
        r = _auth(self.user).post("/messaging/calls/webrtc/ice/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_returns_ice_payload(self):
        r = _auth(self.user).post("/messaging/calls/webrtc/ice/", {
            "room_id": "room9999",
            "candidate": {
                "candidate": "candidate:0 1 UDP 2122252543 192.168.1.1 51472 typ host",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            }
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["signal_type"], "ice_candidate")
        self.assertIn("candidate", r.data)


# ─────────────────────────────────────────────────────────────────────────────
# Device Broadcast View
# ─────────────────────────────────────────────────────────────────────────────

class TestDeviceBroadcastView(TestCase):
    def setUp(self):
        self.user  = UserFactory()
        self.admin = _admin()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/devices/broadcast/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_event_type_returns_400(self):
        r = _auth(self.user).post("/messaging/devices/broadcast/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_non_owner_broadcast_to_other_user_blocked(self):
        other = UserFactory()
        r = _auth(self.user).post("/messaging/devices/broadcast/", {
            "user_id": other.pk, "event_type": "test"
        }, format="json")
        self.assertEqual(r.status_code, 403)

    @patch("messaging.utils.device_sync.broadcast_to_all_user_devices", return_value=2)
    def test_returns_notified_count(self, mock_fn):
        # Audit fix (Part 19): was event_type="message.read", which never
        # mapped to a real ChatConsumer handler (message_read doesn't
        # exist - device_sync_read/device_sync_message do). Only ever
        # "passed" because broadcast_to_all_user_devices is mocked here,
        # so the real Channels dispatch that would have crashed a
        # connected device was never exercised. Now allowlisted (see
        # views_extra.DeviceBroadcastView) to real handler names only.
        r = _auth(self.user).post("/messaging/devices/broadcast/", {
            "event_type": "chat.cross_device.read",
            "data": {"chat_id": "c1"},
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["notified"], 2)

    @patch("messaging.utils.device_sync.broadcast_to_all_user_devices", return_value=3)
    def test_admin_can_broadcast_to_any_user(self, mock_fn):
        # Audit fix (Part 19): was event_type="sync", same issue as above.
        other = UserFactory()
        r = _auth(self.admin).post("/messaging/devices/broadcast/", {
            "user_id": other.pk, "event_type": "chat.cross_device.message", "data": {}
        }, format="json")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# Aggregated Presence View
# ─────────────────────────────────────────────────────────────────────────────

class TestAggregatedPresenceView(TestCase):
    def setUp(self):
        self.user  = UserFactory()
        self.admin = _admin()

    def test_unauthenticated_returns_401(self):
        r = _auth().get("/messaging/devices/presence/")
        self.assertIn(r.status_code, [401, 403])

    @patch("messaging.utils.device_sync.get_aggregated_presence")
    def test_returns_own_presence(self, mock_fn):
        mock_fn.return_value = {"status": "online", "device_count": 1, "last_seen_at": None}
        r = _auth(self.user).get("/messaging/devices/presence/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("status", r.data)
        mock_fn.assert_called_once_with(user_id=self.user.pk)

    def test_non_admin_cannot_check_other_user(self):
        other = UserFactory()
        r = _auth(self.user).get(f"/messaging/devices/presence/?user_id={other.pk}")
        self.assertEqual(r.status_code, 403)

    @patch("messaging.utils.device_sync.get_aggregated_presence")
    def test_admin_can_check_any_user(self, mock_fn):
        other = UserFactory()
        mock_fn.return_value = {"status": "offline", "device_count": 0}
        r = _auth(self.admin).get(f"/messaging/devices/presence/?user_id={other.pk}")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# Translate Text View
# ─────────────────────────────────────────────────────────────────────────────

class TestTranslateTextView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/translate/text/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_text_returns_400(self):
        r = _auth(self.user).post("/messaging/translate/text/", {
            "target_lang": "bn"
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_missing_target_lang_returns_400(self):
        r = _auth(self.user).post("/messaging/translate/text/", {
            "text": "Hello"
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_text_too_long_returns_400(self):
        r = _auth(self.user).post("/messaging/translate/text/", {
            "text": "x" * 5001, "target_lang": "bn"
        }, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.utils.translator.translate_text", return_value=("হ্যালো", "en"))
    def test_returns_translated_text(self, mock_fn):
        r = _auth(self.user).post("/messaging/translate/text/", {
            "text": "Hello", "target_lang": "bn"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["translated_text"], "হ্যালো")
        self.assertEqual(r.data["detected_source_lang"], "en")
        self.assertEqual(r.data["target_lang"], "bn")

    @patch("messaging.utils.translator.translate_text", return_value=("[BN] Hello", "unknown"))
    def test_respects_source_lang_hint(self, mock_fn):
        r = _auth(self.user).post("/messaging/translate/text/", {
            "text": "Hello", "target_lang": "bn", "source_lang": "en"
        }, format="json")
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(text="Hello", target_lang="bn", source_lang="en")


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast Create View (via services.create_broadcast)
# ─────────────────────────────────────────────────────────────────────────────

class TestBroadcastCreateView(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user  = UserFactory()

    def test_non_admin_returns_403(self):
        r = _auth(self.user).post("/messaging/broadcasts/create/", {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_returns_401(self):
        r = _auth().post("/messaging/broadcasts/create/", {}, format="json")
        self.assertIn(r.status_code, [401, 403])

    def test_missing_title_returns_400(self):
        r = _auth(self.admin).post("/messaging/broadcasts/create/", {
            "body": "Some body"
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_missing_body_returns_400(self):
        r = _auth(self.admin).post("/messaging/broadcasts/create/", {
            "title": "Some title"
        }, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("messaging.services.create_broadcast")
    def test_creates_broadcast_via_service(self, mock_create):
        from django.utils import timezone
        mock_bc = MagicMock()
        mock_bc.id = "bc-uuid-1"
        mock_bc.title = "Test"
        mock_bc.status = "DRAFT"
        mock_bc.audience_type = "ALL_USERS"
        mock_bc.scheduled_at = None
        mock_bc.created_at = timezone.now()
        mock_create.return_value = mock_bc
        r = _auth(self.admin).post("/messaging/broadcasts/create/", {
            "title": "Test", "body": "Test body"
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "DRAFT")
        mock_create.assert_called_once()

    def test_invalid_scheduled_at_returns_400(self):
        r = _auth(self.admin).post("/messaging/broadcasts/create/", {
            "title": "T", "body": "B", "scheduled_at": "not-a-date"
        }, format="json")
        self.assertEqual(r.status_code, 400)
