# api/rate_limit/context_processors.py
"""
Context processors for rate limit module.

Provides template context data for rate limiting information.
"""
from django.conf import settings

import logging
from typing import Dict, Any
from django.utils import timezone
from django.core.cache import cache

from api.rate_limit.services import RateLimitService
from api.rate_limit.models import UserRateLimitProfile

logger = logging.getLogger(__name__)


def rate_limit_context(request) -> Dict[str, Any]:
    """
    Add rate limit information to template context.
    
    Args:
        request: HTTP request object
        
    Returns:
        Context dictionary with rate limit information
    """
    context = {}
    
    try:
        # Get user rate limit profile if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            profile, created = UserRateLimitProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'api_health_score': 100,
                    'suspicion_score': 0,
                    'custom_daily_limit': 1000,
                    'custom_hourly_limit': 100,
                }
            )
            
            context['user_rate_limit_profile'] = profile
            context['is_premium_user'] = profile.is_premium
            context['user_api_health_score'] = profile.api_health_score
            context['user_suspicion_score'] = profile.suspicion_score
            context['user_daily_limit'] = profile.custom_daily_limit
            context['user_hourly_limit'] = profile.custom_hourly_limit
            context['user_daily_usage'] = profile.daily_usage
            context['user_hourly_usage'] = profile.hourly_usage
        
        # Get rate limit info from request if available
        if hasattr(request, 'rate_limit_info'):
            context['rate_limit_info'] = request.rate_limit_info
            context['rate_limit_remaining'] = request.rate_limit_info.get('remaining', 0)
            context['rate_limit_max'] = request.rate_limit_info.get('max_requests', 0)
            context['rate_limit_reset_time'] = request.rate_limit_info.get('reset_time')
        
        # Get global rate limit status
        context['rate_limit_enabled'] = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        
        # Add rate limit configuration for JavaScript
        context['rate_limit_config'] = {
            'enabled': context['rate_limit_enabled'],
            'show_remaining': getattr(settings, 'RATE_LIMIT_SHOW_REMAINING', True),
            'show_reset_time': getattr(settings, 'RATE_LIMIT_SHOW_RESET_TIME', True),
            'refresh_interval': getattr(settings, 'RATE_LIMIT_REFRESH_INTERVAL', 30),  # seconds
        }
        
    except Exception as e:
        logger.error(f"Error in rate_limit_context processor: {str(e)}")
        # Don't break template rendering if context processor fails
        pass
    
    return context


def user_rate_limit_stats(request) -> Dict[str, Any]:
    """
    Add user rate limit statistics to template context.
    
    Args:
        request: HTTP request object
        
    Returns:
        Context dictionary with user rate limit statistics
    """
    context = {}
    
    try:
        if hasattr(request, 'user') and request.user.is_authenticated:
            rate_limit_service = RateLimitService()
            stats = rate_limit_service.get_user_rate_limit_stats(request.user)
            
            context['user_rate_limit_stats'] = stats
            
            # Calculate percentage usage
            if stats.get('custom_daily_limit', 0) > 0:
                daily_usage_percent = (stats.get('daily_usage', 0) / stats['custom_daily_limit']) * 100
                context['user_daily_usage_percent'] = min(100, daily_usage_percent)
            
            if stats.get('custom_hourly_limit', 0) > 0:
                hourly_usage_percent = (stats.get('hourly_usage', 0) / stats['custom_hourly_limit']) * 100
                context['user_hourly_usage_percent'] = min(100, hourly_usage_percent)
            
            # Status indicators
            context['user_rate_limit_status'] = 'good'
            if stats.get('block_rate_24h', 0) > 20:
                context['user_rate_limit_status'] = 'warning'
            if stats.get('block_rate_24h', 0) > 40 or stats.get('suspicion_score', 0) > 70:
                context['user_rate_limit_status'] = 'critical'
        
    except Exception as e:
        logger.error(f"Error in user_rate_limit_stats processor: {str(e)}")
        pass
    
    return context


def rate_limit_alerts(request) -> Dict[str, Any]:
    """
    Add rate limit alerts to template context.
    
    Args:
        request: HTTP request object
        
    Returns:
        Context dictionary with rate limit alerts
    """
    context = {'rate_limit_alerts': []}
    
    try:
        # Get alerts from cache
        alerts = cache.get('rate_limit_alerts', [])
        
        # Filter alerts relevant to current user
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_alerts = [
                alert for alert in alerts
                if alert.get('user_id') == request.user.id or 
                   alert.get('global', False) or
                   alert.get('severity') in ['critical', 'high']
            ]
            context['rate_limit_alerts'] = user_alerts
        else:
            # Show only global alerts for anonymous users
            global_alerts = [alert for alert in alerts if alert.get('global', False)]
            context['rate_limit_alerts'] = global_alerts
        
        # Add alert count
        context['rate_limit_alert_count'] = len(context['rate_limit_alerts'])
        
        # Add unread alert count
        unread_alerts = [
            alert for alert in context['rate_limit_alerts']
            if not alert.get('read', False)
        ]
        context['rate_limit_unread_alert_count'] = len(unread_alerts)
        
    except Exception as e:
        logger.error(f"Error in rate_limit_alerts processor: {str(e)}")
        pass
    
    return context


