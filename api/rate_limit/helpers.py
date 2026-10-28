# api/rate_limit/helpers.py
"""
Helper functions and utilities for rate limit module.

Provides common utility functions and helper classes.
"""

import logging
import hashlib
import ipaddress
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from django.contrib.auth import get_user_model

from api.rate_limit.models import RateLimitLog, UserRateLimitProfile

logger = logging.getLogger(__name__)
User = get_user_model()


class RateLimitHelper:
    """
    Helper class for rate limiting operations.
    """
    
    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """
        Get client IP address from request.
        
        Args:
            request: HTTP request
            
        Returns:
            Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get the first IP in the chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return ip
    
    @staticmethod
    def get_user_agent(request: HttpRequest) -> str:
        """
        Get user agent from request.
        
        Args:
            request: HTTP request
            
        Returns:
            User agent string
        """
        return request.META.get('HTTP_USER_AGENT', '')
    
    @staticmethod
    def generate_cache_key(identifier: str, prefix: str = 'rate_limit') -> str:
        """
        Generate cache key for rate limiting.
        
        Args:
            identifier: Unique identifier
            prefix: Cache key prefix
            
        Returns:
            Cache key string
        """
        # Use hash to ensure consistent key format
        key_hash = hashlib.md5(f"{prefix}:{identifier}".encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    @staticmethod
    def is_valid_ip_address(ip: str) -> bool:
        """
        Validate IP address format.
        
        Args:
            ip: IP address string
            
        Returns:
            True if valid IP address
        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_ip_in_range(ip: str, ip_range: str) -> bool:
        """
        Check if IP address is in CIDR range.
        
        Args:
            ip: IP address
            ip_range: CIDR range (e.g., "192.168.1.0/24")
            
        Returns:
            True if IP is in range
        """
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
            return ipaddress.ip_address(ip) in network
        except ValueError:
            return False
    
    @staticmethod
    def normalize_endpoint(endpoint: str) -> str:
        """
        Normalize endpoint path.
        
        Args:
            endpoint: Endpoint path
            
        Returns:
            Normalized endpoint
        """
        # Remove query parameters
        endpoint = endpoint.split('?')[0]
        
        # Ensure leading slash
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        # Remove trailing slash (except for root)
        if len(endpoint) > 1 and endpoint.endswith('/'):
            endpoint = endpoint[:-1]
        
        return endpoint
    
    @staticmethod
    def extract_path_params(endpoint: str) -> Dict[str, str]:
        """
        Extract path parameters from endpoint.
        
        Args:
            endpoint: Endpoint path
            
        Returns:
            Dictionary of path parameters
        """
        # Simple path parameter extraction
        # This is a basic implementation - can be enhanced
        params = {}
        
        # Look for numeric IDs
        pattern = r'/(\d+)/'
        matches = re.findall(pattern, endpoint)
        
        for i, match in enumerate(matches):
            params[f'id_{i+1}'] = match
        
        return params
    
    @staticmethod
    def calculate_time_window(time_unit: str, time_value: int) -> int:
        """
        Calculate time window in seconds.
        
        Args:
            time_unit: Time unit (second, minute, hour, day)
            time_value: Time value
            
        Returns:
            Time window in seconds
        """
        unit_multipliers = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        
        return time_value * unit_multipliers.get(time_unit, 3600)
    
    @staticmethod
    def format_time_window(seconds: int) -> str:
        """
        Format time window in human readable format.
        
        Args:
            seconds: Time window in seconds
            
        Returns:
            Formatted time window string
        """
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"
    
    @staticmethod
    def get_rate_limit_headers(request) -> Dict[str, str]:
        """
        Get rate limit headers from request.
        
        Args:
            request: HTTP request
            
        Returns:
            Rate limit headers
        """
        headers = {}
        
        if hasattr(request, 'rate_limit_info'):
            info = request.rate_limit_info
            
            headers['X-RateLimit-Limit'] = str(info.get('max_requests', 0))
            headers['X-RateLimit-Remaining'] = str(info.get('remaining', 0))
            
            if 'reset_time' in info:
                headers['X-RateLimit-Reset'] = str(int(info['reset_time'].timestamp()))
            
            if 'retry_after' in info:
                headers['Retry-After'] = str(info['retry_after'])
        
        return headers
    
    @staticmethod
    def is_suspicious_user_agent(user_agent: str) -> bool:
        """
        Check if user agent appears suspicious.
        
        Args:
            user_agent: User agent string
            
        Returns:
            True if suspicious
        """
        if not user_agent:
            return True
        
        suspicious_patterns = [
            r'bot',
            r'crawler',
            r'scraper',
            r'automated',
            r'spider',
            r'curl',
            r'wget',
            r'python-requests',
            r'postman',
            r'insomnia'
        ]
        
        user_agent_lower = user_agent.lower()
        
        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent_lower):
                return True
        
        return False
    
    @staticmethod
    def calculate_suspicion_score(request_data: Dict[str, Any]) -> int:
        """
        Calculate suspicion score for a request.
        
        Args:
            request_data: Request data
            
        Returns:
            Suspicion score (0-100)
        """
        score = 0
        
        # Check user agent
        user_agent = request_data.get('user_agent', '')
        if RateLimitHelper.is_suspicious_user_agent(user_agent):
            score += 20
        
        # Check request frequency
        recent_requests = request_data.get('recent_requests', 0)
        if recent_requests > 100:
            score += 30
        elif recent_requests > 50:
            score += 15
        
        # Check endpoint patterns
        endpoint = request_data.get('endpoint', '')
        suspicious_endpoints = ['/admin/', '/api/admin/', '/config/', '/system/']
        for suspicious_endpoint in suspicious_endpoints:
            if endpoint.startswith(suspicious_endpoint):
                score += 25
                break
        
        # Check time-based patterns
        hour = request_data.get('hour', 0)
        if 2 <= hour <= 6:  # Unusual hours
            score += 10
        
        # Check for multiple endpoints
        unique_endpoints = request_data.get('unique_endpoints', 1)
        if unique_endpoints > 20:
            score += 15
        elif unique_endpoints > 10:
            score += 5
        
        return min(100, score)
    
    @staticmethod
    def get_geo_location(ip_address: str) -> Dict[str, Any]:
        """
        Get geolocation data for IP address.
        
        Args:
            ip_address: IP address
            
        Returns:
            Geolocation data
        """
        # This is a placeholder - would integrate with a geo IP service
        # For now, return basic data
        return {
            'country': 'Unknown',
            'city': 'Unknown',
            'latitude': 0.0,
            'longitude': 0.0,
            'timezone': 'UTC'
        }
    
    @staticmethod
    def cleanup_old_cache_keys(pattern: str = 'rate_limit:*', max_age_hours: int = 24):
        """
        Clean up old rate limit cache keys.
        
        Args:
            pattern: Cache key pattern
            max_age_hours: Maximum age in hours
        """
        try:
            keys = cache.keys(pattern)
            cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
            
            for key in keys:
                # Check if key is old
                # This is a simplified approach - in production, you'd store timestamps
                cache.delete(key)
            
            logger.info(f"Cleaned up {len(keys)} rate limit cache keys")
            
        except Exception as e:
            logger.error(f"Failed to cleanup cache keys: {str(e)}")
    
    @staticmethod
    def export_rate_limit_data(start_date: datetime.date, end_date: datetime.date, 
                              format: str = 'csv') -> Dict[str, Any]:
        """
        Export rate limit data for date range.
        
        Args:
            start_date: Start date
            end_date: End date
            format: Export format (csv, json, excel)
            
        Returns:
            Export data
        """
        try:
            from api.rate_limit.models import RateLimitLog
            
            start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            
            logs = RateLimitLog.objects.filter(
                timestamp__gte=start_datetime,
                timestamp__lte=end_datetime
            ).select_related('user', 'config')
            
            # Convert to export format
            export_data = []
            for log in logs:
                export_data.append({
                    'timestamp': log.timestamp.isoformat(),
                    'user': log.user.username if log.user else 'Anonymous',
                    'ip_address': log.ip_address,
                    'endpoint': log.endpoint,
                    'method': log.request_method,
                    'status': log.status,
                    'config': log.config.name if log.config else None,
                    'suspicion_score': log.suspicion_score,
                })
            
            return {
                'format': format,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_records': len(export_data),
                'data': export_data
            }
            
        except Exception as e:
            logger.error(f"Failed to export rate limit data: {str(e)}")
            return {'error': str(e)}


