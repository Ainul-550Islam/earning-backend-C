# api/rate_limit/querysets.py
"""
Custom QuerySets for rate limit module.

Provides optimized database queries for rate limiting models.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.db.models import Count, Q, Sum, Avg, Max, Min, F, Window
from django.db.models.functions import Trunc, Extract, Coalesce
from django.db.models import Case, When, Value, IntegerField

from api.rate_limit.models import RateLimitLog, RateLimitConfig, UserRateLimitProfile, AbuseReport, IPBlockList

logger = logging.getLogger(__name__)


class RateLimitLogQuerySet(models.QuerySet):
    """
    Custom QuerySet for RateLimitLog model.
    """
    
    def active(self) -> 'RateLimitLogQuerySet':
        """Filter for active logs (within last 30 days)."""
        since_time = timezone.now() - timedelta(days=30)
        return self.filter(timestamp__gte=since_time)
    
    def recent(self, hours: int = 24) -> 'RateLimitLogQuerySet':
        """Filter for recent logs within specified hours."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.filter(timestamp__gte=since_time)
    
    def by_status(self, status: str) -> 'RateLimitLogQuerySet':
        """Filter by request status."""
        return self.filter(status=status)
    
    def blocked(self) -> 'RateLimitLogQuerySet':
        """Filter for blocked requests."""
        return self.filter(status='blocked')
    
    def allowed(self) -> 'RateLimitLogQuerySet':
        """Filter for allowed requests."""
        return self.filter(status='allowed')
    
    def by_user(self, user) -> 'RateLimitLogQuerySet':
        """Filter by user."""
        return self.filter(user=user)
    
    def by_ip(self, ip_address: str) -> 'RateLimitLogQuerySet':
        """Filter by IP address."""
        return self.filter(ip_address=ip_address)
    
    def by_endpoint(self, endpoint: str) -> 'RateLimitLogQuerySet':
        """Filter by endpoint."""
        return self.filter(endpoint=endpoint)
    
    def by_method(self, method: str) -> 'RateLimitLogQuerySet':
        """Filter by HTTP method."""
        return self.filter(request_method=method)
    
    def suspicious(self, min_score: int = 50) -> 'RateLimitLogQuerySet':
        """Filter for suspicious requests."""
        return self.filter(suspicion_score__gte=min_score)
    
    def with_user_stats(self) -> 'RateLimitLogQuerySet':
        """Annotate with user statistics."""
        return self.annotate(
            user_total_requests=Count('id'),
            user_blocked_requests=Count('id', filter=Q(status='blocked')),
            user_block_rate=Case(
                When(total_requests__gt=0, then=Count('id', filter=Q(status='blocked')) * 100.0 / Count('id')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        )
    
    def with_hourly_stats(self) -> 'RateLimitLogQuerySet':
        """Annotate with hourly statistics."""
        return self.annotate(
            hour=Extract('timestamp', 'hour'),
            date=Trunc('timestamp', 'day')
        )
    
    def by_date_range(self, start_date: datetime.date, end_date: datetime.date) -> 'RateLimitLogQuerySet':
        """Filter by date range."""
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        return self.filter(timestamp__gte=start_datetime, timestamp__lte=end_datetime)
    
    def top_ips(self, limit: int = 10) -> 'RateLimitLogQuerySet':
        """Get top IP addresses by request count."""
        return self.values('ip_address').annotate(
            request_count=Count('id')
        ).order_by('-request_count')[:limit]
    
    def top_users(self, limit: int = 10) -> 'RateLimitLogQuerySet':
        """Get top users by request count."""
        return self.values('user__username').annotate(
            request_count=Count('id')
        ).order_by('-request_count')[:limit]
    
    def top_endpoints(self, limit: int = 10) -> 'RateLimitLogQuerySet':
        """Get top endpoints by request count."""
        return self.values('endpoint').annotate(
            request_count=Count('id')
        ).order_by('-request_count')[:limit]
    
    def hourly_distribution(self) -> 'RateLimitLogQuerySet':
        """Get hourly request distribution."""
        return self.extra({
            'hour': "strftime('%%H', timestamp)"
        }).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
    
    def daily_distribution(self, days: int = 30) -> 'RateLimitLogQuerySet':
        """Get daily request distribution."""
        since_time = timezone.now() - timedelta(days=days)
        return self.filter(timestamp__gte=since_time).extra({
            'date': "date(timestamp)"
        }).values('date').annotate(
            count=Count('id'),
            blocked_count=Count('id', filter=Q(status='blocked'))
        ).order_by('date')
    
    def response_time_stats(self) -> Dict[str, Any]:
        """Get response time statistics."""
        stats = self.aggregate(
            avg_response_time=Avg('response_time'),
            min_response_time=Min('response_time'),
            max_response_time=Max('response_time'),
            total_requests=Count('id')
        )
        
        return {
            'average_response_time': stats['avg_response_time'] or 0,
            'min_response_time': stats['min_response_time'] or 0,
            'max_response_time': stats['max_response_time'] or 0,
            'total_requests': stats['total_requests'] or 0
        }
    
    def block_rate_by_period(self, period: str = 'hour') -> 'RateLimitLogQuerySet':
        """Get block rate by time period."""
        if period == 'hour':
            trunc_func = Trunc('timestamp', 'hour')
        elif period == 'day':
            trunc_func = Trunc('timestamp', 'day')
        elif period == 'week':
            trunc_func = Trunc('timestamp', 'week')
        else:
            trunc_func = Trunc('timestamp', 'hour')
        
        return self.annotate(
            period=trunc_func
        ).values('period').annotate(
            total_requests=Count('id'),
            blocked_requests=Count('id', filter=Q(status='blocked')),
            block_rate=Case(
                When(total_requests__gt=0, then=Count('id', filter=Q(status='blocked')) * 100.0 / Count('id')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        ).order_by('period')


class RateLimitConfigQuerySet(models.QuerySet):
    """
    Custom QuerySet for RateLimitConfig model.
    """
    
    def active(self) -> 'RateLimitConfigQuerySet':
        """Filter for active configurations."""
        return self.filter(is_active=True)
    
    def inactive(self) -> 'RateLimitConfigQuerySet':
        """Filter for inactive configurations."""
        return self.filter(is_active=False)
    
    def by_type(self, rate_limit_type: str) -> 'RateLimitConfigQuerySet':
        """Filter by rate limit type."""
        return self.filter(rate_limit_type=rate_limit_type)
    
    def user_configs(self) -> 'RateLimitConfigQuerySet':
        """Filter for user-specific configurations."""
        return self.filter(rate_limit_type='user')
    
    def ip_configs(self) -> 'RateLimitConfigQuerySet':
        """Filter for IP-specific configurations."""
        return self.filter(rate_limit_type='ip')
    
    def endpoint_configs(self) -> 'RateLimitConfigQuerySet':
        """Filter for endpoint-specific configurations."""
        return self.filter(rate_limit_type='endpoint')
    
    def global_configs(self) -> 'RateLimitConfigQuerySet':
        """Filter for global configurations."""
        return self.filter(rate_limit_type='global')
    
    def for_user(self, user) -> 'RateLimitConfigQuerySet':
        """Filter configurations applicable to a user."""
        return self.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='user', user=user) |
            Q(rate_limit_type='endpoint') |
            Q(rate_limit_type='ip', ip_address__isnull=True)  # General IP configs
        )
    
    def for_ip(self, ip_address: str) -> 'RateLimitConfigQuerySet':
        """Filter configurations applicable to an IP."""
        return self.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='ip', ip_address=ip_address) |
            Q(rate_limit_type='endpoint') |
            Q(rate_limit_type='user', user__isnull=True)  # General user configs
        )
    
    def for_endpoint(self, endpoint: str) -> 'RateLimitConfigQuerySet':
        """Filter configurations applicable to an endpoint."""
        return self.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='endpoint', endpoint=endpoint) |
            Q(rate_limit_type='user', user__isnull=True) |
            Q(rate_limit_type='ip', ip_address__isnull=True)
        )
    
    def with_usage_stats(self) -> 'RateLimitConfigQuerySet':
        """Annotate with usage statistics."""
        return self.annotate(
            hit_count=Coalesce(F('hit_count'), Value(0)),
            block_count=Coalesce(F('block_count'), Value(0)),
            block_rate=Case(
                When(hit_count__gt=0, then=F('block_count') * 100.0 / F('hit_count')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        )
    
    def high_block_rate(self, threshold: float = 20.0) -> 'RateLimitConfigQuerySet':
        """Filter configurations with high block rates."""
        return self.with_usage_stats().filter(block_rate__gte=threshold)
    
    def low_usage(self, threshold: int = 10) -> 'RateLimitConfigQuerySet':
        """Filter configurations with low usage."""
        return self.with_usage_stats().filter(hit_count__lt=threshold)
    
    def by_time_unit(self, time_unit: str) -> 'RateLimitConfigQuerySet':
        """Filter by time unit."""
        return self.filter(time_unit=time_unit)
    
    def sorted_by_usage(self) -> 'RateLimitConfigQuerySet':
        """Sort by usage statistics."""
        return self.with_usage_stats().order_by('-hit_count')
    
    def sorted_by_block_rate(self) -> 'RateLimitConfigQuerySet':
        """Sort by block rate."""
        return self.with_usage_stats().order_by('-block_rate')


class UserRateLimitProfileQuerySet(models.QuerySet):
    """
    Custom QuerySet for UserRateLimitProfile model.
    """
    
    def premium_users(self) -> 'UserRateLimitProfileQuerySet':
        """Filter for premium users."""
        return self.filter(is_premium=True)
    
    def standard_users(self) -> 'UserRateLimitProfileQuerySet':
        """Filter for standard users."""
        return self.filter(is_premium=False)
    
    def suspicious_users(self, min_score: int = 50) -> 'UserRateLimitProfileQuerySet':
        """Filter for suspicious users."""
        return self.filter(suspicion_score__gte=min_score)
    
    def high_suspicion_users(self, min_score: int = 70) -> 'UserRateLimitProfileQuerySet':
        """Filter for high suspicion users."""
        return self.filter(suspicion_score__gte=min_score)
    
    def low_health_score(self, max_score: int = 50) -> 'UserRateLimitProfileQuerySet':
        """Filter for users with low health scores."""
        return self.filter(api_health_score__lte=max_score)
    
    def high_usage_users(self, threshold: int = 1000) -> 'UserRateLimitProfileQuerySet':
        """Filter for high usage users."""
        return self.filter(total_requests__gte=threshold)
    
    def recently_active(self, hours: int = 24) -> 'UserRateLimitProfileQuerySet':
        """Filter for recently active users."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.filter(last_request_at__gte=since_time)
    
    def inactive_users(self, days: int = 30) -> 'UserRateLimitProfileQuerySet':
        """Filter for inactive users."""
        since_time = timezone.now() - timedelta(days=days)
        return self.filter(last_request_at__lt=since_time)
    
    def with_usage_ratios(self) -> 'UserRateLimitProfileQuerySet':
        """Annotate with usage ratios."""
        return self.annotate(
            block_rate=Case(
                When(total_requests__gt=0, then=F('blocked_requests') * 100.0 / F('total_requests')),
                default=Value(0.0),
                output_field=models.FloatField()
            ),
            daily_usage_ratio=Case(
                When(custom_daily_limit__gt=0, then=F('daily_usage') * 100.0 / F('custom_daily_limit')),
                default=Value(0.0),
                output_field=models.FloatField()
            ),
            hourly_usage_ratio=Case(
                When(custom_hourly_limit__gt=0, then=F('hourly_usage') * 100.0 / F('custom_hourly_limit')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        )
    
    def risk_assessment(self) -> 'UserRateLimitProfileQuerySet':
        """Annotate with risk assessment."""
        return self.annotate(
            risk_score=Case(
                When(suspicion_score__gte=80, then=Value(90)),
                When(suspicion_score__gte=60, then=Value(70)),
                When(suspicion_score__gte=40, then=Value(50)),
                When(suspicion_score__gte=20, then=Value(30)),
                default=Value(10),
                output_field=models.IntegerField()
            ),
            risk_level=Case(
                When(suspicion_score__gte=80, then=Value('critical')),
                When(suspicion_score__gte=60, then=Value('high')),
                When(suspicion_score__gte=40, then=Value('medium')),
                When(suspicion_score__gte=20, then=Value('low')),
                default=Value('minimal'),
                output_field=models.CharField()
            )
        )
    
    def sorted_by_suspicion(self) -> 'UserRateLimitProfileQuerySet':
        """Sort by suspicion score."""
        return self.order_by('-suspicion_score')
    
    def sorted_by_health(self) -> 'UserRateLimitProfileQuerySet':
        """Sort by health score."""
        return self.order_by('api_health_score')
    
    def sorted_by_usage(self) -> 'UserRateLimitProfileQuerySet':
        """Sort by total requests."""
        return self.order_by('-total_requests')


class AbuseReportQuerySet(models.QuerySet):
    """
    Custom QuerySet for AbuseReport model.
    """
    
    def investigated(self) -> 'AbuseReportQuerySet':
        """Filter for investigated reports."""
        return self.filter(is_investigated=True)
    
    def uninvestigated(self) -> 'AbuseReportQuerySet':
        """Filter for uninvestigated reports."""
        return self.filter(is_investigated=False)
    
    def blocked(self) -> 'AbuseReportQuerySet':
        """Filter for reports that resulted in blocks."""
        return self.filter(is_blocked=True)
    
    def by_abuse_type(self, abuse_type: str) -> 'AbuseReportQuerySet':
        """Filter by abuse type."""
        return self.filter(abuse_type=abuse_type)
    
    def by_severity(self, severity: int) -> 'AbuseReportQuerySet':
        """Filter by severity level."""
        return self.filter(severity=severity)
    
    def high_severity(self, min_severity: int = 4) -> 'AbuseReportQuerySet':
        """Filter for high severity reports."""
        return self.filter(severity__gte=min_severity)
    
    def recent(self, hours: int = 24) -> 'AbuseReportQuerySet':
        """Filter for recent reports."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=since_time)
    
    def by_ip(self, ip_address: str) -> 'AbuseReportQuerySet':
        """Filter by IP address."""
        return self.filter(ip_address=ip_address)
    
    def by_user(self, user) -> 'AbuseReportQuerySet':
        """Filter by user."""
        return self.filter(user=user)
    
    def with_investigation_stats(self) -> 'AbuseReportQuerySet':
        """Annotate with investigation statistics."""
        return self.annotate(
            total_reports=Count('id'),
            investigated_reports=Count('id', filter=Q(is_investigated=True)),
            blocked_reports=Count('id', filter=Q(is_blocked=True)),
            investigation_rate=Case(
                When(total_reports__gt=0, then=Count('id', filter=Q(is_investigated=True)) * 100.0 / Count('id')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        )
    
    def by_abuse_type_stats(self) -> 'AbuseReportQuerySet':
        """Get statistics by abuse type."""
        return self.values('abuse_type').annotate(
            count=Count('id'),
            avg_severity=Avg('severity'),
            blocked_count=Count('id', filter=Q(is_blocked=True))
        ).order_by('-count')
    
    def by_severity_stats(self) -> 'AbuseReportQuerySet':
        """Get statistics by severity level."""
        return self.values('severity').annotate(
            count=Count('id'),
            blocked_count=Count('id', filter=Q(is_blocked=True))
        ).order_by('-severity')


class IPBlockListQuerySet(models.QuerySet):
    """
    Custom QuerySet for IPBlockList model.
    """
    
    def active(self) -> 'IPBlockListQuerySet':
        """Filter for active blocks."""
        return self.filter(is_active=True)
    
    def inactive(self) -> 'IPBlockListQuerySet':
        """Filter for inactive blocks."""
        return self.filter(is_active=False)
    
    def permanent(self) -> 'IPBlockListQuerySet':
        """Filter for permanent blocks."""
        return self.filter(permanent=True)
    
    def temporary(self) -> 'IPBlockListQuerySet':
        """Filter for temporary blocks."""
        return self.filter(permanent=False)
    
    def expired(self) -> 'IPBlockListQuerySet':
        """Filter for expired blocks."""
        return self.filter(
            permanent=False,
            expires_at__lt=timezone.now()
        )
    
    def by_reason(self, block_reason: str) -> 'IPBlockListQuerySet':
        """Filter by block reason."""
        return self.filter(block_reason=block_reason)
    
    def by_type(self, block_type: str) -> 'IPBlockListQuerySet':
        """Filter by block type."""
        return self.filter(block_type=block_type)
    
    def security_blocks(self) -> 'IPBlockListQuerySet':
        """Filter for security-related blocks."""
        security_reasons = ['abuse', 'security', 'malware', 'auto_detection']
        return self.filter(block_reason__in=security_reasons)
    
    def manual_blocks(self) -> 'IPBlockListQuerySet':
        """Filter for manually created blocks."""
        return self.filter(block_reason='manual')
    
    def expiring_soon(self, hours: int = 24) -> 'IPBlockListQuerySet':
        """Filter for blocks expiring soon."""
        until_time = timezone.now() + timedelta(hours=hours)
        return self.filter(
            permanent=False,
            expires_at__lte=until_time,
            expires_at__gt=timezone.now()
        )
    
    def with_block_stats(self) -> 'IPBlockListQuerySet':
        """Annotate with block statistics."""
        return self.annotate(
            block_duration=Case(
                When(permanent=True, then=Value(None)),
                default=Extract('expires_at', 'epoch') - Extract('created_at', 'epoch'),
                output_field=models.IntegerField()
            )
        )
    
    def by_block_reason_stats(self) -> 'IPBlockListQuerySet':
        """Get statistics by block reason."""
        return self.values('block_reason').annotate(
            count=Count('id'),
            permanent_count=Count('id', filter=Q(permanent=True)),
            temporary_count=Count('id', filter=Q(permanent=False))
        ).order_by('-count')


# Export QuerySet classes
__all__ = [
    'RateLimitLogQuerySet',
    'RateLimitConfigQuerySet',
    'UserRateLimitProfileQuerySet',
    'AbuseReportQuerySet',
    'IPBlockListQuerySet'
]
