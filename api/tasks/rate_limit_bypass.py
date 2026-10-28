"""
tasks/rate_limit_bypass.py
Emergency bypass mechanisms for rate limiting.
Allows temporary suspension of rate limits during system issues or emergencies.
"""

import logging
import time
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimitBypass:
    """
    Emergency bypass system for rate limiting.
    Allows temporary suspension of rate limits for specific users/endpoints.
    """

    BYPASS_CACHE_KEY = 'rate_limit_bypass'
    BYPASS_TTL = 3600  # 1 hour default

    @staticmethod
    def activate_global_bypass(reason: str, duration_minutes: int = 60, activated_by: str = 'system') -> bool:
        """
        Activate global rate limit bypass.
        WARNING: This disables ALL rate limiting system-wide.
        """
        try:
            bypass_data = {
                'active': True,
                'global': True,
                'reason': reason,
                'activated_at': timezone.now().isoformat(),
                'activated_by': activated_by,
                'expires_at': (timezone.now() + timezone.timedelta(minutes=duration_minutes)).isoformat(),
                'duration_minutes': duration_minutes,
            }

            cache.set(RateLimitBypass.BYPASS_CACHE_KEY, bypass_data, timeout=duration_minutes * 60)

            logger.critical(
                f"[RATE_LIMIT_BYPASS] GLOBAL BYPASS ACTIVATED: {reason} "
                f"by {activated_by} for {duration_minutes} minutes"
            )

            return True
        except Exception as e:
            logger.error(f"Failed to activate global bypass: {e}")
            return False

    @staticmethod
    def activate_user_bypass(user_id: int, reason: str, duration_minutes: int = 30,
                           activated_by: str = 'system') -> bool:
        """
        Activate bypass for specific user.
        """
        try:
            bypass_key = f'{RateLimitBypass.BYPASS_CACHE_KEY}_user_{user_id}'
            bypass_data = {
                'active': True,
                'user_id': user_id,
                'reason': reason,
                'activated_at': timezone.now().isoformat(),
                'activated_by': activated_by,
                'expires_at': (timezone.now() + timezone.timedelta(minutes=duration_minutes)).isoformat(),
                'duration_minutes': duration_minutes,
            }

            cache.set(bypass_key, bypass_data, timeout=duration_minutes * 60)

            logger.warning(
                f"[RATE_LIMIT_BYPASS] User bypass activated for user {user_id}: {reason} "
                f"by {activated_by} for {duration_minutes} minutes"
            )

            return True
        except Exception as e:
            logger.error(f"Failed to activate user bypass for {user_id}: {e}")
            return False

    @staticmethod
    def activate_endpoint_bypass(endpoint: str, reason: str, duration_minutes: int = 15,
                                activated_by: str = 'system') -> bool:
        """
        Activate bypass for specific endpoint.
        """
        try:
            bypass_key = f'{RateLimitBypass.BYPASS_CACHE_KEY}_endpoint_{endpoint}'
            bypass_data = {
                'active': True,
                'endpoint': endpoint,
                'reason': reason,
                'activated_at': timezone.now().isoformat(),
                'activated_by': activated_by,
                'expires_at': (timezone.now() + timezone.timedelta(minutes=duration_minutes)).isoformat(),
                'duration_minutes': duration_minutes,
            }

            cache.set(bypass_key, bypass_data, timeout=duration_minutes * 60)

            logger.warning(
                f"[RATE_LIMIT_BYPASS] Endpoint bypass activated for {endpoint}: {reason} "
                f"by {activated_by} for {duration_minutes} minutes"
            )

            return True
        except Exception as e:
            logger.error(f"Failed to activate endpoint bypass for {endpoint}: {e}")
            return False

    @staticmethod
    def is_global_bypass_active() -> bool:
        """Check if global bypass is active."""
        bypass_data = cache.get(RateLimitBypass.BYPASS_CACHE_KEY)
        return bypass_data and bypass_data.get('active', False) and bypass_data.get('global', False)

    @staticmethod
    def is_user_bypass_active(user_id: int) -> bool:
        """Check if user bypass is active."""
        bypass_key = f'{RateLimitBypass.BYPASS_CACHE_KEY}_user_{user_id}'
        bypass_data = cache.get(bypass_key)
        return bypass_data and bypass_data.get('active', False)

    @staticmethod
    def is_endpoint_bypass_active(endpoint: str) -> bool:
        """Check if endpoint bypass is active."""
        bypass_key = f'{RateLimitBypass.BYPASS_CACHE_KEY}_endpoint_{endpoint}'
        bypass_data = cache.get(bypass_key)
        return bypass_data and bypass_data.get('active', False)

    @staticmethod
    def get_active_bypasses() -> Dict[str, Any]:
        """Get all currently active bypasses."""
        bypasses = {}

        # Global bypass
        global_bypass = cache.get(RateLimitBypass.BYPASS_CACHE_KEY)
        if global_bypass and global_bypass.get('active'):
            bypasses['global'] = global_bypass

        # Get all bypass keys (this is a simplified approach)
        # In production, you might want to use Redis SCAN or maintain a registry
        try:
            # This is a basic implementation - in production you'd want better tracking
            bypasses['summary'] = {
                'global_active': RateLimitBypass.is_global_bypass_active(),
                'note': 'Individual user/endpoint bypasses require manual checking'
            }
        except Exception:
            pass  # Return partial bypasses on error

    @staticmethod
    def deactivate_global_bypass() -> bool:
        """Deactivate global bypass."""
        try:
            cache.delete(RateLimitBypass.BYPASS_CACHE_KEY)
            logger.info("[RATE_LIMIT_BYPASS] Global bypass deactivated")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate global bypass: {e}")
            return False

    @staticmethod
    def deactivate_user_bypass(user_id: int) -> bool:
        """Deactivate user bypass."""
        try:
            bypass_key = f'{RateLimitBypass.BYPASS_CACHE_KEY}_user_{user_id}'
            cache.delete(bypass_key)
            logger.info(f"[RATE_LIMIT_BYPASS] User bypass deactivated for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate user bypass for {user_id}: {e}")
            return False

    @staticmethod
    def deactivate_endpoint_bypass(endpoint: str) -> bool:
        """Deactivate endpoint bypass."""
        try:
            bypass_key = f'{RateLimitBypass.BYPASS_CACHE_KEY}_endpoint_{endpoint}'
            cache.delete(bypass_key)
            logger.info(f"[RATE_LIMIT_BYPASS] Endpoint bypass deactivated for {endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate endpoint bypass for {endpoint}: {e}")
            return False


