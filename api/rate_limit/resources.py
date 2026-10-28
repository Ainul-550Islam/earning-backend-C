# api/rate_limit/resources.py
"""
Resource classes for rate limit module.

Provides resource management and API resource representations.
"""
from django.db.models import Count
from django.db.models import F
from django.db.models import Q

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.services import RateLimitService
from api.rate_limit.logic import HealthMonitoring

logger = logging.getLogger(__name__)
User = get_user_model()


class RateLimitResource:
    """
    Base class for rate limit resources.
    """
    
    def __init__(self, model_class):
        self.model_class = model_class
        self.cache_timeout = 300  # 5 minutes
    
    def get_resource_data(self, instance: Any) -> Dict[str, Any]:
        """
        Get resource data for an instance.
        
        Args:
            instance: Model instance
            
        Returns:
            Resource data dictionary
        """
        data = {}
        
        # Add basic fields
        for field in instance._meta.fields:
            field_name = field.name
            value = getattr(instance, field_name)
            
            # Handle different field types
            if isinstance(value, datetime):
                data[field_name] = value.isoformat()
            elif hasattr(value, 'id'):  # Foreign key
                data[field_name] = value.id
            else:
                data[field_name] = value
        
        return data
    
    def get_resource_list(self, queryset) -> List[Dict[str, Any]]:
        """
        Get resource data for a queryset.
        
        Args:
            queryset: QuerySet of instances
            
        Returns:
            List of resource data dictionaries
        """
        return [self.get_resource_data(instance) for instance in queryset]
    
    def cache_resource(self, key: str, data: Any):
        """
        Cache resource data.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        cache.set(key, data, self.cache_timeout)
    
    def get_cached_resource(self, key: str) -> Optional[Any]:
        """
        Get cached resource data.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None
        """
        return cache.get(key)


class RateLimitConfigResource(RateLimitResource):
    """
    Resource for RateLimitConfig model.
    """
    
    def __init__(self):
        super().__init__(RateLimitConfig)
    
    def get_resource_data(self, instance: RateLimitConfig) -> Dict[str, Any]:
        """
        Get rate limit config resource data.
        
        Args:
            instance: RateLimitConfig instance
            
        Returns:
            Resource data dictionary
        """
        data = super().get_resource_data(instance)
        
        # Add computed fields
        data.update({
            'hit_count': instance.hit_count or 0,
            'block_count': instance.block_count or 0,
            'block_rate': (instance.block_count / max(instance.hit_count, 1)) * 100 if instance.hit_count else 0,
            'is_active': instance.is_active,
            'config_summary': f"{instance.requests_per_unit} per {instance.time_unit}"
        })
        
        # Add related data
        if instance.user:
            data['user_username'] = instance.user.username
        
        return data
    
    def get_config_stats(self) -> Dict[str, Any]:
        """
        Get configuration statistics.
        
        Returns:
            Configuration statistics
        """
        cache_key = 'rate_limit_config_stats'
        cached_stats = self.get_cached_resource(cache_key)
        
        if cached_stats:
            return cached_stats
        
        stats = {
            'total_configs': RateLimitConfig.objects.count(),
            'active_configs': RateLimitConfig.objects.filter(is_active=True).count(),
            'inactive_configs': RateLimitConfig.objects.filter(is_active=False).count(),
            'configs_by_type': {},
            'configs_by_time_unit': {},
            'high_block_rate_configs': 0,
            'unused_configs': 0
        }
        
        # Configs by type
        for config_type in ['user', 'ip', 'endpoint', 'global', 'referral', 'task', 'offer']:
            stats['configs_by_type'][config_type] = RateLimitConfig.objects.filter(
                rate_limit_type=config_type
            ).count()
        
        # Configs by time unit
        for time_unit in ['second', 'minute', 'hour', 'day']:
            stats['configs_by_time_unit'][time_unit] = RateLimitConfig.objects.filter(
                time_unit=time_unit
            ).count()
        
        # High block rate configs
        stats['high_block_rate_configs'] = RateLimitConfig.objects.filter(
            hit_count__gt=100,
            block_count__gt=F('hit_count') * 0.2  # More than 20% block rate
        ).count()
        
        # Unused configs (no hits)
        stats['unused_configs'] = RateLimitConfig.objects.filter(
            Q(hit_count=0) | Q(hit_count__isnull=True)
        ).count()
        
        self.cache_resource(cache_key, stats)
        return stats


class RateLimitLogResource(RateLimitResource):
    """
    Resource for RateLimitLog model.
    """
    
    def __init__(self):
        super().__init__(RateLimitLog)
    
    def get_resource_data(self, instance: RateLimitLog) -> Dict[str, Any]:
        """
        Get rate limit log resource data.
        
        Args:
            instance: RateLimitLog instance
            
        Returns:
            Resource data dictionary
        """
        data = super().get_resource_data(instance)
        
        # Add computed fields
        data.update({
            'timestamp_formatted': instance.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_blocked': instance.status == 'blocked',
            'is_suspicious': instance.suspicion_score > 50,
            'risk_level': self._get_risk_level(instance.suspicion_score)
        })
        
        # Add related data
        if instance.user:
            data['user_username'] = instance.user.username
        
        if instance.config:
            data['config_name'] = instance.config.name
        
        return data
    
    def _get_risk_level(self, suspicion_score: int) -> str:
        """Get risk level based on suspicion score."""
        if suspicion_score >= 80:
            return 'critical'
        elif suspicion_score >= 60:
            return 'high'
        elif suspicion_score >= 40:
            return 'medium'
        elif suspicion_score >= 20:
            return 'low'
        else:
            return 'minimal'
    
    def get_log_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get log analytics for the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Analytics data
        """
        cache_key = f'rate_limit_log_analytics_{hours}h'
        cached_analytics = self.get_cached_resource(cache_key)
        
        if cached_analytics:
            return cached_analytics
        
        since_time = timezone.now() - timedelta(hours=hours)
        logs = RateLimitLog.objects.filter(timestamp__gte=since_time)
        
        analytics = {
            'period_hours': hours,
            'total_requests': logs.count(),
            'blocked_requests': logs.filter(status='blocked').count(),
            'allowed_requests': logs.filter(status='allowed').count(),
            'unique_ips': logs.values('ip_address').distinct().count(),
            'unique_users': logs.values('user').distinct().count(),
            'block_rate': 0,
            'top_endpoints': [],
            'top_ips': [],
            'hourly_distribution': [],
            'status_distribution': [],
            'suspicious_requests': logs.filter(suspicion_score__gt=50).count()
        }
        
        # Calculate block rate
        if analytics['total_requests'] > 0:
            analytics['block_rate'] = (analytics['blocked_requests'] / analytics['total_requests']) * 100
        
        # Top endpoints
        analytics['top_endpoints'] = list(
            logs.values('endpoint')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
            .values('endpoint', 'count')
        )
        
        # Top IPs
        analytics['top_ips'] = list(
            logs.values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
            .values('ip_address', 'count')
        )
        
        # Hourly distribution
        analytics['hourly_distribution'] = list(
            logs.extra({'hour': "strftime('%%H', timestamp)"})
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )
        
        # Status distribution
        analytics['status_distribution'] = list(
            logs.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values('status', 'count')
        )
        
        self.cache_resource(cache_key, analytics)
        return analytics


