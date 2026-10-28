# api/rate_limit/utils.py
"""
Utility functions for rate limit module.

Provides common utility functions and helpers.
"""
from typing import Callable

import logging
import hashlib
import time
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.http import HttpRequest
import ipaddress
import json
import re

logger = logging.getLogger(__name__)
User = get_user_model()


class RateLimitUtils:
    """Utility class for rate limit operations."""
    
    @staticmethod
    def generate_cache_key(identifier: str, limit_type: str, time_unit: str, time_value: int) -> str:
        """
        Generate cache key for rate limiting.
        
        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            limit_type: Type of rate limit
            time_unit: Time unit (second, minute, hour, etc.)
            time_value: Time value
            
        Returns:
            Cache key string
        """
        key_parts = [
            'rate_limit',
            limit_type,
            str(time_unit),
            str(time_value),
            str(identifier)
        ]
        
        return ':'.join(key_parts)
    
    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """
        Get client IP address from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        
        if x_forwarded_for:
            # Get the first IP from the list
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip
    
    @staticmethod
    def validate_ip_address(ip_address: str) -> bool:
        """
        Validate IP address format.
        
        Args:
            ip_address: IP address string
            
        Returns:
            True if valid IP address
        """
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_private_ip(ip_address: str) -> bool:
        """
        Check if IP address is private.
        
        Args:
            ip_address: IP address string
            
        Returns:
            True if private IP
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            return ip.is_private
        except ValueError:
            return False
    
    @staticmethod
    def get_user_from_request(request: HttpRequest) -> Optional[User]:
        """
        Get user from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            User object or None
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            return request.user
        return None
    
    @staticmethod
    def generate_request_id() -> str:
        """
        Generate unique request ID.
        
        Returns:
            Unique request ID
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """
        Hash sensitive data for logging.
        
        Args:
            data: Sensitive data string
            
        Returns:
            Hashed data
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """
        Mask sensitive data for display.
        
        Args:
            data: Sensitive data string
            mask_char: Character to use for masking
            visible_chars: Number of characters to keep visible
            
        Returns:
            Masked data
        """
        if len(data) <= visible_chars:
            return mask_char * len(data)
        
        return data[:visible_chars] + mask_char * (len(data) - visible_chars)
    
    @staticmethod
    def parse_user_agent(user_agent: str) -> Dict[str, str]:
        """
        Parse user agent string.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Parsed user agent components
        """
        parsed = {
            'browser': 'Unknown',
            'os': 'Unknown',
            'device': 'Unknown',
            'raw': user_agent
        }
        
        if not user_agent:
            return parsed
        
        # Simple parsing logic
        user_agent_lower = user_agent.lower()
        
        # Browser detection
        browsers = {
            'chrome': 'Chrome',
            'firefox': 'Firefox',
            'safari': 'Safari',
            'edge': 'Edge',
            'opera': 'Opera',
            'ie': 'Internet Explorer'
        }
        
        for browser_key, browser_name in browsers.items():
            if browser_key in user_agent_lower:
                parsed['browser'] = browser_name
                break
        
        # OS detection
        os_patterns = {
            'windows': 'Windows',
            'mac': 'macOS',
            'linux': 'Linux',
            'android': 'Android',
            'ios': 'iOS',
            'ubuntu': 'Ubuntu'
        }
        
        for os_key, os_name in os_patterns.items():
            if os_key in user_agent_lower:
                parsed['os'] = os_name
                break
        
        # Device detection
        device_patterns = {
            'mobile': 'Mobile',
            'tablet': 'Tablet',
            'android': 'Mobile',
            'iphone': 'Mobile',
            'ipad': 'Tablet'
        }
        
        for device_key, device_name in device_patterns.items():
            if device_key in user_agent_lower:
                parsed['device'] = device_name
                break
        
        return parsed
    
    @staticmethod
    def get_time_window_seconds(time_unit: str, time_value: int) -> int:
        """
        Convert time unit and value to seconds.
        
        Args:
            time_unit: Time unit (second, minute, hour, day, week, month)
            time_value: Time value
            
        Returns:
            Time in seconds
        """
        multipliers = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400,
            'week': 604800,
            'month': 2592000  # 30 days
        }
        
        multiplier = multipliers.get(time_unit, 60)  # Default to minute
        return time_value * multiplier
    
    @staticmethod
    def format_time_window(seconds: int) -> str:
        """
        Format seconds into human-readable time window.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time window
        """
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"
        else:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''}"
    
    @staticmethod
    def calculate_retry_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0, backoff_factor: float = 2.0) -> float:
        """
        Calculate exponential backoff retry delay.
        
        Args:
            attempt: Current attempt number
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Backoff multiplier
            
        Returns:
            Delay in seconds
        """
        delay = base_delay * (backoff_factor ** (attempt - 1))
        return min(delay, max_delay)
    
    @staticmethod
    def is_rate_limit_exempt(request: HttpRequest) -> bool:
        """
        Check if request is exempt from rate limiting.
        
        Args:
            request: HTTP request object
            
        Returns:
            True if exempt
        """
        # Check exempt paths
        exempt_paths = getattr(settings, 'RATE_LIMIT_EXEMPT_PATHS', [])
        path = request.path_info
        
        for exempt_path in exempt_paths:
            if re.match(exempt_path, path):
                return True
        
        # Check exempt IP addresses
        exempt_ips = getattr(settings, 'RATE_LIMIT_EXEMPT_IPS', [])
        client_ip = RateLimitUtils.get_client_ip(request)
        
        if client_ip in exempt_ips:
            return True
        
        # Check exempt user agents
        exempt_user_agents = getattr(settings, 'RATE_LIMIT_EXEMPT_USER_AGENTS', [])
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        for exempt_ua in exempt_user_agents:
            if re.search(exempt_ua, user_agent, re.IGNORECASE):
                return True
        
        # Check staff users
        user = RateLimitUtils.get_user_from_request(request)
        if user and user.is_staff:
            return True
        
        return False
    
    @staticmethod
    def get_rate_limit_multiplier(user: User = None, ip_address: str = None) -> float:
        """
        Get rate limit multiplier based on user or IP.
        
        Args:
            user: User object
            ip_address: IP address
            
        Returns:
            Multiplier value
        """
        multiplier = 1.0
        
        # User-based multipliers
        if user:
            if user.is_superuser:
                multiplier = 10.0
            elif user.is_staff:
                multiplier = 5.0
            elif hasattr(user, 'is_premium') and user.is_premium:
                multiplier = 3.0
            elif hasattr(user, 'subscription_tier'):
                tier_multipliers = {
                    'basic': 1.0,
                    'standard': 1.5,
                    'premium': 3.0,
                    'enterprise': 5.0
                }
                multiplier = tier_multipliers.get(user.subscription_tier, 1.0)
        
        # IP-based multipliers
        if ip_address:
            # Check if IP is in trusted network
            trusted_networks = getattr(settings, 'RATE_LIMIT_TRUSTED_NETWORKS', [])
            for network in trusted_networks:
                try:
                    if ipaddress.ip_address(ip_address) in ipaddress.ip_network(network):
                        multiplier = max(multiplier, 2.0)
                        break
                except ValueError:
                    continue
        
        return multiplier
    
    @staticmethod
    def sanitize_endpoint(endpoint: str) -> str:
        """
        Sanitize endpoint URL for consistent matching.
        
        Args:
            endpoint: Endpoint URL
            
        Returns:
            Sanitized endpoint
        """
        if not endpoint:
            return '/'
        
        # Remove query parameters
        if '?' in endpoint:
            endpoint = endpoint.split('?')[0]
        
        # Ensure leading slash
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        # Remove trailing slash for consistency (except root)
        if len(endpoint) > 1 and endpoint.endswith('/'):
            endpoint = endpoint.rstrip('/')
        
        return endpoint
    
    @staticmethod
    def extract_request_context(request: HttpRequest) -> Dict[str, Any]:
        """
        Extract relevant context from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            Request context dictionary
        """
        context = {
            'method': request.method,
            'path': request.path_info,
            'endpoint': RateLimitUtils.sanitize_endpoint(request.path_info),
            'ip_address': RateLimitUtils.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'referer': request.META.get('HTTP_REFERER', ''),
            'timestamp': timezone.now().isoformat(),
            'request_id': RateLimitUtils.generate_request_id()
        }
        
        # Add user information if available
        user = RateLimitUtils.get_user_from_request(request)
        if user:
            context.update({
                'user_id': user.id,
                'username': user.username,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser
            })
        
        # Add parsed user agent
        context['parsed_user_agent'] = RateLimitUtils.parse_user_agent(context['user_agent'])
        
        return context
    
    @staticmethod
    def calculate_suspicion_score(context: Dict[str, Any]) -> int:
        """
        Calculate suspicion score based on request context.
        
        Args:
            context: Request context
            
        Returns:
            Suspicion score (0-100)
        """
        score = 0
        
        # IP-based scoring
        ip_address = context.get('ip_address', '')
        if RateLimitUtils.validate_ip_address(ip_address):
            if not RateLimitUtils.is_private_ip(ip_address):
                score += 10  # Public IP gets some points
        
        # User agent scoring
        user_agent = context.get('user_agent', '')
        if not user_agent or len(user_agent) < 10:
            score += 20  # Suspicious user agent
        elif 'bot' in user_agent.lower() or 'crawler' in user_agent.lower():
            score += 30  # Bot or crawler
        
        # Request pattern scoring
        method = context.get('method', '')
        if method == 'POST':
            score += 5  # POST requests get slight increase
        
        # Path-based scoring
        path = context.get('path', '')
        suspicious_paths = ['/admin', '/api/admin', '/wp-admin', '/login']
        if any(suspicious in path.lower() for suspicious in suspicious_paths):
            score += 15  # Access to sensitive paths
        
        # Time-based scoring (requests during odd hours)
        try:
            timestamp = datetime.fromisoformat(context.get('timestamp', '').replace('Z', '+00:00'))
            hour = timestamp.hour
            if hour < 6 or hour > 22:  # Late night or early morning
                score += 10
        except (ValueError, AttributeError):
            pass
        
        # Cap at 100
        return min(score, 100)
    
    @staticmethod
    def format_rate_limit_headers(remaining: int, reset_time: datetime, limit: int) -> Dict[str, str]:
        """
        Format rate limit headers for HTTP response.
        
        Args:
            remaining: Remaining requests
            reset_time: Reset time
            limit: Total limit
            
        Returns:
            Dictionary of rate limit headers
        """
        reset_timestamp = int(reset_time.timestamp())
        
        return {
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': str(remaining),
            'X-RateLimit-Reset': str(reset_timestamp),
            'Retry-After': str(max(0, reset_timestamp - int(time.time()))),
            'X-RateLimit-Reset-ISO': reset_time.isoformat()
        }
    
    @staticmethod
    def parse_rate_limit_headers(headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Parse rate limit headers from HTTP response.
        
        Args:
            headers: HTTP response headers
            
        Returns:
            Parsed rate limit information
        """
        parsed = {}
        
        if 'X-RateLimit-Limit' in headers:
            parsed['limit'] = int(headers['X-RateLimit-Limit'])
        
        if 'X-RateLimit-Remaining' in headers:
            parsed['remaining'] = int(headers['X-RateLimit-Remaining'])
        
        if 'X-RateLimit-Reset' in headers:
            reset_timestamp = int(headers['X-RateLimit-Reset'])
            parsed['reset_time'] = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
        
        if 'Retry-After' in headers:
            parsed['retry_after'] = int(headers['Retry-After'])
        
        return parsed
    
    @staticmethod
    def cleanup_expired_cache_keys(pattern: str = "rate_limit:*") -> int:
        """
        Clean up expired cache keys.
        
        Args:
            pattern: Cache key pattern
            
        Returns:
            Number of keys cleaned up
        """
        try:
            # This is a simplified implementation
            # In production, you might use Redis SCAN or Django cache backend specific methods
            cleaned_count = 0
            
            # Get all keys matching pattern
            # Note: This implementation depends on your cache backend
            # For Redis, you might use: cache.client.keys(pattern)
            
            return cleaned_count
        except Exception as e:
            logger.error("Failed to cleanup cache keys: %s", e, exc_info=True)
            return 0
    
    @staticmethod
    def get_rate_limit_statistics(days: int = 30) -> Dict[str, Any]:
        """
        Get rate limit statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Statistics dictionary
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # This would typically query your database or analytics
            # For now, return mock statistics
            stats = {
                'total_requests': 0,
                'blocked_requests': 0,
                'allowed_requests': 0,
                'unique_users': 0,
                'unique_ips': 0,
                'top_endpoints': {},
                'top_blocked_ips': {},
                'daily_stats': {},
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                }
            }
            
            return stats
        except Exception as e:
            logger.error("Failed to get rate limit statistics: %s", e, exc_info=True)
            return {}
    
    @staticmethod
    def validate_rate_limit_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate rate limit configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Validation result
        """
        errors = []
        warnings = []
        
        # Required fields
        required_fields = ['limit_type', 'requests_per_unit', 'time_unit', 'time_value']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate requests_per_unit
        if 'requests_per_unit' in config:
            requests = config['requests_per_unit']
            if not isinstance(requests, int) or requests < 1:
                errors.append("requests_per_unit must be a positive integer")
            elif requests > 1000000:
                warnings.append("requests_per_unit is very large, consider reducing")
        
        # Validate time_unit
        if 'time_unit' in config:
            valid_units = ['second', 'minute', 'hour', 'day', 'week', 'month']
            unit = config['time_unit']
            if unit not in valid_units:
                errors.append(f"Invalid time_unit: {unit}. Must be one of: {valid_units}")
        
        # Validate time_value
        if 'time_value' in config:
            value = config['time_value']
            if not isinstance(value, int) or value < 1:
                errors.append("time_value must be a positive integer")
            elif value > 10080:  # 1 week in minutes
                warnings.append("time_value is very large, consider reducing")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }


