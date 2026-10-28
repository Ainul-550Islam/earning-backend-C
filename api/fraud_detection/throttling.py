# =============================================================================
# fraud_detection/throttling.py
# =============================================================================
"""
Rate Limiting and Throttling Layer for Fraud Detection System.

Provides custom rate-limiting logic for suspicious IPs, users,
and fraud-related endpoints with adaptive throttling based on risk levels.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from collections import defaultdict, deque

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.fraud_detection.repositories import fraud_suspicious_ip_repository
from api.fraud_detection.selectors import fraud_suspicious_ip_selector
from api.fraud_detection.encryption import encrypt_ip_address
from api.fraud_detection.exceptions import ThrottlingError
from api.fraud_detection.constants import CACHE_KEYS, CACHE_TTL


logger = logging.getLogger(__name__)

User = get_user_model()


class RateLimiter:
    """
    Base rate limiter with configurable windows and limits.
    
    Provides sliding window rate limiting with memory-efficient
    tracking and automatic cleanup of expired entries.
    """
    
    def __init__(self, window_seconds: int = 60, max_requests: int = 100):
        """
        Initialize rate limiter.
        
        Args:
            window_seconds: Time window in seconds
            max_requests: Maximum requests per window
        """
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests = defaultdict(deque)  # {key: deque of timestamps}
    
    def is_allowed(self, key: str, request_time: Optional[datetime] = None) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            key: Rate limiting key (IP, user ID, etc.)
            request_time: Request timestamp (defaults to now)
            
        Returns:
            True if request is allowed
        """
        if request_time is None:
            request_time = timezone.now()
        
        request_timestamp = request_time.timestamp()
        request_deque = self.requests[key]
        
        # Remove expired entries
        cutoff_time = request_timestamp - self.window_seconds
        while request_deque and request_deque[0] <= cutoff_time:
            request_deque.popleft()
        
        # Check if under limit
        if len(request_deque) < self.max_requests:
            request_deque.append(request_timestamp)
            return True
        
        return False
    
    def get_remaining_requests(self, key: str, request_time: Optional[datetime] = None) -> int:
        """
        Get remaining requests for key.
        
        Args:
            key: Rate limiting key
            request_time: Request timestamp
            
        Returns:
            Number of remaining requests
        """
        if request_time is None:
            request_time = timezone.now()
        
        request_timestamp = request_time.timestamp()
        request_deque = self.requests[key]
        
        # Remove expired entries
        cutoff_time = request_timestamp - self.window_seconds
        while request_deque and request_deque[0] <= cutoff_time:
            request_deque.popleft()
        
        return max(0, self.max_requests - len(request_deque))
    
    def reset(self, key: str):
        """Reset rate limit for key."""
        if key in self.requests:
            del self.requests[key]
    
    def get_stats(self, key: str) -> Dict[str, Any]:
        """Get rate limiting statistics for key."""
        request_deque = self.requests.get(key, deque())
        
        if not request_deque:
            return {
                'current_requests': 0,
                'remaining_requests': self.max_requests,
                'window_start': None,
                'window_end': None
            }
        
        current_time = timezone.now().timestamp()
        cutoff_time = current_time - self.window_seconds
        
        # Remove expired entries
        while request_deque and request_deque[0] <= cutoff_time:
            request_deque.popleft()
        
        if request_deque:
            window_start = datetime.fromtimestamp(request_deque[0])
            window_end = datetime.fromtimestamp(request_deque[-1])
        else:
            window_start = None
            window_end = None
        
        return {
            'current_requests': len(request_deque),
            'remaining_requests': max(0, self.max_requests - len(request_deque)),
            'window_start': window_start.isoformat() if window_start else None,
            'window_end': window_end.isoformat() if window_end else None
        }


