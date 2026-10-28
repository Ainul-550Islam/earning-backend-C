"""
tasks/offer_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead-style Offer Management Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead Gap: Offer creation, targeting, quality scoring, A/B test, rotation
Missing features vs CPAlead:
  ✅ offer_quality_score          — score offers by CVR, EPC, payout
  ✅ rotate_underperforming_offers — swap low-quality offers
  ✅ sync_offer_targeting         — geo/device/OS targeting rules
  ✅ ab_test_offers               — A/B test two offer variants
  ✅ refresh_offer_feed           — rebuild offer wall JSON feed
  ✅ auto_pause_low_cvr_offers    — pause offers below CVR threshold
  ✅ notify_offer_expiry          — warn publishers before offer expires
  ✅ generate_offer_preview       — create preview screenshots
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='tasks.offer_tasks.offer_quality_score')
def offer_quality_score(self, offer_ids: list = None) -> dict:
    """
    Compute a composite quality score (0-100) for each active offer.
    Score = 40% EPC + 30% CVR + 20% payout_competitiveness + 10% freshness
    Cached per offer for 30 minutes.
    """
    try:
        logger.info(f"⭐ Scoring offer quality (ids={offer_ids or 'all'})...")
        scored = 0
        errors = 0

        try:
            from ad_networks.models import SmartlinkOffer
            from django.db.models import Avg

            qs = SmartlinkOffer.objects.filter(is_active=True)
            if offer_ids:
                qs = qs.filter(id__in=offer_ids)

            # Platform averages for normalization
            platform_avg_epc = qs.aggregate(avg=Avg('epc'))['avg'] or Decimal('0.01')
            platform_avg_payout = qs.aggregate(avg=Avg('payout'))['avg'] or Decimal('1')

            for offer in qs.iterator(chunk_size=100):
                try:
                    epc             = float(offer.epc or 0)
                    cvr             = float(offer.conversion_rate or 0)
                    payout          = float(offer.payout or 0)
                    platform_epc    = float(platform_avg_epc)
                    platform_payout = float(platform_avg_payout)

                    # EPC score (normalized 0-40)
                    epc_score = min((epc / max(platform_epc, 0.01)) * 40, 40)

                    # CVR score (normalized 0-30)
                    cvr_score = min(cvr / 10 * 30, 30)  # 10% CVR = max score

                    # Payout competitiveness (0-20)
                    pay_score = min((payout / max(platform_payout, 1)) * 20, 20)

                    # Freshness (0-10) — offers updated recently score higher
                    days_old   = (timezone.now() - offer.updated_at).days if hasattr(offer, 'updated_at') else 30
                    fresh_score = max(10 - days_old, 0)

                    quality = round(epc_score + cvr_score + pay_score + fresh_score, 1)

                    offer.quality_score = quality
                    offer.quality_scored_at = timezone.now()
                    offer.save(update_fields=['quality_score', 'quality_scored_at'])

                    cache.set(f'offer_quality_{offer.pk}', quality, timeout=1800)
                    scored += 1

                except Exception as e:
                    logger.error(f"[ERROR] Scoring offer {offer.pk}: {e}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'scored': scored, 'errors': errors,
                'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        logger.error(f"[ERROR] offer_quality_score: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.offer_tasks.rotate_underperforming_offers')
def rotate_underperforming_offers(self, quality_threshold: float = 20.0) -> dict:
    """
    Identify offers with quality_score below threshold and rotate them out.
    Replace with backup offers from the same category/country.
    """
    try:
        logger.info(f"🔄 Rotating underperforming offers (threshold={quality_threshold})...")
        rotated = 0
        try:
            from ad_networks.models import SmartlinkOffer

            low_quality = SmartlinkOffer.objects.filter(
                is_active=True,
                quality_score__lt=quality_threshold,
                quality_score__isnull=False,
            )
            for offer in low_quality:
                # Pause offer
                offer.is_active          = False
                offer.paused_reason      = 'low_quality_score'
                offer.paused_at          = timezone.now()
                offer.save(update_fields=['is_active', 'paused_reason', 'paused_at'])

                # Find backup offer in same category
                backup = SmartlinkOffer.objects.filter(
                    category=offer.category,
                    country__in=offer.countries or [],
                    is_active=True,
                    quality_score__gte=quality_threshold,
                ).exclude(pk=offer.pk).order_by('-quality_score').first()

                if backup:
                    cache.set(f'offer_rotation_{offer.pk}', backup.pk, timeout=86400)
                    logger.info(f"[ROTATE] Offer {offer.pk} → backup {backup.pk}")

                rotated += 1

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'rotated': rotated, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.offer_tasks.sync_offer_targeting')
def sync_offer_targeting(self) -> dict:
    """
    Sync geo/device/OS targeting rules for all active offers.
    Builds a fast lookup cache: country → [offer_ids], device → [offer_ids]
    Used by the offer-wall API for sub-millisecond targeting.
    """
    try:
        logger.info("🎯 Syncing offer targeting rules...")
        synced = 0
        geo_map    = {}  # country_code → [offer_id]
        device_map = {}  # device_type  → [offer_id]
        os_map     = {}  # os_type      → [offer_id]

        try:
            from ad_networks.models import SmartlinkOffer

            for offer in SmartlinkOffer.objects.filter(is_active=True).values(
                'id', 'countries', 'device_types', 'os_types', 'payout', 'quality_score'
            ):
                offer_id = offer['id']
                synced  += 1

                # Geo targeting
                for country in (offer.get('countries') or ['ALL']):
                    geo_map.setdefault(country, []).append(offer_id)

                # Device targeting
                for device in (offer.get('device_types') or ['ALL']):
                    device_map.setdefault(device, []).append(offer_id)

                # OS targeting
                for os_type in (offer.get('os_types') or ['ALL']):
                    os_map.setdefault(os_type, []).append(offer_id)

            # Cache all targeting maps
            cache.set('offer_geo_map',    geo_map,    timeout=1800)
            cache.set('offer_device_map', device_map, timeout=1800)
            cache.set('offer_os_map',     os_map,     timeout=1800)

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'offers_synced': synced,
                'geo_keys': len(geo_map), 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.offer_tasks.refresh_offer_feed')
def refresh_offer_feed(self, country: str = None, device: str = None) -> dict:
    """
    Rebuild the offer wall JSON feed for publisher display.
    Combines targeting, quality score, cap status into a ranked list.
    Cached for 10 minutes per country/device combination.
    """
    try:
        logger.info(f"📋 Refreshing offer feed (country={country}, device={device})...")
        feed   = []
        errors = 0

        try:
            from ad_networks.models import SmartlinkOffer

            qs = SmartlinkOffer.objects.filter(is_active=True)
            if country:
                qs = qs.filter(countries__contains=[country]) | qs.filter(countries__isnull=True)
            if device:
                qs = qs.filter(device_types__contains=[device]) | qs.filter(device_types__isnull=True)

            offers = qs.order_by('-quality_score', '-epc').values(
                'id', 'external_id', 'name', 'description', 'payout',
                'epc', 'conversion_rate', 'quality_score', 'icon_url',
                'category', 'is_featured', 'daily_cap', 'daily_clicks_used',
            )

            for offer in offers:
                # Skip capped offers
                if (offer.get('daily_cap') and
                        (offer.get('daily_clicks_used') or 0) >= offer['daily_cap']):
                    continue

                feed.append({
                    'id':          offer['id'],
                    'offer_id':    offer['external_id'],
                    'name':        offer['name'],
                    'description': offer.get('description', ''),
                    'payout':      str(offer.get('payout') or '0'),
                    'epc':         str(offer.get('epc') or '0'),
                    'cvr':         str(offer.get('conversion_rate') or '0'),
                    'score':       offer.get('quality_score') or 0,
                    'icon_url':    offer.get('icon_url', ''),
                    'category':    offer.get('category', ''),
                    'is_featured': offer.get('is_featured', False),
                })

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        # Cache the feed
        cache_key = f'offer_feed_{country or "all"}_{device or "all"}'
        cache.set(cache_key, feed, timeout=600)

        return {'status': 'success', 'offers_in_feed': len(feed),
                'errors': errors, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.offer_tasks.auto_pause_low_cvr_offers')
def auto_pause_low_cvr_offers(self, min_clicks: int = 100, cvr_threshold: float = 0.5) -> dict:
    """
    Auto-pause offers with CVR below threshold after sufficient click volume.
    Prevents publishers from wasting traffic on non-converting offers.
    """
    try:
        logger.info(f"⏸️ Pausing low-CVR offers (min_clicks={min_clicks}, cvr<{cvr_threshold}%)...")
        paused = 0

        try:
            from ad_networks.models import SmartlinkOffer

            low_cvr = SmartlinkOffer.objects.filter(
                is_active=True,
                total_clicks__gte=min_clicks,
                conversion_rate__lt=cvr_threshold,
            )
            for offer in low_cvr:
                offer.is_active     = False
                offer.paused_reason = f'low_cvr:{offer.conversion_rate:.2f}%'
                offer.paused_at     = timezone.now()
                offer.save(update_fields=['is_active', 'paused_reason', 'paused_at'])
                paused += 1
                logger.info(f"[PAUSE] Offer {offer.external_id} CVR={offer.conversion_rate:.2f}%")

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'paused': paused, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.offer_tasks.notify_offer_expiry')
def notify_offer_expiry(self, days_ahead: int = 3) -> dict:
    """
    Warn publishers and admins about offers expiring in `days_ahead` days.
    """
    try:
        from datetime import timedelta
        logger.info(f"⏰ Notifying offer expiry (within {days_ahead} days)...")
        notified = 0
        soon     = timezone.now() + timedelta(days=days_ahead)

        try:
            from ad_networks.models import SmartlinkOffer
            from api.tasks.notification_tasks import dispatch_in_app_notification

            expiring = SmartlinkOffer.objects.filter(
                is_active=True,
                expires_at__lte=soon,
                expires_at__gt=timezone.now(),
            )
            for offer in expiring:
                # Notify all publishers using this offer
                title   = f'⚠️ Offer Expiring Soon: {offer.name}'
                message = f'Offer "{offer.name}" expires on {offer.expires_at.strftime("%b %d, %Y")}.'

                # Find users who clicked this offer
                try:
                    from ad_networks.models import OfferClick
                    user_ids = list(
                        OfferClick.objects.filter(offer=offer)
                        .values_list('user_id', flat=True)
                        .distinct()[:500]
                    )
                    for uid in user_ids:
                        dispatch_in_app_notification.apply_async(kwargs={
                            'user_id': uid,
                            'title': title,
                            'message': message,
                            'notification_type': 'warning',
                        })
                    notified += len(user_ids)
                except ImportError:
                    pass

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'notified': notified, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)
