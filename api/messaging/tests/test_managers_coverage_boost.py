"""
Coverage-boost tests for messaging/managers.py.

These exercise every QuerySet/Manager method with real DB round-trips
(no mocking of the manager layer) so that filter/exclude logic, guard
clauses, and chained calls all actually execute against SQLite —
consistent with this project's "dynamic execution surfaces real bugs"
testing philosophy.

Caller cross-check (see session handoff item 3): grepped the whole
non-test codebase for every public method on these managers/querysets.
Only two call sites exist in production code:
  - viewsets.py InternalChatViewSet.get_queryset():
        InternalChat.objects.for_user(pk).with_last_message().with_participants()
  - services.py (direct-chat lookup):
        InternalChat.objects.get_direct_chat(user_id_a, user_id_b)
Both match their manager signatures exactly - no parameter-mismatch bugs
found here. The remaining methods are not yet wired into any view/service/
task, which is why coverage was low; they're tested directly below.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from api.messaging.models import (
    InternalChat,
    ChatMessage,
    AdminBroadcast,
    SupportThread,
    UserInbox,
)
from api.messaging.tests.factories import (
    UserFactory,
    InternalChatFactory,
    GroupChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    AdminBroadcastFactory,
    SupportThreadFactory,
    UserInboxFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# InternalChat
# ---------------------------------------------------------------------------

class TestInternalChatQuerySetAndManager:
    def test_active_returns_only_active(self):
        active_chat = InternalChatFactory(status="ACTIVE")
        InternalChatFactory(status="ARCHIVED")
        InternalChatFactory(status="DELETED")
        result = list(InternalChat.objects.active())
        assert active_chat in result
        assert all(c.status == "ACTIVE" for c in result)

    def test_archived_returns_only_archived(self):
        archived_chat = InternalChatFactory(status="ARCHIVED")
        InternalChatFactory(status="ACTIVE")
        result = list(InternalChat.objects.get_queryset().archived())
        assert archived_chat in result
        assert all(c.status == "ARCHIVED" for c in result)

    def test_not_deleted_excludes_deleted(self):
        deleted_chat = InternalChatFactory(status="DELETED")
        active_chat = InternalChatFactory(status="ACTIVE")
        result = list(InternalChat.objects.get_queryset().not_deleted())
        assert deleted_chat not in result
        assert active_chat in result

    def test_for_user_raises_on_none(self):
        with pytest.raises(ValueError):
            InternalChat.objects.get_queryset().for_user(None)
        with pytest.raises(ValueError):
            InternalChat.objects.for_user(None)

    def test_for_user_returns_chats_with_participant(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        other_chat = InternalChatFactory()
        result = list(InternalChat.objects.for_user(user.pk))
        assert chat in result
        assert other_chat not in result

    def test_for_user_excludes_deleted(self):
        user = UserFactory()
        chat = InternalChatFactory(status="DELETED")
        ChatParticipantFactory(chat=chat, user=user)
        result = list(InternalChat.objects.for_user(user.pk))
        assert chat not in result

    def test_direct_chats(self):
        direct = InternalChatFactory(is_group=False)
        group = GroupChatFactory()
        result = list(InternalChat.objects.get_queryset().direct_chats())
        assert direct in result
        assert group not in result

    def test_group_chats(self):
        direct = InternalChatFactory(is_group=False)
        group = GroupChatFactory()
        result = list(InternalChat.objects.get_queryset().group_chats())
        assert group in result
        assert direct not in result

    def test_with_participants_prefetches_without_error(self):
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat)
        qs = InternalChat.objects.get_queryset().with_participants()
        fetched = qs.get(pk=chat.pk)
        assert list(fetched.participants.all())

    def test_with_last_message_orders_without_error(self):
        InternalChatFactory()
        qs = InternalChat.objects.get_queryset().with_last_message()
        assert list(qs) is not None

    def test_get_direct_chat_raises_on_none(self):
        user = UserFactory()
        with pytest.raises(ValueError):
            InternalChat.objects.get_direct_chat(None, user.pk)
        with pytest.raises(ValueError):
            InternalChat.objects.get_direct_chat(user.pk, None)

    def test_get_direct_chat_found(self):
        user_a = UserFactory()
        user_b = UserFactory()
        chat = InternalChatFactory(is_group=False)
        ChatParticipantFactory(chat=chat, user=user_a)
        ChatParticipantFactory(chat=chat, user=user_b)
        found = InternalChat.objects.get_direct_chat(user_a.pk, user_b.pk)
        assert found == chat

    def test_get_direct_chat_not_found_returns_none(self):
        user_a = UserFactory()
        user_b = UserFactory()
        found = InternalChat.objects.get_direct_chat(user_a.pk, user_b.pk)
        assert found is None

    def test_get_direct_chat_ignores_group_chats(self):
        user_a = UserFactory()
        user_b = UserFactory()
        chat = GroupChatFactory()
        ChatParticipantFactory(chat=chat, user=user_a)
        ChatParticipantFactory(chat=chat, user=user_b)
        found = InternalChat.objects.get_direct_chat(user_a.pk, user_b.pk)
        assert found is None


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class TestChatMessageQuerySetAndManager:
    def test_visible_excludes_deleted(self):
        visible_msg = ChatMessageFactory(status="SENT")
        deleted_msg = ChatMessageFactory(status="DELETED")
        result = list(ChatMessage.objects.visible())
        assert visible_msg in result
        assert deleted_msg not in result

    def test_for_chat_raises_on_none(self):
        with pytest.raises(ValueError):
            ChatMessage.objects.get_queryset().for_chat(None)
        with pytest.raises(ValueError):
            ChatMessage.objects.for_chat(None)

    def test_for_chat_filters_and_orders(self):
        chat = InternalChatFactory()
        other_chat = InternalChatFactory()
        msg1 = ChatMessageFactory(chat=chat)
        ChatMessageFactory(chat=other_chat)
        result = list(ChatMessage.objects.for_chat(chat.pk))
        assert msg1 in result
        assert all(m.chat_id == chat.pk for m in result)

    def test_for_chat_excludes_deleted(self):
        chat = InternalChatFactory()
        deleted_msg = ChatMessageFactory(chat=chat, status="DELETED")
        result = list(ChatMessage.objects.for_chat(chat.pk))
        assert deleted_msg not in result

    def test_unread_for_user_none_last_read_returns_all(self):
        msg = ChatMessageFactory()
        qs = ChatMessage.objects.get_queryset().unread_for_user(msg.sender_id, None)
        assert msg in list(qs)

    def test_unread_for_user_excludes_own_messages(self):
        sender = UserFactory()
        cutoff = timezone.now() - timedelta(days=1)
        own_msg = ChatMessageFactory(sender=sender)
        result = list(
            ChatMessage.objects.get_queryset().unread_for_user(sender.pk, cutoff)
        )
        assert own_msg not in result

    def test_unread_for_user_includes_others_after_cutoff(self):
        sender = UserFactory()
        other = UserFactory()
        cutoff = timezone.now() - timedelta(days=1)
        other_msg = ChatMessageFactory(sender=other)
        result = list(
            ChatMessage.objects.get_queryset().unread_for_user(sender.pk, cutoff)
        )
        assert other_msg in result

    def test_with_sender_select_related(self):
        msg = ChatMessageFactory()
        qs = ChatMessage.objects.get_queryset().with_sender()
        fetched = qs.get(pk=msg.pk)
        assert fetched.sender_id == msg.sender_id


# ---------------------------------------------------------------------------
# AdminBroadcast
# ---------------------------------------------------------------------------

class TestAdminBroadcastQuerySetAndManager:
    def test_draft(self):
        draft = AdminBroadcastFactory(status="DRAFT")
        AdminBroadcastFactory(status="SENT")
        result = list(AdminBroadcast.objects.draft())
        assert draft in result
        assert all(b.status == "DRAFT" for b in result)

    def test_scheduled(self):
        scheduled = AdminBroadcastFactory(
            status="SCHEDULED", scheduled_at=timezone.now() + timedelta(days=1)
        )
        result = list(AdminBroadcast.objects.get_queryset().scheduled())
        assert scheduled in result

    def test_due_for_sending(self):
        # AdminBroadcast.clean() requires scheduled_at to be in the future
        # at save time, so a "due" row is created validly (future time),
        # then backdated via a bare queryset .update() - which bypasses
        # clean() - to simulate real wall-clock time having passed.
        due = AdminBroadcastFactory(
            status="SCHEDULED", scheduled_at=timezone.now() + timedelta(hours=1)
        )
        AdminBroadcast.objects.filter(pk=due.pk).update(
            scheduled_at=timezone.now() - timedelta(hours=1)
        )
        not_due = AdminBroadcastFactory(
            status="SCHEDULED", scheduled_at=timezone.now() + timedelta(hours=1)
        )
        result = list(AdminBroadcast.objects.due_for_sending())
        assert due.pk in [b.pk for b in result]
        assert not_due not in result

    def test_sent(self):
        sent = AdminBroadcastFactory(status="SENT")
        result = list(AdminBroadcast.objects.sent())
        assert sent in result

    def test_failed(self):
        failed = AdminBroadcastFactory(status="FAILED")
        result = list(AdminBroadcast.objects.get_queryset().failed())
        assert failed in result

    def test_by_creator_raises_on_none(self):
        with pytest.raises(ValueError):
            AdminBroadcast.objects.get_queryset().by_creator(None)

    def test_by_creator_filters(self):
        creator = UserFactory()
        broadcast = AdminBroadcastFactory(created_by=creator)
        other = AdminBroadcastFactory()
        result = list(AdminBroadcast.objects.get_queryset().by_creator(creator.pk))
        assert broadcast in result
        assert other not in result


# ---------------------------------------------------------------------------
# SupportThread
# ---------------------------------------------------------------------------

class TestSupportThreadQuerySetAndManager:
    def test_open(self):
        open_thread = SupportThreadFactory(status="OPEN")
        closed_thread = SupportThreadFactory(status="CLOSED")
        result = list(SupportThread.objects.open())
        assert open_thread in result
        assert closed_thread not in result

    def test_in_progress(self):
        t = SupportThreadFactory(status="IN_PROGRESS")
        result = list(SupportThread.objects.get_queryset().in_progress())
        assert t in result

    def test_closed(self):
        t = SupportThreadFactory(status="CLOSED")
        result = list(SupportThread.objects.get_queryset().closed())
        assert t in result

    def test_active_excludes_closed(self):
        closed = SupportThreadFactory(status="CLOSED")
        open_ = SupportThreadFactory(status="OPEN")
        result = list(SupportThread.objects.get_queryset().active())
        assert closed not in result
        assert open_ in result

    def test_for_user_raises_on_none(self):
        with pytest.raises(ValueError):
            SupportThread.objects.get_queryset().for_user(None)
        with pytest.raises(ValueError):
            SupportThread.objects.for_user(None)

    def test_for_user(self):
        user = UserFactory()
        thread = SupportThreadFactory(user=user)
        result = list(SupportThread.objects.for_user(user.pk))
        assert thread in result

    def test_for_agent_raises_on_none(self):
        with pytest.raises(ValueError):
            SupportThread.objects.get_queryset().for_agent(None)

    def test_for_agent(self):
        agent = UserFactory()
        thread = SupportThreadFactory(assigned_agent=agent)
        result = list(SupportThread.objects.get_queryset().for_agent(agent.pk))
        assert thread in result

    def test_unassigned(self):
        unassigned = SupportThreadFactory(assigned_agent=None)
        agent = UserFactory()
        assigned = SupportThreadFactory(assigned_agent=agent)
        result = list(SupportThread.objects.get_queryset().unassigned())
        assert unassigned in result
        assert assigned not in result

    def test_by_priority(self):
        urgent = SupportThreadFactory(priority="URGENT")
        result = list(SupportThread.objects.get_queryset().by_priority("URGENT"))
        assert urgent in result

    def test_urgent(self):
        urgent = SupportThreadFactory(priority="URGENT")
        normal = SupportThreadFactory(priority="NORMAL")
        result = list(SupportThread.objects.get_queryset().urgent())
        assert urgent in result
        assert normal not in result

    def test_with_messages_without_error(self):
        thread = SupportThreadFactory()
        qs = SupportThread.objects.get_queryset().with_messages()
        assert qs.get(pk=thread.pk) == thread

    def test_unassigned_open(self):
        agent = UserFactory()
        unassigned_open = SupportThreadFactory(status="OPEN", assigned_agent=None)
        assigned_open = SupportThreadFactory(status="OPEN", assigned_agent=agent)
        closed = SupportThreadFactory(status="CLOSED", assigned_agent=None)
        result = list(SupportThread.objects.unassigned_open())
        assert unassigned_open in result
        assert assigned_open not in result
        assert closed not in result


# ---------------------------------------------------------------------------
# UserInbox
# ---------------------------------------------------------------------------

class TestUserInboxQuerySetAndManager:
    def test_for_user_raises_on_none(self):
        with pytest.raises(ValueError):
            UserInbox.objects.get_queryset().for_user(None)

    def test_for_user(self):
        user = UserFactory()
        item = UserInboxFactory(user=user)
        other = UserInboxFactory()
        result = list(UserInbox.objects.for_user(user.pk))
        assert item in result
        assert other not in result

    def test_unread(self):
        unread = UserInboxFactory(is_read=False)
        read = UserInboxFactory(is_read=True, read_at=timezone.now())
        result = list(UserInbox.objects.get_queryset().unread())
        assert unread in result
        assert read not in result

    def test_read(self):
        read = UserInboxFactory(is_read=True, read_at=timezone.now())
        unread = UserInboxFactory(is_read=False)
        result = list(UserInbox.objects.get_queryset().read())
        assert read in result
        assert unread not in result

    def test_not_archived(self):
        active = UserInboxFactory(is_archived=False)
        archived = UserInboxFactory(is_archived=True)
        result = list(UserInbox.objects.get_queryset().not_archived())
        assert active in result
        assert archived not in result

    def test_of_type_raises_on_empty(self):
        with pytest.raises(ValueError):
            UserInbox.objects.get_queryset().of_type("")
        with pytest.raises(ValueError):
            UserInbox.objects.get_queryset().of_type(None)

    def test_of_type(self):
        item = UserInboxFactory(item_type="CHAT_MESSAGE")
        result = list(UserInbox.objects.get_queryset().of_type("CHAT_MESSAGE"))
        assert item in result

    def test_unread_count_for_user_on_queryset(self):
        user = UserFactory()
        UserInboxFactory(user=user, is_read=False, is_archived=False)
        UserInboxFactory(
            user=user, is_read=True, is_archived=False, read_at=timezone.now()
        )
        count = UserInbox.objects.get_queryset().unread_count_for_user(user.pk)
        assert count == 1

    def test_manager_for_user_orders_and_excludes_archived(self):
        user = UserFactory()
        visible = UserInboxFactory(user=user, is_archived=False)
        archived = UserInboxFactory(user=user, is_archived=True)
        result = list(UserInbox.objects.for_user(user.pk))
        assert visible in result
        assert archived not in result

    def test_manager_unread_for_user(self):
        user = UserFactory()
        item = UserInboxFactory(user=user, is_read=False)
        read_item = UserInboxFactory(
            user=user, is_read=True, read_at=timezone.now()
        )
        result = list(UserInbox.objects.unread_for_user(user.pk))
        assert item in result
        assert read_item not in result

    def test_manager_unread_count(self):
        user = UserFactory()
        UserInboxFactory(user=user, is_read=False, is_archived=False)
        UserInboxFactory(user=user, is_read=False, is_archived=False)
        assert UserInbox.objects.unread_count(user.pk) == 2

    def test_bulk_mark_read_rejects_non_list(self):
        user = UserFactory()
        assert UserInbox.objects.bulk_mark_read(user.pk, "not-a-list") == 0
        assert UserInbox.objects.bulk_mark_read(user.pk, None) == 0
        assert UserInbox.objects.bulk_mark_read(user.pk, {"a": 1}) == 0

    def test_bulk_mark_read_rejects_empty_list(self):
        user = UserFactory()
        assert UserInbox.objects.bulk_mark_read(user.pk, []) == 0

    def test_bulk_mark_read_updates_only_matching_rows(self):
        user = UserFactory()
        item1 = UserInboxFactory(user=user, is_read=False)
        item2 = UserInboxFactory(user=user, is_read=False)
        other_user_item = UserInboxFactory(is_read=False)
        already_read = UserInboxFactory(
            user=user, is_read=True, read_at=timezone.now()
        )

        updated = UserInbox.objects.bulk_mark_read(
            user.pk,
            [item1.pk, item2.pk, other_user_item.pk, already_read.pk],
        )

        assert updated == 2

        item1.refresh_from_db()
        item2.refresh_from_db()
        other_user_item.refresh_from_db()

        assert item1.is_read is True
        assert item2.is_read is True
        assert item1.read_at is not None
        assert item1.updated_at is not None
        assert other_user_item.is_read is False
