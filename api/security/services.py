# api/security/services.py
"""
Business logic for api.security. Move complex logic out of views.
"""
import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class SecurityService:
    """Central service for security-related operations."""

    @staticmethod
    def check_ip_risk(ip_address: str) -> Dict[str, Any]:
        """Assess risk level for an IP. Integrate with fraud_detection if available."""
        try:
            from api.fraud_detection.models import IPReputation
            rep = IPReputation.objects.filter(ip_address=ip_address).first()
            if rep:
                return {
                    "risk_score": rep.fraud_score,
                    "is_blacklisted": rep.is_blacklisted,
                    "country": getattr(rep, 'country', None),
                }
        except Exception as e:
            logger.debug("Fraud IP check not available: %s", e)
        return {"risk_score": 0, "is_blacklisted": False, "country": None}

    @staticmethod
    def log_security_event(user_id: Optional[int], event_type: str, metadata: Optional[Dict] = None) -> None:
        """Log security event for audit. Override with your SecurityAuditLog model if present."""
        logger.info("Security event: %s for user %s", event_type, user_id, extra=metadata or {})


class RateLimitService:
    """
    Rate limiting service using Django's cache backend.
    Provides methods for checking rate limits and brute force detection.
    """

    @staticmethod
    def is_rate_limited(identifier: str, limit: int = 100, window_seconds: int = 3600) -> bool:
        """
        Check if an identifier (IP, user ID, etc.) has exceeded rate limit.
        
        Args:
            identifier: Unique identifier (e.g., IP address, user ID)
            limit: Maximum requests allowed in the time window
            window_seconds: Time window in seconds (default 1 hour)
        
        Returns:
            True if rate limited, False otherwise
        """
        cache_key = f"rate_limit:{identifier}"
        request_count = cache.get(cache_key, 0)
        
        if request_count >= limit:
            logger.warning(f"Rate limit exceeded for {identifier}: {request_count}/{limit}")
            return True
        
        # Increment counter and set expiration
        cache.set(cache_key, request_count + 1, window_seconds)
        return False

    @staticmethod
    def check_brute_force(identifier: str, max_attempts: int = 5, lockout_seconds: int = 900) -> Dict[str, Any]:
        """
        Check for brute force attacks (e.g., login attempts).
        
        Args:
            identifier: Unique identifier (e.g., username, IP address)
            max_attempts: Maximum failed attempts before lockout
            lockout_seconds: Duration of lockout in seconds (default 15 minutes)
        
        Returns:
            Dict with 'is_locked' bool and 'remaining_time' in seconds
        """
        attempt_key = f"brute_force:attempts:{identifier}"
        lockout_key = f"brute_force:lockout:{identifier}"
        
        # Check if already locked out
        lockout_time = cache.get(lockout_key)
        if lockout_time:
            remaining = lockout_time - timezone.now().timestamp()
            if remaining > 0:
                logger.warning(f"Brute force lockout active for {identifier}. Remaining: {remaining}s")
                return {
                    "is_locked": True,
                    "remaining_time": int(remaining),
                    "message": f"Account locked. Try again in {int(remaining)} seconds."
                }
            else:
                # Lockout expired, clear it
                cache.delete(lockout_key)
                cache.delete(attempt_key)
        
        # Increment attempt counter
        attempts = cache.get(attempt_key, 0)
        attempts += 1
        
        if attempts >= max_attempts:
            # Enforce lockout
            lockout_expiry = timezone.now().timestamp() + lockout_seconds
            cache.set(lockout_key, lockout_expiry, lockout_seconds)
            cache.delete(attempt_key)
            logger.critical(f"Brute force lockout initiated for {identifier} after {attempts} attempts")
            return {
                "is_locked": True,
                "remaining_time": lockout_seconds,
                "message": f"Account locked due to too many failed attempts. Try again in {lockout_seconds} seconds."
            }
        
        # Set attempt counter with TTL
        cache.set(attempt_key, attempts, lockout_seconds)
        
        return {
            "is_locked": False,
            "remaining_time": 0,
            "attempts": attempts,
            "max_attempts": max_attempts,
            "message": f"Failed attempt {attempts}/{max_attempts}"
        }

    @staticmethod
    def reset_brute_force(identifier: str) -> None:
        """Reset brute force counters for an identifier."""
        attempt_key = f"brute_force:attempts:{identifier}"
        lockout_key = f"brute_force:lockout:{identifier}"
        cache.delete(attempt_key)
        cache.delete(lockout_key)
        logger.info(f"Brute force counters reset for {identifier}")

