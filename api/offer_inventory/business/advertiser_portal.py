# api/offer_inventory/business/advertiser_portal.py
"""
Advertiser Portal.
Self-service portal for direct advertisers to manage campaigns,
view performance, fund accounts, and create offers.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class AdvertiserPortalService:
    """Full advertiser self-service portal."""

    # ── Registration ───────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def register_advertiser(company_name: str, contact_name: str,
                             contact_email: str, website: str = '',
                             agreed_rev_share: Decimal = Decimal('60'),
                             tenant=None) -> object:
        """Register a new direct advertiser."""
        from api.offer_inventory.models import DirectAdvertiser
        adv = DirectAdvertiser.objects.create(
            company_name    =company_name,
            contact_name    =contact_name,
            contact_email   =contact_email,
            website         =website,
            agreed_rev_share=agreed_rev_share,
            tenant          =tenant,
            is_active       =True,
        )
        logger.info(f'Advertiser registered: {company_name} ({contact_email})')
        return adv

    # ── Campaign management ────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def create_campaign(advertiser_id: str, name: str, budget: Decimal,
                         goal: str = 'cpa', daily_cap: Decimal = None,
                         starts_at=None, ends_at=None) -> object:
        """Create a campaign for an advertiser."""
        from api.offer_inventory.models import Campaign, DirectAdvertiser
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
        logger.info(f'Campaign created: {name} | advertiser={advertiser.company_name}')
        return campaign

    @staticmethod
    def get_advertiser_campaigns(advertiser_id: str) -> list:
        from api.offer_inventory.models import Campaign
        return list(Campaign.objects.filter(
            advertiser_id=advertiser_id
        ).order_by('-created_at'))

    # ── Performance dashboard ──────────────────────────────────────

    @staticmethod
    def get_performance(advertiser_id: str, days: int = 30) -> dict:
        """Complete performance report for an advertiser."""
        from api.offer_inventory.models import Campaign, Conversion, Click
        from django.db.models import Count, Sum
        from datetime import timedelta

        since     = timezone.now() - timedelta(days=days)
        campaigns = Campaign.objects.filter(advertiser_id=advertiser_id)
        camp_ids  = campaigns.values_list('id', flat=True)

        offers    = []
        for c in campaigns:
            offers.extend(c.offers.all() if hasattr(c, 'offers') else [])

        offer_ids = [o.id for o in offers]
        clicks    = Click.objects.filter(offer_id__in=offer_ids, created_at__gte=since)
        convs     = Conversion.objects.filter(
            offer_id__in=offer_ids, created_at__gte=since, status__name='approved'
        )
        agg = convs.aggregate(count=Count('id'), revenue=Sum('payout_amount'))

        return {
            'advertiser_id'  : advertiser_id,
            'days'           : days,
            'total_campaigns': campaigns.count(),
            'total_budget'   : float(campaigns.aggregate(t=Sum('budget'))['t'] or 0),
            'total_spent'    : float(campaigns.aggregate(t=Sum('spent'))['t'] or 0),
            'total_clicks'   : clicks.count(),
            'conversions'    : agg['count'] or 0,
            'cvr'            : round((agg['count'] or 0) / max(clicks.count(), 1) * 100, 2),
            'total_cost'     : float(agg['revenue'] or 0),
            'cpa'            : round(float(agg['revenue'] or 0) / max(agg['count'] or 1, 1), 4),
        }

    # ── Billing ────────────────────────────────────────────────────

    @staticmethod
    def generate_invoice(advertiser_id: str, period_days: int = 30,
                          notes: str = '') -> object:
        """Generate invoice for an advertiser's spend."""
        from api.offer_inventory.models import Campaign
        from api.offer_inventory.finance_payment.invoice_generator import InvoiceGenerator
        from django.db.models import Sum

        campaigns = Campaign.objects.filter(advertiser_id=advertiser_id)
        total     = campaigns.aggregate(s=Sum('spent'))['s'] or Decimal('0')

        return InvoiceGenerator.generate(
            advertiser_id=advertiser_id,
            amount       =total,
            notes        =notes or f'Campaign spend for last {period_days} days',
        )

    @staticmethod
    def top_advertisers(days: int = 30, limit: int = 10) -> list:
        """Top advertisers by spend."""
        from api.offer_inventory.models import DirectAdvertiser, Campaign
        from django.db.models import Sum, Count
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        return list(
            DirectAdvertiser.objects.filter(is_active=True)
            .annotate(
                total_spent     =Sum('campaigns__spent'),
                campaign_count  =Count('campaigns'),
            )
            .order_by('-total_spent')[:limit]
            .values('company_name', 'contact_email', 'total_spent', 'campaign_count')
        )
