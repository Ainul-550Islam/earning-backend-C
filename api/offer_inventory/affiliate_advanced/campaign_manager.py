# api/offer_inventory/affiliate_advanced/campaign_manager.py
"""Advanced Campaign Manager — Full campaign lifecycle with budget pacing."""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class AdvancedCampaignManager:
    """Campaign creation, activation, pacing, and performance tracking."""

    @staticmethod
    @transaction.atomic
    def create_with_offers(advertiser_id: str, name: str,
                            budget: Decimal, goal: str,
                            offer_configs: list,
                            daily_cap: Decimal = None,
                            starts_at=None,
                            ends_at=None) -> dict:
        """Create a campaign with associated offers in one call."""
        from api.offer_inventory.models import Campaign, Offer, DirectAdvertiser

        advertiser = DirectAdvertiser.objects.get(id=advertiser_id)
        campaign   = Campaign.objects.create(
            advertiser=advertiser,
            name      =name,
            budget    =budget,
            goal      =goal,
            daily_cap =daily_cap,
            starts_at =starts_at,
            ends_at   =ends_at,
            status    ='draft',
        )
        created_offers = []
        for cfg in offer_configs:
            offer = Offer.objects.create(
                title        =cfg.get('title', name),
                description  =cfg.get('description', ''),
                offer_url    =cfg.get('url', ''),
                payout_amount=Decimal(str(cfg.get('payout', 0))),
                reward_amount=Decimal(str(cfg.get('payout', 0))) * Decimal('0.7'),
                status       ='draft',
                tenant       =advertiser.tenant,
            )
            created_offers.append(offer)

        logger.info(f'Campaign created: {name} with {len(created_offers)} offers')
        return {'campaign_id': str(campaign.id), 'offers_created': len(created_offers)}

    @staticmethod
    def activate(campaign_id: str) -> bool:
        """Activate a draft campaign and its offers."""
        from api.offer_inventory.models import Campaign, Offer
        Campaign.objects.filter(id=campaign_id).update(status='live')
        campaign = Campaign.objects.get(id=campaign_id)
        Offer.objects.filter(status='draft').update(status='active')
        logger.info(f'Campaign activated: {campaign_id}')
        return True

    @staticmethod
    def get_pacing_report(campaign_id: str) -> dict:
        """Budget pacing analysis for a live campaign."""
        from api.offer_inventory.models import Campaign
        from datetime import timedelta

        try:
            c = Campaign.objects.get(id=campaign_id, status='live')
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found or not live'}

        now           = timezone.now()
        days_elapsed  = max(1, (now - (c.starts_at or now - timedelta(days=1))).days)
        total_days    = max(1, (c.ends_at - c.starts_at).days if c.ends_at and c.starts_at else 30)
        days_remaining = max(1, total_days - days_elapsed)
        daily_rec     = c.remaining_budget / days_remaining

        if c.daily_cap and daily_rec > c.daily_cap:
            status = 'underspending'
        elif c.daily_cap and daily_rec < c.daily_cap * Decimal('0.5'):
            status = 'overspending'
        else:
            status = 'on_track'

        return {
            'campaign_id'      : campaign_id,
            'budget'           : float(c.budget),
            'spent'            : float(c.spent),
            'remaining'        : float(c.remaining_budget),
            'days_remaining'   : days_remaining,
            'recommended_daily': float(daily_rec),
            'pacing_status'    : status,
        }

    @staticmethod
    def pause(campaign_id: str, reason: str = '') -> bool:
        """Pause a live campaign."""
        from api.offer_inventory.models import Campaign
        Campaign.objects.filter(id=campaign_id).update(status='paused')
        logger.info(f'Campaign paused: {campaign_id} reason={reason}')
        return True
