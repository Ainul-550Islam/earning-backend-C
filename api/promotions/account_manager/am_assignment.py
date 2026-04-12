# =============================================================================
# promotions/account_manager/am_assignment.py
# Dedicated Account Manager — MaxBounty signature feature
# Auto-assign AM based on publisher volume/tier
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status


class PublisherTier:
    STARTER = 'starter'       # $0 - $99/month
    BRONZE = 'bronze'         # $100 - $499/month
    SILVER = 'silver'         # $500 - $1999/month
    GOLD = 'gold'             # $2000 - $9999/month
    PLATINUM = 'platinum'     # $10000+/month
    ELITE = 'elite'           # Top 1% publishers

    THRESHOLDS = {
        STARTER: Decimal('0'),
        BRONZE: Decimal('100'),
        SILVER: Decimal('500'),
        GOLD: Decimal('2000'),
        PLATINUM: Decimal('10000'),
    }

    @classmethod
    def get_tier(cls, monthly_earnings: Decimal) -> str:
        if monthly_earnings >= cls.THRESHOLDS[cls.PLATINUM]:
            return cls.PLATINUM
        elif monthly_earnings >= cls.THRESHOLDS[cls.GOLD]:
            return cls.GOLD
        elif monthly_earnings >= cls.THRESHOLDS[cls.SILVER]:
            return cls.SILVER
        elif monthly_earnings >= cls.THRESHOLDS[cls.BRONZE]:
            return cls.BRONZE
        return cls.STARTER

    @classmethod
    def get_tier_benefits(cls, tier: str) -> dict:
        benefits = {
            cls.STARTER: {
                'dedicated_am': False,
                'support_response_hrs': 72,
                'payout_schedule': 'net-30',
                'min_payout': Decimal('10.00'),
                'bonus_rate': Decimal('0'),
                'priority_support': False,
            },
            cls.BRONZE: {
                'dedicated_am': False,
                'support_response_hrs': 48,
                'payout_schedule': 'net-15',
                'min_payout': Decimal('10.00'),
                'bonus_rate': Decimal('0.02'),
                'priority_support': False,
            },
            cls.SILVER: {
                'dedicated_am': True,
                'support_response_hrs': 24,
                'payout_schedule': 'weekly',
                'min_payout': Decimal('10.00'),
                'bonus_rate': Decimal('0.05'),
                'priority_support': True,
            },
            cls.GOLD: {
                'dedicated_am': True,
                'support_response_hrs': 12,
                'payout_schedule': 'weekly',
                'min_payout': Decimal('10.00'),
                'bonus_rate': Decimal('0.10'),
                'priority_support': True,
                'custom_deals': True,
            },
            cls.PLATINUM: {
                'dedicated_am': True,
                'support_response_hrs': 4,
                'payout_schedule': 'daily',
                'min_payout': Decimal('10.00'),
                'bonus_rate': Decimal('0.15'),
                'priority_support': True,
                'custom_deals': True,
                'exclusive_offers': True,
            },
        }
        return benefits.get(tier, benefits[cls.STARTER])


class AccountManagerAssignment:
    """
    Auto-assign dedicated AMs to publishers based on tier.
    """
    AM_KEY = 'am_assignment:'

    def get_publisher_tier_info(self, user_id: int) -> dict:
        """Get publisher's current tier and AM assignment."""
        from api.promotions.models import PromotionTransaction
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        monthly_earnings = PromotionTransaction.objects.filter(
            user_id=user_id,
            transaction_type='reward',
            created_at__gte=month_start,
        ).aggregate(t=__import__('django.db.models', fromlist=['Sum']).Sum('amount'))['t'] or Decimal('0')

        tier = PublisherTier.get_tier(monthly_earnings)
        benefits = PublisherTier.get_tier_benefits(tier)
        am_info = self._get_assigned_am(user_id)

        return {
            'user_id': user_id,
            'tier': tier,
            'monthly_earnings': str(monthly_earnings),
            'next_tier': self._get_next_tier(tier),
            'amount_to_next_tier': str(self._amount_to_next_tier(tier, monthly_earnings)),
            'benefits': {k: str(v) if isinstance(v, Decimal) else v for k, v in benefits.items()},
            'account_manager': am_info,
        }

    def assign_am_to_publisher(self, publisher_id: int, am_user_id: int, am_name: str, am_email: str) -> dict:
        """Admin assigns an AM to a publisher."""
        assignment = {
            'am_user_id': am_user_id,
            'am_name': am_name,
            'am_email': am_email,
            'am_calendar_link': f'https://calendly.com/{am_name.lower().replace(" ", "")}',
            'assigned_at': timezone.now().isoformat(),
            'publisher_id': publisher_id,
        }
        cache.set(f'{self.AM_KEY}{publisher_id}', assignment, timeout=3600 * 24 * 365)
        return {'success': True, 'assignment': assignment}

    def _get_assigned_am(self, user_id: int) -> dict:
        am = cache.get(f'{self.AM_KEY}{user_id}')
        if am:
            return {
                'has_dedicated_am': True,
                'name': am.get('am_name'),
                'email': am.get('am_email'),
                'calendar_link': am.get('am_calendar_link'),
                'assigned_since': am.get('assigned_at'),
            }
        return {'has_dedicated_am': False, 'support_email': 'support@yourplatform.com'}

    def _get_next_tier(self, current_tier: str) -> str:
        tiers = [PublisherTier.STARTER, PublisherTier.BRONZE, PublisherTier.SILVER,
                 PublisherTier.GOLD, PublisherTier.PLATINUM]
        try:
            idx = tiers.index(current_tier)
            return tiers[idx + 1] if idx < len(tiers) - 1 else 'max'
        except ValueError:
            return PublisherTier.BRONZE

    def _amount_to_next_tier(self, current_tier: str, current_earnings: Decimal) -> Decimal:
        next_tier = self._get_next_tier(current_tier)
        if next_tier == 'max':
            return Decimal('0')
        threshold = PublisherTier.THRESHOLDS.get(next_tier, Decimal('0'))
        return max(threshold - current_earnings, Decimal('0'))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_tier_view(request):
    am = AccountManagerAssignment()
    return Response(am.get_publisher_tier_info(request.user.id))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def assign_am_view(request, publisher_id):
    am = AccountManagerAssignment()
    result = am.assign_am_to_publisher(
        publisher_id=publisher_id,
        am_user_id=request.data.get('am_user_id'),
        am_name=request.data.get('am_name', ''),
        am_email=request.data.get('am_email', ''),
    )
    return Response(result)