class SuspiciousIPRateLimiter:
    """
    Rate limiter for suspicious IP addresses.
    
    Implements adaptive throttling based on IP risk scores
    and suspicious activity patterns.
    """
    
    def __init__(self):
        """Initialize suspicious IP rate limiter."""
        self.base_limiters = self._initialize_base_limiters()
        self.suspicious_limits = self._load_suspicious_limits()
        self.ip_cache_ttl = getattr(settings, 'SUSPICIOUS_IP_CACHE_TTL', 3600)
    
    def _initialize_base_limiters(self) -> Dict[str, RateLimiter]:
        """Initialize base rate limiters for different risk levels."""
        return {
            'normal': RateLimiter(window_seconds=60, max_requests=1000),
            'low_risk': RateLimiter(window_seconds=60, max_requests=500),
            'medium_risk': RateLimiter(window_seconds=60, max_requests=200),
            'high_risk': RateLimiter(window_seconds=60, max_requests=50),
            'critical_risk': RateLimiter(window_seconds=60, max_requests=10),
        }
    
    def _load_suspicious_limits(self) -> Dict[str, Dict[str, int]]:
        """Load suspicious IP rate limiting configuration."""
        default_limits = {
            'suspicious_ip': {
                'window_seconds': 60,
                'max_requests': 100,
                'risk_multiplier': 0.5
            },
            'blacklisted_ip': {
                'window_seconds': 60,
                'max_requests': 10,
                'risk_multiplier': 0.1
            },
            'tor_exit_node': {
                'window_seconds': 60,
                'max_requests': 20,
                'risk_multiplier': 0.2
            },
            'datacenter_ip': {
                'window_seconds': 60,
                'max_requests': 200,
                'risk_multiplier': 0.8
            }
        }
        
        return getattr(settings, 'SUSPICIOUS_IP_RATE_LIMITS', default_limits)
    
    def is_allowed(self, ip_address: str, endpoint: str = 'default',
                  request_time: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if IP request is allowed.
        
        Args:
            ip_address: IP address to check
            endpoint: Endpoint identifier
            request_time: Request timestamp
            
        Returns:
            Tuple of (allowed, throttling_info)
        """
        if request_time is None:
            request_time = timezone.now()
        
        # Get IP risk assessment
        ip_risk_info = self._get_ip_risk_info(ip_address)
        
        # Determine appropriate limiter
        limiter = self._get_appropriate_limiter(ip_risk_info)
        
        # Create rate limiting key
        rate_limit_key = f"{ip_address}:{endpoint}"
        
        # Check rate limit
        allowed = limiter.is_allowed(rate_limit_key, request_time)
        
        # Get throttling information
        throttling_info = {
            'ip_address': ip_address,
            'risk_level': ip_risk_info['risk_level'],
            'risk_score': ip_risk_info['risk_score'],
            'rate_limit_type': ip_risk_info['limit_type'],
            'allowed': allowed,
            'remaining_requests': limiter.get_remaining_requests(rate_limit_key, request_time),
            'window_seconds': limiter.window_seconds,
            'max_requests': limiter.max_requests,
            'request_time': request_time.isoformat()
        }
        
        # Log suspicious activity
        if not allowed and ip_risk_info['risk_level'] in ['high', 'critical']:
            logger.warning(f"Rate limit exceeded for suspicious IP: {ip_address}, risk: {ip_risk_info['risk_level']}")
        
        return allowed, throttling_info
    
    def _get_ip_risk_info(self, ip_address: str) -> Dict[str, Any]:
        """Get IP risk information."""
        # Check cache first
        cache_key = f"{CACHE_KEYS['ip_reputation']}_{ip_address}"
        cached_info = cache.get(cache_key)
        
        if cached_info:
            return cached_info
        
        # Get IP from suspicious IP repository
        suspicious_ip = fraud_suspicious_ip_selector.get_suspicious_ip(ip_address)
        
        risk_info = {
            'risk_score': 0,
            'risk_level': 'normal',
            'limit_type': 'normal',
            'is_suspicious': False,
            'is_blacklisted': False
        }
        
        if suspicious_ip:
            risk_info['risk_score'] = suspicious_ip.risk_score
            risk_info['is_suspicious'] = True
            
            # Determine risk level
            if suspicious_ip.risk_score >= 80:
                risk_info['risk_level'] = 'critical'
                risk_info['limit_type'] = 'blacklisted_ip'
                risk_info['is_blacklisted'] = True
            elif suspicious_ip.risk_score >= 60:
                risk_info['risk_level'] = 'high'
                risk_info['limit_type'] = 'suspicious_ip'
            elif suspicious_ip.risk_score >= 40:
                risk_info['risk_level'] = 'medium'
                risk_info['limit_type'] = 'suspicious_ip'
            else:
                risk_info['risk_level'] = 'low'
                risk_info['limit_type'] = 'suspicious_ip'
        
        # Check for special IP types (simplified)
        if self._is_tor_exit_node(ip_address):
            risk_info['risk_level'] = 'high'
            risk_info['limit_type'] = 'tor_exit_node'
            risk_info['risk_score'] = max(risk_info['risk_score'], 70)
        
        if self._is_datacenter_ip(ip_address):
            if risk_info['risk_level'] == 'normal':
                risk_info['risk_level'] = 'low'
                risk_info['limit_type'] = 'datacenter_ip'
        
        # Cache the result
        cache.set(cache_key, risk_info, self.ip_cache_ttl)
        
        return risk_info
    
    def _get_appropriate_limiter(self, ip_risk_info: Dict[str, Any]) -> RateLimiter:
        """Get appropriate rate limiter based on IP risk."""
        limit_type = ip_risk_info['limit_type']
        
        if limit_type in self.suspicious_limits:
            limits = self.suspicious_limits[limit_type]
            return RateLimiter(
                window_seconds=limits['window_seconds'],
                max_requests=limits['max_requests']
            )
        
        # Use base limiter for risk level
        risk_level = ip_risk_info['risk_level']
        return self.base_limiters.get(risk_level, self.base_limiters['normal'])
    
    def _is_tor_exit_node(self, ip_address: str) -> bool:
        """Check if IP is Tor exit node (simplified)."""
        # In practice, this would check against Tor exit node lists
        tor_exit_nodes = getattr(settings, 'TOR_EXIT_NODES', [])
        return ip_address in tor_exit_nodes
    
    def _is_datacenter_ip(self, ip_address: str) -> bool:
        """Check if IP is from datacenter (simplified)."""
        # In practice, this would check against datacenter IP ranges
        datacenter_ranges = getattr(settings, 'DATACENTER_IP_RANGES', [])
        return any(ip_address.startswith(prefix) for prefix in datacenter_ranges)
    
    def update_ip_risk(self, ip_address: str, risk_score: int, reason: str):
        """Update IP risk score and adjust rate limits."""
        try:
            # Update in repository
            from api.fraud_detection.repositories import fraud_suspicious_ip_repository
            
            updated_ip = fraud_suspicious_ip_repository.update_ip_risk(ip_address, risk_score, reason)
            
            # Clear cache to force refresh
            cache_key = f"{CACHE_KEYS['ip_reputation']}_{ip_address}"
            cache.delete(cache_key)
            
            logger.info(f"Updated IP risk: {ip_address}, new score: {risk_score}")
            
        except Exception as e:
            logger.error("Failed to update IP risk for %s: %s", ip_address, e, exc_info=True)


class UserBasedRateLimiter:
    """
    Rate limiter for user-based throttling.
    
    Implements per-user rate limiting with adaptive limits
    based on user risk profiles and behavior.
    """
    
    def __init__(self):
        """Initialize user-based rate limiter."""
        self.base_limiters = self._initialize_user_limiters()
        self.user_cache_ttl = getattr(settings, 'USER_RATE_LIMIT_CACHE_TTL', 1800)
    
    def _initialize_user_limiters(self) -> Dict[str, RateLimiter]:
        """Initialize user rate limiters for different risk levels."""
        return {
            'normal': RateLimiter(window_seconds=60, max_requests=200),
            'low_risk': RateLimiter(window_seconds=60, max_requests=150),
            'medium_risk': RateLimiter(window_seconds=60, max_requests=100),
            'high_risk': RateLimiter(window_seconds=60, max_requests=50),
            'critical_risk': RateLimiter(window_seconds=60, max_requests=20),
        }
    
    def is_allowed(self, user_id: Union[int, str], endpoint: str = 'default',
                  request_time: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if user request is allowed.
        
        Args:
            user_id: User ID to check
            endpoint: Endpoint identifier
            request_time: Request timestamp
            
        Returns:
            Tuple of (allowed, throttling_info)
        """
        if request_time is None:
            request_time = timezone.now()
        
        # Get user risk assessment
        user_risk_info = self._get_user_risk_info(user_id)
        
        # Determine appropriate limiter
        limiter = self._get_user_limiter(user_risk_info)
        
        # Create rate limiting key
        rate_limit_key = f"user:{user_id}:{endpoint}"
        
        # Check rate limit
        allowed = limiter.is_allowed(rate_limit_key, request_time)
        
        # Get throttling information
        throttling_info = {
            'user_id': user_id,
            'risk_level': user_risk_info['risk_level'],
            'risk_score': user_risk_info['risk_score'],
            'allowed': allowed,
            'remaining_requests': limiter.get_remaining_requests(rate_limit_key, request_time),
            'window_seconds': limiter.window_seconds,
            'max_requests': limiter.max_requests,
            'request_time': request_time.isoformat()
        }
        
        # Log suspicious user activity
        if not allowed and user_risk_info['risk_level'] in ['high', 'critical']:
            logger.warning(f"Rate limit exceeded for suspicious user: {user_id}, risk: {user_risk_info['risk_level']}")
        
        return allowed, throttling_info
    
    def _get_user_risk_info(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """Get user risk information."""
        # Check cache first
        cache_key = f"{CACHE_KEYS['user_risk_score']}_{user_id}"
        cached_info = cache.get(cache_key)
        
        if cached_info:
            return cached_info
        
        # Get user risk profile
        from api.fraud_detection.selectors import fraud_risk_profile_selector
        
        risk_profile = fraud_risk_profile_selector.get_profile_by_user(user_id)
        
        risk_info = {
            'risk_score': 0,
            'risk_level': 'normal',
            'account_age_days': 0,
            'is_verified': False
        }
        
        if risk_profile:
            risk_info['risk_score'] = risk_profile.risk_score
            
            # Determine risk level
            if risk_profile.risk_score >= 80:
                risk_info['risk_level'] = 'critical'
            elif risk_profile.risk_score >= 60:
                risk_info['risk_level'] = 'high'
            elif risk_profile.risk_score >= 40:
                risk_info['risk_level'] = 'medium'
            elif risk_profile.risk_score >= 20:
                risk_info['risk_level'] = 'low'
            else:
                risk_info['risk_level'] = 'normal'
        
        # Get account information
        try:
            user = User.objects.get(pk=user_id)
            risk_info['account_age_days'] = (timezone.now() - user.date_joined).days
            risk_info['is_verified'] = getattr(user, 'is_verified', False)
        except User.DoesNotExist:
            pass
        
        # Cache the result
        cache.set(cache_key, risk_info, self.user_cache_ttl)
        
        return risk_info
    
    def _get_user_limiter(self, user_risk_info: Dict[str, Any]) -> RateLimiter:
        """Get appropriate rate limiter based on user risk."""
        risk_level = user_risk_info['risk_level']
        return self.base_limiters.get(risk_level, self.base_limiters['normal'])


class AdaptiveThrottlingManager:
    """
    Adaptive throttling manager that combines multiple rate limiting strategies.
    
    Provides intelligent throttling that adapts to real-time risk levels
    and system conditions.
    """
    
    def __init__(self):
        """Initialize adaptive throttling manager."""
        self.ip_limiter = SuspiciousIPRateLimiter()
        self.user_limiter = UserBasedRateLimiter()
        self.global_limiter = RateLimiter(window_seconds=60, max_requests=10000)
        self.endpoint_limiters = self._initialize_endpoint_limiters()
        self.adaptation_rules = self._load_adaptation_rules()
    
    def _initialize_endpoint_limiters(self) -> Dict[str, RateLimiter]:
        """Initialize endpoint-specific rate limiters."""
        endpoint_configs = getattr(settings, 'ENDPOINT_RATE_LIMITS', {
            'fraud_detection': {'window': 60, 'limit': 100},
            'login': {'window': 60, 'limit': 20},
            'registration': {'window': 300, 'limit': 5},
            'transaction': {'window': 60, 'limit': 50},
        })
        
        limiters = {}
        for endpoint, config in endpoint_configs.items():
            limiters[endpoint] = RateLimiter(
                window_seconds=config['window'],
                max_requests=config['limit']
            )
        
        return limiters
    
    def _load_adaptation_rules(self) -> Dict[str, Any]:
        """Load adaptive throttling rules."""
        default_rules = {
            'system_load_threshold': 0.8,
            'error_rate_threshold': 0.1,
            'adaptation_factor': 0.5,
            'recovery_factor': 1.2,
            'min_limit': 1,
            'max_limit': 10000
        }
        
        return getattr(settings, 'ADAPTIVE_THROTTLING_RULES', default_rules)
    
    def check_request_allowed(self, request_info: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed using all throttling strategies.
        
        Args:
            request_info: Request information including IP, user, endpoint, etc.
            
        Returns:
            Tuple of (allowed, throttling_info)
        """
        ip_address = request_info.get('ip_address')
        user_id = request_info.get('user_id')
        endpoint = request_info.get('endpoint', 'default')
        request_time = request_info.get('request_time')
        
        if request_time is None:
            request_time = timezone.now()
        
        throttling_results = {
            'overall_allowed': True,
            'ip_throttling': None,
            'user_throttling': None,
            'global_throttling': None,
            'endpoint_throttling': None,
            'adaptive_adjustments': [],
            'final_decision': 'allowed'
        }
        
        # Check IP-based throttling
        if ip_address:
            ip_allowed, ip_info = self.ip_limiter.is_allowed(ip_address, endpoint, request_time)
            throttling_results['ip_throttling'] = ip_info
            
            if not ip_allowed:
                throttling_results['overall_allowed'] = False
                throttling_results['final_decision'] = 'blocked_by_ip'
        
        # Check user-based throttling
        if user_id and throttling_results['overall_allowed']:
            user_allowed, user_info = self.user_limiter.is_allowed(user_id, endpoint, request_time)
            throttling_results['user_throttling'] = user_info
            
            if not user_allowed:
                throttling_results['overall_allowed'] = False
                throttling_results['final_decision'] = 'blocked_by_user'
        
        # Check global throttling
        if throttling_results['overall_allowed']:
            global_key = f"global:{endpoint}"
            global_allowed = self.global_limiter.is_allowed(global_key, request_time)
            
            throttling_results['global_throttling'] = {
                'allowed': global_allowed,
                'remaining_requests': self.global_limiter.get_remaining_requests(global_key, request_time),
                'window_seconds': self.global_limiter.window_seconds,
                'max_requests': self.global_limiter.max_requests
            }
            
            if not global_allowed:
                throttling_results['overall_allowed'] = False
                throttling_results['final_decision'] = 'blocked_by_global'
        
        # Check endpoint-specific throttling
        if throttling_results['overall_allowed'] and endpoint in self.endpoint_limiters:
            endpoint_limiter = self.endpoint_limiters[endpoint]
            endpoint_key = f"endpoint:{endpoint}"
            endpoint_allowed = endpoint_limiter.is_allowed(endpoint_key, request_time)
            
            throttling_results['endpoint_throttling'] = {
                'allowed': endpoint_allowed,
                'remaining_requests': endpoint_limiter.get_remaining_requests(endpoint_key, request_time),
                'window_seconds': endpoint_limiter.window_seconds,
                'max_requests': endpoint_limiter.max_requests
            }
            
            if not endpoint_allowed:
                throttling_results['overall_allowed'] = False
                throttling_results['final_decision'] = 'blocked_by_endpoint'
        
        # Apply adaptive adjustments
        if throttling_results['overall_allowed']:
            adjustments = self._apply_adaptive_adjustments(request_info, throttling_results)
            throttling_results['adaptive_adjustments'] = adjustments
            
            if adjustments.get('further_restriction', False):
                throttling_results['overall_allowed'] = False
                throttling_results['final_decision'] = 'blocked_by_adaptive'
        
        throttling_results['request_time'] = request_time.isoformat()
        throttling_results['endpoint'] = endpoint
        
        return throttling_results['overall_allowed'], throttling_results
    
    def _apply_adaptive_adjustments(self, request_info: Dict[str, Any],
                                  throttling_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply adaptive throttling adjustments based on system conditions."""
        adjustments = []
        
        # Check system load (simplified)
        system_load = self._get_system_load()
        if system_load > self.adaptation_rules['system_load_threshold']:
            adjustments.append({
                'type': 'system_load',
                'value': system_load,
                'action': 'reduce_limits',
                'factor': self.adaptation_rules['adaptation_factor']
            })
        
        # Check error rates (simplified)
        error_rate = self._get_error_rate()
        if error_rate > self.adaptation_rules['error_rate_threshold']:
            adjustments.append({
                'type': 'error_rate',
                'value': error_rate,
                'action': 'reduce_limits',
                'factor': self.adaptation_rules['adaptation_factor']
            })
        
        # Check for rapid requests from same IP
        if throttling_results['ip_throttling']:
            ip_info = throttling_results['ip_throttling']
            if ip_info['remaining_requests'] < (ip_info['max_requests'] * 0.1):
                adjustments.append({
                    'type': 'ip_exhaustion',
                    'value': ip_info['remaining_requests'],
                    'action': 'further_restrict',
                    'factor': 0.5
                })
        
        # Determine if further restriction is needed
        further_restriction = any(
            adj['action'] in ['reduce_limits', 'further_restrict'] 
            for adj in adjustments
        )
        
        if further_restriction:
            adjustments.append({'type': 'final_decision', 'further_restriction': True})
        
        return adjustments
    
    def _get_system_load(self) -> float:
        """Get current system load (simplified)."""
        # In practice, this would check actual system metrics
        return 0.3  # Placeholder
    
    def _get_error_rate(self) -> float:
        """Get current error rate (simplified)."""
        # In practice, this would check actual error metrics
        return 0.05  # Placeholder
    
    def update_throttling_limits(self, updates: Dict[str, Any]):
        """Update throttling limits dynamically."""
        if 'global_limit' in updates:
            new_limit = updates['global_limit']
            self.global_limiter.max_requests = max(
                self.adaptation_rules['min_limit'],
                min(new_limit, self.adaptation_rules['max_limit'])
            )
        
        if 'endpoint_limits' in updates:
            for endpoint, limit in updates['endpoint_limits'].items():
                if endpoint in self.endpoint_limiters:
                    self.endpoint_limiters[endpoint].max_requests = max(
                        self.adaptation_rules['min_limit'],
                        min(limit, self.adaptation_rules['max_limit'])
                    )
    
    def get_throttling_stats(self) -> Dict[str, Any]:
        """Get comprehensive throttling statistics."""
        stats = {
            'global_stats': {
                'current_requests': len(self.global_limiter.requests.get('global:default', [])),
                'max_requests': self.global_limiter.max_requests,
                'window_seconds': self.global_limiter.window_seconds
            },
            'endpoint_stats': {},
            'ip_limiters_count': len(self.ip_limiter.requests),
            'user_limiters_count': len(self.user_limiter.requests),
            'system_load': self._get_system_load(),
            'error_rate': self._get_error_rate()
        }
        
        # Endpoint statistics
        for endpoint, limiter in self.endpoint_limiters.items():
            key = f"endpoint:{endpoint}"
            current_requests = len(limiter.requests.get(key, []))
            stats['endpoint_stats'][endpoint] = {
                'current_requests': current_requests,
                'max_requests': limiter.max_requests,
                'window_seconds': limiter.window_seconds,
                'utilization': current_requests / limiter.max_requests if limiter.max_requests > 0 else 0
            }
        
        return stats


# Global instances for easy access
adaptive_throttling_manager = AdaptiveThrottlingManager()


def check_request_throttling(request_info: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Convenience function for request throttling check.
    
    Args:
        request_info: Request information
        
    Returns:
        Tuple of (allowed, throttling_info)
    """
    return adaptive_throttling_manager.check_request_allowed(request_info)


def update_ip_throttling_risk(ip_address: str, risk_score: int, reason: str):
    """
    Convenience function for updating IP throttling risk.
    
    Args:
        ip_address: IP address
        risk_score: New risk score
        reason: Update reason
    """
    adaptive_throttling_manager.ip_limiter.update_ip_risk(ip_address, risk_score, reason)


def get_throttling_statistics() -> Dict[str, Any]:
    """
    Convenience function for getting throttling statistics.
    
    Returns:
        Throttling statistics
    """
    return adaptive_throttling_manager.get_throttling_stats()
