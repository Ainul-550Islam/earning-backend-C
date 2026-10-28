# api/rate_limit/repositories.py
"""
Repository pattern implementation for rate limit module.

Provides data access layer with clean separation of concerns.
"""
from django.db.models import Case
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Coalesce

import logging
from typing import Dict, Any, List, Optional, Union, Type
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min, F
from django.core.cache import cache

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Base repository class with common functionality.
    """
    
    def __init__(self, model: Type[models.Model]):
        self.model = model
        self.cache_timeout = 300  # 5 minutes
    
    def get_by_id(self, id: int) -> Optional[models.Model]:
        """
        Get model instance by ID.
        
        Args:
            id: Primary key
            
        Returns:
            Model instance or None
        """
        try:
            return self.model.objects.get(id=id)
        except self.model.DoesNotExist:
            return None
    
    def get_all(self) -> models.QuerySet:
        """
        Get all instances.
        
        Returns:
            QuerySet of all instances
        """
        return self.model.objects.all()
    
    def create(self, **kwargs) -> models.Model:
        """
        Create new instance.
        
        Args:
            **kwargs: Model field values
            
        Returns:
            Created instance
        """
        return self.model.objects.create(**kwargs)
    
    def update(self, instance: models.Model, **kwargs) -> models.Model:
        """
        Update instance.
        
        Args:
            instance: Model instance
            **kwargs: Fields to update
            
        Returns:
            Updated instance
        """
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: models.Model) -> bool:
        """
        Delete instance.
        
        Args:
            instance: Model instance
            
        Returns:
            True if deleted
        """
        instance.delete()
        return True
    
    def exists(self, **kwargs) -> bool:
        """
        Check if instance exists.
        
        Args:
            **kwargs: Filter criteria
            
        Returns:
            True if exists
        """
        return self.model.objects.filter(**kwargs).exists()
    
    def count(self, **kwargs) -> int:
        """
        Count instances.
        
        Args:
            **kwargs: Filter criteria
            
        Returns:
            Count of instances
        """
        return self.model.objects.filter(**kwargs).count()


class RateLimitConfigRepository(BaseRepository):
    """
    Repository for RateLimitConfig model.
    """
    
    def __init__(self):
        super().__init__(RateLimitConfig)
    
    def get_active_configs(self) -> models.QuerySet:
        """Get all active configurations."""
        return self.model.objects.filter(is_active=True)
    
    def get_by_type(self, rate_limit_type: str) -> models.QuerySet:
        """Get configurations by type."""
        return self.model.objects.filter(
            rate_limit_type=rate_limit_type,
            is_active=True
        )
    
    def get_for_user(self, user_id: int) -> models.QuerySet:
        """Get configurations applicable to a user."""
        return self.model.objects.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='user', user_id=user_id) |
            Q(rate_limit_type='endpoint') |
            Q(rate_limit_type='ip', ip_address__isnull=True)
        ).filter(is_active=True)
    
    def get_for_ip(self, ip_address: str) -> models.QuerySet:
        """Get configurations applicable to an IP."""
        return self.model.objects.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='ip', ip_address=ip_address) |
            Q(rate_limit_type='endpoint') |
            Q(rate_limit_type='user', user__isnull=True)
        ).filter(is_active=True)
    
    def get_for_endpoint(self, endpoint: str) -> models.QuerySet:
        """Get configurations applicable to an endpoint."""
        return self.model.objects.filter(
            Q(rate_limit_type='global') |
            Q(rate_limit_type='endpoint', endpoint=endpoint) |
            Q(rate_limit_type='user', user__isnull=True) |
            Q(rate_limit_type='ip', ip_address__isnull=True)
        ).filter(is_active=True)
    
    def get_with_usage_stats(self) -> models.QuerySet:
        """Get configurations with usage statistics."""
        return self.model.objects.annotate(
            hit_count=Coalesce(F('hit_count'), Value(0)),
            block_count=Coalesce(F('block_count'), Value(0)),
            block_rate=Case(
                When(hit_count__gt=0, then=F('block_count') * 100.0 / F('hit_count')),
                default=Value(0.0),
                output_field=models.FloatField()
            )
        )
    
    def get_high_block_rate_configs(self, threshold: float = 20.0) -> models.QuerySet:
        """Get configurations with high block rates."""
        return self.get_with_usage_stats().filter(block_rate__gte=threshold)
    
    def bulk_activate(self, config_ids: List[int]) -> int:
        """Bulk activate configurations."""
        return self.model.objects.filter(id__in=config_ids).update(is_active=True)
    
    def bulk_deactivate(self, config_ids: List[int]) -> int:
        """Bulk deactivate configurations."""
        return self.model.objects.filter(id__in=config_ids).update(is_active=False)


class RateLimitLogRepository(BaseRepository):
    """
    Repository for RateLimitLog model.
    """
    
    def __init__(self):
        super().__init__(RateLimitLog)
    
    def get_recent(self, hours: int = 24, user_id: int = None) -> models.QuerySet:
        """Get recent log entries."""
        since_time = timezone.now() - timedelta(hours=hours)
        queryset = self.model.objects.filter(timestamp__gte=since_time)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.order_by('-timestamp')
    
    def get_blocked(self, hours: int = 24, ip_address: str = None) -> models.QuerySet:
        """Get blocked log entries."""
        since_time = timezone.now() - timedelta(hours=hours)
        queryset = self.model.objects.filter(
            timestamp__gte=since_time,
            status='blocked'
        )
        
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        return queryset.order_by('-timestamp')
    
    def get_suspicious(self, min_score: int = 50, hours: int = 24) -> models.QuerySet:
        """Get suspicious log entries."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(
            timestamp__gte=since_time,
            suspicion_score__gte=min_score
        ).order_by('-suspicion_score', '-timestamp')
    
    def get_by_endpoint(self, endpoint: str, hours: int = 24) -> models.QuerySet:
        """Get logs for specific endpoint."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(
            timestamp__gte=since_time,
            endpoint=endpoint
        ).order_by('-timestamp')
    
    def get_top_ips(self, limit: int = 10, hours: int = 24) -> List[Dict[str, Any]]:
        """Get top IP addresses by request count."""
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
    
    def get_top_endpoints(self, limit: int = 10, hours: int = 24) -> List[Dict[str, Any]]:
        """Get top endpoints by request count."""
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
        """Get hourly request distribution."""
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
        """Get activity summary for a user."""
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
            'last_request': logs.order_by('-timestamp').first().timestamp if logs.exists() else None
        }
    
    def bulk_create(self, logs_data: List[Dict[str, Any]]) -> List[models.Model]:
        """Bulk create log entries."""
        return self.model.objects.bulk_create([
            self.model(**data) for data in logs_data
        ])


class UserRateLimitProfileRepository(BaseRepository):
    """
    Repository for UserRateLimitProfile model.
    """
    
    def __init__(self):
        super().__init__(UserRateLimitProfile)
    
    def get_by_user_id(self, user_id: int) -> Optional[models.Model]:
        """Get profile by user ID."""
        try:
            return self.model.objects.get(user_id=user_id)
        except self.model.DoesNotExist:
            return None
    
    def get_or_create_by_user(self, user, defaults: Dict[str, Any] = None) -> models.Model:
        """Get or create profile for user."""
        profile_defaults = {
            'api_health_score': 100,
            'suspicion_score': 0,
            'is_premium': False,
            'custom_daily_limit': 1000,
            'custom_hourly_limit': 100,
        }
        
        if defaults:
            profile_defaults.update(defaults)
        
        profile, created = self.model.objects.get_or_create(
            user=user,
            defaults=profile_defaults
        )
        
        return profile
    
    def get_premium_users(self) -> models.QuerySet:
        """Get premium users."""
        return self.model.objects.filter(is_premium=True)
    
    def get_suspicious_users(self, min_score: int = 50) -> models.QuerySet:
        """Get suspicious users."""
        return self.model.objects.filter(suspicion_score__gte=min_score)
    
    def get_high_risk_users(self, min_suspicion: int = 70, max_health: int = 30) -> models.QuerySet:
        """Get high risk users."""
        return self.model.objects.filter(
            suspicion_score__gte=min_suspicion,
            api_health_score__lte=max_health
        )
    
    def get_inactive_users(self, days: int = 30) -> models.QuerySet:
        """Get inactive users."""
        since_time = timezone.now() - timedelta(days=days)
        return self.model.objects.filter(
            last_request_at__lt=since_time
        )
    
    def get_with_health_scores(self) -> models.QuerySet:
        """Get users with health score categorization."""
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
    
    def update_usage_stats(self, user_id: int, daily: int = 0, hourly: int = 0, current: int = 0) -> bool:
        """Update usage statistics for user."""
        try:
            profile = self.get_by_user_id(user_id)
            if profile:
                profile.daily_usage = daily
                profile.hourly_usage = hourly
                profile.current_usage = current
                profile.save(update_fields=['daily_usage', 'hourly_usage', 'current_usage'])
                return True
        except Exception as e:
            logger.error(f"Failed to update usage stats: {str(e)}")
        
        return False


class AbuseReportRepository(BaseRepository):
    """
    Repository for AbuseReport model.
    """
    
    def __init__(self):
        super().__init__(AbuseReport)
    
    def get_uninvestigated(self) -> models.QuerySet:
        """Get uninvestigated abuse reports."""
        return self.model.objects.filter(is_investigated=False)
    
    def get_high_severity(self, min_severity: int = 4) -> models.QuerySet:
        """Get high severity abuse reports."""
        return self.model.objects.filter(severity__gte=min_severity)
    
    def get_by_type(self, abuse_type: str) -> models.QuerySet:
        """Get reports by abuse type."""
        return self.model.objects.filter(abuse_type=abuse_type)
    
    def get_recent(self, hours: int = 24) -> models.QuerySet:
        """Get recent abuse reports."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.model.objects.filter(created_at__gte=since_time)
    
    def get_by_ip(self, ip_address: str) -> models.QuerySet:
        """Get reports by IP address."""
        return self.model.objects.filter(ip_address=ip_address)
    
    def mark_investigated(self, report_id: int, investigated_by_id: int) -> bool:
        """Mark report as investigated."""
        try:
            report = self.get_by_id(report_id)
            if report:
                report.is_investigated = True
                report.investigated_by_id = investigated_by_id
                report.investigated_at = timezone.now()
                report.save(update_fields=['is_investigated', 'investigated_by_id', 'investigated_at'])
                return True
        except Exception as e:
            logger.error(f"Failed to mark report as investigated: {str(e)}")
        
        return False
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get abuse report statistics."""
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


class IPBlockListRepository(BaseRepository):
    """
    Repository for IPBlockList model.
    """
    
    def __init__(self):
        super().__init__(IPBlockList)
    
    def get_active(self) -> models.QuerySet:
        """Get active IP blocks."""
        return self.model.objects.filter(is_active=True)
    
    def get_expired(self) -> models.QuerySet:
        """Get expired IP blocks."""
        return self.model.objects.filter(
            permanent=False,
            expires_at__lt=timezone.now()
        )
    
    def get_permanent(self) -> models.QuerySet:
        """Get permanent IP blocks."""
        return self.model.objects.filter(permanent=True)
    
    def get_expiring_soon(self, hours: int = 24) -> models.QuerySet:
        """Get blocks expiring soon."""
        until_time = timezone.now() + timedelta(hours=hours)
        return self.model.objects.filter(
            permanent=False,
            expires_at__lte=until_time,
            expires_at__gt=timezone.now()
        )
    
    def get_by_reason(self, block_reason: str) -> models.QuerySet:
        """Get blocks by reason."""
        return self.model.objects.filter(block_reason=block_reason)
    
    def get_security_blocks(self) -> models.QuerySet:
        """Get security-related blocks."""
        security_reasons = ['abuse', 'security', 'malware', 'auto_detection']
        return self.model.objects.filter(block_reason__in=security_reasons)
    
    def block_ip(self, ip_address: str, block_reason: str, hours: int = None, created_by_id: int = None) -> models.Model:
        """Block an IP address."""
        block_data = {
            'ip_address': ip_address,
            'block_type': 'single',
            'block_reason': block_reason,
            'permanent': hours is None,
            'is_active': True
        }
        
        if hours:
            block_data['expires_at'] = timezone.now() + timedelta(hours=hours)
        
        if created_by_id:
            block_data['created_by_id'] = created_by_id
        
        return self.create(**block_data)
    
    def unblock_ip(self, ip_address: str) -> int:
        """Unblock an IP address."""
        return self.model.objects.filter(ip_address=ip_address).update(is_active=False)
    
    def bulk_block(self, ip_addresses: List[str], block_reason: str, hours: int = None) -> int:
        """Bulk block IP addresses."""
        blocked_count = 0
        
        for ip_address in ip_addresses:
            try:
                self.block_ip(ip_address, block_reason, hours)
                blocked_count += 1
            except Exception as e:
                logger.error(f"Failed to block IP {ip_address}: {str(e)}")
        
        return blocked_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get IP blocking statistics."""
        return self.model.objects.aggregate(
            total_blocks=Count('id'),
            active_blocks=Count('id', filter=Q(is_active=True)),
            permanent_blocks=Count('id', filter=Q(permanent=True)),
            temporary_blocks=Count('id', filter=Q(permanent=False)),
            expired_blocks=Count('id', filter=Q(permanent=False, expires_at__lt=timezone.now()))
        )


