"""
test_viewsets_coverage_boost.py
================================
Coverage for the ViewSets in messaging/viewsets.py that had NO prior test
coverage at all: AdminBroadcastViewSet, SupportThreadViewSet, UserInboxViewSet,
MessageReactionViewSet, UserPresenceViewSet, CallSessionViewSet,
AnnouncementChannelViewSet, ScheduledMessageViewSet, MessagePinViewSet,
BotConfigViewSet, MessagingWebhookViewSet, UserBlockViewSet,
MessageSearchViewSet, DeviceTokenViewSet, MessageEditHistoryViewSet,
DisappearingMessageViewSet, UserStoryViewSet, VoiceMessageViewSet,
LinkPreviewViewSet.

Place in: messaging/tests/test_viewsets_coverage_boost.py
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
    GroupChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    AdminBroadcastFactory,
    SupportThreadFactory,
    SupportMessageFactory,
    UserInboxFactory,
    MessageReactionFactory,
    UserPresenceFactory,
    CallSessionFactory,
    AnnouncementChannelFactory,
    DeviceTokenFactory,
    UserStoryFactory,
    BotConfigFactory,
    MessagePinFactory,
)
from ..models import (
    AdminBroadcast,
    SupportThread,
    UserInbox,
    MessageReaction,
    UserPresence,
    CallSession,
    AnnouncementChannel,
    ChannelMember,
    ScheduledMessage,
    MessagePin,
    BotConfig,
    MessagingWebhook,
    UserBlock,
    DeviceToken,
    MessageEditHistory,
    DisappearingMessageConfig,
    UserStory,
    StoryView,
    VoiceMessageTranscription,
    LinkPreview,
    MessageLinkPreview,
    ChatMessage,
)


def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def _admin():
    return UserFactory(is_staff=True, is_superuser=True)


def _chat_with_participant(role="MEMBER", user=None):
    user = user or UserFactory()
    chat = InternalChatFactory()
    ChatParticipantFactory(chat=chat, user=user, role=role)
    return chat, user


# ─────────────────────────────────────────────────────────────────────────────
# AdminBroadcastViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminBroadcastViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_list_requires_admin(self):
        r = _api(self.user).get("/messaging/broadcasts/")
        self.assertEqual(r.status_code, 403)

    def test_list_as_admin(self):
        AdminBroadcastFactory(created_by=self.admin)
        r = _api(self.admin).get("/messaging/broadcasts/")
        self.assertEqual(r.status_code, 200)

    def test_create_routes_through_service(self):
        r = _api(self.admin).post("/messaging/broadcasts/", {
            "title": "New Feature", "body": "Check it out!",
            "audience_type": "ALL_USERS",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        broadcast = AdminBroadcast.objects.get(pk=r.data["id"])
        self.assertEqual(broadcast.status, "DRAFT")
        self.assertEqual(broadcast.created_by_id, self.admin.pk)

    def test_send_not_found(self):
        r = _api(self.admin).post(f"/messaging/broadcasts/{uuid.uuid4()}/send/")
        self.assertEqual(r.status_code, 404)

    def test_send_success(self):
        b = AdminBroadcastFactory(created_by=self.admin, status="DRAFT")
        with patch("messaging.services.send_broadcast") as mock_send:
            mock_send.return_value = {"sent": 1}
            r = _api(self.admin).post(f"/messaging/broadcasts/{b.pk}/send/")
        self.assertEqual(r.status_code, 200)

    def test_send_async_queues_task(self):
        b = AdminBroadcastFactory(created_by=self.admin, status="DRAFT")
        r = _api(self.admin).post(f"/messaging/broadcasts/{b.pk}/send_async/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["queued"])


# ─────────────────────────────────────────────────────────────────────────────
# SupportThreadViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestSupportThreadViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_list_scoped_to_own_threads_for_regular_user(self):
        SupportThreadFactory(user=self.user)
        SupportThreadFactory(user=UserFactory())
        r = _api(self.user).get("/messaging/support/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 1)

    def test_list_sees_all_threads_for_staff(self):
        SupportThreadFactory(user=self.user)
        SupportThreadFactory(user=UserFactory())
        r = _api(self.admin).get("/messaging/support/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 2)

    def test_create_thread(self):
        r = _api(self.user).post("/messaging/support/", {
            "subject": "Payment issue",
            "initial_message": "My payout never arrived.",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(SupportThread.objects.filter(user=self.user).exists())

    def test_create_thread_invalid_missing_subject(self):
        r = _api(self.user).post("/messaging/support/", {
            "initial_message": "Hello",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_retrieve_includes_messages(self):
        thread = SupportThreadFactory(user=self.user)
        SupportMessageFactory(thread=thread, sender=self.user, content="hi")
        r = _api(self.user).get(f"/messaging/support/{thread.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("messages", r.data)
        self.assertEqual(len(r.data["messages"]), 1)

    def test_retrieve_not_found(self):
        r = _api(self.user).get(f"/messaging/support/{uuid.uuid4()}/")
        self.assertEqual(r.status_code, 404)

    def test_reply_requires_content(self):
        thread = SupportThreadFactory(user=self.user)
        r = _api(self.user).post(f"/messaging/support/{thread.pk}/reply/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_reply_success(self):
        thread = SupportThreadFactory(user=self.user)
        r = _api(self.user).post(f"/messaging/support/{thread.pk}/reply/", {
            "content": "Any update?",
        }, format="json")
        self.assertEqual(r.status_code, 201)

    def test_assign_requires_admin(self):
        thread = SupportThreadFactory(user=self.user)
        agent = _admin()
        r = _api(self.user).post(f"/messaging/support/{thread.pk}/assign/", {
            "agent_id": agent.pk,
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_assign_requires_agent_id(self):
        thread = SupportThreadFactory(user=self.user)
        r = _api(self.admin).post(f"/messaging/support/{thread.pk}/assign/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_assign_success(self):
        thread = SupportThreadFactory(user=self.user)
        agent = _admin()
        r = _api(self.admin).post(f"/messaging/support/{thread.pk}/assign/", {
            "agent_id": agent.pk,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_agent_id, agent.pk)

    def test_transition_requires_status(self):
        thread = SupportThreadFactory(user=self.user)
        r = _api(self.admin).post(f"/messaging/support/{thread.pk}/transition/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_transition_success(self):
        thread = SupportThreadFactory(user=self.user, status="OPEN")
        r = _api(self.admin).post(f"/messaging/support/{thread.pk}/transition/", {
            "status": "IN_PROGRESS",
        }, format="json")
        self.assertEqual(r.status_code, 200)

    def test_transition_invalid_status(self):
        thread = SupportThreadFactory(user=self.user, status="OPEN")
        r = _api(self.admin).post(f"/messaging/support/{thread.pk}/transition/", {
            "status": "NOT_A_REAL_STATUS",
        }, format="json")
        self.assertEqual(r.status_code, 400)


# ─────────────────────────────────────────────────────────────────────────────
# UserInboxViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestUserInboxViewSet(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_list_only_own_unarchived(self):
        UserInboxFactory(user=self.user, is_archived=False)
        UserInboxFactory(user=self.user, is_archived=True)
        UserInboxFactory(user=UserFactory())
        r = _api(self.user).get("/messaging/inbox/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 1)

    def test_unread_count(self):
        UserInboxFactory(user=self.user, is_read=False)
        UserInboxFactory(user=self.user, is_read=False)
        r = _api(self.user).get("/messaging/inbox/unread_count/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["unread_count"], 2)

    def test_mark_all_read(self):
        UserInboxFactory(user=self.user, is_read=False)
        UserInboxFactory(user=self.user, is_read=False)
        r = _api(self.user).post("/messaging/inbox/mark_all_read/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["updated"], 2)
        self.assertEqual(UserInbox.objects.filter(user=self.user, is_read=False).count(), 0)

    def test_mark_read_single_item(self):
        item = UserInboxFactory(user=self.user, is_read=False)
        r = _api(self.user).post(f"/messaging/inbox/{item.pk}/mark_read/")
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.is_read)

    def test_archive(self):
        item = UserInboxFactory(user=self.user, is_archived=False)
        r = _api(self.user).post(f"/messaging/inbox/{item.pk}/archive/")
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.is_archived)

    def test_archive_not_found_for_other_users_item(self):
        item = UserInboxFactory(user=UserFactory())
        r = _api(self.user).post(f"/messaging/inbox/{item.pk}/archive/")
        self.assertEqual(r.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# MessageReactionViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageReactionViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_add_requires_fields(self):
        r = _api(self.user).post("/messaging/reactions/add/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_add_success(self):
        r = _api(self.user).post("/messaging/reactions/add/", {
            "message_id": str(self.msg.id), "emoji": "🔥",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(MessageReaction.objects.filter(message=self.msg, emoji="🔥").exists())

    def test_add_message_not_found(self):
        r = _api(self.user).post("/messaging/reactions/add/", {
            "message_id": str(uuid.uuid4()), "emoji": "🔥",
        }, format="json")
        self.assertEqual(r.status_code, 404)

    def test_remove_requires_fields(self):
        r = _api(self.user).post("/messaging/reactions/remove/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_remove_success(self):
        MessageReactionFactory(message=self.msg, user=self.user, emoji="👍")
        r = _api(self.user).post("/messaging/reactions/remove/", {
            "message_id": str(self.msg.id), "emoji": "👍",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["deleted"])

    def test_for_message_requires_message_id(self):
        r = _api(self.user).get("/messaging/reactions/for_message/")
        self.assertEqual(r.status_code, 400)

    def test_for_message_groups_by_emoji(self):
        MessageReactionFactory(message=self.msg, user=self.user, emoji="👍")
        MessageReactionFactory(message=self.msg, user=UserFactory(), emoji="👍")
        r = _api(self.user).get(f"/messaging/reactions/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["👍"], 2)


# ─────────────────────────────────────────────────────────────────────────────
# UserPresenceViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestUserPresenceViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()

    def test_me(self):
        UserPresenceFactory(user=self.user, status="ONLINE")
        r = _api(self.user).get("/messaging/presence/me/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("status", r.data)

    def test_update_status_requires_status(self):
        r = _api(self.user).post("/messaging/presence/update_status/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_update_status_success(self):
        r = _api(self.user).post("/messaging/presence/update_status/", {
            "status": "ONLINE", "platform": "ios",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ONLINE")

    def test_set_custom_status(self):
        r = _api(self.user).post("/messaging/presence/set_custom_status/", {
            "custom_status": "In a meeting", "emoji": "📅",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["custom_status"], "In a meeting")
        presence = UserPresence.objects.get(user=self.user)
        self.assertEqual(presence.custom_status, "In a meeting")

    def test_for_chat_requires_chat_id(self):
        r = _api(self.user).get("/messaging/presence/for_chat/")
        self.assertEqual(r.status_code, 400)

    def test_for_chat_not_found(self):
        r = _api(self.user).get(f"/messaging/presence/for_chat/?chat_id={uuid.uuid4()}")
        self.assertEqual(r.status_code, 404)

    def test_for_chat_access_denied(self):
        outsider = UserFactory()
        r = _api(outsider).get(f"/messaging/presence/for_chat/?chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 403)

    def test_for_chat_success(self):
        r = _api(self.user).get(f"/messaging/presence/for_chat/?chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 200)

    def test_bulk(self):
        u2 = UserFactory()
        UserPresenceFactory(user=self.user)
        UserPresenceFactory(user=u2)
        r = _api(self.user).get(f"/messaging/presence/bulk/?user_ids={self.user.pk}&user_ids={u2.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)


# ─────────────────────────────────────────────────────────────────────────────
# CallSessionViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestCallSessionViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()

    def test_list_own_calls(self):
        call = CallSessionFactory(initiated_by=self.user)
        call.participants.add(self.user)
        r = _api(self.user).get("/messaging/calls/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_initiate_requires_chat_id(self):
        r = _api(self.user).post("/messaging/calls/initiate/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_initiate_success(self):
        r = _api(self.user).post("/messaging/calls/initiate/", {
            "chat_id": str(self.chat.id), "call_type": "AUDIO",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("room_id", r.data)
        self.assertIn("ice_servers", r.data)

    def test_initiate_access_denied(self):
        outsider = UserFactory()
        r = _api(outsider).post("/messaging/calls/initiate/", {
            "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_accept(self):
        call = CallSessionFactory(initiated_by=self.user, status="RINGING")
        r = _api(self.user).post(f"/messaging/calls/{call.pk}/accept/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ONGOING")

    def test_accept_wrong_status(self):
        call = CallSessionFactory(initiated_by=self.user, status="ENDED")
        r = _api(self.user).post(f"/messaging/calls/{call.pk}/accept/")
        self.assertEqual(r.status_code, 400)

    def test_decline(self):
        call = CallSessionFactory(initiated_by=self.user, status="RINGING")
        r = _api(self.user).post(f"/messaging/calls/{call.pk}/decline/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "DECLINED")

    def test_end(self):
        call = CallSessionFactory(initiated_by=self.user, status="ONGOING", started_at=timezone.now())
        r = _api(self.user).post(f"/messaging/calls/{call.pk}/end/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ENDED")

    def test_history(self):
        call = CallSessionFactory(initiated_by=self.user, status="ENDED")
        call.participants.add(self.user)
        r = _api(self.user).get("/messaging/calls/history/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)


# ─────────────────────────────────────────────────────────────────────────────
# AnnouncementChannelViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestAnnouncementChannelViewSet(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_list(self):
        AnnouncementChannelFactory(channel_type="PUBLIC")
        r = _api(self.user).get("/messaging/channels/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_list_filtered_by_type(self):
        AnnouncementChannelFactory(channel_type="PUBLIC")
        AnnouncementChannelFactory(channel_type="PRIVATE")
        r = _api(self.user).get("/messaging/channels/?type=PRIVATE")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["channel_type"], "PRIVATE")

    def test_create(self):
        r = _api(self.user).post("/messaging/channels/", {
            "name": "Product Updates", "description": "News.",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(AnnouncementChannel.objects.filter(slug=r.data["slug"]).exists())

    def test_subscribe(self):
        channel = AnnouncementChannelFactory()
        r = _api(self.user).post(f"/messaging/channels/{channel.pk}/subscribe/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ChannelMember.objects.filter(channel=channel, user=self.user).exists())

    def test_unsubscribe(self):
        channel = AnnouncementChannelFactory()
        from .. import services
        services.subscribe_channel(channel_id=channel.pk, user_id=self.user.pk)
        r = _api(self.user).post(f"/messaging/channels/{channel.pk}/unsubscribe/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["unsubscribed"])

    def test_members(self):
        channel = AnnouncementChannelFactory()
        ChannelMember.objects.create(channel=channel, user=self.user)
        r = _api(self.user).get(f"/messaging/channels/{channel.pk}/members/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)


# ─────────────────────────────────────────────────────────────────────────────
# ScheduledMessageViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduledMessageViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()

    def test_list_own_scheduled(self):
        ScheduledMessage.objects.create(
            chat=self.chat, sender=self.user, content="later",
            scheduled_for=timezone.now() + timedelta(hours=1),
        )
        r = _api(self.user).get("/messaging/scheduled/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_create_requires_fields(self):
        r = _api(self.user).post("/messaging/scheduled/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_create_invalid_datetime(self):
        r = _api(self.user).post("/messaging/scheduled/", {
            "chat_id": str(self.chat.id), "content": "hi", "scheduled_for": "not-a-date",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_create_success(self):
        future = (timezone.now() + timedelta(hours=2)).isoformat()
        r = _api(self.user).post("/messaging/scheduled/", {
            "chat_id": str(self.chat.id), "content": "Happy Monday!", "scheduled_for": future,
        }, format="json")
        self.assertEqual(r.status_code, 201)

    def test_destroy_cancels(self):
        sched = ScheduledMessage.objects.create(
            chat=self.chat, sender=self.user, content="later",
            scheduled_for=timezone.now() + timedelta(hours=1),
        )
        r = _api(self.user).delete(f"/messaging/scheduled/{sched.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["cancelled"])

    def test_destroy_not_sender_denied(self):
        sched = ScheduledMessage.objects.create(
            chat=self.chat, sender=self.user, content="later",
            scheduled_for=timezone.now() + timedelta(hours=1),
        )
        other = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=other)
        r = _api(other).delete(f"/messaging/scheduled/{sched.pk}/")
        self.assertEqual(r.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# MessagePinViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessagePinViewSet(TestCase):
    def setUp(self):
        self.chat, self.admin_user = _chat_with_participant(role="ADMIN")
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.admin_user)

    def test_for_chat_requires_chat_id(self):
        r = _api(self.admin_user).get("/messaging/pins/for_chat/")
        self.assertEqual(r.status_code, 400)

    def test_for_chat_success(self):
        MessagePinFactory(message=self.msg, chat=self.chat, pinned_by=self.admin_user)
        r = _api(self.admin_user).get(f"/messaging/pins/for_chat/?chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_pin_requires_fields(self):
        r = _api(self.admin_user).post("/messaging/pins/pin/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_pin_success_as_admin(self):
        r = _api(self.admin_user).post("/messaging/pins/pin/", {
            "message_id": str(self.msg.id), "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 201)

    def test_pin_denied_for_member(self):
        member = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=member, role="MEMBER")
        r = _api(member).post("/messaging/pins/pin/", {
            "message_id": str(self.msg.id), "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_unpin_requires_fields(self):
        r = _api(self.admin_user).post("/messaging/pins/unpin/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unpin_success(self):
        MessagePinFactory(message=self.msg, chat=self.chat, pinned_by=self.admin_user)
        r = _api(self.admin_user).post("/messaging/pins/unpin/", {
            "message_id": str(self.msg.id), "chat_id": str(self.chat.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["unpinned"])


# ─────────────────────────────────────────────────────────────────────────────
# BotConfigViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestBotConfigViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()

    def test_list_requires_admin(self):
        r = _api(self.user).get("/messaging/bots/")
        self.assertEqual(r.status_code, 403)

    def test_list_as_admin(self):
        BotConfigFactory()
        r = _api(self.admin).get("/messaging/bots/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_create(self):
        r = _api(self.admin).post("/messaging/bots/", {
            "name": "Welcome Bot", "trigger_type": "KEYWORD", "trigger_value": "hi",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(BotConfig.objects.filter(pk=r.data["id"]).exists())

    def test_destroy(self):
        bot = BotConfigFactory()
        r = _api(self.admin).delete(f"/messaging/bots/{bot.pk}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(BotConfig.objects.filter(pk=bot.pk).exists())

    def test_toggle_not_found(self):
        r = _api(self.admin).post(f"/messaging/bots/{uuid.uuid4()}/toggle/")
        self.assertEqual(r.status_code, 404)

    def test_toggle_success(self):
        bot = BotConfigFactory(is_active=True)
        r = _api(self.admin).post(f"/messaging/bots/{bot.pk}/toggle/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_active"])
        bot.refresh_from_db()
        self.assertFalse(bot.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# MessagingWebhookViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessagingWebhookViewSet(TestCase):
    def setUp(self):
        self.admin = _admin()

    def test_list(self):
        MessagingWebhook.objects.create(name="W1", url="https://example.com/hook", secret="s3cr3t")
        r = _api(self.admin).get("/messaging/webhooks/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_create_generates_secret_if_missing(self):
        r = _api(self.admin).post("/messaging/webhooks/", {
            "name": "New Hook", "url": "https://example.com/hook2",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["secret"])

    def test_destroy(self):
        webhook = MessagingWebhook.objects.create(name="W1", url="https://example.com/hook", secret="s3cr3t")
        r = _api(self.admin).delete(f"/messaging/webhooks/{webhook.pk}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(MessagingWebhook.objects.filter(pk=webhook.pk).exists())

    def test_test_action_not_found(self):
        r = _api(self.admin).post(f"/messaging/webhooks/{uuid.uuid4()}/test/")
        self.assertEqual(r.status_code, 404)

    def test_test_action_scopes_to_single_webhook(self):
        # Regression test for the bug where "test" fanned the event out to
        # every registered webhook instead of just the one being tested.
        target = MessagingWebhook.objects.create(
            name="Target", url="https://example.com/target", secret="s1",
            events=["message.sent"],
        )
        other = MessagingWebhook.objects.create(
            name="Other", url="https://example.com/other", secret="s2",
            events=["message.sent"],
        )
        with patch("messaging.tasks.dispatch_webhook_task.delay") as mock_delay:
            r = _api(self.admin).post(f"/messaging/webhooks/{target.pk}/test/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["queued"])
        mock_delay.assert_called_once()
        _, kwargs = mock_delay.call_args
        self.assertEqual(kwargs.get("webhook_id"), str(target.pk))


# ─────────────────────────────────────────────────────────────────────────────
# UserBlockViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestUserBlockViewSet(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.target = UserFactory()

    def test_list(self):
        UserBlock.objects.create(blocker=self.user, blocked=self.target)
        r = _api(self.user).get("/messaging/blocks/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_block_requires_user_id(self):
        r = _api(self.user).post("/messaging/blocks/block/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_block_success(self):
        r = _api(self.user).post("/messaging/blocks/block/", {
            "user_id": self.target.pk, "reason": "spam",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(UserBlock.objects.filter(blocker=self.user, blocked=self.target).exists())

    def test_block_self_rejected(self):
        r = _api(self.user).post("/messaging/blocks/block/", {
            "user_id": self.user.pk,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unblock_requires_user_id(self):
        # Also exercises the fix for the NameError bug (undefined 'pk') that
        # previously crashed this action on every call.
        r = _api(self.user).post("/messaging/blocks/unblock/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unblock_success(self):
        UserBlock.objects.create(blocker=self.user, blocked=self.target)
        r = _api(self.user).post("/messaging/blocks/unblock/", {
            "user_id": self.target.pk,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["unblocked"])
        self.assertFalse(UserBlock.objects.filter(blocker=self.user, blocked=self.target).exists())

    def test_is_blocked_requires_user_id(self):
        r = _api(self.user).get("/messaging/blocks/is_blocked/")
        self.assertEqual(r.status_code, 400)

    def test_is_blocked_true(self):
        UserBlock.objects.create(blocker=self.user, blocked=self.target)
        r = _api(self.user).get(f"/messaging/blocks/is_blocked/?user_id={self.target.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_blocked"])


# ─────────────────────────────────────────────────────────────────────────────
# MessageSearchViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageSearchViewSet(TestCase):
    def test_search_empty_query_returns_empty(self):
        user = UserFactory()
        r = _api(user).get("/messaging/search-vs/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_search_finds_matching_message(self):
        chat, user = _chat_with_participant()
        ChatMessageFactory(chat=chat, sender=user, content="the quarterly report is ready")
        r = _api(user).get("/messaging/search-vs/?q=quarterly")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# DeviceTokenViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestDeviceTokenViewSet(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_list_only_own_active(self):
        DeviceTokenFactory(user=self.user, is_active=True)
        DeviceTokenFactory(user=self.user, is_active=False)
        DeviceTokenFactory(user=UserFactory())
        r = _api(self.user).get("/messaging/device-tokens/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_create_requires_token(self):
        r = _api(self.user).post("/messaging/device-tokens/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_create_registers_token(self):
        r = _api(self.user).post("/messaging/device-tokens/", {
            "token": "abc123", "platform": "ios", "device_name": "iPhone 17",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["registered"])

    def test_create_idempotent_on_same_token(self):
        DeviceToken.objects.create(user=self.user, token="dup-token", platform="android", is_active=True)
        r = _api(self.user).post("/messaging/device-tokens/", {
            "token": "dup-token", "platform": "android",
        }, format="json")
        self.assertEqual(r.status_code, 200)

    def test_destroy_deactivates(self):
        token = DeviceTokenFactory(user=self.user)
        r = _api(self.user).delete(f"/messaging/device-tokens/{token.pk}/")
        self.assertEqual(r.status_code, 204)
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_unregister_token(self):
        DeviceTokenFactory(user=self.user, token="tok-xyz")
        r = _api(self.user).delete("/messaging/device-tokens/unregister_token/", {
            "token": "tok-xyz",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["unregistered"])
        self.assertFalse(DeviceToken.objects.filter(token="tok-xyz", is_active=True).exists())


# ─────────────────────────────────────────────────────────────────────────────
# MessageEditHistoryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageEditHistoryViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="original")

    def test_for_message_requires_message_id(self):
        r = _api(self.user).get("/messaging/edit-history/for_message/")
        self.assertEqual(r.status_code, 400)

    def test_for_message_empty_when_never_edited(self):
        r = _api(self.user).get(f"/messaging/edit-history/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_for_message_returns_history(self):
        MessageEditHistory.objects.create(
            message=self.msg, edited_by=self.user, previous_content="original", edit_number=1,
        )
        r = _api(self.user).get(f"/messaging/edit-history/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_edit_message_requires_fields(self):
        r = _api(self.user).post("/messaging/edit-history/edit_message/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_edit_message_success(self):
        r = _api(self.user).post("/messaging/edit-history/edit_message/", {
            "message_id": str(self.msg.id), "content": "updated content",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_edited"])
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.content, "updated content")


# ─────────────────────────────────────────────────────────────────────────────
# DisappearingMessageViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestDisappearingMessageViewSet(TestCase):
    def setUp(self):
        self.chat, self.admin_user = _chat_with_participant(role="OWNER")

    def test_config_requires_chat_id(self):
        r = _api(self.admin_user).get("/messaging/disappearing/config/")
        self.assertEqual(r.status_code, 400)

    def test_config_defaults_disabled_when_missing(self):
        r = _api(self.admin_user).get(f"/messaging/disappearing/config/?chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_enabled"])

    def test_set_config_requires_chat_id(self):
        r = _api(self.admin_user).post("/messaging/disappearing/set_config/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_set_config_enable(self):
        r = _api(self.admin_user).post("/messaging/disappearing/set_config/", {
            "chat_id": str(self.chat.id), "ttl_seconds": 3600,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_enabled"])
        self.assertEqual(r.data["ttl_seconds"], 3600)

    def test_set_config_denied_for_member(self):
        member = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=member, role="MEMBER")
        r = _api(member).post("/messaging/disappearing/set_config/", {
            "chat_id": str(self.chat.id), "ttl_seconds": 3600,
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_config_after_being_set(self):
        DisappearingMessageConfig.objects.create(
            chat=self.chat, is_enabled=True, ttl_seconds=86400, enabled_by=self.admin_user,
            enabled_at=timezone.now(),
        )
        r = _api(self.admin_user).get(f"/messaging/disappearing/config/?chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_enabled"])
        self.assertEqual(r.data["ttl_seconds"], 86400)


# ─────────────────────────────────────────────────────────────────────────────
# UserStoryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestUserStoryViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()

    def test_list_stories_tray(self):
        r = _api(self.user).get("/messaging/stories/")
        self.assertEqual(r.status_code, 200)

    def test_create_story(self):
        r = _api(self.user).post("/messaging/stories/", {
            "story_type": "text", "content": "Hello world!",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(UserStory.objects.filter(user=self.user).exists())

    def test_view_story(self):
        # Part 21 (world-system audit) tightened view_story() to require
        # the viewer share a chat with the story's owner - same relationship
        # get_active_stories_for_contacts() already required to *show* a
        # story, now also enforced on the view action itself. Needs a
        # shared chat to exercise the (still-working) happy path.
        other = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=other)
        story = UserStoryFactory(user=other)
        r = _api(self.user).post(f"/messaging/stories/{story.pk}/view/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["viewed"])
        self.assertTrue(StoryView.objects.filter(story=story, viewer=self.user).exists())

    def test_view_story_stranger_forbidden(self):
        # The gap Part 21 closed: previously any authenticated user could
        # view any story regardless of tenant or contact relationship.
        stranger = UserFactory()
        story = UserStoryFactory(user=stranger)
        r = _api(self.user).post(f"/messaging/stories/{story.pk}/view/")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(StoryView.objects.filter(story=story, viewer=self.user).exists())

    def test_view_story_not_found(self):
        r = _api(self.user).post(f"/messaging/stories/{uuid.uuid4()}/view/")
        self.assertEqual(r.status_code, 400)

    def test_reply_to_story(self):
        other = UserFactory()
        story = UserStoryFactory(user=other)
        StoryView.objects.create(story=story, viewer=self.user)
        r = _api(self.user).post(f"/messaging/stories/{story.pk}/reply/", {
            "reply_text": "Love this!",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["replied"])

    def test_viewers_visible_to_owner(self):
        story = UserStoryFactory(user=self.user)
        viewer = UserFactory()
        StoryView.objects.create(story=story, viewer=viewer)
        r = _api(self.user).get(f"/messaging/stories/{story.pk}/viewers/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_destroy_own_story(self):
        story = UserStoryFactory(user=self.user)
        r = _api(self.user).delete(f"/messaging/stories/{story.pk}/")
        self.assertEqual(r.status_code, 204)
        story.refresh_from_db()
        self.assertFalse(story.is_active)

    def test_my_stories(self):
        UserStoryFactory(user=self.user)
        UserStoryFactory(user=UserFactory())
        r = _api(self.user).get("/messaging/stories/my_stories/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)


# ─────────────────────────────────────────────────────────────────────────────
# VoiceMessageViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceMessageViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, message_type="AUDIO")

    def test_transcription_requires_message_id(self):
        r = _api(self.user).get("/messaging/voice/transcription/")
        self.assertEqual(r.status_code, 400)

    def test_transcription_not_yet_transcribed(self):
        r = _api(self.user).get(f"/messaging/voice/transcription/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 404)

    def test_transcription_success(self):
        VoiceMessageTranscription.objects.create(
            message=self.msg, transcribed_text="hello there", language="en", confidence=0.95,
        )
        r = _api(self.user).get(f"/messaging/voice/transcription/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["text"], "hello there")

    def test_transcription_access_denied_for_non_participant(self):
        VoiceMessageTranscription.objects.create(
            message=self.msg, transcribed_text="hello there",
        )
        outsider = UserFactory()
        r = _api(outsider).get(f"/messaging/voice/transcription/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 403)

    def test_request_transcription(self):
        r = _api(self.user).post("/messaging/voice/request_transcription/", {
            "message_id": str(self.msg.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["queued"])


# ─────────────────────────────────────────────────────────────────────────────
# LinkPreviewViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestLinkPreviewViewSet(TestCase):
    def setUp(self):
        self.chat, self.user = _chat_with_participant()
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_for_message_requires_message_id(self):
        r = _api(self.user).get("/messaging/link-previews/for_message/")
        self.assertEqual(r.status_code, 400)

    def test_for_message_returns_links(self):
        preview = LinkPreview.objects.create(url="https://example.com", title="Example")
        MessageLinkPreview.objects.create(message=self.msg, preview=preview)
        r = _api(self.user).get(f"/messaging/link-previews/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["title"], "Example")

    def test_fetch_requires_url(self):
        r = _api(self.user).post("/messaging/link-previews/fetch/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_fetch_success(self):
        with patch("messaging.utils.link_preview.fetch_link_preview") as mock_fetch:
            mock_fetch.return_value = {"url": "https://example.com", "title": "Example"}
            r = _api(self.user).post("/messaging/link-previews/fetch/", {
                "url": "https://example.com",
            }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["title"], "Example")

    def test_dismiss(self):
        preview = LinkPreview.objects.create(url="https://example.com")
        mlp = MessageLinkPreview.objects.create(message=self.msg, preview=preview)
        r = _api(self.user).post(f"/messaging/link-previews/{mlp.pk}/dismiss/")
        self.assertEqual(r.status_code, 200)
        mlp.refresh_from_db()
        self.assertTrue(mlp.is_dismissed)
