"""
Ainul Enterprise Engine — Webhook Utilities
utils.py

Utility functions used throughout the webhook system.

FIX: Documented usage of all 15 previously "floating" utility functions:

    generate_webhook_signature   — SignatureEngine.generate_signature()
    verify_webhook_signature     — SignatureVerifier.verify()
    get_cache_key                — RateLimiterService._get_cache_key()
    format_webhook_payload       — DispatchService._prepare_payload()
    get_webhook_headers          — DispatchService._build_headers()
    parse_webhook_headers        — InboundWebhookService._parse_headers()
    calculate_retry_delay        — DispatchService._schedule_retry()
    get_webhook_status_stats     — WebhookAnalyticsService.get_stats()
    sanitize_webhook_url         — WebhookEndpointSerializer.validate_target_url()
    get_event_type_display_name  — no live caller confirmed (Session 9):
                                    the routed EventTypeListAPIView.get()
                                    (views.py) derives display names from
                                    dict(EventType.choices) directly and
                                    never calls this; only the unrouted
                                    viewsets/_deprecated_unused/
                                    EventTypeListAPIView.py referenced it.
                                    Kept and rewritten to match that same
                                    EventType.choices-based approach
                                    rather than removed, since __all__
                                    exports it and something outside this
                                    app may still import it directly.
    format_webhook_error_message — WebhookDeliveryLogSerializer
    set_cache_data               — RateLimiterService._set_rate_limit()
    get_cache_data               — RateLimiterService._get_rate_limit()
    delete_cache_data            — RateLimiterService._clear_rate_limit()
    truncate_string              — WebhookDeliveryLogAdmin.payload_preview()
    format_bytes                 — AdminWebhookExportSerializer
    is_valid_webhook_url         — validate_webhook_url() validator
    mask_sensitive_data          — WebhookEndpointSerializer (secrets)
"""

import json
import logging
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from django.utils import timezone
from django.core.cache import cache
from django.db import models

from .constants import (
    WebhookStatus, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus
)
from .validators import is_valid_webhook_url

logger = logging.getLogger(__name__)


def generate_webhook_signature(payload: Dict[str, Any], secret: str) -> str:
    """
    Generate HMAC signature for webhook payload.
    
    Args:
        payload: Webhook payload data
        secret: Webhook secret key
        
    Returns:
        str: HMAC signature
    """
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_json.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_webhook_signature(payload: Dict[str, Any], signature: str, secret: str) -> bool:
    """
    Verify HMAC signature for webhook payload.
    
    Args:
        payload: Webhook payload data
        signature: Received signature
        secret: Webhook secret key
        
    Returns:
        bool: True if signature is valid
    """
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload_json.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature.encode('utf-8'), signature.encode('utf-8'))


def format_webhook_payload(payload: Dict[str, Any], template: Optional[str] = None) -> Dict[str, Any]:
    """
    Format webhook payload with optional template processing.
    
    Args:
        payload: Original webhook payload
        template: Optional Jinja2 template
        
    Returns:
        dict: Formatted payload
    """
    if template:
        try:
            from jinja2 import Environment, Template
            env = Environment()
            jinja_template = env.from_string(template)
            formatted_payload = jinja_template.render(payload)
            
            # Parse the rendered template back to JSON
            try:
                return json.loads(formatted_payload)
            except json.JSONDecodeError:
                # If template doesn't render valid JSON, return the raw string
                return {'rendered': formatted_payload}
        except ImportError:
            logger.warning("Jinja2 not available for template processing")
            return payload
        except Exception as e:
            logger.error(f"Template processing error: {e}")
            return payload


