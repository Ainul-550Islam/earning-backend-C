"""
context_processors.py – Django context processors for postback module.

Provides template context processors for postback-related
data and functionality in Django templates.
"""
import logging
from typing import Dict, Any

from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .services import PostbackInsightService

logger = logging.getLogger(__name__)
User = get_user_model()


def postback_stats(request):
    """
    Context processor for postback statistics.
    
    Adds postback statistics to template context for dashboard
    and overview pages.
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        # Get recent statistics
        today = timezone.now().date()
        
        # Today's stats
        today_insights = PostbackInsight.objects.filter(date=today)
        today_stats = {
            'total_received': sum(insight.received_count for insight in today_insights),
            'total_rewarded': sum(insight.rewarded_count for insight in today_insights),
            'total_payout': sum(float(insight.total_payout) for insight in today_insights),
            'avg_health': sum(insight.health_score for insight in today_insights) / len(today_insights) if today_insights else 0,
        }
        
        # Overall stats
        all_insights = PostbackInsight.objects.all()
        overall_stats = {
            'total_received': sum(insight.received_count for insight in all_insights),
            'total_rewarded': sum(insight.rewarded_count for insight in all_insights),
            'total_payout': sum(float(insight.total_payout) for insight in all_insights),
            'avg_health': sum(insight.health_score for insight in all_insights) / len(all_insights) if all_insights else 0,
        }
        
        return {
            'postback_stats': {
                'today': today_stats,
                'overall': overall_stats,
                'last_updated': timezone.now().isoformat(),
            }
        }
        
    except Exception as e:
        logger.error(f"Error in postback_stats context processor: {str(e)}")
        return {'postback_stats': {'error': str(e)}}


def network_configs(request):
    """
    Context processor for network configurations.
    
    Adds network configuration data to template context
    for management and configuration pages.
    """
    try:
        if not request.user.is_authenticated or not request.user.is_staff:
            return {}
        
        # Get network configurations
        networks = NetworkPostbackConfig.objects.all()
        
        active_networks = networks.filter(is_active=True)
        inactive_networks = networks.filter(is_active=False)
        
        return {
            'network_configs': {
                'total_count': networks.count(),
                'active_count': active_networks.count(),
                'inactive_count': inactive_networks.count(),
                'recent_networks': networks.order_by('-created_at')[:5],
                'networks_list': networks,
            }
        }
        
    except Exception as e:
        logger.error(f"Error in network_configs context processor: {str(e)}")
        return {'network_configs': {'error': str(e)}}


def user_postback_activity(request):
    """
    Context processor for user-specific postback activity.
    
    Adds user's postback activity data to template context
    for user dashboard and profile pages.
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        # Get user's recent postback activity
        recent_postbacks = PostbackLog.objects.filter(
            resolved_user=user
        ).order_by('-received_at')[:10]
        
        # Get user's postback statistics
        user_postbacks = PostbackLog.objects.filter(resolved_user=user)
        
        user_stats = {
            'total_postbacks': user_postbacks.count(),
            'rewarded_postbacks': user_postbacks.filter(status='rewarded').count(),
            'rejected_postbacks': user_postbacks.filter(status='rejected').count(),
            'total_payout': sum(float(pb.payout) for pb in user_postbacks.filter(status='rewarded') if pb.payout),
        }
        
        return {
            'user_postback_activity': {
                'recent_postbacks': recent_postbacks,
                'statistics': user_stats,
                'last_updated': timezone.now().isoformat(),
            }
        }
        
    except Exception as e:
        logger.error(f"Error in user_postback_activity context processor: {str(e)}")
        return {'user_postback_activity': {'error': str(e)}}


def postback_health(request):
    """
    Context processor for postback system health.
    
    Adds system health indicators to template context
    for monitoring and admin pages.
    """
    try:
        if not request.user.is_staff:
            return {}
        
        # Get health indicators
        today = timezone.now().date()
        
        # Today's health
        today_insights = PostbackInsight.objects.filter(date=today)
        
        if today_insights.exists():
            avg_health = sum(insight.health_score for insight in today_insights) / len(today_insights)
            health_status = 'good' if avg_health >= 80 else 'warning' if avg_health >= 60 else 'critical'
        else:
            avg_health = 0
            health_status = 'unknown'
        
        # Recent anomalies
        recent_anomalies = PostbackInsight.objects.filter(
            date__gte=today - timezone.timedelta(days=7),
            anomaly_detected=True
        ).count()
        
        return {
            'postback_health': {
                'average_health_score': avg_health,
                'health_status': health_status,
                'recent_anomalies': recent_anomalies,
                'last_updated': timezone.now().isoformat(),
            }
        }
        
    except Exception as e:
        logger.error(f"Error in postback_health context processor: {str(e)}")
        return {'postback_health': {'error': str(e)}}


def postback_settings(request):
    """
    Context processor for postback system settings.
    
    Adds system settings and configuration to template context
    for settings and configuration pages.
    """
    try:
        if not request.user.is_staff:
            return {}
        
        from django.conf import settings
        
        # Get relevant settings
        postback_settings = {
            'POSTBACK_AUTO_AGGREGATION': getattr(settings, 'POSTBACK_AUTO_AGGREGATION', False),
            'POSTBACK_INTEGRITY_CHECKING': getattr(settings, 'POSTBACK_INTEGRITY_CHECKING', True),
            'POSTBACK_CACHE_TIMEOUT': getattr(settings, 'POSTBACK_CACHE_TIMEOUT', 3600),
            'POSTBACK_MAX_FILE_SIZE': getattr(settings, 'POSTBACK_MAX_FILE_SIZE', 10485760),  # 10MB
            'POSTBACK_WEBHOOK_TIMEOUT': getattr(settings, 'POSTBACK_WEBHOOK_TIMEOUT', 30),
        }
        
        return {
            'postback_settings': postback_settings
        }
        
    except Exception as e:
        logger.error(f"Error in postback_settings context processor: {str(e)}")
        return {'postback_settings': {'error': str(e)}}


