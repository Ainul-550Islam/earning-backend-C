"""
Security Caching Module
Advanced caching system for security operations
"""

import logging
import hashlib
import pickle
import json
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.db import models

from .models import SecurityLog, SecurityIncident, ThreatIntelligence
from .utils import SecurityUtils
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.caching')


class CacheKey:
    """Cache key patterns"""
    USER_SECURITY_DATA = "user_security_data_{user_id}"
    USER_RISK_SCORE = "user_risk_score_{user_id}"
    USER_DEVICES = "user_devices_{user_id}"
    USER_SANCTIONS = "user_sanctions_{user_id}"
    INCIDENT_DATA = "incident_data_{incident_id}"
    THREAT_DATA = "threat_data_{threat_id}"
    SECURITY_STATS = "security_stats_{period}_{hash}"
    SYSTEM_HEALTH = "system_health"
    FEATURE_FLAGS = "feature_flags_{user_id}"
    RATE_LIMIT = "rate_limit_{key}_{window}"
    SESSION_DATA = "session_data_{session_id}"
    IP_REPUTATION = "ip_reputation_{ip_address}"
    THREAT_INTEL = "threat_intel_{indicator}"
    ANALYTICS_DATA = "analytics_{type}_{period}_{hash}"


class CacheTTL:
    """Cache TTL values (in seconds)"""
    SHORT = 60  # 1 minute
    MEDIUM = 300  # 5 minutes
    LONG = 1800  # 30 minutes
    VERY_LONG = 3600  # 1 hour
    DAILY = 86400  # 24 hours
    WEEKLY = 604800  # 7 days


