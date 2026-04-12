# =============================================================================
# promotions/cpc_offers/cpc_manager.py
# 🟠 HIGH — CPC (Cost Per Click) Offer System
# CPAlead EXCLUSIVE: up to $1+ per click, instant conversion on click
# "No other network matches our CPC campaigns" — CPAlead
# =============================================================================
import hashlib
import hmac
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

CPC_RATE_TIERS = {
    'US':  {'min': Decimal('0.05'), 'max': Decimal('1.50'), 'avg': Decimal('0.35')},
    'GB':  {'min': Decimal('0.04'), 'max': Decimal('1.20'), 'avg': Decimal('0.28')},
    'CA':  {'min': Decimal('0.04'), 'max': Decimal('1.10'), 'avg': Decimal('0.25')},
    'AU':  {'min': Decimal('0.03'), 'max': Decimal('0.90'), 'avg': Decimal('0.22')},
    'DE':  {'min': Decimal('0.03'), 'max': Decimal('0.80'), 'avg': Decimal('0.20')},
    'BD':  {'min': Decimal('0.01'), 'max': Decimal('0.10'), 'avg': Decimal('0.03')},
    'OTHER': {'min': Decimal('0.01'), 'max': Decimal('0.15'), 'avg': Decimal('0.05')},
}


class CPCOfferManager:
    """
    CPC Offer: publisher earns per click (instant conversion, no action needed).
    System verifies click is real (not bot) before paying.
    """
    CLICK_PREFIX = 'cpc_click:'
    SEEN_PREFIX = 'cpc_seen:'   # Prevent duplicate clicks from same visitor
    DEDUP_WINDOW = 3600          # 1 hour dedup window

    def record_cpc_click(
        self,
        campaign_id: int,
        publisher_id: int,
        visitor_id: str,
        country: str,
        ip: str,
        user_agent: str,
    ) -> dict:
        """
        Record a CPC click and award publisher instantly if valid.
        Returns: redirect URL + payout status
        """
        # 1. Duplicate click check
        dedup_key = f'{self.SEEN_PREFIX}{campaign_id}:{visitor_id}'
        if cache.get(dedup_key):
            return {
                'paid': False,
                'reason': 'duplicate_click',
                'redirect': self._get_redirect_url(campaign_id),
            }

        # 2. Bot check (basic)
        if self._is_bot(user_agent, ip):
            return {
                'paid': False,
                'reason': 'bot_detected',
                'redirect': self._get_redirect_url(campaign_id),
            }

        # 3. Calculate payout
        rate_info = CPC_RATE_TIERS.get(country.upper(), CPC_RATE_TIERS['OTHER'])
        payout = rate_info['avg']

        # 4. Mark click as seen (prevent duplicates)
        cache.set(dedup_key, True, timeout=self.DEDUP_WINDOW)

        # 5. Award payout
        self._award_cpc_payout(publisher_id, campaign_id, payout, visitor_id)

        # 6. Log click
        click_key = f'{self.CLICK_PREFIX}{campaign_id}:{publisher_id}:{timezone.now().date()}'
        cache.incr(click_key) if cache.get(click_key) else cache.set(click_key, 1, timeout=3600 * 25)

        logger.info(f'CPC click paid: campaign={campaign_id} pub={publisher_id} ${payout} country={country}')

        return {
            'paid': True,
            'payout': str(payout),
            'currency': 'USD',
            'redirect': self._get_redirect_url(campaign_id),
        }

    def get_cpc_campaigns(self, country: str = 'US', device: str = 'desktop', limit: int = 20) -> list:
        """Get CPC campaigns for publisher to promote."""
        from api.promotions.models import Campaign
        rate_info = CPC_RATE_TIERS.get(country.upper(), CPC_RATE_TIERS['OTHER'])
        # In production: filter campaigns with cpc_enabled=True
        campaigns = Campaign.objects.filter(
            status='active',
        ).order_by('-per_task_reward')[:limit]

        return [
            {
                'campaign_id': c.id,
                'title': c.title,
                'cpc_rate': str(rate_info['avg']),
                'cpc_rate_display': f'${rate_info["avg"]:.2f} per click',
                'max_rate': str(rate_info['max']),
                'category': c.category.name if c.category else 'other',
                'is_instant': True,
                'click_url': f'/api/promotions/cpc/click/{c.id}/',
            }
            for c in campaigns
        ]

    def get_publisher_cpc_stats(self, publisher_id: int, days: int = 7) -> dict:
        """Publisher's CPC performance stats."""
        from api.promotions.models import PromotionTransaction
        from django.db.models import Sum, Count
        cutoff = timezone.now() - timezone.timedelta(days=days)
        stats = PromotionTransaction.objects.filter(
            user_id=publisher_id,
            transaction_type='reward',
            notes__icontains='CPC',
            created_at__gte=cutoff,
        ).aggregate(
            total_earnings=Sum('amount'),
            total_clicks=Count('id'),
        )
        total = stats['total_earnings'] or Decimal('0')
        clicks = stats['total_clicks'] or 0
        return {
            'publisher_id': publisher_id,
            'period_days': days,
            'total_clicks': clicks,
            'total_earnings': str(total),
            'avg_cpc': str((total / clicks).quantize(Decimal('0.0001'))) if clicks > 0 else '0.0000',
            'epc': str((total / clicks * 100).quantize(Decimal('0.01'))) if clicks > 0 else '0.00',
        }

    def _award_cpc_payout(self, publisher_id: int, campaign_id: int, amount: Decimal, visitor_id: str):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id,
                transaction_type='reward',
                amount=amount,
                status='completed',
                notes=f'CPC Click Reward — Campaign #{campaign_id}',
                metadata={'campaign_id': campaign_id, 'visitor_id': visitor_id, 'type': 'cpc'},
            )
        except Exception as e:
            logger.error(f'CPC payout failed: {e}')

    def _is_bot(self, user_agent: str, ip: str) -> bool:
        """Basic bot detection."""
        ua = user_agent.lower()
        bot_signals = ['bot', 'crawler', 'spider', 'scraper', 'headless', 'curl', 'wget', 'python']
        return any(signal in ua for signal in bot_signals)

    def _get_redirect_url(self, campaign_id: int) -> str:
        from api.promotions.models import Campaign
        try:
            c = Campaign.objects.get(id=campaign_id)
            return getattr(c, 'destination_url', f'/offers/{campaign_id}/')
        except Exception:
            return f'/offers/{campaign_id}/'


