"""
tasks/macro_tracking_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Macro Parameter Tracking Tasks (CPAlead Feature)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead passes {cost} and {traffic_id} macro parameters back
to third-party tracking platforms (Voluum, Binom, RedTrack, etc.)

Macros allow advertisers to:
  - Track exact cost per click in 3rd party tools
  - Pass traffic source IDs to their analytics
  - Optimize campaigns across multiple traffic sources
  - Integrate with any tracking platform seamlessly

  ✅ resolve_macro_params       — replace macros in tracker URLs
  ✅ process_macro_postback     — handle postback with macro values
  ✅ track_traffic_source       — log traffic source performance
  ✅ sync_tracking_platforms    — sync data with Voluum/Binom/RedTrack
  ✅ generate_macro_report      — macro tracking analytics report
  ✅ validate_tracking_url      — verify tracker URL format and reachability
"""
import logging
import re
import hashlib
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Supported macros and their resolution
MACRO_DEFINITIONS = {
    '{click_id}':     'click_id',
    '{cost}':         'bid_price',         # Actual cost paid by advertiser
    '{traffic_id}':   'traffic_source_id', # Publisher/traffic source identifier
    '{pub_id}':       'publisher_id',
    '{offer_id}':     'offer_id',
    '{country}':      'country',
    '{device}':       'device',
    '{os}':           'os_type',
    '{browser}':      'browser',
    '{ip}':           'ip_address',
    '{payout}':       'publisher_payout',  # Publisher's share
    '{transaction_id}': 'transaction_id',
    '{status}':       'conversion_status',
    '{timestamp}':    'unix_timestamp',
    '{campaign_id}':  'campaign_id',
    '{creative_id}':  'creative_id',
    '{sub_id}':       'sub_affiliate_id',
    '{sub_id2}':      'sub2',
    '{sub_id3}':      'sub3',
}


@shared_task(bind=True, max_retries=2, default_retry_delay=5,
             name='tasks.macro_tracking_tasks.resolve_macro_params')
def resolve_macro_params(
    self,
    template_url: str,
    context: dict,
) -> dict:
    """
    Replace macro placeholders in a tracking URL with actual values.

    Example:
        template = "https://tracker.io/click?cid={click_id}&cost={cost}&src={traffic_id}"
        context  = {'click_id': 'abc123', 'bid_price': '0.05', 'traffic_source_id': 'pub456'}
        result   = "https://tracker.io/click?cid=abc123&cost=0.05&src=pub456"

    Supports all major tracking platforms: Voluum, Binom, RedTrack, FunnelFlux.
    """
    try:
        resolved_url = template_url
        resolved     = {}
        unresolved   = []

        for macro, context_key in MACRO_DEFINITIONS.items():
            if macro in template_url:
                value = context.get(context_key, '')

                # Special handling
                if macro == '{timestamp}':
                    value = str(int(timezone.now().timestamp()))
                elif macro == '{cost}' and not value:
                    value = context.get('payout', context.get('bid_price', '0.00'))
                elif not value:
                    value = ''

                resolved_url = resolved_url.replace(macro, str(value))
                resolved[macro] = str(value)

                if not value and value != 0:
                    unresolved.append(macro)

        return {
            'status':        'success',
            'resolved_url':  resolved_url,
            'resolved':      resolved,
            'unresolved':    unresolved,
            'original_url':  template_url,
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.macro_tracking_tasks.process_macro_postback')
def process_macro_postback(
    self,
    postback_url: str,
    click_id: str,
    payout: str,
    status: str,
    traffic_id: str = '',
    cost: str = '',
    additional_params: dict = None,
) -> dict:
    """
    Process a postback with macro substitution for 3rd party tracking.
    Fires the resolved URL to the advertiser's tracking system.

    This is how CPAlead passes {cost} and {traffic_id} back to platforms
    like Voluum, Binom, RedTrack, FunnelFlux, etc.
    """
    try:
        import requests

        context = {
            'click_id':          click_id,
            'bid_price':         cost or payout,
            'traffic_source_id': traffic_id,
            'publisher_payout':  payout,
            'conversion_status': status,
            'unix_timestamp':    str(int(timezone.now().timestamp())),
            **(additional_params or {}),
        }

        # Resolve macros
        resolved = resolve_macro_params.apply(kwargs={
            'template_url': postback_url,
            'context': context,
        }).get()

        final_url = resolved.get('resolved_url', postback_url)
        logger.info(f"[MACRO] Firing postback: {final_url[:80]}...")

        # Fire postback
        try:
            resp = requests.get(final_url, timeout=10)
            success = resp.status_code < 400
            if not success:
                logger.error(f"[MACRO] Postback HTTP {resp.status_code}: {final_url[:60]}")
        except Exception as req_err:
            logger.error(f"[MACRO] Postback error: {req_err}")
            success = False

        # Log
        try:
            from ad_networks.models import MacroPostbackLog
            MacroPostbackLog.objects.create(
                click_id=click_id,
                original_url=postback_url,
                resolved_url=final_url[:1000],
                status='success' if success else 'failed',
                payout=Decimal(payout),
                traffic_id=traffic_id,
                fired_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status':       'success' if success else 'failed',
            'resolved_url': final_url,
            'click_id':     click_id,
            'traffic_id':   traffic_id,
            'payout':       payout,
            'timestamp':    timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] process_macro_postback: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15,
             name='tasks.macro_tracking_tasks.track_traffic_source')
