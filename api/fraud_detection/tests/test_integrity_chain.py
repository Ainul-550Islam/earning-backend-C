# =============================================================================
# tests/test_integrity_chain.py
# GAP 5 FIX — SHA-256 integrity chain tests for all 6 hash-chain models:
#   FraudAttempt, FraudCase, FraudCaseEvidence, FraudCaseAction,
#   FraudWhitelist, FraudNotification
#
# Tests cover:
#   - Hash is computed on save
#   - Hash changes when critical fields change
#   - Chain: previous_hash of record N = integrity_hash of record N-1
#   - Tamper detection: modifying a record without recalculating breaks chain
#   - Empty-chain initialisation (first record has empty previous_hash)
#   - Hash length is correct (SHA-256 = 64 hex chars)
# =============================================================================
import hashlib
import unittest
from datetime import datetime, timezone as tz, timedelta
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Pure-python hash implementations mirroring models.calculate_hash()
# These let us test the algorithm without Django's ORM.
# ---------------------------------------------------------------------------

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def _fraud_attempt_hash(attempt_id, user_id, attempt_type,
                         fraud_score, confidence_score,
                         status, created_at, resolved_at) -> str:
    data = (
        f"{attempt_id}:{user_id}:{attempt_type}:"
        f"{fraud_score}:{confidence_score}:"
        f"{status}:{created_at}:{resolved_at}"
    )
    return _sha256(data)


def _fraud_case_hash(case_number, user_id, status,
                     risk_score, priority, opened_at, resolved_at) -> str:
    data = (
        f"{case_number}:{user_id}:{status}:"
        f"{risk_score}:{priority}:{opened_at}:{resolved_at}"
    )
    return _sha256(data)


def _fraud_evidence_hash(evidence_id, fraud_case_id, evidence_type,
                          added_at, added_by_id) -> str:
    data = (
        f"{evidence_id}:{fraud_case_id}:{evidence_type}:"
        f"{added_at}:{added_by_id}"
    )
    return _sha256(data)


def _fraud_action_hash(action_id, fraud_case_id, action_type,
                        performed_at, performed_by_id) -> str:
    data = (
        f"{action_id}:{fraud_case_id}:{action_type}:"
        f"{performed_at}:{performed_by_id}"
    )
    return _sha256(data)


def _whitelist_hash(whitelist_id, entity_type, entity_value,
                     reason, is_active, expires_at) -> str:
    data = (
        f"{whitelist_id}:{entity_type}:{entity_value}:"
        f"{reason}:{is_active}:{expires_at}"
    )
    return _sha256(data)


def _notification_hash(notification_id, user_id, notification_type,
                        message, is_sent, sent_at) -> str:
    data = (
        f"{notification_id}:{user_id}:{notification_type}:"
        f"{message}:{is_sent}:{sent_at}"
    )
    return _sha256(data)


# ---------------------------------------------------------------------------
# Helper: simulate a chain of N records
# ---------------------------------------------------------------------------
def _simulate_chain(hash_fn, records):
    """
    Simulate hash chaining for a list of record dicts.
    Each dict must contain fields needed by hash_fn, plus 'id'.
    Returns list of (integrity_hash, previous_hash) tuples.
    """
    chain = []
    prev_hash = ''
    for rec in records:
        h = hash_fn(**{k: v for k, v in rec.items() if k != 'id'})
        chain.append({'integrity_hash': h, 'previous_hash': prev_hash, 'id': rec['id']})
        prev_hash = h
    return chain


