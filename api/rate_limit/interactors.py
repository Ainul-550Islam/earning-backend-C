# api/rate_limit/interactors.py
"""
Interactor pattern implementation for rate limit module.

Provides business logic orchestration between repositories and services.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.rate_limit.repositories import RepositoryFactory
from api.rate_limit.services import RateLimitService
from api.rate_limit.logic import AbuseDetectionLogic, RateLimitOptimization
from api.rate_limit.helpers import RateLimitHelper

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseInteractor:
    """
    Base interactor class with common functionality.
    """
    
    def __init__(self):
        self.repositories = RepositoryFactory.get_all_repositories()
        self.rate_limit_service = RateLimitService()
    
    def _get_repository(self, name: str):
        """Get repository by name."""
        return self.repositories[name]


class RateLimitInteractor(BaseInteractor):
    """
    Interactor for rate limiting operations.
    """
    
    def check_rate_limit(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if request is within rate limits.
        
        Args:
            request_data: Request data including user, IP, endpoint, etc.
            
        Returns:
            Rate limit check result
        """
        try:
            # Get identifier for rate limiting
            identifier = self._get_identifier(request_data)
            
            # Get rate limit configuration
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
            logger.error(f"Rate limit check failed: {str(e)}")
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
        log_repo = self._get_repository('rate_limit_log')
        
        log_data = {
            'user': request_data.get('user'),
            'ip_address': request_data.get('ip_address'),
            'endpoint': request_data.get('endpoint'),
            'request_method': request_data.get('method', 'GET'),
            'status': 'blocked' if is_limited else 'allowed',
            'suspicion_score': suspicion_score
        }
        
        log_repo.create(**log_data)
    
    def _check_abuse_patterns(self, request_data: Dict[str, Any]):
        """Check for abuse patterns."""
        # Get recent logs for analysis
        log_repo = self._get_repository('rate_limit_log')
        recent_logs = log_repo.get_recent(hours=1)
        
        # Convert to format for analysis
        log_data = []
        for log in recent_logs:
            log_data.append({
                'timestamp': log.timestamp,
                'ip_address': log.ip_address,
                'endpoint': log.endpoint,
                'status': log.status,
                'suspicion_score': log.suspicion_score,
            })
        
        # Detect patterns
        detector = AbuseDetectionLogic()
        patterns = detector.detect_patterns(log_data)
        
        # Create abuse reports for significant patterns
        for pattern in patterns:
            if pattern.get('severity') == 'high':
                self._create_abuse_report_from_pattern(pattern, request_data)
    
    def _create_abuse_report_from_pattern(self, pattern: Dict[str, Any], request_data: Dict[str, Any]):
        """Create abuse report from detected pattern."""
        abuse_repo = self._get_repository('abuse_report')
        
        report_data = {
            'user': request_data.get('user'),
            'ip_address': request_data.get('ip_address'),
            'abuse_type': 'pattern_detected',
            'severity': 4,  # High severity for patterns
            'description': f"Abuse pattern detected: {pattern.get('type', 'unknown')}",
            'evidence': pattern
        }
        
        abuse_repo.create(**report_data)