class RateLimitExceptionRepository(BaseRepository):
    """
    Repository for RateLimitException model.
    """
    
    def __init__(self):
        super().__init__(RateLimitException)
    
    def get_active(self) -> models.QuerySet:
        """Get active exceptions."""
        return self.model.objects.filter(is_active=True)
    
    def get_by_user(self, user_id: int) -> models.QuerySet:
        """Get exceptions for user."""
        return self.model.objects.filter(user_id=user_id, is_active=True)
    
    def get_by_ip(self, ip_address: str) -> models.QuerySet:
        """Get exceptions for IP address."""
        return self.model.objects.filter(ip_address=ip_address, is_active=True)
    
    def get_by_type(self, exception_type: str) -> models.QuerySet:
        """Get exceptions by type."""
        return self.model.objects.filter(exception_type=exception_type, is_active=True)
    
    def get_expired(self) -> models.QuerySet:
        """Get expired exceptions."""
        return self.model.objects.filter(
            permanent=False,
            expires_at__lt=timezone.now()
        )
    
    def create_user_exception(self, user_id: int, exception_type: str, multiplier: float = 1.0) -> models.Model:
        """Create user exception."""
        return self.create(
            user_id=user_id,
            exception_type=exception_type,
            multiplier=multiplier,
            is_active=True
        )
    
    def create_ip_exception(self, ip_address: str, exception_type: str) -> models.Model:
        """Create IP exception."""
        return self.create(
            ip_address=ip_address,
            exception_type=exception_type,
            is_active=True
        )
    
    def increment_usage(self, exception_id: int) -> bool:
        """Increment exception usage count."""
        try:
            exception = self.get_by_id(exception_id)
            if exception:
                exception.usage_count += 1
                exception.last_used_at = timezone.now()
                exception.save(update_fields=['usage_count', 'last_used_at'])
                return True
        except Exception as e:
            logger.error(f"Failed to increment exception usage: {str(e)}")
        
        return False


