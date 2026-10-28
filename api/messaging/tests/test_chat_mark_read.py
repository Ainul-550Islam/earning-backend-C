"""
Tests for InternalChatViewSet.mark_read.

Audit finding: InternalChatViewSet had no dedicated HTTP-level test file.
Its `mark_read` action's own docstring promised it would update the
requesting user's ChatParticipant.last_read_at ("clearing the unread badge
for this chat"), but the implementation actually called
services.mark_inbox_items_read() — an unrelated operation on the UserInbox
notifications model that never touches ChatParticipant at all.

Consequence: ChatParticipant.last_read_at (read by InternalChatSerializer
and ChatMessageQuerySet.unread_for_user() to compute unread counts) could
never be advanced through any reachable code path. Unread counts could
only grow, never clear, for every chat in the system.

ChatParticipant.mark_read() itself was correct and already had a model-level
unit test (test_models.py::test_mark_read_updates_timestamp) — it was simply
never wired into the API. These tests cover the corrected wiring via the new
services.mark_chat_read().
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import ChatParticipantFactory, InternalChatFactory, UserFactory
from ..models import ChatParticipant


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestChatMarkRead(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.chat = InternalChatFactory()
        self.participant = ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_mark_read_updates_participant_last_read_at(self):
        self.assertIsNone(self.participant.last_read_at)

        resp = _api(self.user).post(f"/messaging/chats/{self.chat.id}/mark_read/")

        self.assertEqual(resp.status_code, 200)
        self.participant.refresh_from_db()
        self.assertIsNotNone(self.participant.last_read_at)
        self.assertIsNotNone(resp.data["last_read_at"])

    def test_mark_read_does_not_touch_other_users_inbox_or_participant_rows(self):
        """
        Regression guard for the original bug: mark_read on chat A must not
        depend on / fall through to the generic, chat-agnostic
        mark_inbox_items_read() behavior.
        """
        other_participant = ChatParticipantFactory(chat=self.chat, user=self.other_user)
        self.assertIsNone(other_participant.last_read_at)

        _api(self.user).post(f"/messaging/chats/{self.chat.id}/mark_read/")

        other_participant.refresh_from_db()
        self.assertIsNone(
            other_participant.last_read_at,
            "mark_read for one participant must not mark another participant's row read.",
        )

    def test_mark_read_requires_participant(self):
        non_member = UserFactory()
        resp = _api(non_member).post(f"/messaging/chats/{self.chat.id}/mark_read/")
        self.assertEqual(resp.status_code, 403)

    def test_mark_read_unknown_chat_returns_404(self):
        resp = _api(self.user).post("/messaging/chats/00000000-0000-0000-0000-000000000000/mark_read/")
        self.assertEqual(resp.status_code, 404)

    def test_mark_read_unauthenticated_blocked(self):
        resp = APIClient().post(f"/messaging/chats/{self.chat.id}/mark_read/")
        self.assertIn(resp.status_code, [401, 403])
