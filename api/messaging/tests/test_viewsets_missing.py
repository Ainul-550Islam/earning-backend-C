"""
test_viewsets_missing.py
=========================
Tests for the 7 ViewSets that had no coverage:
  BotResponseViewSet, MessageReportViewSet, MessageSearchIndexViewSet,
  NotificationReadViewSet, PollVoteViewSet, UserDeviceViewSet,
  WebhookDeliveryViewSet

Place this file in: messaging/tests/test_viewsets_missing.py
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    BotConfigFactory,
    AnnouncementChannelFactory,
)
from ..models import (
    BotResponse,
    BotConfig,
    ChatMention,
    CPABroadcast,
    MediaAttachment,
    MessageReport,
    MessageSearchIndex,
    NotificationRead,
    PollVote,
    UserDevice,
    WebhookDelivery,
    MessagingWebhook,
    ChatMessage,
)
from .. import services


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def _admin():
    return UserFactory(is_staff=True, is_superuser=True)


# ─────────────────────────────────────────────────────────────────────────────
# BotResponseViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestBotResponseViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        self.bot = BotConfigFactory()
        self.response = BotResponse.objects.create(
            bot=self.bot,
            trigger_message=self.msg,
            was_successful=True,
        )

    def test_list_requires_admin(self):
        client = _api(self.user)
        r = client.get("/messaging/bot-responses/")
        self.assertEqual(r.status_code, 403)

    def test_list_returns_entries_for_admin(self):
        client = _api(self.admin)
        r = client.get("/messaging/bot-responses/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data["results"]), 1)

    def test_filter_by_bot_id(self):
        other_bot = BotConfigFactory()
        BotResponse.objects.create(bot=other_bot, trigger_message=self.msg, was_successful=False)
        client = _api(self.admin)
        r = client.get(f"/messaging/bot-responses/?bot_id={self.bot.id}")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(str(item["bot"]), str(self.bot.id))

    def test_filter_by_was_successful_true(self):
        client = _api(self.admin)
        r = client.get("/messaging/bot-responses/?was_successful=true")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertTrue(item["was_successful"])

    def test_filter_by_was_successful_false(self):
        BotResponse.objects.create(
            bot=self.bot, trigger_message=self.msg, was_successful=False, error="timeout"
        )
        client = _api(self.admin)
        r = client.get("/messaging/bot-responses/?was_successful=false")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertFalse(item["was_successful"])

    def test_retrieve_single(self):
        client = _api(self.admin)
        r = client.get(f"/messaging/bot-responses/{self.response.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], str(self.response.id))

    def test_write_methods_not_allowed(self):
        client = _api(self.admin)
        r = client.delete(f"/messaging/bot-responses/{self.response.id}/")
        self.assertIn(r.status_code, [405, 403])


# ─────────────────────────────────────────────────────────────────────────────
# MessageReportViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageReportViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.other = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.other)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.other)

    def test_create_report_authenticated(self):
        client = _api(self.user)
        r = client.post("/messaging/reports/", {
            "message": str(self.msg.id),
            "reason": MessageReport.REASON_SPAM,
            "details": "This is spam.",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["reason"], MessageReport.REASON_SPAM)
        self.assertEqual(r.data["status"], MessageReport.STATUS_PENDING)

    def test_create_report_sets_reported_by(self):
        client = _api(self.user)
        r = client.post("/messaging/reports/", {
            "message": str(self.msg.id),
            "reason": MessageReport.REASON_ABUSE,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        report = MessageReport.objects.get(pk=r.data["id"])
        self.assertEqual(report.reported_by, self.user)

    def test_create_report_invalid_reason(self):
        client = _api(self.user)
        r = client.post("/messaging/reports/", {
            "message": str(self.msg.id),
            "reason": "invalid_reason",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_user_can_only_see_own_reports(self):
        client = _api(self.user)
        r1 = client.post("/messaging/reports/", {
            "message": str(self.msg.id),
            "reason": MessageReport.REASON_SPAM,
        }, format="json")
        client2 = _api(self.other)
        client2.post("/messaging/reports/", {
            "message": str(self.msg.id),
            "reason": MessageReport.REASON_NSFW,
        }, format="json")
        # User lists their own reports. Non-admins are allowed to list
        # (see MessageReportViewSet.get_permissions/get_queryset) - they
        # just never see anyone else's reports.
        r_list = client.get("/messaging/reports/")
        self.assertEqual(r_list.status_code, 200)
        items = r_list.data if isinstance(r_list.data, list) else r_list.data.get("results", [])
        self.assertTrue(items)
        for item in items:
            self.assertEqual(item["reported_by"], self.user.pk)

    def test_admin_sees_all_reports(self):
        MessageReport.objects.create(
            message=self.msg, reported_by=self.user, reason=MessageReport.REASON_SPAM
        )
        MessageReport.objects.create(
            message=self.msg, reported_by=self.other, reason=MessageReport.REASON_ABUSE
        )
        client = _api(self.admin)
        r = client.get("/messaging/reports/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data["results"]), 2)

    def test_filter_by_status(self):
        MessageReport.objects.create(
            message=self.msg,
            reported_by=self.user,
            reason=MessageReport.REASON_SPAM,
            status=MessageReport.STATUS_PENDING,
        )
        client = _api(self.admin)
        r = client.get(f"/messaging/reports/?status={MessageReport.STATUS_PENDING}")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(item["status"], MessageReport.STATUS_PENDING)

    def test_review_action(self):
        report = MessageReport.objects.create(
            message=self.msg, reported_by=self.user, reason=MessageReport.REASON_SPAM
        )
        client = _api(self.admin)
        r = client.post(f"/messaging/reports/{report.id}/review/", {
            "status": MessageReport.STATUS_RESOLVED,
            "moderator_note": "Confirmed spam. Message deleted.",
            "action_taken": "message_deleted",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, MessageReport.STATUS_RESOLVED)
        self.assertEqual(report.reviewed_by, self.admin)
        self.assertIsNotNone(report.reviewed_at)
        self.assertEqual(report.moderator_note, "Confirmed spam. Message deleted.")

    def test_review_invalid_status(self):
        report = MessageReport.objects.create(
            message=self.msg, reported_by=self.user, reason=MessageReport.REASON_SPAM
        )
        client = _api(self.admin)
        r = client.post(f"/messaging/reports/{report.id}/review/", {
            "status": "bad_status",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_non_admin_cannot_review(self):
        report = MessageReport.objects.create(
            message=self.msg, reported_by=self.user, reason=MessageReport.REASON_SPAM
        )
        client = _api(self.user)
        r = client.post(f"/messaging/reports/{report.id}/review/", {
            "status": MessageReport.STATUS_DISMISSED,
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_cannot_report(self):
        client = _api()
        r = client.post("/messaging/reports/", {
            "message": str(self.msg.id),
            "reason": MessageReport.REASON_SPAM,
        }, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# MessageSearchIndexViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageSearchIndexViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        self.msg = ChatMessageFactory(chat=self.chat, sender=UserFactory())
        MessageSearchIndex.objects.create(
            message=self.msg,
            chat=self.chat,
            search_text="hello world test",
        )

    def test_list_requires_admin(self):
        client = _api(self.user)
        r = client.get("/messaging/search-index/")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_list(self):
        client = _api(self.admin)
        r = client.get("/messaging/search-index/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data["results"]), 1)

    def test_filter_by_chat_id(self):
        other_chat = InternalChatFactory()
        other_msg = ChatMessageFactory(chat=other_chat, sender=UserFactory())
        MessageSearchIndex.objects.create(
            message=other_msg, chat=other_chat, search_text="other chat message"
        )
        client = _api(self.admin)
        r = client.get(f"/messaging/search-index/?chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(str(item["chat"]), str(self.chat.id))

    @patch("messaging.tasks.bulk_reindex_task")
    def test_rebuild_queues_task(self, mock_task):
        mock_task.delay = MagicMock()
        client = _api(self.admin)
        r = client.post("/messaging/search-index/rebuild/")
        self.assertEqual(r.status_code, 202)
        mock_task.delay.assert_called_once()

    def test_rebuild_requires_admin(self):
        client = _api(self.user)
        r = client.post("/messaging/search-index/rebuild/")
        self.assertEqual(r.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# NotificationReadViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestNotificationReadViewSet(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.broadcast = CPABroadcast.objects.create(
            title="Big Announcement",
            body="Hello affiliates!",
            status="SENT",
            recipient_count=100,
        )

    def test_record_open_creates_record(self):
        client = _api(self.user)
        r = client.post("/messaging/notification-reads/", {
            "broadcast_id": str(self.broadcast.id),
        }, format="json")
        self.assertIn(r.status_code, [200, 201])
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.opened_count, 1)

    def test_opening_twice_does_not_double_count(self):
        client = _api(self.user)
        client.post("/messaging/notification-reads/", {"broadcast_id": str(self.broadcast.id)}, format="json")
        client.post("/messaging/notification-reads/", {"broadcast_id": str(self.broadcast.id)}, format="json")
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.opened_count, 1)
        self.assertEqual(NotificationRead.objects.filter(broadcast=self.broadcast, user=self.user).count(), 1)

    def test_record_click(self):
        read = NotificationRead.objects.create(broadcast=self.broadcast, user=self.user)
        client = _api(self.user)
        r = client.post(f"/messaging/notification-reads/{read.id}/click/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["clicked"])
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.clicked_count, 1)

    def test_click_idempotent(self):
        read = NotificationRead.objects.create(
            broadcast=self.broadcast, user=self.user,
            clicked_at=timezone.now()
        )
        client = _api(self.user)
        r1 = client.post(f"/messaging/notification-reads/{read.id}/click/")
        r2 = client.post(f"/messaging/notification-reads/{read.id}/click/")
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.clicked_count, 0)  # no increment; clicked_at already set

    def test_user_only_sees_own_reads(self):
        NotificationRead.objects.create(broadcast=self.broadcast, user=self.user)
        NotificationRead.objects.create(broadcast=self.broadcast, user=self.other)
        client = _api(self.user)
        r = client.get("/messaging/notification-reads/")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(item["user"], self.user.pk)

    def test_missing_broadcast_id_returns_400(self):
        client = _api(self.user)
        r = client.post("/messaging/notification-reads/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_broadcast_returns_404(self):
        client = _api(self.user)
        r = client.post("/messaging/notification-reads/", {
            "broadcast_id": str(uuid.uuid4()),
        }, format="json")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_blocked(self):
        client = _api()
        r = client.post("/messaging/notification-reads/", {
            "broadcast_id": str(self.broadcast.id),
        }, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# PollVoteViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestPollVoteViewSet(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.creator = UserFactory()
        self.voter = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.creator)
        ChatParticipantFactory(chat=self.chat, user=self.voter)
        # Create a POLL message directly
        self.poll_msg = ChatMessage.objects.create(
            chat=self.chat,
            sender=self.creator,
            content="Best language?",
            message_type="POLL",
            poll_data={
                "question": "Best language?",
                "options": [
                    {"id": "opt_0", "text": "Python"},
                    {"id": "opt_1", "text": "Go"},
                    {"id": "opt_2", "text": "Rust"},
                ],
                "multiple_choice": False,
            },
        )

    def test_cast_vote(self):
        client = _api(self.voter)
        r = client.post("/messaging/poll-votes/", {
            "message": str(self.poll_msg.id),
            "option_id": "opt_0",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["option_id"], "opt_0")

    def test_single_choice_replaces_old_vote(self):
        client = _api(self.voter)
        client.post("/messaging/poll-votes/", {
            "message": str(self.poll_msg.id),
            "option_id": "opt_0",
        }, format="json")
        client.post("/messaging/poll-votes/", {
            "message": str(self.poll_msg.id),
            "option_id": "opt_1",
        }, format="json")
        self.assertEqual(
            PollVote.objects.filter(message=self.poll_msg, user=self.voter).count(), 1
        )
        vote = PollVote.objects.get(message=self.poll_msg, user=self.voter)
        self.assertEqual(vote.option_id, "opt_1")

    def test_multiple_choice_keeps_all_votes(self):
        self.poll_msg.poll_data["multiple_choice"] = True
        self.poll_msg.save()
        client = _api(self.voter)
        client.post("/messaging/poll-votes/", {
            "message": str(self.poll_msg.id),
            "option_id": "opt_0",
        }, format="json")
        client.post("/messaging/poll-votes/", {
            "message": str(self.poll_msg.id),
            "option_id": "opt_1",
        }, format="json")
        self.assertEqual(
            PollVote.objects.filter(message=self.poll_msg, user=self.voter).count(), 2
        )

    def test_cannot_vote_on_non_poll_message(self):
        text_msg = ChatMessageFactory(chat=self.chat, sender=self.creator)
        client = _api(self.voter)
        r = client.post("/messaging/poll-votes/", {
            "message": str(text_msg.id),
            "option_id": "opt_0",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_list_votes_for_poll(self):
        PollVote.objects.create(message=self.poll_msg, user=self.voter, option_id="opt_0")
        client = _api(self.voter)
        r = client.get(f"/messaging/poll-votes/?message_id={self.poll_msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 1)

    def test_retract_own_vote(self):
        vote = PollVote.objects.create(
            message=self.poll_msg, user=self.voter, option_id="opt_0"
        )
        client = _api(self.voter)
        r = client.delete(f"/messaging/poll-votes/{vote.id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(PollVote.objects.filter(pk=vote.id).exists())

    def test_cannot_retract_others_vote(self):
        vote = PollVote.objects.create(
            message=self.poll_msg, user=self.creator, option_id="opt_0"
        )
        client = _api(self.voter)
        r = client.delete(f"/messaging/poll-votes/{vote.id}/")
        self.assertIn(r.status_code, [403, 404])

    def test_results_action(self):
        PollVote.objects.create(message=self.poll_msg, user=self.voter, option_id="opt_0")
        PollVote.objects.create(message=self.poll_msg, user=self.creator, option_id="opt_1")
        client = _api(self.voter)
        r = client.get(f"/messaging/poll-votes/results/?message_id={self.poll_msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_votes"], 2)

    def test_unauthenticated_blocked(self):
        client = _api()
        r = client.post("/messaging/poll-votes/", {
            "message": str(self.poll_msg.id),
            "option_id": "opt_0",
        }, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# UserDeviceViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestUserDeviceViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.other = UserFactory()

    def _register(self, user, platform="android", device_id=None):
        return UserDevice.objects.create(
            user=user,
            device_id=device_id or uuid.uuid4().hex,
            platform=platform,
            device_name="Test Phone",
            is_active=True,
        )

    def test_list_own_devices(self):
        self._register(self.user)
        self._register(self.other)
        client = _api(self.user)
        r = client.get("/messaging/devices/")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(item["user"], self.user.pk)

    def test_register_device(self):
        client = _api(self.user)
        r = client.post("/messaging/devices/", {
            "device_id": "abc123device",
            "device_name": "My Phone",
            "platform": "ios",
            "os_version": "17.0",
            "app_version": "2.5.1",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["platform"], "ios")

    def test_soft_delete_device(self):
        device = self._register(self.user)
        client = _api(self.user)
        r = client.delete(f"/messaging/devices/{device.id}/")
        self.assertEqual(r.status_code, 204)
        device.refresh_from_db()
        self.assertFalse(device.is_active)

    def test_cannot_delete_others_device(self):
        device = self._register(self.other)
        client = _api(self.user)
        r = client.delete(f"/messaging/devices/{device.id}/")
        self.assertIn(r.status_code, [403, 404])

    def test_admin_trust_device(self):
        device = self._register(self.user)
        UserDevice.objects.filter(pk=device.pk).update(is_trusted=False)
        client = _api(self.admin)
        r = client.post(f"/messaging/devices/{device.id}/trust/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_trusted"])
        device.refresh_from_db()
        self.assertTrue(device.is_trusted)

    def test_admin_distrust_device(self):
        device = self._register(self.user)
        client = _api(self.admin)
        r = client.post(f"/messaging/devices/{device.id}/distrust/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_trusted"])

    def test_non_admin_cannot_trust(self):
        device = self._register(self.other)
        client = _api(self.user)
        r = client.post(f"/messaging/devices/{device.id}/trust/")
        self.assertEqual(r.status_code, 403)

    def test_heartbeat_updates_last_active(self):
        device = self._register(self.user)
        client = _api(self.user)
        r = client.post("/messaging/devices/heartbeat/", {
            "device_id": device.device_id,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["updated"])

    def test_heartbeat_missing_device_id(self):
        client = _api(self.user)
        r = client.post("/messaging/devices/heartbeat/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_can_filter_by_user_id(self):
        self._register(self.user)
        self._register(self.other)
        client = _api(self.admin)
        r = client.get(f"/messaging/devices/?user_id={self.user.pk}")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(item["user"], self.user.pk)

    def test_unauthenticated_blocked(self):
        client = _api()
        r = client.get("/messaging/devices/")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# WebhookDeliveryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookDeliveryViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.webhook = MessagingWebhook.objects.create(
            name="Test Webhook",
            url="https://example.com/hook",
            secret="topsecret",
            events=["message.sent"],
            created_by=self.admin,
        )
        self.delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={"message_id": "test-123"},
            response_status=200,
            is_successful=True,
        )
        self.failed_delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={"message_id": "test-456"},
            response_status=500,
            is_successful=False,
            error="Connection refused",
        )

    def test_list_requires_admin(self):
        client = _api(self.user)
        r = client.get("/messaging/webhook-deliveries/")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_list(self):
        client = _api(self.admin)
        r = client.get("/messaging/webhook-deliveries/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data["results"]), 2)

    def test_filter_by_webhook_id(self):
        other_webhook = MessagingWebhook.objects.create(
            name="Other", url="https://other.com/hook", secret="s",
            events=[], created_by=self.admin,
        )
        WebhookDelivery.objects.create(
            webhook=other_webhook, event_type="message.sent",
            payload={}, is_successful=True,
        )
        client = _api(self.admin)
        r = client.get(f"/messaging/webhook-deliveries/?webhook_id={self.webhook.id}")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(str(item["webhook"]), str(self.webhook.id))

    def test_filter_by_is_successful_true(self):
        client = _api(self.admin)
        r = client.get("/messaging/webhook-deliveries/?is_successful=true")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertTrue(item["is_successful"])

    def test_filter_by_is_successful_false(self):
        client = _api(self.admin)
        r = client.get("/messaging/webhook-deliveries/?is_successful=false")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertFalse(item["is_successful"])

    def test_filter_by_event_type(self):
        client = _api(self.admin)
        r = client.get("/messaging/webhook-deliveries/?event_type=message.sent")
        self.assertEqual(r.status_code, 200)
        for item in r.data["results"]:
            self.assertEqual(item["event_type"], "message.sent")

    def test_retrieve_single(self):
        client = _api(self.admin)
        r = client.get(f"/messaging/webhook-deliveries/{self.delivery.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], str(self.delivery.id))

    @patch("messaging.tasks.retry_webhook_delivery_task")
    def test_retry_failed_delivery(self, mock_task):
        mock_task.delay = MagicMock()
        client = _api(self.admin)
        r = client.post(f"/messaging/webhook-deliveries/{self.failed_delivery.id}/retry/")
        self.assertEqual(r.status_code, 202)
        mock_task.delay.assert_called_once_with(str(self.failed_delivery.id))

    def test_retry_successful_delivery_returns_400(self):
        client = _api(self.admin)
        r = client.post(f"/messaging/webhook-deliveries/{self.delivery.id}/retry/")
        self.assertEqual(r.status_code, 400)

    def test_write_not_allowed(self):
        client = _api(self.admin)
        r = client.delete(f"/messaging/webhook-deliveries/{self.delivery.id}/")
        self.assertIn(r.status_code, [405, 403])