class SecurityCache:
    """Advanced security caching system"""
    
    def __init__(self, cache_backend=None):
        self.cache = cache_backend or cache
        self.default_ttl = CacheTTL.MEDIUM
        self.key_prefix = "security_"
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def _make_key(self, key: str) -> str:
        """Create cache key with prefix"""
        return f"{self.key_prefix}{key}"
    
    def _hash_data(self, data: Any) -> str:
        """Hash data for cache key"""
        if isinstance(data, (str, int, float, bool)):
            return str(data)
        
        try:
            # Try JSON serialization first
            json_str = json.dumps(data, sort_keys=True)
            return hashlib.md5(json_str.encode()).hexdigest()
        except (TypeError, ValueError):
            # Fall back to pickle
            try:
                pickle_str = pickle.dumps(data)
                return hashlib.md5(pickle_str).hexdigest()
            except Exception:
                # Last resort: string representation
                return hashlib.md5(str(data).encode()).hexdigest()
    
    def get(self, key: str, default=None):
        """Get value from cache"""
        cache_key = self._make_key(key)
        
        try:
            value = self.cache.get(cache_key, default)
            
            if value is not None:
                self.stats['hits'] += 1
            else:
                self.stats['misses'] += 1
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats['misses'] += 1
            return default
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache"""
        cache_key = self._make_key(key)
        ttl = ttl or self.default_ttl
        
        try:
            self.cache.set(cache_key, value, ttl)
            self.stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str):
        """Delete value from cache"""
        cache_key = self._make_key(key)
        
        try:
            self.cache.delete(cache_key)
            self.stats['deletes'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        cache_keys = [self._make_key(key) for key in keys]
        
        try:
            cached_values = self.cache.get_many(cache_keys)
            
            # Map back to original keys
            result = {}
            for i, key in enumerate(keys):
                cache_key = cache_keys[i]
                if cache_key in cached_values:
                    result[key] = cached_values[cache_key]
                    self.stats['hits'] += 1
                else:
                    self.stats['misses'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            self.stats['misses'] += len(keys)
            return {}
    
    def set_many(self, data: Dict[str, Any], ttl: int = None):
        """Set multiple values in cache"""
        ttl = ttl or self.default_ttl
        
        try:
            cache_data = {}
            for key, value in data.items():
                cache_data[self._make_key(key)] = value
            
            self.cache.set_many(cache_data, ttl)
            self.stats['sets'] += len(data)
            return True
            
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False
    
    def delete_many(self, keys: List[str]):
        """Delete multiple values from cache"""
        cache_keys = [self._make_key(key) for key in keys]
        
        try:
            self.cache.delete_many(cache_keys)
            self.stats['deletes'] += len(keys)
            return True
            
        except Exception as e:
            logger.error(f"Cache delete_many error: {e}")
            return False
    
    def clear(self):
        """Clear all cache entries with prefix"""
        try:
            # This is backend-specific
            # For Redis, we could use pattern matching
            # For Memcached, we need to track keys separately
            logger.info("Cache clear requested - implementation depends on backend")
            return True
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate
        }
    
    def reset_stats(self):
        """Reset cache statistics"""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }


class UserSecurityCache:
    """Cache for user-specific security data"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
    
    def get_user_security_data(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get user security data"""
        key = CacheKey.USER_SECURITY_DATA.format(user_id=user_id)
        return self.cache.get(key)
    
    def set_user_security_data(self, user_id: Union[int, str], data: Dict[str, Any], ttl: int = CacheTTL.MEDIUM):
        """Set user security data"""
        key = CacheKey.USER_SECURITY_DATA.format(user_id=user_id)
        return self.cache.set(key, data, ttl)
    
    def get_user_risk_score(self, user_id: Union[int, str]) -> Optional[float]:
        """Get user risk score"""
        key = CacheKey.USER_RISK_SCORE.format(user_id=user_id)
        return self.cache.get(key)
    
    def set_user_risk_score(self, user_id: Union[int, str], score: float, ttl: int = CacheTTL.MEDIUM):
        """Set user risk score"""
        key = CacheKey.USER_RISK_SCORE.format(user_id=user_id)
        return self.cache.set(key, score, ttl)
    
    def get_user_devices(self, user_id: Union[int, str]) -> Optional[List[Dict[str, Any]]]:
        """Get user devices"""
        key = CacheKey.USER_DEVICES.format(user_id=user_id)
        return self.cache.get(key)
    
    def set_user_devices(self, user_id: Union[int, str], devices: List[Dict[str, Any]], ttl: int = CacheTTL.LONG):
        """Set user devices"""
        key = CacheKey.USER_DEVICES.format(user_id=user_id)
        return self.cache.set(key, devices, ttl)
    
    def get_user_sanctions(self, user_id: Union[int, str]) -> Optional[List[Dict[str, Any]]]:
        """Get user sanctions"""
        key = CacheKey.USER_SANCTIONS.format(user_id=user_id)
        return self.cache.get(key)
    
    def set_user_sanctions(self, user_id: Union[int, str], sanctions: List[Dict[str, Any]], ttl: int = CacheTTL.MEDIUM):
        """Set user sanctions"""
        key = CacheKey.USER_SANCTIONS.format(user_id=user_id)
        return self.cache.set(key, sanctions, ttl)
    
    def invalidate_user_data(self, user_id: Union[int, str]):
        """Invalidate all user-related cache entries"""
        keys = [
            CacheKey.USER_SECURITY_DATA.format(user_id=user_id),
            CacheKey.USER_RISK_SCORE.format(user_id=user_id),
            CacheKey.USER_DEVICES.format(user_id=user_id),
            CacheKey.USER_SANCTIONS.format(user_id=user_id),
            CacheKey.FEATURE_FLAGS.format(user_id=user_id)
        ]
        
        return self.cache.delete_many(keys)


class SecurityStatsCache:
    """Cache for security statistics"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
    
    def get_security_stats(self, period: str, filters: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Get security statistics"""
        filters = filters or {}
        filter_hash = self.cache._hash_data(filters)
        key = CacheKey.SECURITY_STATS.format(period=period, hash=filter_hash)
        return self.cache.get(key)
    
    def set_security_stats(self, period: str, stats: Dict[str, Any], filters: Dict[str, Any] = None, ttl: int = CacheTTL.MEDIUM):
        """Set security statistics"""
        filters = filters or {}
        filter_hash = self.cache._hash_data(filters)
        key = CacheKey.SECURITY_STATS.format(period=period, hash=filter_hash)
        return self.cache.set(key, stats, ttl)
    
    def get_system_health(self) -> Optional[Dict[str, Any]]:
        """Get system health data"""
        return self.cache.get(CacheKey.SYSTEM_HEALTH)
    
    def set_system_health(self, health_data: Dict[str, Any], ttl: int = CacheTTL.SHORT):
        """Set system health data"""
        return self.cache.set(CacheKey.SYSTEM_HEALTH, health_data, ttl)
    
    def get_analytics_data(self, analytics_type: str, period: str, filters: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Get analytics data"""
        filters = filters or {}
        filter_hash = self.cache._hash_data(filters)
        key = CacheKey.ANALYTICS_DATA.format(type=analytics_type, period=period, hash=filter_hash)
        return self.cache.get(key)
    
    def set_analytics_data(self, analytics_type: str, period: str, data: Dict[str, Any], filters: Dict[str, Any] = None, ttl: int = CacheTTL.LONG):
        """Set analytics data"""
        filters = filters or {}
        filter_hash = self.cache._hash_data(filters)
        key = CacheKey.ANALYTICS_DATA.format(type=analytics_type, period=period, hash=filter_hash)
        return self.cache.set(key, data, ttl)


class ThreatIntelligenceCache:
    """Cache for threat intelligence data"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
    
    def get_threat_data(self, indicator: str) -> Optional[Dict[str, Any]]:
        """Get threat data"""
        key = CacheKey.THREAT_INTEL.format(indicator=indicator)
        return self.cache.get(key)
    
    def set_threat_data(self, indicator: str, threat_data: Dict[str, Any], ttl: int = CacheTTL.LONG):
        """Set threat data"""
        key = CacheKey.THREAT_INTEL.format(indicator=indicator)
        return self.cache.set(key, threat_data, ttl)
    
    def get_ip_reputation(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get IP reputation data"""
        key = CacheKey.IP_REPUTATION.format(ip_address=ip_address)
        return self.cache.get(key)
    
    def set_ip_reputation(self, ip_address: str, reputation_data: Dict[str, Any], ttl: int = CacheTTL.VERY_LONG):
        """Set IP reputation data"""
        key = CacheKey.IP_REPUTATION.format(ip_address=ip_address)
        return self.cache.set(key, reputation_data, ttl)
    
    def bulk_set_threat_data(self, threats: List[Dict[str, Any]], ttl: int = CacheTTL.LONG):
        """Bulk set threat data"""
        data = {}
        for threat in threats:
            indicator = threat.get('indicator')
            if indicator:
                key = CacheKey.THREAT_INTEL.format(indicator=indicator)
                data[key] = threat
        
        return self.cache.set_many(data, ttl)


class RateLimitCache:
    """Cache for rate limiting"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
    
    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check rate limit"""
        cache_key = CacheKey.RATE_LIMIT.format(key=key, window=window)
        
        current_count = self.cache.get(cache_key, 0)
        
        if current_count >= limit:
            return False
        
        # Increment counter
        self.cache.set(cache_key, current_count + 1, window)
        return True
    
    def get_rate_limit_status(self, key: str, window: int) -> Dict[str, Any]:
        """Get rate limit status"""
        cache_key = CacheKey.RATE_LIMIT.format(key=key, window=window)
        current_count = self.cache.get(cache_key, 0)
        
        return {
            'current': current_count,
            'remaining': max(0, window - current_count),
            'reset_time': timezone.now() + timedelta(seconds=window)
        }
    
    def reset_rate_limit(self, key: str, window: int):
        """Reset rate limit"""
        cache_key = CacheKey.RATE_LIMIT.format(key=key, window=window)
        return self.cache.delete(cache_key)


class SessionCache:
    """Cache for session data"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
    
    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        key = CacheKey.SESSION_DATA.format(session_id=session_id)
        return self.cache.get(key)
    
    def set_session_data(self, session_id: str, data: Dict[str, Any], ttl: int = CacheTTL.LONG):
        """Set session data"""
        key = CacheKey.SESSION_DATA.format(session_id=session_id)
        return self.cache.set(key, data, ttl)
    
    def update_session_data(self, session_id: str, updates: Dict[str, Any], ttl: int = CacheTTL.LONG):
        """Update session data"""
        current_data = self.get_session_data(session_id) or {}
        current_data.update(updates)
        return self.set_session_data(session_id, current_data, ttl)
    
    def delete_session_data(self, session_id: str):
        """Delete session data"""
        key = CacheKey.SESSION_DATA.format(session_id=session_id)
        return self.cache.delete(key)


class CacheWarmer:
    """Cache warming utility"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
        self.user_cache = UserSecurityCache(cache)
        self.stats_cache = SecurityStatsCache(cache)
        self.threat_cache = ThreatIntelligenceCache(cache)
    
    def warm_user_cache(self, user_ids: List[Union[int, str]]):
        """Warm user cache"""
        from .models import DeviceInfo, UserBan
        from .selectors import SecurityLogSelector
        
        log_selector = SecurityLogSelector()
        
        for user_id in user_ids:
            try:
                # Get user security data
                recent_logs = log_selector.filter_by_user(user_id).filter_recent(days=7)
                security_data = {
                    'total_events': recent_logs.count(),
                    'failed_attempts': recent_logs.filter_failed_attempts().count(),
                    'high_risk_events': recent_logs.filter_high_risk().count(),
                    'last_activity': recent_logs.order_by('-created_at').first().created_at.isoformat() if recent_logs.exists() else None
                }
                
                self.user_cache.set_user_security_data(user_id, security_data)
                
                # Get user devices
                devices = DeviceInfo.objects.filter(user_id=user_id)
                device_data = []
                for device in devices:
                    device_data.append({
                        'id': str(device.id),
                        'device_type': device.device_type,
                        'is_trusted': device.is_trusted,
                        'risk_score': device.risk_score,
                        'last_activity': device.last_activity.isoformat() if device.last_activity else None
                    })
                
                self.user_cache.set_user_devices(user_id, device_data)
                
                # Get user sanctions
                from .models import Sanction
                sanctions = Sanction.objects.filter(user_id=user_id, status='active')
                sanction_data = []
                for sanction in sanctions:
                    sanction_data.append({
                        'id': str(sanction.id),
                        'sanction_type': sanction.sanction_type,
                        'severity': sanction.severity,
                        'reason': sanction.reason,
                        'created_at': sanction.created_at.isoformat()
                    })
                
                self.user_cache.set_user_sanctions(user_id, sanction_data)
                
                logger.info(f"Warmed cache for user {user_id}")
                
            except Exception as e:
                logger.error(f"Error warming cache for user {user_id}: {e}")
    
    def warm_stats_cache(self):
        """Warm statistics cache"""
        try:
            # Pre-compute common statistics
            periods = ['last_hour', 'last_24h', 'last_7d', 'last_30d']
            
            for period in periods:
                # This would call the analytics service to get pre-computed stats
                # For now, just store empty data
                stats_data = {
                    'period': period,
                    'total_events': 0,
                    'total_incidents': 0,
                    'total_threats': 0,
                    'computed_at': timezone.now().isoformat()
                }
                
                self.stats_cache.set_security_stats(period, stats_data)
            
            logger.info("Warmed statistics cache")
            
        except Exception as e:
            logger.error(f"Error warming stats cache: {e}")
    
    def warm_threat_cache(self):
        """Warm threat intelligence cache"""
        try:
            from .models import ThreatIntelligence
            
            # Cache active threats
            threats = ThreatIntelligence.objects.filter(is_active=True)[:1000]
            
            threat_data = []
            for threat in threats:
                threat_info = {
                    'id': str(threat.id),
                    'threat_type': threat.threat_type,
                    'indicator': threat.indicator,
                    'indicator_type': threat.indicator_type,
                    'severity': threat.severity,
                    'confidence': threat.confidence,
                    'source': threat.source
                }
                
                self.threat_cache.set_threat_data(threat.indicator, threat_info)
                threat_data.append(threat_info)
            
            logger.info(f"Warmed threat cache with {len(threat_data)} threats")
            
        except Exception as e:
            logger.error(f"Error warming threat cache: {e}")


class CacheInvalidator:
    """Cache invalidation utility"""
    
    def __init__(self, cache: SecurityCache):
        self.cache = cache
        self.user_cache = UserSecurityCache(cache)
        self.stats_cache = SecurityStatsCache(cache)
        self.threat_cache = ThreatIntelligenceCache(cache)
    
    def invalidate_user(self, user_id: Union[int, str]):
        """Invalidate user cache"""
        self.user_cache.invalidate_user_data(user_id)
        logger.info(f"Invalidated cache for user {user_id}")
    
    def invalidate_stats(self, period: str = None):
        """Invalidate statistics cache"""
        if period:
            # Invalidate specific period
            pattern = f"security_stats_{period}_*"
        else:
            # Invalidate all stats
            pattern = "security_stats_*"
        
        # This would use pattern matching if supported by cache backend
        logger.info(f"Invalidated stats cache for pattern: {pattern}")
    
    def invalidate_threat(self, indicator: str = None):
        """Invalidate threat cache"""
        if indicator:
            key = CacheKey.THREAT_INTEL.format(indicator=indicator)
            self.cache.delete(key)
            logger.info(f"Invalidated threat cache for {indicator}")
        else:
            # Invalidate all threat cache
            pattern = "threat_intel_*"
            logger.info(f"Invalidated all threat cache")
    
    def invalidate_on_security_event(self, event_data: Dict[str, Any]):
        """Invalidate cache based on security event"""
        user_id = event_data.get('user_id')
        if user_id:
            self.invalidate_user(user_id)
        
        # Invalidate stats if high severity
        if event_data.get('severity') in ['high', 'critical']:
            self.invalidate_stats()
        
        # Invalidate threat cache if threat-related
        if event_data.get('security_type') in ['threat_detected', 'malware_detected']:
            self.invalidate_threat()


# Global cache instances
security_cache = SecurityCache()
user_security_cache = UserSecurityCache(security_cache)
security_stats_cache = SecurityStatsCache(security_cache)
threat_intelligence_cache = ThreatIntelligenceCache(security_cache)
rate_limit_cache = RateLimitCache(security_cache)
session_cache = SessionCache(security_cache)

cache_warmer = CacheWarmer(security_cache)
cache_invalidator = CacheInvalidator(security_cache)


# Cache decorator
def cache_result(key_pattern: str, ttl: int = CacheTTL.MEDIUM, cache_instance: SecurityCache = None):
    """Decorator to cache function results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_obj = cache_instance or security_cache
            
            # Generate cache key
            key_data = {
                'args': args,
                'kwargs': kwargs
            }
            key_hash = cache_obj._hash_data(key_data)
            cache_key = f"{key_pattern}_{key_hash}"
            
            # Try to get from cache
            result = cache_obj.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache_obj.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Export classes and utilities
__all__ = [
    'CacheKey',
    'CacheTTL',
    'SecurityCache',
    'security_cache',
    'UserSecurityCache',
    'user_security_cache',
    'SecurityStatsCache',
    'security_stats_cache',
    'ThreatIntelligenceCache',
    'threat_intelligence_cache',
    'RateLimitCache',
    'rate_limit_cache',
    'SessionCache',
    'session_cache',
    'CacheWarmer',
    'cache_warmer',
    'CacheInvalidator',
    'cache_invalidator',
    'cache_result'
]