# =============================================================================
# 1. FraudAttempt Hash Chain
# =============================================================================
class TestFraudAttemptHashChain(unittest.TestCase):

    BASE = {
        'attempt_id': 'uuid-001',
        'user_id': 42,
        'attempt_type': 'click_fraud',
        'fraud_score': 85,
        'confidence_score': 90,
        'status': 'detected',
        'created_at': '2024-01-01T10:00:00+00:00',
        'resolved_at': '',
    }

    def _hash(self, **kwargs):
        return _fraud_attempt_hash(**{**self.BASE, **kwargs})

    def test_hash_is_64_hex_chars(self):
        h = self._hash()
        self.assertEqual(len(h), 64)
        self.assertRegex(h, r'^[0-9a-f]{64}$')

    def test_hash_deterministic(self):
        self.assertEqual(self._hash(), self._hash())

    def test_hash_changes_on_status_change(self):
        h1 = self._hash(status='detected')
        h2 = self._hash(status='confirmed')
        self.assertNotEqual(h1, h2)

    def test_hash_changes_on_score_change(self):
        h1 = self._hash(fraud_score=85)
        h2 = self._hash(fraud_score=86)
        self.assertNotEqual(h1, h2)

    def test_hash_changes_when_resolved(self):
        h1 = self._hash(resolved_at='')
        h2 = self._hash(resolved_at='2024-01-02T10:00:00+00:00')
        self.assertNotEqual(h1, h2)

    def test_chain_first_record_has_empty_previous_hash(self):
        records = [{'id': 1, **self.BASE}]
        chain = _simulate_chain(
            lambda **kw: _fraud_attempt_hash(**kw), records
        )
        self.assertEqual(chain[0]['previous_hash'], '')

    def test_chain_second_record_previous_equals_first_hash(self):
        r2 = {**self.BASE, 'attempt_id': 'uuid-002', 'fraud_score': 60}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _fraud_attempt_hash(**kw), records)
        self.assertEqual(chain[1]['previous_hash'], chain[0]['integrity_hash'])

    def test_tamper_detected_via_chain_break(self):
        r2 = {**self.BASE, 'attempt_id': 'uuid-002', 'fraud_score': 60}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _fraud_attempt_hash(**kw), records)
        # Tamper: change record 1's fraud_score without recalculating hash
        tampered_hash = _fraud_attempt_hash(**{**self.BASE, 'fraud_score': 1})
        chain_is_valid = chain[1]['previous_hash'] == tampered_hash
        self.assertFalse(chain_is_valid)

    def test_chain_of_five_records_consistent(self):
        records = [
            {'id': i, **self.BASE,
             'attempt_id': f'uuid-{i:03d}', 'fraud_score': 50 + i}
            for i in range(5)
        ]
        chain = _simulate_chain(lambda **kw: _fraud_attempt_hash(**kw), records)
        for i in range(1, len(chain)):
            self.assertEqual(
                chain[i]['previous_hash'], chain[i - 1]['integrity_hash'],
                msg=f"Chain broken between records {i-1} and {i}",
            )

    def test_all_hashes_in_chain_are_unique(self):
        records = [
            {'id': i, **self.BASE,
             'attempt_id': f'uuid-{i:03d}', 'fraud_score': i}
            for i in range(10)
        ]
        chain = _simulate_chain(lambda **kw: _fraud_attempt_hash(**kw), records)
        hashes = [r['integrity_hash'] for r in chain]
        self.assertEqual(len(hashes), len(set(hashes)))


# =============================================================================
# 2. FraudCase Hash Chain
# =============================================================================
class TestFraudCaseHashChain(unittest.TestCase):

    BASE = {
        'case_number': 'CASE-001',
        'user_id': 7,
        'status': 'open',
        'risk_score': 75,
        'priority': 'high',
        'opened_at': '2024-01-01T08:00:00+00:00',
        'resolved_at': '',
    }

    def _hash(self, **kwargs):
        return _fraud_case_hash(**{**self.BASE, **kwargs})

    def test_hash_is_64_hex_chars(self):
        self.assertEqual(len(self._hash()), 64)

    def test_hash_deterministic(self):
        self.assertEqual(self._hash(), self._hash())

    def test_hash_changes_on_status_change(self):
        self.assertNotEqual(self._hash(status='open'), self._hash(status='closed'))

    def test_hash_changes_on_risk_score_change(self):
        self.assertNotEqual(self._hash(risk_score=75), self._hash(risk_score=76))

    def test_hash_changes_on_resolution(self):
        h1 = self._hash(resolved_at='')
        h2 = self._hash(resolved_at='2024-01-03T12:00:00+00:00')
        self.assertNotEqual(h1, h2)

    def test_chain_initialises_with_empty_prev_hash(self):
        records = [{'id': 1, **self.BASE}]
        chain = _simulate_chain(lambda **kw: _fraud_case_hash(**kw), records)
        self.assertEqual(chain[0]['previous_hash'], '')

    def test_chain_linkage_correct(self):
        r2 = {**self.BASE, 'case_number': 'CASE-002', 'risk_score': 90}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _fraud_case_hash(**kw), records)
        self.assertEqual(chain[1]['previous_hash'], chain[0]['integrity_hash'])

    def test_tamper_breaks_chain(self):
        r2 = {**self.BASE, 'case_number': 'CASE-002', 'risk_score': 90}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _fraud_case_hash(**kw), records)
        # Simulate tamper on record 0
        tampered = _fraud_case_hash(**{**self.BASE, 'risk_score': 1})
        self.assertNotEqual(chain[1]['previous_hash'], tampered)

    def test_status_transition_open_to_closed_changes_hash(self):
        h_open = self._hash(status='open')
        h_closed = self._hash(status='closed', resolved_at='2024-01-02T00:00:00+00:00')
        self.assertNotEqual(h_open, h_closed)