def track_traffic_source(
    self,
    traffic_id: str,
    event_type: str,    # 'click' | 'conversion' | 'rejection'
    offer_id: str = '',
    country: str = '',
    device: str = '',
    payout: str = '0',
) -> dict:
    """
    Track performance metrics per traffic source.
    Builds a per-source performance profile used for optimization
    and blacklisting.
    """
    try:
        stats_key = f'traffic_source_{traffic_id}'
        stats     = cache.get(stats_key) or {
            'traffic_id':   traffic_id,
            'clicks':       0,
            'conversions':  0,
            'rejections':   0,
            'revenue':      '0',
            'cvr':          '0',
            'quality_score': 50,
        }

        if event_type == 'click':
            stats['clicks'] += 1
        elif event_type == 'conversion':
            stats['conversions'] += 1
            stats['revenue'] = str(Decimal(stats['revenue']) + Decimal(payout))
        elif event_type == 'rejection':
            stats['rejections'] += 1

        # Compute CVR
        clicks = stats['clicks']
        convs  = stats['conversions']
        stats['cvr'] = str(round(convs / clicks * 100, 2)) if clicks > 0 else '0'

        # Quality score (0-100) — higher CVR = better quality
        cvr_float = float(stats['cvr'])
        rej_rate  = stats['rejections'] / max(clicks, 1) * 100
        stats['quality_score'] = max(0, min(100, int(cvr_float * 10 - rej_rate)))

        stats['last_event_at'] = timezone.now().isoformat()
        cache.set(stats_key, stats, timeout=86400 * 7)

        # DB persistence
        try:
            from ad_networks.models import TrafficSource
            TrafficSource.objects.update_or_create(
                traffic_id=traffic_id,
                defaults={
                    'clicks':        stats['clicks'],
                    'conversions':   stats['conversions'],
                    'rejections':    stats['rejections'],
                    'revenue':       Decimal(stats['revenue']),
                    'quality_score': stats['quality_score'],
                    'last_event_at': timezone.now(),
                },
            )
        except ImportError:
            pass

        return {
            'status':     'tracked',
            'traffic_id': traffic_id,
            'event':      event_type,
            'stats':      stats,
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.macro_tracking_tasks.sync_tracking_platforms')
def sync_tracking_platforms(self) -> dict:
    """
    Sync conversion data with connected 3rd party tracking platforms.
    Platforms: Voluum, Binom, RedTrack, FunnelFlux, Skro.
    Sends conversion events via their API or postback.
    """
    try:
        from datetime import timedelta
        from django.conf import settings
        logger.info("🔄 Syncing with tracking platforms...")

        synced  = 0
        errors  = 0
        cutoff  = timezone.now() - timedelta(minutes=30)

        TRACKING_PLATFORMS = getattr(settings, 'THIRD_PARTY_TRACKERS', {})

        try:
            from ad_networks.models import OfferConversion
            import requests

            recent = OfferConversion.objects.filter(
                converted_at__gte=cutoff,
                status='approved',
                tracker_synced=False,
            )[:500]

            for conv in recent:
                for platform_name, config in TRACKING_PLATFORMS.items():
                    if not config.get('api_key'):
                        continue
                    try:
                        resp = requests.post(
                            config['postback_url'],
                            json={
                                'click_id':       conv.click_id,
                                'payout':         str(conv.payout),
                                'transaction_id': conv.transaction_id,
                                'status':         'approved',
                            },
                            headers={'X-API-Key': config['api_key']},
                            timeout=5,
                        )
                        if resp.status_code < 400:
                            synced += 1
                    except Exception:
                        errors += 1

                conv.tracker_synced = True
                conv.save(update_fields=['tracker_synced'])

        except ImportError as e:
            logger.warning(f"[WARN] OfferConversion not available: {e}")

        return {
            'status':  'success',
            'synced':  synced,
            'errors':  errors,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.macro_tracking_tasks.validate_tracking_url')
def validate_tracking_url(self, url: str) -> dict:
    """Validate a tracking URL format and check reachability."""
    try:
        import requests

        # Check URL format
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$',
            re.IGNORECASE,
        )
        is_valid_format = bool(url_pattern.match(url))

        # Check required macros
        has_click_id = '{click_id}' in url
        has_cost     = '{cost}' in url
        detected_macros = [m for m in MACRO_DEFINITIONS if m in url]

        # Test reachability (with test macros resolved)
        test_url     = url
        is_reachable = False
        status_code  = None

        for macro in MACRO_DEFINITIONS:
            test_url = test_url.replace(macro, 'TEST_VALUE')

        if is_valid_format:
            try:
                resp        = requests.head(test_url, timeout=5, allow_redirects=True)
                status_code = resp.status_code
                is_reachable = resp.status_code < 500
            except Exception:
                is_reachable = False

        return {
            'status':           'success',
            'url':              url,
            'is_valid_format':  is_valid_format,
            'is_reachable':     is_reachable,
            'http_status':      status_code,
            'has_click_id':     has_click_id,
            'has_cost_macro':   has_cost,
            'detected_macros':  detected_macros,
            'missing_macros':   [] if has_click_id else ['{click_id}'],
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.macro_tracking_tasks.generate_macro_report')
def generate_macro_report(self, date_str: str = None) -> dict:
    """Daily macro tracking report: top traffic sources, CVR, revenue."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum, Avg

        target    = (datetime.strptime(date_str, '%Y-%m-%d').date()
                     if date_str else (timezone.now() - timedelta(days=1)).date())

        report = {
            'date':             str(target),
            'type':             'macro_tracking_daily',
            'top_sources':      [],
            'generated_at':     timezone.now().isoformat(),
        }

        try:
            from ad_networks.models import TrafficSource
            top = TrafficSource.objects.order_by('-revenue').values(
                'traffic_id', 'clicks', 'conversions', 'revenue', 'quality_score'
            )[:20]
            report['top_sources'] = [
                {
                    'traffic_id':    r['traffic_id'],
                    'clicks':        r['clicks'],
                    'conversions':   r['conversions'],
                    'cvr':           round(r['conversions'] / max(r['clicks'], 1) * 100, 2),
                    'revenue':       str(r['revenue'] or 0),
                    'quality_score': r['quality_score'],
                }
                for r in top
            ]
        except ImportError:
            pass

        cache.set(f'macro_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)
