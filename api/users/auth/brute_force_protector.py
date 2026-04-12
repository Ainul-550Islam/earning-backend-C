"""
api/users/auth/brute_force_protector.py
Login brute force protection — IP + username উভয়ে track করে
"""
import logging
from django.core.cache import cache
from ..constants import AuthConstants
from ..exceptions import AccountLockedException, RateLimitExceededException

logger = logging.getLogger(__name__)


class BruteForceProtector:

    MAX_ATTEMPTS = AuthConstants.MAX_LOGIN_ATTEMPTS         # 5
    LOCKOUT_SEC  = AuthConstants.LOCKOUT_DURATION_MINUTES * 60  # 1800s

    # ─────────────────────────────────────
    # CHECK
    # ─────────────────────────────────────
    def is_locked(self, identifier: str) -> bool:
        """identifier = username বা IP"""
        key   = self._key(identifier)
        count = cache.get(key, 0)
        return count >= self.MAX_ATTEMPTS

    def get_attempts(self, identifier: str) -> int:
        return cache.get(self._key(identifier), 0)

    def get_remaining_attempts(self, identifier: str) -> int:
        return max(0, self.MAX_ATTEMPTS - self.get_attempts(identifier))

    def get_lockout_ttl(self, identifier: str) -> int:
        """কত সেকেন্ড পরে unlock হবে"""
        return cache.ttl(self._key(identifier)) or 0

    # ─────────────────────────────────────
    # RECORD FAIL / SUCCESS
    # ─────────────────────────────────────
    def record_failure(self, identifier: str) -> int:
        """
        Failed attempt record করো।
        Returns: current attempt count
        Raises: AccountLockedException যদি limit exceed হয়
        """
        key   = self._key(identifier)
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=self.LOCKOUT_SEC)

        logger.warning(f'Failed login attempt {count}/{self.MAX_ATTEMPTS} for: {identifier}')

        if count >= self.MAX_ATTEMPTS:
            logger.warning(f'Account LOCKED: {identifier}')
            raise AccountLockedException(unlock_after_minutes=AuthConstants.LOCKOUT_DURATION_MINUTES)

        return count

    def record_success(self, identifier: str) -> None:
        """Successful login — attempt count reset করো"""
        cache.delete(self._key(identifier))
        logger.info(f'Login success, attempts reset for: {identifier}')

    # ─────────────────────────────────────
    # GUARD (decorator-style check)
    # ─────────────────────────────────────
    def guard(self, identifier: str) -> None:
        """
        Login attempt-এর আগে call করো।
        Locked হলে exception raise করবে।
        """
        if self.is_locked(identifier):
            ttl_minutes = max(1, self.get_lockout_ttl(identifier) // 60)
            raise AccountLockedException(unlock_after_minutes=ttl_minutes)

    # ─────────────────────────────────────
    # MANUAL UNLOCK (admin action)
    # ─────────────────────────────────────
    def unlock(self, identifier: str) -> bool:
        """Admin manually unlock করবে"""
        cache.delete(self._key(identifier))
        logger.info(f'Account manually unlocked: {identifier}')
        return True

    # ─────────────────────────────────────
    # IP-BASED CHECK
    # ─────────────────────────────────────
    def check_ip(self, ip: str, max_per_ip: int = 20) -> None:
        """
        একটা IP থেকে অনেক বেশি attempt — block করো।
        এটা username lockout-এর আলাদা layer।
        """
        key   = f'bf:ip:{ip}'
        count = cache.get(key, 0) + 1
        cache.set(key, count, timeout=3600)  # 1 hour

        if count > max_per_ip:
            raise RateLimitExceededException(
                action='login',
                retry_after=3600
            )

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _key(self, identifier: str) -> str:
        return f'bf:user:{identifier}'


# Singleton
brute_force_protector = BruteForceProtector()