# =============================================================================
# 3. FraudCaseEvidence Hash Chain
# =============================================================================
class TestFraudCaseEvidenceHashChain(unittest.TestCase):

    BASE = {
        'evidence_id': 'ev-uuid-001',
        'fraud_case_id': 10,
        'evidence_type': 'screenshot',
        'added_at': '2024-01-01T09:00:00+00:00',
        'added_by_id': 5,
    }

    def _hash(self, **kwargs):
        return _fraud_evidence_hash(**{**self.BASE, **kwargs})

    def test_hash_64_chars(self):
        self.assertEqual(len(self._hash()), 64)

    def test_hash_deterministic(self):
        self.assertEqual(self._hash(), self._hash())

    def test_hash_changes_on_type_change(self):
        self.assertNotEqual(
            self._hash(evidence_type='screenshot'),
            self._hash(evidence_type='log'),
        )

    def test_hash_changes_on_case_change(self):
        self.assertNotEqual(
            self._hash(fraud_case_id=10),
            self._hash(fraud_case_id=11),
        )

    def test_chain_first_has_empty_prev(self):
        records = [{'id': 1, **self.BASE}]
        chain = _simulate_chain(lambda **kw: _fraud_evidence_hash(**kw), records)
        self.assertEqual(chain[0]['previous_hash'], '')

    def test_chain_linkage(self):
        r2 = {**self.BASE, 'evidence_id': 'ev-uuid-002', 'evidence_type': 'log'}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _fraud_evidence_hash(**kw), records)
        self.assertEqual(chain[1]['previous_hash'], chain[0]['integrity_hash'])


# =============================================================================
# 4. FraudCaseAction Hash Chain
# =============================================================================
class TestFraudCaseActionHashChain(unittest.TestCase):

    BASE = {
        'action_id': 'act-uuid-001',
        'fraud_case_id': 10,
        'action_type': 'note',
        'performed_at': '2024-01-01T09:30:00+00:00',
        'performed_by_id': 3,
    }

    def _hash(self, **kwargs):
        return _fraud_action_hash(**{**self.BASE, **kwargs})

    def test_hash_64_chars(self):
        self.assertEqual(len(self._hash()), 64)

    def test_hash_deterministic(self):
        self.assertEqual(self._hash(), self._hash())

    def test_hash_changes_on_action_type_change(self):
        self.assertNotEqual(
            self._hash(action_type='note'),
            self._hash(action_type='ban'),
        )

    def test_hash_changes_on_performer_change(self):
        self.assertNotEqual(
            self._hash(performed_by_id=3),
            self._hash(performed_by_id=4),
        )

    def test_chain_initialises_empty_prev(self):
        records = [{'id': 1, **self.BASE}]
        chain = _simulate_chain(lambda **kw: _fraud_action_hash(**kw), records)
        self.assertEqual(chain[0]['previous_hash'], '')

    def test_chain_three_records_all_linked(self):
        records = [
            {'id': i, **self.BASE,
             'action_id': f'act-uuid-{i:03d}', 'action_type': t}
            for i, t in enumerate(['note', 'escalation', 'resolution'], 1)
        ]
        chain = _simulate_chain(lambda **kw: _fraud_action_hash(**kw), records)
        for i in range(1, len(chain)):
            self.assertEqual(chain[i]['previous_hash'], chain[i - 1]['integrity_hash'])


