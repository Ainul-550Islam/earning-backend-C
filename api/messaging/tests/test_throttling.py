"""
Tests for messaging/throttling.py

Covers all 8 throttle classes:
  MessageSendThrottle, ReactionThrottle, CallInitiateThrottle,
  BotRequestThrottle, SupportThreadCreateThrottle, StoryCreateThrottle,
  MediaUploadThrottle, SearchThrottle, BroadcastSendThrottle, StrictAnonThrottle

Each test class verifies:
  - scope matches the settings.py key
  - rate string is parseable and matches constants
  - inherits from the correct DRF base
"""
from __future__ import annotations

import unittest
TestCase = unittest.TestCase
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from ..throttling import (
    MessageSendThrottle,
    ReactionThrottle,
    CallInitiateThrottle,
    BotRequestThrottle,
    SupportThreadCreateThrottle,
    StoryCreateThrottle,
    MediaUploadThrottle,
    SearchThrottle,
    BroadcastSendThrottle,
    StrictAnonThrottle,
)
from ..constants import (
    MAX_MESSAGES_PER_MINUTE,
    MAX_REACTIONS_PER_MINUTE,
    MAX_CALLS_PER_HOUR,
    MAX_BOT_REQUESTS_PER_MINUTE,
    MAX_SUPPORT_THREADS_PER_USER,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rate_count(throttle_class: type) -> int:
    """Parse 'N/period' from THROTTLE_RATES and return N."""
    rate_str = throttle_class.THROTTLE_RATES.get(throttle_class.scope, "0/min")
    return int(rate_str.split("/")[0])


def _rate_period(throttle_class: type) -> str:
    """Return 'period' from 'N/period'."""
    rate_str = throttle_class.THROTTLE_RATES.get(throttle_class.scope, "0/min")
    return rate_str.split("/")[1]


# ── MessageSendThrottle ───────────────────────────────────────────────────────

class TestMessageSendThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(MessageSendThrottle, UserRateThrottle))

    def test_scope_is_message_send(self):
        self.assertEqual(MessageSendThrottle.scope, "message_send")

    def test_rate_matches_constant(self):
        self.assertEqual(_rate_count(MessageSendThrottle), MAX_MESSAGES_PER_MINUTE)

    def test_rate_period_is_minute(self):
        self.assertEqual(_rate_period(MessageSendThrottle), "minute")

    def test_scope_key_present_in_throttle_rates(self):
        self.assertIn("message_send", MessageSendThrottle.THROTTLE_RATES)


# ── ReactionThrottle ──────────────────────────────────────────────────────────

class TestReactionThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(ReactionThrottle, UserRateThrottle))

    def test_scope_is_reaction(self):
        self.assertEqual(ReactionThrottle.scope, "reaction")

    def test_rate_matches_constant(self):
        self.assertEqual(_rate_count(ReactionThrottle), MAX_REACTIONS_PER_MINUTE)

    def test_rate_period_is_minute(self):
        self.assertEqual(_rate_period(ReactionThrottle), "minute")

    def test_reaction_limit_higher_than_message_limit(self):
        """Users can react more times per minute than they can send messages."""
        self.assertGreater(MAX_REACTIONS_PER_MINUTE, MAX_MESSAGES_PER_MINUTE)


# ── CallInitiateThrottle ──────────────────────────────────────────────────────

class TestCallInitiateThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(CallInitiateThrottle, UserRateThrottle))

    def test_scope_is_call_initiate(self):
        self.assertEqual(CallInitiateThrottle.scope, "call_initiate")

    def test_rate_matches_constant(self):
        self.assertEqual(_rate_count(CallInitiateThrottle), MAX_CALLS_PER_HOUR)

    def test_rate_period_is_hour(self):
        self.assertEqual(_rate_period(CallInitiateThrottle), "hour")

    def test_call_limit_lower_than_message_limit(self):
        """Calls are initiated far less frequently than messages."""
        self.assertLess(MAX_CALLS_PER_HOUR, MAX_MESSAGES_PER_MINUTE)


# ── BotRequestThrottle ────────────────────────────────────────────────────────

class TestBotRequestThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(BotRequestThrottle, UserRateThrottle))

    def test_scope_is_bot_request(self):
        self.assertEqual(BotRequestThrottle.scope, "bot_request")

    def test_rate_matches_constant(self):
        self.assertEqual(_rate_count(BotRequestThrottle), MAX_BOT_REQUESTS_PER_MINUTE)

    def test_rate_period_is_minute(self):
        self.assertEqual(_rate_period(BotRequestThrottle), "minute")

    def test_bot_limit_higher_than_message_limit(self):
        """Bots process more requests per minute than humans send messages."""
        self.assertGreater(MAX_BOT_REQUESTS_PER_MINUTE, MAX_MESSAGES_PER_MINUTE)


# ── SupportThreadCreateThrottle ───────────────────────────────────────────────

class TestSupportThreadCreateThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(SupportThreadCreateThrottle, UserRateThrottle))

    def test_scope_is_support_thread(self):
        self.assertEqual(SupportThreadCreateThrottle.scope, "support_thread")

    def test_rate_matches_constant(self):
        self.assertEqual(_rate_count(SupportThreadCreateThrottle), MAX_SUPPORT_THREADS_PER_USER)

    def test_rate_period_is_day(self):
        self.assertEqual(_rate_period(SupportThreadCreateThrottle), "day")

    def test_support_thread_limit_very_low(self):
        """Support thread creation should be tightly limited."""
        self.assertLessEqual(MAX_SUPPORT_THREADS_PER_USER, 20)


# ── StoryCreateThrottle ───────────────────────────────────────────────────────

class TestStoryCreateThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(StoryCreateThrottle, UserRateThrottle))

    def test_scope_is_story_create(self):
        self.assertEqual(StoryCreateThrottle.scope, "story_create")

    def test_rate_period_is_hour(self):
        self.assertEqual(_rate_period(StoryCreateThrottle), "hour")

    def test_story_rate_positive(self):
        self.assertGreater(_rate_count(StoryCreateThrottle), 0)


# ── MediaUploadThrottle ───────────────────────────────────────────────────────

class TestMediaUploadThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(MediaUploadThrottle, UserRateThrottle))

    def test_scope_is_media_upload(self):
        self.assertEqual(MediaUploadThrottle.scope, "media_upload")

    def test_rate_period_is_hour(self):
        self.assertEqual(_rate_period(MediaUploadThrottle), "hour")


# ── SearchThrottle ────────────────────────────────────────────────────────────

class TestSearchThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(SearchThrottle, UserRateThrottle))

    def test_scope_is_search(self):
        self.assertEqual(SearchThrottle.scope, "search")

    def test_rate_period_is_minute(self):
        self.assertEqual(_rate_period(SearchThrottle), "minute")

    def test_search_rate_positive(self):
        self.assertGreater(_rate_count(SearchThrottle), 0)


# ── BroadcastSendThrottle ─────────────────────────────────────────────────────

class TestBroadcastSendThrottle(TestCase):

    def test_inherits_user_rate_throttle(self):
        self.assertTrue(issubclass(BroadcastSendThrottle, UserRateThrottle))

    def test_scope_is_broadcast_send(self):
        self.assertEqual(BroadcastSendThrottle.scope, "broadcast_send")

    def test_rate_period_is_minute(self):
        self.assertEqual(_rate_period(BroadcastSendThrottle), "minute")

    def test_broadcast_limit_very_low(self):
        """Broadcast send must be tightly rate-limited to prevent mass-send storms."""
        self.assertLessEqual(_rate_count(BroadcastSendThrottle), 10)


# ── StrictAnonThrottle ────────────────────────────────────────────────────────

class TestStrictAnonThrottle(TestCase):

    def test_inherits_anon_rate_throttle(self):
        self.assertTrue(issubclass(StrictAnonThrottle, AnonRateThrottle))

    def test_scope_is_anon(self):
        self.assertEqual(StrictAnonThrottle.scope, "anon")

    def test_rate_period_is_minute(self):
        self.assertEqual(_rate_period(StrictAnonThrottle), "minute")

    def test_anon_limit_lower_than_authenticated(self):
        """Anonymous users should be throttled more strictly than authenticated."""
        anon_rate = _rate_count(StrictAnonThrottle)
        msg_rate  = _rate_count(MessageSendThrottle)
        self.assertLessEqual(anon_rate, msg_rate)


# ── Cross-class consistency checks ────────────────────────────────────────────

class TestThrottleScopeUniqueness(TestCase):

    def test_all_scopes_are_unique(self):
        """Each throttle class must have a distinct scope string."""
        all_throttles = [
            MessageSendThrottle, ReactionThrottle, CallInitiateThrottle,
            BotRequestThrottle, SupportThreadCreateThrottle, StoryCreateThrottle,
            MediaUploadThrottle, SearchThrottle, BroadcastSendThrottle,
            StrictAnonThrottle,
        ]
        scopes = [t.scope for t in all_throttles]
        self.assertEqual(len(scopes), len(set(scopes)),
                         f"Duplicate scopes found: {scopes}")

    def test_all_throttle_rates_are_parseable(self):
        """Every THROTTLE_RATES entry must be in 'N/period' format."""
        all_throttles = [
            MessageSendThrottle, ReactionThrottle, CallInitiateThrottle,
            BotRequestThrottle, SupportThreadCreateThrottle, StoryCreateThrottle,
            MediaUploadThrottle, SearchThrottle, BroadcastSendThrottle,
            StrictAnonThrottle,
        ]
        for throttle in all_throttles:
            rate = throttle.THROTTLE_RATES.get(throttle.scope, "")
            self.assertRegex(rate, r'^\d+/(second|minute|hour|day)$',
                             f"{throttle.__name__} has invalid rate: '{rate}'")
