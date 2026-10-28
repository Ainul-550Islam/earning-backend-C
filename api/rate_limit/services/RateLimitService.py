from typing import Dict, Any, List, Optional, Tuple
import time
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from api.rate_limit.services.RedisRateLimiter import RedisRateLimiter
from api.rate_limit.services.TokenBucket import TokenBucket, LeakyBucket, FixedWindowCounter
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.IPBlockService import IPBlockService
import logging

logger = logging.getLogger(__name__)


class RateLimitService:
    """Main rate limit service for earning application"""
    
    def __init__(self):
        self.redis_limiter = RedisRateLimiter()
        self.algorithm_cache = {}  # Cache algorithm instances
        self.abuse_detection_service = AbuseDetectionService()
        self.ip_block_service = IPBlockService()
    
    def get_applicable_configs(self, request) -> List[RateLimitConfig]:
        """
        Get all applicable rate limit configs for a request
        """
        from django.contrib.auth.models import AnonymousUser
        
        # Base query for active configs
        query = Q(is_active=True)
        
        # Add conditions based on request
        conditions = Q()
        
        # Global configs
        conditions |= Q(rate_limit_type='global')
        
        # User-specific configs
        if request.user and not isinstance(request.user, AnonymousUser):
            conditions |= Q(rate_limit_type='user', user=request.user)
            
            # Check for user group configs
            if hasattr(request.user, 'groups'):
                user_groups = request.user.groups.all()
                if user_groups:
                    conditions |= Q(rate_limit_type='user', user__groups__in=user_groups)
        
        # IP-based configs
        ip_address = self._get_client_ip(request)
        if ip_address:
            conditions |= Q(rate_limit_type='ip', ip_address=ip_address)
        
        # Endpoint-based configs
        if request.path:
            # Exact match
            conditions |= Q(rate_limit_type='endpoint', endpoint=request.path)
            # Prefix match (for API endpoints)
            conditions |= Q(rate_limit_type='endpoint', endpoint__startswith=request.path.rsplit('/', 1)[0])
        
        # Referral-based configs
        if request.user and not isinstance(request.user, AnonymousUser):
            if hasattr(request.user, 'referral_code') and request.user.referral_code:
                conditions |= Q(rate_limit_type='referral')
        
        # Task-based configs
        task_type = getattr(request, 'task_type', None)
        if task_type:
            conditions |= Q(rate_limit_type='task', task_type=task_type)
        
        # Combine queries
        query &= conditions
        
        # Get configs
        configs = RateLimitConfig.objects.filter(query).distinct()
        
        # Order by specificity (more specific first)
        return sorted(configs, key=lambda x: self._get_config_priority(x), reverse=True)
    
    def _get_config_priority(self, config: RateLimitConfig) -> int:
        """Get priority score for config (higher = more specific)"""
        priority = 0
        
        if config.user:
            priority += 4  # User-specific configs are most specific
        
        if config.ip_address:
            priority += 3
        
        if config.endpoint:
            priority += 2
        
        if config.task_type or config.offer_wall:
            priority += 1
        
        return priority
    
    def check_request(self, request, log_request: bool = True) -> Dict[str, Any]:
        """
        Check rate limit for a request
        
        Returns:
            dict: Result containing is_allowed, metadata, and configs
        """
        from django.contrib.auth.models import AnonymousUser
        
        # Get applicable configs
        configs = self.get_applicable_configs(request)
        
        if not configs:
            return {
                'is_allowed': True,
                'metadata': {'reason': 'no_configs'},
                'failed_configs': [],
                'configs': []
            }
        
        # Check all configs
        is_allowed, failed_configs = self.redis_limiter.check_multiple_limits(request, configs)
        
        # Log the request if needed
        if log_request:
            self._log_request(request, configs, failed_configs, is_allowed)
        
        # Update user profile stats
        if request.user and not isinstance(request.user, AnonymousUser):
            self._update_user_stats(request.user, is_allowed)
        
        return {
            'is_allowed': is_allowed,
            'metadata': {
                'total_configs': len(configs),
                'failed_count': len(failed_configs),
                'remaining_configs': len(configs) - len(failed_configs)
            },
            'failed_configs': failed_configs,
            'configs': configs
        }
    
    def _log_request(self, request, configs, failed_configs, is_allowed):
        """Log rate limit request"""
        from django.contrib.auth.models import AnonymousUser
        
        try:
            user = request.user if request.user and not isinstance(request.user, AnonymousUser) else None
            ip_address = self._get_client_ip(request)
            
            # Determine status
            if not is_allowed and failed_configs:
                status = 'blocked'
                failed_config = failed_configs[0]['config']
            elif not is_allowed:
                status = 'exceeded'
                failed_config = configs[0] if configs else None
            else:
                status = 'allowed'
                failed_config = None
            
            # Create log entry
            log_data = {
                'user': user,
                'ip_address': ip_address,
                'endpoint': request.path,
                'request_method': request.method,
                'config': failed_config,
                'status': status,
                'requests_count': 1
            }
            
            # Add earning app specific data
            for attr in ['task_id', 'offer_id', 'referral_code']:
                if hasattr(request, attr):
                    log_data[attr] = getattr(request, attr)
            
            RateLimitLog.objects.create(**log_data)
            
        except Exception as e:
            # Log error but don't break the request
            if settings.DEBUG:
                print(f"Rate limit logging error: {e}")
    
    def _update_user_stats(self, user, is_allowed: bool):
        """Update user rate limit statistics"""
        try:
            profile, created = UserRateLimitProfile.objects.get_or_create(user=user)
            
            # Update last request time
            profile.last_request_at = timezone.now()
            
            # Update stats
            profile.total_requests += 1
            if not is_allowed:
                profile.blocked_requests += 1
            
            profile.save()
            
        except Exception as e:
            if settings.DEBUG:
                print(f"User stats update error: {e}")
    
    def get_user_rate_limit_info(self, user) -> Dict[str, Any]:
        """Get rate limit information for a user"""
        try:
            profile = UserRateLimitProfile.objects.get(user=user)
            configs = RateLimitConfig.objects.filter(
                Q(is_active=True) & 
                (Q(rate_limit_type='user', user=user) | Q(rate_limit_type='global'))
            )
            
            info = {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'is_premium': profile.is_premium,
                    'total_requests': profile.total_requests,
                    'blocked_requests': profile.blocked_requests,
                    'success_rate': ((profile.total_requests - profile.blocked_requests) / 
                                   profile.total_requests * 100) if profile.total_requests > 0 else 100
                },
                'configs': []
            }
            
            # Get current status for each config
            for config in configs:
                identifier = f"user:{user.id}"
                if config.endpoint:
                    identifier += f":endpoint:{config.endpoint}"
                
                limit_info = self.redis_limiter.get_rate_limit_info(identifier, config)
                info['configs'].append({
                    'config': config.name,
                    'current': limit_info['current'],
                    'limit': limit_info['limit'],
                    'remaining': limit_info['remaining'],
                    'reset_time': limit_info['reset_time']
                })
            
            return info
            
        except UserRateLimitProfile.DoesNotExist:
            return {'error': 'User profile not found'}
    
    # Earning app specific methods
    def check_task_completion_limit(self, user, task_type: str) -> Dict[str, Any]:
        """
        Check if user can complete more tasks of a specific type today
        """
        from api.rate_limit.models import UserRateLimitProfile
        
        try:
            profile = UserRateLimitProfile.objects.get(user=user)
            
            # Premium users get higher limits
            base_limit = 10  # Default daily limit
            if profile.is_premium:
                base_limit = 50  # Premium daily limit
            
            # Check custom limit
            if profile.custom_daily_limit:
                base_limit = profile.custom_daily_limit
            
            # Check rate limit
            is_allowed, metadata = self.redis_limiter.check_task_rate_limit(
                user.id, task_type, base_limit
            )
            
            return {
                'is_allowed': is_allowed,
                'limit': base_limit,
                'current': metadata['current'],
                'remaining': metadata['remaining'],
                'reset_time': metadata['reset_time'],
                'is_premium': profile.is_premium
            }
            
        except UserRateLimitProfile.DoesNotExist:
            return {
                'is_allowed': True,
                'limit': 10,
                'current': 0,
                'remaining': 10,
                'reset_time': 0,
                'is_premium': False
            }
    
    def check_offer_access_limit(self, user, offer_wall: str) -> Dict[str, Any]:
        """
        Check if user can access more offers from a specific offer wall
        """
        # Default hourly limit
        hourly_limit = 20
        
        # Check rate limit
        is_allowed, metadata = self.redis_limiter.check_offer_wall_limit(
            user.id, offer_wall, hourly_limit
        )
        
        return {
            'is_allowed': is_allowed,
            'limit': hourly_limit,
            'current': metadata['current'],
            'remaining': metadata['remaining'],
            'reset_time': metadata['reset_time']
        }
    
    def check_referral_activity(self, ip_address: str) -> Dict[str, Any]:
        """
        Check referral click limit for an IP address
        """
        # Daily referral click limit
        daily_limit = 50
        
        is_allowed, metadata = self.redis_limiter.check_referral_click_limit(
            ip_address, daily_limit
        )
        
        return {
            'is_allowed': is_allowed,
            'limit': daily_limit,
            'current': metadata['current'],
            'remaining': metadata['remaining'],
            'reset_time': metadata['reset_time']
        }
    
    def reset_user_limits(self, user):
        """Reset all rate limits for a user"""
        configs = RateLimitConfig.objects.filter(
            Q(is_active=True) & 
            (Q(rate_limit_type='user', user=user) | Q(rate_limit_type='global'))
        )
        
        for config in configs:
            identifier = f"user:{user.id}"
            if config.endpoint:
                identifier += f":endpoint:{config.endpoint}"
            
            self.redis_limiter.reset_rate_limit(identifier, config)
        
        # Also reset task limits
        today = time.strftime("%Y-%m-%d")
        task_keys = self.redis_limiter.redis_client.keys(f"task_limit:{user.id}:*:{today}")
        for key in task_keys:
            self.redis_limiter.redis_client.delete(key)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get rate limit system health information"""
        try:
            total_configs = RateLimitConfig.objects.count()
            active_configs = RateLimitConfig.objects.filter(is_active=True).count()
            total_logs = RateLimitLog.objects.count()
            recent_logs = RateLimitLog.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            # Get Redis info
            redis_info = {}
            try:
                redis_info = self.redis_limiter.redis_client.info()
            except:
                redis_info = {'error': 'Redis not available'}
            
            return {
                'status': 'healthy',
                'configs': {
                    'total': total_configs,
                    'active': active_configs,
                    'inactive': total_configs - active_configs
                },
                'logs': {
                    'total': total_logs,
                    'recent_hour': recent_logs
                },
                'redis': redis_info,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    # ─────────────────────────────────────────────────────────
    # Integration-friendly methods (called by integration_service.py)
    # ─────────────────────────────────────────────────────────

    def check_request_by_config(
        self,
        config,
        identifier: str,
        user_id=None,
        ip_address: str = '',
        extra_context: dict = None,
    ) -> dict:
        """
        Check rate limit given an explicit config object + identifier.
        Called by integration_service._run_check().

        Returns unified dict with keys: allowed, reason, remaining, reset_at, extra
        """
        try:
            is_allowed, metadata = self.redis_limiter.check_rate_limit_by_identifier(
                identifier=identifier,
                config=config,
            )

            # Map to unified response keys
            return {
                'allowed': is_allowed,
                'reason': 'rate_limit_exceeded' if not is_allowed else '',
                'remaining': metadata.get('remaining', -1),
                'reset_at': metadata.get('reset_time'),
                'extra': {
                    'current': metadata.get('current', 0),
                    'limit': metadata.get('limit', config.requests_per_unit),
                    'identifier': identifier,
                    **(extra_context or {}),
                },
            }
        except Exception as e:
            logger.error(f'check_request_by_config error: {e}')
            return {'allowed': True, 'reason': 'error_fail_open', 'remaining': -1, 'reset_at': None, 'extra': {}}

    def reset_user_limits_by_id(self, user_id: int, action_names: list = None):
        """
        Reset rate limits for a user by user_id.
        Called by integration_service.reset_user_limits().
        action_names: list of config names to reset (None = reset all).
        """
        try:
            from api.rate_limit.models import RateLimitConfig
            from django.db.models import Q

            configs = RateLimitConfig.objects.filter(is_active=True)
            if action_names:
                configs = configs.filter(name__in=action_names)
            else:
                configs = configs.filter(
                    Q(rate_limit_type='user', user_id=user_id) |
                    Q(rate_limit_type='global') |
                    Q(rate_limit_type='endpoint')
                )

            identifier = f'user:{user_id}'
            for config in configs:
                try:
                    self.redis_limiter.reset_rate_limit(identifier, config)
                except Exception as e:
                    logger.debug(f'reset_rate_limit error for config {config.name}: {e}')

            # Also reset Redis task keys
            try:
                today = __import__('time').strftime('%Y-%m-%d')
                keys = self.redis_limiter.redis_client.keys(f'task_limit:{user_id}:*:{today}')
                for key in keys:
                    self.redis_limiter.redis_client.delete(key)
            except Exception:
                pass

            logger.info(f'[RateLimitService] Reset limits for user_id={user_id} actions={action_names}')
        except Exception as e:
            logger.error(f'reset_user_limits_by_id error: {e}')

    def check_rate_limit(self, identifier: str = None, config=None, request=None,
                         user=None, endpoint=None, method=None, **kwargs) -> dict:
        """Check rate limit for identifier. Returns {allowed, remaining, reset_at}.
        Supports both positional identifier and keyword user=/endpoint=/method=."""
        try:
            # Build identifier from kwargs when not supplied directly
            if identifier is None:
                if user and hasattr(user, 'pk') and user.pk:
                    identifier = str(user.pk)
                elif endpoint:
                    identifier = endpoint
                else:
                    identifier = 'anonymous'

            if config is None:
                return {'allowed': True, 'remaining': -1, 'reset_at': None}
            return self.check_request_by_config(config=config, identifier=identifier)
        except Exception:
            return {'allowed': True, 'remaining': -1, 'reset_at': None}

    def is_rate_limited(self, identifier: str, config=None) -> bool:
        """Simple bool check - True if rate limited (blocked)."""
        result = self.check_rate_limit(identifier=identifier, config=config)
        return not result.get('allowed', True)

    def get_rate_limit_info(self, identifier: str, config=None) -> dict:
        """Get current rate limit info for identifier."""
        return self.check_rate_limit(identifier=identifier, config=config)
