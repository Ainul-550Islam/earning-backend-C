"""
tasks/ad_unit_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ad Unit Management Tasks (CPAlead WordPress Plugin Features)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead's WordPress plugin provides pop-unders, banners, interstitials,
push-up ads, and custom ad units — 90% Pay Per Click.

  ✅ serve_ad_unit              — select & serve the best ad for a slot
  ✅ track_ad_impression        — record impression event
  ✅ track_ad_click             — record click + instant PPC credit
  ✅ rotate_ad_creatives        — swap out low-CTR creatives
  ✅ update_ad_cpm_rates        — refresh CPM/CPC rates per geo
  ✅ generate_ad_report         — daily ad performance report
  ✅ cleanup_old_impressions    — purge impression logs
  ✅ score_ad_quality           — quality-score each ad creative
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

AD_UNIT_TYPES  = ['popunder', 'banner', 'interstitial', 'pushup', 'custom', 'native']
PPC_RATE_TTL   = 300    # Cache ad rates for 5 minutes


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.ad_unit_tasks.serve_ad_unit')
def serve_ad_unit(
    self,
    publisher_id: int,
    slot_type: str,        # 'popunder' | 'banner' | 'interstitial' | 'pushup'
    country: str = 'US',
    device: str  = 'desktop',
    page_url: str = '',
) -> dict:
    """
    Select and return the highest-paying ad unit for a publisher slot.
    Uses cached geo/device-targeted ad inventory.
    90% of impressions are PPC — credit fires on click.
    """
    try:
        cache_key = f'ad_inventory_{slot_type}_{country}_{device}'
        ads       = cache.get(cache_key) or _load_ads_from_db(slot_type, country, device)

        if not ads:
            return {'status': 'no_fill', 'slot_type': slot_type, 'country': country}

        # Pick highest-paying ad
        best_ad = max(ads, key=lambda x: float(x.get('bid_price', 0)))

        # Record impression
        impression_id = _record_impression(
            ad_id=best_ad['ad_id'],
            publisher_id=publisher_id,
            slot_type=slot_type,
            country=country,
            device=device,
            page_url=page_url,
        )

        return {
            'status':        'filled',
            'impression_id': impression_id,
            'ad_id':         best_ad['ad_id'],
            'ad_type':       slot_type,
            'creative_url':  best_ad.get('creative_url', ''),
            'click_url':     best_ad.get('click_url', ''),
            'width':         best_ad.get('width', 300),
            'height':        best_ad.get('height', 250),
            'bid_price':     str(best_ad.get('bid_price', 0)),
            'timestamp':     timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5,
             name='tasks.ad_unit_tasks.track_ad_impression')
def track_ad_impression(
    self,
    impression_id: str,
    ad_id: int,
    publisher_id: int,
    slot_type: str,
    country: str = '',
    device: str  = '',
) -> dict:
    """Record an ad impression. CPM-based ads pay per 1000 impressions."""
    try:
        # Increment impression counter
        counter_key = f'ad_impressions_{ad_id}'
        count       = cache.get(counter_key, 0) + 1
        cache.set(counter_key, count, timeout=86400)

        # CPM credit (if ad is CPM-type)
        try:
            from ad_units.models import AdUnit, AdImpression
            ad = AdUnit.objects.filter(pk=ad_id).first()
            if ad and ad.pricing_model == 'cpm' and count % 1000 == 0:
                cpm_payout = Decimal(str(ad.cpm_rate or 0)) / 1000
                from api.tasks.services import WalletService
                WalletService().credit(
                    user_id=publisher_id,
                    amount=cpm_payout,
                    transaction_type='cpm_impression',
                    reference=f'cpm_{ad_id}_{count}',
                )

            AdImpression.objects.create(
                impression_id=impression_id,
                ad_id=ad_id,
                publisher_id=publisher_id,
                slot_type=slot_type,
                country=country,
                device=device,
                created_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status': 'recorded',
            'impression_id': impression_id,
            'ad_id': ad_id,
            'count': count,
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5,
             name='tasks.ad_unit_tasks.track_ad_click')
def track_ad_click(
    self,
    impression_id: str,
    ad_id: int,
    publisher_id: int,
    user_id: int    = None,
    ip_address: str = '',
) -> dict:
    """
    Record an ad click and instantly credit publisher (PPC model).
    90% of CPAlead's ad units are PPC.
    """
    try:
        # Dedup: same impression can only have 1 click
        dedup_key = f'ad_click_dedup_{impression_id}'
        if cache.get(dedup_key):
            return {'status': 'duplicate_click'}
        cache.set(dedup_key, 1, timeout=3600)

        # Fraud check
        ip_key   = f'ad_click_ip_{ip_address}'
        ip_count = cache.get(ip_key, 0) + 1
        cache.set(ip_key, ip_count, timeout=3600)
        if ip_count > 50:
            logger.warning(f"[AD] Click fraud detected: IP {ip_address} {ip_count} clicks/hour")
            return {'status': 'fraud_blocked'}

        # Get PPC rate
        ppc_rate = _get_ppc_rate(ad_id)
        pub_share = ppc_rate * Decimal('0.70')   # 70% to publisher

        # Credit publisher
        if pub_share > Decimal('0'):
            try:
                from api.tasks.services import WalletService
                WalletService().credit(
                    user_id=publisher_id,
                    amount=pub_share,
                    transaction_type='ppc_click',
                    reference=f'ppc_{ad_id}_{impression_id[:8]}',
                    metadata={'ad_id': ad_id, 'impression_id': impression_id},
                )
            except ImportError:
                pass

        # Record click
        try:
            from ad_units.models import AdClick
            AdClick.objects.create(
                impression_id=impression_id,
                ad_id=ad_id,
                publisher_id=publisher_id,
                user_id=user_id,
                ip_address=ip_address,
                ppc_payout=ppc_rate,
                publisher_payout=pub_share,
                created_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status':     'success',
            'ad_id':      ad_id,
            'ppc_rate':   str(ppc_rate),
            'pub_share':  str(pub_share),
            'timestamp':  timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ad_unit_tasks.rotate_ad_creatives')
def rotate_ad_creatives(self, min_impressions: int = 1000,
                        min_ctr: float = 0.5) -> dict:
    """Pause ad creatives with CTR below threshold and rotate in alternatives."""
    try:
        logger.info(f"🔄 Rotating low-CTR ad creatives (min_ctr={min_ctr}%)")
        rotated = 0
        try:
            from ad_units.models import AdUnit, AdImpression, AdClick
            from django.db.models import Count, F

            for ad in AdUnit.objects.filter(is_active=True):
                imps   = cache.get(f'ad_impressions_{ad.pk}', 0)
                clicks = cache.get(f'ad_clicks_{ad.pk}', 0)
                if imps < min_impressions:
                    continue
                ctr = (clicks / imps * 100) if imps > 0 else 0
                if ctr < min_ctr:
                    ad.is_active     = False
                    ad.paused_reason = f'low_ctr:{ctr:.2f}%'
                    ad.save(update_fields=['is_active', 'paused_reason'])
                    rotated += 1
                    logger.info(f"[AD] Rotated ad {ad.pk}: CTR={ctr:.2f}%")
        except ImportError:
            pass
        return {'status': 'success', 'rotated': rotated, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ad_unit_tasks.update_ad_cpm_rates')
def update_ad_cpm_rates(self) -> dict:
    """Refresh geo-targeted CPC/CPM rates from the ad bidding system."""
    try:
        logger.info("💱 Updating ad rates...")
        updated = 0
        # Default PPC rates per country (US gets highest)
        geo_rates = {
            'US': Decimal('0.05'), 'GB': Decimal('0.04'), 'CA': Decimal('0.04'),
            'AU': Decimal('0.035'), 'DE': Decimal('0.03'), 'FR': Decimal('0.025'),
            'DEFAULT': Decimal('0.01'),
        }
        for country, rate in geo_rates.items():
            cache.set(f'ad_ppc_rate_{country}', str(rate), timeout=PPC_RATE_TTL)
            updated += 1
        cache.set('ad_ppc_rates', {k: str(v) for k, v in geo_rates.items()},
                  timeout=PPC_RATE_TTL)
        return {'status': 'success', 'updated': updated, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ad_unit_tasks.score_ad_quality')
def score_ad_quality(self) -> dict:
    """Score each active ad creative by CTR, fill rate, and revenue."""
    try:
        logger.info("⭐ Scoring ad quality...")
        scored = 0
        try:
            from ad_units.models import AdUnit
            for ad in AdUnit.objects.filter(is_active=True):
                imps    = cache.get(f'ad_impressions_{ad.pk}', 0)
                clicks  = cache.get(f'ad_clicks_{ad.pk}', 0)
                ctr     = (clicks / imps * 100) if imps > 0 else 0
                # Quality = min(CTR * 10, 100)
                quality = min(ctr * 10, 100)
                ad.quality_score = quality
                ad.save(update_fields=['quality_score'])
                scored += 1
        except ImportError:
            pass
        return {'status': 'success', 'scored': scored, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ad_unit_tasks.generate_ad_report')
def generate_ad_report(self, date_str: str = None) -> dict:
    """Daily ad performance report: impressions, clicks, CTR, revenue."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum
        target    = (datetime.strptime(date_str, '%Y-%m-%d').date()
                     if date_str else (timezone.now() - timedelta(days=1)).date())
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)
        report    = {'date': str(target), 'type': 'ad_daily', 'by_type': {}}
        try:
            from ad_units.models import AdImpression, AdClick
            for slot in AD_UNIT_TYPES:
                imps   = AdImpression.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end, slot_type=slot
                ).count()
                clicks = AdClick.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end,
                    impression__slot_type=slot,
                ).aggregate(cnt=Count('id'), rev=Sum('publisher_payout'))
                if imps > 0:
                    report['by_type'][slot] = {
                        'impressions': imps,
                        'clicks': clicks['cnt'] or 0,
                        'ctr': round((clicks['cnt'] or 0) / imps * 100, 2),
                        'revenue': str(clicks['rev'] or Decimal('0')),
                    }
        except ImportError:
            pass
        cache.set(f'ad_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.ad_unit_tasks.cleanup_old_impressions')
