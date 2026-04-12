# api/promotions/services/campaign_service.py
import logging
from decimal import Decimal
from django.core.cache import cache
from django.db import transaction
logger = logging.getLogger('services.campaign')

class CampaignService:
    def create(self, advertiser_id: int, data: dict) -> dict:
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        from api.promotions.governance.trust_score import TrustScoreEngine
        trust = TrustScoreEngine().calculate(advertiser_id)
        if trust < 20:
            return {'error': 'Trust score too low for campaign creation', 'trust_score': trust}
        with transaction.atomic():
            camp = Campaign.objects.create(advertiser_id=advertiser_id, status=CampaignStatus.PENDING, **data)
            cache.delete(f'warm:active_campaigns')
            logger.info(f'Campaign created: {camp.id} by advertiser={advertiser_id}')
            return {'campaign_id': camp.id, 'status': camp.status}

    def approve(self, campaign_id: int, admin_id: int) -> bool:
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        updated = Campaign.objects.filter(pk=campaign_id, status=CampaignStatus.PENDING).update(status=CampaignStatus.ACTIVE)
        if updated:
            cache.delete('warm:active_campaigns')
            logger.info(f'Campaign approved: {campaign_id} by admin={admin_id}')
        return bool(updated)

    def pause(self, campaign_id: int, reason: str = '') -> bool:
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        updated = Campaign.objects.filter(pk=campaign_id).update(status=CampaignStatus.PAUSED, pause_reason=reason)
        cache.delete('warm:active_campaigns')
        return bool(updated)

    def check_budget(self, campaign_id: int) -> dict:
        from api.promotions.models import Campaign
        try:
            c = Campaign.objects.get(pk=campaign_id)
            remaining = float(c.total_budget_usd) - float(c.spent_usd)
            pct       = float(c.spent_usd)/float(max(c.total_budget_usd,1))*100
            return {'remaining_usd': remaining, 'spent_pct': round(pct,2), 'budget_ok': remaining > 0}
        except Exception as e:
            return {'error': str(e)}
