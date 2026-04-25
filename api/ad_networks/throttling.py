"""
api/ad_networks/throttling.py
Throttling utilities for ad networks module
SaaS-ready with tenant support
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework.exceptions import Throttled

from .constants import (
    API_RATE_LIMIT_PER_IP, API_RATE_LIMIT_PER_TENANT,
    API_RATE_LIMIT_PER_USER, CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


class ThrottleType(Enum):
    """Throttle types"""
    
    IP_BASED = "ip_based"
    USER_BASED = "user_based"
    TENANT_BASED = "tenant_based"
    ENDPOINT_BASED = "endpoint_based"
    OFFER_BASED = "offer_based"
    CONVERSION_BASED = "conversion_based"
    REWARD_BASED = "reward_based"


class ThrottleScope(Enum):
    """Throttle scopes"""
    
    # General API throttles
    API_READ = "api_read"
    API_WRITE = "api_write"
    API_UPLOAD = "api_upload"
    
    # Offer throttles
    OFFER_CLICK = "offer_click"
    OFFER_ENGAGE = "offer_engage"
    OFFER_COMPLETE = "offer_complete"
    
    # Conversion throttles
    CONVERSION_CREATE = "conversion_create"
    CONVERSION_VERIFY = "conversion_verify"
    
    # Reward throttles
    REWARD_REQUEST = "reward_request"
    REWARD_PAYOUT = "reward_payout"
    
    # Admin throttles
    ADMIN_SYNC = "admin_sync"
    ADMIN_EXPORT = "admin_export"
    ADMIN_BULK = "admin_bulk"


class ThrottleConfig:
    """Throttle configuration"""
    
    def __init__(self, scope: ThrottleScope, throttle_type: ThrottleType,
                 rate: str, burst: int = None, period: int = None):
        self.scope = scope
        self.throttle_type = throttle_type
        self.rate = rate
        self.burst = burst
        self.period = period
        self.cache_timeout = period or 3600
    
    def get_cache_key(self, request) -> str:
        """Generate cache key for throttle"""
        key_parts = [f"throttle_{self.scope.value}_{self.throttle_type.value}"]
        
        if self.throttle_type == ThrottleType.IP_BASED:
            key_parts.append(self._get_client_ip(request))
        elif self.throttle_type == ThrottleType.USER_BASED:
            if request.user.is_authenticated:
                key_parts.append(f"user_{request.user.id}")
            else:
                key_parts.append(f"anon_{self._get_client_ip(request)}")
        elif self.throttle_type == ThrottleType.TENANT_BASED:
            tenant_id = getattr(request, 'tenant_id', 'default')
            key_parts.append(f"tenant_{tenant_id}")
        elif self.throttle_type == ThrottleType.ENDPOINT_BASED:
            key_parts.append(f"endpoint_{request.resolver_match.url_name}")
        elif self.throttle_type == ThrottleType.OFFER_BASED:
            offer_id = request.resolver_match.kwargs.get('pk')
            if offer_id:
                key_parts.append(f"offer_{offer_id}")
        elif self.throttle_type == ThrottleType.CONVERSION_BASED:
            conversion_id = request.resolver_match.kwargs.get('pk')
            if conversion_id:
                key_parts.append(f"conversion_{conversion_id}")
        elif self.throttle_type == ThrottleType.REWARD_BASED:
            reward_id = request.resolver_match.kwargs.get('pk')
            if reward_id:
                key_parts.append(f"reward_{reward_id}")
        
        return '_'.join(key_parts)
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', '')


class ThrottleManager:
    """Manager for throttling operations"""
    
    def __init__(self):
        self.configs: Dict[ThrottleScope, List[ThrottleConfig]] = {}
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Setup default throttle configurations"""
        # API read throttles
        self.configs[ThrottleScope.API_READ] = [
            ThrottleConfig(
                ThrottleScope.API_READ,
                ThrottleType.IP_BASED,
                "1000/hour"
            ),
            ThrottleConfig(
                ThrottleScope.API_READ,
                ThrottleType.USER_BASED,
                "5000/hour"
            ),
            ThrottleConfig(
                ThrottleScope.API_READ,
                ThrottleType.TENANT_BASED,
                "10000/hour"
            )
        ]
        
        # API write throttles
        self.configs[ThrottleScope.API_WRITE] = [
            ThrottleConfig(
                ThrottleScope.API_WRITE,
                ThrottleType.IP_BASED,
                "100/hour"
            ),
            ThrottleConfig(
                ThrottleScope.API_WRITE,
                ThrottleType.USER_BASED,
                "500/hour"
            ),
            ThrottleConfig(
                ThrottleScope.API_WRITE,
                ThrottleType.TENANT_BASED,
                "1000/hour"
            )
        ]
        
        # API upload throttles
        self.configs[ThrottleScope.API_UPLOAD] = [
            ThrottleConfig(
                ThrottleScope.API_UPLOAD,
                ThrottleType.USER_BASED,
                "10/hour"
            ),
            ThrottleConfig(
                ThrottleScope.API_UPLOAD,
                ThrottleType.TENANT_BASED,
                "100/hour"
            )
        ]
        
        # Offer click throttles
        self.configs[ThrottleScope.OFFER_CLICK] = [
            ThrottleConfig(
                ThrottleScope.OFFER_CLICK,
                ThrottleType.IP_BASED,
                "100/minute"
            ),
            ThrottleConfig(
                ThrottleScope.OFFER_CLICK,
                ThrottleType.USER_BASED,
                "50/minute"
            )
        ]
        
        # Offer engage throttles
        self.configs[ThrottleScope.OFFER_ENGAGE] = [
            ThrottleConfig(
                ThrottleScope.OFFER_ENGAGE,
                ThrottleType.USER_BASED,
                "20/minute"
            ),
            ThrottleConfig(
                ThrottleScope.OFFER_ENGAGE,
                ThrottleType.OFFER_BASED,
                "5/minute"
            )
        ]
        
        # Offer complete throttles
        self.configs[ThrottleScope.OFFER_COMPLETE] = [
            ThrottleConfig(
                ThrottleScope.OFFER_COMPLETE,
                ThrottleType.USER_BASED,
                "10/hour"
            )
        ]
        
        # Conversion create throttles
        self.configs[ThrottleScope.CONVERSION_CREATE] = [
            ThrottleConfig(
                ThrottleScope.CONVERSION_CREATE,
                ThrottleType.IP_BASED,
                "50/hour"
            ),
            ThrottleConfig(
                ThrottleScope.CONVERSION_CREATE,
                ThrottleType.USER_BASED,
                "25/hour"
            ),
            ThrottleConfig(
                ThrottleScope.CONVERSION_CREATE,
                ThrottleType.TENANT_BASED,
                "500/hour"
            )
        ]
        
        # Conversion verify throttles
        self.configs[ThrottleScope.CONVERSION_VERIFY] = [
            ThrottleConfig(
                ThrottleScope.CONVERSION_VERIFY,
                ThrottleType.USER_BASED,
                "100/hour"
            )
        ]
        
        # Reward request throttles
        self.configs[ThrottleScope.REWARD_REQUEST] = [
            ThrottleConfig(
                ThrottleScope.REWARD_REQUEST,
                ThrottleType.USER_BASED,
                "20/hour"
            )
        ]
        
        # Reward payout throttles
        self.configs[ThrottleScope.REWARD_PAYOUT] = [
            ThrottleConfig(
                ThrottleScope.REWARD_PAYOUT,
                ThrottleType.USER_BASED,
                "5/day"
            )
        ]
        
        # Admin sync throttles
        self.configs[ThrottleScope.ADMIN_SYNC] = [
            ThrottleConfig(
                ThrottleScope.ADMIN_SYNC,
                ThrottleType.TENANT_BASED,
                "10/hour"
            )
        ]
        
        # Admin export throttles
        self.configs[ThrottleScope.ADMIN_EXPORT] = [
            ThrottleConfig(
                ThrottleScope.ADMIN_EXPORT,
                ThrottleType.USER_BASED,
                "5/hour"
            ),
            ThrottleConfig(
                ThrottleScope.ADMIN_EXPORT,
                ThrottleType.TENANT_BASED,
                "20/hour"
            )
        ]
        
        # Admin bulk throttles
        self.configs[ThrottleScope.ADMIN_BULK] = [
            ThrottleConfig(
                ThrottleScope.ADMIN_BULK,
                ThrottleType.USER_BASED,
                "10/hour"
            )
        ]
    
    def check_throttle(self, scope: ThrottleScope, request) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is throttled"""
        configs = self.configs.get(scope, [])
        
        for config in configs:
            is_throttled, info = self._check_config_throttle(config, request)
            if is_throttled:
                return True, info
        
        return False, {}
    
    def _check_config_throttle(self, config: ThrottleConfig, 
                              request) -> Tuple[bool, Dict[str, Any]]:
        """Check specific throttle configuration"""
        try:
            cache_key = config.get_cache_key(request)
            current_count = cache.get(cache_key, 0)
            
            # Parse rate
            rate_parts = config.rate.split('/')
            if len(rate_parts) != 2:
                return False, {}
            
            limit = int(rate_parts[0])
            period = rate_parts[1]
            
            # Convert period to seconds
            if period == 'second':
                period_seconds = 1
            elif period == 'minute':
                period_seconds = 60
            elif period == 'hour':
                period_seconds = 3600
            elif period == 'day':
                period_seconds = 86400
            else:
                period_seconds = 3600  # Default to hour
            
            # Check if limit exceeded
            if current_count >= limit:
                # Calculate retry after
                retry_after = cache.ttl(cache_key)
                
                return True, {
                    'throttle_type': config.throttle_type.value,
                    'limit': limit,
                    'period': period,
                    'current': current_count,
                    'retry_after': retry_after,
                    'cache_key': cache_key
                }
            
            # Increment counter
            cache.set(cache_key, current_count + 1, timeout=period_seconds)
            
            return False, {
                'throttle_type': config.throttle_type.value,
                'limit': limit,
                'period': period,
                'current': current_count + 1,
                'remaining': limit - (current_count + 1),
                'cache_key': cache_key
            }
            
        except Exception as e:
            logger.error(f"Error checking throttle: {str(e)}")
            return False, {}
    
    def add_config(self, scope: ThrottleScope, config: ThrottleConfig):
        """Add throttle configuration"""
        if scope not in self.configs:
            self.configs[scope] = []
        
        self.configs[scope].append(config)
    
    def remove_config(self, scope: ThrottleScope, 
                     throttle_type: ThrottleType):
        """Remove throttle configuration"""
        if scope in self.configs:
            self.configs[scope] = [
                config for config in self.configs[scope]
                if config.throttle_type != throttle_type
            ]
    
    def get_throttle_stats(self, scope: ThrottleScope, request) -> Dict[str, Any]:
        """Get throttle statistics"""
        configs = self.configs.get(scope, [])
        stats = {}
        
        for config in configs:
            cache_key = config.get_cache_key(request)
            current_count = cache.get(cache_key, 0)
            ttl = cache.ttl(cache_key)
            
            # Parse rate
            rate_parts = config.rate.split('/')
            if len(rate_parts) == 2:
                limit = int(rate_parts[0])
                period = rate_parts[1]
                
                stats[config.throttle_type.value] = {
                    'limit': limit,
                    'period': period,
                    'current': current_count,
                    'remaining': max(0, limit - current_count),
                    'reset_in': ttl
                }
        
        return stats
    
    def reset_throttle(self, scope: ThrottleScope, request):
        """Reset throttle counters"""
        configs = self.configs.get(scope, [])
        
        for config in configs:
            cache_key = config.get_cache_key(request)
            cache.delete(cache_key)


# Global throttle manager instance
throttle_manager = ThrottleManager()


class AdNetworksThrottle(BaseThrottle):
    """Custom throttle for ad networks"""
    
    def __init__(self, scope: ThrottleScope):
        self.scope = scope
        super().__init__()
    
    def allow_request(self, request, view) -> bool:
        """Check if request is allowed"""
        try:
            is_throttled, info = throttle_manager.check_throttle(self.scope, request)
            
            if is_throttled:
                # Set throttle info for response
                self.throttle_info = info
                
                # Raise throttled exception
                raise Throttled(
                    detail={
                        'error': 'Request throttled',
                        'throttle_type': info['throttle_type'],
                        'limit': info['limit'],
                        'period': info['period'],
                        'retry_after': info.get('retry_after', 60)
                    },
                    wait=info.get('retry_after', 60)
                )
            
            return True
            
        except Throttled:
            raise
        except Exception as e:
            logger.error(f"Error in throttle check: {str(e)}")
            # Allow request on error
            return True


class APIReadThrottle(AdNetworksThrottle):
    """Throttle for API read operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.API_READ)