class CacheHelper:
    """
    Helper class for cache operations.
    """
    
    @staticmethod
    def get_cached_rate_limit(identifier: str, time_window: str) -> Optional[int]:
        """
        Get cached rate limit count.
        
        Args:
            identifier: Unique identifier
            time_window: Time window
            
        Returns:
            Current count or None
        """
        cache_key = RateLimitHelper.generate_cache_key(f"{identifier}:{time_window}")
        return cache.get(cache_key)
    
    @staticmethod
    def set_cached_rate_limit(identifier: str, time_window: str, count: int, ttl: int = 3600):
        """
        Set cached rate limit count.
        
        Args:
            identifier: Unique identifier
            time_window: Time window
            count: Current count
            ttl: Cache TTL
        """
        cache_key = RateLimitHelper.generate_cache_key(f"{identifier}:{time_window}")
        cache.set(cache_key, count, ttl)
    
    @staticmethod
    def increment_cached_rate_limit(identifier: str, time_window: str, ttl: int = 3600) -> int:
        """
        Increment cached rate limit count.
        
        Args:
            identifier: Unique identifier
            time_window: Time window
            ttl: Cache TTL
            
        Returns:
            New count
        """
        cache_key = RateLimitHelper.generate_cache_key(f"{identifier}:{time_window}")
        
        # Use cache.incr if available, otherwise get/set
        try:
            return cache.incr(cache_key, 1, ttl)
        except AttributeError:
            # Fallback for cache backends that don't support incr
            current = cache.get(cache_key, 0)
            new_count = current + 1
            cache.set(cache_key, new_count, ttl)
            return new_count
    
    @staticmethod
    def reset_cached_rate_limit(identifier: str, time_window: str):
        """
        Reset cached rate limit count.
        
        Args:
            identifier: Unique identifier
            time_window: Time window
        """
        cache_key = RateLimitHelper.generate_cache_key(f"{identifier}:{time_window}")
        cache.delete(cache_key)