class CacheUtils:
    """Utility class for cache operations."""
    
    @staticmethod
    def set_with_metadata(key: str, value: Any, timeout: int = None, metadata: Dict[str, Any] = None):
        """
        Set cache value with metadata.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            metadata: Additional metadata
        """
        cache_data = {
            'value': value,
            'metadata': metadata or {},
            'created_at': timezone.now().isoformat()
        }
        
        cache.set(key, cache_data, timeout)
    
    @staticmethod
    def get_with_metadata(key: str) -> Dict[str, Any]:
        """
        Get cache value with metadata.
        
        Args:
            key: Cache key
            
        Returns:
            Cache data dictionary
        """
        return cache.get(key, {})
    
    @staticmethod
    def increment_with_metadata(key: str, delta: int = 1, timeout: int = None) -> int:
        """
        Increment cache value with metadata.
        
        Args:
            key: Cache key
            delta: Increment amount
            timeout: Cache timeout
            
        Returns:
            New value
        """
        current_data = CacheUtils.get_with_metadata(key)
        
        if current_data:
            current_value = current_data.get('value', 0)
            new_value = current_value + delta
            
            CacheUtils.set_with_metadata(key, new_value, timeout, current_data.get('metadata', {}))
            return new_value
        else:
            CacheUtils.set_with_metadata(key, delta, timeout)
            return delta
    
    @staticmethod
    def get_or_set(key: str, default_func: Callable, timeout: int = None) -> Any:
        """
        Get value from cache or set using default function.
        
        Args:
            key: Cache key
            default_func: Function to generate default value
            timeout: Cache timeout
            
        Returns:
            Cached or generated value
        """
        cached_data = CacheUtils.get_with_metadata(key)
        
        if cached_data and 'value' in cached_data:
            return cached_data['value']
        
        # Generate default value
        default_value = default_func()
        CacheUtils.set_with_metadata(key, default_value, timeout)
        
        return default_value


