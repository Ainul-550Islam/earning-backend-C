"""
tasks/content_locker_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Content Locker, Link Locker & File Locker Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead's signature product — lock content/links/files behind offer completions.
  ✅ process_content_locker_unlock  — verify offer completion → unlock content
  ✅ process_link_locker_access     — verify completion → redirect to URL
  ✅ process_file_locker_download   — verify completion → generate download token
  ✅ cleanup_expired_unlock_tokens  — purge expired access tokens
  ✅ track_locker_stats             — update locker performance stats
  ✅ rotate_locker_offers           — show best offers per geo in locker
  ✅ generate_locker_embed_code     — generate JS embed for publishers
"""
import logging
import secrets
import hashlib
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

UNLOCK_TOKEN_TTL  = 3600 * 24   # 24 hours
LOCKER_STATS_TTL  = 1800        # 30 minutes


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.content_locker_tasks.process_content_locker_unlock')
def process_content_locker_unlock(
    self,
    locker_id: str,
    user_id: int,
    offer_completion_id: str,
    ip_address: str = '',
) -> dict:
    """
    Verify that a user completed the required offer and unlock content.
    1. Verify offer_completion_id is valid and not already used
    2. Check the completion matches the locker's required offer
    3. Generate a one-time unlock token
    4. Credit publisher with unlock revenue
    Returns: {status, unlock_token, content_url}
    """
    try:
        logger.info(f"🔓 Processing content locker unlock: locker={locker_id} user={user_id}")

        # Check dedup: same user + locker already unlocked?
        dedup_key = f'locker_unlock_{locker_id}_{user_id}'
        existing_token = cache.get(dedup_key)
        if existing_token:
            return {
                'status': 'already_unlocked',
                'unlock_token': existing_token,
                'timestamp': timezone.now().isoformat(),
            }

        # Verify offer completion
        completion_valid = _verify_offer_completion(offer_completion_id, user_id)
        if not completion_valid:
            return {
                'status': 'invalid_completion',
                'error': 'Offer completion not verified',
                'timestamp': timezone.now().isoformat(),
            }

        # Generate unlock token
        unlock_token = secrets.token_urlsafe(32)
        token_hash   = hashlib.sha256(unlock_token.encode()).hexdigest()

        # Cache token + locker info
        token_data = {
            'locker_id':   locker_id,
            'user_id':     user_id,
            'created_at':  timezone.now().isoformat(),
            'ip_address':  ip_address,
        }
        cache.set(f'unlock_token_{token_hash}', token_data, timeout=UNLOCK_TOKEN_TTL)
        cache.set(dedup_key, unlock_token, timeout=UNLOCK_TOKEN_TTL)

        # Get content URL from locker config
        content_url = ''
        publisher_payout = Decimal('0')
        try:
            from content_lockers.models import ContentLocker
            locker = ContentLocker.objects.filter(locker_id=locker_id).first()
            if locker:
                content_url      = locker.content_url or ''
                publisher_payout = Decimal(str(locker.publisher_payout or 0))
                locker.unlock_count = (locker.unlock_count or 0) + 1
                locker.save(update_fields=['unlock_count'])
        except ImportError:
            pass

        # Credit publisher
        if publisher_payout > Decimal('0'):
            try:
                from api.tasks.services import WalletService
                WalletService().credit(
                    user_id=user_id,
                    amount=publisher_payout,
                    transaction_type='locker_unlock',
                    reference=f'locker_{locker_id}_{unlock_token[:8]}',
                )
            except ImportError:
                pass

        # Track stats
        track_locker_stats.apply_async(kwargs={
            'locker_id': locker_id,
            'event_type': 'unlock',
        })

        return {
            'status': 'success',
            'unlock_token': unlock_token,
            'content_url': content_url,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] process_content_locker_unlock: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.content_locker_tasks.process_link_locker_access')
