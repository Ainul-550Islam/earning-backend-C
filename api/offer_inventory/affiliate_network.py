# api/offer_inventory/affiliate_network.py
"""
Affiliate Network Manager.
Manages multiple CPA/affiliate networks, their APIs,
postback configurations, and performance tracking.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AffiliateNetworkManager:
    """
    Full lifecycle management of affiliate networks.
    """

    @staticmethod
    def register_network(name: str, slug: str, base_url: str,
                          api_key: str = '', api_secret: str = '',
                          postback_url: str = '', revenue_share: Decimal = Decimal('70'),
                          tenant=None) -> object:
        """Register a new affiliate network."""
        from api.offer_inventory.models import OfferNetwork
        network = OfferNetwork.objects.create(
            name            =name,
            slug            =slug,
            base_url        =base_url,
            api_key         =api_key,
            api_secret      =api_secret,
            postback_url    =postback_url,
            revenue_share_pct=revenue_share,
            tenant          =tenant,
            status          ='active',
        )
        logger.info(f'Network registered: {name} ({slug})')
        return network

    @staticmethod
    def get_active_networks(tenant=None) -> list:
        """List all active affiliate networks."""
        from api.offer_inventory.models import OfferNetwork
        qs = OfferNetwork.objects.filter(status='active').order_by('priority')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs)

    @staticmethod
    def get_network_performance(network_id: str, days: int = 30) -> dict:
        """Full performance report for a network."""
        from api.offer_inventory.models import Click, Conversion, NetworkStat
        from django.db.models import Count, Sum, Avg
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)

        clicks  = Click.objects.filter(
            offer__network_id=network_id, created_at__gte=since, is_fraud=False
        ).count()
        fraud   = Click.objects.filter(
            offer__network_id=network_id, created_at__gte=since, is_fraud=True
        ).count()
        conv_agg = Conversion.objects.filter(
            offer__network_id=network_id,
            created_at__gte=since,
            status__name='approved',
        ).aggregate(
            count  =Count('id'),
            revenue=Sum('payout_amount'),
            rewards=Sum('reward_amount'),
        )

        convs   = conv_agg['count']   or 0
        revenue = conv_agg['revenue'] or Decimal('0')
        rewards = conv_agg['rewards'] or Decimal('0')

        return {
            'network_id'    : network_id,
            'days'          : days,
            'total_clicks'  : clicks,
            'fraud_clicks'  : fraud,
            'fraud_rate'    : round(fraud / max(clicks, 1) * 100, 2),
            'conversions'   : convs,
            'cvr'           : round(convs / max(clicks, 1) * 100, 2),
            'gross_revenue' : float(revenue),
            'user_rewards'  : float(rewards),
            'platform_profit': float(revenue - rewards),
            'epc'           : round(float(revenue) / max(clicks, 1), 4),
        }

    @staticmethod
    def sync_all_feeds():
        """Trigger feed sync for all enabled sources."""
        from api.offer_inventory.offerwall_integration import OfferWallIntegrationService
        return OfferWallIntegrationService.fetch_and_sync_all()

    @staticmethod
    def test_postback(network_id: str) -> dict:
        """Send a test postback to verify configuration."""
        from api.offer_inventory.models import OfferNetwork
        from api.offer_inventory.webhooks.s2s_postback import OutboundPostbackSender
        try:
            network = OfferNetwork.objects.get(id=network_id)
            if not network.postback_url:
                return {'success': False, 'error': 'No postback URL configured'}
            url = network.postback_url.replace('{click_id}', 'TEST_CLICK').replace('{transaction_id}', 'TEST_TX').replace('{payout}', '0')
            result = OutboundPostbackSender.send(url, {}, secret=network.api_secret, timeout=5)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def update_daily_network_stats(network_id: str):
        """Update NetworkStat for today."""
        from api.offer_inventory.models import NetworkStat, Click, Conversion
        from django.db.models import Count, Sum, Avg

        today = timezone.now().date()
        clicks  = Click.objects.filter(offer__network_id=network_id, created_at__date=today, is_fraud=False).count()
        convs   = Conversion.objects.filter(offer__network_id=network_id, created_at__date=today, status__name='approved')
        agg     = convs.aggregate(count=Count('id'), rev=Sum('payout_amount'))
        count   = agg['count'] or 0
        revenue = agg['rev']   or Decimal('0')

        avg_payout = (revenue / count) if count > 0 else Decimal('0')
        cvr        = round(count / max(clicks, 1) * 100, 2)
        epc        = round(float(revenue) / max(clicks, 1), 4)

        NetworkStat.objects.update_or_create(
            network_id=network_id, date=today,
            defaults={
                'clicks'     : clicks,
                'conversions': count,
                'revenue'    : revenue,
                'avg_payout' : avg_payout,
                'cvr'        : cvr,
                'epc'        : epc,
            }
        )


class SubIDTracker:
    """
    Sub-ID tracking for deep affiliate analytics.
    Tracks s1–s5 parameter chains.
    """

    @staticmethod
    def get_sub_id_report(offer_id: str, days: int = 7) -> list:
        """Performance breakdown by s1 parameter."""
        from api.offer_inventory.models import SubID, Conversion
        from django.db.models import Count, Sum
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        return list(
            SubID.objects.filter(offer_id=offer_id)
            .values('s1')
            .annotate(
                clicks     =Count('clicks'),
                conversions=Count('clicks__conversion'),
                revenue    =Sum('revenue'),
            )
            .order_by('-conversions')[:20]
        )

    @staticmethod
    def attribute_revenue(sub_id_obj, amount: Decimal):
        """Add revenue to a sub-ID."""
        from api.offer_inventory.models import SubID
        from django.db.models import F
        SubID.objects.filter(id=sub_id_obj.id).update(
            revenue=F('revenue') + amount
        )