class ValidationHelper:
    """
    Helper class for validation operations.
    """
    
    @staticmethod
    def validate_rate_limit_config(config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate rate limit configuration data.
        
        Args:
            config_data: Configuration data
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Validate required fields
        if 'rate_limit_type' not in config_data:
            errors.append("rate_limit_type is required")
        
        if 'requests_per_unit' not in config_data:
            errors.append("requests_per_unit is required")
        
        if 'time_unit' not in config_data:
            errors.append("time_unit is required")
        
        # Validate field values
        if 'rate_limit_type' in config_data:
            valid_types = ['user', 'ip', 'endpoint', 'global', 'referral', 'task', 'offer']
            if config_data['rate_limit_type'] not in valid_types:
                errors.append(f"Invalid rate_limit_type. Must be one of: {valid_types}")
        
        if 'requests_per_unit' in config_data:
            requests = config_data['requests_per_unit']
            if not isinstance(requests, int) or requests <= 0:
                errors.append("requests_per_unit must be a positive integer")
            elif requests > 1000000:
                errors.append("requests_per_unit cannot exceed 1,000,000")
        
        if 'time_unit' in config_data:
            valid_units = ['second', 'minute', 'hour', 'day']
            if config_data['time_unit'] not in valid_units:
                errors.append(f"Invalid time_unit. Must be one of: {valid_units}")
        
        if 'time_value' in config_data:
            time_value = config_data['time_value']
            if not isinstance(time_value, int) or time_value <= 0:
                errors.append("time_value must be a positive integer")
            elif time_value > 365:
                errors.append("time_value cannot exceed 365")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_ip_block_data(block_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate IP block data.
        
        Args:
            block_data: Block data
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Validate required fields
        if 'ip_address' not in block_data:
            errors.append("ip_address is required")
        
        if 'block_type' not in block_data:
            errors.append("block_type is required")
        
        if 'block_reason' not in block_data:
            errors.append("block_reason is required")
        
        # Validate field values
        if 'ip_address' in block_data:
            ip = block_data['ip_address']
            if not RateLimitHelper.is_valid_ip_address(ip):
                errors.append("Invalid IP address format")
        
        if 'block_type' in block_data:
            valid_types = ['single', 'range', 'subnet', 'country', 'asn', 'wildcard']
            if block_data['block_type'] not in valid_types:
                errors.append(f"Invalid block_type. Must be one of: {valid_types}")
        
        return len(errors) == 0, errors


class FormatHelper:
    """
    Helper class for formatting data.
    """
    
    @staticmethod
    def format_bytes(bytes_count: int) -> str:
        """
        Format bytes in human readable format.
        
        Args:
            bytes_count: Number of bytes
            
        Returns:
            Formatted string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        
        return f"{bytes_count:.2f} PB"
    
    @staticmethod
    def format_number(number: int) -> str:
        """
        Format number with thousands separator.
        
        Args:
            number: Number to format
            
        Returns:
            Formatted string
        """
        return f"{number:,}"
    
    @staticmethod
    def format_percentage(value: float, decimal_places: int = 2) -> str:
        """
        Format percentage.
        
        Args:
            value: Percentage value (0-100)
            decimal_places: Decimal places
            
        Returns:
            Formatted percentage string
        """
        return f"{value:.{decimal_places}f}%"
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Format duration in human readable format.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        elif seconds < 86400:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{hours}h {remaining_minutes}m"
        else:
            days = seconds // 86400
            remaining_hours = (seconds % 86400) // 3600
            return f"{days}d {remaining_hours}h"


# Export helper classes and functions
__all__ = [
    'RateLimitHelper',
    'CacheHelper',
    'ValidationHelper',
    'FormatHelper'
]
