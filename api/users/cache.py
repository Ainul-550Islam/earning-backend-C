"""
api/users/cache.py
User data Redis caching — সব user cache এক জায়গায়
"""
import json
import logging
from django.core.cache import cache
from django.conf import settings
from .constants import CacheKeys

logger = logging.getLogger(__name__)


class UserCacheManager:
    """
    User-related সব Redis cache operation এখানে।
    অন্য app যদি user data cache করতে চায়,
    এই class import করবে — নিজে cache key বানাবে না।
    """

    # ─────────────────────────────────────
    # PROFILE CACHE
    # ─────────────────────────────────────
    @staticmethod
    def get_profile(user_id: str) -> dict | None:
        key = CacheKeys.USER_PROFILE.format(user_id=user_id)
        try:
            data = cache.get(key)
            return data
        except Exception as e:
            logger.warning(f'Cache get profile failed: {e}')
            return None

    @staticmethod
    def set_profile(user_id: str, profile_data: dict) -> bool:
        key = CacheKeys.USER_PROFILE.format(user_id=user_id)
        try:
            cache.set(key, profile_data, timeout=CacheKeys.TTL_PROFILE)
            return True
        except Exception as e:
            logger.warning(f'Cache set profile failed: {e}')
            return False

    @staticmethod
    def invalidate_profile(user_id: str) -> None:
        key = CacheKeys.USER_PROFILE.format(user_id=user_id)
        cache.delete(key)

    # ─────────────────────────────────────
    # BALANCE CACHE (api.wallet থেকে update হবে)
    # ─────────────────────────────────────
    @staticmethod
    def get_balance(user_id: str) -> float | None:
        key = CacheKeys.USER_BALANCE.format(user_id=user_id)
        try:
            return cache.get(key)
        except Exception:
            return None

    @staticmethod
    def set_balance(user_id: str, balance: float) -> bool:
        key = CacheKeys.USER_BALANCE.format(user_id=user_id)
        try:
            cache.set(key, balance, timeout=CacheKeys.TTL_BALANCE)
            return True
        except Exception:
            return False

    @staticmethod
    def invalidate_balance(user_id: str) -> None:
        key = CacheKeys.USER_BALANCE.format(user_id=user_id)
        cache.delete(key)

    # ─────────────────────────────────────
    # TIER CACHE
    # ─────────────────────────────────────
    @staticmethod
    def get_tier(user_id: str) -> str | None:
        key = CacheKeys.USER_TIER.format(user_id=user_id)
        return cache.get(key)

    @staticmethod
    def set_tier(user_id: str, tier: str) -> bool:
        key = CacheKeys.USER_TIER.format(user_id=user_id)
        try:
            cache.set(key, tier, timeout=CacheKeys.TTL_PERMISSIONS)
            return True
        except Exception:
            return False

    # ─────────────────────────────────────
    # PERMISSIONS CACHE
    # ─────────────────────────────────────
    @staticmethod
    def get_permissions(user_id: str) -> list | None:
        key = CacheKeys.USER_PERMISSIONS.format(user_id=user_id)
        return cache.get(key)

    @staticmethod
    def set_permissions(user_id: str, perms: list) -> bool:
        key = CacheKeys.USER_PERMISSIONS.format(user_id=user_id)
        try:
            cache.set(key, perms, timeout=CacheKeys.TTL_PERMISSIONS)
            return True
        except Exception:
            return False

    # ─────────────────────────────────────
    # LOGIN ATTEMPTS CACHE
    # ─────────────────────────────────────
    @staticmethod
    def get_login_attempts(identifier: str) -> int:
        key = CacheKeys.LOGIN_ATTEMPTS.format(identifier=identifier)
        return cache.get(key, default=0)

    @staticmethod
    def increment_login_attempts(identifier: str, lockout_seconds: int = 1800) -> int:
        key = CacheKeys.LOGIN_ATTEMPTS.format(identifier=identifier)
        try:
            count = cache.get(key, 0) + 1
            cache.set(key, count, timeout=lockout_seconds)
            return count
        except Exception:
            return 0

    @staticmethod
    def reset_login_attempts(identifier: str) -> None:
        key = CacheKeys.LOGIN_ATTEMPTS.format(identifier=identifier)
        cache.delete(key)

    @staticmethod
    def is_locked_out(identifier: str, max_attempts: int = 5) -> bool:
        return UserCacheManager.get_login_attempts(identifier) >= max_attempts

    # ─────────────────────────────────────
    # OTP CACHE
    # ─────────────────────────────────────
    @staticmethod
    def set_otp(user_id: str, purpose: str, otp_data: dict) -> bool:
        key = CacheKeys.OTP_CODE.format(user_id=user_id, purpose=purpose)
        try:
            cache.set(key, otp_data, timeout=CacheKeys.TTL_OTP)
            return True
        except Exception:
            return False

    @staticmethod
    def get_otp(user_id: str, purpose: str) -> dict | None:
        key = CacheKeys.OTP_CODE.format(user_id=user_id, purpose=purpose)
        return cache.get(key)

    @staticmethod
    def delete_otp(user_id: str, purpose: str) -> None:
        key = CacheKeys.OTP_CODE.format(user_id=user_id, purpose=purpose)
        cache.delete(key)

    # ─────────────────────────────────────
    # MAGIC LINK CACHE
    # ─────────────────────────────────────
    @staticmethod
    def set_magic_link(token: str, user_id: str) -> bool:
        key = CacheKeys.MAGIC_LINK.format(token=token)
        try:
            cache.set(key, user_id, timeout=CacheKeys.TTL_MAGIC_LINK)
            return True
        except Exception:
            return False

    @staticmethod
    def get_magic_link(token: str) -> str | None:
        key = CacheKeys.MAGIC_LINK.format(token=token)
        return cache.get(key)

    @staticmethod
    def delete_magic_link(token: str) -> None:
        key = CacheKeys.MAGIC_LINK.format(token=token)
        cache.delete(key)

    # ─────────────────────────────────────
    # API KEY CACHE
    # ─────────────────────────────────────
    @staticmethod
    def set_api_key(key_hash: str, user_data: dict) -> bool:
        key = CacheKeys.API_KEY.format(key_hash=key_hash)
        try:
            cache.set(key, user_data, timeout=CacheKeys.TTL_API_KEY)
            return True
        except Exception:
            return False

    @staticmethod
    def get_api_key(key_hash: str) -> dict | None:
        key = CacheKeys.API_KEY.format(key_hash=key_hash)
        return cache.get(key)

    @staticmethod
    def invalidate_api_key(key_hash: str) -> None:
        key = CacheKeys.API_KEY.format(key_hash=key_hash)
        cache.delete(key)

    # ─────────────────────────────────────
    # RATE LIMIT CACHE
    # ─────────────────────────────────────
    @staticmethod
    def check_rate_limit(user_id: str, action: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Returns: (is_allowed, remaining)
        window: seconds
        """
        key = CacheKeys.RATE_LIMIT.format(user_id=user_id, action=action)
        count = cache.get(key, 0)
        if count >= limit:
            return False, 0
        new_count = count + 1
        cache.set(key, new_count, timeout=window)
        return True, limit - new_count

    # ─────────────────────────────────────
    # BULK INVALIDATE (logout হলে সব clear)
    # ─────────────────────────────────────
    @staticmethod
    def invalidate_all(user_id: str) -> None:
        """User logout বা ban হলে সব cache মুছে ফেলো"""
        keys = [
            CacheKeys.USER_PROFILE.format(user_id=user_id),
            CacheKeys.USER_BALANCE.format(user_id=user_id),
            CacheKeys.USER_TIER.format(user_id=user_id),
            CacheKeys.USER_PERMISSIONS.format(user_id=user_id),
        ]
        cache.delete_many(keys)
        logger.info(f'Cache invalidated for user: {user_id}')


# ─────────────────────────────────────────
# DECORATOR — view-level caching
# ─────────────────────────────────────────
def cache_user_response(ttl: int = 60, key_suffix: str = ''):
    """
    View decorator — response cache করো
    Usage:
        @cache_user_response(ttl=300, key_suffix='profile')
        def my_view(request):
            ...
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return func(request, *args, **kwargs)

            cache_key = f'view:{request.user.id}:{key_suffix}'
            cached = cache.get(cache_key)
            if cached:
                from rest_framework.response import Response
                return Response(cached)

            response = func(request, *args, **kwargs)

            if hasattr(response, 'data') and response.status_code == 200:
                cache.set(cache_key, response.data, timeout=ttl)

            return response
        return wrapper
    return decorator


# Singleton instance
user_cache = UserCacheManager()
