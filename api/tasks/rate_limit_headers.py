"""
tasks/rate_limit_headers.py
RFC 6585 compliant rate limit headers implementation.
Provides standardized headers for rate limiting information.
"""

import logging
from typing import Dict, Optional
from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class RateLimitHeaders:
    """
    RFC 6585 compliant rate limit headers.
    https://tools.ietf.org/html/rfc6585
    """

    # Standard headers
    RATE_LIMIT_LIMIT = 'X-RateLimit-Limit'
    RATE_LIMIT_REMAINING = 'X-RateLimit-Remaining'
    RATE_LIMIT_RESET = 'X-RateLimit-Reset'
    RATE_LIMIT_RETRY_AFTER = 'Retry-After'

    # Custom headers for additional info
    RATE_LIMIT_POLICY = 'X-RateLimit-Policy'
    RATE_LIMIT_SCOPE = 'X-RateLimit-Scope'
    RATE_LIMIT_USER = 'X-RateLimit-User'

    @staticmethod
    def add_headers(response: HttpResponse,
                   limit: int,
                   remaining: int,
                   reset_timestamp: Optional[int] = None,
                   scope: str = 'user',
                   policy: str = 'fixed-window',
                   user_id: Optional[int] = None) -> HttpResponse:
        """
        Add rate limit headers to HTTP response.

        Args:
            response: Django HttpResponse object
            limit: Maximum requests allowed in window
            remaining: Remaining requests in current window
            reset_timestamp: Unix timestamp when limit resets
            scope: Rate limit scope (user, global, ip)
            policy: Rate limiting policy (fixed-window, sliding-window, token-bucket)
            user_id: User ID if applicable
        """
        headers = {
            RateLimitHeaders.RATE_LIMIT_LIMIT: str(limit),
            RateLimitHeaders.RATE_LIMIT_REMAINING: str(max(0, remaining)),
            RateLimitHeaders.RATE_LIMIT_POLICY: policy,
            RateLimitHeaders.RATE_LIMIT_SCOPE: scope,
        }

        if reset_timestamp:
            headers[RateLimitHeaders.RATE_LIMIT_RESET] = str(reset_timestamp)

        if user_id:
            headers[RateLimitHeaders.RATE_LIMIT_USER] = str(user_id)

        # Add headers to response
        for header_name, header_value in headers.items():
            response[header_name] = header_value

        return response

    @staticmethod
    def add_violation_headers(response: HttpResponse,
                             retry_after_seconds: int = 60,
                             limit: int = 100,
                             scope: str = 'user') -> HttpResponse:
        """
        Add headers for rate limit violation (429) responses.
        """
        headers = {
            RateLimitHeaders.RATE_LIMIT_RETRY_AFTER: str(retry_after_seconds),
            RateLimitHeaders.RATE_LIMIT_LIMIT: str(limit),
            RateLimitHeaders.RATE_LIMIT_REMAINING: '0',
            RateLimitHeaders.RATE_LIMIT_SCOPE: scope,
        }

        for header_name, header_value in headers.items():
            response[header_name] = header_value

        return response

    @staticmethod
    def get_reset_timestamp(window_seconds: int) -> int:
        """
        Calculate reset timestamp for current window.
        """
        now = timezone.now()
        # For fixed window, reset at next window boundary
        current_window_start = now.timestamp() // window_seconds * window_seconds
        next_window_start = current_window_start + window_seconds
        return int(next_window_start)


class RateLimitResponse:
    """
    Helper class for creating rate-limited responses with proper headers.
    """

    @staticmethod
    def too_many_requests(message: str = "Rate limit exceeded",
                         retry_after: int = 60,
                         limit: int = 100,
                         scope: str = 'user') -> HttpResponse:
        """
        Create a 429 Too Many Requests response with rate limit headers.
        """
        response = HttpResponse(
            content=f'{{"error": "{message}"}}',
            status=429,
            content_type='application/json'
        )

        RateLimitHeaders.add_violation_headers(
            response=response,
            retry_after_seconds=retry_after,
            limit=limit,
            scope=scope
        )

        return response

    @staticmethod
    def ok_with_limits(response: HttpResponse,
                      limit: int,
                      remaining: int,
                      window_seconds: int,
                      scope: str = 'user',
                      user_id: Optional[int] = None) -> HttpResponse:
        """
        Add rate limit headers to successful response.
        """
        reset_timestamp = RateLimitHeaders.get_reset_timestamp(window_seconds)

        return RateLimitHeaders.add_headers(
            response=response,
            limit=limit,
            remaining=remaining,
            reset_timestamp=reset_timestamp,
            scope=scope,
            user_id=user_id
        )


def apply_rate_limit_headers(view_func):
    """
    Decorator to automatically apply rate limit headers to view responses.
    """
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)

        # Only apply to successful responses
        if hasattr(response, 'status_code') and 200 <= response.status_code < 300:
            # Get rate limit info from request (set by middleware)
            if hasattr(request, '_rate_limit_info'):
                info = request._rate_limit_info
                response = RateLimitResponse.ok_with_limits(
                    response=response,
                    limit=info.get('limit', 100),
                    remaining=info.get('remaining', 99),
                    window_seconds=info.get('window_seconds', 3600),
                    scope=info.get('scope', 'user'),
                    user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None
                )

        return response

    return wrapper


class RateLimitHeaderMiddleware:
    """
    Middleware to add rate limit headers to all responses.
    Should be placed after RateLimitMiddleware in MIDDLEWARE setting.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Check if rate limit info was set by RateLimitMiddleware
        if hasattr(request, '_rate_limit_info'):
            info = request._rate_limit_info

            if response.status_code == 429:
                # Violation response
                response = RateLimitHeaders.add_violation_headers(
                    response=response,
                    retry_after_seconds=info.get('retry_after', 60),
                    limit=info.get('limit', 100),
                    scope=info.get('scope', 'user')
                )
            elif 200 <= response.status_code < 300:
                # Successful response
                reset_timestamp = RateLimitHeaders.get_reset_timestamp(
                    info.get('window_seconds', 3600)
                )

                response = RateLimitHeaders.add_headers(
                    response=response,
                    limit=info.get('limit', 100),
                    remaining=info.get('remaining', 99),
                    reset_timestamp=reset_timestamp,
                    scope=info.get('scope', 'user'),
                    user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None
                )

        return response