# ── API Views ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def cpc_click_view(request, campaign_id):
    """
    GET /api/promotions/cpc/click/<campaign_id>/?pub=123
    → Records click, awards publisher, redirects to offer
    """
    from django.shortcuts import redirect
    pub_id = int(request.query_params.get('pub', 0))
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    ua = request.META.get('HTTP_USER_AGENT', '')
    country = request.META.get('HTTP_CF_IPCOUNTRY', 'US')
    visitor_id = hashlib.sha256(f'{ip}:{ua}'.encode()).hexdigest()[:20]
    manager = CPCOfferManager()
    result = manager.record_cpc_click(
        campaign_id=campaign_id,
        publisher_id=pub_id,
        visitor_id=visitor_id,
        country=country,
        ip=ip,
        user_agent=ua,
    )
    return redirect(result['redirect'])


@api_view(['GET'])
@permission_classes([AllowAny])
def cpc_campaigns_view(request):
    """GET /api/promotions/cpc/campaigns/?country=US&device=mobile"""
    manager = CPCOfferManager()
    campaigns = manager.get_cpc_campaigns(
        country=request.query_params.get('country', 'US'),
        device=request.query_params.get('device', 'desktop'),
    )
    return Response({'campaigns': campaigns})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cpc_stats_view(request):
    """GET /api/promotions/cpc/stats/?days=7"""
    manager = CPCOfferManager()
    return Response(manager.get_publisher_cpc_stats(
        publisher_id=request.user.id,
        days=int(request.query_params.get('days', 7)),
    ))
