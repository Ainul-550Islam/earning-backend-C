# =============================================================================
# promotions/advertiser/budget_manager.py
# Budget Management — Daily caps, auto-pause, top-up
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class BudgetManager:
    """
    Campaign budget controls:
    - Daily spend caps
    - Auto-pause when budget exhausted
    - Budget top-up
    - Real-time spend tracking
    """

    def get_campaign_budget_status(self, campaign_id: int, advertiser_id: int) -> dict:
        from api.promotions.models import Campaign, PromotionTransaction
        try:
            campaign = Campaign.objects.get(id=campaign_id, advertiser_id=advertiser_id)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found'}

        today_start = timezone.now().replace(hour=0, minute=0, second=0)
        today_spend = PromotionTransaction.objects.filter(
            transaction_type='escrow_release',
            metadata__campaign_id=campaign_id,
            created_at__gte=today_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        total_spend = PromotionTransaction.objects.filter(
            transaction_type='escrow_release',
            metadata__campaign_id=campaign_id,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        remaining = campaign.total_budget - abs(total_spend)
        daily_budget = getattr(campaign, 'daily_budget', None) or campaign.total_budget
        daily_remaining = daily_budget - abs(today_spend)
        utilization = float(abs(total_spend) / campaign.total_budget * 100) if campaign.total_budget > 0 else 0

        return {
            'campaign_id': campaign_id,
            'total_budget': str(campaign.total_budget),
            'total_spent': str(abs(total_spend)),
            'total_remaining': str(max(remaining, Decimal('0'))),
            'daily_budget': str(daily_budget),
            'today_spent': str(abs(today_spend)),
            'today_remaining': str(max(daily_remaining, Decimal('0'))),
            'utilization_pct': round(utilization, 2),
            'is_budget_exhausted': remaining <= Decimal('0'),
            'is_daily_cap_hit': daily_remaining <= Decimal('0'),
        }

    def top_up_campaign_budget(self, campaign_id: int, advertiser_id: int, amount: Decimal) -> dict:
        from api.promotions.models import Campaign
        try:
            campaign = Campaign.objects.get(id=campaign_id, advertiser_id=advertiser_id)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found'}
        if amount < Decimal('10.00'):
            return {'error': 'Minimum top-up is $10.00'}
        old_budget = campaign.total_budget
        campaign.total_budget += amount
        if campaign.status == 'paused':
            campaign.status = 'active'
        campaign.save(update_fields=['total_budget', 'status'])
        return {
            'success': True,
            'campaign_id': campaign_id,
            'old_budget': str(old_budget),
            'added_amount': str(amount),
            'new_budget': str(campaign.total_budget),
            'status': campaign.status,
        }

    def set_daily_cap(self, campaign_id: int, advertiser_id: int, daily_cap: Decimal) -> dict:
        from api.promotions.models import Campaign
        try:
            campaign = Campaign.objects.get(id=campaign_id, advertiser_id=advertiser_id)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found'}
        # Store daily cap in cache (or extend model to have daily_budget field)
        cache.set(f'daily_cap:{campaign_id}', str(daily_cap), timeout=3600 * 24 * 365)
        return {
            'success': True,
            'campaign_id': campaign_id,
            'daily_cap': str(daily_cap),
        }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_budget_status_view(request, campaign_id):
    manager = BudgetManager()
    return Response(manager.get_campaign_budget_status(campaign_id, request.user.id))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def campaign_topup_view(request, campaign_id):
    manager = BudgetManager()
    amount = Decimal(str(request.data.get('amount', '0')))
    result = manager.top_up_campaign_budget(campaign_id, request.user.id, amount)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)
