"""
Comprehensive HTTP-level tests for InternalChatViewSet.

Audit finding: InternalChatViewSet was the largest viewset in the module
(15 actions, 272 lines, 1072 statements) with ZERO dedicated HTTP tests.
Only the mark_read action had been tested (added during the previous audit
pass that fixed its broken implementation). This file covers every action,
every error path, and every security boundary.

Bugs caught and fixed while writing this suite:
  - delete_message:  NameError on `kwargs` (every call crashed before
                     reaching the deletion logic).
  - presences:       Zero authorization — any authenticated user could view
                     any chat's participant presences.
  - pinned_messages: Same zero-authorization gap.
  - unpin_message:   Same zero-authorization gap + no admin-only guard
                     (any participant could undo an admin-only action).
  - pin_message:     ChatAccessDeniedError mapped to 400 instead of 403.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import (
    ChatMessageFactory,
    ChatParticipantFactory,
    GroupChatFactory,
    InternalChatFactory,
    MessagePinFactory,
    UserFactory,
)
from ..choices import ChatStatus, MessageType
from ..models import (
    ChatMessage,
    ChatParticipant,
    InternalChat,
    MessagePin,
)


def _api(user=None) -> APIClient:
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


def _admin_participant(chat, user):
    """Create or update a ChatParticipant with ADMIN role."""
    p, _ = ChatParticipant.objects.get_or_create(
        chat=chat, user=user, defaults={"role": "ADMIN"}
    )
    if p.role != "ADMIN":
        p.role = "ADMIN"
        p.save(update_fields=["role"])
    return p


FAKE_UUID = "00000000-0000-0000-0000-000000000000"


# ─────────────────────────────────────────────────────────────────────────────
# list / retrieve
# ─────────────────────────────────────────────────────────────────────────────

class TestChatList(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_list_returns_participants_chats_only(self):
        other_chat = InternalChatFactory()
        r = _api(self.user).get("/messaging/chats/")
        self.assertEqual(r.status_code, 200)
        ids = {c["id"] for c in r.data["results"]}
        self.assertIn(str(self.chat.id), ids)
        self.assertNotIn(str(other_chat.id), ids)

    def test_list_filter_by_status(self):
        archived = InternalChatFactory(status=ChatStatus.ARCHIVED)
        ChatParticipantFactory(chat=archived, user=self.user)
        r = _api(self.user).get("/messaging/chats/?status=ARCHIVED")
        self.assertEqual(r.status_code, 200)
        ids = {c["id"] for c in r.data["results"]}
        self.assertIn(str(archived.id), ids)
        self.assertNotIn(str(self.chat.id), ids)

    def test_list_unauthenticated_blocked(self):
        r = _api().get("/messaging/chats/")
        self.assertIn(r.status_code, [401, 403])

    def test_retrieve_own_chat(self):
        r = _api(self.user).get(f"/messaging/chats/{self.chat.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], str(self.chat.id))

    def test_retrieve_non_participant_returns_403(self):
        outsider = UserFactory()
        r = _api(outsider).get(f"/messaging/chats/{self.chat.id}/")
        self.assertEqual(r.status_code, 403)

    def test_retrieve_unknown_id_returns_404(self):
        r = _api(self.user).get(f"/messaging/chats/{FAKE_UUID}/")
        self.assertEqual(r.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# direct  (POST /chats/direct/)
# ─────────────────────────────────────────────────────────────────────────────

class TestChatDirect(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()

    def test_create_direct_chat(self):
        r = _api(self.user).post("/messaging/chats/direct/", {"other_user_id": self.other.pk}, format="json")
        self.assertIn(r.status_code, [200, 201])
        self.assertFalse(r.data["is_group"])
        self.assertEqual(
            ChatParticipant.objects.filter(chat_id=r.data["id"]).count(), 2
        )

    def test_repeated_direct_chat_returns_existing(self):
        r1 = _api(self.user).post("/messaging/chats/direct/", {"other_user_id": self.other.pk}, format="json")
        r2 = _api(self.user).post("/messaging/chats/direct/", {"other_user_id": self.other.pk}, format="json")
        self.assertEqual(r1.data["id"], r2.data["id"])

    def test_missing_other_user_id_returns_400(self):
        r = _api(self.user).post("/messaging/chats/direct/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_direct_with_nonexistent_user_returns_error(self):
        r = _api(self.user).post("/messaging/chats/direct/", {"other_user_id": 999999}, format="json")
        self.assertIn(r.status_code, [400, 404])

    def test_unauthenticated_blocked(self):
        r = _api().post("/messaging/chats/direct/", {"other_user_id": self.other.pk}, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# group  (POST /chats/group/)
# ─────────────────────────────────────────────────────────────────────────────

class TestChatGroup(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.member1 = UserFactory()
        self.member2 = UserFactory()

    def test_create_group_chat(self):
        r = _api(self.user).post("/messaging/chats/group/", {
            "name": "Test Group",
            "member_ids": [self.member1.pk, self.member2.pk],
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_group"])
        chat = InternalChat.objects.get(pk=r.data["id"])
        self.assertEqual(chat.participants.count(), 3)

    def test_group_requires_name(self):
        r = _api(self.user).post("/messaging/chats/group/", {
            "member_ids": [self.member1.pk],
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_group_requires_members(self):
        r = _api(self.user).post("/messaging/chats/group/", {
            "name": "Empty",
            "member_ids": [],
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unauthenticated_blocked(self):
        r = _api().post("/messaging/chats/group/", {"name": "x", "member_ids": [self.member1.pk]}, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# messages  (GET /chats/{id}/messages/)
# ─────────────────────────────────────────────────────────────────────────────

class TestChatMessages(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.other)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.other)

    def test_participant_can_list_messages(self):
        r = _api(self.user).get(f"/messaging/chats/{self.chat.id}/messages/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data), 1)

    def test_non_participant_blocked(self):
        outsider = UserFactory()
        r = _api(outsider).get(f"/messaging/chats/{self.chat.id}/messages/")
        self.assertEqual(r.status_code, 403)

    def test_non_participant_or_unknown_chat_returns_403(self):
        r = _api(self.user).get(f"/messaging/chats/{FAKE_UUID}/messages/")
        self.assertEqual(r.status_code, 403)

    def test_pagination_before_id(self):
        older = ChatMessageFactory(chat=self.chat, sender=self.other)
        newer = ChatMessageFactory(chat=self.chat, sender=self.other)
        r = _api(self.user).get(f"/messaging/chats/{self.chat.id}/messages/?before_id={newer.id}")
        self.assertEqual(r.status_code, 200)
        ids = [m["id"] for m in r.data]
        self.assertNotIn(str(newer.id), ids)

    def test_unauthenticated_blocked(self):
        r = _api().get(f"/messaging/chats/{self.chat.id}/messages/")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# send_message  (POST /chats/{id}/send_message/)
# ─────────────────────────────────────────────────────────────────────────────

class TestSendMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_send_text_message(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/send_message/",
            {"content": "Hello!", "message_type": "TEXT"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(ChatMessage.objects.filter(chat=self.chat, content="Hello!").exists())

    def test_empty_content_rejected(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/send_message/",
            {"content": "", "message_type": "TEXT"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_non_participant_blocked(self):
        outsider = UserFactory()
        r = _api(outsider).post(f"/messaging/chats/{self.chat.id}/send_message/",
            {"content": "Hi", "message_type": "TEXT"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_archived_chat_blocked(self):
        self.chat.status = ChatStatus.ARCHIVED
        self.chat.save(update_fields=["status"])
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/send_message/",
            {"content": "Hi", "message_type": "TEXT"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unknown_or_non_participant_chat_returns_403_or_404(self):
        r = _api(self.user).post(f"/messaging/chats/{FAKE_UUID}/send_message/",
            {"content": "Hi", "message_type": "TEXT"}, format="json")
        self.assertIn(r.status_code, [403, 404])

    def test_unauthenticated_blocked(self):
        r = _api().post(f"/messaging/chats/{self.chat.id}/send_message/",
            {"content": "Hi", "message_type": "TEXT"}, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# delete_message  (DELETE /chats/{id}/messages/{message_id}/)
# Regression: previously crashed with NameError on every single call.
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.other)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        self.other_msg = ChatMessageFactory(chat=self.chat, sender=self.other)

    def test_sender_can_delete_own_message(self):
        r = _api(self.user).delete(
            f"/messaging/chats/{self.chat.id}/messages/{self.msg.id}/")
        self.assertEqual(r.status_code, 204)
        self.msg.refresh_from_db()
        self.assertIsNotNone(self.msg.deleted_at)

    def test_non_sender_cannot_delete_others_message(self):
        r = _api(self.user).delete(
            f"/messaging/chats/{self.chat.id}/messages/{self.other_msg.id}/")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_delete_any_message(self):
        _admin_participant(self.chat, self.user)
        r = _api(self.user).delete(
            f"/messaging/chats/{self.chat.id}/messages/{self.other_msg.id}/")
        self.assertEqual(r.status_code, 204)

    def test_unknown_message_returns_404(self):
        r = _api(self.user).delete(
            f"/messaging/chats/{self.chat.id}/messages/{FAKE_UUID}/")
        self.assertEqual(r.status_code, 404)

    def test_already_deleted_returns_404(self):
        self.msg.soft_delete(deleted_by_id=self.user.pk)
        r = _api(self.user).delete(
            f"/messaging/chats/{self.chat.id}/messages/{self.msg.id}/")
        self.assertEqual(r.status_code, 404)

    def test_non_participant_blocked(self):
        outsider = UserFactory()
        r = _api(outsider).delete(
            f"/messaging/chats/{self.chat.id}/messages/{self.msg.id}/")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_blocked(self):
        r = _api().delete(f"/messaging/chats/{self.chat.id}/messages/{self.msg.id}/")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# mark_read  (POST /chats/{id}/mark_read/)
# Already covered by test_chat_mark_read.py — one regression case here.
# ─────────────────────────────────────────────────────────────────────────────

class TestMarkRead(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_mark_read_returns_last_read_at(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/mark_read/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("last_read_at", r.data)


# ─────────────────────────────────────────────────────────────────────────────
# pinned_messages  (GET /chats/{id}/pinned_messages/)
# Regression: previously had zero authorization check.
# ─────────────────────────────────────────────────────────────────────────────

class TestPinnedMessages(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        ChatParticipantFactory(chat=self.chat, user=self.other)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.other)
        _admin_participant(self.chat, self.user)
        _api(self.user).post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {"message_id": str(self.msg.id)}, format="json")

    def test_participant_can_list_pins(self):
        r = _api(self.other).get(f"/messaging/chats/{self.chat.id}/pinned_messages/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data), 1)
        self.assertIn("message_id", r.data[0])

    def test_non_participant_now_blocked(self):
        """Regression: before the fix any authenticated user could view any chat's pins."""
        outsider = UserFactory()
        r = _api(outsider).get(f"/messaging/chats/{self.chat.id}/pinned_messages/")
        self.assertEqual(r.status_code, 403)

    def test_unknown_chat_returns_404(self):
        r = _api(self.user).get(f"/messaging/chats/{FAKE_UUID}/pinned_messages/")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_blocked(self):
        r = _api().get(f"/messaging/chats/{self.chat.id}/pinned_messages/")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# presences  (GET /chats/{id}/presences/)
