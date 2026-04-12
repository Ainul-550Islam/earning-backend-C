"""
api/users/auth/api_key_manager.py
API Key generation, validation, rotation
Developer-দের জন্য programmatic access
"""
import hashlib
import secrets
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..constants import AuthConstants, CacheKeys
from ..cache import user_cache
from ..exceptions import InvalidAPIKeyException

logger = logging.getLogger(__name__)
User   = get_user_model()


# ─────────────────────────────────────────
# MODEL (models.py-তে এই model যোগ করো)
# ─────────────────────────────────────────
# class UserAPIKey(models.Model):
#     user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
#     name        = models.CharField(max_length=100)           # "My App Key"
#     key_prefix  = models.CharField(max_length=10)            # "ek_abc123" (show করা যাবে)
#     key_hash    = models.CharField(max_length=64, unique=True)  # sha256 (store করা হয়)
#     scopes      = models.JSONField(default=list)             # ['read', 'write']
#     is_active   = models.BooleanField(default=True)
#     last_used_at= models.DateTimeField(null=True, blank=True)
#     expires_at  = models.DateTimeField(null=True, blank=True)
#     created_at  = models.DateTimeField(auto_now_add=True)


class APIKeyManager:

    PREFIX = AuthConstants.API_KEY_PREFIX   # 'ek_'
    LENGTH = AuthConstants.API_KEY_LENGTH   # 48

    # ─────────────────────────────────────
    # GENERATE
    # ─────────────────────────────────────
    def generate(self, user, name: str, scopes: list = None, expires_days: int = None) -> dict:
        """
        নতুন API key তৈরি করো।
        Returns: raw key (একবারই দেখাবে), prefix, hash
        """
        raw_key    = f"{self.PREFIX}{secrets.token_urlsafe(self.LENGTH)}"
        key_hash   = self._hash(raw_key)
        key_prefix = raw_key[:10]   # প্রথম ১০ char দেখাবে (e.g. ek_AbCdEf12)

        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timezone.timedelta(days=expires_days)

        # DB-তে save করো
        from django.apps import apps
        try:
            APIKey = apps.get_model('users', 'UserAPIKey')
            api_key_obj = APIKey.objects.create(
                user       = user,
                name       = name,
                key_prefix = key_prefix,
                key_hash   = key_hash,
                scopes     = scopes or ['read'],
                expires_at = expires_at,
            )
        except Exception as e:
            logger.error(f'API key DB save failed: {e}')
            api_key_obj = None

        # Cache করো
        user_cache.set_api_key(key_hash, {
            'user_id': str(user.id),
            'scopes':  scopes or ['read'],
        })

        logger.info(f'API key created for user: {user.id}, name: {name}')

        return {
            'key':        raw_key,   # ⚠️ একবারই দেখাবে
            'key_prefix': key_prefix,
            'name':       name,
            'scopes':     scopes or ['read'],
            'expires_at': expires_at.isoformat() if expires_at else None,
        }

    # ─────────────────────────────────────
    # VALIDATE
    # ─────────────────────────────────────
    def validate(self, raw_key: str) -> dict:
        """
        API key validate করো।
        Returns: {'user_id': ..., 'scopes': [...]}
        Raises: InvalidAPIKeyException
        """
        if not raw_key or not raw_key.startswith(self.PREFIX):
            raise InvalidAPIKeyException()

        key_hash = self._hash(raw_key)

        # Cache check (fast path)
        cached = user_cache.get_api_key(key_hash)
        if cached:
            return cached

        # DB check (slow path)
        try:
            from django.apps import apps
            APIKey = apps.get_model('users', 'UserAPIKey')
            api_key = APIKey.objects.select_related('user').get(
                key_hash  = key_hash,
                is_active = True,
            )

            # Expiry check
            if api_key.expires_at and api_key.expires_at < timezone.now():
                raise InvalidAPIKeyException()

            # Last used update
            api_key.last_used_at = timezone.now()
            api_key.save(update_fields=['last_used_at'])

            result = {
                'user_id': str(api_key.user.id),
                'scopes':  api_key.scopes,
            }
            user_cache.set_api_key(key_hash, result)
            return result

        except Exception:
            raise InvalidAPIKeyException()

    # ─────────────────────────────────────
    # REVOKE
    # ─────────────────────────────────────
    def revoke(self, raw_key: str, user) -> bool:
        """API key revoke করো"""
        key_hash = self._hash(raw_key)
        try:
            from django.apps import apps
            APIKey = apps.get_model('users', 'UserAPIKey')
            updated = APIKey.objects.filter(
                key_hash = key_hash,
                user     = user,
            ).update(is_active=False)
            user_cache.invalidate_api_key(key_hash)
            return updated > 0
        except Exception as e:
            logger.error(f'API key revoke failed: {e}')
            return False

    def revoke_all(self, user) -> int:
        """User-এর সব API key revoke করো"""
        try:
            from django.apps import apps
            APIKey = apps.get_model('users', 'UserAPIKey')
            count = APIKey.objects.filter(user=user, is_active=True).update(is_active=False)
            logger.info(f'Revoked {count} API keys for user: {user.id}')
            return count
        except Exception as e:
            logger.error(f'Bulk revoke failed: {e}')
            return 0

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _hash(self, raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()


# Singleton
api_key_manager = APIKeyManager()
