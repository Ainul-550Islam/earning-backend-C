# api/rate_limit/factories.py
"""
Factory classes for rate limit module.

Provides factory methods for creating rate limit objects.
"""
from django.db.models import Count

import logging
from typing import Dict, Any, List, Optional, Type
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import RequestFactory as DjangoRequestFactory

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.logic import RateLimitAlgorithm
from api.rate_limit.services import RateLimitService

logger = logging.getLogger(__name__)
User = get_user_model()


class RateLimitConfigFactory:
    """
    Factory for creating RateLimitConfig objects.
    """
    
    @staticmethod
    def create_config(**kwargs) -> RateLimitConfig:
        """
        Create a rate limit configuration.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            RateLimitConfig instance
        """
        defaults = {
            'name': 'default_config',
            'rate_limit_type': 'endpoint',
            'requests_per_unit': 100,
            'time_unit': 'hour',
            'time_value': 1,
            'is_active': True,
        }
        
        defaults.update(kwargs)
        
        # Validate required fields
        if not defaults.get('name'):
            raise ValueError("Name is required")
        
        if defaults.get('rate_limit_type') not in ['user', 'ip', 'endpoint', 'global', 'referral', 'task', 'offer']:
            raise ValueError("Invalid rate_limit_type")
        
        # Create config
        config = RateLimitConfig.objects.create(**defaults)
        
        logger.info(f"Created rate limit config: {config.name}")
        return config
    
    @staticmethod
    def create_user_config(user, limit: int = 100, time_unit: str = 'hour') -> RateLimitConfig:
        """
        Create user-specific rate limit configuration.
        
        Args:
            user: User instance
            limit: Request limit
            time_unit: Time unit
            
        Returns:
            RateLimitConfig instance
        """
        return RateLimitConfigFactory.create_config(
            name=f'user_{user.username}',
            rate_limit_type='user',
            user=user,
            requests_per_unit=limit,
            time_unit=time_unit
        )
    
    @staticmethod
    def create_ip_config(ip_address: str, limit: int = 50, time_unit: str = 'hour') -> RateLimitConfig:
        """
        Create IP-specific rate limit configuration.
        
        Args:
            ip_address: IP address
            limit: Request limit
            time_unit: Time unit
            
        Returns:
            RateLimitConfig instance
        """
        return RateLimitConfigFactory.create_config(
            name=f'ip_{ip_address.replace(".", "_")}',
            rate_limit_type='ip',
            ip_address=ip_address,
            requests_per_unit=limit,
            time_unit=time_unit
        )
    
    @staticmethod
    def create_endpoint_config(endpoint: str, limit: int = 100, time_unit: str = 'hour') -> RateLimitConfig:
        """
        Create endpoint-specific rate limit configuration.
        
        Args:
            endpoint: Endpoint path
            limit: Request limit
            time_unit: Time unit
            
        Returns:
            RateLimitConfig instance
        """
        return RateLimitConfigFactory.create_config(
            name=f'endpoint_{endpoint.replace("/", "_").replace("-", "_")}',
            rate_limit_type='endpoint',
            endpoint=endpoint,
            requests_per_unit=limit,
            time_unit=time_unit
        )
    
    @staticmethod
    def create_global_config(limit: int = 1000, time_unit: str = 'hour') -> RateLimitConfig:
        """
        Create global rate limit configuration.
        
        Args:
            limit: Request limit
            time_unit: Time unit
            
        Returns:
            RateLimitConfig instance
        """
        return RateLimitConfigFactory.create_config(
            name='global_limit',
            rate_limit_type='global',
            requests_per_unit=limit,
            time_unit=time_unit
        )


