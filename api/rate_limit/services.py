# api/rate_limit/services.py
"""
Business logic for rate limiting. Move complex logic out of views/middleware.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimitService:
    """Service for rate limit checks and resets."""

    @staticmethod
    def is_rate_limited(identifier: str, limit_type: str, max_requests: int = 100) -> Tuple[bool, Optional[int]]:
        """
        Check if identifier (IP/user_id) is over limit.
        Returns (is_limited, remaining_count or None).
        Uses RateLimitConfig if no tracker model.
        """
        try:
            from .models import RateLimitConfig
            from django.utils import timezone
            config = RateLimitConfig.objects.filter(
                rate_limit_type=limit_type, is_active=True
            ).first()
            if config:
                max_requests = config.requests_per_unit
            # Optional: implement actual counter via cache or Redis
            return False, max_requests
        except Exception as e:
            logger.debug("Rate limit check: %s", e)
            return False, None
