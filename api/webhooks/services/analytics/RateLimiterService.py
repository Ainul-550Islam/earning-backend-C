"""Webhook Rate Limiter Service

This service implements per-endpoint rate limiting with Redis backend.
Tracks API usage and implements throttling for webhook endpoints.
"""

from ...exceptions import WebhookRateLimitError

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

    Two calling conventions coexist on is_rate_limited()/reset_rate_limit()
    (see each method's docstring) — legacy (endpoint, identifier=None),
    driven by a stored WebhookRateLimit config or the global default, and
    explicit (window_seconds=, max_requests=, ...), where the caller
    controls the window and limit directly per call. Existing callers
    (admin/analytics_admin.py, tasks/rate_limit_reset_tasks.py) use the
    legacy convention and are unaffected by the explicit-mode additions.
    """
    
    def __init__(self, backend: str = None, key_prefix: str = '', default_ttl: int = None):
        """
        Initialize rate limiter service.

        Args:
            backend: Optional backend hint (e.g. 'redis'). Django's cache
                     framework already abstracts the actual backend via
                     CACHES settings — this doesn't switch clients, it's
                     accepted for callers that want to be explicit/for
                     future backend-specific tuning.
            key_prefix: Optional prefix prepended to explicit-mode cache
                        keys (legacy-mode keys are unaffected).
            default_ttl: Optional override for the TTL used when writing
                         explicit-mode cache entries. Defaults to the
                         request's window_seconds when not given.
        """
        self.logger = logger
        self.cache_timeout = 3600  # 1 hour
        self.backend = backend
        self.key_prefix = key_prefix or ''
        self.default_ttl = default_ttl

    def _build_rate_limit_key(
        self, endpoint: WebhookEndpoint, window_seconds: int,
        sliding_window: bool = False, ip_address: str = None,
        user_id=None, limit_by: str = None,
    ) -> str:
        """
        Build a cache key for explicit-mode rate limiting. Distinct from
        _get_cache_key() below (legacy mode) — this one varies by
        window_seconds (and optionally ip/user/sliding-window bucket) so
        different explicit calls never collide.
        """
        parts = [f"{self.key_prefix}webhook_rate_limit", str(endpoint.id), str(window_seconds)]

        if limit_by == 'ip' and ip_address:
            parts.append(f"ip:{ip_address}")
        elif limit_by == 'user' and user_id is not None:
            parts.append(f"user:{user_id}")

        if sliding_window:
            bucket = int(time.time() // window_seconds) if window_seconds else int(time.time())
            parts.append(f"sliding:{bucket}")

        return ':'.join(parts)
    
    def is_rate_limited(
        self, endpoint: WebhookEndpoint, identifier: str = None,
        window_seconds: int = None, max_requests: int = None,
        sliding_window: bool = False, burst_capacity: int = None,
        ip_address: str = None, user_id=None, limit_by: str = None,
    ) -> bool:
        """
        Check if a request is rate limited.

        Legacy mode — is_rate_limited(endpoint, identifier=None): checks
        against the endpoint's stored WebhookRateLimit config (or the
        global default), a single persistent counter. Read-only — does
        not increment.

        Explicit mode — is_rate_limited(endpoint, window_seconds=,
        max_requests=, ...): triggered by providing either kwarg. Caller
        controls the window/limit directly; check-and-increment (counts
        this call if not limited), keyed per-window/ip/user/sliding-bucket
        as given.

        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier (legacy mode only)
            window_seconds: Time window in seconds (explicit mode)
            max_requests: Max requests allowed in the window (explicit mode)
            sliding_window: Use a time-bucketed sliding window key
            burst_capacity: Extra headroom added to max_requests before limiting
            ip_address: IP to scope the limit to (with limit_by='ip')
            user_id: User id to scope the limit to (with limit_by='user')
            limit_by: 'ip' or 'user' to scope by identifier above

        Returns:
            bool: True if rate limited
        """
        try:
            explicit_mode = window_seconds is not None or max_requests is not None

            if explicit_mode:
                effective_window = window_seconds if window_seconds is not None else 60
                effective_max = max_requests if max_requests is not None else 100

                cache_key = self._build_rate_limit_key(
                    endpoint, effective_window, sliding_window=sliding_window,
                    ip_address=ip_address, user_id=user_id, limit_by=limit_by,
                )

                current_count = cache.get(cache_key)
                current_count = current_count if current_count is not None else 0

                effective_limit = effective_max + burst_capacity if burst_capacity else effective_max
                is_limited = current_count >= effective_limit

                if not is_limited:
                    ttl = self.default_ttl if self.default_ttl is not None else effective_window
                    cache.set(cache_key, current_count + 1, timeout=ttl)

                return is_limited

            # Legacy path — unchanged from before this session.
            cache_key = self._get_cache_key(endpoint, identifier)
            
            # Get current count from cache
            current_count = cache.get(cache_key, 0)
            
            # Get rate limit configuration
            rate_limit = self._get_rate_limit(endpoint)
            
            if current_count >= rate_limit:
                self.logger.warning(
                    f"Rate limit exceeded for {endpoint.target_url}: {current_count}/{rate_limit}"
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
                    f"Rate limit exceeded for {endpoint.target_url}: {current_count}/{rate_limit}"
                )
                return False
            
            # Increment count
            new_count = current_count + 1
            cache.set(cache_key, new_count, timeout=self.cache_timeout)
            
            # Update database record
            self._update_rate_limit_record(endpoint, count=new_count, identifier=identifier)
            
            self.logger.debug(
                f"Incremented rate limit for {endpoint.target_url}: {new_count}/{rate_limit}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rate limit increment error: {e}")
            return False
    
    def reset_rate_limit(self, endpoint: WebhookEndpoint, identifier: str = None, window_seconds: int = None) -> bool:
        """
        Reset rate limit counter for an endpoint.

        Explicit mode (window_seconds given): clears just that window's
        cache counter — there's no stored config tied to an explicit-mode
        call, so nothing else to reset.
        Legacy mode (window_seconds=None): unchanged from before this
        session — clears the cache counter and zeroes the stored
        WebhookRateLimit record.
        
        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier (legacy mode)
            window_seconds: Time window in seconds (explicit mode)
            
        Returns:
            bool: True if successful
        """
        try:
            if window_seconds is not None:
                cache_key = self._build_rate_limit_key(endpoint, window_seconds)
                cache.delete(cache_key)
                return True

            cache_key = self._get_cache_key(endpoint, identifier)
            
            # Clear cache
            cache.delete(cache_key)
            
            # Update database record
            self._update_rate_limit_record(endpoint, count=0, identifier=identifier)
            
            self.logger.info(f"Reset rate limit for {endpoint.target_url}")
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
                'remaining_requests': max(0, rate_limit - current_count),
                'usage_percentage': round((current_count / rate_limit * 100), 2) if rate_limit else 0.0,
                'reset_at': reset_at,
                'seconds_until_reset': seconds_until_reset,
                'identifier': identifier,
            }
            
        except Exception as e:
            self.logger.error(f"Rate limit status error: {e}")
            return {}

    def get_rate_limit_info(
        self, endpoint: WebhookEndpoint, window_seconds: int = 60, max_requests: int = 100,
        sliding_window: bool = False, ip_address: str = None, user_id=None, limit_by: str = None,
    ) -> Dict[str, Any]:
        """
        Explicit-mode counterpart to get_rate_limit_status() — caller
        supplies window_seconds/max_requests directly rather than relying
        on a stored WebhookRateLimit config.

        Returns:
            Dict with current_count, max_requests, remaining_requests,
            reset_time, is_rate_limited.
        """
        try:
            cache_key = self._build_rate_limit_key(
                endpoint, window_seconds, sliding_window=sliding_window,
                ip_address=ip_address, user_id=user_id, limit_by=limit_by,
            )
            current_count = cache.get(cache_key)
            current_count = current_count if current_count is not None else 0

            reset_time = cache.get(f"{cache_key}:reset_time")

            return {
                'current_count': current_count,
                'max_requests': max_requests,
                'remaining_requests': max(0, max_requests - current_count),
                'reset_time': reset_time,
                'is_rate_limited': current_count >= max_requests,
            }
        except Exception as e:
            self.logger.error(f"Rate limit info error: {e}")
            return {}

    def increment_rate_limit(self, endpoint: WebhookEndpoint, window_seconds: int = 60) -> int:
        """
        Increment the explicit-mode counter for an endpoint/window and
        return the new count. Django's cache.incr() raises ValueError on
        a key that doesn't exist yet (unlike Redis's native INCR, which
        auto-creates at 1) — falls back to creating it at 1 in that case.
        Only (re)sets the TTL on the count that actually started the
        window (new_count == 1); an already-running window's TTL is left
        alone rather than being pushed back on every request.

        Args:
            endpoint: WebhookEndpoint instance
            window_seconds: Time window in seconds

        Returns:
            int: The new count after incrementing
        """
        cache_key = self._build_rate_limit_key(endpoint, window_seconds)
        ttl = self.default_ttl if self.default_ttl is not None else window_seconds

        try:
            new_count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=ttl)
            new_count = 1

        if new_count == 1:
            cache.touch(cache_key, ttl)

        return new_count

    def check_webhook_rate_limit(self, endpoint: WebhookEndpoint) -> Dict[str, Any]:
        """
        Check an endpoint's rate limit using its stored WebhookRateLimit
        config if one exists, otherwise the same defaults as the rest of
        explicit mode (window_seconds=60, max_requests=100).

        Returns:
            Dict with is_rate_limited, current_count, remaining_requests,
            window_seconds, max_requests.
        """
        try:
            rate_limit_config = WebhookRateLimit.objects.filter(endpoint=endpoint).first()
            window_seconds = rate_limit_config.window_seconds if rate_limit_config else 60
            max_requests = rate_limit_config.max_requests if rate_limit_config else 100

            cache_key = self._build_rate_limit_key(endpoint, window_seconds)
            current_count = cache.get(cache_key)
            current_count = current_count if current_count is not None else 0

            return {
                'is_rate_limited': current_count >= max_requests,
                'current_count': current_count,
                'remaining_requests': max(0, max_requests - current_count),
                'window_seconds': window_seconds,
                'max_requests': max_requests,
            }
        except Exception as e:
            self.logger.error(f"Webhook rate limit check error: {e}")
            return {'is_rate_limited': False, 'current_count': 0, 'remaining_requests': 0}

    def record_webhook_request(
        self, endpoint: WebhookEndpoint, check_limit: bool = False, max_requests: int = None,
    ) -> Dict[str, Any]:
        """
        Record (increment) a webhook request, optionally checking it
        against a limit at the same time.

        Args:
            endpoint: WebhookEndpoint instance
            check_limit: If True, also report whether this request pushed
                         the count past max_requests.
            max_requests: Limit to check against (overrides the stored
                          config's max_requests if both are given).

        Returns:
            Dict with success, current_count, and (when check_limit=True)
            is_rate_limited.
        """
        rate_limit_config = WebhookRateLimit.objects.filter(endpoint=endpoint).first()
        window_seconds = rate_limit_config.window_seconds if rate_limit_config else 60
        effective_max = max_requests if max_requests is not None else (
            rate_limit_config.max_requests if rate_limit_config else 100
        )

        new_count = self.increment_rate_limit(endpoint, window_seconds=window_seconds)

        result = {'success': True, 'current_count': new_count}

        if check_limit:
            is_limited = new_count > effective_max
            result['is_rate_limited'] = is_limited
            result['success'] = not is_limited

        return result

    def get_rate_limit_statistics(self, endpoint: WebhookEndpoint) -> Dict[str, Any]:
        """
        Get current utilization statistics for an endpoint, using its
        stored WebhookRateLimit config if one exists, otherwise the same
        defaults as the rest of explicit mode.

        Returns:
            Dict with current_count, max_requests, remaining_requests,
            utilization_percentage, window_seconds.
        """
        try:
            rate_limit_config = WebhookRateLimit.objects.filter(endpoint=endpoint).first()
            window_seconds = rate_limit_config.window_seconds if rate_limit_config else 60
            max_requests = rate_limit_config.max_requests if rate_limit_config else 100

            cache_key = self._build_rate_limit_key(endpoint, window_seconds)
            current_count = cache.get(cache_key)
            current_count = current_count if current_count is not None else 0

            utilization = round((current_count / max_requests * 100), 2) if max_requests else 0.0

            return {
                'current_count': current_count,
                'max_requests': max_requests,
                'remaining_requests': max(0, max_requests - current_count),
                'utilization_percentage': utilization,
                'window_seconds': window_seconds,
            }
        except Exception as e:
            self.logger.error(f"Rate limit statistics error: {e}")
            return {}

    def cleanup_expired_rate_limits(self) -> Dict[str, Any]:
        """
        Delete WebhookRateLimit records whose window has already reset
        (reset_at in the past). Distinct from cleanup_expired_limits()
        below, which uses a 7-day grace period for a different purpose
        (garbage-collecting long-abandoned records) — this one is for
        promptly clearing out records whose data is simply stale the
        moment their window rolls over.

        Returns:
            Dict with cleaned_count.
        """
        try:
            deleted_count = WebhookRateLimit.objects.filter(
                reset_at__lt=timezone.now()
            ).delete()[0]

            self.logger.info(f"Cleaned up {deleted_count} expired rate limit records")
            return {'cleaned_count': deleted_count}
        except Exception as e:
            self.logger.error(f"Rate limit cleanup error: {e}")
            return {'cleaned_count': 0}

    def get_rate_limit(self, endpoint: WebhookEndpoint) -> Optional[WebhookRateLimit]:
        """
        Get the rate-limit configuration record for an endpoint, if one
        exists.

        Args:
            endpoint: WebhookEndpoint instance

        Returns:
            WebhookRateLimit instance, or None if no config exists yet.
        """
        return WebhookRateLimit.objects.filter(endpoint=endpoint).first()

    def create_rate_limit(
        self, endpoint: WebhookEndpoint, window_seconds: int = 3600, max_requests: int = 1000
    ) -> WebhookRateLimit:
        """
        Create a rate-limit configuration record for an endpoint.

        Args:
            endpoint: WebhookEndpoint instance
            window_seconds: Time window in seconds
            max_requests: Maximum requests allowed in the window

        Returns:
            The created WebhookRateLimit instance.
        """
        return WebhookRateLimit.objects.create(
            endpoint=endpoint,
            window_seconds=window_seconds,
            max_requests=max_requests,
            current_count=0,
            reset_at=timezone.now(),
        )

    def update_rate_limit(
        self, rate_limit: WebhookRateLimit, window_seconds: int = None, max_requests: int = None
    ) -> WebhookRateLimit:
        """
        Update a rate-limit configuration record. Resets current_count to 0
        (a changed window/limit invalidates the count accumulated under the
        old configuration).

        Args:
            rate_limit: WebhookRateLimit instance to update
            window_seconds: New time window in seconds (unchanged if None)
            max_requests: New max requests (unchanged if None)

        Returns:
            The updated WebhookRateLimit instance.
        """
        if window_seconds is not None:
            rate_limit.window_seconds = window_seconds
        if max_requests is not None:
            rate_limit.max_requests = max_requests
        rate_limit.current_count = 0
        rate_limit.reset_at = timezone.now()
        rate_limit.save(update_fields=['window_seconds', 'max_requests', 'current_count', 'reset_at', 'updated_at'])
        return rate_limit

    def delete_rate_limit(self, rate_limit: WebhookRateLimit) -> bool:
        """
        Delete a rate-limit configuration record.

        Args:
            rate_limit: WebhookRateLimit instance to delete

        Returns:
            bool: True if deleted successfully.
        """
        try:
            rate_limit.delete()
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete rate limit: {e}")
            return False
    
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

        BUG FIX: was `hasattr(endpoint, 'rate_limit_per_hour')`, a field
        that doesn't exist on WebhookEndpoint - always False, so per-endpoint
        limits never applied, only the global default. Checks the
        endpoint's own WebhookRateLimit row (which does exist for exactly
        this purpose) before falling back to the global default.

        Args:
            endpoint: WebhookEndpoint instance
            
        Returns:
            int: Rate limit
        """
        existing = WebhookRateLimit.objects.filter(endpoint=endpoint).only('max_requests').first()
        if existing:
            return existing.max_requests

        from django.conf import settings
        return getattr(settings, 'WEBHOOK_DEFAULT_RATE_LIMIT', 1000)
    
    def _get_rate_limit_record(self, endpoint: WebhookEndpoint, identifier: str = None) -> Optional[WebhookRateLimit]:
        """
        Get or create rate limit record.

        BUG FIX: previously filtered/created on a `cache_key` field that
        doesn't exist on WebhookRateLimit (real fields: endpoint,
        window_seconds, max_requests, current_count, reset_at) - every call
        raised FieldError/TypeError, silently caught, so no record was ever
        actually persisted. Keyed on endpoint alone instead, via
        get_or_create - the model has no field to persist per-identifier
        sub-scoping distinctly; that still works at the cache-counter layer
        via _get_cache_key, just isn't mirrored into a separate DB row.

        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier (kept in the signature for
                        backward compatibility with existing call sites;
                        not yet persisted per-record - see note above)

        Returns:
            WebhookRateLimit or None
        """
        try:
            rate_limit, _created = WebhookRateLimit.objects.get_or_create(
                endpoint=endpoint,
                defaults={
                    'window_seconds': 3600,
                    'max_requests': self._get_rate_limit(endpoint),
                    'current_count': 0,
                    'reset_at': timezone.now(),
                },
            )
            return rate_limit

        except Exception as e:
            self.logger.error(f"Failed to get rate limit record: {e}")
            return None
    
    def _update_rate_limit_record(self, endpoint: WebhookEndpoint, count: int, identifier: str = None) -> bool:
        """
        Update rate limit record.

        BUG FIX: same `cache_key` field issue as _get_rate_limit_record()
        above - fixed the same way.

        Args:
            endpoint: WebhookEndpoint instance
            identifier: Optional identifier
            count: New count value
            
        Returns:
            bool: True if successful
        """
        try:
            rate_limit = self._get_rate_limit_record(endpoint, identifier)

            if rate_limit:
                rate_limit.current_count = count
                rate_limit.save(update_fields=['current_count', 'updated_at'])
                return True

            return False
            
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
                        'url': limit.endpoint.target_url,
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