def get_webhook_headers(secret: str, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Generate standard webhook headers with signature.
    
    Args:
        secret: Webhook secret key
        additional_headers: Optional additional headers
        
    Returns:
        dict: Complete webhook headers
    """
    timestamp = datetime.utcnow().isoformat()
    payload_hash = generate_webhook_signature({'timestamp': timestamp}, secret)
    
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': payload_hash,
        'X-Webhook-Timestamp': timestamp,
        'User-Agent': 'Webhooks-Client/1.0',
    }
    
    if additional_headers:
        headers.update(additional_headers)
    
    return headers


def parse_webhook_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Parse webhook headers and extract relevant information.
    
    Args:
        headers: Raw HTTP headers
        
    Returns:
        dict: Parsed headers
    """
    parsed = {}
    
    for key, value in headers.items():
        # Normalize header names
        normalized_key = key.lower().replace('_', '-')
        
        # Extract specific headers
        if normalized_key == 'x-webhook-signature':
            parsed['signature'] = value
        elif normalized_key == 'x-webhook-timestamp':
            parsed['timestamp'] = value
        elif normalized_key == 'content-type':
            parsed['content_type'] = value
        elif normalized_key == 'user-agent':
            parsed['user_agent'] = value
    
    return parsed


def calculate_retry_delay(attempt_number: int, max_retries: int = 3, backoff_type: str = 'exponential') -> int:
    """
    Calculate retry delay based on attempt number and backoff strategy.
    
    Args:
        attempt_number: Current retry attempt (1-based)
        max_retries: Maximum retry attempts allowed
        backoff_type: Type of backoff strategy
        
    Returns:
        int: Delay in seconds
    """
    if attempt_number > max_retries:
        return 0
    
    if backoff_type == 'exponential':
        # Exponential backoff: 2^(attempt-1) * base_delay
        base_delay = 2
        delay = min(base_delay ** (attempt_number - 1), 300)  # Cap at 5 minutes
    elif backoff_type == 'linear':
        # Linear backoff: attempt * base_delay
        base_delay = 5
        delay = min(attempt_number * base_delay, 300)
    else:
        # Fixed delay
        delay = 10
    
    return delay


def get_webhook_status_stats(endpoint_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Get webhook status statistics for a specific endpoint.
    
    Args:
        endpoint_id: Webhook endpoint ID
        days: Number of days to analyze
        
    Returns:
        dict: Status statistics
    """
    from ...models import (
        WebhookDeliveryLog, WebhookEndpoint,
        WebhookAnalytics, WebhookHealthLog
    )
    
    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        since = timezone.now() - timedelta(days=days)
        
        # Get delivery logs
        delivery_logs = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            created_at__gte=since
        )
        
        # Get analytics data
        analytics_data = WebhookAnalytics.objects.filter(
            endpoint=endpoint,
            date__gte=since.date()
        )
        
        # Get health logs
        health_logs = WebhookHealthLog.objects.filter(
            endpoint=endpoint,
            checked_at__gte=since
        )
        
        # Calculate statistics
        total_deliveries = delivery_logs.count()
        successful_deliveries = delivery_logs.filter(status=DeliveryStatus.SUCCESS).count()
        failed_deliveries = delivery_logs.filter(status=DeliveryStatus.FAILED).count()
        
        # Calculate success rate
        success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Calculate average response time
        avg_response_time = 0
        successful_logs = delivery_logs.filter(status=DeliveryStatus.SUCCESS)
        if successful_logs.exists():
            avg_response_time = successful_logs.aggregate(
                avg_response_time=models.Avg('response_time_ms')
            )['avg_response_time'] or 0
        
        # Calculate uptime
        health_checks = health_logs.count()
        healthy_checks = health_logs.filter(is_healthy=True).count()
        uptime_percentage = (healthy_checks / health_checks * 100) if health_checks > 0 else 0
        
        return {
            'endpoint_id': endpoint_id,
            'endpoint_url': endpoint.target_url,
            'period_days': days,
            'total_deliveries': total_deliveries,
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': round(success_rate, 2),
            'avg_response_time_ms': round(avg_response_time, 2),
            'health_checks': health_checks,
            'healthy_checks': healthy_checks,
            'uptime_percentage': round(uptime_percentage, 2),
            'generated_at': timezone.now(),
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'error': f'Webhook endpoint with ID {endpoint_id} not found'
        }
    except Exception as e:
        logger.error(f"Error calculating webhook stats: {e}")
        return {
            'error': str(e)
        }


def sanitize_webhook_url(url: str) -> str:
    """
    Sanitize webhook URL for security.
    
    Args:
        url: Webhook URL to sanitize
        
    Returns:
        str: Sanitized URL
    """
    try:
        parsed = urlparse(url)
        
        # Remove potential sensitive information
        if parsed.password:
            parsed = parsed._replace(password='', params='')
        
        if parsed.fragment:
            parsed = parsed._replace(fragment='')
        
        # Reconstruct URL
        sanitized_url = parsed.geturl()
        
        return sanitized_url
        
    except Exception:
        return url


def get_event_type_display_name(event_type: str) -> str:
    """
    Get human-readable display name for an event type.

    BUG FIX (Session 9): this used to maintain its own hand-written,
    ~75-entry dict - a second, independently-maintained vocabulary for
    the exact same concept EventType already owns ("one task, one
    owner" - see FIXES_APPLIED_SESSION9.md, Cluster 4/5 for the full
    writeup and the sibling EventType.all_choices() bug found alongside
    it). Confirmed this had already drifted from reality: about 40 of
    those ~75 keys (e.g. 'payment.succeeded', 'fraud.detected',
    'wallet.transaction.created') were never real EventType values at
    all - a naming scheme that doesn't match EventType's own
    (EventType.PAYOUT_SUCCESS = "payout.success", not
    "payment.succeeded"). EventType was even imported here already,
    unused anywhere in the function body - a leftover of an incomplete
    migration, not a deliberate design.

    Confirmed via a full search this function has zero live callers
    (only a stale comment referencing the *deprecated*, unrouted
    viewsets/_deprecated_unused/EventTypeListAPIView.py) and zero
    existing test coverage - the *live*, routed event-types endpoint
    (views.py's EventTypeListAPIView, via EventTypeListAPIViewSerializer)
    already solved this exact problem independently, deriving display
    names from dict(EventType.choices) directly. Rewritten to do the
    same here, so there's one real implementation of "how do we get an
    event type's display name" instead of two that can disagree -
    kept this function's own existing fallback style (auto-formatted
    from the raw value) for anything not in EventType, so nothing that
    called this before with a non-canonical value starts erroring; it
    just stops being backed by a second hand-maintained, already-stale
    list.

    Args:
        event_type: Event type identifier

    Returns:
        str: Display name
    """
    from .constants import EventType

    display_names = dict(EventType.choices)

    return display_names.get(event_type, event_type.replace('.', ' ').title())


def format_webhook_error_message(error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Format webhook error message for logging and API responses.
    
    Args:
        error: Exception object
        context: Optional context for additional information
        
    Returns:
        str: Formatted error message
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    if context:
        try:
            context_str = ', '.join([f"{k}={v}" for k, v in context.items()])
            return f"{error_type}: {error_message} (Context: {context_str})"
        except Exception:
            pass
    
    return f"{error_type}: {error_message}"


def get_cache_key(prefix: str, identifier: str) -> str:
    """
    Generate cache key for webhook operations.
    
    Args:
        prefix: Cache key prefix
        identifier: Unique identifier
        
    Returns:
        str: Cache key
    """
    return f"{prefix}:{identifier}"


def set_cache_data(key: str, value: Any, timeout: int = 300) -> bool:
    """
    Set cache data with timeout.
    
    Args:
        key: Cache key
        value: Value to cache
        timeout: Cache timeout in seconds
        
    Returns:
        bool: True if successful
    """
    try:
        cache.set(key, value, timeout)
        return True
    except Exception as e:
        logger.error(f"Cache set error for key {key}: {e}")
        return False


def get_cache_data(key: str) -> Any:
    """
    Get cache data.
    
    Args:
        key: Cache key
        
    Returns:
        Any: Cached value or None
    """
    try:
        return cache.get(key)
    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
        return None


def delete_cache_data(key: str) -> bool:
    """
    Delete cache data.
    
    Args:
        key: Cache key to delete
        
    Returns:
        bool: True if successful
    """
    try:
        cache.delete(key)
        return True
    except Exception as e:
        logger.error(f"Cache delete error for key {key}: {e}")
        return False


def truncate_string(text: str, max_length: int = 100) -> str:
    """
    Truncate string to specified maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        str: Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + '...' if len(text) > max_length else text


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable string.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        str: Formatted string
    """
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"


def mask_sensitive_data(data: Dict[str, Any], fields_to_mask: List[str] = None) -> Dict[str, Any]:
    """
    Mask sensitive data in webhook payloads for logging.
    
    Args:
        data: Original data
        fields_to_mask: List of field names to mask
        
    Returns:
        dict: Data with masked sensitive fields
    """
    if not fields_to_mask:
        return data
    
    masked_data = data.copy()
    
    for field in fields_to_mask:
        if field in masked_data:
            value = masked_data[field]
            if isinstance(value, str):
                # Mask email-like fields
                if '@' in value:
                    masked_data[field] = value[:2] + '***@' + value.split('@')[1].split('.')[0]
                # Mask phone-like fields
                elif value.replace('-', '').isdigit() and len(value) >= 10:
                    masked_data[field] = value[:3] + '***' + value[-4:]
                # Mask credit card-like fields
                elif len(value) >= 16 and any(c.isdigit() or c in value.lower() for c in '0123456789'):
                    masked_data[field] = '****-****-****-' + value[-4:]
    
    return masked_data

# Explicit public API
__all__ = [
    'generate_webhook_signature',
    'verify_webhook_signature',
    'format_webhook_payload',
    'get_webhook_headers',
    'parse_webhook_headers',
    'calculate_retry_delay',
    'get_webhook_status_stats',
    'sanitize_webhook_url',
    'get_event_type_display_name',
    'format_webhook_error_message',
    'get_cache_key',
    'set_cache_data',
    'get_cache_data',
    'delete_cache_data',
    'truncate_string',
    'format_bytes',
    'is_valid_webhook_url',
    'mask_sensitive_data',
]