class RateLimitLogFactory:
    """
    Factory for creating RateLimitLog objects.
    """
    
    @staticmethod
    def create_log(**kwargs) -> RateLimitLog:
        """
        Create a rate limit log entry.
        
        Args:
            **kwargs: Log parameters
            
        Returns:
            RateLimitLog instance
        """
        defaults = {
            'status': 'allowed',
            'requests_count': 1,
            'suspicion_score': 0,
            'timestamp': timezone.now(),
        }
        
        defaults.update(kwargs)
        
        # Validate required fields
        if not defaults.get('ip_address'):
            defaults['ip_address'] = '127.0.0.1'
        
        # Create log
        log = RateLimitLog.objects.create(**defaults)
        
        logger.debug(f"Created rate limit log: {log.id}")
        return log
    
    @staticmethod
    def create_blocked_log(user=None, ip_address=None, endpoint=None, suspicion_score=0) -> RateLimitLog:
        """
        Create a blocked request log.
        
        Args:
            user: User instance
            ip_address: IP address
            endpoint: Endpoint path
            suspicion_score: Suspicion score
            
        Returns:
            RateLimitLog instance
        """
        return RateLimitLogFactory.create_log(
            user=user,
            ip_address=ip_address or '127.0.0.1',
            endpoint=endpoint,
            status='blocked',
            suspicion_score=suspicion_score
        )
    
    @staticmethod
    def create_allowed_log(user=None, ip_address=None, endpoint=None) -> RateLimitLog:
        """
        Create an allowed request log.
        
        Args:
            user: User instance
            ip_address: IP address
            endpoint: Endpoint path
            
        Returns:
            RateLimitLog instance
        """
        return RateLimitLogFactory.create_log(
            user=user,
            ip_address=ip_address or '127.0.0.1',
            endpoint=endpoint,
            status='allowed'
        )
    
    @staticmethod
    def create_bulk_logs(logs_data: List[Dict[str, Any]]) -> List[RateLimitLog]:
        """
        Create multiple log entries in bulk.
        
        Args:
            logs_data: List of log data dictionaries
            
        Returns:
            List of RateLimitLog instances
        """
        logs = []
        for data in logs_data:
            log = RateLimitLogFactory.create_log(**data)
            logs.append(log)
        
        return logs


class UserRateLimitProfileFactory:
    """
    Factory for creating UserRateLimitProfile objects.
    """
    
    @staticmethod
    def create_profile(user, **kwargs) -> UserRateLimitProfile:
        """
        Create a user rate limit profile.
        
        Args:
            user: User instance
            **kwargs: Profile parameters
            
        Returns:
            UserRateLimitProfile instance
        """
        defaults = {
            'api_health_score': 100,
            'suspicion_score': 0,
            'is_premium': False,
            'custom_daily_limit': 1000,
            'custom_hourly_limit': 100,
            'daily_usage': 0,
            'hourly_usage': 0,
            'current_usage': 0,
        }
        
        defaults.update(kwargs)
        
        profile, created = UserRateLimitProfile.objects.get_or_create(
            user=user,
            defaults=defaults
        )
        
        if created:
            logger.info(f"Created user rate limit profile: {user.username}")
        else:
            # Update existing profile with new values
            for key, value in defaults.items():
                setattr(profile, key, value)
            profile.save()
        
        return profile
    
    @staticmethod
    def create_premium_profile(user, days: int = 30) -> UserRateLimitProfile:
        """
        Create a premium user profile.
        
        Args:
            user: User instance
            days: Premium duration in days
            
        Returns:
            UserRateLimitProfile instance
        """
        return UserRateLimitProfileFactory.create_profile(
            user,
            is_premium=True,
            premium_until=timezone.now() + timedelta(days=days),
            custom_daily_limit=5000,
            custom_hourly_limit=500,
            api_health_score=100,
            suspicion_score=0
        )
    
    @staticmethod
    def create_suspicious_profile(user, suspicion_score: int = 75) -> UserRateLimitProfile:
        """
        Create a suspicious user profile.
        
        Args:
            user: User instance
            suspicion_score: Suspicion score
            
        Returns:
            UserRateLimitProfile instance
        """
        return UserRateLimitProfileFactory.create_profile(
            user,
            suspicion_score=suspicion_score,
            api_health_score=30,
            custom_daily_limit=100,
            custom_hourly_limit=10
        )


class AbuseReportFactory:
    """
    Factory for creating AbuseReport objects.
    """
    
    @staticmethod
    def create_report(**kwargs) -> AbuseReport:
        """
        Create an abuse report.
        
        Args:
            **kwargs: Report parameters
            
        Returns:
            AbuseReport instance
        """
        defaults = {
            'abuse_type': 'suspicious_pattern',
            'severity': 3,
            'is_investigated': False,
            'is_blocked': False,
            'created_at': timezone.now(),
        }
        
        defaults.update(kwargs)
        
        # Validate required fields
        if not defaults.get('abuse_type'):
            raise ValueError("abuse_type is required")
        
        # Create report
        report = AbuseReport.objects.create(**defaults)
        
        logger.info(f"Created abuse report: {report.id}")
        return report
    
    @staticmethod
    def create_ip_abuse_report(ip_address: str, abuse_type: str = 'spam', severity: int = 3) -> AbuseReport:
        """
        Create an IP-based abuse report.
        
        Args:
            ip_address: IP address
            abuse_type: Type of abuse
            severity: Severity level
            
        Returns:
            AbuseReport instance
        """
        return AbuseReportFactory.create_report(
            ip_address=ip_address,
            abuse_type=abuse_type,
            severity=severity,
            description=f"Abuse detected from IP: {ip_address}"
        )
    
    @staticmethod
    def create_user_abuse_report(user, abuse_type: str = 'fraud', severity: int = 4) -> AbuseReport:
        """
        Create a user-based abuse report.
        
        Args:
            user: User instance
            abuse_type: Type of abuse
            severity: Severity level
            
        Returns:
            AbuseReport instance
        """
        return AbuseReportFactory.create_report(
            user=user,
            abuse_type=abuse_type,
            severity=severity,
            description=f"Abuse detected from user: {user.username}"
        )