class ValidationUtils:
    """Utility class for validation operations."""
    
    @staticmethod
    def validate_endpoint_pattern(pattern: str) -> bool:
        """
        Validate endpoint pattern.
        
        Args:
            pattern: Endpoint pattern
            
        Returns:
            True if valid
        """
        try:
            re.compile(pattern)
            return True
        except re.error:
            return False
    
    @staticmethod
    def validate_time_window(time_unit: str, time_value: int) -> bool:
        """
        Validate time window parameters.
        
        Args:
            time_unit: Time unit
            time_value: Time value
            
        Returns:
            True if valid
        """
        valid_units = ['second', 'minute', 'hour', 'day', 'week', 'month']
        
        if time_unit not in valid_units:
            return False
        
        if not isinstance(time_value, int) or time_value < 1:
            return False
        
        # Additional validation for specific units
        if time_unit == 'second' and time_value > 3600:  # Max 1 hour
            return False
        elif time_unit == 'minute' and time_value > 1440:  # Max 1 day
            return False
        elif time_unit == 'hour' and time_value > 168:  # Max 1 week
            return False
        elif time_unit == 'day' and time_value > 365:  # Max 1 year
            return False
        
        return True
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """
        Sanitize string value.
        
        Args:
            value: String to sanitize
            max_length: Maximum length
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Remove control characters
        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
        
        # Trim and limit length
        value = value.strip()[:max_length]
        
        return value


# Global utility instances
rate_limit_utils = RateLimitUtils()
cache_utils = CacheUtils()
validation_utils = ValidationUtils()


# Export utility classes and functions
__all__ = [
    'RateLimitUtils',
    'CacheUtils',
    'ValidationUtils',
    'rate_limit_utils',
    'cache_utils',
    'validation_utils'
]
