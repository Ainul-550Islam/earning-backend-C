"""
Django context processors for alerts app
"""
from django.utils import timezone
from django.db.models import Count, Q
from .models import AlertRule, AlertLog, Notification


def alert_counts(request):
    """Add alert counts to all templates"""
    if not request.user.is_authenticated:
        return {}
    
    return {
        'alert_counts': {
            'total_rules': AlertRule.objects.count(),
            'active_rules': AlertRule.objects.filter(is_active=True).count(),
            'unresolved_alerts': AlertLog.objects.filter(is_resolved=False).count(),
            'critical_alerts': AlertLog.objects.filter(
                is_resolved=False,
                rule__severity='critical'
            ).count(),
            'pending_notifications': Notification.objects.filter(status='pending').count(),
        }
    }


def user_alerts(request):
    """Add user-specific alerts to context"""
    if not request.user.is_authenticated:
        return {}
    
    # Get alerts related to user's rules
    user_rules = AlertRule.objects.filter(created_by=request.user)
    user_alerts = AlertLog.objects.filter(
        rule__in=user_rules
    ).select_related('rule').order_by('-triggered_at')[:5]
    
    return {
        'user_alerts': user_alerts,
        'user_alert_count': AlertLog.objects.filter(
            rule__in=user_rules,
            is_resolved=False
        ).count()
    }


def system_health(request):
    """Add system health information to context"""
    if not request.user.is_authenticated:
        return {}
    
    # Get recent system health status
    from .models import SystemHealthCheck
    health_checks = SystemHealthCheck.objects.filter(
        is_active=True
    ).order_by('-checked_at')[:5]
    
    # Calculate overall health
    if health_checks:
        healthy_count = health_checks.filter(status='healthy').count()
        total_count = health_checks.count()
        health_percentage = (healthy_count / total_count) * 100 if total_count > 0 else 0
    else:
        health_percentage = 0
    
    return {
        'system_health': {
            'checks': health_checks,
            'overall_percentage': round(health_percentage, 1),
            'status': 'healthy' if health_percentage >= 80 else 'degraded' if health_percentage >= 60 else 'unhealthy'
        }
    }


def alert_statistics(request):
    """Add alert statistics to context"""
    if not request.user.is_authenticated:
        return {}
    
    today = timezone.now().date()
    
    # Today's statistics
    today_alerts = AlertLog.objects.filter(triggered_at__date=today)
    today_stats = {
        'total': today_alerts.count(),
        'resolved': today_alerts.filter(is_resolved=True).count(),
        'critical': today_alerts.filter(rule__severity='critical').count(),
    }
    
    # This week's statistics
    week_ago = today - timezone.timedelta(days=7)
    week_alerts = AlertLog.objects.filter(triggered_at__date__gte=week_ago)
    week_stats = {
        'total': week_alerts.count(),
        'resolved': week_alerts.filter(is_resolved=True).count(),
        'critical': week_alerts.filter(rule__severity='critical').count(),
    }
    
    return {
        'alert_statistics': {
            'today': today_stats,
            'week': week_stats,
        }
    }


def notification_channels(request):
    """Add notification channel information to context"""
    if not request.user.is_authenticated:
        return {}
    
    from .models import AlertChannel
    channels = AlertChannel.objects.filter(is_enabled=True)
    
    return {
        'notification_channels': channels,
        'available_channels': [channel.channel_type for channel in channels]
    }


def recent_activity(request):
    """Add recent activity to context"""
    if not request.user.is_authenticated:
        return {}
    
    # Recent alerts
    recent_alerts = AlertLog.objects.select_related('rule').order_by('-triggered_at')[:10]
    
    # Recent notifications
    recent_notifications = Notification.objects.order_by('-created_at')[:10]
    
    return {
        'recent_activity': {
            'alerts': recent_alerts,
            'notifications': recent_notifications,
        }
    }


def alert_types(request):
    """Add alert types and severities to context"""
    from .choices import ALERT_TYPES, SEVERITY_LEVELS
    
    return {
        'alert_types': ALERT_TYPES,
        'severity_levels': SEVERITY_LEVELS,
    }


def user_permissions(request):
    """Add user permissions to context"""
    if not request.user.is_authenticated:
        return {}
    
    permissions = {
        'can_manage_alerts': request.user.has_perm('alerts.manage_alerts'),
        'can_view_alerts': request.user.has_perm('alerts.view_alerts'),
        'can_resolve_alerts': request.user.has_perm('alerts.resolve_alerts'),
        'can_manage_notifications': request.user.has_perm('alerts.manage_notifications'),
        'can_export_data': request.user.has_perm('alerts.export_data'),
        'can_view_sensitive_data': request.user.has_perm('alerts.view_sensitive_data'),
        'is_staff': request.user.is_staff,
    }
    
    return {
        'user_permissions': permissions
    }


def alert_dashboard_config(request):
    """Add dashboard configuration to context"""
    if not request.user.is_authenticated:
        return {}
    
    from .models import AlertDashboardConfig
    config, created = AlertDashboardConfig.objects.get_or_create(
        user=request.user,
        defaults={
            'layout': 'default',
            'widgets': ['stats', 'charts', 'recent_alerts'],
            'refresh_interval': 30,
        }
    )
    
    return {
        'dashboard_config': config
    }


def maintenance_mode(request):
    """Add maintenance mode information to context"""
    from django.conf import settings
    
    maintenance_mode = getattr(settings, 'SYSTEM_MAINTENANCE_MODE', False)
    maintenance_message = getattr(settings, 'SYSTEM_MAINTENANCE_MESSAGE', 'System under maintenance')
    
    # Check if user can access during maintenance
    can_access = False
    if request.user.is_authenticated:
        can_access = (
            request.user.is_staff or
            request.user.has_perm('alerts.access_during_maintenance')
        )
    
    return {
        'maintenance_mode': {
            'active': maintenance_mode,
            'message': maintenance_message,
            'can_access': can_access,
        }
    }


def feature_flags(request):
    """Add feature flags to context"""
    from django.conf import settings
    
    flags = {
        'real_time_updates': getattr(settings, 'ENABLE_REAL_TIME_UPDATES', True),
        'advanced_analytics': getattr(settings, 'ENABLE_ADVANCED_ANALYTICS', False),
        'multi_tenant': getattr(settings, 'ENABLE_MULTI_TENANT', False),
        'ai_correlation': getattr(settings, 'ENABLE_AI_CORRELATION', False),
        'custom_dashboards': getattr(settings, 'ENABLE_CUSTOM_DASHBOARDS', True),
        'export_functionality': getattr(settings, 'ENABLE_EXPORT', True),
        'bulk_operations': getattr(settings, 'ENABLE_BULK_OPERATIONS', True),
    }
    
    return {
        'feature_flags': flags
    }


def timezones(request):
    """Add timezone information to context"""
    from django.utils import timezone
    
    return {
        'current_timezone': timezone.get_current_timezone_name(),
        'current_time': timezone.now(),
    }


def api_info(request):
    """Add API information to context"""
    from django.conf import settings
    
    return {
        'api_info': {
            'version': getattr(settings, 'API_VERSION', '1.0'),
            'base_url': getattr(settings, 'API_BASE_URL', '/api/v1/alerts/'),
            'rate_limit': getattr(settings, 'API_RATE_LIMIT', 1000),
            'timeout': getattr(settings, 'API_TIMEOUT', 30),
        }
    }
