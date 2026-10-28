# api/rate_limit/use_cases.py
"""
Use cases for rate limit module.

Provides business logic use cases for rate limiting operations.
"""
from django.db.models import Count

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitException
)
from api.rate_limit.services import RateLimitService
from api.rate_limit.logic import AbuseDetectionLogic, RateLimitOptimization
from api.rate_limit.helpers import RateLimitHelper

logger = logging.getLogger(__name__)
User = get_user_model()


class RateLimitUseCase:
    """
    Base use case class for rate limiting operations.
    """
    
    def __init__(self):
        self.rate_limit_service = RateLimitService()
        self.abuse_detector = AbuseDetectionLogic()
        self.optimizer = RateLimitOptimization()


class CheckRateLimitUseCase(RateLimitUseCase):
    """
    Use case for checking rate limits.
    """
    
    def execute(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if request is within rate limits.
        
        Args:
            request_data: Request data including user, IP, endpoint, etc.
            
        Returns:
            Rate limit check result
        """
        try:
            identifier = self._get_identifier(request_data)
            limit_type = request_data.get('limit_type', 'endpoint')
            max_requests = request_data.get('max_requests', 100)
            
            # Check rate limit
            is_limited, remaining, metadata = self.rate_limit_service.is_rate_limited(
                identifier=identifier,
                limit_type=limit_type,
                max_requests=max_requests,
                user=request_data.get('user'),
                ip_address=request_data.get('ip_address'),
                endpoint=request_data.get('endpoint')
            )
            
            # Calculate suspicion score
            suspicion_score = RateLimitHelper.calculate_suspicion_score(request_data)
            
            # Log the request
            self._log_request(request_data, is_limited, suspicion_score)
            
            # Check for abuse patterns
            if suspicion_score > 70:
                self._check_abuse_patterns(request_data)
            
            return {
                'success': True,
                'is_allowed': not is_limited,
                'remaining': remaining,
                'suspicion_score': suspicion_score,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error("Rate limit check failed: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'is_allowed': True  # Allow on error
            }
    
    def _get_identifier(self, request_data: Dict[str, Any]) -> str:
        """Get identifier for rate limiting."""
        user = request_data.get('user')
        if user and user.is_authenticated:
            return f"user:{user.id}"
        else:
            return f"ip:{request_data.get('ip_address', '127.0.0.1')}"
    
    def _log_request(self, request_data: Dict[str, Any], is_limited: bool, suspicion_score: int):
        """Log the request for analytics."""
        # This would create a RateLimitLog entry
        pass
    
    def _check_abuse_patterns(self, request_data: Dict[str, Any]):
        """Check for abuse patterns."""
        # This would trigger abuse detection
        pass


class CreateUserRateLimitProfileUseCase(RateLimitUseCase):
    """
    Use case for creating user rate limit profiles.
    """
    
    def execute(self, user, profile_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create or update user rate limit profile.
        
        Args:
            user: User instance
            profile_data: Additional profile data
            
        Returns:
            Result with profile information
        """
        try:
            profile, created = UserRateLimitProfile.objects.get_or_create(
                user=user,
                defaults={
                    'api_health_score': 100,
                    'suspicion_score': 0,
                    'is_premium': False,
                    'custom_daily_limit': 1000,
                    'custom_hourly_limit': 100,
                }
            )
            
            if profile_data:
                # Update profile with provided data
                for key, value in profile_data.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                
                profile.save()
            
            return {
                'success': True,
                'profile_id': profile.id,
                'created': created,
                'profile_data': {
                    'api_health_score': profile.api_health_score,
                    'suspicion_score': profile.suspicion_score,
                    'is_premium': profile.is_premium,
                    'custom_daily_limit': profile.custom_daily_limit,
                    'custom_hourly_limit': profile.custom_hourly_limit,
                }
            }
            
        except Exception as e:
            logger.error("Failed to create user profile: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}


class UpgradeUserToPremiumUseCase(RateLimitUseCase):
    """
    Use case for upgrading users to premium status.
    """
    
    def execute(self, user_id: int, days: int = 30, upgraded_by: User = None) -> Dict[str, Any]:
        """
        Upgrade user to premium status.
        
        Args:
            user_id: User ID to upgrade
            days: Duration in days
            upgraded_by: User who performed the upgrade
            
        Returns:
            Upgrade result
        """
        try:
            user = User.objects.get(id=user_id)
            
            # Get or create profile
            profile, created = UserRateLimitProfile.objects.get_or_create(
                user=user,
                defaults={
                    'api_health_score': 100,
                    'suspicion_score': 0,
                    'is_premium': False,
                }
            )
            
            # Set premium status
            profile.is_premium = True
            profile.premium_until = timezone.now() + timedelta(days=days)
            profile.custom_daily_limit = 5000
            profile.custom_hourly_limit = 500
            profile.save()
            
            # Log the upgrade
            logger.info(f"User {user.username} upgraded to premium for {days} days by {upgraded_by}")
            
            return {
                'success': True,
                'user_id': user_id,
                'username': user.username,
                'premium_until': profile.premium_until,
                'days': days,
                'upgraded_by': upgraded_by.username if upgraded_by else None
            }
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            logger.error("Failed to upgrade user to premium: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}


class BlockIPAddressUseCase(RateLimitUseCase):
    """
    Use case for blocking IP addresses.
    """
    
    def execute(self, ip_address: str, block_reason: str = 'manual', 
                hours: int = None, blocked_by: User = None) -> Dict[str, Any]:
        """
        Block an IP address.
        
        Args:
            ip_address: IP address to block
            block_reason: Reason for blocking
            hours: Duration in hours (None for permanent)
            blocked_by: User who performed the block
            
        Returns:
            Block result
        """
        try:
            # Validate IP address
            if not RateLimitHelper.is_valid_ip_address(ip_address):
                return {'success': False, 'error': 'Invalid IP address'}
            
            # Create IP block
            block_data = {
                'ip_address': ip_address,
                'block_type': 'single',
                'block_reason': block_reason,
                'permanent': hours is None,
                'is_active': True
            }
            
            if hours:
                block_data['expires_at'] = timezone.now() + timedelta(hours=hours)
            
            if blocked_by:
                block_data['created_by'] = blocked_by
            
            block = IPBlockList.objects.create(**block_data)
            
            # Clear any existing rate limit counters for this IP
            self._clear_ip_counters(ip_address)
            
            logger.info(f"IP {ip_address} blocked for reason: {block_reason}")
            
            return {
                'success': True,
                'block_id': block.id,
                'ip_address': ip_address,
                'block_reason': block_reason,
                'permanent': block.permanent,
                'expires_at': block.expires_at,
                'blocked_by': blocked_by.username if blocked_by else None
            }
            
        except Exception as e:
            logger.error("Failed to block IP address: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _clear_ip_counters(self, ip_address: str):
        """Clear rate limit counters for IP address."""
        # This would clear cache entries for the IP
        cache_keys = cache.keys(f"rate_limit:ip:{ip_address}:*")
        for key in cache_keys:
            cache.delete(key)


class CreateAbuseReportUseCase(RateLimitUseCase):
    """
    Use case for creating abuse reports.
    """
    
    def execute(self, report_data: Dict[str, Any], reported_by: User = None) -> Dict[str, Any]:
        """
        Create an abuse report.
        
        Args:
            report_data: Abuse report data
            reported_by: User creating the report
            
        Returns:
            Report creation result
        """
        try:
            # Validate required fields
            if not report_data.get('abuse_type'):
                return {'success': False, 'error': 'abuse_type is required'}
            
            if not report_data.get('severity'):
                return {'success': False, 'error': 'severity is required'}
            
            # Create abuse report
            abuse_report = AbuseReport.objects.create(
                user=report_data.get('user'),
                ip_address=report_data.get('ip_address'),
                abuse_type=report_data['abuse_type'],
                severity=report_data['severity'],
                description=report_data.get('description', ''),
                evidence=report_data.get('evidence', {}),
                created_by=reported_by
            )
            
            # Auto-investigate high severity reports
            if report_data['severity'] >= 4:
                self._auto_investigate(abuse_report)
            
            # Auto-block for critical severity
            if report_data['severity'] == 5 and report_data.get('ip_address'):
                self._auto_block_ip(report_data['ip_address'], abuse_report)
            
            logger.info(f"Abuse report created: {abuse_report.id} - {report_data['abuse_type']}")
            
            return {
                'success': True,
                'report_id': abuse_report.id,
                'abuse_type': abuse_report.abuse_type,
                'severity': abuse_report.severity,
                'auto_investigated': report_data['severity'] >= 4,
                'auto_blocked': report_data['severity'] == 5 and report_data.get('ip_address')
            }
            
        except Exception as e:
            logger.error("Failed to create abuse report: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _auto_investigate(self, abuse_report: AbuseReport):
        """Auto-investigate high severity abuse reports."""
        abuse_report.is_investigated = True
        abuse_report.investigated_at = timezone.now()
        abuse_report.save(update_fields=['is_investigated', 'investigated_at'])
    
    def _auto_block_ip(self, ip_address: str, abuse_report: AbuseReport):
        """Auto-block IP for critical abuse."""
        block_use_case = BlockIPAddressUseCase()
        block_use_case.execute(
            ip_address=ip_address,
            block_reason='abuse_report',
            hours=24 * 7  # 1 week
        )


class GenerateRateLimitInsightsUseCase(RateLimitUseCase):
    """
    Use case for generating rate limit insights.
    """
    
    def execute(self, date: datetime.date = None) -> Dict[str, Any]:
        """
        Generate rate limit insights for a date.
        
        Args:
            date: Date to generate insights for (defaults to yesterday)
            
        Returns:
            Generated insights
        """
        try:
            if date is None:
                date = timezone.now().date() - timedelta(days=1)
            
            # Get logs for the date
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
            
            # Get top endpoints
            top_endpoints = list(
                logs.values('endpoint')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
                .values('endpoint', 'count')
            )
            
            # Get top IPs
            top_ips = list(
                logs.values('ip_address')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
                .values('ip_address', 'count')
            )
            
            # Create or update insight
            from api.rate_limit.models import RateLimitInsight
            
            insight, created = RateLimitInsight.objects.update_or_create(
                date=date,
                defaults={
                    'total_requests': total_requests,
                    'blocked_requests': blocked_requests,
                    'unique_ips': unique_ips,
                    'unique_users': unique_users,
                    'peak_hour': peak_hour,
                    'top_endpoints': top_endpoints,
                    'top_ips': top_ips,
                }
            )
            
            return {
                'success': True,
                'date': date.isoformat(),
                'insight_id': insight.id,
                'created': created,
                'metrics': {
                    'total_requests': total_requests,
                    'blocked_requests': blocked_requests,
                    'unique_ips': unique_ips,
                    'unique_users': unique_users,
                    'peak_hour': peak_hour,
                    'block_rate': (blocked_requests / max(total_requests, 1)) * 100
                }
            }
            
        except Exception as e:
            logger.error("Failed to generate insights: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}


class OptimizeRateLimitConfigUseCase(RateLimitUseCase):
    """
    Use case for optimizing rate limit configurations.
    """
    
    def execute(self, config_id: int = None) -> Dict[str, Any]:
        """
        Optimize rate limit configuration.
        
        Args:
            config_id: Specific config ID to optimize (None for all)
            
        Returns:
            Optimization results
        """
        try:
            if config_id:
                # Optimize specific config
                configs = [RateLimitConfig.objects.get(id=config_id)]
            else:
                # Optimize all active configs
                configs = RateLimitConfig.objects.filter(is_active=True)
            
            results = []
            
            for config in configs:
                try:
                    suggestion = self.optimizer.suggest_config_adjustments(config.id)
                    
                    if 'suggestions' in suggestion:
                        results.append({
                            'config_id': config.id,
                            'config_name': config.name,
                            'suggestions': suggestion['suggestions'],
                            'current_block_rate': suggestion.get('block_rate', 0),
                            'priority': suggestion.get('priority', 'medium')
                        })
                
                except Exception as e:
                    logger.error("Failed to optimize config %s: %s", config.id, str(e), exc_info=True)
                    continue
            
            return {
                'success': True,
                'optimized_configs': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error("Failed to optimize configs: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}


class ResetUserRateLimitUseCase(RateLimitUseCase):
    """
    Use case for resetting user rate limits.
    """
    
    def execute(self, user_id: int, reset_type: str = 'all', reset_by: User = None) -> Dict[str, Any]:
        """
        Reset user rate limits.
        
        Args:
            user_id: User ID to reset
            reset_type: Type of reset ('all', 'daily', 'hourly', 'current')
            reset_by: User performing the reset
            
        Returns:
            Reset result
        """
        try:
            user = User.objects.get(id=user_id)
            profile = UserRateLimitProfile.objects.get(user=user)
            
            reset_fields = []
            
            if reset_type == 'all':
                profile.daily_usage = 0
                profile.hourly_usage = 0
                profile.current_usage = 0
                reset_fields = ['daily_usage', 'hourly_usage', 'current_usage']
            elif reset_type == 'daily':
                profile.daily_usage = 0
                reset_fields = ['daily_usage']
            elif reset_type == 'hourly':
                profile.hourly_usage = 0
                reset_fields = ['hourly_usage']
            elif reset_type == 'current':
                profile.current_usage = 0
                reset_fields = ['current_usage']
            
            profile.save(update_fields=reset_fields)
            
            # Clear user cache entries
            self._clear_user_counters(user_id)
            
            logger.info(f"User {user.username} rate limits reset ({reset_type}) by {reset_by}")
            
            return {
                'success': True,
                'user_id': user_id,
                'username': user.username,
                'reset_type': reset_type,
                'reset_fields': reset_fields,
                'reset_by': reset_by.username if reset_by else None
            }
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except UserRateLimitProfile.DoesNotExist:
            return {'success': False, 'error': 'User rate limit profile not found'}
        except Exception as e:
            logger.error("Failed to reset user rate limits: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _clear_user_counters(self, user_id: int):
        """Clear rate limit counters for user."""
        cache_keys = cache.keys(f"rate_limit:user:{user_id}:*")
        for key in cache_keys:
            cache.delete(key)


# Export use case classes
__all__ = [
    'CheckRateLimitUseCase',
    'CreateUserRateLimitProfileUseCase',
    'UpgradeUserToPremiumUseCase',
    'BlockIPAddressUseCase',
    'CreateAbuseReportUseCase',
    'GenerateRateLimitInsightsUseCase',
    'OptimizeRateLimitConfigUseCase',
    'ResetUserRateLimitUseCase'
]
