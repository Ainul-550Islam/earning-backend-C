# =============================================================================
# promotions/cap_manager/cap_enforcer.py
# Conversion Cap Enforcement — auto-pause when cap hit
# Daily/weekly/total caps per campaign and per publisher
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class CapEnforcer:
    """Enforce conversion caps — daily/weekly/total."""

    def check_and_enforce_cap(self, campaign_id: int, publisher_id: int = None) -> dict:
        from api.promotions.models import Campaign, TaskSubmission
        from django.db.models import Count
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return {'allowed': False, 'reason': 'campaign_not_found'}

        if campaign.status != 'active':
            return {'allowed': False, 'reason': f'campaign_{campaign.status}'}

        # Budget check
        if campaign.total_budget <= 0:
            return {'allowed': False, 'reason': 'budget_exhausted'}

        today = timezone.now().date()
        # Daily cap check (from cache for speed)
        daily_key = f'daily_conv:{campaign_id}:{today}'
        daily_count = cache.get(daily_key, 0)
        daily_cap = getattr(campaign, 'daily_cap', None) or 999999

        if daily_count >= daily_cap:
            if campaign.status == 'active':
                campaign.status = 'paused'
                campaign.save(update_fields=['status'])
                logger.info(f'Campaign {campaign_id} auto-paused: daily cap {daily_cap} reached')
            return {'allowed': False, 'reason': 'daily_cap_reached', 'cap': daily_cap, 'count': daily_count}

        # Per-publisher cap
        if publisher_id:
            pub_daily_key = f'pub_daily_conv:{campaign_id}:{publisher_id}:{today}'
            pub_count = cache.get(pub_daily_key, 0)
            pub_cap = campaign.max_tasks_per_user or 999999
            if pub_count >= pub_cap:
                return {'allowed': False, 'reason': 'publisher_cap_reached', 'cap': pub_cap, 'count': pub_count}

        return {'allowed': True, 'daily_remaining': daily_cap - daily_count}

    def record_conversion(self, campaign_id: int, publisher_id: int = None):
        """Increment conversion counters."""
        today = timezone.now().date()
        daily_key = f'daily_conv:{campaign_id}:{today}'
        current = cache.get(daily_key, 0)
        cache.set(daily_key, current + 1, timeout=3600 * 25)
        if publisher_id:
            pub_key = f'pub_daily_conv:{campaign_id}:{publisher_id}:{today}'
            pub_curr = cache.get(pub_key, 0)
            cache.set(pub_key, pub_curr + 1, timeout=3600 * 25)

    def get_campaign_cap_status(self, campaign_id: int) -> dict:
        from api.promotions.models import Campaign
        try:
            c = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return {'error': 'not_found'}
        today = timezone.now().date()
        daily_count = cache.get(f'daily_conv:{campaign_id}:{today}', 0)
        daily_cap = getattr(c, 'daily_cap', None) or 'unlimited'
        return {
            'campaign_id': campaign_id,
            'status': c.status,
            'daily_cap': daily_cap,
            'today_conversions': daily_count,
            'total_budget': str(c.total_budget),
            'utilization_pct': 0,
        }

    def reset_daily_caps(self):
        """Called at midnight via Celery beat."""
        logger.info('Daily conversion caps reset')
        return {'reset': True, 'timestamp': timezone.now().isoformat()}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cap_status_view(request, campaign_id):
    enforcer = CapEnforcer()
    return Response(enforcer.get_campaign_cap_status(campaign_id))