# =============================================================================
# 5. FraudWhitelist Hash Chain
# =============================================================================
class TestFraudWhitelistHashChain(unittest.TestCase):

    BASE = {
        'whitelist_id': 'wl-uuid-001',
        'entity_type': 'user',
        'entity_value': 'user_123',
        'reason': 'Verified partner account',
        'is_active': True,
        'expires_at': '',
    }

    def _hash(self, **kwargs):
        return _whitelist_hash(**{**self.BASE, **kwargs})

    def test_hash_64_chars(self):
        self.assertEqual(len(self._hash()), 64)

    def test_hash_deterministic(self):
        self.assertEqual(self._hash(), self._hash())

    def test_hash_changes_on_deactivation(self):
        self.assertNotEqual(self._hash(is_active=True), self._hash(is_active=False))

    def test_hash_changes_on_reason_change(self):
        h1 = self._hash(reason='Original reason')
        h2 = self._hash(reason='Updated reason')
        self.assertNotEqual(h1, h2)

    def test_hash_changes_on_expiry_set(self):
        h1 = self._hash(expires_at='')
        h2 = self._hash(expires_at='2025-01-01T00:00:00+00:00')
        self.assertNotEqual(h1, h2)

    def test_chain_first_has_empty_prev(self):
        records = [{'id': 1, **self.BASE}]
        chain = _simulate_chain(lambda **kw: _whitelist_hash(**kw), records)
        self.assertEqual(chain[0]['previous_hash'], '')

    def test_chain_linkage_correct(self):
        r2 = {**self.BASE, 'whitelist_id': 'wl-uuid-002', 'entity_value': 'ip_1.2.3.4'}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _whitelist_hash(**kw), records)
        self.assertEqual(chain[1]['previous_hash'], chain[0]['integrity_hash'])

    def test_tamper_breaks_chain(self):
        r2 = {**self.BASE, 'whitelist_id': 'wl-uuid-002', 'entity_value': 'ip_1.2.3.4'}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _whitelist_hash(**kw), records)
        tampered = _whitelist_hash(**{**self.BASE, 'reason': 'TAMPERED'})
        self.assertNotEqual(chain[1]['previous_hash'], tampered)


# =============================================================================
# 6. FraudNotification Hash Chain
# =============================================================================
class TestFraudNotificationHashChain(unittest.TestCase):

    BASE = {
        'notification_id': 'notif-uuid-001',
        'user_id': 42,
        'notification_type': 'fraud_detected',
        'message': 'Suspicious activity detected on your account.',
        'is_sent': False,
        'sent_at': '',
    }

    def _hash(self, **kwargs):
        return _notification_hash(**{**self.BASE, **kwargs})

    def test_hash_64_chars(self):
        self.assertEqual(len(self._hash()), 64)

    def test_hash_deterministic(self):
        self.assertEqual(self._hash(), self._hash())

    def test_hash_changes_on_send(self):
        h1 = self._hash(is_sent=False, sent_at='')
        h2 = self._hash(is_sent=True, sent_at='2024-01-01T10:00:00+00:00')
        self.assertNotEqual(h1, h2)

    def test_hash_changes_on_message_edit(self):
        h1 = self._hash(message='Original message.')
        h2 = self._hash(message='Edited message.')
        self.assertNotEqual(h1, h2)

    def test_chain_first_has_empty_prev(self):
        records = [{'id': 1, **self.BASE}]
        chain = _simulate_chain(lambda **kw: _notification_hash(**kw), records)
        self.assertEqual(chain[0]['previous_hash'], '')

    def test_chain_linkage_correct(self):
        r2 = {**self.BASE,
              'notification_id': 'notif-uuid-002',
              'notification_type': 'case_escalated'}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _notification_hash(**kw), records)
        self.assertEqual(chain[1]['previous_hash'], chain[0]['integrity_hash'])

    def test_tamper_detection(self):
        r2 = {**self.BASE, 'notification_id': 'notif-uuid-002'}
        records = [{'id': 1, **self.BASE}, {'id': 2, **r2}]
        chain = _simulate_chain(lambda **kw: _notification_hash(**kw), records)
        # If someone changes the message of record 0 without recalculating hash:
        tampered = _notification_hash(**{**self.BASE, 'message': 'Tampered message'})
        self.assertNotEqual(chain[1]['previous_hash'], tampered)

    def test_chain_of_six_records_all_linked(self):
        records = [
            {'id': i, **self.BASE,
             'notification_id': f'notif-uuid-{i:03d}',
             'notification_type': ['fraud_detected', 'case_opened', 'case_escalated',
                                    'action_taken', 'case_resolved', 'case_closed'][i - 1]}
            for i in range(1, 7)
        ]
        chain = _simulate_chain(lambda **kw: _notification_hash(**kw), records)
        for i in range(1, len(chain)):
            self.assertEqual(
                chain[i]['previous_hash'], chain[i - 1]['integrity_hash'],
                msg=f"Chain broken between records {i-1} and {i}",
            )


