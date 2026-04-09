# api/djoyalty/services/engagement/ChallengeService.py
import logging
from decimal import Decimal
from django.utils import timezone
from ...models.engagement import Challenge, ChallengeParticipant
from ...exceptions import ChallengeNotActiveError, ChallengeAlreadyCompletedError

logger = logging.getLogger(__name__)

class ChallengeService:
    @staticmethod
    def join(customer, challenge_id: int, tenant=None):
        challenge = Challenge.objects.get(id=challenge_id)
        if challenge.status != 'active':
            raise ChallengeNotActiveError()
        participant, created = ChallengeParticipant.objects.get_or_create(
            challenge=challenge, customer=customer,
            defaults={'status': 'active'},
        )
        return participant

    @staticmethod
    def update_progress(customer, challenge_id: int, value: Decimal):
        try:
            participant = ChallengeParticipant.objects.get(challenge_id=challenge_id, customer=customer)
            if participant.status == 'completed':
                raise ChallengeAlreadyCompletedError()
            participant.progress = value
            if participant.progress >= participant.challenge.target_value:
                participant.status = 'completed'
                participant.completed_at = timezone.now()
                participant.points_awarded = participant.challenge.points_reward
                if participant.points_reward > 0:
                    from ..earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        customer, participant.challenge.points_reward,
                        reason=f'Challenge completed: {participant.challenge.name}',
                        triggered_by='challenge',
                    )
            participant.save()
            return participant
        except ChallengeParticipant.DoesNotExist:
            return None