class IPBlockListFactory:
    """
    Factory for creating IPBlockList objects.
    """
    
    @staticmethod
    def create_block(**kwargs) -> IPBlockList:
        """
        Create an IP block entry.
        
        Args:
            **kwargs: Block parameters
            
        Returns:
            IPBlockList instance
        """
        defaults = {
            'block_type': 'single',
            'block_reason': 'manual',
            'permanent': False,
            'is_active': True,
            'created_at': timezone.now(),
        }
        
        defaults.update(kwargs)
        
        # Validate required fields
        if not defaults.get('ip_address'):
            raise ValueError("ip_address is required")
        
        # Create block
        block = IPBlockList.objects.create(**defaults)
        
        logger.warning(f"Created IP block: {block.ip_address}")
        return block
    
    @staticmethod
    def create_temporary_block(ip_address: str, hours: int = 24, reason: str = 'auto_detection') -> IPBlockList:
        """
        Create a temporary IP block.
        
        Args:
            ip_address: IP address
            hours: Block duration in hours
            reason: Block reason
            
        Returns:
            IPBlockList instance
        """
        return IPBlockListFactory.create_block(
            ip_address=ip_address,
            block_type='single',
            block_reason=reason,
            permanent=False,
            expires_at=timezone.now() + timedelta(hours=hours)
        )
    
    @staticmethod
    def create_permanent_block(ip_address: str, reason: str = 'abuse') -> IPBlockList:
        """
        Create a permanent IP block.
        
        Args:
            ip_address: IP address
            reason: Block reason
            
        Returns:
            IPBlockList instance
        """
        return IPBlockListFactory.create_block(
            ip_address=ip_address,
            block_type='single',
            block_reason=reason,
            permanent=True
        )
    
    @staticmethod
    def create_range_block(ip_range: str, reason: str = 'abuse') -> IPBlockList:
        """
        Create an IP range block.
        
        Args:
            ip_range: IP range (CIDR notation)
            reason: Block reason
            
        Returns:
            IPBlockList instance
        """
        return IPBlockListFactory.create_block(
            ip_address=ip_range,
            block_type='range',
            block_reason=reason,
            permanent=False,
            expires_at=timezone.now() + timedelta(days=7)
        )


class RateLimitInsightFactory:
    """
    Factory for creating RateLimitInsight objects.
    """
    
    @staticmethod
    def create_insight(**kwargs) -> RateLimitInsight:
        """
        Create a rate limit insight.
        
        Args:
            **kwargs: Insight parameters
            
        Returns:
            RateLimitInsight instance
        """
        defaults = {
            'date': timezone.now().date(),
            'total_requests': 0,
            'blocked_requests': 0,
            'unique_ips': 0,
            'unique_users': 0,
            'avg_response_time': 0.0,
            'peak_hour': 12,
        }
        
        defaults.update(kwargs)
        
        # Create insight
        insight = RateLimitInsight.objects.create(**defaults)
        
        logger.info(f"Created rate limit insight: {insight.id}")
        return insight
    
    @staticmethod
    def create_daily_insight(date: datetime.date = None) -> RateLimitInsight:
        """
        Create a daily insight with calculated statistics.
        
        Args:
            date: Date for insight (defaults to today)
            
        Returns:
            RateLimitInsight instance
        """
        if date is None:
            date = timezone.now().date()
        
        # Calculate statistics for the date
        start_datetime = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        
        logs = RateLimitLog.objects.filter(
            timestamp__gte=start_datetime,
            timestamp__lte=end_datetime
        )
        
        # Calculate metrics
        total_requests = logs.count()
        blocked_requests = logs.filter(status='blocked').count()
        unique_ips = logs.values('ip_address').distinct().count()
        unique_users = logs.values('user').distinct().count()
        
        # Calculate peak hour
        hour_counts = logs.extra({'hour': "strftime('%%H', timestamp)"}) \
                      .values('hour') \
                      .annotate(count=Count('id')) \
                      .order_by('-count')
        
        peak_hour = hour_counts.first()['hour'] if hour_counts.exists() else 12
        
        # Create insight
        return RateLimitInsightFactory.create_insight(
            date=date,
            total_requests=total_requests,
            blocked_requests=blocked_requests,
            unique_ips=unique_ips,
            unique_users=unique_users,
            peak_hour=peak_hour
        )


