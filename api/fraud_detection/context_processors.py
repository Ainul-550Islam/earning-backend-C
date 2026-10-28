# =============================================================================
# fraud_detection/context_processors.py
# =============================================================================
"""
Context Processors for Fraud Detection System.

Provides Django template context processors for fraud detection
data and functionality in templates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.fraud_detection.services import fraud_detection_service, risk_assessment_service
from api.fraud_detection.analytics import get_fraud_analytics
from api.fraud_detection.feature_flags import feature_flag_manager
from api.fraud_detection.constants import RISK_THRESHOLDS


logger = logging.getLogger(__name__)

User = get_user_model()


def fraud_detection_context(request) -> Dict[str, Any]:
    """
    Main fraud detection context processor.
    
    Provides fraud detection data and functionality to templates.
    
    Args:
        request: HTTP request
        
    Returns:
        Context dictionary with fraud detection data
    """
    context = {
        'fraud_detection_enabled': getattr(settings, 'FRAUD_DETECTION_ENABLED', True),
        'show_fraud_warnings': getattr(settings, 'FRAUD_SHOW_WARNINGS', True),
        'fraud_risk_thresholds': RISK_THRESHOLDS,
    }
    
    # Add user-specific fraud data if authenticated
    if hasattr(request, 'user') and request.user.is_authenticated:
        user_context = get_user_fraud_context(request.user)
        context.update(user_context)
    
    # Add system-wide fraud statistics
    if getattr(settings, 'FRAUD_DETECTION_SHOW_STATS', False):
        stats_context = get_fraud_statistics_context()
        context.update(stats_context)
    
    # Add feature flags
    feature_context = get_fraud_feature_flags_context(request.user)
    context.update(feature_context)
    
    return context


def get_user_fraud_context(user) -> Dict[str, Any]:
    """
    Get user-specific fraud detection context.
    
    Args:
        user: User object
        
    Returns:
        User fraud context dictionary
    """
    context = {
        'user_fraud_data': {},
        'user_risk_level': 'unknown',
        'user_risk_score': 0,
        'user_fraud_indicators': [],
        'user_recent_alerts': [],
        'show_user_fraud_warning': False,
    }
    
    try:
        # Get user risk assessment
        risk_result = risk_assessment_service.get_user_risk_summary(user.id)
        
        if risk_result.success:
            context['user_risk_score'] = risk_result.data.get('current_risk_score', 0)
            context['user_risk_level'] = risk_result.data.get('risk_level', 'unknown')
            context['user_fraud_indicators'] = risk_result.data.get('recommendations', [])
            context['user_fraud_data'] = risk_result.data
        
        # Check if user should see fraud warnings
        context['show_user_fraud_warning'] = (
            context['user_risk_score'] >= RISK_THRESHOLDS['medium'] and
            getattr(settings, 'FRAUD_DETECTION_SHOW_USER_WARNINGS', True)
        )
        
        # Get recent fraud alerts for user
        from api.fraud_detection.selectors import fraud_alert_selector
        recent_alerts = fraud_alert_selector.get_alerts_by_user(user.id, limit=5)
        
        context['user_recent_alerts'] = [
            {
                'id': alert.pk,
                'alert_type': alert.alert_type,
                'severity_score': alert.severity_score,
                'description': alert.description,
                'created_at': alert.created_at,
                'acknowledged': alert.acknowledged
            }
            for alert in recent_alerts
        ]
        
    except Exception as e:
        logger.error(f"Error getting user fraud context for user {user.id}: {e}")
    
    return context


def get_fraud_statistics_context() -> Dict[str, Any]:
    """
    Get system-wide fraud statistics context.
    
    Returns:
        Fraud statistics context dictionary
    """
    context = {
        'fraud_stats': {},
        'fraud_trends': {},
        'system_health': 'unknown',
    }
    
    try:
        # Get fraud analytics
        analytics = get_fraud_analytics()
        overview = analytics.get_fraud_overview(period_days=7)
        
        if overview:
            context['fraud_stats'] = {
                'total_cases': overview.get('summary_statistics', {}).get('total_cases', 0),
                'total_alerts': overview.get('summary_statistics', {}).get('total_alerts', 0),
                'total_financial_loss': overview.get('summary_statistics', {}).get('total_financial_loss', 0),
                'average_risk_score': overview.get('summary_statistics', {}).get('average_risk_score', 0),
                'cases_by_severity': overview.get('cases_by_severity', {}),
                'alerts_by_type': overview.get('alerts_by_type', {}),
            }
            
            # Get trend data
            context['fraud_trends'] = overview.get('trend_analysis', {})
        
        # System health check
        context['system_health'] = get_fraud_system_health()
        
    except Exception as e:
        logger.error(f"Error getting fraud statistics context: {e}")
    
    return context


def get_fraud_feature_flags_context(user) -> Dict[str, Any]:
    """
    Get fraud detection feature flags context.
    
    Args:
        user: User object
        
    Returns:
        Feature flags context dictionary
    """
    context = {
        'fraud_feature_flags': {},
        'fraud_features_enabled': [],
    }
    
    try:
        # Get common fraud detection feature flags
        common_flags = [
            'fraud_detection_enabled',
            'real_time_monitoring',
            'advanced_analytics',
            'user_notifications',
            'case_management',
            'compliance_reporting'
        ]
        
        user_id = user.id if user.is_authenticated else None
        
        for flag in common_flags:
            is_enabled = feature_flag_manager.is_enabled(flag, user_id)
            context['fraud_feature_flags'][flag] = is_enabled
            
            if is_enabled:
                context['fraud_features_enabled'].append(flag)
        
    except Exception as e:
        logger.error(f"Error getting fraud feature flags context: {e}")
    
    return context


def get_fraud_system_health() -> str:
    """
    Get fraud detection system health status.
    
    Returns:
        Health status string
    """
    try:
        # Check if fraud detection services are responding
        health_check = fraud_detection_service.get_service_info()
        
        if health_check and health_check.get('status') == 'healthy':
            return 'healthy'
        elif health_check and health_check.get('status') == 'degraded':
            return 'degraded'
        else:
            return 'unhealthy'
            
    except Exception as e:
        logger.error(f"Error checking fraud system health: {e}")
        return 'error'


def admin_fraud_dashboard_context(request) -> Dict[str, Any]:
    """
    Context processor for admin fraud dashboard.
    
    Args:
        request: HTTP request
        
    Returns:
        Admin dashboard context dictionary
    """
    context = {}
    
    # Only provide admin context to staff users
    if not (hasattr(request, 'user') and request.user.is_staff):
        return context
    
    try:
        # Get comprehensive admin fraud data
        analytics = get_fraud_analytics()
        
        # Get different time period data
        periods = {
            'today': 1,
            'week': 7,
            'month': 30,
            'quarter': 90
        }
        
        admin_data = {}
        
        for period_name, days in periods.items():
            overview = analytics.get_fraud_overview(period_days=days)
            
            if overview:
                admin_data[period_name] = {
                    'cases': overview.get('summary_statistics', {}).get('total_cases', 0),
                    'alerts': overview.get('summary_statistics', {}).get('total_alerts', 0),
                    'financial_loss': overview.get('summary_statistics', {}).get('total_financial_loss', 0),
                    'avg_risk_score': overview.get('summary_statistics', {}).get('average_risk_score', 0),
                }
        
        context['admin_fraud_data'] = admin_data
        
        # Get recent cases needing attention
        from api.fraud_detection.selectors import fraud_case_selector
        recent_cases = fraud_case_selector.get_cases_by_status('open', limit=10)
        
        context['admin_recent_cases'] = [
            {
                'id': case.pk,
                'user_id': case.user_id,
                'risk_score': case.risk_score,
                'severity': case.severity,
                'status': case.status,
                'created_at': case.created_at,
                'description': case.description[:100] + '...' if len(case.description) > 100 else case.description
            }
            for case in recent_cases
        ]
        
        # Get high-priority alerts
        from api.fraud_detection.selectors import fraud_alert_selector
        high_priority_alerts = fraud_alert_selector.get_alerts_by_severity(min_score=70, limit=10)
        
        context['admin_high_priority_alerts'] = [
            {
                'id': alert.pk,
                'user_id': alert.user_id,
                'alert_type': alert.alert_type,
                'severity_score': alert.severity_score,
                'description': alert.description[:100] + '...' if len(alert.description) > 100 else alert.description,
                'created_at': alert.created_at,
                'acknowledged': alert.acknowledged
            }
            for alert in high_priority_alerts
        ]
        
        # Get system metrics
        context['admin_system_metrics'] = {
            'total_users': User.objects.count(),
            'active_cases': fraud_case_selector.get_cases_by_status('open').count(),
            'unacknowledged_alerts': fraud_alert_selector.get_unacknowledged_alerts().count(),
            'system_health': get_fraud_system_health(),
        }
        
    except Exception as e:
        logger.error(f"Error getting admin fraud dashboard context: {e}")
    
    return context


def user_fraud_warnings_context(request) -> Dict[str, Any]:
    """
    Context processor for user fraud warnings.
    
    Args:
        request: HTTP request
        
    Returns:
        User warnings context dictionary
    """
    context = {
        'show_fraud_warning': False,
        'fraud_warning_message': '',
        'fraud_warning_level': 'info',
        'fraud_warning_actions': [],
    }
    
    # Only show warnings to authenticated users
    if not (hasattr(request, 'user') and request.user.is_authenticated):
        return context
    
    try:
        # Get user risk data
        risk_result = risk_assessment_service.get_user_risk_summary(request.user.id)
        
        if risk_result.success:
            risk_score = risk_result.data.get('current_risk_score', 0)
            risk_level = risk_result.data.get('risk_level', 'unknown')
            
            # Determine if warning should be shown
            if risk_score >= RISK_THRESHOLDS['critical']:
                context['show_fraud_warning'] = True
                context['fraud_warning_message'] = 'Your account shows critical risk indicators. Please verify your identity immediately.'
                context['fraud_warning_level'] = 'danger'
                context['fraud_warning_actions'] = ['verify_identity', 'contact_support']
                
            elif risk_score >= RISK_THRESHOLDS['high']:
                context['show_fraud_warning'] = True
                context['fraud_warning_message'] = 'Unusual activity detected on your account. Please review recent transactions.'
                context['fraud_warning_level'] = 'warning'
                context['fraud_warning_actions'] = ['review_activity', 'change_password']
                
            elif risk_score >= RISK_THRESHOLDS['medium']:
                context['show_fraud_warning'] = True
                context['fraud_warning_message'] = 'Some activity patterns require attention. Consider enabling additional security measures.'
                context['fraud_warning_level'] = 'info'
                context['fraud_warning_actions'] = ['enable_2fa', 'review_settings']
        
        # Check for recent suspicious alerts
        from api.fraud_detection.selectors import fraud_alert_selector
        recent_alerts = fraud_alert_selector.get_alerts_by_user(
            request.user.id, 
            limit=1, 
            hours=24
        )
        
        if recent_alerts and not context['show_fraud_warning']:
            alert = recent_alerts[0]
            if alert.severity_score >= RISK_THRESHOLDS['high']:
                context['show_fraud_warning'] = True
                context['fraud_warning_message'] = f'Suspicious activity detected: {alert.description}'
                context['fraud_warning_level'] = 'warning'
                context['fraud_warning_actions'] = ['review_alert', 'secure_account']
        
    except Exception as e:
        logger.error(f"Error getting user fraud warnings context for user {request.user.id}: {e}")
    
    return context


def fraud_detection_navigation_context(request) -> Dict[str, Any]:
    """
    Context processor for fraud detection navigation.
    
    Args:
        request: HTTP request
        
    Returns:
        Navigation context dictionary
    """
    context = {
        'fraud_nav_items': [],
        'show_fraud_nav': False,
    }
    
    # Show navigation based on user permissions and feature flags
    if hasattr(request, 'user') and request.user.is_authenticated:
        user_id = request.user.id
        
        # Check if user has access to fraud detection features
        if request.user.is_staff:
            context['show_fraud_nav'] = True
            
            # Staff navigation items
            context['fraud_nav_items'] = [
                {
                    'name': 'Dashboard',
                    'url': '/admin/fraud-detection/',
                    'icon': 'dashboard',
                    'active': request.path.startswith('/admin/fraud-detection/')
                },
                {
                    'name': 'Cases',
                    'url': '/admin/fraud-detection/cases/',
                    'icon': 'cases',
                    'active': request.path.startswith('/admin/fraud-detection/cases/')
                },
                {
                    'name': 'Alerts',
                    'url': '/admin/fraud-detection/alerts/',
                    'icon': 'alerts',
                    'active': request.path.startswith('/admin/fraud-detection/alerts/')
                },
                {
                    'name': 'Analytics',
                    'url': '/admin/fraud-detection/analytics/',
                    'icon': 'analytics',
                    'active': request.path.startswith('/admin/fraud-detection/analytics/')
                },
                {
                    'name': 'Settings',
                    'url': '/admin/fraud-detection/settings/',
                    'icon': 'settings',
                    'active': request.path.startswith('/admin/fraud-detection/settings/')
                }
            ]
        
        elif feature_flag_manager.is_enabled('user_fraud_portal', user_id):
            context['show_fraud_nav'] = True
            
            # User navigation items
            context['fraud_nav_items'] = [
                {
                    'name': 'My Security',
                    'url': '/fraud-detection/security/',
                    'icon': 'security',
                    'active': request.path.startswith('/fraud-detection/security/')
                },
                {
                    'name': 'Activity Log',
                    'url': '/fraud-detection/activity/',
                    'icon': 'activity',
                    'active': request.path.startswith('/fraud-detection/activity/')
                },
                {
                    'name': 'Alerts',
                    'url': '/fraud-detection/alerts/',
                    'icon': 'alerts',
                    'active': request.path.startswith('/fraud-detection/alerts/')
                }
            ]
    
    return context


def fraud_detection_api_context(request) -> Dict[str, Any]:
    """
    Context processor for fraud detection API information.
    
    Args:
        request: HTTP request
        
    Returns:
        API context dictionary
    """
    context = {
        'fraud_api_config': {},
        'fraud_api_endpoints': [],
    }
    
    try:
        # API configuration
        context['fraud_api_config'] = {
            'version': getattr(settings, 'FRAUD_DETECTION_API_VERSION', 'v1'),
            'base_url': getattr(settings, 'FRAUD_DETECTION_API_URL', '/api/fraud-detection/'),
            'timeout': getattr(settings, 'FRAUD_DETECTION_API_TIMEOUT', 30),
            'rate_limit': getattr(settings, 'FRAUD_DETECTION_API_RATE_LIMIT', 100),
        }
        
        # Available endpoints
        context['fraud_api_endpoints'] = [
            {
                'name': 'Detect Fraud',
                'method': 'POST',
                'path': '/detect/',
                'description': 'Analyze transaction for fraud'
            },
            {
                'name': 'Risk Assessment',
                'method': 'GET',
                'path': '/risk-assessment/{user_id}/',
                'description': 'Get user risk assessment'
            },
            {
                'name': 'Create Case',
                'method': 'POST',
                'path': '/cases/',
                'description': 'Create new fraud case'
            },
            {
                'name': 'Get Alerts',
                'method': 'GET',
                'path': '/alerts/',
                'description': 'Get fraud alerts'
            },
            {
                'name': 'Analytics',
                'method': 'GET',
                'path': '/analytics/',
                'description': 'Get fraud analytics data'
            }
        ]
        
    except Exception as e:
        logger.error(f"Error getting fraud detection API context: {e}")
    
    return context


# Utility functions for context processors
def get_user_recent_fraud_activity(user_id: Union[int, str], days: int = 7) -> List[Dict[str, Any]]:
    """
    Get user's recent fraud activity.
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        List of recent activity
    """
    activity = []
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get recent alerts
        from api.fraud_detection.selectors import fraud_alert_selector
        recent_alerts = fraud_alert_selector.get_alerts_by_user(
            user_id, 
            limit=10,
            since_date=cutoff_date
        )
        
        for alert in recent_alerts:
            activity.append({
                'type': 'alert',
                'id': alert.pk,
                'description': alert.description,
                'severity_score': alert.severity_score,
                'created_at': alert.created_at,
                'acknowledged': alert.acknowledged
            })
        
        # Get recent cases
        from api.fraud_detection.selectors import fraud_case_selector
        recent_cases = fraud_case_selector.get_cases_by_user(
            user_id,
            limit=5,
            since_date=cutoff_date
        )
        
        for case in recent_cases:
            activity.append({
                'type': 'case',
                'id': case.pk,
                'description': case.description,
                'risk_score': case.risk_score,
                'status': case.status,
                'created_at': case.created_at
            })
        
        # Sort by creation date (newest first)
        activity.sort(key=lambda x: x['created_at'], reverse=True)
        
    except Exception as e:
        logger.error(f"Error getting user recent fraud activity for user {user_id}: {e}")
    
    return activity


def get_system_fraud_metrics() -> Dict[str, Any]:
    """
    Get system-wide fraud metrics.
    
    Returns:
        System metrics dictionary
    """
    metrics = {
        'total_cases': 0,
        'total_alerts': 0,
        'active_cases': 0,
        'unacknowledged_alerts': 0,
        'average_risk_score': 0,
        'system_health': 'unknown'
    }
    
    try:
        from api.fraud_detection.selectors import (
            fraud_case_selector, fraud_alert_selector
        )
        
        # Get counts
        metrics['total_cases'] = fraud_case_selector.get_total_count()
        metrics['total_alerts'] = fraud_alert_selector.get_total_count()
        metrics['active_cases'] = fraud_case_selector.get_cases_by_status('open').count()
        metrics['unacknowledged_alerts'] = fraud_alert_selector.get_unacknowledged_alerts().count()
        
        # Get average risk score
        analytics = get_fraud_analytics()
        overview = analytics.get_fraud_overview(period_days=7)
        
        if overview:
            metrics['average_risk_score'] = overview.get('summary_statistics', {}).get('average_risk_score', 0)
        
        # System health
        metrics['system_health'] = get_fraud_system_health()
        
    except Exception as e:
        logger.error(f"Error getting system fraud metrics: {e}")
    
    return metrics


# Context processor registration helper
def register_fraud_context_processors():
    """
    Register all fraud detection context processors.
    
    Returns:
        List of context processor functions
    """
    return [
        'api.fraud_detection.context_processors.fraud_detection_context',
        'api.fraud_detection.context_processors.admin_fraud_dashboard_context',
        'api.fraud_detection.context_processors.user_fraud_warnings_context',
        'api.fraud_detection.context_processors.fraud_detection_navigation_context',
        'api.fraud_detection.context_processors.fraud_detection_api_context',
    ]


# Export all context processors
__all__ = [
    'fraud_detection_context',
    'admin_fraud_dashboard_context',
    'user_fraud_warnings_context',
    'fraud_detection_navigation_context',
    'fraud_detection_api_context',
    'get_user_fraud_context',
    'get_fraud_statistics_context',
    'get_fraud_feature_flags_context',
    'get_fraud_system_health',
    'get_user_recent_fraud_activity',
    'get_system_fraud_metrics',
    'register_fraud_context_processors',
]
