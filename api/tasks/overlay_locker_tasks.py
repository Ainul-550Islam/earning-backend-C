"""
tasks/overlay_locker_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overlay Locker Mode Tasks (CPAlead Exclusive Feature)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead's Overlay Locker Mode lets publishers:
  • Lock content with a timed-access model
  • 24h access: user completes one offer → unlocked for 24 hours
  • 720h access: one offer → unlocked for 30 days
  • 0h (zero): must complete every time (reward-based)
  • Postback integration to track unlock events

  ✅ create_overlay_session      — create timed access after offer completion
  ✅ check_overlay_access        — verify user still has active access
  ✅ expire_overlay_sessions     — purge expired sessions
  ✅ revoke_overlay_access       — admin-triggered access revocation
  ✅ track_overlay_stats         — track views, unlocks, revenue
  ✅ generate_overlay_report     — daily overlay locker analytics
"""
import logging
import secrets
import hashlib
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Access duration options (hours)
OVERLAY_MODES = {
    '24h':  24,
    '720h': 720,
    '0h':   0,      # Every-time (postback required each visit)
}
OVERLAY_PREFIX = 'overlay_access_'


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.overlay_locker_tasks.create_overlay_session')
def create_overlay_session(
    self,
    locker_id: str,
    user_id: int,
    offer_completion_id: str,
    access_mode: str = '24h',   # '24h' | '720h' | '0h'
    publisher_id: int = None,
    ip_address: str = '',
) -> dict:
    """
    Grant timed content access after a user completes the required offer.

    Flow:
    1. Verify offer completion is genuine
    2. Check for duplicate grant (same locker + user + mode)
    3. Create access session with expiry timestamp
    4. Credit publisher for the unlock event
    5. Return signed access token

    access_mode:
        '24h'  → 24-hour access window (recommended)
        '720h' → 30-day (720-hour) access window
        '0h'   → No caching; user must re-complete every visit
    """
    try:
        hours      = OVERLAY_MODES.get(access_mode, 24)
        access_key = f"{OVERLAY_PREFIX}{locker_id}_{user_id}"

        # Check existing valid session (skip for 0h mode)
        if hours > 0:
            existing = cache.get(access_key)
            if existing and existing.get('valid'):
                return {
                    'status': 'already_active',
                    'access_token': existing['token'],
                    'expires_at':   existing['expires_at'],
                    'locker_id':    locker_id,
                    'user_id':      user_id,
                }

        # Verify offer completion
        completion_valid = _verify_completion(offer_completion_id, user_id)
        if not completion_valid:
            return {
                'status': 'invalid_completion',
                'error':  'Offer completion not verified or already used',
            }

        # Generate signed access token
        raw_token    = secrets.token_urlsafe(32)
        token_hash   = hashlib.sha256(
            f"{raw_token}:{locker_id}:{user_id}".encode()
        ).hexdigest()

        expires_at   = None
        ttl_seconds  = None
        if hours > 0:
            import datetime
            expires_at  = (timezone.now() + datetime.timedelta(hours=hours)).isoformat()
            ttl_seconds = hours * 3600

        session_data = {
            'locker_id':    locker_id,
            'user_id':      user_id,
            'access_mode':  access_mode,
            'token':        raw_token,
            'token_hash':   token_hash,
            'expires_at':   expires_at,
            'ip_address':   ip_address,
            'granted_at':   timezone.now().isoformat(),
            'valid':        True,
        }

        if hours > 0:
            cache.set(access_key, session_data, timeout=ttl_seconds)
            # Also index by token for validation
            cache.set(f'{OVERLAY_PREFIX}token_{token_hash}', session_data, timeout=ttl_seconds)

        # Persist to DB
        try:
            from content_lockers.models import OverlaySession
            OverlaySession.objects.create(
                locker_id=locker_id,
                user_id=user_id,
                publisher_id=publisher_id,
                offer_completion_id=offer_completion_id,
                access_mode=access_mode,
                token_hash=token_hash,
                expires_at=expires_at,
                ip_address=ip_address,
            )
        except ImportError:
            pass

        # Credit publisher for unlock
        _credit_publisher_unlock(locker_id, publisher_id, access_mode)

        # Track unlock event
        track_overlay_stats.apply_async(kwargs={
            'locker_id':   locker_id,
            'event_type':  'unlock',
            'access_mode': access_mode,
        })

        logger.info(
            f"[OVERLAY] Session created: locker={locker_id} user={user_id} "
            f"mode={access_mode} expires={expires_at}"
        )
        return {
            'status':        'success',
            'access_token':  raw_token,
            'access_mode':   access_mode,
            'expires_at':    expires_at,
            'hours':         hours,
            'locker_id':     locker_id,
            'user_id':       user_id,
            'timestamp':     timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] create_overlay_session: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=5,
             name='tasks.overlay_locker_tasks.check_overlay_access')
