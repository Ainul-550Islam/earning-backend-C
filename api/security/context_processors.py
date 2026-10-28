"""
Security Context Processors
Django context processors for security module
"""
from datetime import timedelta

import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .models import SecurityLog, SecurityIncident, ThreatIntelligence
from .utils import SecurityUtils
from .monitoring import monitoring_manager
from .feature_flags import feature_flag_manager
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.context_processors')


def security_context(request) -> Dict[str, Any]:
    """Main security context processor"""
    context = {}
    
    try:
        # Add user security context
        if request.user.is_authenticated:
            context.update(get_user_security_context(request.user))
        
        # Add system security context
        context.update(get_system_security_context())
        
        # Add feature flags
        context.update(get_security_feature_flags(request))
        
        # Add security alerts
        context.update(get_security_alerts(request))
        
        # Add security metrics
        context.update(get_security_metrics(request))
        
    except Exception as e:
        logger.error(f"Error in security context processor: {e}")
    
    return context


def get_user_security_context(user: User) -> Dict[str, Any]:
    """Get user-specific security context"""
    context = {
        'user_security': {}
    }
    
    try:
        # User risk score
        cache_key = f"user_security_context_{user.id}"
        cached_context = cache.get(cache_key)
        
        if cached_context:
            context['user_security'] = cached_context
            return context
        
        # Calculate user risk score
        risk_score = calculate_user_risk_score(user)
        
        # Get user devices
        user_devices = get_user_devices(user)
        
        # Get recent security events
        recent_events = get_user_security_events(user)
        
        # Check if user has active bans
        has_active_ban = check_user_bans(user)
        
        # Get user security settings
        security_settings = get_user_security_settings(user)
        
        user_security_data = {
            'risk_score': risk_score,
            'risk_level': get_risk_level(risk_score),
            'devices_count': len(user_devices),
            'trusted_devices_count': len([d for d in user_devices if d.get('is_trusted')]),
            'recent_events_count': len(recent_events),
            'has_active_ban': has_active_ban,
            'security_settings': security_settings,
            'last_security_check': timezone.now().isoformat()
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, user_security_data, 300)
        context['user_security'] = user_security_data
        
    except Exception as e:
        logger.error(f"Error getting user security context for user {user.id}: {e}")
        context['user_security'] = {'error': 'Unable to load security context'}
    
    return context


def get_system_security_context() -> Dict[str, Any]:
    """Get system-wide security context"""
    context = {
        'system_security': {}
    }
    
    try:
        cache_key = "system_security_context"
        cached_context = cache.get(cache_key)
        
        if cached_context:
            context['system_security'] = cached_context
            return context
        
        # Get system health
        system_health = get_system_health()
        
        # Get active incidents
        active_incidents = get_active_incidents()
        
        # Get active threats
        active_threats = get_active_threats()
        
        # Get security metrics
        security_metrics = get_system_security_metrics()
        
        # Get monitoring status
        monitoring_status = get_monitoring_status()
        
        system_security_data = {
            'system_health': system_health,
            'active_incidents_count': active_incidents,
            'active_threats_count': active_threats,
            'security_metrics': security_metrics,
            'monitoring_status': monitoring_status,
            'last_updated': timezone.now().isoformat()
        }
        
        # Cache for 1 minute
        cache.set(cache_key, system_security_data, 60)
        context['system_security'] = system_security_data
        
    except Exception as e:
        logger.error(f"Error getting system security context: {e}")
        context['system_security'] = {'error': 'Unable to load system security context'}
    
    return context


def get_security_feature_flags(request) -> Dict[str, Any]:
    """Get security feature flags"""
    context = {
        'security_features': {}
    }
    
    try:
        if request.user.is_authenticated:
            # Get user-specific feature flags
            user_flags = feature_flag_manager.get_user_flags(request.user)
            
            # Get global feature flags
            global_flags = feature_flag_manager.get_global_flags()
            
            context['security_features'] = {
                'user_flags': user_flags,
                'global_flags': global_flags
            }
        else:
            # Get anonymous user flags
            context['security_features'] = {
                'anonymous_flags': feature_flag_manager.get_anonymous_flags()
            }
        
    except Exception as e:
        logger.error(f"Error getting security feature flags: {e}")
        context['security_features'] = {'error': 'Unable to load feature flags'}
    
    return context


