# api/support/tests/test_logic.py
"""Tests for business logic layer."""
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal


class DeterminePriorityTest(TestCase):
    def test_fraud_is_urgent(self):
        from api.support.logic import determine_ticket_priority
        self.assertEqual(determine_ticket_priority('fraud'), 'urgent')

    def test_payment_is_high(self):
        from api.support.logic import determine_ticket_priority
        self.assertEqual(determine_ticket_priority('payment'), 'high')

    def test_other_is_low(self):
        from api.support.logic import determine_ticket_priority
        self.assertEqual(determine_ticket_priority('other'), 'low')

    def test_large_amount_upgrades_priority(self):
        from api.support.logic import determine_ticket_priority
        priority = determine_ticket_priority('other', amount=Decimal('1500'))
        self.assertEqual(priority, 'urgent')


class SLADueTimeTest(TestCase):
    def test_urgent_sla_1h(self):
        from api.support.logic import calculate_sla_due_times
        fr, res = calculate_sla_due_times('urgent')
        diff_fr  = (fr  - timezone.now()).total_seconds() / 3600
        diff_res = (res - timezone.now()).total_seconds() / 3600
        self.assertAlmostEqual(diff_fr,  1.0, delta=0.1)
        self.assertAlmostEqual(diff_res, 4.0, delta=0.1)

    def test_low_sla_24h(self):
        from api.support.logic import calculate_sla_due_times
        fr, res = calculate_sla_due_times('low')
        diff_fr  = (fr  - timezone.now()).total_seconds() / 3600
        self.assertAlmostEqual(diff_fr, 24.0, delta=0.1)

    def test_resolution_after_first_response(self):
        from api.support.logic import calculate_sla_due_times
        fr, res = calculate_sla_due_times('medium')
        self.assertGreater(res, fr)


class DisputeConfidenceTest(TestCase):
    def test_high_confidence_with_good_signals(self):
        from api.support.logic import calculate_dispute_confidence
        score = calculate_dispute_confidence(
            postback_result={'confidence': 0.95},
            offerwall_result={'found': True, 'status': 'completed'},
            fraud_risk={'score': 10, 'is_flagged': False},
            kyc_verified=True,
            amount=Decimal('50'),
        )
        self.assertGreater(score, 0.85)

    def test_low_confidence_with_fraud(self):
        from api.support.logic import calculate_dispute_confidence
        score = calculate_dispute_confidence(
            postback_result={'confidence': 0.1},
            offerwall_result={'found': False},
            fraud_risk={'score': 90, 'is_flagged': True},
            kyc_verified=False,
            amount=Decimal('500'),
        )
        self.assertLess(score, 0.4)


class CSATTest(TestCase):
    def test_csat_calculation(self):
        from api.support.logic import calculate_csat_score
        r = calculate_csat_score([5, 5, 4, 3, 1, 2, 5])
        self.assertEqual(r['total'], 7)
        self.assertEqual(r['promoters'], 3)
        self.assertEqual(r['detractors'], 2)

    def test_empty_scores(self):
        from api.support.logic import calculate_csat_score
        r = calculate_csat_score([])
        self.assertEqual(r['total'], 0)
        self.assertEqual(r['avg'], 0.0)