def check_overlay_access(
    self,
    locker_id: str,
    user_id: int,
    access_token: str = '',
) -> dict:
    """
    Check whether a user currently has valid overlay access to a locker.
    Called on every page load to gate content.

    Returns:
        {has_access: True/False, expires_at: ..., reason: ...}
    """
    try:
        access_key = f"{OVERLAY_PREFIX}{locker_id}_{user_id}"
        session    = cache.get(access_key)

        if not session:
            # Try DB fallback
            try:
                from content_lockers.models import OverlaySession
                db_session = OverlaySession.objects.filter(
                    locker_id=locker_id,
                    user_id=user_id,
                    is_revoked=False,
                ).order_by('-created_at').first()

                if db_session and db_session.is_valid:
                    # Re-warm cache
                    session_data = {
                        'locker_id':   locker_id,
                        'user_id':     user_id,
                        'access_mode': db_session.access_mode,
                        'expires_at':  db_session.expires_at.isoformat() if db_session.expires_at else None,
                        'valid':       True,
                    }
                    remaining_ttl = max(
                        int((db_session.expires_at - timezone.now()).total_seconds()),
                        1
                    ) if db_session.expires_at else 3600
                    cache.set(access_key, session_data, timeout=remaining_ttl)
                    session = session_data
            except ImportError:
                pass

        if not session:
            track_overlay_stats.apply_async(kwargs={
                'locker_id': locker_id, 'event_type': 'access_denied'
            })
            return {
                'has_access':  False,
                'locker_id':   locker_id,
                'user_id':     user_id,
                'reason':      'no_active_session',
                'timestamp':   timezone.now().isoformat(),
            }

        # Validate token if provided
        if access_token:
            expected_hash = hashlib.sha256(
                f"{access_token}:{locker_id}:{user_id}".encode()
            ).hexdigest()
            if session.get('token_hash') and session['token_hash'] != expected_hash:
                return {
                    'has_access': False,
                    'reason':     'invalid_token',
                }

        track_overlay_stats.apply_async(kwargs={
            'locker_id': locker_id, 'event_type': 'access_granted'
        })
        return {
            'has_access':  True,
            'locker_id':   locker_id,
            'user_id':     user_id,
            'access_mode': session.get('access_mode'),
            'expires_at':  session.get('expires_at'),
            'timestamp':   timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.overlay_locker_tasks.expire_overlay_sessions')
def expire_overlay_sessions(self) -> dict:
    """
    Purge expired overlay sessions from DB.
    Cache entries auto-expire via Redis TTL — only DB cleanup needed.
    """
    try:
        logger.info("🧹 Expiring overlay sessions...")
        expired = 0
        try:
            from content_lockers.models import OverlaySession
            n, _ = OverlaySession.objects.filter(
                expires_at__lt=timezone.now(),
                is_revoked=False,
            ).update(is_revoked=True)
            expired = n
        except ImportError:
            pass

        return {
            'status':    'success',
            'expired':   expired,
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.overlay_locker_tasks.revoke_overlay_access')
def revoke_overlay_access(
    self,
    locker_id: str,
    user_id: int,
    reason: str = 'admin_revoked',
) -> dict:
    """Admin-triggered: immediately revoke a user's overlay access."""
    try:
        access_key = f"{OVERLAY_PREFIX}{locker_id}_{user_id}"
        cache.delete(access_key)

        try:
            from content_lockers.models import OverlaySession
            OverlaySession.objects.filter(
                locker_id=locker_id, user_id=user_id
            ).update(is_revoked=True, revoke_reason=reason, revoked_at=timezone.now())
        except ImportError:
            pass

        logger.info(f"[OVERLAY] Access revoked: locker={locker_id} user={user_id} reason={reason}")
        return {
            'status':    'success',
            'locker_id': locker_id,
            'user_id':   user_id,
            'reason':    reason,
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.overlay_locker_tasks.track_overlay_stats')
def track_overlay_stats(
    self,
    locker_id: str,
    event_type: str = 'view',
    access_mode: str = '24h',
) -> dict:
    """Track overlay locker events in cache for real-time analytics."""
    try:
        stats_key = f'overlay_stats_{locker_id}'
        stats     = cache.get(stats_key) or {
            'views': 0, 'unlocks': 0, 'access_granted': 0,
            'access_denied': 0, 'revenue': '0',
        }
        if event_type in stats:
            stats[event_type] = stats.get(event_type, 0) + 1
        stats['last_updated'] = timezone.now().isoformat()
        cache.set(stats_key, stats, timeout=86400)
        return {'status': 'success', 'event': event_type, 'locker_id': locker_id}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.overlay_locker_tasks.generate_overlay_report')
def generate_overlay_report(self, date_str: str = None) -> dict:
    """Daily overlay locker performance report."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Avg

        target    = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)
        report    = {'date': str(target), 'type': 'overlay_daily', 'by_mode': {}}

        try:
            from content_lockers.models import OverlaySession
            for mode in ['24h', '720h', '0h']:
                agg = OverlaySession.objects.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end,
                    access_mode=mode,
                ).aggregate(cnt=Count('id'))
                report['by_mode'][mode] = {'unlocks': agg['cnt'] or 0}
        except ImportError:
            pass

        cache.set(f'overlay_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ─────────────────────────────────────────────────────────

def _verify_completion(completion_id: str, user_id: int) -> bool:
    if not completion_id:
        return False
    dedup_key = f'overlay_completion_used_{completion_id}'
    if cache.get(dedup_key):
        return False
    try:
        from ad_networks.models import OfferConversion
        conv = OfferConversion.objects.filter(
            transaction_id=completion_id,
            user_id=user_id,
            status='approved',
        ).first()
        if conv:
            cache.set(dedup_key, 1, timeout=86400 * 7)
            return True
    except ImportError:
        pass
    # Fallback: accept if cached as valid
    if cache.get(f'completion_valid_{completion_id}') == str(user_id):
        cache.set(dedup_key, 1, timeout=86400 * 7)
        return True
    return False


def _credit_publisher_unlock(locker_id: str, publisher_id: int, access_mode: str) -> None:
    """Credit publisher for a successful overlay unlock event."""
    if not publisher_id:
        return
    payout_map = {'24h': Decimal('0.10'), '720h': Decimal('0.25'), '0h': Decimal('0.05')}
    payout     = payout_map.get(access_mode, Decimal('0.10'))
    try:
        from api.tasks.services import WalletService
        WalletService().credit(
            user_id=publisher_id,
            amount=payout,
            transaction_type='overlay_unlock',
            reference=f'overlay_{locker_id}_{int(timezone.now().timestamp())}',
        )
    except ImportError:
        pass
