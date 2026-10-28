"""Test utils.get_event_type_display_name()

Had zero test coverage before Session 9. Regression coverage for the "one
owner, one task" fix: this used to maintain its own ~75-entry dict,
independent of and partially inconsistent with EventType (the codebase's
own "canonical platform event registry"). See utils.py's own docstring on
get_event_type_display_name() for the full writeup, and
FIXES_APPLIED_SESSION9.md's Cluster 4/5 for the broader context.
"""

from django.test import SimpleTestCase

from ..utils import get_event_type_display_name
from ..constants import EventType


class GetEventTypeDisplayNameTest(SimpleTestCase):

    def test_returns_the_real_eventtype_label_for_a_canonical_value(self):
        """The single source of truth is EventType.choices now - confirm
        a real EventType member's label comes back unchanged."""
        self.assertEqual(
            get_event_type_display_name(EventType.USER_REGISTERED),
            EventType.USER_REGISTERED.label,
        )

    def test_the_two_values_added_this_session_resolve_correctly(self):
        """USER_CREATED/USER_UPDATED were added to EventType this session
        specifically because they were real (pervasively used in tests,
        and for USER_UPDATED, actually emitted by signals/user_signals.py)
        despite never having been registered. Confirms this function
        picks them up automatically now that they're real EventType
        members, with no separate entry needed here.
        """
        self.assertEqual(get_event_type_display_name('user.created'), 'User Created')
        self.assertEqual(get_event_type_display_name('user.updated'), 'User Updated')

    def test_unrecognized_value_falls_back_to_auto_formatting(self):
        """Values not in EventType at all (the ~38 remaining entries from
        the old dict that weren't concretely confirmed real - see
        FIXES_APPLIED_SESSION9.md - plus any genuinely unknown value)
        still get a reasonable, non-erroring display name, matching this
        function's pre-existing fallback behavior for unmapped values."""
        self.assertEqual(
            get_event_type_display_name('some.made.up.event'),
            'Some Made Up Event',
        )

    def test_every_real_eventtype_member_resolves_without_error(self):
        """Sanity sweep - every single real EventType choice should
        resolve to its own real label, not silently fall through to the
        auto-formatter (which would indicate a lookup bug)."""
        for value, label in EventType.choices:
            self.assertEqual(get_event_type_display_name(value), label)