class UserProfileInteractor(BaseInteractor):
    """
    Interactor for user profile operations.
    """
    
    def create_or_update_profile(self, user_id: int, profile_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create or update user rate limit profile.
        
        Args:
            user_id: User ID
            profile_data: Additional profile data
            
        Returns:
            Profile operation result
        """
        try:
            user = User.objects.get(id=user_id)
            profile_repo = self._get_repository('user_rate_limit_profile')
            
            # Get or create profile
            profile = profile_repo.get_or_create_by_user(user, profile_data)
            
            return {
                'success': True,
                'profile_id': profile.id,
                'profile_data': {
                    'api_health_score': profile.api_health_score,
                    'suspicion_score': profile.suspicion_score,
                    'is_premium': profile.is_premium,
                    'custom_daily_limit': profile.custom_daily_limit,
                    'custom_hourly_limit': profile.custom_hourly_limit,
                }
            }
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            logger.error(f"Failed to create/update user profile: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def upgrade_to_premium(self, user_id: int, days: int = 30, upgraded_by_id: int = None) -> Dict[str, Any]:
        """
        Upgrade user to premium status.
        
        Args:
            user_id: User ID to upgrade
            days: Duration in days
            upgraded_by_id: User ID who performed the upgrade
            
        Returns:
            Upgrade result
        """
        try:
            user = User.objects.get(id=user_id)
            profile_repo = self._get_repository('user_rate_limit_profile')
            
            # Get profile
            profile = profile_repo.get_or_create_by_user(user)
            
            # Set premium status
            profile.is_premium = True
            profile.premium_until = timezone.now() + timedelta(days=days)
            profile.custom_daily_limit = 5000
            profile.custom_hourly_limit = 500
            profile.save()
            
            # Log the upgrade
            logger.info(f"User {user.username} upgraded to premium for {days} days")
            
            return {
                'success': True,
                'user_id': user_id,
                'username': user.username,
                'premium_until': profile.premium_until,
                'days': days
            }
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            logger.error(f"Failed to upgrade user to premium: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def reset_user_usage(self, user_id: int, reset_type: str = 'all', reset_by_id: int = None) -> Dict[str, Any]:
        """
        Reset user rate limits.
        
        Args:
            user_id: User ID to reset
            reset_type: Type of reset ('all', 'daily', 'hourly', 'current')
            reset_by_id: User ID performing the reset
            
        Returns:
            Reset result
        """
        try:
            user = User.objects.get(id=user_id)
            profile_repo = self._get_repository('user_rate_limit_profile')
            
            # Update usage stats
            success = profile_repo.update_usage_stats(user_id, 0, 0, 0)
            
            if success:
                logger.info(f"User {user.username} rate limits reset ({reset_type})")
                return {
                    'success': True,
                    'user_id': user_id,
                    'username': user.username,
                    'reset_type': reset_type
                }
            else:
                return {'success': False, 'error': 'Failed to update usage stats'}
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            logger.error(f"Failed to reset user rate limits: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_user_analytics(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """
        Get user analytics data.
        
        Args:
            user_id: User ID
            days: Number of days to analyze
            
        Returns:
            User analytics
        """
        try:
            log_repo = self._get_repository('rate_limit_log')
            profile_repo = self._get_repository('user_rate_limit_profile')
            
            # Get profile
            profile = profile_repo.get_by_user_id(user_id)
            if not profile:
                return {'success': False, 'error': 'User profile not found'}
            
            # Get activity summary
            activity = log_repo.get_user_activity_summary(user_id, days)
            
            # Get recent logs
            recent_logs = log_repo.get_recent(hours=24, user_id=user_id)
            
            return {
                'success': True,
                'user_id': user_id,
                'period_days': days,
                'profile': {
                    'api_health_score': profile.api_health_score,
                    'suspicion_score': profile.suspicion_score,
                    'is_premium': profile.is_premium,
                    'custom_daily_limit': profile.custom_daily_limit,
                    'custom_hourly_limit': profile.custom_hourly_limit,
                    'daily_usage': profile.daily_usage,
                    'hourly_usage': profile.hourly_usage,
                },
                'activity': activity,
                'recent_requests': recent_logs.count(),
                'recent_blocked': recent_logs.filter(status='blocked').count()
            }
            
        except Exception as e:
            logger.error(f"Failed to get user analytics: {str(e)}")
            return {'success': False, 'error': str(e)}


class IPBlockingInteractor(BaseInteractor):
    """
    Interactor for IP blocking operations.
    """
    
    def block_ip_address(self, ip_address: str, block_reason: str = 'manual', 
                       hours: int = None, blocked_by_id: int = None) -> Dict[str, Any]:
        """
        Block an IP address.
        
        Args:
            ip_address: IP address to block
            block_reason: Reason for blocking
            hours: Duration in hours (None for permanent)
            blocked_by_id: User ID who performed the block
            
        Returns:
            Block result
        """
        try:
            # Validate IP address
            if not RateLimitHelper.is_valid_ip_address(ip_address):
                return {'success': False, 'error': 'Invalid IP address'}
            
            # Create IP block
            block_repo = self._get_repository('ip_block_list')
            block = block_repo.block_ip(ip_address, block_reason, hours, blocked_by_id)
            
            # Clear rate limit counters for this IP
            self._clear_ip_counters(ip_address)
            
            logger.info(f"IP {ip_address} blocked for reason: {block_reason}")
            
            return {
                'success': True,
                'block_id': block.id,
                'ip_address': ip_address,
                'block_reason': block_reason,
                'permanent': block.permanent,
                'expires_at': block.expires_at
            }
            
        except Exception as e:
            logger.error(f"Failed to block IP address: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def unblock_ip_address(self, ip_address: str) -> Dict[str, Any]:
        """
        Unblock an IP address.
        
        Args:
            ip_address: IP address to unblock
            
        Returns:
            Unblock result
        """
        try:
            block_repo = self._get_repository('ip_block_list')
            updated_count = block_repo.unblock_ip(ip_address)
            
            if updated_count > 0:
                logger.info(f"IP {ip_address} unblocked")
                return {
                    'success': True,
                    'ip_address': ip_address,
                    'unblocked_count': updated_count
                }
            else:
                return {
                    'success': False,
                    'error': 'No active blocks found for this IP'
                }
            
        except Exception as e:
            logger.error(f"Failed to unblock IP address: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def bulk_block_ips(self, ip_addresses: List[str], block_reason: str = 'manual', 
                      hours: int = None, blocked_by_id: int = None) -> Dict[str, Any]:
        """
        Bulk block IP addresses.
        
        Args:
            ip_addresses: List of IP addresses to block
            block_reason: Reason for blocking
            hours: Duration in hours (None for permanent)
            blocked_by_id: User ID who performed the block
            
        Returns:
            Bulk block result
        """
        try:
            block_repo = self._get_repository('ip_block_list')
            blocked_count = block_repo.bulk_block(ip_addresses, block_reason, hours)
            
            logger.info(f"Bulk blocked {blocked_count} IP addresses for reason: {block_reason}")
            
            return {
                'success': True,
                'total_ips': len(ip_addresses),
                'blocked_count': blocked_count,
                'failed_count': len(ip_addresses) - blocked_count,
                'block_reason': block_reason
            }
            
        except Exception as e:
            logger.error(f"Failed to bulk block IPs: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_blocking_statistics(self) -> Dict[str, Any]:
        """
        Get IP blocking statistics.
        
        Returns:
            Blocking statistics
        """
        try:
            block_repo = self._get_repository('ip_block_list')
            stats = block_repo.get_statistics()
            
            # Get additional statistics
            active_blocks = block_repo.get_active()
            expired_blocks = block_repo.get_expired()
            
            return {
                'success': True,
                'statistics': stats,
                'active_blocks_count': active_blocks.count(),
                'expired_blocks_count': expired_blocks.count(),
                'blocks_expiring_soon': block_repo.get_expiring_soon(hours=24).count()
            }
            
        except Exception as e:
            logger.error(f"Failed to get blocking statistics: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _clear_ip_counters(self, ip_address: str):
        """Clear rate limit counters for IP address."""
        from django.core.cache import cache
        
        cache_keys = cache.keys(f"rate_limit:ip:{ip_address}:*")
        for key in cache_keys:
            cache.delete(key)


class AbuseReportInteractor(BaseInteractor):
    """
    Interactor for abuse report operations.
    """
    
    def create_abuse_report(self, report_data: Dict[str, Any], reported_by_id: int = None) -> Dict[str, Any]:
        """
        Create an abuse report.
        
        Args:
            report_data: Abuse report data
            reported_by_id: User ID creating the report
            
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
            abuse_repo = self._get_repository('abuse_report')
            
            # Add reporter if provided
            if reported_by_id:
                report_data['created_by_id'] = reported_by_id
            
            report = abuse_repo.create(**report_data)
            
            # Auto-investigate high severity reports
            if report_data['severity'] >= 4:
                self._auto_investigate_report(report.id)
            
            # Auto-block for critical severity
            if report_data['severity'] == 5 and report_data.get('ip_address'):
                self._auto_block_ip_from_report(report)
            
            logger.info(f"Abuse report created: {report.id} - {report_data['abuse_type']}")
            
            return {
                'success': True,
                'report_id': report.id,
                'abuse_type': report.abuse_type,
                'severity': report.severity,
                'auto_investigated': report_data['severity'] >= 4,
                'auto_blocked': report_data['severity'] == 5 and report_data.get('ip_address')
            }
            
        except Exception as e:
            logger.error(f"Failed to create abuse report: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def investigate_report(self, report_id: int, investigated_by_id: int) -> Dict[str, Any]:
        """
        Mark abuse report as investigated.
        
        Args:
            report_id: Report ID
            investigated_by_id: User ID investigating
            
        Returns:
            Investigation result
        """
        try:
            abuse_repo = self._get_repository('abuse_report')
            success = abuse_repo.mark_investigated(report_id, investigated_by_id)
            
            if success:
                logger.info(f"Abuse report {report_id} marked as investigated")
                return {
                    'success': True,
                    'report_id': report_id,
                    'investigated_by_id': investigated_by_id
                }
            else:
                return {'success': False, 'error': 'Report not found'}
            
        except Exception as e:
            logger.error(f"Failed to investigate abuse report: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_abuse_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get abuse report statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Abuse statistics
        """
        try:
            abuse_repo = self._get_repository('abuse_report')
            stats = abuse_repo.get_statistics(days)
            
            return {
                'success': True,
                'period_days': days,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get abuse statistics: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _auto_investigate_report(self, report_id: int):
        """Auto-investigate high severity abuse reports."""
        # This would implement auto-investigation logic
        pass
    
    def _auto_block_ip_from_report(self, report):
        """Auto-block IP from critical abuse report."""
        blocking_interactor = IPBlockingInteractor()
        blocking_interactor.block_ip_address(
            ip_address=report.ip_address,
            block_reason='abuse_report',
            hours=24 * 7  # 1 week
        )


class ConfigurationInteractor(BaseInteractor):
    """
    Interactor for rate limit configuration operations.
    """
    
    def optimize_configurations(self, config_id: int = None) -> Dict[str, Any]:
        """
        Optimize rate limit configurations.
        
        Args:
            config_id: Specific config ID to optimize (None for all)
            
        Returns:
            Optimization results
        """
        try:
            optimizer = RateLimitOptimization()
            
            if config_id:
                # Optimize specific config
                suggestion = optimizer.suggest_config_adjustments(config_id)
                results = [suggestion] if 'suggestions' in suggestion else []
            else:
                # Optimize all active configs
                config_repo = self._get_repository('rate_limit_config')
                configs = config_repo.get_active_configs()
                
                results = []
                for config in configs:
                    try:
                        suggestion = optimizer.suggest_config_adjustments(config.id)
                        if 'suggestions' in suggestion:
                            results.append(suggestion)
                    except Exception as e:
                        logger.error(f"Failed to optimize config {config.id}: {str(e)}")
                        continue
            
            return {
                'success': True,
                'optimized_configs': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Failed to optimize configs: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_configuration_health(self) -> Dict[str, Any]:
        """
        Get configuration health metrics.
        
        Returns:
            Configuration health data
        """
        try:
            config_repo = self._get_repository('rate_limit_config')
            
            # Get statistics
            total_configs = config_repo.count()
            active_configs = config_repo.get_active_configs().count()
            high_block_rate_configs = config_repo.get_high_block_rate_configs().count()
            
            # Calculate health score
            if total_configs > 0:
                active_ratio = (active_configs / total_configs) * 100
                health_score = active_ratio - (high_block_rate_configs / total_configs) * 10
            else:
                health_score = 100
            
            return {
                'success': True,
                'health_score': max(0, health_score),
                'total_configs': total_configs,
                'active_configs': active_configs,
                'inactive_configs': total_configs - active_configs,
                'high_block_rate_configs': high_block_rate_configs,
                'health_status': self._get_health_status(health_score)
            }
            
        except Exception as e:
            logger.error(f"Failed to get configuration health: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_health_status(self, score: float) -> str:
        """Get health status based on score."""
        if score >= 80:
            return 'excellent'
        elif score >= 60:
            return 'good'
        elif score >= 40:
            return 'fair'
        elif score >= 20:
            return 'poor'
        else:
            return 'critical'


# Export interactor classes
__all__ = [
    'BaseInteractor',
    'RateLimitInteractor',
    'UserProfileInteractor',
    'IPBlockingInteractor',
    'AbuseReportInteractor',
    'ConfigurationInteractor'
]
