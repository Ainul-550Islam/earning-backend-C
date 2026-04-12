"""
Service layer tests — comprehensive coverage for all service functions.
"""
from __future__ import annotations

import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock

from .factories import (
    UserFactory, InternalChatFactory, GroupChatFactory,
    ChatParticipantFactory, ChatMessageFactory,
    AdminBroadcastFactory, SupportThreadFactory, SupportMessageFactory,
    UserInboxFactory, MessageReactionFactory, DeviceTokenFactory,
    BotConfigFactory,
)
from ..models import (
    InternalChat, ChatParticipant, ChatMessage,
    AdminBroadcast, SupportThread, UserInbox,
    MessageReaction, UserPresence, CallSession, UserBlock,
)
from ..choices import (
    ChatStatus, MessageStatus, BroadcastStatus, SupportThreadStatus, CallStatus,
)
from ..exceptions import (
    ChatNotFoundError, ChatAccessDeniedError, ChatArchivedError,
    MessageNotFoundError, MessageDeletedError, BroadcastStateError,
    SupportThreadClosedError, SupportThreadLimitError,
    UserNotFoundError, RateLimitError, MessagingError,
)
from .. import services


class TestCreateDirectChat(TestCase):
    def setUp(self):
        self.user_a = UserFactory()
        self.user_b = UserFactory()

    def test_creates_new_direct_chat(self):
        chat = services.create_direct_chat(self.user_a.pk, self.user_b.pk)
        self.assertFalse(chat.is_group)
        self.assertEqual(chat.status, ChatStatus.ACTIVE)
        self.assertEqual(chat.participants.count(), 2)

    def test_returns_existing_chat_if_already_exists(self):
        chat1 = services.create_direct_chat(self.user_a.pk, self.user_b.pk)
        chat2 = services.create_direct_chat(self.user_a.pk, self.user_b.pk)
        self.assertEqual(str(chat1.id), str(chat2.id))

    def test_raises_if_same_user(self):
        with self.assertRaises(MessagingError):
            services.create_direct_chat(self.user_a.pk, self.user_a.pk)

    def test_raises_if_user_not_found(self):
        with self.assertRaises(UserNotFoundError):
            services.create_direct_chat(self.user_a.pk, 99999999)


class TestCreateGroupChat(TestCase):
    def setUp(self):
        self.creator = UserFactory()
        self.members = [UserFactory() for _ in range(3)]

    def test_creates_group_chat(self):
        chat = services.create_group_chat(
            creator_id=self.creator.pk,
            name="Test Group",
            member_ids=[m.pk for m in self.members],
        )
        self.assertTrue(chat.is_group)
        self.assertEqual(chat.name, "Test Group")
        self.assertEqual(chat.participants.count(), 4)  # creator + 3 members

    def test_creator_gets_owner_role(self):
        chat = services.create_group_chat(
            creator_id=self.creator.pk,
            name="Test Group",
            member_ids=[self.members[0].pk],
        )
        creator_part = ChatParticipant.objects.get(chat=chat, user=self.creator)
        self.assertEqual(creator_part.role, "OWNER")

    def test_raises_if_empty_name(self):
        with self.assertRaises(MessagingError):
            services.create_group_chat(creator_id=self.creator.pk, name="", member_ids=[])


