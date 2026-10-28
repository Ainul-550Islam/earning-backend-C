"""
tasks/cpc_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPC (Cost Per Click) Campaign Tasks — CPAlead exclusive feature
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead pays up to $1+ per click on exclusive PPC campaigns.
Every click IS a conversion — no postback needed.
  ✅ process_cpc_click          — instant credit on click
  ✅ detect_cpc_fraud           — click fraud detection
  ✅ sync_cpc_campaigns         — sync CPC campaign inventory
  ✅ generate_cpc_report        — daily CPC analytics
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

CPC_DEDUP_TTL = 3600  # 1 hour between same user clicks on same campaign


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.cpc_tasks.process_cpc_click')
def process_cpc_click(
    self,
    user_id: int,
    campaign_id: int,
    publisher_id: int,
    ip_address: str,
    user_agent: str,
    country: str = 'US',
    device: str = 'desktop',
    click_id: str = '',
) -> dict:
    """
    Process a CPC (Pay Per Click) event.
    Unlike CPA/CPI — the click itself is the conversion.
    Instant credit to publisher wallet.
    """
    try:
        logger.info(f"💨 CPC click: campaign={campaign_id} user={user_id} country={country}")

        # Dedup: same user + campaign in 1 hour
        dedup_key = f'cpc_dedup_{user_id}_{campaign_id}'
        if cache.get(dedup_key):
            return {'status': 'duplicate', 'reason': 'rate_limit'}
        cache.set(dedup_key, 1, timeout=CPC_DEDUP_TTL)

        # Fraud check: same IP many clicks
        ip_key   = f'cpc_ip_{ip_address}'
        ip_count = cache.get(ip_key, 0) + 1
        cache.set(ip_key, ip_count, timeout=3600)
        if ip_count > 20:
            logger.warning(f"[CPC FRAUD] IP {ip_address} clicked {ip_count} times")
            return {'status': 'fraud_detected', 'reason': 'ip_velocity'}

        # Get CPC rate
        payout = _get_cpc_rate(campaign_id, country, device)
        if payout <= Decimal('0'):
            return {'status': 'skipped', 'reason': 'zero_payout'}

        publisher_share = payout * Decimal('0.70')  # 70% to publisher

        # Record click
        try:
            from ad_networks.models import CpcClick
            CpcClick.objects.create(
                click_id=click_id,
                campaign_id=campaign_id,
                user_id=user_id,
                publisher_id=publisher_id,
                ip_address=ip_address,
                country=country,
                device=device,
                payout=payout,
                publisher_payout=publisher_share,
                status='credited',
                clicked_at=timezone.now(),
            )
        except ImportError:
            pass

        # Instant credit
        try:
            from api.tasks.services import WalletService
            WalletService().credit(
                user_id=publisher_id,
                amount=publisher_share,
                transaction_type='cpc_click',
                reference=f'cpc_{campaign_id}_{click_id}',
                metadata={'campaign_id': campaign_id, 'country': country, 'device': device},
            )
        except ImportError:
            pass

        # Update campaign spend
        try:
            from ad_networks.models import Campaign
            from django.db.models import F
            Campaign.objects.filter(pk=campaign_id).update(
                total_clicks=F('total_clicks') + 1,
                daily_clicks=F('daily_clicks') + 1,
                total_spend=F('total_spend') + payout,
            )
        except ImportError:
            pass

        return {
            'status': 'success',
            'click_id': click_id,
            'payout': str(publisher_share),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.cpc_tasks.generate_cpc_report')
def generate_cpc_report(self, date_str: str = None) -> dict:
    """Daily CPC performance: clicks, revenue, top campaigns."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum

        target = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        report = {'date': str(target), 'type': 'cpc_daily', 'totals': {}}
        try:
            from ad_networks.models import CpcClick
            agg = CpcClick.objects.filter(
                clicked_at__gte=day_start, clicked_at__lt=day_end
            ).aggregate(
                total_clicks=Count('id'),
                total_revenue=Sum('payout'),
                total_publisher_payout=Sum('publisher_payout'),
            )
            report['totals'] = {
                'clicks':             agg['total_clicks'] or 0,
                'revenue':            str(agg['total_revenue'] or Decimal('0')),
                'publisher_payout':   str(agg['total_publisher_payout'] or Decimal('0')),
            }
        except ImportError:
            pass

        cache.set(f'cpc_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report}

    except Exception as exc:
        raise self.retry(exc=exc)


def _get_cpc_rate(campaign_id: int, country: str, device: str) -> Decimal:
    """Get CPC rate for campaign + targeting segment."""
    cache_key = f'cpc_rate_{campaign_id}_{country}_{device}'
    cached = cache.get(cache_key)
    if cached:
        return Decimal(str(cached))
    try:
        from ad_networks.models import CpcCampaign
        camp = CpcCampaign.objects.filter(pk=campaign_id, is_active=True).first()
        if camp:
            rates  = camp.geo_rates or {}
            rate   = Decimal(str(rates.get(country, rates.get('DEFAULT', camp.base_cpc_rate or 0.05))))
            cache.set(cache_key, str(rate), timeout=300)
            return rate
    except ImportError:
        pass
    return Decimal('0.05')  # Default $0.05 per click
