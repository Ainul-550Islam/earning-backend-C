"""Webhook Rate Limiter Service

This service implements per-endpoint rate limiting with Redis backend.
Tracks API usage and implements throttling for webhook endpoints.
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from ...models import WebhookEndpoint, WebhookRateLimit
from ...choices import WebhookStatus

logger = logging.getLogger(__name__)


class RateLimiterService:
    """
    Service for managing webhook rate limits.
    Uses Redis for distributed rate limiting across multiple servers.
    """
    
    def __init__(self):
        """Initialize rate limiter service."""
        self.logger = logger
        self.cache_timeout = 3600  # 1 hour
    
    def is_rate_limited(self, endpoint: WebhookEndpoint, identifier: str = None) -> bool:
        """
        Check if a request is rate limited.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier (IP address, API key, etc.)
            
        Returns:
            bool: True if rate limited
        """
        try:
            cache_key = self._get_cache_key(endpoint, identifier)
            
            # Get current count from cache
            current_count = cache.get(cache_key, 0)
            
            # Get rate limit configuration
            rate_limit = self._get_rate_limit(endpoint)
            
            if current_count >= rate_limit:
                self.logger.warning(
                    f"Rate limit exceeded for {endpoint.url}: {current_count}/{rate_limit}"
                )
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Rate limit check error: {e}")
            return False
    
    def increment_request(self, endpoint: WebhookEndpoint, identifier: str = None) -> bool:
        """
        Increment request count for rate limiting.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            
        Returns:
            bool: True if successful
        """
        try:
            cache_key = self._get_cache_key(endpoint, identifier)
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Get rate limit
            rate_limit = self._get_rate_limit(endpoint)
            
            # Check if rate limit is exceeded
            if current_count >= rate_limit:
                self.logger.warning(
                    f"Rate limit exceeded for {endpoint.url}: {current_count}/{rate_limit}"
                )
                return False
            
            # Increment count
            new_count = current_count + 1
            cache.set(cache_key, new_count, timeout=self.cache_timeout)
            
            # Update database record
            self._update_rate_limit_record(endpoint, identifier, new_count)
            
            self.logger.debug(
                f"Incremented rate limit for {endpoint.url}: {new_count}/{rate_limit}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rate limit increment error: {e}")
            return False
    
    def reset_rate_limit(self, endpoint: WebhookEndpoint, identifier: str = None) -> bool:
        """
        Reset rate limit counter for an endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            
        Returns:
            bool: True if successful
        """
        try:
            cache_key = self._get_cache_key(endpoint, identifier)
            
            # Clear cache
            cache.delete(cache_key)
            
            # Update database record
            self._update_rate_limit_record(endpoint, identifier, 0)
            
            self.logger.info(f"Reset rate limit for {endpoint.url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Rate limit reset error: {e}")
            return False
    
    def get_rate_limit_status(self, endpoint: WebhookEndpoint, identifier: str = None) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            
        Returns:
            Dict: Rate limit status
        """
        try:
            cache_key = self._get_cache_key(endpoint, identifier)
            current_count = cache.get(cache_key, 0)
            rate_limit = self._get_rate_limit(endpoint)
            
            # Get reset time
            rate_limit_record = self._get_rate_limit_record(endpoint, identifier)
            reset_at = rate_limit_record.reset_at if rate_limit_record else timezone.now()
            
            # Calculate time until reset
            time_until_reset = reset_at + timedelta(seconds=3600) - timezone.now()
            seconds_until_reset = max(0, int(time_until_reset.total_seconds()))
            
            return {
                'endpoint_id': endpoint.id,
                'current_count': current_count,
                'rate_limit': rate_limit,
                'is_limited': current_count >= rate_limit,
                'reset_at': reset_at,
                'seconds_until_reset': seconds_until_reset,
                'identifier': identifier,
            }
            
        except Exception as e:
            self.logger.error(f"Rate limit status error: {e}")
            return {}
    
    def cleanup_expired_limits(self) -> int:
        """
        Clean up expired rate limit records.
        
        Returns:
            int: Number of records cleaned up
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=7)  # Keep 7 days
            
            deleted_count = WebhookRateLimit.objects.filter(
                reset_at__lt=cutoff_date
            ).delete()[0]
            
            self.logger.info(f"Cleaned up {deleted_count} expired rate limit records")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Rate limit cleanup error: {e}")
            return 0
    
    def _get_cache_key(self, endpoint: WebhookEndpoint, identifier: str = None) -> str:
        """
        Generate cache key for rate limiting.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            
        Returns:
            str: Cache key
        """
        base_key = f"webhook_rate_limit:{endpoint.id}"
        
        if identifier:
            base_key += f":{identifier}"
        
        return base_key
    
    def _get_rate_limit(self, endpoint: WebhookEndpoint) -> int:
        """
        Get rate limit for an endpoint.
        
        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            int: Rate limit
        """
        # Check if endpoint has custom rate limit
        if hasattr(endpoint, 'rate_limit_per_hour'):
            return endpoint.rate_limit_per_hour
        
        # Use default rate limit
        from django.conf import settings
        return getattr(settings, 'WEBHOOK_DEFAULT_RATE_LIMIT', 1000)
    
    def _get_rate_limit_record(self, endpoint: WebhookEndpoint, identifier: str = None) -> Optional[WebhookRateLimit]:
        """
        Get or create rate limit record.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            
        Returns:
            WebhookRateLimit or None
        """
        try:
            cache_key = self._get_cache_key(endpoint, identifier)
            
            # Try to get existing record
            rate_limit = WebhookRateLimit.objects.filter(
                endpoint=endpoint,
                cache_key=cache_key
            ).first()
            
            if rate_limit:
                return rate_limit
            
            # Create new record
            rate_limit = WebhookRateLimit.objects.create(
                endpoint=endpoint,
                cache_key=cache_key,
                window_seconds=3600,
                max_requests=self._get_rate_limit(endpoint),
                current_count=0,
                reset_at=timezone.now(),
            )
            
            return rate_limit
            
        except Exception as e:
            self.logger.error(f"Failed to get rate limit record: {e}")
            return None
    
    def _update_rate_limit_record(self, endpoint: WebhookEndpoint, identifier: str = None, count: int) -> bool:
        """
        Update rate limit record.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            count: New count value
            
        Returns:
            bool: True if successful
        """
        try:
            cache_key = self._get_cache_key(endpoint, identifier)
            
            rate_limit = self._get_rate_limit_record(endpoint, identifier)
            
            if rate_limit:
                rate_limit.current_count = count
                rate_limit.save()
                return True
            
            # Create new record
            WebhookRateLimit.objects.create(
                endpoint=endpoint,
                cache_key=cache_key,
                window_seconds=3600,
                max_requests=self._get_rate_limit(endpoint),
                current_count=count,
                reset_at=timezone.now(),
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update rate limit record: {e}")
            return False
    
    def get_global_rate_limit_stats(self) -> Dict[str, Any]:
        """
        Get global rate limiting statistics.
        
        Returns:
            Dict: Global statistics
        """
        try:
            # Get all active rate limits
            active_limits = WebhookRateLimit.objects.filter(
                reset_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            total_requests = sum(limit.current_count for limit in active_limits)
            total_limits = active_limits.count()
            
            # Get most active endpoints
            most_active = active_limits.order_by('-current_count')[:5]
            
            return {
                'total_active_limits': total_limits,
                'total_requests': total_requests,
                'most_active_endpoints': [
                    {
                        'endpoint_id': limit.endpoint.id,
                        'url': limit.endpoint.url,
                        'current_count': limit.current_count,
                        'rate_limit': limit.max_requests,
                    }
                    for limit in most_active
                ],
                'generated_at': timezone.now(),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get global rate limit stats: {e}")
            return {}