def postback_navigation(request):
    """
    Context processor for postback navigation menu.
    
    Adds navigation menu items and permissions to template context
    for navigation and menu rendering.
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        # Define navigation items
        navigation_items = [
            {
                'name': 'Dashboard',
                'url': '/postback/dashboard/',
                'icon': 'dashboard',
                'permission': True,  # Available to all authenticated users
            },
            {
                'name': 'Postback Logs',
                'url': '/postback/logs/',
                'icon': 'list',
                'permission': user.is_staff,  # Staff only
            },
            {
                'name': 'Analytics',
                'url': '/postback/analytics/',
                'icon': 'analytics',
                'permission': user.is_staff,  # Staff only
            },
            {
                'name': 'Networks',
                'url': '/postback/networks/',
                'icon': 'network',
                'permission': user.is_superuser,  # Superuser only
            },
            {
                'name': 'Insights',
                'url': '/postback/insights/',
                'icon': 'insights',
                'permission': user.is_staff,  # Staff only
            },
            {
                'name': 'Settings',
                'url': '/postback/settings/',
                'icon': 'settings',
                'permission': user.is_superuser,  # Superuser only
            },
        ]
        
        # Filter items based on user permissions
        available_items = [item for item in navigation_items if item['permission']]
        
        return {
            'postback_navigation': {
                'items': available_items,
                'current_path': request.path,
            }
        }
        
    except Exception as e:
        logger.error(f"Error in postback_navigation context processor: {str(e)}")
        return {'postback_navigation': {'error': str(e)}}


def postback_alerts(request):
    """
    Context processor for postback system alerts.
    
    Adds system alerts and notifications to template context
    for alert display and notification system.
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        alerts = []
        
        # Check for system alerts based on user role
        if request.user.is_staff:
            # Check for recent anomalies
            today = timezone.now().date()
            recent_anomalies = PostbackInsight.objects.filter(
                date__gte=today - timezone.timedelta(days=1),
                anomaly_detected=True
            ).count()
            
            if recent_anomalies > 0:
                alerts.append({
                    'type': 'warning',
                    'message': f'{recent_anomalies} anomalies detected in the last 24 hours',
                    'url': '/postback/analytics/',
                    'dismissible': True,
                })
            
            # Check for inactive networks
            inactive_networks = NetworkPostbackConfig.objects.filter(is_active=False).count()
            if inactive_networks > 0:
                alerts.append({
                    'type': 'info',
                    'message': f'{inactive_networks} networks are currently inactive',
                    'url': '/postback/networks/',
                    'dismissible': True,
                })
        
        # Check for user-specific alerts
        if request.user.is_authenticated and not request.user.is_staff:
            # Check for recent successful postbacks
            recent_success = PostbackLog.objects.filter(
                resolved_user=request.user,
                status='rewarded',
                received_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count()
            
            if recent_success > 0:
                alerts.append({
                    'type': 'success',
                    'message': f'Congratulations! You have {recent_success} successful postbacks today',
                    'url': '/postback/profile/',
                    'dismissible': True,
                })
        
        return {
            'postback_alerts': {
                'alerts': alerts,
                'count': len(alerts),
            }
        }
        
    except Exception as e:
        logger.error(f"Error in postback_alerts context processor: {str(e)}")
        return {'postback_alerts': {'error': str(e)}}


def postback_quick_actions(request):
    """
    Context processor for postback quick actions.
    
    Adds quick action buttons and shortcuts to template context
    for dashboard and sidebar quick actions.
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        quick_actions = []
        
        # Common actions for all users
        quick_actions.extend([
            {
                'name': 'View Dashboard',
                'url': '/postback/dashboard/',
                'icon': 'dashboard',
                'description': 'View postback dashboard',
            },
            {
                'name': 'View Profile',
                'url': '/postback/profile/',
                'icon': 'user',
                'description': 'View your postback activity',
            },
        ])
        
        # Staff actions
        if user.is_staff:
            quick_actions.extend([
                {
                    'name': 'Generate Report',
                    'url': '/postback/reports/generate/',
                    'icon': 'report',
                    'description': 'Generate analytics report',
                },
                {
                    'name': 'View Logs',
                    'url': '/postback/logs/',
                    'icon': 'logs',
                    'description': 'View postback logs',
                },
            ])
        
        # Superuser actions
        if user.is_superuser:
            quick_actions.extend([
                {
                    'name': 'Add Network',
                    'url': '/postback/networks/add/',
                    'icon': 'add',
                    'description': 'Add new network configuration',
                },
                {
                    'name': 'System Health',
                    'url': '/postback/health/',
                    'icon': 'health',
                    'description': 'Check system health',
                },
            ])
        
        return {
            'postback_quick_actions': {
                'actions': quick_actions,
                'count': len(quick_actions),
            }
        }
        
    except Exception as e:
        logger.error(f"Error in postback_quick_actions context processor: {str(e)}")
        return {'postback_quick_actions': {'error': str(e)}}
