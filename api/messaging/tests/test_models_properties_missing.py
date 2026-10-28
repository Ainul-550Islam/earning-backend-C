"""
test_models_properties_missing.py
===================================
Direct unit tests for model computed properties/methods that were defined
in models.py but had zero test coverage anywhere — despite several of them
(is_editable, open_rate, click_rate, is_expired) being exposed directly in
API responses via serializers.

Covers:
  AdminBroadcast.is_editable, AdminBroadcast.mark_failed
  CPABroadcast.open_rate, CPABroadcast.click_rate
  UserStory.is_expired
  ChatMessage.is_visible
  SupportThread.is_closed, SupportThread.is_resolved

Place in: messaging/tests/test_models_properties_missing.py
"""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .factories import (
    AdminBroadcastFactory,
    InternalChatFactory,
    SupportThreadFactory,
    UserFactory,
    UserStoryFactory,
)
from ..models import ChatMessage, CPABroadcast
from ..choices import BroadcastStatus, MessageStatus, SupportThreadStatus


class TestAdminBroadcastIsEditable(TestCase):
    def test_draft_is_editable(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.DRAFT)
        self.assertTrue(b.is_editable)

    def test_failed_is_editable(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.FAILED)
        self.assertTrue(b.is_editable)

    def test_sent_is_not_editable(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENT)
        self.assertFalse(b.is_editable)

    def test_sending_is_not_editable(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENDING)
        self.assertFalse(b.is_editable)


class TestAdminBroadcastMarkFailed(TestCase):
    def test_mark_failed_sets_status_and_message(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENDING)
        b.mark_failed("SMTP timeout")
        self.assertEqual(b.status, BroadcastStatus.FAILED)
        self.assertEqual(b.error_message, "SMTP timeout")

    def test_mark_failed_persists_to_db(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENDING)
        b.mark_failed("Connection refused")
        b.refresh_from_db()
        self.assertEqual(b.status, BroadcastStatus.FAILED)
        self.assertEqual(b.error_message, "Connection refused")

    def test_mark_failed_truncates_long_error(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENDING)
        b.mark_failed("x" * 5000)
        self.assertEqual(len(b.error_message), 4096)

    def test_mark_failed_handles_non_string_error(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENDING)
        b.mark_failed(None)  # type: ignore[arg-type]
        self.assertEqual(b.error_message, "Unknown error.")

    def test_mark_failed_makes_broadcast_editable_again(self):
        b = AdminBroadcastFactory(status=BroadcastStatus.SENDING)
        self.assertFalse(b.is_editable)
        b.mark_failed("oops")
        self.assertTrue(b.is_editable)


class TestCPABroadcastRates(TestCase):
    def test_open_rate_computed_from_counts(self):
        b = CPABroadcast.objects.create(
            title="x", body="y", recipient_count=200, delivered_count=200, opened_count=50,
        )
        self.assertEqual(b.open_rate, 25.0)

    def test_click_rate_computed_from_counts(self):
        b = CPABroadcast.objects.create(
            title="x", body="y", recipient_count=200, delivered_count=200, clicked_count=10,
        )
        self.assertEqual(b.click_rate, 5.0)

    def test_open_rate_none_when_nothing_delivered(self):
        b = CPABroadcast.objects.create(title="x", body="y", recipient_count=0, delivered_count=0, opened_count=0)
        self.assertIsNone(b.open_rate)

    def test_click_rate_none_when_nothing_delivered(self):
        b = CPABroadcast.objects.create(title="x", body="y", recipient_count=0, delivered_count=0, clicked_count=0)
        self.assertIsNone(b.click_rate)

    def test_open_rate_caps_sensibly_with_full_open(self):
        b = CPABroadcast.objects.create(
            title="x", body="y", recipient_count=10, delivered_count=10, opened_count=10,
        )
        self.assertEqual(b.open_rate, 100.0)


class TestUserStoryIsExpired(TestCase):
    def test_future_expiry_is_not_expired(self):
        story = UserStoryFactory(expires_at=timezone.now() + timedelta(hours=1))
        self.assertFalse(story.is_expired)

    def test_past_expiry_is_expired(self):
        story = UserStoryFactory(expires_at=timezone.now() - timedelta(hours=1))
        self.assertTrue(story.is_expired)

    def test_expiry_exactly_now_is_expired(self):
        story = UserStoryFactory(expires_at=timezone.now() - timedelta(milliseconds=1))
        self.assertTrue(story.is_expired)


class TestChatMessageIsVisible(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()

    def test_sent_message_is_visible(self):
        msg = ChatMessage.objects.create(
            chat=self.chat, sender=self.user, content="hi",
            message_type="TEXT", status=MessageStatus.SENT,
        )
        self.assertTrue(msg.is_visible)
        self.assertFalse(msg.is_deleted)

    def test_deleted_message_is_not_visible(self):
        msg = ChatMessage.objects.create(
            chat=self.chat, sender=self.user, content="hi",
            message_type="TEXT", status=MessageStatus.SENT,
        )
        msg.soft_delete()
        self.assertFalse(msg.is_visible)
        self.assertTrue(msg.is_deleted)

    def test_is_visible_is_exact_inverse_of_is_deleted(self):
        msg = ChatMessage.objects.create(
            chat=self.chat, sender=self.user, content="hi",
            message_type="TEXT", status=MessageStatus.SENT,
        )
        for target_status in (MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.DELETED):
            msg.status = target_status
            self.assertEqual(msg.is_visible, not msg.is_deleted)


class TestSupportThreadIsClosedIsResolved(TestCase):
    def test_open_thread_is_neither_closed_nor_resolved(self):
        t = SupportThreadFactory(status=SupportThreadStatus.OPEN)
        self.assertFalse(t.is_closed)
        self.assertFalse(t.is_resolved)

    def test_resolved_thread(self):
        t = SupportThreadFactory(status=SupportThreadStatus.RESOLVED)
        self.assertFalse(t.is_closed)
        self.assertTrue(t.is_resolved)

    def test_closed_thread(self):
        t = SupportThreadFactory(status=SupportThreadStatus.CLOSED)
        self.assertTrue(t.is_closed)
        self.assertFalse(t.is_resolved)
