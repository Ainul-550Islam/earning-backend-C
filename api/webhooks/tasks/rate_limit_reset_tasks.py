"""Rate Limit Reset Tasks

This module contains background tasks for webhook rate limiting and reset operations.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from ..models import WebhookEndpoint, WebhookRateLimit
from ..services.analytics import RateLimiterService


@shared_task
def reset_rate_limits():
    """
    Reset rate limit counters for all endpoints.
    This task is typically run on a schedule (e.g., every minute).
    
    Returns:
        dict: Summary of reset operations
    """
    try:
        # Get all rate limits
        rate_limits = WebhookRateLimit.objects.all()
        
        rate_limiter = RateLimiterService()
        reset_count = 0
        
        for rate_limit in rate_limits:
            try:
                # Check if it's time to reset
                if rate_limit.reset_at and rate_limit.reset_at <= timezone.now():
                    # Reset the rate limit
                    result = rate_limiter.reset_rate_limit(
                        rate_limit.endpoint,
                        rate_limit.window_seconds
                    )
                    
                    if result:
                        reset_count += 1
                        
            except Exception as e:
                print(f"Failed to reset rate limit for endpoint {rate_limit.endpoint.id}: {e}")
        
        return {
            'success': True,
            'rate_limits_checked': rate_limits.count(),
            'rate_limits_reset': reset_count,
            'reset_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def reset_rate_limit(endpoint_id, window_seconds=None):
    """
    Reset rate limit counter for a specific endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint
        window_seconds: Optional window seconds to reset (default: use existing)
        
    Returns:
        dict: Result of reset operation
    """
    try:
        # Get the endpoint
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        # Reset the rate limit
        rate_limiter = RateLimiterService()
        result = rate_limiter.reset_rate_limit(endpoint, window_seconds)
        
        return {
            'success': result,
            'endpoint_id': str(endpoint_id),
            'window_seconds': window_seconds,
            'reset_timestamp': timezone.now().isoformat()
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'success': False,
            'error': 'Endpoint not found',
            'endpoint_id': str(endpoint_id)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'endpoint_id': str(endpoint_id)
        }


@shared_task
def cleanup_expired_rate_limits():
    """
    Clean up expired rate limit records.
    
    Returns:
        dict: Summary of cleanup operations
    """
    try:
        # Use the rate limiter service to clean up expired limits
        rate_limiter = RateLimiterService()
        result = rate_limiter.cleanup_expired_rate_limits()
        
        return {
            'success': True,
            'cleaned_count': result.get('cleaned_count', 0),
            'cleanup_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def initialize_rate_limits():
    """
    Initialize rate limits for endpoints that don't have them.
    
    Returns:
        dict: Summary of initialization operations
    """
    try:
        # Get endpoints without rate limits
        endpoints_without_limits = WebhookEndpoint.objects.filter(
            rate_limit_per_min__gt=0
        ).exclude(
            rate_limits__isnull=False
        )
        
        initialized_count = 0
        
        for endpoint in endpoints_without_limits:
            try:
                # Create rate limit record
                WebhookRateLimit.objects.create(
                    endpoint=endpoint,
                    window_seconds=60,  # 1 minute window
                    max_requests=endpoint.rate_limit_per_min,
                    current_count=0,
                    reset_at=timezone.now() + timedelta(minutes=1),
                    created_by=endpoint.created_by
                )
                initialized_count += 1
                
            except Exception as e:
                print(f"Failed to initialize rate limit for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_processed': endpoints_without_limits.count(),
            'initialized_count': initialized_count,
            'initialization_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def sync_rate_limits_with_endpoints():
    """
    Synchronize rate limits with endpoint configurations.
    
    Returns:
        dict: Summary of synchronization operations
    """
    try:
        # Get all endpoints with rate limits
        endpoints_with_limits = WebhookEndpoint.objects.filter(
            rate_limit_per_min__gt=0
        )
        
        updated_count = 0
        created_count = 0
        
        for endpoint in endpoints_with_limits:
            try:
                # Get or create rate limit record
                rate_limit, created = WebhookRateLimit.objects.get_or_create(
                    endpoint=endpoint,
                    window_seconds=60,  # 1 minute window
                    defaults={
                        'max_requests': endpoint.rate_limit_per_min,
                        'current_count': 0,
                        'reset_at': timezone.now() + timedelta(minutes=1),
                        'created_by': endpoint.created_by
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Update existing rate limit if max_requests changed
                    if rate_limit.max_requests != endpoint.rate_limit_per_min:
                        rate_limit.max_requests = endpoint.rate_limit_per_min
                        rate_limit.save()
                        updated_count += 1
                        
            except Exception as e:
                print(f"Failed to sync rate limit for endpoint {endpoint.id}: {e}")
        
        return {
            'success': True,
            'endpoints_processed': endpoints_with_limits.count(),
            'created_count': created_count,
            'updated_count': updated_count,
            'sync_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def get_rate_limit_statistics():
    """
    Get statistics about rate limiting.
    
    Returns:
        dict: Rate limiting statistics
    """
    try:
        from django.db.models import Count, Avg, Max, Sum
        
        # Get overall statistics
        total_rate_limits = WebhookRateLimit.objects.count()
        active_rate_limits = WebhookRateLimit.objects.filter(is_active=True).count()
        
        # Get utilization statistics
        rate_limit_stats = WebhookRateLimit.objects.aggregate(
            avg_utilization=Avg('current_count'),
            max_utilization=Max('current_count'),
            total_requests=Sum('current_count')
        )
        
        # Get endpoint statistics
        endpoints_with_limits = WebhookEndpoint.objects.filter(
            rate_limit_per_min__gt=0
        ).count()
        
        # Get most utilized rate limits
        most_utilized = WebhookRateLimit.objects.filter(
            is_active=True
        ).order_by('-current_count')[:10]
        
        most_utilized_data = []
        for rate_limit in most_utilized:
            utilization = (rate_limit.current_count / rate_limit.max_requests * 100) if rate_limit.max_requests > 0 else 0
            most_utilized_data.append({
                'endpoint_id': str(rate_limit.endpoint.id),
                'endpoint_label': rate_limit.endpoint.label or rate_limit.endpoint.url,
                'current_count': rate_limit.current_count,
                'max_requests': rate_limit.max_requests,
                'utilization_percentage': round(utilization, 2)
            })
        
        return {
            'success': True,
            'total_rate_limits': total_rate_limits,
            'active_rate_limits': active_rate_limits,
            'endpoints_with_limits': endpoints_with_limits,
            'avg_utilization': rate_limit_stats['avg_utilization'] or 0,
            'max_utilization': rate_limit_stats['max_utilization'] or 0,
            'total_requests': rate_limit_stats['total_requests'] or 0,
            'most_utilized': most_utilized_data,
            'statistics_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def reset_rate_limit_by_utilization(utilization_threshold=90):
    """
    Reset rate limits for endpoints with high utilization.
    
    Args:
        utilization_threshold: Utilization percentage threshold (default: 90)
        
    Returns:
        dict: Summary of reset operations
    """
    try:
        # Get rate limits with high utilization
        high_utilization_limits = WebhookRateLimit.objects.filter(
            is_active=True
        )
        
        reset_count = 0
        
        for rate_limit in high_utilization_limits:
            try:
                # Calculate utilization
                utilization = (rate_limit.current_count / rate_limit.max_requests * 100) if rate_limit.max_requests > 0 else 0
                
                if utilization >= utilization_threshold:
                    # Reset the rate limit
                    rate_limiter = RateLimiterService()
                    result = rate_limiter.reset_rate_limit(rate_limit.endpoint, rate_limit.window_seconds)
                    
                    if result:
                        reset_count += 1
                        
            except Exception as e:
                print(f"Failed to reset rate limit for endpoint {rate_limit.endpoint.id}: {e}")
        
        return {
            'success': True,
            'rate_limits_checked': high_utilization_limits.count(),
            'rate_limits_reset': reset_count,
            'utilization_threshold': utilization_threshold,
            'reset_timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'utilization_threshold': utilization_threshold
        }
