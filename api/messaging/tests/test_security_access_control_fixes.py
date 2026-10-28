"""
test_security_access_control_fixes.py
========================================
Regression tests proving the access-control fixes from the security
audit round actually block unauthorized access, not just that existing
tests still pass with them in place.

Bugs fixed, all sharing the same root cause (a chat/message-scoped
function or queryset with no check that the requesting user is actually
a participant of the relevant chat):

  1. PollVoteViewSet.get_queryset() - had ZERO scoping. The bare list
     endpoint returned every vote from every user platform-wide,
     ?user_id=<any> pulled any user's full voting history, and there was
     no perform_update() check (only perform_destroy() had one).
  2. services.forward_message() - never checked the forwarder was a
     participant of the SOURCE chat before reading its content.
  3. services.translate_message() - same gap, exposed full translated
     message content.
  4. services.vote_on_poll() - non-participants could vote on polls in
     chats they have no access to.
  5. services.get_message_reactions() / get_poll_results() - exposed
     aggregate data for any message platform-wide with no membership
     check (both gained a new required requesting_user_id parameter).
  6. VoiceMessageViewSet.request_transcription() - no check before
     queuing a real transcription job for any message_id (resource-abuse
     angle, not just disclosure).
  7. LinkPreviewViewSet.for_message() - same disclosure gap; and
     LinkPreviewViewSet.fetch() had no rate limiting at all despite
     making a real outbound HTTP request to a caller-supplied URL.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from . import factories as f
from .. import services
from ..exceptions import ChatAccessDeniedError
from ..models import ChatParticipant, PollVote, MessageReaction, VoiceMessageTranscription
from ..throttling import LinkPreviewFetchThrottle


def _api(user=None) -> APIClient:
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


class SecurityFixtureMixin:
    """Standard fixture: a chat with one real member and one outsider."""

    def setUp(self):
        self.chat = f.InternalChatFactory()
        self.member = f.UserFactory()
        f.ChatParticipantFactory(chat=self.chat, user=self.member)
        self.outsider = f.UserFactory()
        self.staff = f.UserFactory(is_staff=True)
        self.msg = f.ChatMessageFactory(chat=self.chat, sender=self.member)


# ─────────────────────────────────────────────────────────────────────────
# 1. PollVoteViewSet
# ─────────────────────────────────────────────────────────────────────────

class TestPollVoteViewSetScoping(SecurityFixtureMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.member.pk,
            question="Pick one", options=["Red", "Blue"],
        )
        self.member_vote = services.vote_on_poll(
            message_id=str(self.poll.id), user_id=self.member.pk, option_id="0"
        )
        # Second, unrelated chat + voter, to prove no platform-wide leak.
        self.other_chat = f.InternalChatFactory()
        self.other_voter = f.UserFactory()
        f.ChatParticipantFactory(chat=self.other_chat, user=self.other_voter)
        self.other_poll = services.create_poll(
            chat_id=str(self.other_chat.id), sender_id=self.other_voter.pk,
            question="Other poll", options=["X", "Y"],
        )
        self.other_vote = services.vote_on_poll(
            message_id=str(self.other_poll.id), user_id=self.other_voter.pk, option_id="0"
        )

    def test_bare_list_does_not_dump_every_vote_platform_wide(self):
        """This is the core bug: GET /poll-votes/ with no params used to
        return literally every vote from every user."""
        r = _api(self.member).get("/messaging/poll-votes/")
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data["results"]} if "results" in r.data else {row["id"] for row in r.data}
        self.assertIn(str(self.member_vote.id), ids)
        self.assertNotIn(str(self.other_vote.id), ids)

    def test_user_id_param_cannot_pull_another_users_voting_history(self):
        r = _api(self.outsider).get(f"/messaging/poll-votes/?user_id={self.other_voter.pk}")
        self.assertEqual(r.status_code, 200)
        rows = r.data["results"] if "results" in r.data else r.data
        self.assertEqual(len(rows), 0)

    def test_user_can_still_see_own_votes_via_user_id_param(self):
        r = _api(self.member).get(f"/messaging/poll-votes/?user_id={self.member.pk}")
        self.assertEqual(r.status_code, 200)
        rows = r.data["results"] if "results" in r.data else r.data
        ids = {row["id"] for row in rows}
        self.assertIn(str(self.member_vote.id), ids)

    def test_message_id_param_blocked_for_non_participant(self):
        r = _api(self.outsider).get(f"/messaging/poll-votes/?message_id={self.other_poll.id}")
        self.assertEqual(r.status_code, 200)
        rows = r.data["results"] if "results" in r.data else r.data
        self.assertEqual(len(rows), 0)

    def test_message_id_param_works_for_real_participant(self):
        r = _api(self.other_voter).get(f"/messaging/poll-votes/?message_id={self.other_poll.id}")
        self.assertEqual(r.status_code, 200)
        rows = r.data["results"] if "results" in r.data else r.data
        ids = {row["id"] for row in rows}
        self.assertIn(str(self.other_vote.id), ids)

    def test_staff_sees_everything(self):
        r = _api(self.staff).get("/messaging/poll-votes/")
        self.assertEqual(r.status_code, 200)
        rows = r.data["results"] if "results" in r.data else r.data
        ids = {row["id"] for row in rows}
        self.assertIn(str(self.member_vote.id), ids)
        self.assertIn(str(self.other_vote.id), ids)

    def test_cannot_update_another_users_vote(self):
        r = _api(self.outsider).patch(
            f"/messaging/poll-votes/{self.other_vote.id}/", {"option_id": "1"}, format="json"
        )
        self.assertIn(r.status_code, (403, 404))
        self.other_vote.refresh_from_db()
        self.assertEqual(self.other_vote.option_id, "0")

    def test_owner_can_still_update_own_vote(self):
        r = _api(self.member).patch(
            f"/messaging/poll-votes/{self.member_vote.id}/", {"option_id": "1"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.member_vote.refresh_from_db()
        self.assertEqual(self.member_vote.option_id, "1")


# ─────────────────────────────────────────────────────────────────────────
# 2-4. forward_message / translate_message / vote_on_poll
# ─────────────────────────────────────────────────────────────────────────

class TestServiceLayerChatMembershipChecks(SecurityFixtureMixin, TestCase):

    def test_forward_message_blocked_for_non_participant_of_source_chat(self):
        target_chat = f.InternalChatFactory()
        f.ChatParticipantFactory(chat=target_chat, user=self.outsider)
        with self.assertRaises(ChatAccessDeniedError):
            services.forward_message(
                message_id=str(self.msg.id),
                target_chat_id=str(target_chat.id),
                forwarded_by_id=self.outsider.pk,
            )

    def test_forward_message_works_for_real_participant(self):
        target_chat = f.InternalChatFactory()
        f.ChatParticipantFactory(chat=target_chat, user=self.member)
        forwarded = services.forward_message(
            message_id=str(self.msg.id),
            target_chat_id=str(target_chat.id),
            forwarded_by_id=self.member.pk,
        )
        self.assertEqual(forwarded.content, self.msg.content)

    def test_translate_message_blocked_for_non_participant(self):
        with self.assertRaises(ChatAccessDeniedError):
            services.translate_message(
                message_id=str(self.msg.id), target_language="es", user_id=self.outsider.pk
            )

    def test_translate_message_works_for_real_participant(self):
        translated = services.translate_message(
            message_id=str(self.msg.id), target_language="es", user_id=self.member.pk
        )
        self.assertIsInstance(translated, str)

    def test_vote_on_poll_blocked_for_non_participant(self):
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.member.pk,
            question="Q", options=["A", "B"],
        )
        with self.assertRaises(ChatAccessDeniedError):
            services.vote_on_poll(message_id=str(poll.id), user_id=self.outsider.pk, option_id="0")
        self.assertEqual(PollVote.objects.filter(message=poll, user=self.outsider).count(), 0)

    def test_vote_on_poll_works_for_real_participant(self):
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.member.pk,
            question="Q", options=["A", "B"],
        )
        vote = services.vote_on_poll(message_id=str(poll.id), user_id=self.member.pk, option_id="0")
        self.assertEqual(vote.option_id, "0")


# ─────────────────────────────────────────────────────────────────────────
# 5. get_message_reactions / get_poll_results
# ─────────────────────────────────────────────────────────────────────────

class TestReactionAndPollResultsAuthorization(SecurityFixtureMixin, TestCase):

    def test_get_message_reactions_blocked_for_non_participant(self):
        with self.assertRaises(ChatAccessDeniedError):
            services.get_message_reactions(str(self.msg.id), self.outsider.pk)

    def test_get_message_reactions_works_for_participant(self):
        services.add_reaction(message_id=str(self.msg.id), user_id=self.member.pk, emoji="👍")
        counts = services.get_message_reactions(str(self.msg.id), self.member.pk)
        self.assertEqual(counts.get("👍"), 1)

    def test_reactions_for_message_endpoint_blocks_outsider(self):
        r = _api(self.outsider).get(f"/messaging/reactions/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 403)

    def test_reactions_for_message_endpoint_allows_participant(self):
        r = _api(self.member).get(f"/messaging/reactions/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)

    def test_get_poll_results_blocked_for_non_participant(self):
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.member.pk, question="Q", options=["A", "B"]
        )
        with self.assertRaises(ChatAccessDeniedError):
            services.get_poll_results(str(poll.id), self.outsider.pk)

    def test_poll_vote_results_endpoint_blocks_outsider(self):
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.member.pk, question="Q", options=["A", "B"]
        )
        r = _api(self.outsider).get(f"/messaging/poll-votes/results/?message_id={poll.id}")
        self.assertEqual(r.status_code, 403)

    def test_poll_view_get_endpoint_blocks_outsider(self):
        """views_extra.py's separate PollView.get() - same underlying fix."""
        poll = services.create_poll(
            chat_id=str(self.chat.id), sender_id=self.member.pk, question="Q", options=["A", "B"]
        )
        r = _api(self.outsider).get(f"/messaging/polls/?message_id={poll.id}")
        self.assertEqual(r.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────
# 6. VoiceMessageViewSet.request_transcription
# ─────────────────────────────────────────────────────────────────────────

class TestVoiceTranscriptionRequestAuthorization(SecurityFixtureMixin, TestCase):

    @patch("messaging.tasks.process_voice_message_task.delay")
    def test_non_participant_cannot_trigger_transcription_job(self, mock_delay):
        r = _api(self.outsider).post(
            "/messaging/voice/request_transcription/", {"message_id": str(self.msg.id)}, format="json"
        )
        self.assertEqual(r.status_code, 403)
        mock_delay.assert_not_called()

    @patch("messaging.tasks.process_voice_message_task.delay")
    def test_participant_can_trigger_transcription_job(self, mock_delay):
        r = _api(self.member).post(
            "/messaging/voice/request_transcription/", {"message_id": str(self.msg.id)}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        mock_delay.assert_called_once_with(str(self.msg.id))

    @patch("messaging.tasks.process_voice_message_task.delay")
    def test_unknown_message_id_returns_404_not_500(self, mock_delay):
        r = _api(self.member).post(
            "/messaging/voice/request_transcription/",
            {"message_id": "00000000-0000-0000-0000-000000000000"}, format="json",
        )
        self.assertEqual(r.status_code, 404)
        mock_delay.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# 7. LinkPreviewViewSet
# ─────────────────────────────────────────────────────────────────────────

class TestLinkPreviewAuthorizationAndThrottle(SecurityFixtureMixin, TestCase):

    def test_non_participant_cannot_list_link_previews_for_message(self):
        r = _api(self.outsider).get(f"/messaging/link-previews/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 403)

    def test_participant_can_list_link_previews_for_message(self):
        r = _api(self.member).get(f"/messaging/link-previews/for_message/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)

    def test_fetch_action_is_throttled(self):
        """fetch() must use the dedicated throttle, not the default."""
        from ..viewsets import LinkPreviewViewSet
        vs = LinkPreviewViewSet()
        vs.action = "fetch"
        throttles = vs.get_throttles()
        self.assertEqual(len(throttles), 1)
        self.assertIsInstance(throttles[0], LinkPreviewFetchThrottle)

    def test_for_message_action_is_not_throttled_by_fetch_limit(self):
        """Reads shouldn't inherit fetch()'s tighter throttle - avoids
        false-positive rate limiting when a chat view loads many
        messages' previews at once."""
        from ..viewsets import LinkPreviewViewSet
        vs = LinkPreviewViewSet()
        vs.action = "for_message"
        throttles = vs.get_throttles()
        self.assertFalse(any(isinstance(t, LinkPreviewFetchThrottle) for t in throttles))


# ─────────────────────────────────────────────────────────────────────────
# 8. MessageSearchView / search_messages chat_id bypass (critical)
# ─────────────────────────────────────────────────────────────────────────

class TestSearchEndpointCannotBypassChatMembership(SecurityFixtureMixin, TestCase):
    """
    SECURITY (critical): search_messages()'s ES path only restricted
    results to the requester's own chats when NO chat_id was given -
    passing an explicit ?chat_id=<any chat> bypassed that restriction
    completely, letting any authenticated user full-text search the
    message content of any chat on the platform. This harness has no
    ELASTICSEARCH_URL configured, so these hit _db_search_fallback(),
    which (unlike the ES path, before this fix) already applied
    chat_id__in=<user's chats> unconditionally - this class proves the
    end-to-end HTTP behavior is correct via that path, while the
    dedicated search_engine tests prove the ES path's query-building
    directly.
    """

    def test_cannot_search_a_chat_via_explicit_chat_id_without_being_a_member(self):
        secret_chat = f.InternalChatFactory()
        someone_else = f.UserFactory()
        f.ChatParticipantFactory(chat=secret_chat, user=someone_else)
        f.ChatMessageFactory(chat=secret_chat, sender=someone_else, content="topsecretplan")

        r = _api(self.outsider).get(f"/messaging/search/?q=topsecretplan&chat_id={secret_chat.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data.get("total", 0), 0)
        self.assertEqual(r.data.get("results", []), [])

    def test_can_still_search_a_chat_youre_actually_in(self):
        f.ChatMessageFactory(chat=self.chat, sender=self.member, content="findablecontent")
        r = _api(self.member).get(f"/messaging/search/?q=findablecontent&chat_id={self.chat.id}")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data.get("total", 0), 1)


# ─────────────────────────────────────────────────────────────────────────
# 9. ScheduledSendNowView ownership check
# ─────────────────────────────────────────────────────────────────────────

class TestScheduledSendNowOwnership(SecurityFixtureMixin, TestCase):

    def _make_scheduled(self, sender):
        from ..models import ScheduledMessage
        from django.utils import timezone
        from datetime import timedelta
        return ScheduledMessage.objects.create(
            chat=self.chat, sender=sender, content="future announcement",
            scheduled_for=timezone.now() + timedelta(hours=6),
        )

    def test_non_owner_cannot_force_early_send(self):
        sched = self._make_scheduled(self.member)
        r = _api(self.outsider).post(f"/messaging/scheduled/{sched.id}/send-now/")
        self.assertEqual(r.status_code, 403)
        sched.refresh_from_db()
        self.assertEqual(sched.status, "PENDING")

    def test_owner_can_force_early_send(self):
        sched = self._make_scheduled(self.member)
        r = _api(self.member).post(f"/messaging/scheduled/{sched.id}/send-now/")
        self.assertEqual(r.status_code, 200)
        sched.refresh_from_db()
        self.assertEqual(sched.status, "SENT")

    def test_staff_can_force_early_send_for_anyone(self):
        sched = self._make_scheduled(self.member)
        r = _api(self.staff).post(f"/messaging/scheduled/{sched.id}/send-now/")
        self.assertEqual(r.status_code, 200)
