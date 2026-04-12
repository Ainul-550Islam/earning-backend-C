# =============================================================================
# promotions/offer_review/content_moderator.py
# Campaign Content Moderation — Auto + Manual review queue
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

AUTO_REJECT_KEYWORDS = [
    'scam', 'guaranteed money', 'get rich quick', 'pyramid', 'mlm scheme',
    'illegal', 'xxx', 'adult content', 'drugs', 'weapons', 'hack',
]

AUTO_APPROVE_CATEGORIES = ['apps', 'surveys', 'social']
MANUAL_REVIEW_CATEGORIES = ['dating', 'finance', 'health_nutra', 'sweepstakes']


class ContentModerator:
    """Auto + Manual campaign review workflow."""

    def review_campaign(self, campaign_id: int, admin_id: int = None) -> dict:
        from api.promotions.models import Campaign
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found'}

        # Auto-reject check
        auto_reject = self._check_auto_reject(campaign)
        if auto_reject:
            campaign.status = 'cancelled'
            campaign.save(update_fields=['status'])
            return {'decision': 'auto_rejected', 'reason': auto_reject, 'campaign_id': campaign_id}

        # Auto-approve check
        category_name = campaign.category.name if campaign.category else ''
        if category_name in AUTO_APPROVE_CATEGORIES:
            campaign.status = 'active'
            campaign.save(update_fields=['status'])
            logger.info(f'Campaign {campaign_id} auto-approved [{category_name}]')
            return {'decision': 'auto_approved', 'campaign_id': campaign_id}

        # Manual review queue
        return {
            'decision': 'pending_manual_review',
            'campaign_id': campaign_id,
            'category': category_name,
            'estimated_review_time': '2-4 hours',
            'reason': f'{category_name} category requires manual review',
        }

    def approve_campaign(self, campaign_id: int, admin_id: int, notes: str = '') -> dict:
        from api.promotions.models import Campaign
        updated = Campaign.objects.filter(id=campaign_id, status='pending').update(status='active')
        if updated:
            logger.info(f'Campaign {campaign_id} approved by admin {admin_id}')
            return {'approved': True, 'campaign_id': campaign_id, 'status': 'active'}
        return {'error': 'Campaign not found or not pending'}

    def reject_campaign(self, campaign_id: int, admin_id: int, reason: str) -> dict:
        from api.promotions.models import Campaign
        updated = Campaign.objects.filter(id=campaign_id, status='pending').update(status='cancelled')
        if updated:
            return {'rejected': True, 'campaign_id': campaign_id, 'reason': reason}
        return {'error': 'Campaign not found or not pending'}

    def get_review_queue(self) -> list:
        from api.promotions.models import Campaign
        pending = Campaign.objects.filter(status='pending').select_related('advertiser', 'category').order_by('created_at')
        return [
            {
                'campaign_id': c.id, 'title': c.title,
                'advertiser': c.advertiser.username,
                'category': c.category.name if c.category else '',
                'payout': str(c.per_task_reward), 'budget': str(c.total_budget),
                'submitted': c.created_at.isoformat(),
                'priority': 'high' if c.total_budget > Decimal('1000') else 'normal',
            }
            for c in pending
        ]

    def _check_auto_reject(self, campaign) -> str:
        text = f"{campaign.title} {campaign.description or ''}".lower()
        for kw in AUTO_REJECT_KEYWORDS:
            if kw in text:
                return f'Contains prohibited keyword: "{kw}"'
        if campaign.per_task_reward < Decimal('0.01'):
            return 'Payout too low (minimum $0.01)'
        if campaign.total_budget < Decimal('10'):
            return 'Budget too low (minimum $10)'
        return None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def review_queue_view(request):
    mod = ContentModerator()
    return Response({'queue': mod.get_review_queue()})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def approve_campaign_view(request, campaign_id):
    mod = ContentModerator()
    result = mod.approve_campaign(campaign_id, request.user.id, request.data.get('notes', ''))
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reject_campaign_view(request, campaign_id):
    mod = ContentModerator()
    result = mod.reject_campaign(campaign_id, request.user.id, request.data.get('reason', ''))
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auto_review_campaign_view(request, campaign_id):
    mod = ContentModerator()
    return Response(mod.review_campaign(campaign_id))