class EmergencyRateLimitControl:
    """
    Emergency control panel for rate limiting system.
    Provides high-level controls for system operators.
    """

    @staticmethod
    def emergency_shutdown(reason: str, operator: str) -> Dict[str, Any]:
        """
        Emergency shutdown - activate global bypass.
        Use only in critical system failures.
        """
        success = RateLimitBypass.activate_global_bypass(
            reason=f"EMERGENCY SHUTDOWN: {reason}",
            duration_minutes=120,  # 2 hours
            activated_by=operator
        )

        return {
            'action': 'emergency_shutdown',
            'success': success,
            'reason': reason,
            'operator': operator,
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def maintenance_mode(reason: str, operator: str, duration_minutes: int = 30) -> Dict[str, Any]:
        """
        Maintenance mode - temporary bypass for system maintenance.
        """
        success = RateLimitBypass.activate_global_bypass(
            reason=f"MAINTENANCE: {reason}",
            duration_minutes=duration_minutes,
            activated_by=operator
        )

        return {
            'action': 'maintenance_mode',
            'success': success,
            'reason': reason,
            'operator': operator,
            'duration_minutes': duration_minutes,
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def vip_user_access(user_id: int, reason: str, operator: str, duration_minutes: int = 60) -> Dict[str, Any]:
        """
        Grant VIP access to specific user.
        """
        success = RateLimitBypass.activate_user_bypass(
            user_id=user_id,
            reason=f"VIP ACCESS: {reason}",
            duration_minutes=duration_minutes,
            activated_by=operator
        )

        return {
            'action': 'vip_user_access',
            'success': success,
            'user_id': user_id,
            'reason': reason,
            'operator': operator,
            'duration_minutes': duration_minutes,
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def system_status() -> Dict[str, Any]:
        """Get current system status and active bypasses."""
        return {
            'global_bypass_active': RateLimitBypass.is_global_bypass_active(),
            'active_bypasses': RateLimitBypass.get_active_bypasses(),
            'timestamp': timezone.now().isoformat(),
        }