"""
test_serializers_coverage_boost.py
====================================
Direct unit tests for messaging/serializers.py validation methods and
SerializerMethodFields that aren't fully exercised by the ViewSet-level
integration tests — especially MessagingWebhookSerializer.validate_url's
SSRF protection, which had zero coverage.

Place in: messaging/tests/test_serializers_coverage_boost.py
"""
from __future__ import annotations

from unittest.mock import MagicMock

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers as drf_serializers

from .. import serializers
from .factories import UserFactory, ChatMessageFactory, InternalChatFactory, ChatParticipantFactory


class TestChatParticipantSerializerMethodField(TestCase):
    def test_user_display_name_none_user(self):
        s = serializers.ChatParticipantSerializer()
        fake = MagicMock()
        fake.user = None
        self.assertEqual(s.get_user_display_name(fake), "")

    def test_user_display_name_falls_back_on_exception(self):
        s = serializers.ChatParticipantSerializer()
        fake = MagicMock()
        fake.user_id = "abc123"
        # Accessing first_name raises -> except branch returns str(obj.user_id)
        type(fake.user).first_name = property(lambda self: (_ for _ in ()).throw(RuntimeError()))
        self.assertEqual(s.get_user_display_name(fake), "abc123")

    def test_user_display_name_uses_username_when_no_real_name(self):
        user = UserFactory(first_name="", last_name="")
        s = serializers.ChatParticipantSerializer()
        fake = MagicMock()
        fake.user = user
        self.assertEqual(s.get_user_display_name(fake), user.username)


class TestInternalChatSerializerValidation(TestCase):
    def test_group_chat_requires_name(self):
        s = serializers.InternalChatSerializer(data={"is_group": True, "name": "  "})
        s.initial_data = {"is_group": True, "name": "  "}
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_name("  ")

    def test_non_group_chat_name_optional(self):
        s = serializers.InternalChatSerializer()
        s.initial_data = {"is_group": False}
        self.assertEqual(s.validate_name("  "), "")

    def test_metadata_must_be_dict(self):
        s = serializers.InternalChatSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_metadata(["not", "a", "dict"])

    def test_metadata_dict_passes(self):
        s = serializers.InternalChatSerializer()
        self.assertEqual(s.validate_metadata({"k": "v"}), {"k": "v"})


class TestInternalChatListSerializerUnreadCount(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        self.participant = ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_unread_count_no_request_context(self):
        s = serializers.InternalChatListSerializer(context={})
        self.assertEqual(s.get_unread_count(self.chat), 0)

    def test_unread_count_unauthenticated_request(self):
        req = MagicMock()
        req.user.is_authenticated = False
        s = serializers.InternalChatListSerializer(context={"request": req})
        self.assertEqual(s.get_unread_count(self.chat), 0)

    def test_unread_count_never_read(self):
        ChatMessageFactory(chat=self.chat, sender=self.user)
        req = MagicMock()
        req.user = self.user
        s = serializers.InternalChatListSerializer(context={"request": req})
        self.assertEqual(s.get_unread_count(self.chat), 1)

    def test_unread_count_since_last_read(self):
        self.participant.last_read_at = timezone.now()
        self.participant.save(update_fields=["last_read_at"])
        other = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=other)
        ChatMessageFactory(chat=self.chat, sender=other)
        req = MagicMock()
        req.user = self.user
        s = serializers.InternalChatListSerializer(context={"request": req})
        self.assertEqual(s.get_unread_count(self.chat), 1)

    def test_unread_count_exception_returns_zero(self):
        # obj with no participants relation matching -> DoesNotExist inside try -> except returns 0
        other_chat = InternalChatFactory()
        req = MagicMock()
        req.user = self.user
        s = serializers.InternalChatListSerializer(context={"request": req})
        self.assertEqual(s.get_unread_count(other_chat), 0)


class TestChatMessageSerializerMethodsAndValidation(TestCase):
    def test_sender_name_none_sender(self):
        s = serializers.ChatMessageSerializer()
        fake = MagicMock()
        fake.sender = None
        self.assertEqual(s.get_sender_name(fake), "System")

    def test_content_too_long_rejected(self):
        from ..constants import MAX_MESSAGE_LENGTH
        s = serializers.ChatMessageSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_content("x" * (MAX_MESSAGE_LENGTH + 1))

    def test_invalid_message_type_rejected(self):
        s = serializers.ChatMessageSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_message_type("NOT_A_REAL_TYPE")

    def test_valid_message_type_passes(self):
        s = serializers.ChatMessageSerializer()
        self.assertEqual(s.validate_message_type("TEXT"), "TEXT")