# Repository factory
class RepositoryFactory:
    """
    Factory for creating repository instances.
    """
    
    _repositories = {
        'rate_limit_config': RateLimitConfigRepository,
        'rate_limit_log': RateLimitLogRepository,
        'user_rate_limit_profile': UserRateLimitProfileRepository,
        'abuse_report': AbuseReportRepository,
        'ip_block_list': IPBlockListRepository,
        'rate_limit_exception': RateLimitExceptionRepository,
    }
    
    @classmethod
    def get_repository(cls, name: str) -> BaseRepository:
        """
        Get repository instance by name.
        
        Args:
            name: Repository name
            
        Returns:
            Repository instance
        """
        if name not in cls._repositories:
            raise ValueError(f"Unknown repository: {name}")
        
        return cls._repositories[name]()
    
    @classmethod
    def get_all_repositories(cls) -> Dict[str, BaseRepository]:
        """
        Get all repository instances.
        
        Returns:
            Dictionary of repository instances
        """
        return {name: repo() for name, repo in cls._repositories.items()}


# Export repository classes
__all__ = [
    'BaseRepository',
    'RateLimitConfigRepository',
    'RateLimitLogRepository',
    'UserRateLimitProfileRepository',
    'AbuseReportRepository',
    'IPBlockListRepository',
    'RateLimitExceptionRepository',
    'RepositoryFactory'
]
