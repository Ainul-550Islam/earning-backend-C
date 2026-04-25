"""
api/ad_networks/caching.py
Advanced caching system for ad networks module
SaaS-ready with tenant support
"""

import logging
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from functools import wraps

from .constants import CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)


# ==================== CACHE KEYS ====================

class CacheKeys:
    """Cache key patterns"""
    
    # Offer cache keys
    OFFER_DETAIL = "offer_detail:{offer_id}"
    OFFER_LIST = "offer_list:{filters_hash}"
    OFFER_FEATURED = "offer_featured:{limit}"
    OFFER_HOT = "offer_hot:{limit}"
    OFFER_NEW = "offer_new:{days}:{limit}"
    OFFER_BY_CATEGORY = "offer_category:{category_id}:{limit}"
    OFFER_SEARCH = "offer_search:{query_hash}:{limit}"
    
    # User cache keys
    USER_OFFERS = "user_offers:{user_id}:{status}:{limit}"
    USER_ENGAGEMENTS = "user_engagements:{user_id}:{status}:{limit}"
    USER_CONVERSIONS = "user_conversions:{user_id}:{status}:{limit}"
    USER_REWARDS = "user_rewards:{user_id}:{status}:{limit}"
    USER_WALLET = "user_wallet:{user_id}"
    USER_ANALYTICS = "user_analytics:{user_id}:{period}"
    USER_PREFERENCES = "user_preferences:{user_id}"
    
    # Analytics cache keys
    ANALYTICS_OFFER_PERFORMANCE = "analytics_offer_performance:{offer_id}:{period}"
    ANALYTICS_USER_STATS = "analytics_user_stats:{user_id}:{period}"
    ANALYTICS_REVENUE = "analytics_revenue:{period}"
    ANALYTICS_CONVERSIONS = "analytics_conversions:{period}"
    ANALYTICS_DASHBOARD = "analytics_dashboard:{period}"
    
    # System cache keys
    SYSTEM_HEALTH = "system_health"
    SYSTEM_METRICS = "system_metrics"
    DATABASE_STATS = "database_stats"
    CACHE_STATS = "cache_stats"
    
    # Configuration cache keys
    CONFIG_FEATURE_FLAGS = "config_feature_flags"
    CONFIG_NETWORKS = "config_networks"
    CONFIG_CATEGORIES = "config_categories"
    CONFIG_TAGS = "config_tags"


# ==================== CACHE STRATEGIES ====================

class CacheStrategy:
    """Cache strategies"""
    
    LAZY_LOADING = "lazy_loading"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    CACHE_ASIDE = "cache_aside"
    REFRESH_AHEAD = "refresh_ahead"


# ==================== BASE CACHE MANAGER ====================