def cleanup_old_impressions(self, days_to_keep: int = 30) -> dict:
    """Delete impression logs older than retention period."""
    try:
        from datetime import timedelta
        deleted = 0
        cutoff  = timezone.now() - timedelta(days=days_to_keep)
        try:
            from ad_units.models import AdImpression
            deleted, _ = AdImpression.objects.filter(created_at__lt=cutoff).delete()
        except ImportError:
            pass
        return {'status': 'success', 'deleted': deleted, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ─────────────────────────────────────────────────────────

def _load_ads_from_db(slot_type: str, country: str, device: str) -> list:
    ads = []
    try:
        from ad_units.models import AdUnit
        qs = AdUnit.objects.filter(
            is_active=True, slot_type=slot_type
        ).values('id', 'creative_url', 'click_url', 'bid_price', 'width', 'height')[:50]
        ads = [{'ad_id': a['id'], **a} for a in qs]
        if ads:
            cache.set(f'ad_inventory_{slot_type}_{country}_{device}', ads, timeout=300)
    except ImportError:
        pass
    return ads


def _record_impression(ad_id, publisher_id, slot_type, country, device, page_url) -> str:
    import uuid
    imp_id = str(uuid.uuid4())[:16]
    cache.set(f'impression_{imp_id}', {
        'ad_id': ad_id, 'publisher_id': publisher_id,
        'slot_type': slot_type, 'country': country,
        'device': device, 'page_url': page_url,
        'created_at': timezone.now().isoformat(),
    }, timeout=3600)
    return imp_id


def _get_ppc_rate(ad_id: int) -> Decimal:
    cached = cache.get(f'ad_ppc_rate_id_{ad_id}')
    if cached:
        return Decimal(str(cached))
    try:
        from ad_units.models import AdUnit
        ad = AdUnit.objects.filter(pk=ad_id).values_list('bid_price', flat=True).first()
        if ad:
            cache.set(f'ad_ppc_rate_id_{ad_id}', str(ad), timeout=300)
            return Decimal(str(ad))
    except ImportError:
        pass
    return Decimal('0.03')   # Default $0.03/click