def get_security_alerts(request) -> Dict[str, Any]:
    """Get security alerts for the current user"""
    context = {
        'security_alerts': {
            'alerts': [],
            'count': 0
        }
    }
    
    try:
        if request.user.is_authenticated and request.user.is_staff:
            # Get security alerts for staff users
            alerts = get_staff_security_alerts(request.user)
            
            context['security_alerts'] = {
                'alerts': alerts,
                'count': len(alerts)
            }
        elif request.user.is_authenticated:
            # Get user-specific alerts
            alerts = get_user_security_alerts(request.user)
            
            context['security_alerts'] = {
                'alerts': alerts,
                'count': len(alerts)
            }
        
    except Exception as e:
        logger.error(f"Error getting security alerts: {e}")
        context['security_alerts'] = {'error': 'Unable to load security alerts'}
    
    return context


def get_security_metrics(request) -> Dict[str, Any]:
    """Get security metrics"""
    context = {
        'security_metrics': {}
    }
    
    try:
        # Get basic security metrics
        metrics = {
            'total_security_events_today': get_total_events_today(),
            'failed_login_attempts_today': get_failed_logins_today(),
            'active_incidents': get_active_incidents_count(),
            'high_risk_users': get_high_risk_users_count(),
            'blocked_ips_today': get_blocked_ips_count()
        }
        
        context['security_metrics'] = metrics
        
    except Exception as e:
        logger.error(f"Error getting security metrics: {e}")
        context['security_metrics'] = {'error': 'Unable to load security metrics'}
    
    return context


# Helper functions

def calculate_user_risk_score(user: User) -> float:
    """Calculate user risk score"""
    try:
        from .logic import security_logic_engine
        
        # Get recent security events for user
        recent_events = SecurityLog.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')[:10]
        
        if not recent_events.exists():
            return 10.0  # Low risk for users with no events
        
        # Calculate average risk score from recent events
        total_score = 0
        event_count = 0
        
        for event in recent_events:
            if event.risk_score:
                total_score += event.risk_score
                event_count += 1
        
        if event_count == 0:
            return 10.0
        
        average_score = total_score / event_count
        
        # Apply time decay (older events have less impact)
        time_decay = 0.8  # 80% of recent events weight
        
        return min(100.0, max(0.0, average_score * time_decay))
        
    except Exception as e:
        logger.error(f"Error calculating risk score for user {user.id}: {e}")
        return 50.0  # Medium risk as fallback


def get_risk_level(risk_score: float) -> str:
    """Get risk level from score"""
    if risk_score >= 80:
        return 'critical'
    elif risk_score >= 60:
        return 'high'
    elif risk_score >= 40:
        return 'medium'
    else:
        return 'low'


def get_user_devices(user: User) -> list:
    """Get user devices"""
    try:
        from .models import DeviceInfo
        
        devices = DeviceInfo.objects.filter(user=user).order_by('-last_activity')
        
        device_list = []
        for device in devices:
            device_list.append({
                'id': str(device.id),
                'device_type': device.device_type,
                'device_brand': device.device_brand,
                'is_trusted': device.is_trusted,
                'risk_score': device.risk_score,
                'last_activity': device.last_activity.isoformat() if device.last_activity else None
            })
        
        return device_list
        
    except Exception as e:
        logger.error(f"Error getting devices for user {user.id}: {e}")
        return []


def get_user_security_events(user: User) -> list:
    """Get user security events"""
    try:
        events = SecurityLog.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')[:5]
        
        event_list = []
        for event in events:
            event_list.append({
                'id': str(event.id),
                'security_type': event.security_type,
                'severity': event.severity,
                'description': event.description,
                'created_at': event.created_at.isoformat()
            })
        
        return event_list
        
    except Exception as e:
        logger.error(f"Error getting security events for user {user.id}: {e}")
        return []