def system_health_status(request) -> Dict[str, Any]:
    """
    Add system health status to template context.
    
    Args:
        request: HTTP request object
        
    Returns:
        Context dictionary with system health status
    """
    context = {}
    
    try:
        # Get system health from cache
        health_data = cache.get('rate_limit_system_health')
        
        if health_data:
            context['system_health'] = health_data
            context['system_health_score'] = health_data.get('health_score', 0)
            context['system_health_status'] = health_data.get('status', 'unknown')
            
            # Add health status color for UI
            status_colors = {
                'excellent': 'green',
                'good': 'blue',
                'fair': 'yellow',
                'poor': 'orange',
                'critical': 'red',
                'error': 'red'
            }
            context['system_health_color'] = status_colors.get(
                context['system_health_status'], 'gray'
            )
            
            # Add health status icon
            status_icons = {
                'excellent': 'check-circle',
                'good': 'check',
                'fair': 'exclamation-triangle',
                'poor': 'exclamation-circle',
                'critical': 'times-circle',
                'error': 'times'
            }
            context['system_health_icon'] = status_icons.get(
                context['system_health_status'], 'question-circle'
            )
        
        # Add last updated time
        context['system_health_updated'] = cache.get('rate_limit_system_health_updated')
        
    except Exception as e:
        logger.error(f"Error in system_health_status processor: {str(e)}")
        pass
    
    return context


def rate_limit_configuration(request) -> Dict[str, Any]:
    """
    Add rate limit configuration to template context.
    
    Args:
        request: HTTP request object
        
    Returns:
        Context dictionary with rate limit configuration
    """
    context = {}
    
    try:
        # Add configuration settings
        context['rate_limit_settings'] = {
            'enabled': getattr(settings, 'RATE_LIMIT_ENABLED', True),
            'show_ui': getattr(settings, 'RATE_LIMIT_SHOW_UI', True),
            'show_stats': getattr(settings, 'RATE_LIMIT_SHOW_STATS', True),
            'show_health': getattr(settings, 'RATE_LIMIT_SHOW_HEALTH', True),
            'allow_manual_reset': getattr(settings, 'RATE_LIMIT_ALLOW_MANUAL_RESET', False),
            'debug_mode': getattr(settings, 'RATE_LIMIT_DEBUG', False),
        }
        
        # Add feature flags
        context['rate_limit_features'] = {
            'premium_access': getattr(settings, 'RATE_LIMIT_PREMIUM_ACCESS', True),
            'abuse_detection': getattr(settings, 'RATE_LIMIT_ABUSE_DETECTION', True),
            'auto_blocking': getattr(settings, 'RATE_LIMIT_AUTO_BLOCKING', True),
            'analytics': getattr(settings, 'RATE_LIMIT_ANALYTICS', True),
            'notifications': getattr(settings, 'RATE_LIMIT_NOTIFICATIONS', True),
        }
        
        # Add UI configuration
        context['rate_limit_ui'] = {
            'refresh_interval': getattr(settings, 'RATE_LIMIT_UI_REFRESH_INTERVAL', 30),
            'chart_colors': getattr(settings, 'RATE_LIMIT_CHART_COLORS', {
                'primary': '#007bff',
                'success': '#28a745',
                'warning': '#ffc107',
                'danger': '#dc3545',
                'info': '#17a2b8',
            }),
            'max_chart_points': getattr(settings, 'RATE_LIMIT_MAX_CHART_POINTS', 100),
        }
        
        # Add API endpoints
        context['rate_limit_api'] = {
            'base_url': getattr(settings, 'RATE_LIMIT_API_BASE_URL', '/api/rate-limit/'),
            'stats_url': f"{getattr(settings, 'RATE_LIMIT_API_BASE_URL', '/api/rate-limit/')}stats/",
            'health_url': f"{getattr(settings, 'RATE_LIMIT_API_BASE_URL', '/api/rate-limit/')}health/",
            'reset_url': f"{getattr(settings, 'RATE_LIMIT_API_BASE_URL', '/api/rate-limit/')}reset/",
        }
        
    except Exception as e:
        logger.error(f"Error in rate_limit_configuration processor: {str(e)}")
        pass
    
    return context


def rate_limit_debug_info(request) -> Dict[str, Any]:
    """
    Add debug information to template context (only in debug mode).
    
    Args:
        request: HTTP request object
        
    Returns:
        Context dictionary with debug information
    """
    context = {}
    
    try:
        # Only add debug info in debug mode
        if getattr(settings, 'RATE_LIMIT_DEBUG', False) and getattr(settings, 'DEBUG', False):
            from django.db import connection
            
            # Add request debug info
            context['debug_request'] = {
                'path': request.path,
                'method': request.method,
                'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
            
            # Add rate limit debug info if available
            if hasattr(request, 'rate_limit_info'):
                context['debug_rate_limit'] = request.rate_limit_info
            
            # Add cache debug info
            cache_keys = cache.keys('rate_limit:*')
            context['debug_cache'] = {
                'total_keys': len(cache_keys),
                'sample_keys': list(cache_keys)[:10],  # First 10 keys
            }
            
            # Add database debug info
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM rate_limit_ratelimitlog WHERE timestamp >= NOW() - INTERVAL 1 HOUR")
                recent_logs = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM rate_limit_ratelimitconfig WHERE is_active = true")
                active_configs = cursor.fetchone()[0]
            
            context['debug_database'] = {
                'recent_logs_1h': recent_logs,
                'active_configs': active_configs,
                'queries': len(connection.queries) if hasattr(connection, 'queries') else 0,
            }
            
            # Add performance debug info
            if hasattr(request, 'start_time'):
                import time
                processing_time = time.time() - request.start_time
                context['debug_performance'] = {
                    'processing_time_ms': processing_time * 1000,
                    'memory_usage': 'N/A',  # Would need to implement
                }
        
    except Exception as e:
        logger.error(f"Error in rate_limit_debug_info processor: {str(e)}")
        pass
    
    return context


# Export context processors
__all__ = [
    'rate_limit_context',
    'user_rate_limit_stats',
    'rate_limit_alerts',
    'system_health_status',
    'rate_limit_configuration',
    'rate_limit_debug_info'
]