class TestSendChatMessage(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_sends_text_message(self):
        msg = services.send_chat_message(
            chat_id=str(self.chat.id),
            sender_id=self.user.pk,
            content="Hello world",
        )
        self.assertEqual(msg.content, "Hello world")
        self.assertEqual(msg.message_type, "TEXT")
        self.assertEqual(msg.status, MessageStatus.SENT)

    def test_creates_inbox_items_for_other_participants(self):
        other_user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=other_user)
        services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="Hi",
        )
        self.assertTrue(
            UserInbox.objects.filter(user=other_user, item_type="CHAT_MESSAGE").exists()
        )

    def test_raises_if_not_participant(self):
        outsider = UserFactory()
        with self.assertRaises(ChatAccessDeniedError):
            services.send_chat_message(
                chat_id=str(self.chat.id), sender_id=outsider.pk, content="Hi",
            )

    def test_raises_if_chat_archived(self):
        self.chat.status = ChatStatus.ARCHIVED
        self.chat.save()
        with self.assertRaises(ChatArchivedError):
            services.send_chat_message(
                chat_id=str(self.chat.id), sender_id=self.user.pk, content="Hi",
            )

    def test_raises_if_empty_text(self):
        with self.assertRaises(MessagingError):
            services.send_chat_message(
                chat_id=str(self.chat.id), sender_id=self.user.pk, content="",
            )

    def test_touches_chat_last_message_at(self):
        before = self.chat.last_message_at
        services.send_chat_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk, content="Test",
        )
        self.chat.refresh_from_db()
        self.assertIsNotNone(self.chat.last_message_at)


class TestDeleteChatMessage(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_soft_deletes_own_message(self):
        services.delete_chat_message(
            message_id=str(self.msg.id), requesting_user_id=self.user.pk
        )
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, MessageStatus.DELETED)
        self.assertEqual(self.msg.content, "[This message was deleted]")

    def test_raises_if_already_deleted(self):
        self.msg.soft_delete()
        with self.assertRaises(MessageDeletedError):
            services.delete_chat_message(
                message_id=str(self.msg.id), requesting_user_id=self.user.pk
            )

    def test_raises_if_not_message_owner(self):
        other = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=other)
        with self.assertRaises(ChatAccessDeniedError):
            services.delete_chat_message(
                message_id=str(self.msg.id), requesting_user_id=other.pk
            )

    def test_admin_can_delete_others_message(self):
        admin_user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=admin_user, role="ADMIN")
        services.delete_chat_message(
            message_id=str(self.msg.id), requesting_user_id=admin_user.pk
        )
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, MessageStatus.DELETED)


class TestMessageReactions(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_add_reaction(self):
        reaction = services.add_reaction(
            message_id=str(self.msg.id), user_id=self.user.pk, emoji="👍",
        )
        self.assertEqual(reaction.emoji, "👍")
        self.assertEqual(reaction.user_id, self.user.pk)

    def test_add_reaction_idempotent(self):
        services.add_reaction(message_id=str(self.msg.id), user_id=self.user.pk, emoji="👍")
        services.add_reaction(message_id=str(self.msg.id), user_id=self.user.pk, emoji="👍")
        self.assertEqual(
            MessageReaction.objects.filter(message=self.msg, user=self.user, emoji="👍").count(), 1
        )

    def test_remove_reaction(self):
        services.add_reaction(message_id=str(self.msg.id), user_id=self.user.pk, emoji="❤️")
        deleted = services.remove_reaction(
            message_id=str(self.msg.id), user_id=self.user.pk, emoji="❤️"
        )
        self.assertTrue(deleted)
        self.assertFalse(
            MessageReaction.objects.filter(message=self.msg, user=self.user, emoji="❤️").exists()
        )

    def test_get_reaction_counts(self):
        user2 = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=user2)
        services.add_reaction(message_id=str(self.msg.id), user_id=self.user.pk, emoji="👍")
        services.add_reaction(message_id=str(self.msg.id), user_id=user2.pk, emoji="👍")
        services.add_reaction(message_id=str(self.msg.id), user_id=user2.pk, emoji="❤️")
        counts = services.get_message_reactions(str(self.msg.id))
        self.assertEqual(counts.get("👍"), 2)
        self.assertEqual(counts.get("❤️"), 1)