class RateLimitExceptionFactory:
    """
    Factory for creating RateLimitException objects.
    """
    
    @staticmethod
    def create_exception(**kwargs) -> RateLimitException:
        """
        Create a rate limit exception.
        
        Args:
            **kwargs: Exception parameters
            
        Returns:
            RateLimitException instance
        """
        defaults = {
            'exception_type': 'whitelist',
            'multiplier': 1.0,
            'permanent': False,
            'is_active': True,
            'usage_count': 0,
            'created_at': timezone.now(),
        }
        
        defaults.update(kwargs)
        
        # Validate required fields
        if not defaults.get('exception_type'):
            raise ValueError("exception_type is required")
        
        # Create exception
        exception = RateLimitException.objects.create(**defaults)
        
        logger.info(f"Created rate limit exception: {exception.id}")
        return exception
    
    @staticmethod
    def create_user_exception(user, exception_type: str = 'increased_limit', multiplier: float = 2.0) -> RateLimitException:
        """
        Create a user-specific rate limit exception.
        
        Args:
            user: User instance
            exception_type: Type of exception
            multiplier: Rate limit multiplier
            
        Returns:
            RateLimitException instance
        """
        return RateLimitExceptionFactory.create_exception(
            user=user,
            exception_type=exception_type,
            multiplier=multiplier
        )
    
    @staticmethod
    def create_ip_exception(ip_address: str, exception_type: str = 'whitelist') -> RateLimitException:
        """
        Create an IP-specific rate limit exception.
        
        Args:
            ip_address: IP address
            exception_type: Type of exception
            
        Returns:
            RateLimitException instance
        """
        return RateLimitExceptionFactory.create_exception(
            ip_address=ip_address,
            exception_type=exception_type
        )


class RequestFactory:
    """
    Factory for creating mock HTTP requests for testing.
    """
    
    def __init__(self):
        self.django_factory = DjangoRequestFactory()
    
    def create_request(self, method: str = 'GET', path: str = '/', user=None, **kwargs) -> Any:
        """
        Create a mock HTTP request.
        
        Args:
            method: HTTP method
            path: Request path
            user: User instance
            **kwargs: Additional request parameters
            
        Returns:
            Mock request object
        """
        # Create base request
        if method.upper() == 'GET':
            request = self.django_factory.get(path, **kwargs)
        elif method.upper() == 'POST':
            request = self.django_factory.post(path, **kwargs)
        elif method.upper() == 'PUT':
            request = self.django_factory.put(path, **kwargs)
        elif method.upper() == 'DELETE':
            request = self.django_factory.delete(path, **kwargs)
        else:
            request = self.django_factory.generic(method, path, **kwargs)
        
        # Set user if provided
        if user:
            request.user = user
        
        # Set common headers
        request.META.setdefault('REMOTE_ADDR', '127.0.0.1')
        request.META.setdefault('HTTP_USER_AGENT', 'RateLimit-Test/1.0')
        
        return request
    
    def create_user_request(self, user, method: str = 'GET', path: str = '/', **kwargs) -> Any:
        """
        Create a request with authenticated user.
        
        Args:
            user: User instance
            method: HTTP method
            path: Request path
            **kwargs: Additional request parameters
            
        Returns:
            Mock request object
        """
        return self.create_request(method=method, path=path, user=user, **kwargs)
    
    def create_api_request(self, endpoint: str, method: str = 'GET', user=None, **kwargs) -> Any:
        """
        Create an API request.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            user: User instance
            **kwargs: Additional request parameters
            
        Returns:
            Mock request object
        """
        path = f'/api{endpoint}'
        return self.create_request(method=method, path=path, user=user, **kwargs)


# Export factory classes
__all__ = [
    'RateLimitConfigFactory',
    'RateLimitLogFactory',
    'UserRateLimitProfileFactory',
    'AbuseReportFactory',
    'IPBlockListFactory',
    'RateLimitInsightFactory',
    'RateLimitExceptionFactory',
    'RequestFactory'
]
