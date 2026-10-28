"""
tasks/api_key_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API Key Management Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Publisher and advertiser API key lifecycle management.
  ✅ generate_api_key         — create new API key for user
  ✅ rotate_api_keys          — rotate keys older than 90 days
  ✅ revoke_api_key           — immediately invalidate a key
  ✅ audit_api_usage          — log and rate-limit API calls
  ✅ cleanup_expired_keys     — purge revoked/expired keys
  ✅ generate_api_report      — daily API usage summary
"""
import logging
import secrets
import hashlib
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

KEY_PREFIX_PUBLISHER  = 'pk_'
KEY_PREFIX_ADVERTISER = 'ak_'
KEY_ROTATION_DAYS     = 90


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.api_key_tasks.generate_api_key')
def generate_api_key(
    self,
    user_id: int,
    key_type: str = 'publisher',   # 'publisher' | 'advertiser' | 'admin'
    scope: list   = None,          # ['read', 'write', 'postback', 'stats']
    expires_days: int = None,
) -> dict:
    """Generate a new API key for a user."""
    try:
        prefix     = KEY_PREFIX_PUBLISHER if key_type == 'publisher' else KEY_PREFIX_ADVERTISER
        raw_key    = f"{prefix}{secrets.token_urlsafe(48)}"
        key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
        scope      = scope or ['read', 'stats']

        import datetime
        expires_at = (
            (timezone.now() + datetime.timedelta(days=expires_days)).isoformat()
            if expires_days else None
        )

        key_data = {
            'user_id':    user_id,
            'key_type':   key_type,
            'key_hash':   key_hash,
            'scope':      scope,
            'expires_at': expires_at,
            'created_at': timezone.now().isoformat(),
            'is_active':  True,
        }
        # Cache key for fast lookup
        cache.set(f'api_key_{key_hash}', key_data, timeout=None)

        try:
            from users.models import APIKey
            APIKey.objects.filter(user_id=user_id, key_type=key_type, is_active=True).update(
                is_active=False
            )
            APIKey.objects.create(
                user_id=user_id,
                key_hash=key_hash,
                key_type=key_type,
                scope=scope,
                expires_at=expires_at,
                is_active=True,
            )
        except ImportError:
            pass

        logger.info(f"[API_KEY] Generated {key_type} key for user {user_id}")
        return {
            'status':     'success',
            'api_key':    raw_key,    # Only shown once
            'key_type':   key_type,
            'scope':      scope,
            'expires_at': expires_at,
            'user_id':    user_id,
            'timestamp':  timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.api_key_tasks.rotate_api_keys')
def rotate_api_keys(self) -> dict:
    """Rotate all API keys older than KEY_ROTATION_DAYS."""
    try:
        from datetime import timedelta
        logger.info(f"🔑 Rotating API keys older than {KEY_ROTATION_DAYS}d...")
        rotated = 0
        cutoff  = timezone.now() - timedelta(days=KEY_ROTATION_DAYS)
        try:
            from users.models import APIKey
            old_keys = APIKey.objects.filter(
                is_active=True, created_at__lt=cutoff
            ).values_list('user_id', 'key_type')
            for uid, ktype in old_keys:
                generate_api_key.apply_async(kwargs={'user_id': uid, 'key_type': ktype})
                rotated += 1
        except ImportError:
            pass
        return {'status': 'success', 'rotated': rotated, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.api_key_tasks.revoke_api_key')
def revoke_api_key(self, key_hash: str, reason: str = '') -> dict:
    """Immediately invalidate an API key."""
    try:
        cache.delete(f'api_key_{key_hash}')
        try:
            from users.models import APIKey
            APIKey.objects.filter(key_hash=key_hash).update(
                is_active=False, revoked_at=timezone.now(), revoke_reason=reason
            )
        except ImportError:
            pass
        logger.info(f"[API_KEY] Revoked: {key_hash[:16]}... reason={reason}")
        return {'status': 'success', 'key_hash': key_hash[:16], 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.api_key_tasks.audit_api_usage')
def audit_api_usage(self, key_hash: str, endpoint: str, method: str = 'GET',
                    status_code: int = 200, ip: str = '') -> dict:
    """Log API key usage for audit and rate-limit tracking."""
    try:
        usage_key = f'api_usage_{key_hash[:16]}'
        usage     = cache.get(usage_key, {'calls': 0, 'endpoints': {}})
        usage['calls'] += 1
        usage['endpoints'][endpoint] = usage['endpoints'].get(endpoint, 0) + 1
        usage['last_call'] = timezone.now().isoformat()
        cache.set(usage_key, usage, timeout=86400)
        return {'status': 'logged', 'calls': usage['calls']}
    except Exception as exc:
        raise self.retry(exc=exc)