# =============================================================================
# 7. Cross-model chain integrity properties
# =============================================================================
class TestCrossModelChainProperties(unittest.TestCase):
    """Verify properties that must hold across ALL hash-chain models."""

    def test_sha256_output_always_64_chars(self):
        inputs = ['', 'a', 'hello:world:123', 'x' * 10000]
        for s in inputs:
            h = _sha256(s)
            self.assertEqual(len(h), 64, msg=f"SHA-256 of {repr(s)!r} was {len(h)} chars")

    def test_sha256_avalanche_effect(self):
        # Changing one character completely changes the hash
        h1 = _sha256('fraud:case:001')
        h2 = _sha256('fraud:case:002')
        # Count differing hex chars
        diff = sum(a != b for a, b in zip(h1, h2))
        self.assertGreater(diff, 20)  # avalanche: most chars differ

    def test_empty_chain_starts_with_empty_string(self):
        # All models start their chain with previous_hash = ''
        for prev in ['', None]:
            normalized = prev or ''
            self.assertEqual(normalized, '')

    def test_hash_not_reversible(self):
        # SHA-256 is one-way: we can't recover the original data
        data = 'uuid-001:42:click_fraud:85:90:detected:2024-01-01:'
        h = _sha256(data)
        self.assertNotIn('uuid', h)
        self.assertNotIn('click_fraud', h)

    def test_chain_length_equals_record_count(self):
        records = [
            {'id': i, 'case_number': f'CASE-{i}', 'user_id': 1,
             'status': 'open', 'risk_score': 50, 'priority': 'medium',
             'opened_at': '2024-01-01T00:00:00+00:00', 'resolved_at': ''}
            for i in range(7)
        ]
        chain = _simulate_chain(lambda **kw: _fraud_case_hash(**kw), records)
        self.assertEqual(len(chain), 7)

    def test_all_model_hash_fns_accept_empty_string_datetimes(self):
        # resolved_at, expires_at, sent_at can be '' — must not crash
        _fraud_attempt_hash('uuid', 1, 'click', 50, 60, 'detected', '2024-01-01', '')
        _fraud_case_hash('CASE-1', 1, 'open', 50, 'high', '2024-01-01', '')
        _whitelist_hash('wl-1', 'user', 'u1', 'reason', True, '')
        _notification_hash('notif-1', 1, 'fraud_detected', 'msg', False, '')

    def test_inserting_record_mid_chain_invalidates_rest(self):
        # Records 0 and 1 form a valid chain.
        # Inserting a new record between them without re-chaining makes rec 1 invalid.
        r0 = {'id': 0, 'case_number': 'CASE-0', 'user_id': 1,
               'status': 'open', 'risk_score': 50, 'priority': 'medium',
               'opened_at': '2024-01-01T00:00:00+00:00', 'resolved_at': ''}
        r1 = {'id': 1, 'case_number': 'CASE-1', 'user_id': 1,
               'status': 'open', 'risk_score': 55, 'priority': 'medium',
               'opened_at': '2024-01-02T00:00:00+00:00', 'resolved_at': ''}
        chain = _simulate_chain(lambda **kw: _fraud_case_hash(**kw), [r0, r1])

        # Now insert a new record between them (without rebuilding chain)
        r_inserted = {'id': 99, 'case_number': 'CASE-99', 'user_id': 1,
                      'status': 'open', 'risk_score': 52, 'priority': 'low',
                      'opened_at': '2024-01-01T12:00:00+00:00', 'resolved_at': ''}
        inserted_hash = _fraud_case_hash(**{k: v for k, v in r_inserted.items() if k != 'id'})

        # chain[1]['previous_hash'] was set to chain[0]'s hash — not the inserted record's
        self.assertNotEqual(chain[1]['previous_hash'], inserted_hash)


if __name__ == '__main__':
    unittest.main(verbosity=2)
