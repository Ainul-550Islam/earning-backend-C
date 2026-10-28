"""
api/adapters/rate_limit.py
Rate Limit adapter for earning backend platform
"""
from django.db.models import Q
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta
import json

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rate_limit_status(request):
    """Get user's rate limit status."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's current rate limits
        rate_limits = _get_user_rate_limits(user, tenant_id)
        
        # Get current usage
        current_usage = _get_current_rate_usage(user, tenant_id)
        
        status_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'rate_limits': rate_limits,
            'current_usage': current_usage,
            'status': {
                'is_limited': _is_user_rate_limited(user, tenant_id),
                'remaining_requests': _get_remaining_requests(user, tenant_id),
                'reset_time': _get_rate_limit_reset_time(user, tenant_id),
                'limit_percentage': _get_limit_percentage(user, tenant_id),
            },
            'endpoints': _get_endpoint_limits(user, tenant_id),
            'recommendations': _get_rate_limit_recommendations(user, tenant_id)
        }
        
        return Response({
            'success': True,
            'data': status_data,
            'message': 'Rate limit status retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[RateLimitAdapter] Error getting rate limit status: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve rate limit status',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rate_limit_history(request):
    """Get user's rate limit history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        endpoint = request.GET.get('endpoint')  # 'all', 'api', 'tasks', 'wallet', etc.
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get rate limit history
        from rate_limit.models import RateLimitLog
        queryset = RateLimitLog.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply endpoint filter
        if endpoint and endpoint != 'all':
            queryset = queryset.filter(endpoint=endpoint)
        
        # Paginate
        logs = queryset[offset:offset+limit]
        
        # Serialize logs
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'endpoint': log.endpoint,
                'method': log.method,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'status_code': log.status_code,
                'response_time_ms': log.response_time_ms,
                'rate_limited': log.rate_limited,
                'limit_type': log.limit_type,
                'limit_value': log.limit_value,
                'window_seconds': log.window_seconds,
                'current_count': log.current_count,
                'created_at': log.created_at.isoformat(),
                'metadata': log.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'logs': log_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(log_data) == limit
                },
                'filters': {
                    'endpoint': endpoint
                },
                'summary': _get_rate_limit_summary(queryset)
            },
            'message': 'Rate limit history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[RateLimitAdapter] Error getting rate limit history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve rate limit history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_rate_limit_increase(request):
    """Request rate limit increase."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['endpoint', 'requested_limit', 'reason']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user can request increase
        if not _can_request_rate_limit_increase(user, tenant_id):
            return Response({
                'success': False,
                'error': 'Cannot request rate limit increase',
                'details': 'You have reached the maximum allowed requests for rate limit increases'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create rate limit increase request
        from rate_limit.models import RateLimitRequest
        increase_request = RateLimitRequest.objects.create(
            user=user,
            endpoint=data['endpoint'],
            current_limit=_get_current_rate_limit(user, data['endpoint'], tenant_id),
            requested_limit=data['requested_limit'],
            reason=data['reason'],
            status='pending',
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Emit rate limit request event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('rate_limit.increase_requested', {
            'user_id': user.id,
            'request_id': increase_request.id,
            'endpoint': data['endpoint'],
            'requested_limit': data['requested_limit'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'request_id': increase_request.id,
                'endpoint': data['endpoint'],
                'current_limit': increase_request.current_limit,
                'requested_limit': data['requested_limit'],
                'status': 'pending',
                'created_at': increase_request.created_at.isoformat(),
                'estimated_review_time': '24-48 hours'
            },
            'message': 'Rate limit increase request submitted successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[RateLimitAdapter] Error requesting rate limit increase: {e}")
        return Response({
            'success': False,
            'error': 'Failed to request rate limit increase',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rate_limit_requests(request):
    """Get user's rate limit increase requests."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status_filter = request.GET.get('status')  # 'all', 'pending', 'approved', 'rejected'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get rate limit requests
        from rate_limit.models import RateLimitRequest
        queryset = RateLimitRequest.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply status filter
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        # Paginate
        requests = queryset[offset:offset+limit]
        
        # Serialize requests
        request_data = []
        for req in requests:
            request_data.append({
                'id': req.id,
                'endpoint': req.endpoint,
                'current_limit': req.current_limit,
                'requested_limit': req.requested_limit,
                'reason': req.reason,
                'status': req.status,
                'approved_limit': req.approved_limit,
                'rejection_reason': req.rejection_reason,
                'reviewed_by': {
                    'id': req.reviewed_by.id,
                    'username': req.reviewed_by.username,
                } if req.reviewed_by else None,
                'created_at': req.created_at.isoformat(),
                'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
                'metadata': req.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'requests': request_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(request_data) == limit
                },
                'filters': {
                    'status': status_filter
                },
                'summary': _get_rate_limit_requests_summary(queryset)
            },
            'message': 'Rate limit requests retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[RateLimitAdapter] Error getting rate limit requests: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve rate limit requests',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_rate_limit_analytics(request):
    """Get rate limit analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get rate limit analytics
        from rate_limit.models import RateLimitLog, RateLimitRequest
        logs = RateLimitLog.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        requests = RateLimitRequest.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('user', 'reviewed_by')
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'usage_metrics': {
                'total_requests': logs.count(),
                'rate_limited_requests': logs.filter(rate_limited=True).count(),
                'rate_limit_rate': round((logs.filter(rate_limited=True).count() / max(logs.count(), 1)) * 100, 2),
                'average_response_time_ms': logs.aggregate(
                    avg_time=Avg(F('response_time_ms'))
                )['avg_time'] or 0,
                'endpoints': list(logs.values('endpoint').annotate(
                    count=Count('id'),
                    rate_limited=Count('id', filter=Q(rate_limited=True))
                ).order_by('-count')),
                'methods': list(logs.values('method').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'status_codes': list(logs.values('status_code').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'daily_trends': _get_rate_limit_trends(logs, days)
            },
            'request_metrics': {
                'total_increase_requests': requests.count(),
                'pending_requests': requests.filter(status='pending').count(),
                'approved_requests': requests.filter(status='approved').count(),
                'rejected_requests': requests.filter(status='rejected').count(),
                'approval_rate': round((requests.filter(status='approved').count() / max(requests.count(), 1)) * 100, 2),
                'average_increase_percentage': requests.filter(status='approved').aggregate(
                    avg_increase=Avg(F('approved_limit') - F('current_limit'))
                )['avg_increase'] or 0,
                'request_types': list(requests.values('endpoint').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'daily_trends': _get_increase_request_trends(requests, days)
            },
            'user_metrics': {
                'unique_users': logs.values('user').distinct().count(),
                'most_active_users': list(logs.values(
                    'user__username',
                    'user__first_name',
                    'user__last_name'
                ).annotate(
                    request_count=Count('id')
                ).order_by('-request_count')[:10]),
                'users_most_limited': list(logs.filter(rate_limited=True).values(
                    'user__username',
                    'user__first_name',
                    'user__last_name'
                ).annotate(
                    limited_count=Count('id')
                ).order_by('-limited_count')[:10]),
                'top_requesters': list(logs.values(
                    'user__username',
                    'user__first_name',
                    'user__last_name'
                ).annotate(
                    request_count=Count('id')
                ).order_by('-request_count')[:10])
            },
            'performance_metrics': {
                'peak_requests_per_minute': _get_peak_requests_per_minute(logs),
                'average_requests_per_minute': _get_average_requests_per_minute(logs),
                'slowest_endpoints': list(logs.order_by('-response_time_ms')[:10]),
                'fastest_endpoints': list(logs.order_by('response_time_ms')[:10]),
                'error_rate': _get_error_rate(logs),
                'throughput': _get_throughput_metrics(logs)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Rate limit analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[RateLimitAdapter] Error getting rate limit analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve rate limit analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_rate_limit_config(request):
    """Update rate limit configuration."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        if 'config' not in data:
            return Response({
                'success': False,
                'error': 'Configuration required',
                'details': 'Please provide rate limit configuration'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        config = data['config']
        
        # Update rate limit configuration
        from rate_limit.models import RateLimitConfig
        rate_limit_config, created = RateLimitConfig.objects.get_or_create(
            tenant_id=tenant_id,
            defaults={
                'config': config,
                'created_at': timezone.now()
            }
        )
        
        if not created:
            rate_limit_config.config = config
            rate_limit_config.updated_at = timezone.now()
            rate_limit_config.save()
        
        # Clear rate limit cache
        _clear_rate_limit_cache(tenant_id)
        
        # Emit configuration updated event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('rate_limit.config_updated', {
            'tenant_id': tenant_id,
            'config': config,
            'updated_by': request.user.id
        })
        
        return Response({
            'success': True,
            'data': {
                'tenant_id': tenant_id,
                'config': config,
                'updated_at': rate_limit_config.updated_at.isoformat(),
                'created': created
            },
            'message': 'Rate limit configuration updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[RateLimitAdapter] Error updating rate limit config: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update rate limit configuration',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_user_rate_limits(user, tenant_id) -> Dict:
    """Get user's rate limits."""
    try:
        from rate_limit.models import RateLimitConfig
        
        # Get tenant rate limit config
        config = RateLimitConfig.objects.filter(tenant_id=tenant_id).first()
        if not config:
            return _get_default_rate_limits()
        
        # Get user-specific limits
        user_limits = config.config.get('user_limits', {})
        
        # Apply user level and KYC tier modifications
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        base_limits = user_limits.get(ctx.user_level, user_limits.get('default', {}))
        
        # Apply KYC tier multipliers
        kyc_multipliers = {
            'none': 0.5,
            'basic': 0.75,
            'standard': 1.0,
            'full': 1.5
        }
        
        multiplier = kyc_multipliers.get(ctx.kyc_tier, 1.0)
        
        # Apply multiplier to limits
        final_limits = {}
        for endpoint, limits in base_limits.items():
            final_limits[endpoint] = {
                'requests_per_minute': int(limits.get('requests_per_minute', 60) * multiplier),
                'requests_per_hour': int(limits.get('requests_per_hour', 1000) * multiplier),
                'requests_per_day': int(limits.get('requests_per_day', 10000) * multiplier),
                'burst_limit': int(limits.get('burst_limit', 100) * multiplier),
                'window_seconds': limits.get('window_seconds', 60)
            }
        
        return final_limits
    except Exception:
        return _get_default_rate_limits()


def _get_default_rate_limits() -> Dict:
    """Get default rate limits."""
    return {
        'api': {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'requests_per_day': 10000,
            'burst_limit': 100,
            'window_seconds': 60
        },
        'tasks': {
            'requests_per_minute': 30,
            'requests_per_hour': 500,
            'requests_per_day': 5000,
            'burst_limit': 50,
            'window_seconds': 60
        },
        'wallet': {
            'requests_per_minute': 20,
            'requests_per_hour': 300,
            'requests_per_day': 3000,
            'burst_limit': 30,
            'window_seconds': 60
        },
        'analytics': {
            'requests_per_minute': 120,
            'requests_per_hour': 2000,
            'requests_per_day': 20000,
            'burst_limit': 200,
            'window_seconds': 60
        }
    }


def _get_current_rate_usage(user, tenant_id) -> Dict:
    """Get current rate limit usage."""
    try:
        usage = {}
        rate_limits = _get_user_rate_limits(user, tenant_id)
        
        for endpoint, limits in rate_limits.items():
            window_key = f'rate_limit_{user.id}_{endpoint}_{limits["window_seconds"]}'
            
            # Get current count from cache
            current_count = cache.get(window_key, 0)
            
            usage[endpoint] = {
                'current_count': current_count,
                'limit': limits['requests_per_minute'],
                'percentage': round((current_count / max(limits['requests_per_minute'], 1)) * 100, 2),
                'remaining': max(0, limits['requests_per_minute'] - current_count),
                'reset_time': _get_window_reset_time(window_key, limits['window_seconds'])
            }
        
        return usage
    except Exception:
        return {}


def _is_user_rate_limited(user, tenant_id) -> bool:
    """Check if user is rate limited."""
    try:
        usage = _get_current_rate_usage(user, tenant_id)
        
        for endpoint_usage in usage.values():
            if endpoint_usage['current_count'] >= endpoint_usage['limit']:
                return True
        
        return False
    except Exception:
        return False


def _get_remaining_requests(user, tenant_id) -> int:
    """Get remaining requests for user."""
    try:
        usage = _get_current_rate_usage(user, tenant_id)
        
        min_remaining = float('inf')
        for endpoint_usage in usage.values():
            min_remaining = min(min_remaining, endpoint_usage['remaining'])
        
        return max(0, min_remaining)
    except Exception:
        return 0


def _get_rate_limit_reset_time(user, tenant_id) -> Optional[str]:
    """Get rate limit reset time."""
    try:
        usage = _get_current_rate_usage(user, tenant_id)
        
        next_reset = None
        for endpoint_usage in usage.values():
            if endpoint_usage['reset_time']:
                if not next_reset or endpoint_usage['reset_time'] < next_reset:
                    next_reset = endpoint_usage['reset_time']
        
        return next_reset
    except Exception:
        return None


def _get_limit_percentage(user, tenant_id) -> float:
    """Get rate limit percentage."""
    try:
        usage = _get_current_rate_usage(user, tenant_id)
        
        max_percentage = 0
        for endpoint_usage in usage.values():
            max_percentage = max(max_percentage, endpoint_usage['percentage'])
        
        return max_percentage
    except Exception:
        return 0


def _get_endpoint_limits(user, tenant_id) -> Dict:
    """Get endpoint-specific limits."""
    try:
        rate_limits = _get_user_rate_limits(user, tenant_id)
        
        endpoint_info = {}
        for endpoint, limits in rate_limits.items():
            endpoint_info[endpoint] = {
                'requests_per_minute': limits['requests_per_minute'],
                'requests_per_hour': limits['requests_per_hour'],
                'requests_per_day': limits['requests_per_day'],
                'burst_limit': limits['burst_limit'],
                'window_seconds': limits['window_seconds'],
                'current_usage': _get_endpoint_usage(user, endpoint, tenant_id),
                'is_limited': _is_endpoint_limited(user, endpoint, tenant_id)
            }
        
        return endpoint_info
    except Exception:
        return {}


def _get_endpoint_usage(user, endpoint, tenant_id) -> Dict:
    """Get usage for specific endpoint."""
    try:
        rate_limits = _get_user_rate_limits(user, tenant_id)
        endpoint_limits = rate_limits.get(endpoint, {})
        
        window_key = f'rate_limit_{user.id}_{endpoint}_{endpoint_limits.get("window_seconds", 60)}'
        current_count = cache.get(window_key, 0)
        
        return {
            'current_count': current_count,
            'limit': endpoint_limits.get('requests_per_minute', 60),
            'percentage': round((current_count / max(endpoint_limits.get('requests_per_minute', 60), 1)) * 100, 2),
            'remaining': max(0, endpoint_limits.get('requests_per_minute', 60) - current_count),
            'reset_time': _get_window_reset_time(window_key, endpoint_limits.get('window_seconds', 60))
        }
    except Exception:
        return {}


def _is_endpoint_limited(user, endpoint, tenant_id) -> bool:
    """Check if specific endpoint is limited."""
    try:
        usage = _get_endpoint_usage(user, endpoint, tenant_id)
        return usage['current_count'] >= usage['limit']
    except Exception:
        return False


def _get_rate_limit_recommendations(user, tenant_id) -> List[str]:
    """Get rate limit recommendations."""
    recommendations = []
    
    # Get current usage
    usage = _get_current_rate_usage(user, tenant_id)
    
    # Check for high usage
    for endpoint, endpoint_usage in usage.items():
        if endpoint_usage['percentage'] > 80:
            recommendations.append(f'High usage on {endpoint} endpoint ({endpoint_usage["percentage"]}% of limit)')
        
        if endpoint_usage['remaining'] < 10:
            recommendations.append(f'Low remaining requests on {endpoint} endpoint')
    
    # Check user level
    from api.tasks.integration.shared_context import SharedContext
    ctx = SharedContext.for_user(user.id)
    
    if ctx.user_level < 3:
        recommendations.append('Upgrade your account level for higher rate limits')
    
    if ctx.kyc_tier != 'full':
        recommendations.append('Complete full KYC verification for increased rate limits')
    
    return recommendations


def _get_rate_limit_summary(queryset) -> Dict:
    """Get rate limit summary statistics."""
    try:
        total_logs = queryset.count()
        rate_limited = queryset.filter(rate_limited=True).count()
        
        return {
            'total_logs': total_logs,
            'rate_limited': rate_limited,
            'rate_limit_rate': round((rate_limited / max(total_logs, 1)) * 100, 2),
            'average_response_time_ms': queryset.aggregate(
                avg_time=Avg(F('response_time_ms'))
            )['avg_time'] or 0,
            'endpoints': list(queryset.values('endpoint').annotate(
                count=Count('id')
            ).order_by('-count')),
            'methods': list(queryset.values('method').annotate(
                count=Count('id')
            ).order_by('-count'))
        }
    except Exception:
        return {}


def _can_request_rate_limit_increase(user, tenant_id) -> bool:
    """Check if user can request rate limit increase."""
    try:
        from rate_limit.models import RateLimitRequest
        
        # Check recent requests
        recent_requests = RateLimitRequest.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Allow max 3 requests per 30 days
        return recent_requests < 3
    except Exception:
        return False


def _get_current_rate_limit(user, endpoint, tenant_id) -> int:
    """Get current rate limit for endpoint."""
    try:
        rate_limits = _get_user_rate_limits(user, tenant_id)
        endpoint_limits = rate_limits.get(endpoint, {})
        return endpoint_limits.get('requests_per_minute', 60)
    except Exception:
        return 60


def _get_rate_limit_requests_summary(queryset) -> Dict:
    """Get rate limit requests summary."""
    try:
        total_requests = queryset.count()
        approved_requests = queryset.filter(status='approved').count()
        rejected_requests = queryset.filter(status='rejected').count()
        
        return {
            'total_requests': total_requests,
            'approved_requests': approved_requests,
            'rejected_requests': rejected_requests,
            'pending_requests': queryset.filter(status='pending').count(),
            'approval_rate': round((approved_requests / max(total_requests, 1)) * 100, 2),
            'average_increase': queryset.filter(status='approved').aggregate(
                avg_increase=Avg(F('approved_limit') - F('current_limit'))
            )['avg_increase'] or 0
        }
    except Exception:
        return {}


def _get_window_reset_time(window_key, window_seconds) -> str:
    """Get window reset time."""
    try:
        # Get window start time from cache
        window_start = cache.get(f'{window_key}_start')
        
        if window_start:
            reset_time = window_start + timedelta(seconds=window_seconds)
            return reset_time.isoformat()
        
        return None
    except Exception:
        return None


def _get_rate_limit_trends(logs, days) -> List[Dict]:
    """Get rate limit trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = logs.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total_requests=Count('id'),
            rate_limited=Count('id', filter=Q(rate_limited=True)),
            avg_response_time=Avg(F('response_time_ms'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_requests': trend['total_requests'],
                'rate_limited': trend['rate_limited'],
                'rate_limit_rate': round((trend['rate_limited'] / max(trend['total_requests'], 1)) * 100, 2),
                'avg_response_time_ms': trend['avg_response_time_ms'] or 0
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_increase_request_trends(requests, days) -> List[Dict]:
    """Get increase request trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = requests.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total_requests=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_requests': trend['total_requests'],
                'approved': trend['approved'],
                'rejected': trend['rejected'],
                'approval_rate': round((trend['approved'] / max(trend['total_requests'], 1)) * 100, 2)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_peak_requests_per_minute(logs) -> int:
    """Get peak requests per minute."""
    try:
        from django.db.models import TruncMinute
        from datetime import timedelta
        
        # Get last 24 hours
        start_time = timezone.now() - timedelta(hours=24)
        
        minute_counts = logs.filter(
            created_at__gte=start_time
        ).extra({
            'minute': TruncMinute('created_at')
        }).values('minute').annotate(
            count=Count('id')
        ).order_by('-count')[:1]
        
        return minute_counts[0]['count'] if minute_counts else 0
    except Exception:
        return 0


def _get_average_requests_per_minute(logs) -> float:
    """Get average requests per minute."""
    try:
        from django.db.models import TruncMinute
        from datetime import timedelta
        
        # Get last 24 hours
        start_time = timezone.now() - timedelta(hours=24)
        
        minute_counts = logs.filter(
            created_at__gte=start_time
        ).extra({
            'minute': TruncMinute('created_at')
        }).values('minute').annotate(
            count=Count('id')
        ).aggregate(
            avg_count=Avg('count')
        )['avg_count'] or 0
        
        return minute_counts
    except Exception:
        return 0


def _get_error_rate(logs) -> float:
    """Get error rate."""
    try:
        total_requests = logs.count()
        error_requests = logs.filter(
            status_code__gte=400
        ).count()
        
        return round((error_requests / max(total_requests, 1)) * 100, 2)
    except Exception:
        return 0


def _get_throughput_metrics(logs) -> Dict:
    """Get throughput metrics."""
    try:
        total_requests = logs.count()
        total_response_time = logs.aggregate(
            total_time=Sum(F('response_time_ms'))
        )['total_time'] or 0
        
        return {
            'total_requests': total_requests,
            'total_response_time_ms': total_response_time,
            'average_response_time_ms': total_response_time / max(total_requests, 1),
            'requests_per_second': total_requests / 86400,  # Assuming 24 hour period
            'throughput_score': min(100, 1000 / max(total_response_time / max(total_requests, 1), 1))
        }
    except Exception:
        return {}


def _clear_rate_limit_cache(tenant_id):
    """Clear rate limit cache."""
    try:
        # Clear all rate limit cache keys for tenant
        cache_pattern = f'rate_limit_*_{tenant_id}_*'
        
        # In real implementation, use cache backend's pattern deletion
        # For now, simulate cache clearing
        logger.info(f"Rate limit cache cleared for tenant {tenant_id}")
    except Exception:
        pass