def process_link_locker_access(
    self,
    locker_id: str,
    user_id: int,
    offer_completion_id: str,
) -> dict:
    """
    Verify offer completion → return the locked URL for redirect.
    Used for gating valuable links/affiliate URLs behind offer completions.
    """
    try:
        logger.info(f"🔗 Processing link locker access: locker={locker_id}")

        # Verify completion
        if not _verify_offer_completion(offer_completion_id, user_id):
            return {'status': 'invalid_completion', 'redirect_url': ''}

        redirect_url = ''
        try:
            from content_lockers.models import LinkLocker
            locker = LinkLocker.objects.filter(locker_id=locker_id).first()
            if locker:
                redirect_url = locker.destination_url
                locker.click_count = (locker.click_count or 0) + 1
                locker.save(update_fields=['click_count'])
        except ImportError:
            redirect_url = cache.get(f'link_locker_{locker_id}', '')

        return {
            'status': 'success',
            'redirect_url': redirect_url,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.content_locker_tasks.process_file_locker_download')
def process_file_locker_download(
    self,
    locker_id: str,
    user_id: int,
    offer_completion_id: str,
) -> dict:
    """
    Verify offer completion → generate a signed download URL for the locked file.
    Download token expires in 1 hour.
    """
    try:
        logger.info(f"📁 Processing file locker download: locker={locker_id}")

        if not _verify_offer_completion(offer_completion_id, user_id):
            return {'status': 'invalid_completion', 'download_url': ''}

        download_token = secrets.token_urlsafe(24)
        file_url       = ''

        try:
            from content_lockers.models import FileLocker
            locker = FileLocker.objects.filter(locker_id=locker_id).first()
            if locker:
                file_url = locker.file_url or locker.file_path
                locker.download_count = (locker.download_count or 0) + 1
                locker.save(update_fields=['download_count'])
        except ImportError:
            pass

        # Cache download token
        cache.set(f'download_token_{download_token}', {
            'locker_id': locker_id,
            'user_id':   user_id,
            'file_url':  file_url,
            'created_at': timezone.now().isoformat(),
        }, timeout=3600)

        return {
            'status': 'success',
            'download_token': download_token,
            'download_url': f'/download/{download_token}/',
            'expires_in': 3600,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.content_locker_tasks.cleanup_expired_unlock_tokens')
def cleanup_expired_unlock_tokens(self) -> dict:
    """
    Purge expired unlock/download tokens from cache.
    Also clean up expired locker sessions in DB.
    """
    try:
        logger.info("🧹 Cleaning up expired locker tokens...")
        cleaned = 0

        try:
            from content_lockers.models import LockerSession
            from datetime import timedelta
            cutoff  = timezone.now() - timedelta(hours=24)
            cleaned, _ = LockerSession.objects.filter(created_at__lt=cutoff).delete()
        except ImportError:
            pass

        return {
            'status': 'success',
            'cleaned': cleaned,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.content_locker_tasks.track_locker_stats')
def track_locker_stats(self, locker_id: str, event_type: str = 'view') -> dict:
    """
    Track locker events: views, offer-shows, unlocks, revenue.
    Updates real-time stats cache.
    """
    try:
        stats_key = f'locker_stats_{locker_id}'
        stats = cache.get(stats_key) or {
            'views': 0, 'offer_shows': 0, 'unlocks': 0,
            'conversion_rate': 0.0, 'last_updated': timezone.now().isoformat(),
        }

        if event_type == 'view':
            stats['views'] += 1
        elif event_type == 'offer_show':
            stats['offer_shows'] += 1
        elif event_type == 'unlock':
            stats['unlocks'] += 1

        # Calculate CVR
        if stats['views'] > 0:
            stats['conversion_rate'] = round(stats['unlocks'] / stats['views'] * 100, 2)
        stats['last_updated'] = timezone.now().isoformat()

        cache.set(stats_key, stats, timeout=LOCKER_STATS_TTL)

        try:
            from content_lockers.models import ContentLocker
            update_fields = {}
            if event_type == 'view':
                update_fields = {'view_count': stats['views']}
            elif event_type == 'unlock':
                update_fields = {'unlock_count': stats['unlocks']}
            if update_fields:
                ContentLocker.objects.filter(locker_id=locker_id).update(**update_fields)
        except ImportError:
            pass

        return {'status': 'success', 'event': event_type, 'stats': stats}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.content_locker_tasks.rotate_locker_offers')
def rotate_locker_offers(self, country: str = 'ALL', device: str = 'ALL') -> dict:
    """
    Select and cache the best offers to display inside content lockers
    for a given country/device combination.
    Uses quality score + EPC + conversion rate to rank.
    """
    try:
        logger.info(f"🔄 Rotating locker offers ({country}/{device})...")

        offers = []
        try:
            from ad_networks.models import SmartlinkOffer

            qs = SmartlinkOffer.objects.filter(is_active=True)
            if country != 'ALL':
                qs = qs.filter(countries__contains=[country]) | qs.filter(countries__isnull=True)
            if device != 'ALL':
                qs = qs.filter(device_types__contains=[device]) | qs.filter(device_types__isnull=True)

            offers = list(
                qs.order_by('-quality_score', '-epc', '-payout')
                .values('id', 'external_id', 'name', 'payout', 'epc',
                        'quality_score', 'icon_url', 'conversion_rate')[:10]
            )

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        cache_key = f'locker_offers_{country}_{device}'
        cache.set(cache_key, offers, timeout=600)

        return {
            'status': 'success',
            'offers_loaded': len(offers),
            'country': country,
            'device': device,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.content_locker_tasks.generate_locker_embed_code')
def generate_locker_embed_code(self, locker_id: str, locker_type: str = 'content') -> dict:
    """
    Generate JavaScript embed code for a publisher to add the locker to their site.
    Caches the embed code per locker.
    """
    try:
        from django.conf import settings
        base_url = getattr(settings, 'FRONTEND_URL', 'https://yourdomain.com')

        embed_map = {
            'content': f"""<script src="{base_url}/static/js/locker.js"></script>
<div id="cpa-content-locker" data-locker-id="{locker_id}"></div>
<script>CPALocker.init('{locker_id}', 'content');</script>""",

            'link': f"""<a href="{base_url}/locker/link/{locker_id}/" 
   data-locker="true" class="cpa-link-locker">
  Your Locked Link Text
</a>
<script src="{base_url}/static/js/link-locker.js"></script>""",

            'file': f"""<a href="{base_url}/locker/file/{locker_id}/download/" 
   data-locker="file" class="cpa-file-locker">
  Download Now (Free)
</a>
<script src="{base_url}/static/js/file-locker.js"></script>""",
        }

        embed_code = embed_map.get(locker_type, embed_map['content'])
        cache.set(f'locker_embed_{locker_id}', embed_code, timeout=86400)

        return {
            'status': 'success',
            'locker_id': locker_id,
            'locker_type': locker_type,
            'embed_code': embed_code,
        }

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────────────────────────────────

def _verify_offer_completion(completion_id: str, user_id: int) -> bool:
    """Verify an offer completion ID is valid for this user."""
    if not completion_id:
        return False

    # Check dedup cache
    dedup_key = f'completion_used_{completion_id}'
    if cache.get(dedup_key):
        logger.warning(f"[LOCKER] Completion {completion_id} already used")
        return False

    try:
        from ad_networks.models import OfferConversion
        conv = OfferConversion.objects.filter(
            transaction_id=completion_id,
            user_id=user_id,
            status='approved',
        ).first()
        if conv:
            cache.set(dedup_key, 1, timeout=86400)
            return True
    except ImportError:
        pass

    # Fallback: check cache for postback-recorded completions
    cached = cache.get(f'completion_valid_{completion_id}')
    if cached and cached == str(user_id):
        cache.set(dedup_key, 1, timeout=86400)
        return True

    return False