class APIWriteThrottle(AdNetworksThrottle):
    """Throttle for API write operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.API_WRITE)


class APIUploadThrottle(AdNetworksThrottle):
    """Throttle for API upload operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.API_UPLOAD)


class OfferClickThrottle(AdNetworksThrottle):
    """Throttle for offer click operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.OFFER_CLICK)


class OfferEngageThrottle(AdNetworksThrottle):
    """Throttle for offer engage operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.OFFER_ENGAGE)


class OfferCompleteThrottle(AdNetworksThrottle):
    """Throttle for offer complete operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.OFFER_COMPLETE)


class ConversionCreateThrottle(AdNetworksThrottle):
    """Throttle for conversion create operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.CONVERSION_CREATE)


class ConversionVerifyThrottle(AdNetworksThrottle):
    """Throttle for conversion verify operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.CONVERSION_VERIFY)


class RewardRequestThrottle(AdNetworksThrottle):
    """Throttle for reward request operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.REWARD_REQUEST)


class RewardPayoutThrottle(AdNetworksThrottle):
    """Throttle for reward payout operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.REWARD_PAYOUT)


class AdminSyncThrottle(AdNetworksThrottle):
    """Throttle for admin sync operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.ADMIN_SYNC)


class AdminExportThrottle(AdNetworksThrottle):
    """Throttle for admin export operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.ADMIN_EXPORT)


class AdminBulkThrottle(AdNetworksThrottle):
    """Throttle for admin bulk operations"""
    
    def __init__(self):
        super().__init__(ThrottleScope.ADMIN_BULK)


# Decorator for throttling
def throttle(scope: ThrottleScope):
    """Decorator to apply throttling to view"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            try:
                is_throttled, info = throttle_manager.check_throttle(scope, request)
                
                if is_throttled:
                    response = HttpResponse(
                        json.dumps({
                            'success': False,
                            'error': 'Request throttled',
                            'throttle_type': info['throttle_type'],
                            'limit': info['limit'],
                            'period': info['period'],
                            'retry_after': info.get('retry_after', 60)
                        }),
                        content_type='application/json',
                        status=429
                    )
                    response['Retry-After'] = str(info.get('retry_after', 60))
                    return response
                
                return view_func(request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in throttle decorator: {str(e)}")
                return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Helper functions
def get_throttle_headers(request, scope: ThrottleScope) -> Dict[str, str]:
    """Get throttle headers for response"""
    stats = throttle_manager.get_throttle_stats(scope, request)
    headers = {}
    
    for throttle_type, info in stats.items():
        headers[f'X-RateLimit-{throttle_type.title()}-Limit'] = str(info['limit'])
        headers[f'X-RateLimit-{throttle_type.title()}-Remaining'] = str(info['remaining'])
        headers[f'X-RateLimit-{throttle_type.title()}-Reset'] = str(info['reset_in'])
    
    return headers


def reset_user_throttles(request):
    """Reset all throttles for current user"""
    for scope in ThrottleScope:
        throttle_manager.reset_throttle(scope, request)


def get_throttle_info(request) -> Dict[str, Any]:
    """Get comprehensive throttle information"""
    info = {}
    
    for scope in ThrottleScope:
        info[scope.value] = throttle_manager.get_throttle_stats(scope, request)
    
    return info


# Export all classes and functions
__all__ = [
    # Enums
    'ThrottleType',
    'ThrottleScope',
    
    # Classes
    'ThrottleConfig',
    'ThrottleManager',
    'AdNetworksThrottle',
    
    # Specific throttle classes
    'APIReadThrottle',
    'APIWriteThrottle',
    'APIUploadThrottle',
    'OfferClickThrottle',
    'OfferEngageThrottle',
    'OfferCompleteThrottle',
    'ConversionCreateThrottle',
    'ConversionVerifyThrottle',
    'RewardRequestThrottle',
    'RewardPayoutThrottle',
    'AdminSyncThrottle',
    'AdminExportThrottle',
    'AdminBulkThrottle',
    
    # Global instance
    'throttle_manager',
    
    # Decorator
    'throttle',
    
    # Helper functions
    'get_throttle_headers',
    'reset_user_throttles',
    'get_throttle_info'
]