class TestSendMessageSerializer(TestCase):
    def test_text_message_requires_content(self):
        s = serializers.SendMessageSerializer(data={"message_type": "TEXT", "content": "  "})
        self.assertFalse(s.is_valid())
        self.assertIn("content", s.errors)

    def test_text_message_with_content_valid(self):
        s = serializers.SendMessageSerializer(data={"message_type": "TEXT", "content": "hi"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_non_text_message_type_no_content_required(self):
        s = serializers.SendMessageSerializer(data={"message_type": "IMAGE"})
        self.assertTrue(s.is_valid(), s.errors)


class TestAdminBroadcastSerializerValidation(TestCase):
    def test_empty_title_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_title("   ")

    def test_empty_body_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_body("")

    def test_body_too_long_rejected(self):
        from ..constants import MAX_BROADCAST_BODY_LENGTH
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_body("x" * (MAX_BROADCAST_BODY_LENGTH + 1))

    def test_invalid_audience_type_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_audience_type("EVERY_HUMAN_EVER")

    def test_audience_filter_none_or_empty_passes(self):
        s = serializers.AdminBroadcastSerializer()
        self.assertEqual(s.validate_audience_filter(None), {})
        self.assertEqual(s.validate_audience_filter({}), {})

    def test_audience_filter_must_be_dict(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_audience_filter(["not", "a", "dict"])

    def test_audience_filter_unknown_keys_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_audience_filter({"totally_made_up_key": 1})

    def test_audience_filter_list_field_must_be_list(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_audience_filter({"countries": "BD"})

    def test_audience_filter_negative_numeric_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_audience_filter({"min_balance": -5})

    def test_audience_filter_non_numeric_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_audience_filter({"min_balance": "not-a-number"})

    def test_audience_filter_valid_passes(self):
        s = serializers.AdminBroadcastSerializer()
        value = {"countries": ["BD", "IN"], "min_balance": 10}
        self.assertEqual(s.validate_audience_filter(value), value)

    def test_scheduled_at_in_past_rejected(self):
        s = serializers.AdminBroadcastSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_scheduled_at(timezone.now() - timedelta(hours=1))

    def test_scheduled_at_none_passes(self):
        s = serializers.AdminBroadcastSerializer()
        self.assertIsNone(s.validate_scheduled_at(None))

    def test_scheduled_at_future_passes(self):
        s = serializers.AdminBroadcastSerializer()
        future = timezone.now() + timedelta(hours=1)
        self.assertEqual(s.validate_scheduled_at(future), future)


class TestSupportMessageSerializerMethod(TestCase):
    def test_sender_name_none_sender(self):
        s = serializers.SupportMessageSerializer()
        fake = MagicMock()
        fake.sender = None
        self.assertEqual(s.get_sender_name(fake), "System")

    def test_sender_name_with_real_user(self):
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        s = serializers.SupportMessageSerializer()
        fake = MagicMock()
        fake.sender = user
        self.assertEqual(s.get_sender_name(fake), "Ada Lovelace")


class TestSupportThreadSerializerValidation(TestCase):
    def test_invalid_priority_rejected(self):
        s = serializers.SupportThreadSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_priority("SUPER_URGENT")

    def test_valid_priority_passes(self):
        s = serializers.SupportThreadSerializer()
        self.assertEqual(s.validate_priority("NORMAL"), "NORMAL")


class TestCreateSupportThreadSerializer(TestCase):
    def test_blank_subject_rejected(self):
        s = serializers.CreateSupportThreadSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_subject("   ")

    def test_blank_initial_message_rejected(self):
        s = serializers.CreateSupportThreadSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_initial_message("")

    def test_valid_passes(self):
        s = serializers.CreateSupportThreadSerializer(data={
            "subject": "Help", "initial_message": "Something's wrong",
        })
        self.assertTrue(s.is_valid(), s.errors)


class TestScheduledMessageSerializerValidation(TestCase):
    def test_scheduled_for_in_past_rejected(self):
        s = serializers.ScheduledMessageSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_scheduled_for(timezone.now() - timedelta(minutes=5))

    def test_scheduled_for_future_passes(self):
        s = serializers.ScheduledMessageSerializer()
        future = timezone.now() + timedelta(hours=1)
        self.assertEqual(s.validate_scheduled_for(future), future)

    def test_empty_content_rejected(self):
        s = serializers.ScheduledMessageSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_content("   ")

    def test_content_stripped(self):
        s = serializers.ScheduledMessageSerializer()
        self.assertEqual(s.validate_content("  hello  "), "hello")


class TestMessageReactionSerializerMethod(TestCase):
    def test_user_name_uses_full_name(self):
        user = UserFactory(first_name="Grace", last_name="Hopper")
        s = serializers.MessageReactionSerializer()
        fake = MagicMock()
        fake.user = user
        self.assertEqual(s.get_user_name(fake), "Grace Hopper")

    def test_user_name_exception_returns_empty_string(self):
        s = serializers.MessageReactionSerializer()
        fake = MagicMock()
        type(fake).user = property(lambda self: (_ for _ in ()).throw(RuntimeError()))
        self.assertEqual(s.get_user_name(fake), "")


class TestMessagingWebhookSerializerURLValidation(TestCase):
    """
    validate_url() implements HTTPS enforcement + SSRF protection.
    This had ZERO prior coverage despite being security-relevant.
    """
    def setUp(self):
        self.s = serializers.MessagingWebhookSerializer()

    def test_valid_https_url_passes(self):
        url = "https://example.com/webhook"
        self.assertEqual(self.s.validate_url(url), url)

    def test_http_scheme_rejected(self):
        with self.assertRaises(drf_serializers.ValidationError) as ctx:
            self.s.validate_url("http://example.com/webhook")
        self.assertIn("HTTPS", str(ctx.exception))

    def test_missing_hostname_rejected(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https:///path-only")

    def test_localhost_hostname_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError) as ctx:
            self.s.validate_url("https://localhost/webhook")
        self.assertIn("blocked hostname", str(ctx.exception))

    def test_gcp_metadata_hostname_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https://metadata.google.internal/webhook")

    def test_cloud_metadata_ip_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https://169.254.169.254/latest/meta-data/")

    def test_loopback_ip_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError) as ctx:
            self.s.validate_url("https://127.0.0.1/webhook")
        self.assertIn("private or reserved", str(ctx.exception))

    def test_private_class_a_ip_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https://10.0.0.5/webhook")

    def test_private_class_b_ip_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https://172.16.0.5/webhook")

    def test_private_class_c_ip_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https://192.168.1.5/webhook")

    def test_ipv6_loopback_blocked(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_url("https://[::1]/webhook")

    def test_public_ip_allowed(self):
        url = "https://8.8.8.8/webhook"
        self.assertEqual(self.s.validate_url(url), url)

    def test_non_ip_hostname_that_looks_like_domain_allowed(self):
        url = "https://hooks.partner-service.io/callback"
        self.assertEqual(self.s.validate_url(url), url)


class TestMessagingWebhookSerializerEventsValidation(TestCase):
    def setUp(self):
        self.s = serializers.MessagingWebhookSerializer()

    def test_non_list_rejected(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_events("message.sent")

    def test_unknown_event_type_rejected(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_events(["message.sent", "totally.made.up"])

    def test_empty_list_rejected(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self.s.validate_events([])

    def test_valid_events_pass(self):
        events = ["message.sent", "call.ended"]
        self.assertEqual(self.s.validate_events(events), events)


class TestMessageReportSerializerValidation(TestCase):
    def test_invalid_reason_rejected(self):
        s = serializers.MessageReportSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_reason("not_a_real_reason")

    def test_valid_reason_passes(self):
        from ..models import MessageReport
        s = serializers.MessageReportSerializer()
        self.assertEqual(s.validate_reason(MessageReport.REASON_SPAM), MessageReport.REASON_SPAM)


class TestPollVoteSerializerValidation(TestCase):
    def test_rejects_vote_on_non_poll_message(self):
        chat = InternalChatFactory()
        user = UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, sender=user, message_type="TEXT")
        s = serializers.PollVoteSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate({"message": msg})

    def test_allows_vote_on_poll_message(self):
        chat = InternalChatFactory()
        user = UserFactory()
        ChatParticipantFactory(chat=chat, user=user)
        msg = ChatMessageFactory(chat=chat, sender=user, message_type="POLL")
        s = serializers.PollVoteSerializer()
        attrs = {"message": msg}
        self.assertEqual(s.validate(attrs), attrs)

    def test_allows_missing_message(self):
        s = serializers.PollVoteSerializer()
        self.assertEqual(s.validate({}), {})


class TestUserDeviceSerializerValidation(TestCase):
    def test_blank_device_id_rejected(self):
        s = serializers.UserDeviceSerializer()
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_device_id("   ")

    def test_valid_device_id_passes(self):
        s = serializers.UserDeviceSerializer()
        self.assertEqual(s.validate_device_id("device-123"), "device-123")


class TestMessageLinkPreviewSerializerMethod(TestCase):
    def test_preview_detail_none_when_no_preview(self):
        s = serializers.MessageLinkPreviewSerializer()
        fake = MagicMock()
        fake.preview = None
        self.assertIsNone(s.get_preview_detail(fake))

    def test_preview_detail_returns_dict_when_present(self):
        from ..models import LinkPreview
        preview = LinkPreview.objects.create(
            url="https://example.com", title="Example", description="desc",
            domain="example.com",
        )
        s = serializers.MessageLinkPreviewSerializer()
        fake = MagicMock()
        fake.preview = preview
        result = s.get_preview_detail(fake)
        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["title"], "Example")
        self.assertEqual(result["domain"], "example.com")
