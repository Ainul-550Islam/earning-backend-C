# api/offer_inventory/affiliate_advanced/budget_control.py
"""Budget Controller — Real-time campaign budget enforcement."""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger(__name__)


class BudgetController:
    """Real-time campaign budget monitoring and enforcement."""

    @staticmethod
    def check_budget(campaign_id: str, cost: Decimal) -> dict:
        """Check if campaign has enough budget. Returns {'allowed': bool}."""
        cache_key = f'campaign_budget:{campaign_id}'
        remaining = cache.get(cache_key)

        if remaining is None:
            try:
                from api.offer_inventory.models import Campaign
                campaign  = Campaign.objects.get(id=campaign_id)
                remaining = float(campaign.remaining_budget)
                cache.set(cache_key, remaining, 60)
            except Campaign.DoesNotExist:
                return {'allowed': False, 'reason': 'campaign_not_found'}

        if float(cost) > remaining:
            return {'allowed': False, 'reason': 'budget_depleted', 'remaining': remaining}
        return {'allowed': True, 'remaining': remaining - float(cost)}

    @staticmethod
    @transaction.atomic
    def deduct(campaign_id: str, amount: Decimal):
        """Deduct from campaign budget atomically."""
        from api.offer_inventory.models import Campaign
        from django.db.models import F
        Campaign.objects.filter(id=campaign_id).update(spent=F('spent') + amount)
        cache.delete(f'campaign_budget:{campaign_id}')

    @staticmethod
    def get_alerts(warning_pct: float = 80.0) -> list:
        """Get campaigns at or above warning budget usage."""
        from api.offer_inventory.models import Campaign
        alerts = []
        for c in Campaign.objects.filter(status='live', budget__gt=0):
            usage = float(c.spent / c.budget * 100) if c.budget else 0
            if usage >= warning_pct:
                alerts.append({
                    'campaign_id': str(c.id),
                    'name'       : c.name,
                    'usage_pct'  : round(usage, 1),
                    'remaining'  : float(c.remaining_budget),
                    'status'     : 'critical' if usage >= 95 else 'warning',
                })
        return sorted(alerts, key=lambda x: x['usage_pct'], reverse=True)

    @staticmethod
    def auto_pause_depleted() -> int:
        """Auto-pause campaigns that have exhausted their budget."""
        from api.offer_inventory.models import Campaign
        depleted = Campaign.objects.filter(
            status='live', budget__gt=0
        )
        paused = 0
        for c in depleted:
            if c.remaining_budget <= 0:
                Campaign.objects.filter(id=c.id).update(status='paused')
                cache.delete(f'campaign_budget:{c.id}')
                logger.info(f'Campaign auto-paused (budget depleted): {c.id}')
                paused += 1
        return paused
