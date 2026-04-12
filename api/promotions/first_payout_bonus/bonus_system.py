# =============================================================================
# promotions/first_payout_bonus/bonus_system.py
# 🟡 MEDIUM — First Payout Bonus System
# MaxBounty: "20% bonus on first payout" — publishers love this
# Zeydoo: Special welcome bonus for new publishers
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

FIRST_PAYOUT_BONUS_RATE = Decimal('0.20')   # 20% like MaxBounty
WELCOME_BONUS_FIXED = Decimal('2.00')        # $2 signup bonus like CPAlead


class FirstPayoutBonus:
    """Award 20% bonus on publisher's first payout."""
    BONUS_KEY = 'first_payout_bonus:'
    CLAIMED_KEY = 'first_payout_claimed:'

    def award_welcome_bonus(self, user_id: int) -> dict:
        """Award $2 welcome bonus on signup."""
        if cache.get(f'welcome_bonus:{user_id}'):
            return {'already_claimed': True}
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=user_id,
                transaction_type='bonus',
                amount=WELCOME_BONUS_FIXED,
                status='completed',
                notes=f'🎉 Welcome Bonus — Start earning today!',
                metadata={'type': 'welcome_bonus'},
            )
            cache.set(f'welcome_bonus:{user_id}', True, timeout=3600 * 24 * 365)
            return {
                'success': True,
                'bonus_amount': str(WELCOME_BONUS_FIXED),
                'message': f'Welcome! ${WELCOME_BONUS_FIXED} bonus added to your wallet.',
            }
        except Exception as e:
            return {'error': str(e)}

    def check_and_award_first_payout_bonus(self, user_id: int, payout_amount: Decimal) -> dict:
        """Check if this is first payout and award 20% bonus."""
        if cache.get(f'{self.CLAIMED_KEY}{user_id}'):
            return {'bonus_applied': False, 'reason': 'already_claimed'}

        bonus_amount = (payout_amount * FIRST_PAYOUT_BONUS_RATE).quantize(Decimal('0.01'))

        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=user_id,
                transaction_type='bonus',
                amount=bonus_amount,
                status='completed',
                notes=f'🎉 First Payout Bonus — {int(FIRST_PAYOUT_BONUS_RATE * 100)}% of ${payout_amount}',
                metadata={'type': 'first_payout_bonus', 'base_amount': str(payout_amount)},
            )
            cache.set(f'{self.CLAIMED_KEY}{user_id}', True, timeout=3600 * 24 * 365)
            return {
                'bonus_applied': True,
                'base_payout': str(payout_amount),
                'bonus_rate': f'{int(FIRST_PAYOUT_BONUS_RATE * 100)}%',
                'bonus_amount': str(bonus_amount),
                'total': str(payout_amount + bonus_amount),
                'message': f'🎉 First payout bonus: +${bonus_amount}!',
            }
        except Exception as e:
            return {'bonus_applied': False, 'error': str(e)}

    def get_bonus_eligibility(self, user_id: int) -> dict:
        """Check if publisher is eligible for first payout bonus."""
        is_claimed = bool(cache.get(f'{self.CLAIMED_KEY}{user_id}'))
        welcome_claimed = bool(cache.get(f'welcome_bonus:{user_id}'))
        return {
            'first_payout_bonus': {
                'eligible': not is_claimed,
                'rate': f'{int(FIRST_PAYOUT_BONUS_RATE * 100)}%',
                'claimed': is_claimed,
                'description': f'Earn {int(FIRST_PAYOUT_BONUS_RATE * 100)}% extra on your first payout!',
            },
            'welcome_bonus': {
                'eligible': not welcome_claimed,
                'amount': str(WELCOME_BONUS_FIXED),
                'claimed': welcome_claimed,
                'description': f'${WELCOME_BONUS_FIXED} welcome bonus for new publishers',
            },
        }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bonus_eligibility_view(request):
    bonus = FirstPayoutBonus()
    return Response(bonus.get_bonus_eligibility(request.user.id))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_welcome_bonus_view(request):
    bonus = FirstPayoutBonus()
    return Response(bonus.award_welcome_bonus(request.user.id))