def check_user_bans(user: User) -> bool:
    """Check if user has active bans"""
    try:
        from .models import UserBan
        
        return UserBan.objects.filter(user=user, is_active=True).exists()
        
    except Exception as e:
        logger.error(f"Error checking bans for user {user.id}: {e}")
        return False


def get_user_security_settings(user: User) -> dict:
    """Get user security settings"""
    try:
        # This would get user-specific security settings
        # For now, return basic settings
        return {
            'two_factor_enabled': getattr(user, 'two_factor_enabled', False),
            'email_notifications': getattr(user, 'security_email_notifications', True),
            'sms_notifications': getattr(user, 'security_sms_notifications', False),
            'trusted_devices_only': getattr(user, 'trusted_devices_only', False)
        }
        
    except Exception as e:
        logger.error(f"Error getting security settings for user {user.id}: {e}")
        return {}


def get_system_health() -> dict:
    """Get system health status"""
    try:
        health_data = monitoring_manager.get_system_health()
        
        return {
            'status': health_data.get('status', 'unknown'),
            'overall_score': health_data.get('overall_score', 0),
            'checks': health_data.get('checks', {}),
            'last_check': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {
            'status': 'error',
            'overall_score': 0,
            'error': str(e)
        }


def get_active_incidents() -> int:
    """Get count of active incidents"""
    try:
        return SecurityIncident.objects.filter(
            status__in=['open', 'investigating']
        ).count()
        
    except Exception as e:
        logger.error(f"Error getting active incidents: {e}")
        return 0


def get_active_threats() -> int:
    """Get count of active threats"""
    try:
        return ThreatIntelligence.objects.filter(is_active=True).count()
        
    except Exception as e:
        logger.error(f"Error getting active threats: {e}")
        return 0


def get_system_security_metrics() -> dict:
    """Get system security metrics"""
    try:
        from datetime import timedelta
        
        # Get metrics for the last 24 hours
        start_time = timezone.now() - timedelta(hours=24)
        
        total_events = SecurityLog.objects.filter(created_at__gte=start_time).count()
        critical_events = SecurityLog.objects.filter(
            created_at__gte=start_time,
            severity='critical'
        ).count()
        high_events = SecurityLog.objects.filter(
            created_at__gte=start_time,
            severity='high'
        ).count()
        
        return {
            'total_events_24h': total_events,
            'critical_events_24h': critical_events,
            'high_events_24h': high_events,
            'average_risk_score': calculate_average_risk_score(),
            'incident_response_time': get_average_incident_response_time()
        }
        
    except Exception as e:
        logger.error(f"Error getting system security metrics: {e}")
        return {}


def get_monitoring_status() -> dict:
    """Get monitoring status"""
    try:
        return monitoring_manager.get_monitor_status()
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        return {'status': 'error', 'error': str(e)}


def get_staff_security_alerts(user: User) -> list:
    """Get security alerts for staff users"""
    try:
        alerts = []
        
        # Check for critical incidents
        critical_incidents = SecurityIncident.objects.filter(
            severity='critical',
            status__in=['open', 'investigating']
        ).order_by('-opened_at')[:5]
        
        for incident in critical_incidents:
            alerts.append({
                'type': 'critical_incident',
                'title': f'Critical Incident: {incident.title}',
                'message': incident.description[:100] + '...',
                'severity': 'critical',
                'created_at': incident.opened_at.isoformat(),
                'url': f'/security/incidents/{incident.id}/'
            })
        
        # Check for high-risk users
        from .models import DeviceInfo
        
        high_risk_devices = DeviceInfo.objects.filter(
            risk_score__gte=70,
            is_trusted=False
        ).order_by('-risk_score')[:5]
        
        for device in high_risk_devices:
            alerts.append({
                'type': 'high_risk_device',
                'title': f'High Risk Device: {device.device_type}',
                'message': f'Device risk score: {device.risk_score}',
                'severity': 'high',
                'created_at': device.last_activity.isoformat() if device.last_activity else None,
                'url': f'/security/devices/{device.id}/'
            })
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting staff security alerts: {e}")
        return []


def get_user_security_alerts(user: User) -> list:
    """Get security alerts for regular users"""
    try:
        alerts = []
        
        # Check for account issues
        if check_user_bans(user):
            alerts.append({
                'type': 'account_banned',
                'title': 'Account Restricted',
                'message': 'Your account has been restricted due to security concerns.',
                'severity': 'critical',
                'created_at': timezone.now().isoformat(),
                'url': '/security/account-status/'
            })
        
        # Check for new devices
        recent_devices = get_user_devices(user)
        untrusted_devices = [d for d in recent_devices if not d.get('is_trusted')]
        
        if untrusted_devices:
            alerts.append({
                'type': 'untrusted_device',
                'title': 'New Device Detected',
                'message': f'{len(untrusted_devices)} new device(s) detected on your account.',
                'severity': 'medium',
                'created_at': untrusted_devices[0].get('last_activity'),
                'url': '/security/devices/'
            })
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting user security alerts: {e}")
        return []


def get_total_events_today() -> int:
    """Get total security events today"""
    try:
        today = timezone.now().date()
        return SecurityLog.objects.filter(
            created_at__date=today
        ).count()
        
    except Exception as e:
        logger.error(f"Error getting total events today: {e}")
        return 0


def get_failed_logins_today() -> int:
    """Get failed login attempts today"""
    try:
        today = timezone.now().date()
        return SecurityLog.objects.filter(
            created_at__date=today,
            security_type='failed_login'
        ).count()
        
    except Exception as e:
        logger.error(f"Error getting failed logins today: {e}")
        return 0


def get_active_incidents_count() -> int:
    """Get active incidents count"""
    return get_active_incidents()


def get_high_risk_users_count() -> int:
    """Get high risk users count"""
    try:
        from .models import DeviceInfo
        
        # Count users with high-risk devices
        high_risk_users = DeviceInfo.objects.filter(
            risk_score__gte=70
        ).values('user').distinct().count()
        
        return high_risk_users
        
    except Exception as e:
        logger.error(f"Error getting high risk users count: {e}")
        return 0


def get_blocked_ips_count() -> int:
    """Get blocked IPs count today"""
    try:
        today = timezone.now().date()
        return SecurityLog.objects.filter(
            created_at__date=today,
            security_type='ip_blocked'
        ).count()
        
    except Exception as e:
        logger.error(f"Error getting blocked IPs count: {e}")
        return 0


def calculate_average_risk_score() -> float:
    """Calculate average risk score"""
    try:
        from datetime import timedelta
        
        start_time = timezone.now() - timedelta(hours=24)
        
        events_with_score = SecurityLog.objects.filter(
            created_at__gte=start_time,
            risk_score__isnull=False
        )
        
        if not events_with_score.exists():
            return 0.0
        
        total_score = sum(event.risk_score for event in events_with_score)
        return total_score / events_with_score.count()
        
    except Exception as e:
        logger.error(f"Error calculating average risk score: {e}")
        return 0.0


def get_average_incident_response_time() -> float:
    """Get average incident response time in minutes"""
    try:
        from datetime import timedelta
        
        resolved_incidents = SecurityIncident.objects.filter(
            status='resolved',
            resolved_at__isnull=False
        )
        
        if not resolved_incidents.exists():
            return 0.0
        
        total_response_time = 0
        count = 0
        
        for incident in resolved_incidents:
            if incident.opened_at and incident.resolved_at:
                response_time = incident.resolved_at - incident.opened_at
                total_response_time += response_time.total_seconds() / 60  # Convert to minutes
                count += 1
        
        if count == 0:
            return 0.0
        
        return total_response_time / count
        
    except Exception as e:
        logger.error(f"Error calculating average incident response time: {e}")
        return 0.0


# Export context processors
__all__ = [
    'security_context',
    'get_user_security_context',
    'get_system_security_context',
    'get_security_feature_flags',
    'get_security_alerts',
    'get_security_metrics'
]