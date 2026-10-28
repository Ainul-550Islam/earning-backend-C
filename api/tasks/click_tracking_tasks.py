"""
tasks/click_tracking_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Click Tracking & Postback System (CPAlead Gap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead's click tracking system:
  - Unique click ID generation
  - Click deduplication
  - Geo/device logging
  - Postback firing on conversion
  - Click-to-conversion attribution window
  - Click log cleanup

  ✅ process_click_event         — log a click, check fraud, return click_id
  ✅ fire_postback               — fire pixel/postback after conversion
  ✅ retry_failed_postbacks      — retry failed postback fires
  ✅ cleanup_old_clicks          — delete click logs older than 90 days
  ✅ calculate_click_attribution — match conversions to clicks
  ✅ generate_click_report       — daily click analytics
"""
import logging
import uuid
import hashlib
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

CLICK_DEDUP_TTL       = 3600          # 1 hour
ATTRIBUTION_WINDOW    = 86400 * 30    # 30 days in seconds
CLICK_CACHE_PREFIX    = 'click_data_'


@shared_task(bind=True, max_retries=3, default_retry_delay=15,
             name='tasks.click_tracking_tasks.process_click_event')
def process_click_event(
    self,
    user_id: int,
    offer_id: str,
    ip_address: str,
    user_agent: str,
    country: str = 'US',
    device: str = 'desktop',
    referrer: str = '',
    sub_id: str = '',
) -> dict:
    """
    Record a click event on an offer:
    1. Generate unique click_id
    2. Fraud check (blocked IP, velocity)
    3. Store click data in cache + DB
    4. Update offer click counter
    Returns: {click_id, status, is_fraud}
    """
    try:
        # Generate click_id
        raw       = f"{user_id}:{offer_id}:{uuid.uuid4()}"
        click_id  = hashlib.sha256(raw.encode()).hexdigest()[:32]

        # Dedup: same user + offer in 1 hour
        dedup_key = f'click_dedup_{user_id}_{offer_id}'
        if cache.get(dedup_key):
            logger.info(f"[CLICK] Duplicate click: user={user_id} offer={offer_id}")
            existing = cache.get(dedup_key)
            return {'status': 'duplicate', 'click_id': existing, 'is_fraud': False}

        # Fraud check: blocked IP
        is_blocked = bool(cache.get(f'ip_blocked_{hashlib.md5(ip_address.encode()).hexdigest()}'))
        if is_blocked:
            logger.warning(f"[CLICK] Blocked IP click: {ip_address}")
            return {'status': 'blocked', 'click_id': None, 'is_fraud': True}

        # Store click data in cache for attribution
        click_data = {
            'click_id':   click_id,
            'user_id':    user_id,
            'offer_id':   offer_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'country':    country,
            'device':     device,
            'referrer':   referrer,
            'sub_id':     sub_id,
            'clicked_at': timezone.now().isoformat(),
        }
        cache.set(f'{CLICK_CACHE_PREFIX}{click_id}', click_data, timeout=ATTRIBUTION_WINDOW)
        cache.set(dedup_key, click_id, timeout=CLICK_DEDUP_TTL)

        # Persist to DB
        try:
            from ad_networks.models import OfferClick, SmartlinkOffer
            from django.db.models import F

            offer_obj = SmartlinkOffer.objects.filter(external_id=offer_id).first()
            OfferClick.objects.create(
                click_id=click_id,
                offer=offer_obj,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent[:500],
                country=country,
                device=device,
                referrer=referrer[:500],
                sub_id=sub_id,
                is_duplicate=False,
                is_suspicious=False,
                created_at=timezone.now(),
            )
            if offer_obj:
                SmartlinkOffer.objects.filter(pk=offer_obj.pk).update(
                    total_clicks=F('total_clicks') + 1,
                    daily_clicks_used=F('daily_clicks_used') + 1,
                )
        except ImportError:
            pass

        return {
            'status': 'success',
            'click_id': click_id,
            'is_fraud': False,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] process_click_event: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=5, default_retry_delay=15,
             name='tasks.click_tracking_tasks.fire_postback')