class UserRateLimitProfileResource(RateLimitResource):
    """
    Resource for UserRateLimitProfile model.
    """
    
    def __init__(self):
        super().__init__(UserRateLimitProfile)
    
    def get_resource_data(self, instance: UserRateLimitProfile) -> Dict[str, Any]:
        """
        Get user rate limit profile resource data.
        
        Args:
            instance: UserRateLimitProfile instance
            
        Returns:
            Resource data dictionary
        """
        data = super().get_resource_data(instance)
        
        # Add computed fields
        data.update({
            'username': instance.user.username,
            'email': instance.user.email,
            'is_premium_user': instance.is_premium,
            'premium_status': self._get_premium_status(instance),
            'health_status': self._get_health_status(instance.api_health_score),
            'risk_level': self._get_risk_level(instance.suspicion_score),
            'usage_stats': {
                'total_requests': instance.total_requests,
                'blocked_requests': instance.blocked_requests,
                'block_rate': (instance.blocked_requests / max(instance.total_requests, 1)) * 100,
                'daily_usage': instance.daily_usage,
                'hourly_usage': instance.hourly_usage,
                'current_usage': instance.current_usage
            },
            'limits': {
                'custom_daily_limit': instance.custom_daily_limit,
                'custom_hourly_limit': instance.custom_hourly_limit,
                'daily_usage_percentage': (instance.daily_usage / max(instance.custom_daily_limit, 1)) * 100,
                'hourly_usage_percentage': (instance.hourly_usage / max(instance.custom_hourly_limit, 1)) * 100
            }
        })
        
        return data
    
    def _get_premium_status(self, instance: UserRateLimitProfile) -> str:
        """Get premium status description."""
        if not instance.is_premium:
            return 'standard'
        elif instance.premium_until and instance.premium_until > timezone.now():
            return 'active'
        elif instance.premium_until and instance.premium_until <= timezone.now():
            return 'expired'
        else:
            return 'lifetime'
    
    def _get_health_status(self, health_score: int) -> str:
        """Get health status based on score."""
        if health_score >= 80:
            return 'excellent'
        elif health_score >= 60:
            return 'good'
        elif health_score >= 40:
            return 'fair'
        elif health_score >= 20:
            return 'poor'
        else:
            return 'critical'
    
    def _get_risk_level(self, suspicion_score: int) -> str:
        """Get risk level based on suspicion score."""
        if suspicion_score >= 80:
            return 'critical'
        elif suspicion_score >= 60:
            return 'high'
        elif suspicion_score >= 40:
            return 'medium'
        elif suspicion_score >= 20:
            return 'low'
        else:
            return 'minimal'
    
    def get_user_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive user summary.
        
        Args:
            user_id: User ID
            
        Returns:
            User summary data
        """
        try:
            profile = UserRateLimitProfile.objects.get(user_id=user_id)
            return self.get_resource_data(profile)
        except UserRateLimitProfile.DoesNotExist:
            return {'error': 'User profile not found'}


class SystemHealthResource(RateLimitResource):
    """
    Resource for system health monitoring.
    """
    
    def __init__(self):
        super().__init__(None)  # No specific model
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health data.
        
        Returns:
            System health data
        """
        cache_key = 'rate_limit_system_health'
        cached_health = self.get_cached_resource(cache_key)
        
        if cached_health:
            return cached_health
        
        health_monitor = HealthMonitoring()
        health_data = health_monitor.calculate_system_health()
        
        # Add additional metrics
        health_data.update({
            'performance_metrics': health_monitor.get_performance_metrics(),
            'alert_count': self._get_active_alert_count(),
            'recent_issues': self._get_recent_issues(),
            'recommendations': self._get_health_recommendations(health_data)
        })
        
        self.cache_resource(cache_key, health_data)
        return health_data
    
    def _get_active_alert_count(self) -> int:
        """Get count of active alerts."""
        # This would integrate with an alert system
        # For now, return a placeholder
        return 0
    
    def _get_recent_issues(self) -> List[Dict[str, Any]]:
        """Get recent system issues."""
        # This would query system logs or issue tracking
        # For now, return empty list
        return []
    
    def _get_health_recommendations(self, health_data: Dict[str, Any]) -> List[str]:
        """Get health recommendations based on system status."""
        recommendations = []
        
        health_score = health_data.get('health_score', 0)
        block_rate = health_data.get('hourly_block_rate', 0)
        active_blocks = health_data.get('active_blocks', 0)
        
        if health_score < 50:
            recommendations.append("System health is critical - immediate attention required")
        
        if block_rate > 20:
            recommendations.append("High block rate detected - consider adjusting rate limits")
        
        if active_blocks > 1000:
            recommendations.append("High number of active IP blocks - review blocking policies")
        
        if health_score > 80:
            recommendations.append("System health is excellent - current configuration is optimal")
        
        return recommendations


