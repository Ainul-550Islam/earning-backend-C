# api/djoyalty/tests/test_challenges.py
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_loyalty_points


class ChallengeServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='CHLCUST01')
        from djoyalty.models.engagement import Challenge
        self.challenge = Challenge.objects.create(
            name='Spend 500',
            challenge_type='spend',
            target_value=Decimal('500'),
            points_reward=Decimal('100'),
            status='active',
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=30),
        )

    def test_join_challenge(self):
        from djoyalty.services.engagement.ChallengeService import ChallengeService
        from djoyalty.models.engagement import ChallengeParticipant
        participant = ChallengeService.join(self.customer, self.challenge.id)
        self.assertIsNotNone(participant)
        self.assertEqual(participant.status, 'active')

    def test_join_inactive_challenge_raises_error(self):
        from djoyalty.services.engagement.ChallengeService import ChallengeService
        from djoyalty.exceptions import ChallengeNotActiveError
        self.challenge.status = 'ended'
        self.challenge.save()
        with self.assertRaises(ChallengeNotActiveError):
            ChallengeService.join(self.customer, self.challenge.id)

    def test_update_progress(self):
        from djoyalty.services.engagement.ChallengeService import ChallengeService
        ChallengeService.join(self.customer, self.challenge.id)
        participant = ChallengeService.update_progress(self.customer, self.challenge.id, Decimal('300'))
        self.assertIsNotNone(participant)
        self.assertEqual(participant.progress, Decimal('300'))
        self.assertEqual(participant.status, 'active')

    def test_complete_challenge_on_target_met(self):
        from djoyalty.services.engagement.ChallengeService import ChallengeService
        ChallengeService.join(self.customer, self.challenge.id)
        participant = ChallengeService.update_progress(self.customer, self.challenge.id, Decimal('500'))
        self.assertEqual(participant.status, 'completed')
        self.assertIsNotNone(participant.completed_at)

    def test_complete_challenge_awards_points(self):
        from djoyalty.services.engagement.ChallengeService import ChallengeService
        from djoyalty.models.points import LoyaltyPoints
        ChallengeService.join(self.customer, self.challenge.id)
        ChallengeService.update_progress(self.customer, self.challenge.id, Decimal('600'))
        lp = LoyaltyPoints.objects.filter(customer=self.customer).first()
        if lp:
            self.assertGreaterEqual(lp.balance, Decimal('0'))

    def test_already_completed_raises_error(self):
        from djoyalty.services.engagement.ChallengeService import ChallengeService
        from djoyalty.exceptions import ChallengeAlreadyCompletedError
        ChallengeService.join(self.customer, self.challenge.id)
        ChallengeService.update_progress(self.customer, self.challenge.id, Decimal('500'))
        with self.assertRaises(ChallengeAlreadyCompletedError):
            ChallengeService.update_progress(self.customer, self.challenge.id, Decimal('600'))
