"""
test_admin_coverage_boost.py
==============================
First dedicated test coverage for messaging/admin.py. Its baseline coverage
came only from Django's admin autodiscovery importing the module at startup
(class bodies, list_display tuples, @admin.register decorators) -- none of
the custom display methods or bulk actions were ever actually called.

Tests instantiate each ModelAdmin directly (AdminClass(Model, admin.site))
and call its display methods and actions() with a real queryset + a request
carrying a working messages framework (required by self.message_user()).

Place in: messaging/tests/test_admin_coverage_boost.py
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import TestCase, RequestFactory

from .. import admin as messaging_admin
from ..models import (
    InternalChat, ChatMessage, AdminBroadcast, SupportThread,
    UserInbox, MessageReaction, AnnouncementChannel, ScheduledMessage,
    MessagePin, BotConfig, MessagingWebhook, MediaAttachment, MessageReport,
    UserDevice, DeviceToken, UserBlock, UserStory, LinkPreview,
    WebhookDelivery, VoiceMessageTranscription,
)
from ..choices import ChatStatus
from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory, ChatMessageFactory,
    AdminBroadcastFactory, SupportThreadFactory, UserInboxFactory,
    MessageReactionFactory, AnnouncementChannelFactory, DeviceTokenFactory,
    UserStoryFactory, BotConfigFactory,
)

User = get_user_model()


def _request(user):
    req = RequestFactory().get("/admin/")
    req.user = user
    req._messages = CookieStorage(req)
    return req


class TestInternalChatAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.InternalChatAdmin(InternalChat, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_display_methods(self):
        chat = InternalChatFactory(name="", is_group=False)
        self.assertEqual(len(self.admin.id_short(chat)), 8)
        self.assertEqual(self.admin.name_or_direct(chat), "(Direct)")
        self.assertEqual(self.admin.participant_count(chat), 0)

    def test_named_group_chat_display(self):
        chat = InternalChatFactory(name="Team Room", is_group=True)
        self.assertEqual(self.admin.name_or_direct(chat), "Team Room")

    def test_archive_chats_action(self):
        chat = InternalChatFactory(status=ChatStatus.ACTIVE)
        qs = InternalChat.objects.filter(pk=chat.pk)
        self.admin.archive_chats(_request(self.staff), qs)
        chat.refresh_from_db()
        self.assertEqual(chat.status, ChatStatus.ARCHIVED)

    def test_delete_chats_action(self):
        chat = InternalChatFactory(status=ChatStatus.ACTIVE)
        qs = InternalChat.objects.filter(pk=chat.pk)
        self.admin.delete_chats(_request(self.staff), qs)
        chat.refresh_from_db()
        self.assertEqual(chat.status, ChatStatus.DELETED)


class TestChatMessageAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.ChatMessageAdmin(ChatMessage, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.staff)

    def test_id_short_and_content_preview(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.staff, content="x" * 100)
        self.assertEqual(len(self.admin.id_short(msg)), 8)
        preview = self.admin.content_preview(msg)
        self.assertTrue(preview.endswith("…"))
        self.assertEqual(len(preview), 61)

    def test_content_preview_short_message_no_ellipsis(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.staff, content="hi")
        self.assertEqual(self.admin.content_preview(msg), "hi")

    def test_sender_link_with_and_without_sender(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.staff)
        html = self.admin.sender_link(msg)
        self.assertIn(self.staff.username, html)

        system_msg = ChatMessageFactory(chat=self.chat, sender=None, message_type="SYSTEM", content="x")
        self.assertEqual(self.admin.sender_link(system_msg), "—")

    def test_chat_link_renders_admin_url(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.staff)
        html = self.admin.chat_link(msg)
        self.assertIn(str(self.chat.id)[:8], html)

    def test_soft_delete_messages_action(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.staff)
        qs = ChatMessage.objects.filter(pk=msg.pk)
        self.admin.soft_delete_messages(_request(self.staff), qs)
        msg.refresh_from_db()
        self.assertTrue(msg.is_deleted)


class TestAdminBroadcastAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.AdminBroadcastAdmin(AdminBroadcast, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_delivery_rate_with_and_without_recipients(self):
        b = AdminBroadcastFactory(created_by=self.staff, recipient_count=0)
        self.assertEqual(self.admin.delivery_rate(b), "—")

    def test_send_now_action_queues_task(self):
        b = AdminBroadcastFactory(created_by=self.staff, status="DRAFT")
        qs = AdminBroadcast.objects.filter(pk=b.pk)
        with patch("messaging.tasks.send_broadcast_async.delay") as mock_delay:
            self.admin.send_now(_request(self.staff), qs)
        mock_delay.assert_called_once()


class TestSupportThreadAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.SupportThreadAdmin(SupportThread, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_subject_short(self):
        thread = SupportThreadFactory(subject="x" * 100)
        self.assertEqual(len(self.admin.subject_short(thread)), 60)

    def test_close_threads_action(self):
        thread = SupportThreadFactory(status="OPEN")
        qs = SupportThread.objects.filter(pk=thread.pk)
        self.admin.close_threads(_request(self.staff), qs)
        thread.refresh_from_db()
        self.assertEqual(thread.status, "CLOSED")

    def test_assign_to_me_action(self):
        thread = SupportThreadFactory()
        qs = SupportThread.objects.filter(pk=thread.pk)
        self.admin.assign_to_me(_request(self.staff), qs)
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_agent_id, self.staff.pk)


class TestUserInboxAdmin(TestCase):
    def test_title_short(self):
        item = UserInboxFactory(title="x" * 60)
        admin_ = messaging_admin.UserInboxAdmin(UserInbox, admin.site)
        self.assertEqual(len(admin_.title_short(item)), 50)


class TestMessageReactionAdmin(TestCase):
    def test_message_id_short(self):
        chat, user = InternalChatFactory(), UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, sender=user)
        reaction = MessageReactionFactory(message=msg, user=user)
        admin_ = messaging_admin.MessageReactionAdmin(MessageReaction, admin.site)
        self.assertEqual(len(admin_.message_id_short(reaction)), 8)


class TestAnnouncementChannelAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.AnnouncementChannelAdmin(AnnouncementChannel, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_verify_channels_action(self):
        channel = AnnouncementChannelFactory(is_verified=False)
        qs = AnnouncementChannel.objects.filter(pk=channel.pk)
        self.admin.verify_channels(_request(self.staff), qs)
        channel.refresh_from_db()
        self.assertTrue(channel.is_verified)


class TestScheduledMessageAdmin(TestCase):
    def test_display_methods(self):
        chat, user = InternalChatFactory(), UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        from django.utils import timezone
        from datetime import timedelta
        sched = ScheduledMessage.objects.create(
            chat=chat, sender=user, content="x" * 100,
            scheduled_for=timezone.now() + timedelta(hours=1),
        )
        admin_ = messaging_admin.ScheduledMessageAdmin(ScheduledMessage, admin.site)
        self.assertEqual(len(admin_.chat_id_short(sched)), 8)
        self.assertEqual(len(admin_.content_preview(sched)), 60)


class TestMessagePinAdmin(TestCase):
    def test_display_methods(self):
        chat, user = InternalChatFactory(), UserFactory()
        ChatParticipantFactory(chat=chat, user=user, role="ADMIN")
        msg = ChatMessageFactory(chat=chat, sender=user)
        from ..models import MessagePin as MessagePinModel
        pin = MessagePinModel.objects.create(chat=chat, message=msg, pinned_by=user)
        admin_ = messaging_admin.MessagePinAdmin(MessagePin, admin.site)
        self.assertEqual(len(admin_.chat_id_short(pin)), 8)
        self.assertEqual(len(admin_.message_id_short(pin)), 8)


class TestBotConfigAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.BotConfigAdmin(BotConfig, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_trigger_value_short(self):
        bot = BotConfigFactory(trigger_value="x" * 60)
        self.assertEqual(len(self.admin.trigger_value_short(bot)), 40)

    def test_activate_and_deactivate_actions(self):
        bot = BotConfigFactory(is_active=False)
        qs = BotConfig.objects.filter(pk=bot.pk)
        self.admin.activate_bots(_request(self.staff), qs)
        bot.refresh_from_db()
        self.assertTrue(bot.is_active)

        self.admin.deactivate_bots(_request(self.staff), qs)
        bot.refresh_from_db()
        self.assertFalse(bot.is_active)


class TestMessagingWebhookAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.MessagingWebhookAdmin(MessagingWebhook, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_display_methods(self):
        webhook = MessagingWebhook.objects.create(
            name="W", url="https://example.com/" + "x" * 60, secret="s",
            events=["message.sent", "call.ended"],
        )
        self.assertEqual(len(self.admin.url_short(webhook)), 60)
        self.assertEqual(self.admin.events_count(webhook), 2)

    def test_reset_failure_count_action(self):
        webhook = MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s", failure_count=5,
        )
        qs = MessagingWebhook.objects.filter(pk=webhook.pk)
        self.admin.reset_failure_count(_request(self.staff), qs)
        webhook.refresh_from_db()
        self.assertEqual(webhook.failure_count, 0)

    def test_deactivate_webhooks_action(self):
        webhook = MessagingWebhook.objects.create(
            name="W", url="https://example.com/hook", secret="s", is_active=True,
        )
        qs = MessagingWebhook.objects.filter(pk=webhook.pk)
        self.admin.deactivate_webhooks(_request(self.staff), qs)
        webhook.refresh_from_db()
        self.assertFalse(webhook.is_active)


class TestMediaAttachmentAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.MediaAttachmentAdmin(MediaAttachment, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_file_size_display_bytes_kb_mb(self):
        small = MediaAttachment.objects.create(
            uploaded_by=self.staff, original_filename="a.txt", file_key="k1",
            original_url="https://x/k1", mimetype="text/plain", file_size=500,
        )
        kb = MediaAttachment.objects.create(
            uploaded_by=self.staff, original_filename="b.txt", file_key="k2",
            original_url="https://x/k2", mimetype="text/plain", file_size=5000,
        )
        mb = MediaAttachment.objects.create(
            uploaded_by=self.staff, original_filename="c.jpg", file_key="k3",
            original_url="https://x/k3", mimetype="image/jpeg", file_size=5_000_000,
        )
        self.assertEqual(self.admin.file_size_display(small), "500 B")
        self.assertEqual(self.admin.file_size_display(kb), "5.0 KB")
        self.assertEqual(self.admin.file_size_display(mb), "5.0 MB")

    def test_reprocess_media_action_routes_by_type(self):
        img = MediaAttachment.objects.create(
            uploaded_by=self.staff, original_filename="a.jpg", file_key="k4",
            original_url="https://x/k4", mimetype="image/jpeg", file_size=100,
        )
        qs = MediaAttachment.objects.filter(pk=img.pk)
        with patch("messaging.tasks.process_image_task.delay") as mock_img:
            self.admin.reprocess_media(_request(self.staff), qs)
        mock_img.assert_called_once_with(str(img.id))

    def test_block_nsfw_action(self):
        media = MediaAttachment.objects.create(
            uploaded_by=self.staff, original_filename="a.jpg", file_key="k5",
            original_url="https://x/k5", mimetype="image/jpeg", file_size=100,
        )
        qs = MediaAttachment.objects.filter(pk=media.pk)
        self.admin.block_nsfw(_request(self.staff), qs)
        media.refresh_from_db()
        self.assertTrue(media.is_nsfw)
        self.assertEqual(media.status, MediaAttachment.STATUS_BLOCKED)


class TestMessageReportAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.MessageReportAdmin(MessageReport, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.staff)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.staff)

    def _report(self):
        return MessageReport.objects.create(
            message=self.msg, reported_by=self.staff, reason=MessageReport.REASON_SPAM,
        )

    def test_mark_reviewed_action(self):
        report = self._report()
        qs = MessageReport.objects.filter(pk=report.pk)
        self.admin.mark_reviewed(_request(self.staff), qs)
        report.refresh_from_db()
        self.assertEqual(report.status, MessageReport.STATUS_REVIEWED)
        self.assertEqual(report.reviewed_by_id, self.staff.pk)

    def test_mark_dismissed_action(self):
        report = self._report()
        qs = MessageReport.objects.filter(pk=report.pk)
        self.admin.mark_dismissed(_request(self.staff), qs)
        report.refresh_from_db()
        self.assertEqual(report.status, MessageReport.STATUS_DISMISSED)

    def test_delete_reported_message_action(self):
        report = self._report()
        qs = MessageReport.objects.filter(pk=report.pk)
        self.admin.delete_reported_message(_request(self.staff), qs)
        report.refresh_from_db()
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.is_deleted)
        self.assertEqual(report.status, MessageReport.STATUS_RESOLVED)
        self.assertEqual(report.action_taken, "message deleted by admin")


class TestUserDeviceAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.UserDeviceAdmin(UserDevice, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_revoke_and_trust_actions(self):
        device = UserDevice.objects.create(
            user=self.staff, device_id="dev-1", device_name="Phone", platform="ios",
            is_active=True, is_trusted=False,
        )
        qs = UserDevice.objects.filter(pk=device.pk)
        self.admin.revoke_devices(_request(self.staff), qs)
        device.refresh_from_db()
        self.assertFalse(device.is_active)

        self.admin.trust_devices(_request(self.staff), qs)
        device.refresh_from_db()
        self.assertTrue(device.is_trusted)


class TestUserBlockAdmin(TestCase):
    def test_reason_short(self):
        a, b = UserFactory(), UserFactory()
        block = UserBlock.objects.create(blocker=a, blocked=b, reason="x" * 60)
        admin_ = messaging_admin.UserBlockAdmin(UserBlock, admin.site)
        self.assertEqual(len(admin_.reason_short(block)), 50)


class TestUserStoryAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.UserStoryAdmin(UserStory, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_content_preview_truncates_long_content(self):
        story = UserStoryFactory(user=self.staff, content="x" * 60)
        preview = self.admin.content_preview(story)
        self.assertTrue(preview.endswith("…"))

    def test_content_preview_short_no_ellipsis(self):
        story = UserStoryFactory(user=self.staff, content="short")
        self.assertEqual(self.admin.content_preview(story), "short")

    def test_expire_stories_action(self):
        story = UserStoryFactory(user=self.staff, is_active=True)
        qs = UserStory.objects.filter(pk=story.pk)
        self.admin.expire_stories(_request(self.staff), qs)
        story.refresh_from_db()
        self.assertFalse(story.is_active)

    def test_deactivate_stories_action(self):
        story = UserStoryFactory(user=self.staff, is_active=True)
        qs = UserStory.objects.filter(pk=story.pk)
        self.admin.deactivate_stories(_request(self.staff), qs)
        story.refresh_from_db()
        self.assertFalse(story.is_active)


class TestLinkPreviewAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.LinkPreviewAdmin(LinkPreview, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)

    def test_title_short(self):
        preview = LinkPreview.objects.create(url="https://example.com", title="x" * 80)
        self.assertEqual(len(self.admin.title_short(preview)), 60)

    def test_mark_unsafe_action(self):
        preview = LinkPreview.objects.create(url="https://example.com", is_safe=True)
        qs = LinkPreview.objects.filter(pk=preview.pk)
        self.admin.mark_unsafe(_request(self.staff), qs)
        preview.refresh_from_db()
        self.assertFalse(preview.is_safe)

    def test_refetch_action(self):
        preview = LinkPreview.objects.create(url="https://example.com", title="old")
        qs = LinkPreview.objects.filter(pk=preview.pk)
        with patch("messaging.utils.link_preview.fetch_link_preview") as mock_fetch:
            mock_fetch.return_value = {"title": "new title", "is_safe": True}
            self.admin.refetch(_request(self.staff), qs)
        preview.refresh_from_db()
        self.assertEqual(preview.title, "new title")


class TestVoiceTranscriptionAdmin(TestCase):
    def setUp(self):
        self.admin = messaging_admin.VoiceTranscriptionAdmin(VoiceMessageTranscription, admin.site)
        self.staff = UserFactory(is_staff=True, is_superuser=True)
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.staff)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.staff, message_type="AUDIO")

    def test_display_methods(self):
        t = VoiceMessageTranscription.objects.create(
            message=self.msg, confidence=0.875, duration_seconds=12.3,
        )
        self.assertEqual(len(self.admin.message_id_short(t)), 8)
        self.assertEqual(self.admin.confidence_pct(t), "88%")
        self.assertEqual(self.admin.duration_display(t), "12.3s")

    def test_retranscribe_action(self):
        t = VoiceMessageTranscription.objects.create(message=self.msg)
        qs = VoiceMessageTranscription.objects.filter(pk=t.pk)
        with patch("messaging.tasks.process_voice_message_task.delay") as mock_delay:
            self.admin.retranscribe(_request(self.staff), qs)
        mock_delay.assert_called_once_with(str(self.msg.id))


class TestReadOnlyMixin(TestCase):
    def test_permissions(self):
        admin_ = messaging_admin.WebhookDeliveryAdmin(WebhookDelivery, admin.site)
        superuser = UserFactory(is_staff=True, is_superuser=True)
        staff = UserFactory(is_staff=True, is_superuser=False)
        self.assertFalse(admin_.has_add_permission(_request(staff)))
        self.assertFalse(admin_.has_change_permission(_request(staff)))
        self.assertFalse(admin_.has_delete_permission(_request(staff)))
        self.assertTrue(admin_.has_delete_permission(_request(superuser)))