class BaseCacheManager:
    """Base cache manager with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.default_timeout = getattr(settings, 'CACHE_DEFAULT_TIMEOUT', 300)
        self.key_prefix = f"ad_networks:{tenant_id}:"
    
    def _make_key(self, key: str) -> str:
        """Create full cache key with prefix"""
        return f"{self.key_prefix}{key}"
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for caching"""
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, default=str)
        return value
    
    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize value from cache"""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            full_key = self._make_key(key)
            value = cache.get(full_key, default)
            return self._deserialize_value(value)
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return default
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache"""
        try:
            full_key = self._make_key(key)
            serialized_value = self._serialize_value(value)
            timeout = timeout or self.default_timeout
            return cache.set(full_key, serialized_value, timeout)
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            full_key = self._make_key(key)
            return cache.delete(full_key)
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            full_key = self._make_key(key)
            return cache.has_key(full_key)
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {str(e)}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear cache keys matching pattern"""
        try:
            # This would typically use cache.delete_pattern if available
            # For now, return 0 (placeholder)
            logger.info(f"Clearing cache pattern: {pattern}")
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {str(e)}")
            return 0
    
    def get_ttl(self, key: str) -> int:
        """Get time-to-live for key"""
        try:
            full_key = self._make_key(key)
            # This would typically get TTL from cache backend
            # For now, return default timeout (placeholder)
            return self.default_timeout
        except Exception as e:
            logger.error(f"Error getting TTL for cache key {key}: {str(e)}")
            return 0


# ==================== ADVANCED CACHE MANAGER ====================

class AdvancedCacheManager(BaseCacheManager):
    """Advanced cache manager with additional features"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
        }
    
    def get_with_stats(self, key: str, default: Any = None) -> Any:
        """Get value with statistics tracking"""
        value = self.get(key, default)
        
        if value is not None and value != default:
            self.stats['hits'] += 1
        else:
            self.stats['misses'] += 1
        
        return value
    
    def set_with_stats(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value with statistics tracking"""
        result = self.set(key, value, timeout)
        if result:
            self.stats['sets'] += 1
        return result
    
    def delete_with_stats(self, key: str) -> bool:
        """Delete value with statistics tracking"""
        result = self.delete(key)
        if result:
            self.stats['deletes'] += 1
        return result
    
    def get_or_set(self, key: str, default_func: Callable, timeout: int = None) -> Any:
        """Get value or set using default function"""
        value = self.get_with_stats(key)
        
        if value is None:
            value = default_func()
            self.set_with_stats(key, value, timeout)
        
        return value
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values"""
        result = {}
        for key in keys:
            result[key] = self.get_with_stats(key)
        return result
    
    def set_many(self, mapping: Dict[str, Any], timeout: int = None) -> bool:
        """Set multiple values"""
        success = True
        for key, value in mapping.items():
            if not self.set_with_stats(key, value, timeout):
                success = False
        return success
    
    def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys"""
        deleted_count = 0
        for key in keys:
            if self.delete_with_stats(key):
                deleted_count += 1
        return deleted_count
    
    def increment(self, key: str, delta: int = 1) -> int:
        """Increment numeric value"""
        try:
            full_key = self._make_key(key)
            return cache.incr(full_key, delta)
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {str(e)}")
            return 0
    
    def decrement(self, key: str, delta: int = 1) -> int:
        """Decrement numeric value"""
        try:
            full_key = self._make_key(key)
            return cache.decr(full_key, delta)
        except Exception as e:
            logger.error(f"Error decrementing cache key {key}: {str(e)}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
        }


# ==================== CACHE DECORATORS ====================

def cached_result(key_pattern: str, timeout: int = None, cache_manager: BaseCacheManager = None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_pattern.format(*args, **kwargs)
            
            # Use provided cache manager or create default
            manager = cache_manager or AdvancedCacheManager()
            
            # Try to get from cache
            result = manager.get_with_stats(cache_key)
            
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            manager.set_with_stats(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def cached_user_result(key_pattern: str, timeout: int = None):
    """Decorator to cache user-specific results"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Extract user_id from kwargs or self
            user_id = kwargs.get('user_id') or getattr(self, 'user_id', None)
            
            if not user_id:
                return func(self, *args, **kwargs)
            
            # Generate cache key with user_id
            cache_key = f"user:{user_id}:{key_pattern.format(*args, **kwargs)}"
            
            # Get tenant_id
            tenant_id = getattr(self, 'tenant_id', 'default')
            manager = AdvancedCacheManager(tenant_id)
            
            # Try to get from cache
            result = manager.get_with_stats(cache_key)
            
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(self, *args, **kwargs)
            manager.set_with_stats(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def cached_query(timeout: int = None, key_func: Callable = None):
    """Decorator to cache database query results"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__] + [str(arg) for arg in args] + [f"{k}:{v}" for k, v in sorted(kwargs.items())]
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Get tenant_id
            tenant_id = getattr(self, 'tenant_id', 'default')
            manager = AdvancedCacheManager(tenant_id)
            
            # Try to get from cache
            result = manager.get_with_stats(cache_key)
            
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(self, *args, **kwargs)
            manager.set_with_stats(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


# ==================== OFFER CACHE MANAGER ====================

class OfferCacheManager(AdvancedCacheManager):
    """Cache manager for offers"""
    
    def get_offer_detail(self, offer_id: int) -> Optional[Dict[str, Any]]:
        """Get offer detail from cache"""
        key = CacheKeys.OFFER_DETAIL.format(offer_id=offer_id)
        return self.get_with_stats(key)
    
    def set_offer_detail(self, offer_id: int, offer_data: Dict[str, Any], timeout: int = None) -> bool:
        """Set offer detail in cache"""
        key = CacheKeys.OFFER_DETAIL.format(offer_id=offer_id)
        timeout = timeout or CACHE_TIMEOUTS.get('offer_detail', 300)
        return self.set_with_stats(key, offer_data, timeout)
    
    def invalidate_offer_detail(self, offer_id: int) -> bool:
        """Invalidate offer detail cache"""
        key = CacheKeys.OFFER_DETAIL.format(offer_id=offer_id)
        return self.delete_with_stats(key)
    
    def get_offer_list(self, filters: Dict[str, Any], limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Get offer list from cache"""
        filters_hash = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()
        key = CacheKeys.OFFER_LIST.format(filters_hash=filters_hash)
        return self.get_with_stats(key)
    
    def set_offer_list(self, filters: Dict[str, Any], offers: List[Dict[str, Any]], 
                      timeout: int = None) -> bool:
        """Set offer list in cache"""
        filters_hash = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()
        key = CacheKeys.OFFER_LIST.format(filters_hash=filters_hash)
        timeout = timeout or CACHE_TIMEOUTS.get('offer_list', 180)
        return self.set_with_stats(key, offers, timeout)
    
    def get_featured_offers(self, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Get featured offers from cache"""
        key = CacheKeys.OFFER_FEATURED.format(limit=limit)
        return self.get_with_stats(key)
    
    def set_featured_offers(self, offers: List[Dict[str, Any]], timeout: int = None) -> bool:
        """Set featured offers in cache"""
        key = CacheKeys.OFFER_FEATURED.format(limit=len(offers))
        timeout = timeout or CACHE_TIMEOUTS.get('featured_offers', 600)
        return self.set_with_stats(key, offers, timeout)
    
    def invalidate_offer_lists(self) -> int:
        """Invalidate all offer list caches"""
        patterns = [
            "offer_list:*",
            "offer_featured:*",
            "offer_hot:*",
            "offer_new:*",
            "offer_category:*",
            "offer_search:*",
        ]
        
        deleted_count = 0
        for pattern in patterns:
            deleted_count += self.clear_pattern(pattern)
        
        return deleted_count


# ==================== USER CACHE MANAGER ====================

class UserCacheManager(AdvancedCacheManager):
    """Cache manager for user data"""
    
    def get_user_wallet(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user wallet from cache"""
        key = CacheKeys.USER_WALLET.format(user_id=user_id)
        return self.get_with_stats(key)
    
    def set_user_wallet(self, user_id: int, wallet_data: Dict[str, Any], timeout: int = None) -> bool:
        """Set user wallet in cache"""
        key = CacheKeys.USER_WALLET.format(user_id=user_id)
        timeout = timeout or CACHE_TIMEOUTS.get('user_wallet', 300)
        return self.set_with_stats(key, wallet_data, timeout)
    
    def invalidate_user_wallet(self, user_id: int) -> bool:
        """Invalidate user wallet cache"""
        key = CacheKeys.USER_WALLET.format(user_id=user_id)
        return self.delete_with_stats(key)
    
    def get_user_analytics(self, user_id: int, period: str = '30d') -> Optional[Dict[str, Any]]:
        """Get user analytics from cache"""
        key = CacheKeys.USER_ANALYTICS.format(user_id=user_id, period=period)
        return self.get_with_stats(key)
    
    def set_user_analytics(self, user_id: int, analytics_data: Dict[str, Any], 
                          period: str = '30d', timeout: int = None) -> bool:
        """Set user analytics in cache"""
        key = CacheKeys.USER_ANALYTICS.format(user_id=user_id, period=period)
        timeout = timeout or CACHE_TIMEOUTS.get('user_analytics', 600)
        return self.set_with_stats(key, analytics_data, timeout)
    
    def invalidate_user_data(self, user_id: int) -> int:
        """Invalidate all user data caches"""
        patterns = [
            f"user_offers:{user_id}:*",
            f"user_engagements:{user_id}:*",
            f"user_conversions:{user_id}:*",
            f"user_rewards:{user_id}:*",
            f"user_wallet:{user_id}",
            f"user_analytics:{user_id}:*",
            f"user_preferences:{user_id}",
        ]
        
        deleted_count = 0
        for pattern in patterns:
            deleted_count += self.clear_pattern(pattern)
        
        return deleted_count


# ==================== ANALYTICS CACHE MANAGER ====================

class AnalyticsCacheManager(AdvancedCacheManager):
    """Cache manager for analytics data"""
    
    def get_offer_performance(self, offer_id: int, period: str = '30d') -> Optional[Dict[str, Any]]:
        """Get offer performance from cache"""
        key = CacheKeys.ANALYTICS_OFFER_PERFORMANCE.format(offer_id=offer_id, period=period)
        return self.get_with_stats(key)
    
    def set_offer_performance(self, offer_id: int, performance_data: Dict[str, Any], 
                             period: str = '30d', timeout: int = None) -> bool:
        """Set offer performance in cache"""
        key = CacheKeys.ANALYTICS_OFFER_PERFORMANCE.format(offer_id=offer_id, period=period)
        timeout = timeout or CACHE_TIMEOUTS.get('analytics_performance', 900)
        return self.set_with_stats(key, performance_data, timeout)
    
    def get_revenue_analytics(self, period: str = '30d') -> Optional[Dict[str, Any]]:
        """Get revenue analytics from cache"""
        key = CacheKeys.ANALYTICS_REVENUE.format(period=period)
        return self.get_with_stats(key)
    
    def set_revenue_analytics(self, revenue_data: Dict[str, Any], 
                             period: str = '30d', timeout: int = None) -> bool:
        """Set revenue analytics in cache"""
        key = CacheKeys.ANALYTICS_REVENUE.format(period=period)
        timeout = timeout or CACHE_TIMEOUTS.get('analytics_revenue', 600)
        return self.set_with_stats(key, revenue_data, timeout)
    
    def get_dashboard_analytics(self, period: str = '30d') -> Optional[Dict[str, Any]]:
        """Get dashboard analytics from cache"""
        key = CacheKeys.ANALYTICS_DASHBOARD.format(period=period)
        return self.get_with_stats(key)
    
    def set_dashboard_analytics(self, dashboard_data: Dict[str, Any], 
                               period: str = '30d', timeout: int = None) -> bool:
        """Set dashboard analytics in cache"""
        key = CacheKeys.ANALYTICS_DASHBOARD.format(period=period)
        timeout = timeout or CACHE_TIMEOUTS.get('analytics_dashboard', 300)
        return self.set_with_stats(key, dashboard_data, timeout)
    
    def invalidate_analytics(self, period: str = None) -> int:
        """Invalidate analytics caches"""
        if period:
            patterns = [
                f"analytics_*:{period}",
            ]
        else:
            patterns = [
                "analytics_*",
            ]
        
        deleted_count = 0
        for pattern in patterns:
            deleted_count += self.clear_pattern(pattern)
        
        return deleted_count


# ==================== CACHE WARMER ====================

class CacheWarmer:
    """Cache warming utility"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.offer_cache = OfferCacheManager(tenant_id)
        self.user_cache = UserCacheManager(tenant_id)
        self.analytics_cache = AnalyticsCacheManager(tenant_id)
    
    def warm_offer_cache(self, limit: int = 100) -> Dict[str, Any]:
        """Warm offer cache with popular offers"""
        try:
            from .models import Offer, OfferCategory
            
            # Warm featured offers
            featured_offers = Offer.objects.filter(
                tenant_id=self.tenant_id,
                is_featured=True,
                status='active'
            )[:10]
            
            featured_data = []
            for offer in featured_offers:
                featured_data.append({
                    'id': offer.id,
                    'title': offer.title,
                    'reward_amount': float(offer.reward_amount),
                    'reward_currency': offer.reward_currency,
                })
            
            self.offer_cache.set_featured_offers(featured_data)
            
            # Warm offers by category
            categories = OfferCategory.objects.all()[:10]
            for category in categories:
                category_offers = Offer.objects.filter(
                    tenant_id=self.tenant_id,
                    category=category,
                    status='active'
                )[:20]
                
                category_data = []
                for offer in category_offers:
                    category_data.append({
                        'id': offer.id,
                        'title': offer.title,
                        'reward_amount': float(offer.reward_amount),
                    })
                
                filters = {'category_id': category.id}
                self.offer_cache.set_offer_list(filters, category_data)
            
            return {
                'featured_offers': len(featured_data),
                'categories_processed': len(categories),
            }
            
        except Exception as e:
            logger.error(f"Error warming offer cache: {str(e)}")
            return {'error': str(e)}
    
    def warm_user_cache(self, user_ids: List[int]) -> Dict[str, Any]:
        """Warm user cache for specific users"""
        try:
            from .models import UserWallet
            
            wallets_warmed = 0
            
            for user_id in user_ids:
                try:
                    wallet = UserWallet.objects.get(user_id=user_id, tenant_id=self.tenant_id)
                    wallet_data = {
                        'current_balance': float(wallet.current_balance),
                        'pending_balance': float(wallet.pending_balance),
                        'total_earned': float(wallet.total_earned),
                        'currency': wallet.currency,
                    }
                    
                    self.user_cache.set_user_wallet(user_id, wallet_data)
                    wallets_warmed += 1
                    
                except UserWallet.DoesNotExist:
                    continue
            
            return {
                'users_processed': len(user_ids),
                'wallets_warmed': wallets_warmed,
            }
            
        except Exception as e:
            logger.error(f"Error warming user cache: {str(e)}")
            return {'error': str(e)}
    
    def warm_analytics_cache(self, periods: List[str] = ['7d', '30d']) -> Dict[str, Any]:
        """Warm analytics cache"""
        try:
            warmed_periods = []
            
            for period in periods:
                # This would typically calculate real analytics
                # For now, set placeholder data
                analytics_data = {
                    'period': period,
                    'total_revenue': 0,
                    'total_conversions': 0,
                    'cached_at': timezone.now().isoformat(),
                }
                
                self.analytics_cache.set_revenue_analytics(analytics_data, period)
                warmed_periods.append(period)
            
            return {
                'periods_warmed': warmed_periods,
            }
            
        except Exception as e:
            logger.error(f"Error warming analytics cache: {str(e)}")
            return {'error': str(e)}


# ==================== CACHE INVALIDATION SERVICE ====================

class CacheInvalidationService:
    """Service for cache invalidation"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.offer_cache = OfferCacheManager(tenant_id)
        self.user_cache = UserCacheManager(tenant_id)
        self.analytics_cache = AnalyticsCacheManager(tenant_id)
    
    def invalidate_offer_cache(self, offer_id: int = None) -> Dict[str, Any]:
        """Invalidate offer-related caches"""
        invalidated = 0
        
        if offer_id:
            # Invalidate specific offer
            if self.offer_cache.invalidate_offer_detail(offer_id):
                invalidated += 1
        else:
            # Invalidate all offer caches
            invalidated += self.offer_cache.invalidate_offer_lists()
        
        return {
            'type': 'offer',
            'offer_id': offer_id,
            'invalidated_count': invalidated,
        }
    
    def invalidate_user_cache(self, user_id: int = None) -> Dict[str, Any]:
        """Invalidate user-related caches"""
        invalidated = 0
        
        if user_id:
            # Invalidate specific user
            if self.user_cache.invalidate_user_wallet(user_id):
                invalidated += 1
            invalidated += self.user_cache.invalidate_user_data(user_id)
        else:
            # Invalidate all user caches (placeholder)
            invalidated = 0
        
        return {
            'type': 'user',
            'user_id': user_id,
            'invalidated_count': invalidated,
        }
    
    def invalidate_analytics_cache(self, period: str = None) -> Dict[str, Any]:
        """Invalidate analytics caches"""
        invalidated = self.analytics_cache.invalidate_analytics(period)
        
        return {
            'type': 'analytics',
            'period': period,
            'invalidated_count': invalidated,
        }
    
    def invalidate_all_caches(self) -> Dict[str, Any]:
        """Invalidate all caches"""
        offer_result = self.invalidate_offer_cache()
        user_result = self.invalidate_user_cache()
        analytics_result = self.invalidate_analytics_cache()
        
        return {
            'offer': offer_result,
            'user': user_result,
            'analytics': analytics_result,
            'total_invalidated': (
                offer_result['invalidated_count'] +
                user_result['invalidated_count'] +
                analytics_result['invalidated_count']
            ),
        }


# ==================== EXPORTS ====================

__all__ = [
    # Keys and strategies
    'CacheKeys',
    'CacheStrategy',
    
    # Managers
    'BaseCacheManager',
    'AdvancedCacheManager',
    'OfferCacheManager',
    'UserCacheManager',
    'AnalyticsCacheManager',
    
    # Decorators
    'cached_result',
    'cached_user_result',
    'cached_query',
    
    # Services
    'CacheWarmer',
    'CacheInvalidationService',
]