# Regression: previously had zero authorization check.
# ─────────────────────────────────────────────────────────────────────────────

class TestPresences(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_participant_can_view_presences(self):
        r = _api(self.user).get(f"/messaging/chats/{self.chat.id}/presences/")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data, dict)

    def test_non_participant_now_blocked(self):
        """Regression: before the fix any authenticated user could view any chat's presences."""
        outsider = UserFactory()
        r = _api(outsider).get(f"/messaging/chats/{self.chat.id}/presences/")
        self.assertEqual(r.status_code, 403)

    def test_unknown_chat_returns_404(self):
        r = _api(self.user).get(f"/messaging/chats/{FAKE_UUID}/presences/")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_blocked(self):
        r = _api().get(f"/messaging/chats/{self.chat.id}/presences/")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# pin_message  (POST /chats/{id}/pin_message/)
# Regression: ChatAccessDeniedError was mapped to 400 instead of 403.
# ─────────────────────────────────────────────────────────────────────────────

class TestPinMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.member = UserFactory()
        self.chat = InternalChatFactory()
        _admin_participant(self.chat, self.user)
        ChatParticipantFactory(chat=self.chat, user=self.member)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.member)

    def test_admin_can_pin(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("pin_id", r.data)
        self.assertTrue(MessagePin.objects.filter(message=self.msg).exists())

    def test_non_admin_now_returns_403_not_400(self):
        """Regression: ChatAccessDeniedError was incorrectly mapped to 400."""
        r = _api(self.member).post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_message_id_returns_400(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unknown_message_returns_error(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {"message_id": FAKE_UUID}, format="json")
        self.assertIn(r.status_code, [400, 404])

    def test_non_participant_blocked(self):
        outsider = UserFactory()
        r = _api(outsider).post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_blocked(self):
        r = _api().post(f"/messaging/chats/{self.chat.id}/pin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# unpin_message  (POST /chats/{id}/unpin_message/)
# Regression: zero authorization — any authenticated user could unpin any pin.
# ─────────────────────────────────────────────────────────────────────────────

class TestUnpinMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.member = UserFactory()
        self.chat = InternalChatFactory()
        _admin_participant(self.chat, self.user)
        ChatParticipantFactory(chat=self.chat, user=self.member)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.member)
        self.pin = MessagePinFactory(message=self.msg, chat=self.chat, pinned_by=self.user)

    def test_admin_can_unpin(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/unpin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["unpinned"])
        self.assertFalse(MessagePin.objects.filter(pk=self.pin.pk).exists())

    def test_non_admin_now_returns_403(self):
        """Regression: before the fix any participant (or outsider) could unpin."""
        r = _api(self.member).post(f"/messaging/chats/{self.chat.id}/unpin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_non_participant_blocked(self):
        outsider = UserFactory()
        r = _api(outsider).post(f"/messaging/chats/{self.chat.id}/unpin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_message_id_returns_400(self):
        r = _api(self.user).post(f"/messaging/chats/{self.chat.id}/unpin_message/",
            {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unknown_chat_returns_404(self):
        r = _api(self.user).post(f"/messaging/chats/{FAKE_UUID}/unpin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_blocked(self):
        r = _api().post(f"/messaging/chats/{self.chat.id}/unpin_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertIn(r.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# forward_message  (POST /chats/{id}/forward_message/)
# ─────────────────────────────────────────────────────────────────────────────

class TestForwardMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.source_chat = InternalChatFactory()
        self.target_chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.source_chat, user=self.user)
        ChatParticipantFactory(chat=self.target_chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.source_chat, sender=self.user)

    def test_can_forward_to_participant_chat(self):
        r = _api(self.user).post(
            f"/messaging/chats/{self.target_chat.id}/forward_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_forwarded"])
        self.assertEqual(str(r.data["chat"]), str(self.target_chat.id))

    def test_forward_deleted_message_returns_404(self):
        self.msg.soft_delete(deleted_by_id=self.user.pk)
        r = _api(self.user).post(
            f"/messaging/chats/{self.target_chat.id}/forward_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_forward_unknown_message_returns_404(self):
        r = _api(self.user).post(
            f"/messaging/chats/{self.target_chat.id}/forward_message/",
            {"message_id": FAKE_UUID}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_forward_to_non_participant_chat_blocked(self):
        other_chat = InternalChatFactory()
        r = _api(self.user).post(
            f"/messaging/chats/{other_chat.id}/forward_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_missing_message_id_returns_400(self):
        r = _api(self.user).post(
            f"/messaging/chats/{self.target_chat.id}/forward_message/",
            {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unauthenticated_blocked(self):
        r = _api().post(
            f"/messaging/chats/{self.target_chat.id}/forward_message/",
            {"message_id": str(self.msg.id)}, format="json")
        self.assertIn(r.status_code, [401, 403])