class TestUserPresence(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_update_presence_creates_record(self):
        presence = services.update_presence(user_id=self.user.pk, status="ONLINE")
        self.assertEqual(presence.status, "ONLINE")

    def test_get_presence_returns_offline_if_no_record(self):
        result = services.get_presence(99999)
        self.assertEqual(result["status"], "OFFLINE")

    def test_invisible_shows_offline(self):
        presence = services.update_presence(user_id=self.user.pk, status="ONLINE")
        UserPresence.objects.filter(pk=presence.pk).update(is_invisible=True)
        result = services.get_presence(self.user.pk)
        self.assertEqual(result["status"], "OFFLINE")


class TestCallServices(TestCase):
    def setUp(self):
        self.caller = UserFactory()
        self.callee = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.caller)
        ChatParticipantFactory(chat=self.chat, user=self.callee)

    def test_initiate_call(self):
        call = services.initiate_call(
            caller_id=self.caller.pk,
            chat_id=str(self.chat.id),
            call_type="AUDIO",
        )
        self.assertEqual(call.status, CallStatus.RINGING)
        self.assertEqual(call.initiated_by_id, self.caller.pk)
        self.assertIsNotNone(call.room_id)

    def test_accept_call(self):
        call = services.initiate_call(caller_id=self.caller.pk, chat_id=str(self.chat.id))
        call = services.accept_call(call_id=str(call.id), user_id=self.callee.pk)
        self.assertEqual(call.status, CallStatus.ONGOING)
        self.assertIsNotNone(call.started_at)

    def test_decline_call(self):
        call = services.initiate_call(caller_id=self.caller.pk, chat_id=str(self.chat.id))
        call = services.decline_call(call_id=str(call.id), user_id=self.callee.pk)
        self.assertEqual(call.status, CallStatus.DECLINED)

    def test_end_call(self):
        call = services.initiate_call(caller_id=self.caller.pk, chat_id=str(self.chat.id))
        services.accept_call(call_id=str(call.id), user_id=self.callee.pk)
        call = services.end_call(call_id=str(call.id), user_id=self.caller.pk)
        self.assertEqual(call.status, CallStatus.ENDED)


class TestUserBlock(TestCase):
    def setUp(self):
        self.blocker = UserFactory()
        self.blocked = UserFactory()

    def test_block_user(self):
        block = services.block_user(blocker_id=self.blocker.pk, blocked_id=self.blocked.pk)
        self.assertTrue(services.is_user_blocked(self.blocker.pk, self.blocked.pk))

    def test_unblock_user(self):
        services.block_user(blocker_id=self.blocker.pk, blocked_id=self.blocked.pk)
        deleted = services.unblock_user(blocker_id=self.blocker.pk, blocked_id=self.blocked.pk)
        self.assertTrue(deleted)
        self.assertFalse(services.is_user_blocked(self.blocker.pk, self.blocked.pk))

    def test_cannot_block_self(self):
        with self.assertRaises(MessagingError):
            services.block_user(blocker_id=self.blocker.pk, blocked_id=self.blocker.pk)

    def test_blocked_user_cannot_send_message(self):
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=self.blocker)
        ChatParticipantFactory(chat=chat, user=self.blocked)
        services.block_user(blocker_id=self.blocker.pk, blocked_id=self.blocked.pk)
        with self.assertRaises(ChatAccessDeniedError):
            services.send_chat_message(
                chat_id=str(chat.id), sender_id=self.blocked.pk, content="Hi"
            )


class TestBroadcast(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)
        self.broadcast = AdminBroadcastFactory(created_by=self.admin)

    def test_create_broadcast(self):
        b = services.create_broadcast(
            title="Test", body="Body content", created_by_id=self.admin.pk
        )
        self.assertEqual(b.status, BroadcastStatus.DRAFT)

    def test_send_broadcast(self):
        UserFactory.create_batch(5)
        result = services.send_broadcast(broadcast_id=str(self.broadcast.id))
        self.assertTrue(result["success"])
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.status, BroadcastStatus.SENT)

    def test_cannot_send_already_sent(self):
        self.broadcast.status = BroadcastStatus.SENT
        self.broadcast.save()
        with self.assertRaises(BroadcastStateError):
            services.send_broadcast(broadcast_id=str(self.broadcast.id))


