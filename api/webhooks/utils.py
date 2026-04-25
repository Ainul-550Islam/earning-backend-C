"""Webhooks Utilities Module

This module contains utility functions for the webhooks system,
including data processing, formatting, and helper functions.
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

from .constants import (
    WebhookStatus, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus
)

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
                avg_response_time=models.Avg('duration_ms')
            )['avg_response_time__avg'] or 0
        
        # Calculate uptime
        health_checks = health_logs.count()
        healthy_checks = health_logs.filter(is_healthy=True).count()
        uptime_percentage = (healthy_checks / health_checks * 100) if health_checks > 0 else 0
        
        return {
            'endpoint_id': endpoint_id,
            'endpoint_url': endpoint.url,
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
    
    Args:
        event_type: Event type identifier
        
    Returns:
        str: Display name
    """
    from .constants import EventType
    
    # Map event types to display names
    display_names = {
        'user.created': _('User Created'),
        'user.updated': _('User Updated'),
        'user.deleted': _('User Deleted'),
        'user.login': _('User Login'),
        'user.logout': _('User Logout'),
        'wallet.transaction.created': _('Wallet Transaction Created'),
        'wallet.balance.updated': _('Wallet Balance Updated'),
        'wallet.frozen': _('Wallet Frozen'),
        'wallet.unfrozen': _('Wallet Unfrozen'),
        'withdrawal.requested': _('Withdrawal Requested'),
        'withdrawal.approved': _('Withdrawal Approved'),
        'withdrawal.rejected': _('Withdrawal Rejected'),
        'withdrawal.completed': _('Withdrawal Completed'),
        'offer.credited': _('Offer Credited'),
        'offer.completed': _('Offer Completed'),
        'offer.expired': _('Offer Expired'),
        'offer.revoked': _('Offer Revoked'),
        'kyc.submitted': _('KYC Submitted'),
        'kyc.verified': _('KYC Verified'),
        'kyc.rejected': _('KYC Rejected'),
        'payment.succeeded': _('Payment Succeeded'),
        'payment.failed': _('Payment Failed'),
        'payment.refunded': _('Payment Refunded'),
        'payment.chargeback': _('Payment Chargeback'),
        'fraud.detected': _('Fraud Detected'),
        'fraud.reviewed': _('Fraud Reviewed'),
        'fraud.confirmed': _('Fraud Confirmed'),
        'fraud.false_positive': _('Fraud False Positive'),
        'system.maintenance': _('System Maintenance'),
        'system.backup': _('System Backup'),
        'system.restored': _('System Restored'),
        'system.error': _('System Error'),
        'analytics.report.generated': _('Analytics Report Generated'),
        'analytics.data.exported': _('Analytics Data Exported'),
        'analytics.threshold.reached': _('Analytics Threshold Reached'),
        'security.breach': _('Security Breach'),
        'security.suspicious_activity': _('Security Suspicious Activity'),
        'security.login.blocked': _('Security Login Blocked'),
        'security.password.changed': _('Security Password Changed'),
        'integration.connected': _('Integration Connected'),
        'integration.disconnected': _('Integration Disconnected'),
        'integration.sync.failed': _('Integration Sync Failed'),
        'integration.api.limit.reached': _('Integration API Limit Reached'),
        'notification.sent': _('Notification Sent'),
        'notification.delivered': _('Notification Delivered'),
        'notification.failed': _('Notification Failed'),
        'notification.opened': _('Notification Opened'),
        'notification.clicked': _('Notification Clicked'),
        'campaign.created': _('Campaign Created'),
        'campaign.started': _('Campaign Started'),
        'campaign.paused': _('Campaign Paused'),
        'campaign.resumed': _('Campaign Resumed'),
        'campaign.completed': _('Campaign Completed'),
        'subscription.created': _('Subscription Created'),
        'subscription.updated': _('Subscription Updated'),
        'subscription.cancelled': _('Subscription Cancelled'),
        'subscription.renewed': _('Subscription Renewed'),
        'subscription.expired': _('Subscription Expired'),
        'api.request': _('API Request'),
        'api.response': _('API Response'),
        'api.error': _('API Error'),
        'api.rate_limit': _('API Rate Limit'),
        'api.quota.exceeded': _('API Quota Exceeded'),
        'health.check.passed': _('Health Check Passed'),
        'health.check.failed': _('Health Check Failed'),
        'health.endpoint.up': _('Health Endpoint Up'),
        'health.endpoint.down': _('Health Endpoint Down'),
        'batch.created': _('Batch Created'),
        'batch.started': _('Batch Started'),
        'batch.completed': _('Batch Completed'),
        'batch.failed': _('Batch Failed'),
        'batch.cancelled': _('Batch Cancelled'),
        'replay.started': _('Replay Started'),
        'replay.completed': _('Replay Completed'),
        'replay.failed': _('Replay Failed'),
        'replay.cancelled': _('Replay Cancelled'),
    }
    
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


def is_valid_webhook_url(url: str) -> bool:
    """
    Check if URL is valid for webhook usage.
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if valid
    """
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ['http', 'https'] and
            parsed.netloc and
            len(url) <= 2048
        )
    except Exception:
        return False


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
