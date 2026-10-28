# api/rate_limit/selectors.py
"""
Selectors for rate limit module.

Provides query selectors for complex database operations.
"""
from django.db import models
from django.db.models import QuerySet

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Window
from django.db.models.functions import Trunc, Extract, Coalesce, Cast
from django.db.models import Case, When, Value, IntegerField

from api.rate_limit.models import RateLimitLog, RateLimitConfig, UserRateLimitProfile, AbuseReport, IPBlockList

logger = logging.getLogger(__name__)


class RateLimitLogSelector:
    """
    Selector for RateLimitLog queries.
    """
    
    def __init__(self):
        self.model = RateLimitLog
    
    def get_recent_logs(self, hours: int = 24, user_id: int = None) -> 'QuerySet':
        """
        Get recent log entries.
        
        Args:
            hours: Number of hours to look back
            user_id: Optional user ID filter
            
        Returns:
            QuerySet of recent logs
        """
        since_time = timezone.now() - timedelta(hours=hours)
        queryset = self.model.objects.filter(timestamp__gte=since_time)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.order_by('-timestamp')
    
    def get_blocked_logs(self, hours: int = 24, ip_address: str = None) -> 'QuerySet':
        """
        Get blocked log entries.
        
        Args:
            hours: Number of hours to look back
            ip_address: Optional IP address filter
            
        Returns:
            QuerySet of blocked logs
        """
        since_time = timezone.now() - timedelta(hours=hours)
        queryset = self.model.objects.filter(
            timestamp__gte=since_time,
            status='blocked'
        )
        
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        return queryset.order_by('-timestamp')
    
    def get_suspicious_logs(self, min_score: int = 50, hours: int = 24) -> 'QuerySet':
        """
        Get suspicious log entries.
        
        Args:
            min_score: Minimum suspicion score
            hours: Number of hours to look back
            
        Returns:
            QuerySet of suspicious logs
        """
        since_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(
            timestamp__gte=since_time,
            suspicion_score__gte=min_score
        ).order_by('-suspicion_score', '-timestamp')
    
    def get_logs_by_endpoint(self, endpoint: str, hours: int = 24) -> 'QuerySet':
        """
        Get logs for specific endpoint.
        
        Args:
            endpoint: Endpoint path
            hours: Number of hours to look back
            
        Returns:
            QuerySet of endpoint logs
        """
        since_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(
            timestamp__gte=since_time,
            endpoint=endpoint
        ).order_by('-timestamp')
    
    def get_top_ips_by_requests(self, limit: int = 10, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get top IP addresses by request count.
        
        Args:
            limit: Number of results to return
            hours: Number of hours to look back
            
        Returns:
            List of IP statistics
        """
        since_time = timezone.now() - timedelta(hours=hours)
        
        return list(
            self.model.objects.filter(timestamp__gte=since_time)
            .values('ip_address')
            .annotate(
                request_count=Count('id'),
                blocked_count=Count('id', filter=Q(status='blocked')),
                avg_suspicion_score=Avg('suspicion_score')
            )
            .order_by('-request_count')[:limit]
        )
    
    def get_top_endpoints_by_requests(self, limit: int = 10, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get top endpoints by request count.
        
        Args:
            limit: Number of results to return
            hours: Number of hours to look back
            
        Returns:
            List of endpoint statistics
        """
        since_time = timezone.now() - timedelta(hours=hours)
        
        return list(
            self.model.objects.filter(timestamp__gte=since_time)
            .values('endpoint')
            .annotate(
                request_count=Count('id'),
                blocked_count=Count('id', filter=Q(status='blocked')),
                unique_users=Count('user', distinct=True),
                unique_ips=Count('ip_address', distinct=True)
            )
            .order_by('-request_count')[:limit]
        )
    
    def get_hourly_distribution(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get hourly request distribution.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            List of hourly statistics
        """
        since_time = timezone.now() - timedelta(hours=hours)
        
        return list(
            self.model.objects.filter(timestamp__gte=since_time)
            .extra({'hour': "strftime('%%H', timestamp)"})
            .values('hour')
            .annotate(
                total_requests=Count('id'),
                blocked_requests=Count('id', filter=Q(status='blocked')),
                allowed_requests=Count('id', filter=Q(status='allowed'))
            )
            .order_by('hour')
        )
    
    def get_user_activity_summary(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """
        Get activity summary for a user.
        
        Args:
            user_id: User ID
            days: Number of days to analyze
            
        Returns:
            User activity summary
        """
        since_time = timezone.now() - timedelta(days=days)
        
        logs = self.model.objects.filter(
            user_id=user_id,
            timestamp__gte=since_time
        )
        
        return {
            'total_requests': logs.count(),
            'blocked_requests': logs.filter(status='blocked').count(),
            'allowed_requests': logs.filter(status='allowed').count(),
            'block_rate': (logs.filter(status='blocked').count() / max(logs.count(), 1)) * 100,
            'avg_suspicion_score': logs.aggregate(avg=Avg('suspicion_score'))['avg'] or 0,
            'unique_endpoints': logs.values('endpoint').distinct().count(),
            'last_request': logs.order_by('-timestamp').first().timestamp if logs.exists() else None,
            'peak_hour': logs.extra({'hour': "strftime('%%H', timestamp)"}).values('hour').annotate(count=Count('id')).order_by('-count').first()['hour'] if logs.exists() else None
        }


class RateLimitConfigSelector:
    """
    Selector for RateLimitConfig queries.
    """
    
    def __init__(self):
        self.model = RateLimitConfig
    
    def get_active_configs(self) -> 'QuerySet':
        """Get all active configurations."""
        return self.model.objects.filter(is_active=True)
    
    def get_configs_by_type(self, rate_limit_type: str) -> 'QuerySet':
        """
        Get configurations by type.
        
        Args:
            rate_limit_type: Type of rate limit
            
        Returns:
            QuerySet of configurations
        """
        return self.model.objects.filter(
            rate_limit_type=rate_limit_type,
            is_active=True
        )
    
    def get_user_configs(self, user_id: int) -> 'QuerySet':
        """
        Get configurations applicable to a user.
        
        Args:
            user_id: User ID
            
        Returns:
            QuerySet of applicable configurations
        """
        return self.model.objects.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='user', user_id=user_id) |
            Q(rate_limit_type='endpoint') |
            Q(rate_limit_type='ip', ip_address__isnull=True)
        ).filter(is_active=True)
    
    def get_ip_configs(self, ip_address: str) -> 'QuerySet':
        """
        Get configurations applicable to an IP address.
        
        Args:
            ip_address: IP address
            
        Returns:
            QuerySet of applicable configurations
        """
        return self.model.objects.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='ip', ip_address=ip_address) |
            Q(rate_limit_type='endpoint') |
            Q(rate_limit_type='user', user__isnull=True)
        ).filter(is_active=True)
    
    def get_endpoint_configs(self, endpoint: str) -> 'QuerySet':
        """
        Get configurations applicable to an endpoint.
        
        Args:
            endpoint: Endpoint path
            
        Returns:
            QuerySet of applicable configurations
        """
        return self.model.objects.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='endpoint', endpoint=endpoint) |
            Q(rate_limit_type='user', user__isnull=True) |
            Q(rate_limit_type='ip', ip_address__isnull=True)
        ).filter(is_active=True)
    
    def get_configs_with_stats(self) -> 'QuerySet':
        """
        Get configurations with usage statistics.
        
        Returns:
            QuerySet with annotated statistics
        """
        return self.model.objects.annotate(
            hit_count=Coalesce(F('hit_count'), Value(0)),
            block_count=Coalesce(F('block_count'), Value(0)),
            block_rate=Case(
                When(hit_count__gt=0, then=F('block_count') * 100.0 / F('hit_count')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        ).order_by('-hit_count')
    
    def get_high_block_rate_configs(self, threshold: float = 20.0) -> 'QuerySet':
        """
        Get configurations with high block rates.
        
        Args:
            threshold: Block rate threshold percentage
            
        Returns:
            QuerySet of high block rate configurations
        """
        return self.get_configs_with_stats().filter(block_rate__gte=threshold)
    
    def get_unused_configs(self, days: int = 30) -> 'QuerySet':
        """
        Get configurations that haven't been used.
        
        Args:
            days: Number of days to check
            
        Returns:
            QuerySet of unused configurations
        """
        return self.model.objects.filter(
            Q(hit_count=0) | Q(hit_count__isnull=True),
            is_active=True
        )


class UserRateLimitProfileSelector:
    """
    Selector for UserRateLimitProfile queries.
    """
    
    def __init__(self):
        self.model = UserRateLimitProfile
    
    def get_premium_users(self) -> 'QuerySet':
        """Get premium users."""
        return self.model.objects.filter(is_premium=True)
    
    def get_suspicious_users(self, min_score: int = 50) -> 'QuerySet':
        """
        Get suspicious users.
        
        Args:
            min_score: Minimum suspicion score
            
        Returns:
            QuerySet of suspicious users
        """
        return self.model.objects.filter(suspicion_score__gte=min_score)
    
    def get_high_risk_users(self, min_suspicion: int = 70, max_health: int = 30) -> 'QuerySet':
        """
        Get high risk users.
        
        Args:
            min_suspicion: Minimum suspicion score
            max_health: Maximum health score
            
        Returns:
            QuerySet of high risk users
        """
        return self.model.objects.filter(
            suspicion_score__gte=min_suspicion,
            api_health_score__lte=max_health
        )
    
    def get_inactive_users(self, days: int = 30) -> 'QuerySet':
        """
        Get inactive users.
        
        Args:
            days: Number of days of inactivity
            
        Returns:
            QuerySet of inactive users
        """
        since_time = timezone.now() - timedelta(days=days)
        return self.model.objects.filter(
            last_request_at__lt=since_time
        )
    
    def get_users_by_usage(self, min_requests: int = 1000) -> 'QuerySet':
        """
        Get users by minimum request count.
        
        Args:
            min_requests: Minimum request count
            
        Returns:
            QuerySet of users with high usage
        """
        return self.model.objects.filter(total_requests__gte=min_requests)
    
    def get_users_with_health_scores(self) -> 'QuerySet':
        """
        Get users with health score categorization.
        
        Returns:
            QuerySet with health score categories
        """
        return self.model.objects.annotate(
            health_category=Case(
                When(api_health_score__gte=80, then=Value('excellent')),
                When(api_health_score__gte=60, then=Value('good')),
                When(api_health_score__gte=40, then=Value('fair')),
                When(api_health_score__gte=20, then=Value('poor')),
                default=Value('critical'),
                output_field=models.CharField()
            ),
            risk_category=Case(
                When(suspicion_score__gte=80, then=Value('critical')),
                When(suspicion_score__gte=60, then=Value('high')),
                When(suspicion_score__gte=40, then=Value('medium')),
                When(suspicion_score__gte=20, then=Value('low')),
                default=Value('minimal'),
                output_field=models.CharField()
            )
        )
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Get overall usage statistics.
        
        Returns:
            Usage statistics
        """
        return self.model.objects.aggregate(
            total_users=Count('id'),
            premium_users=Count('id', filter=Q(is_premium=True)),
            avg_health_score=Avg('api_health_score'),
            avg_suspicion_score=Avg('suspicion_score'),
            total_requests=Sum('total_requests'),
            total_blocked=Sum('blocked_requests'),
            avg_daily_usage=Avg('daily_usage'),
            avg_hourly_usage=Avg('hourly_usage')
        )


class AbuseReportSelector:
    """
    Selector for AbuseReport queries.
    """
    
    def __init__(self):
        self.model = AbuseReport
    
    def get_uninvestigated_reports(self) -> 'QuerySet':
        """Get uninvestigated abuse reports."""
        return self.model.objects.filter(is_investigated=False)
    
    def get_high_severity_reports(self, min_severity: int = 4) -> 'QuerySet':
        """
        Get high severity abuse reports.
        
        Args:
            min_severity: Minimum severity level
            
        Returns:
            QuerySet of high severity reports
        """
        return self.model.objects.filter(severity__gte=min_severity)
    
    def get_reports_by_type(self, abuse_type: str) -> 'QuerySet':
        """
        Get reports by abuse type.
        
        Args:
            abuse_type: Type of abuse
            
        Returns:
            QuerySet of abuse reports
        """
        return self.model.objects.filter(abuse_type=abuse_type)
    
    def get_recent_reports(self, hours: int = 24) -> 'QuerySet':
        """
        Get recent abuse reports.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            QuerySet of recent reports
        """
        since_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(created_at__gte=since_time)
    
    def get_reports_by_ip(self, ip_address: str) -> 'QuerySet':
        """
        Get reports by IP address.
        
        Args:
            ip_address: IP address
            
        Returns:
            QuerySet of IP reports
        """
        return self.model.objects.filter(ip_address=ip_address)
    
    def get_abuse_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get abuse report statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Abuse statistics
        """
        since_time = timezone.now() - timedelta(days=days)
        reports = self.model.objects.filter(created_at__gte=since_time)
        
        return {
            'total_reports': reports.count(),
            'investigated_reports': reports.filter(is_investigated=True).count(),
            'uninvestigated_reports': reports.filter(is_investigated=False).count(),
            'blocked_reports': reports.filter(is_blocked=True).count(),
            'avg_severity': reports.aggregate(avg=Avg('severity'))['avg'] or 0,
            'reports_by_type': list(
                reports.values('abuse_type')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
            'reports_by_severity': list(
                reports.values('severity')
                .annotate(count=Count('id'))
                .order_by('-severity')
            )
        }


class IPBlockListSelector:
    """
    Selector for IPBlockList queries.
    """
    
    def __init__(self):
        self.model = IPBlockList
    
    def get_active_blocks(self) -> 'QuerySet':
        """Get active IP blocks."""
        return self.model.objects.filter(is_active=True)
    
    def get_expired_blocks(self) -> 'QuerySet':
        """Get expired IP blocks."""
        return self.model.objects.filter(
            permanent=False,
            expires_at__lt=timezone.now()
        )
    
    def get_permanent_blocks(self) -> 'QuerySet':
        """Get permanent IP blocks."""
        return self.model.objects.filter(permanent=True)
    
    def get_blocks_expiring_soon(self, hours: int = 24) -> 'QuerySet':
        """
        Get blocks expiring soon.
        
        Args:
            hours: Hours until expiration
            
        Returns:
            QuerySet of expiring blocks
        """
        until_time = timezone.now() + timedelta(hours=hours)
        return self.model.objects.filter(
            permanent=False,
            expires_at__lte=until_time,
            expires_at__gt=timezone.now()
        )
    
    def get_blocks_by_reason(self, block_reason: str) -> 'QuerySet':
        """
        Get blocks by reason.
        
        Args:
            block_reason: Block reason
            
        Returns:
            QuerySet of blocks
        """
        return self.model.objects.filter(block_reason=block_reason)
    
    def get_security_blocks(self) -> 'QuerySet':
        """Get security-related blocks."""
        security_reasons = ['abuse', 'security', 'malware', 'auto_detection']
        return self.model.objects.filter(block_reason__in=security_reason)
    
    def get_blocking_statistics(self) -> Dict[str, Any]:
        """
        Get IP blocking statistics.
        
        Returns:
            Blocking statistics
        """
        return self.model.objects.aggregate(
            total_blocks=Count('id'),
            active_blocks=Count('id', filter=Q(is_active=True)),
            permanent_blocks=Count('id', filter=Q(permanent=True)),
            temporary_blocks=Count('id', filter=Q(permanent=False)),
            expired_blocks=Count('id', filter=Q(permanent=False, expires_at__lt=timezone.now()))
        )


# Export selector classes
__all__ = [
    'RateLimitLogSelector',
    'RateLimitConfigSelector',
    'UserRateLimitProfileSelector',
    'AbuseReportSelector',
    'IPBlockListSelector'
]
