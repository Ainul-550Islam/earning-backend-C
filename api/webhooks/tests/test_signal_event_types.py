"""Test signal-emitted event types against EventType

Session 9: a systematic search confirmed 7 signal domains (payment, fraud,
kyc, offer, user, wallet, withdrawal - all connected via
signals/connector.py, itself already fixed in an earlier session per its
own header comment) fire real webhook events, most of which were missing
from EventType (the "canonical platform event registry"). 20 confirmed-real,
format-valid ones were added; a handful of 3-segment ones were deliberately
left out (format doesn't match this registry's domain.action convention) -
see FIXES_APPLIED_SESSION9.md for the full evidence trail on each.

This test is the sweep that keeps that claim honest: every event_type
string this session found actually being dispatched by a connected signal
handler is listed here explicitly, so a future change to any signal file
that adds/renames/removes an emitted event type will show up as a
diff against this list rather than silently drifting again.
"""

from django.test import SimpleTestCase

from ..constants import EventType

# (module, [event_type values confirmed via grep against signals/<module>.py,
#  cross-checked against signals/connector.py for real connection])
CONFIRMED_SIGNAL_EVENT_TYPES = {
    'wallet_signals': [
        'wallet.balance.updated',        # 3-segment, not in EventType - see below
        'wallet.transaction.created',    # 3-segment, not in EventType - see below
        'wallet.transaction.failed',     # 3-segment, not in EventType - see below
    ],
    'withdrawal_signals': [
        'withdrawal.approved', 'withdrawal.completed', 'withdrawal.failed',
        'withdrawal.rejected', 'withdrawal.requested',
    ],
    'user_signals': [
        'user.created', 'user.login', 'user.logout',
        'user.profile.updated',          # 3-segment, not in EventType - see below
        'user.status.changed',           # 3-segment, not in EventType - see below
        'user.updated',
    ],
    'offer_signals': [
        'offer.cancelled', 'offer.completed', 'offer.credited',
        'offer.expired', 'offer.updated',
    ],
    'fraud_signals': [
        'fraud.cleared', 'fraud.detected', 'fraud.flagged',
        'fraud.investigation.completed',  # 3-segment, not in EventType - see below
        'fraud.investigation.started',    # 3-segment, not in EventType - see below
    ],
    'kyc_signals': [
        'kyc.document.uploaded',          # 3-segment, not in EventType - see below
        'kyc.rejected',
        'kyc.review.started',             # 3-segment, not in EventType - see below
        'kyc.status.changed',             # 3-segment, not in EventType - see below
        'kyc.submitted', 'kyc.verified',
    ],
    'payment_signals': [
        'payment.cancelled', 'payment.disputed', 'payment.failed',
        'payment.initiated', 'payment.refunded', 'payment.succeeded',
    ],
}

# 3-segment values (two dots) don't match EventType's domain.action
# convention or validate_event_type()'s format regex - deliberately not
# added to EventType this session (see constants.py's comments at each
# omission, and FIXES_APPLIED_SESSION9.md Cluster 6 for the full
# reasoning). Listed here so the sweep test below can assert on the
# *rest* without tripping over these on purpose.
KNOWN_UNRESOLVED_FORMAT_MISMATCH = {
    'wallet.balance.updated', 'wallet.transaction.created', 'wallet.transaction.failed',
    'user.profile.updated', 'user.status.changed',
    'fraud.investigation.completed', 'fraud.investigation.started',
    'kyc.document.uploaded', 'kyc.review.started', 'kyc.status.changed',
}


class SignalEventTypesRegisteredTest(SimpleTestCase):

    def test_every_2_segment_signal_event_type_is_now_in_eventtype(self):
        registered = {c[0] for c in EventType.choices}
        missing = []
        for module, event_types in CONFIRMED_SIGNAL_EVENT_TYPES.items():
            for event_type in event_types:
                if event_type in KNOWN_UNRESOLVED_FORMAT_MISMATCH:
                    continue
                if event_type not in registered:
                    missing.append(f"{event_type} (from signals/{module}.py)")
        self.assertEqual(
            missing, [],
            "these signal-emitted event types are real (confirmed via "
            "signals/connector.py) but missing from EventType",
        )

    def test_known_format_mismatches_are_still_actually_unregistered(self):
        """If one of these ever gets added to EventType (e.g. the 3-segment
        question gets resolved), this test should start failing - a
        prompt to update KNOWN_UNRESOLVED_FORMAT_MISMATCH above, not
        something to silence.
        """
        registered = {c[0] for c in EventType.choices}
        still_missing = KNOWN_UNRESOLVED_FORMAT_MISMATCH - registered
        self.assertEqual(still_missing, KNOWN_UNRESOLVED_FORMAT_MISMATCH)
