# =============================================================================
# promotions/offer_tools/offer_cloner.py
# Offer Clone + Bulk Updater — advertiser management tools
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class OfferCloner:
    """Clone a campaign with modified settings."""

    def clone_campaign(self, original_campaign_id: int, advertiser_id: int,
                        new_title: str = '', new_payout: Decimal = None,
                        new_budget: Decimal = None) -> dict:
        from api.promotions.models import Campaign
        try:
            original = Campaign.objects.get(id=original_campaign_id, advertiser_id=advertiser_id)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found or not yours'}

        # Clone
        clone = Campaign.objects.create(
            title=new_title or f'[Copy] {original.title}',
            description=original.description,
            advertiser=original.advertiser,
            category=original.category,
            reward_policy=original.reward_policy,
            per_task_reward=new_payout or original.per_task_reward,
            max_tasks_per_user=original.max_tasks_per_user,
            total_budget=new_budget or original.total_budget,
            status='draft',
        )

        logger.info(f'Campaign cloned: {original_campaign_id} → {clone.id} by advertiser {advertiser_id}')
        return {
            'original_id':   original_campaign_id,
            'clone_id':      clone.id,
            'clone_title':   clone.title,
            'status':        'draft',
            'message':       'Campaign cloned successfully. Review and activate when ready.',
        }


class BulkCampaignUpdater:
    """Bulk update multiple campaigns at once."""

    def bulk_pause(self, campaign_ids: list, advertiser_id: int) -> dict:
        from api.promotions.models import Campaign
        updated = Campaign.objects.filter(
            id__in=campaign_ids, advertiser_id=advertiser_id, status='active'
        ).update(status='paused')
        return {'updated': updated, 'action': 'paused', 'campaign_ids': campaign_ids}

    def bulk_resume(self, campaign_ids: list, advertiser_id: int) -> dict:
        from api.promotions.models import Campaign
        updated = Campaign.objects.filter(
            id__in=campaign_ids, advertiser_id=advertiser_id, status='paused'
        ).update(status='active')
        return {'updated': updated, 'action': 'resumed', 'campaign_ids': campaign_ids}

    def bulk_update_payout(self, campaign_ids: list, advertiser_id: int,
                            new_payout: Decimal) -> dict:
        from api.promotions.models import Campaign
        updated = Campaign.objects.filter(
            id__in=campaign_ids, advertiser_id=advertiser_id
        ).update(per_task_reward=new_payout)
        return {'updated': updated, 'new_payout': str(new_payout), 'campaign_ids': campaign_ids}

    def bulk_update_budget(self, campaign_ids: list, advertiser_id: int,
                            add_budget: Decimal) -> dict:
        from api.promotions.models import Campaign
        from django.db.models import F
        updated = Campaign.objects.filter(
            id__in=campaign_ids, advertiser_id=advertiser_id
        ).update(total_budget=F('total_budget') + add_budget)
        return {'updated': updated, 'added_budget': str(add_budget), 'campaign_ids': campaign_ids}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clone_campaign_view(request, campaign_id):
    cloner = OfferCloner()
    result = cloner.clone_campaign(
        original_campaign_id=campaign_id,
        advertiser_id=request.user.id,
        new_title=request.data.get('new_title', ''),
        new_payout=Decimal(str(request.data['new_payout'])) if 'new_payout' in request.data else None,
        new_budget=Decimal(str(request.data['new_budget'])) if 'new_budget' in request.data else None,
    )
    if 'error' in result:
        return Response(result, status=status.HTTP_404_NOT_FOUND)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_view(request):
    updater = BulkCampaignUpdater()
    action = request.data.get('action', '')
    campaign_ids = request.data.get('campaign_ids', [])
    if action == 'pause':
        result = updater.bulk_pause(campaign_ids, request.user.id)
    elif action == 'resume':
        result = updater.bulk_resume(campaign_ids, request.user.id)
    elif action == 'update_payout':
        result = updater.bulk_update_payout(campaign_ids, request.user.id,
                                             Decimal(str(request.data.get('new_payout', '0'))))
    elif action == 'add_budget':
        result = updater.bulk_update_budget(campaign_ids, request.user.id,
                                            Decimal(str(request.data.get('add_budget', '0'))))
    else:
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)