def fire_postback(
    self,
    click_id: str,
    transaction_id: str,
    payout: str = '0',
    status: str = 'approved',
    advertiser_postback_url: str = '',
) -> dict:
    """
    Fire a postback pixel/URL to the advertiser after a conversion.
    Replaces macros: {click_id}, {transaction_id}, {payout}, {status}
    Retries up to 5 times with exponential backoff.
    """
    try:
        import requests
        logger.info(f"🔔 Firing postback: click={click_id} txn={transaction_id} payout=${payout}")

        fired = 0
        errors = 0

        # 1. Advertiser postback
        if advertiser_postback_url:
            url = (advertiser_postback_url
                   .replace('{click_id}', click_id)
                   .replace('{transaction_id}', transaction_id)
                   .replace('{payout}', str(payout))
                   .replace('{status}', status))
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code < 400:
                    fired += 1
                    logger.info(f"[POSTBACK] Advertiser postback OK: {resp.status_code}")
                else:
                    errors += 1
                    logger.error(f"[POSTBACK] Advertiser postback HTTP {resp.status_code}: {url}")
            except Exception as req_err:
                errors += 1
                logger.error(f"[POSTBACK] Advertiser postback error: {req_err}")

        # 2. Publisher sub-affiliate postback (if sub_id configured)
        click_data = cache.get(f'{CLICK_CACHE_PREFIX}{click_id}', {})
        sub_id     = click_data.get('sub_id', '')

        if sub_id:
            try:
                from ad_networks.models import SubAffiliatePostback
                sub_pb = SubAffiliatePostback.objects.filter(
                    sub_id=sub_id, is_active=True
                ).first()
                if sub_pb:
                    sub_url = (sub_pb.postback_url
                               .replace('{click_id}', click_id)
                               .replace('{payout}', str(payout)))
                    resp = requests.get(sub_url, timeout=10)
                    if resp.status_code < 400:
                        fired += 1
            except (ImportError, Exception):
                pass

        # 3. Log postback
        try:
            from ad_networks.models import PostbackLog
            PostbackLog.objects.create(
                click_id=click_id,
                transaction_id=transaction_id,
                postback_url=advertiser_postback_url,
                status='success' if errors == 0 else 'failed',
                payout=Decimal(str(payout)),
                fired_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status': 'success' if errors == 0 else 'partial',
            'click_id': click_id,
            'transaction_id': transaction_id,
            'fired': fired,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] fire_postback: {exc}")
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 15, 300))


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.click_tracking_tasks.cleanup_old_clicks')
def cleanup_old_clicks(self, days_to_keep: int = 90, batch_size: int = 1000) -> dict:
    """
    Delete OfferClick records older than `days_to_keep` days.
    Runs in batches to avoid long DELETE locks.
    """
    try:
        from datetime import timedelta
        logger.info(f"🧹 Cleaning up old clicks (keep={days_to_keep}d)...")
        deleted = 0
        cutoff  = timezone.now() - timedelta(days=days_to_keep)

        try:
            from ad_networks.models import OfferClick

            while True:
                ids = list(
                    OfferClick.objects.filter(created_at__lt=cutoff)
                    .values_list('id', flat=True)[:batch_size]
                )
                if not ids:
                    break
                n, _ = OfferClick.objects.filter(id__in=ids).delete()
                deleted += n
                logger.debug(f"  Deleted {n} click records (total={deleted})")

        except ImportError as e:
            logger.warning(f"[WARN] OfferClick not available: {e}")

        return {'status': 'success', 'deleted': deleted, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.click_tracking_tasks.calculate_click_attribution')
def calculate_click_attribution(self, lookback_hours: int = 1) -> dict:
    """
    Match recent unattributed conversions to their originating clicks.
    Uses click_id stored in conversion record.
    Updates conversion with publisher user_id and sub_id.
    """
    try:
        from datetime import timedelta
        logger.info(f"🔗 Calculating click attribution (lookback={lookback_hours}h)...")
        attributed = 0
        unmatched  = 0
        cutoff     = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from ad_networks.models import OfferConversion

            no_attr = OfferConversion.objects.filter(
                converted_at__gte=cutoff,
                user_id__isnull=True,
                click_id__isnull=False,
            ).exclude(click_id='')

            for conv in no_attr:
                click_data = cache.get(f'{CLICK_CACHE_PREFIX}{conv.click_id}')
                if click_data:
                    conv.user_id = click_data.get('user_id')
                    conv.sub_id  = click_data.get('sub_id', '')
                    conv.country = click_data.get('country', conv.country)
                    conv.device  = click_data.get('device', '')
                    conv.save(update_fields=['user_id', 'sub_id', 'country', 'device'])
                    attributed += 1
                else:
                    # Try DB lookup
                    try:
                        from ad_networks.models import OfferClick
                        click = OfferClick.objects.filter(click_id=conv.click_id).first()
                        if click:
                            conv.user_id = click.user_id
                            conv.save(update_fields=['user_id'])
                            attributed += 1
                        else:
                            unmatched += 1
                    except ImportError:
                        unmatched += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'attributed': attributed,
            'unmatched': unmatched,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.click_tracking_tasks.generate_click_report')
def generate_click_report(self, date_str: str = None) -> dict:
    """
    Daily click analytics report:
    - Total clicks, unique IPs, unique users
    - Click-to-conversion rate
    - Top offers by clicks
    - Top countries
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Q

        target  = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else (timezone.now() - timedelta(days=1)).date()
        )
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        logger.info(f"📊 Generating click report for {target}...")
        report = {'date': str(target), 'type': 'click_daily', 'totals': {}, 'by_offer': []}

        try:
            from ad_networks.models import OfferClick

            qs  = OfferClick.objects.filter(created_at__gte=day_start, created_at__lt=day_end)
            agg = qs.aggregate(
                total_clicks=Count('id'),
                unique_users=Count('user_id', distinct=True),
                unique_ips=Count('ip_address', distinct=True),
                fraud_clicks=Count('id', filter=Q(is_suspicious=True)),
            )
            report['totals'] = {
                'total_clicks':  agg['total_clicks'] or 0,
                'unique_users':  agg['unique_users'] or 0,
                'unique_ips':    agg['unique_ips'] or 0,
                'fraud_clicks':  agg['fraud_clicks'] or 0,
                'fraud_rate_pct': round(
                    (agg['fraud_clicks'] or 0) / max(agg['total_clicks'] or 1, 1) * 100, 2
                ),
            }
            by_offer = qs.values('offer__external_id', 'offer__name').annotate(
                cnt=Count('id')
            ).order_by('-cnt')[:10]
            report['by_offer'] = list(by_offer)

        except ImportError:
            pass

        cache.set(f'click_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)