class TestSupportThread(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.agent = UserFactory(is_staff=True)

    def test_create_support_thread(self):
        thread = services.create_support_thread(
            user_id=self.user.pk,
            subject="I have a problem",
            initial_message="Please help me.",
        )
        self.assertEqual(thread.status, SupportThreadStatus.OPEN)
        self.assertEqual(thread.messages.count(), 1)

    def test_reply_transitions_to_in_progress(self):
        thread = services.create_support_thread(
            user_id=self.user.pk, subject="Help", initial_message="Please help.",
        )
        services.reply_to_support_thread(
            thread_id=str(thread.id), sender_id=self.agent.pk,
            content="We are looking into this.", is_agent=True,
        )
        thread.refresh_from_db()
        self.assertEqual(thread.status, SupportThreadStatus.IN_PROGRESS)

    def test_cannot_reply_to_closed_thread(self):
        thread = services.create_support_thread(
            user_id=self.user.pk, subject="Help", initial_message="Please help.",
        )
        thread.status = SupportThreadStatus.CLOSED
        thread.save()
        with self.assertRaises(SupportThreadClosedError):
            services.reply_to_support_thread(
                thread_id=str(thread.id), sender_id=self.user.pk,
                content="Another message.", is_agent=False,
            )

    def test_support_thread_limit(self):
        from ..constants import MAX_SUPPORT_THREADS_PER_USER
        for i in range(MAX_SUPPORT_THREADS_PER_USER):
            services.create_support_thread(
                user_id=self.user.pk, subject=f"Issue {i}", initial_message="Help."
            )
        with self.assertRaises(SupportThreadLimitError):
            services.create_support_thread(
                user_id=self.user.pk, subject="One more", initial_message="Help."
            )


class TestScheduledMessages(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_schedule_future_message(self):
        future = timezone.now() + __import__("datetime").timedelta(hours=1)
        sched = services.schedule_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk,
            content="Future message", scheduled_for=future,
        )
        self.assertEqual(sched.status, "PENDING")

    def test_cannot_schedule_past_message(self):
        past = timezone.now() - __import__("datetime").timedelta(hours=1)
        with self.assertRaises(MessagingError):
            services.schedule_message(
                chat_id=str(self.chat.id), sender_id=self.user.pk,
                content="Past message", scheduled_for=past,
            )

    def test_cancel_scheduled_message(self):
        future = timezone.now() + __import__("datetime").timedelta(hours=1)
        sched = services.schedule_message(
            chat_id=str(self.chat.id), sender_id=self.user.pk,
            content="Cancel me", scheduled_for=future,
        )
        sched = services.cancel_scheduled_message(
            scheduled_id=str(sched.id), user_id=self.user.pk
        )
        self.assertEqual(sched.status, "CANCELLED")


class TestPollServices(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        self.voter = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.voter)

    def test_create_poll(self):
        poll_msg = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.user.pk,
            question="Best framework?",
            options=["Django", "FastAPI", "Flask"],
        )
        self.assertEqual(poll_msg.message_type, "POLL")
        self.assertEqual(len(poll_msg.poll_data["options"]), 3)

    def test_vote_on_poll(self):
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.user.pk,
            question="Favorite?", options=["A", "B"],
        )
        vote = services.vote_on_poll(
            message_id=str(poll.id), user_id=self.voter.pk, option_id="0"
        )
        self.assertEqual(vote.option_id, "0")

    def test_get_poll_results(self):
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.user.pk,
            question="Which?", options=["X", "Y"],
        )
        services.vote_on_poll(message_id=str(poll.id), user_id=self.voter.pk, option_id="0")
        results = services.get_poll_results(str(poll.id))
        self.assertEqual(results["total_votes"], 1)
        self.assertEqual(results["options"]["0"]["votes"], 1)