class AbuseReportResource(RateLimitResource):
    """
    Resource for AbuseReport model.
    """
    
    def __init__(self):
        super().__init__(AbuseReport)
    
    def get_resource_data(self, instance: AbuseReport) -> Dict[str, Any]:
        """
        Get abuse report resource data.
        
        Args:
            instance: AbuseReport instance
            
        Returns:
            Resource data dictionary
        """
        data = super().get_resource_data(instance)
        
        # Add computed fields
        data.update({
            'severity_level': self._get_severity_level(instance.severity),
            'urgency': self._get_urgency(instance),
            'is_action_required': instance.severity >= 4 and not instance.is_investigated,
            'days_since_creation': (timezone.now() - instance.created_at).days
        })
        
        # Add related data
        if instance.user:
            data['user_username'] = instance.user.username
        
        if instance.investigated_by:
            data['investigated_by_username'] = instance.investigated_by.username
        
        return data
    
    def _get_severity_level(self, severity: int) -> str:
        """Get severity level description."""
        severity_map = {
            1: 'very_low',
            2: 'low',
            3: 'medium',
            4: 'high',
            5: 'critical'
        }
        return severity_map.get(severity, 'unknown')
    
    def _get_urgency(self, instance: AbuseReport) -> str:
        """Get urgency level."""
        if instance.severity >= 4 and not instance.is_investigated:
            return 'urgent'
        elif instance.severity >= 3 and not instance.is_investigated:
            return 'normal'
        else:
            return 'low'


class IPBlockListResource(RateLimitResource):
    """
    Resource for IPBlockList model.
    """
    
    def __init__(self):
        super().__init__(IPBlockList)
    
    def get_resource_data(self, instance: IPBlockList) -> Dict[str, Any]:
        """
        Get IP block resource data.
        
        Args:
            instance: IPBlockList instance
            
        Returns:
            Resource data dictionary
        """
        data = super().get_resource_data(instance)
        
        # Add computed fields
        data.update({
            'is_expired': not instance.permanent and instance.expires_at and instance.expires_at < timezone.now(),
            'days_until_expiry': self._get_days_until_expiry(instance),
            'block_duration_days': self._get_block_duration(instance),
            'is_security_block': instance.block_reason in ['abuse', 'security', 'malware', 'auto_detection']
        })
        
        # Add related data
        if instance.created_by:
            data['created_by_username'] = instance.created_by.username
        
        return data
    
    def _get_days_until_expiry(self, instance: IPBlockList) -> Optional[int]:
        """Get days until block expires."""
        if instance.permanent or not instance.expires_at:
            return None
        
        delta = instance.expires_at - timezone.now()
        return max(0, delta.days)
    
    def _get_block_duration(self, instance: IPBlockList) -> Optional[int]:
        """Get block duration in days."""
        if instance.permanent:
            return None
        
        if instance.expires_at and instance.created_at:
            delta = instance.expires_at - instance.created_at
            return delta.days
        
        return None


# Export resource classes
__all__ = [
    'RateLimitResource',
    'RateLimitConfigResource',
    'RateLimitLogResource',
    'UserRateLimitProfileResource',
    'SystemHealthResource',
    'AbuseReportResource',
    'IPBlockListResource'
]
