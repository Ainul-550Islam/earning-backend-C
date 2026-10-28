# api/rate_limit/validator.py
"""
Validators for rate limit module.

Provides validation functions for rate limiting data and configurations.
"""

import re
import ipaddress
from typing import Dict, Any, List, Optional, Union
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta

from api.rate_limit.models import RateLimitConfig, RateLimitException, IPBlockList


class RateLimitConfigValidator:
    """
    Validator for rate limit configurations.
    """
    
    @staticmethod
    def validate_config_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate rate limit configuration data.
        
        Args:
            data: Configuration data to validate
            
        Returns:
            Validated and cleaned data
            
        Raises:
            ValidationError: If data is invalid
        """
        errors = {}
        cleaned_data = {}
        
        # Validate name
        if 'name' in data:
            name = data.get('name', '').strip()
            if not name:
                errors['name'] = 'Name is required'
            elif len(name) > 100:
                errors['name'] = 'Name cannot exceed 100 characters'
            elif not re.match(r'^[a-zA-Z0-9_-]+$', name):
                errors['name'] = 'Name can only contain letters, numbers, underscores, and hyphens'
            else:
                cleaned_data['name'] = name
        
        # Validate rate limit type
        if 'rate_limit_type' in data:
            valid_types = ['user', 'ip', 'endpoint', 'global', 'referral', 'task', 'offer']
            rate_limit_type = data.get('rate_limit_type')
            if rate_limit_type not in valid_types:
                errors['rate_limit_type'] = f'Invalid type. Must be one of: {valid_types}'
            else:
                cleaned_data['rate_limit_type'] = rate_limit_type
        
        # Validate requests per unit
        if 'requests_per_unit' in data:
            requests_per_unit = data.get('requests_per_unit')
            if not isinstance(requests_per_unit, int) or requests_per_unit <= 0:
                errors['requests_per_unit'] = 'Requests per unit must be a positive integer'
            elif requests_per_unit > 1000000:
                errors['requests_per_unit'] = 'Requests per unit cannot exceed 1,000,000'
            else:
                cleaned_data['requests_per_unit'] = requests_per_unit
        
        # Validate time unit
        if 'time_unit' in data:
            valid_units = ['second', 'minute', 'hour', 'day']
            time_unit = data.get('time_unit')
            if time_unit not in valid_units:
                errors['time_unit'] = f'Invalid time unit. Must be one of: {valid_units}'
            else:
                cleaned_data['time_unit'] = time_unit
        
        # Validate time value
        if 'time_value' in data:
            time_value = data.get('time_value')
            if not isinstance(time_value, int) or time_value <= 0:
                errors['time_value'] = 'Time value must be a positive integer'
            elif time_value > 365:  # Max 365 days
                errors['time_value'] = 'Time value cannot exceed 365'
            else:
                cleaned_data['time_value'] = time_value
        
        # Validate target fields (at least one must be set for non-global configs)
        target_fields = ['user', 'ip_address', 'endpoint', 'task_type', 'offer_wall']
        has_target = any(data.get(field) for field in target_fields)
        
        if data.get('rate_limit_type') != 'global' and not has_target:
            errors['target'] = 'At least one target field must be specified for non-global configs'
        
        # Validate IP address
        if 'ip_address' in data and data.get('ip_address'):
            try:
                ipaddress.ip_address(data['ip_address'])
                cleaned_data['ip_address'] = data['ip_address']
            except ValueError:
                errors['ip_address'] = 'Invalid IP address format'
        
        # Validate endpoint
        if 'endpoint' in data and data.get('endpoint'):
            endpoint = data.get('endpoint', '').strip()
            if not endpoint.startswith('/'):
                errors['endpoint'] = 'Endpoint must start with /'
            elif len(endpoint) > 500:
                errors['endpoint'] = 'Endpoint cannot exceed 500 characters'
            else:
                cleaned_data['endpoint'] = endpoint
        
        # Validate task type
        if 'task_type' in data and data.get('task_type'):
            task_type = data.get('task_type', '').strip()
            if len(task_type) > 50:
                errors['task_type'] = 'Task type cannot exceed 50 characters'
            elif not re.match(r'^[a-zA-Z0-9_-]+$', task_type):
                errors['task_type'] = 'Task type can only contain letters, numbers, underscores, and hyphens'
            else:
                cleaned_data['task_type'] = task_type
        
        # Validate offer wall
        if 'offer_wall' in data and data.get('offer_wall'):
            offer_wall = data.get('offer_wall', '').strip()
            if len(offer_wall) > 100:
                errors['offer_wall'] = 'Offer wall cannot exceed 100 characters'
            elif not re.match(r'^[a-zA-Z0-9_-]+$', offer_wall):
                errors['offer_wall'] = 'Offer wall can only contain letters, numbers, underscores, and hyphens'
            else:
                cleaned_data['offer_wall'] = offer_wall
        
        # Validate whitelist
        if 'whitelist' in data:
            whitelist = data.get('whitelist')
            if not isinstance(whitelist, list):
                errors['whitelist'] = 'Whitelist must be a list'
            else:
                cleaned_data['whitelist'] = whitelist
        
        # Validate is_active
        if 'is_active' in data:
            is_active = data.get('is_active')
            if not isinstance(is_active, bool):
                errors['is_active'] = 'is_active must be a boolean'
            else:
                cleaned_data['is_active'] = is_active
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data
    
    @staticmethod
    def validate_config_limits(requests_per_unit: int, time_unit: str, time_value: int) -> None:
        """
        Validate rate limit limits are reasonable.
        
        Args:
            requests_per_unit: Number of requests allowed
            time_unit: Time unit (second, minute, hour, day)
            time_value: Time value
            
        Raises:
            ValidationError: If limits are unreasonable
        """
        # Calculate requests per second
        unit_multipliers = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        
        total_seconds = time_value * unit_multipliers.get(time_unit, 3600)
        requests_per_second = requests_per_unit / total_seconds
        
        # Check for unreasonable limits
        if requests_per_second > 1000:  # More than 1000 requests per second
            raise ValidationError('Rate limit is too permissive (max 1000 requests per second)')
        
        if requests_per_second < 0.001:  # Less than 1 request per 1000 seconds
            raise ValidationError('Rate limit is too restrictive (min 0.001 requests per second)')


class IPBlockValidator:
    """
    Validator for IP block configurations.
    """
    
    @staticmethod
    def validate_ip_block_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate IP block data.
        
        Args:
            data: IP block data to validate
            
        Returns:
            Validated and cleaned data
            
        Raises:
            ValidationError: If data is invalid
        """
        errors = {}
        cleaned_data = {}
        
        # Validate IP address or range
        if 'ip_address' in data:
            ip_address = data.get('ip_address', '').strip()
            if not ip_address:
                errors['ip_address'] = 'IP address is required'
            else:
                try:
                    # Validate single IP or CIDR range
                    if '/' in ip_address:
                        ipaddress.ip_network(ip_address, strict=False)
                    else:
                        ipaddress.ip_address(ip_address)
                    cleaned_data['ip_address'] = ip_address
                except ValueError:
                    errors['ip_address'] = 'Invalid IP address or CIDR range format'
        
        # Validate block type
        if 'block_type' in data:
            valid_types = ['single', 'range', 'subnet', 'country', 'asn', 'wildcard']
            block_type = data.get('block_type')
            if block_type not in valid_types:
                errors['block_type'] = f'Invalid block type. Must be one of: {valid_types}'
            else:
                cleaned_data['block_type'] = block_type
        
        # Validate block reason
        if 'block_reason' in data:
            valid_reasons = ['manual', 'abuse', 'rate_limit', 'security', 'policy', 
                           'malware', 'suspicious', 'auto_detection', 'user_report', 'system_detection']
            block_reason = data.get('block_reason')
            if block_reason not in valid_reasons:
                errors['block_reason'] = f'Invalid block reason. Must be one of: {valid_reasons}'
            else:
                cleaned_data['block_reason'] = block_reason
        
        # Validate expires_at
        if 'expires_at' in data and data.get('expires_at'):
            expires_at = data.get('expires_at')
            if isinstance(expires_at, str):
                try:
                    from django.utils.dateparse import parse_datetime
                    parsed = parse_datetime(expires_at)
                    if not parsed:
                        errors['expires_at'] = 'Invalid datetime format'
                    elif parsed <= timezone.now():
                        errors['expires_at'] = 'Expiration time must be in the future'
                    else:
                        cleaned_data['expires_at'] = parsed
                except Exception:
                    errors['expires_at'] = 'Invalid datetime format'
            elif expires_at <= timezone.now():
                errors['expires_at'] = 'Expiration time must be in the future'
            else:
                cleaned_data['expires_at'] = expires_at
        
        # Validate permanent flag
        if 'permanent' in data:
            permanent = data.get('permanent')
            if not isinstance(permanent, bool):
                errors['permanent'] = 'permanent must be a boolean'
            else:
                cleaned_data['permanent'] = permanent
        
        # Validate is_active
        if 'is_active' in data:
            is_active = data.get('is_active')
            if not isinstance(is_active, bool):
                errors['is_active'] = 'is_active must be a boolean'
            else:
                cleaned_data['is_active'] = is_active
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data
    
    @staticmethod
    def validate_ip_range(ip_address: str, block_type: str) -> None:
        """
        Validate IP address range matches block type.
        
        Args:
            ip_address: IP address or range
            block_type: Type of block
            
        Raises:
            ValidationError: If IP doesn't match block type
        """
        try:
            if block_type == 'single':
                # Must be single IP
                ipaddress.ip_address(ip_address)
                if '/' in ip_address:
                    raise ValidationError('Single IP block type cannot use CIDR notation')
            
            elif block_type == 'range':
                # Should be CIDR range
                if '/' not in ip_address:
                    raise ValidationError('Range block type requires CIDR notation')
                ipaddress.ip_network(ip_address, strict=False)
            
            elif block_type == 'subnet':
                # Should be subnet (CIDR with /24, /16, /8)
                if '/' not in ip_address:
                    raise ValidationError('Subnet block type requires CIDR notation')
                network = ipaddress.ip_network(ip_address, strict=False)
                if network.prefixlen not in [8, 16, 24, 32]:
                    raise ValidationError('Subnet block type requires /8, /16, /24, or /32')
            
        except ValueError as e:
            raise ValidationError(f'Invalid IP format for {block_type}: {str(e)}')


class AbuseReportValidator:
    """
    Validator for abuse reports.
    """
    
    @staticmethod
    def validate_abuse_report_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate abuse report data.
        
        Args:
            data: Abuse report data to validate
            
        Returns:
            Validated and cleaned data
            
        Raises:
            ValidationError: If data is invalid
        """
        errors = {}
        cleaned_data = {}
        
        # Validate abuse type
        if 'abuse_type' in data:
            valid_types = ['rate_limit', 'spam', 'fraud', 'malicious', 'bot', 
                          'scraping', 'brute_force', 'ddos', 'suspicious_pattern', 'other']
            abuse_type = data.get('abuse_type')
            if abuse_type not in valid_types:
                errors['abuse_type'] = f'Invalid abuse type. Must be one of: {valid_types}'
            else:
                cleaned_data['abuse_type'] = abuse_type
        
        # Validate severity
        if 'severity' in data:
            severity = data.get('severity')
            if not isinstance(severity, int) or severity < 1 or severity > 5:
                errors['severity'] = 'Severity must be an integer between 1 and 5'
            else:
                cleaned_data['severity'] = severity
        
        # Validate description
        if 'description' in data:
            description = data.get('description', '').strip()
            if len(description) > 1000:
                errors['description'] = 'Description cannot exceed 1000 characters'
            else:
                cleaned_data['description'] = description
        
        # Validate IP address
        if 'ip_address' in data and data.get('ip_address'):
            try:
                ipaddress.ip_address(data['ip_address'])
                cleaned_data['ip_address'] = data['ip_address']
            except ValueError:
                errors['ip_address'] = 'Invalid IP address format'
        
        # Validate evidence
        if 'evidence' in data:
            evidence = data.get('evidence')
            if not isinstance(evidence, dict):
                errors['evidence'] = 'Evidence must be a dictionary'
            else:
                cleaned_data['evidence'] = evidence
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class RateLimitExceptionValidator:
    """
    Validator for rate limit exceptions.
    """
    
    @staticmethod
    def validate_exception_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate rate limit exception data.
        
        Args:
            data: Exception data to validate
            
        Returns:
            Validated and cleaned data
            
        Raises:
            ValidationError: If data is invalid
        """
        errors = {}
        cleaned_data = {}
        
        # Validate exception type
        if 'exception_type' in data:
            valid_types = ['whitelist', 'blacklist', 'bypass', 'increased_limit', 
                          'decreased_limit', 'no_limit', 'custom_limit']
            exception_type = data.get('exception_type')
            if exception_type not in valid_types:
                errors['exception_type'] = f'Invalid exception type. Must be one of: {valid_types}'
            else:
                cleaned_data['exception_type'] = exception_type
        
        # Validate multiplier
        if 'multiplier' in data:
            multiplier = data.get('multiplier')
            if not isinstance(multiplier, (int, float)) or multiplier <= 0:
                errors['multiplier'] = 'Multiplier must be a positive number'
            elif multiplier > 1000:
                errors['multiplier'] = 'Multiplier cannot exceed 1000'
            else:
                cleaned_data['multiplier'] = multiplier
        
        # Validate max_requests
        if 'max_requests' in data and data.get('max_requests') is not None:
            max_requests = data.get('max_requests')
            if not isinstance(max_requests, int) or max_requests <= 0:
                errors['max_requests'] = 'Max requests must be a positive integer'
            elif max_requests > 1000000:
                errors['max_requests'] = 'Max requests cannot exceed 1,000,000'
            else:
                cleaned_data['max_requests'] = max_requests
        
        # Validate expires_at
        if 'expires_at' in data and data.get('expires_at'):
            expires_at = data.get('expires_at')
            if isinstance(expires_at, str):
                try:
                    from django.utils.dateparse import parse_datetime
                    parsed = parse_datetime(expires_at)
                    if not parsed:
                        errors['expires_at'] = 'Invalid datetime format'
                    elif parsed <= timezone.now():
                        errors['expires_at'] = 'Expiration time must be in the future'
                    else:
                        cleaned_data['expires_at'] = parsed
                except Exception:
                    errors['expires_at'] = 'Invalid datetime format'
            elif expires_at <= timezone.now():
                errors['expires_at'] = 'Expiration time must be in the future'
            else:
                cleaned_data['expires_at'] = expires_at
        
        # Validate permanent flag
        if 'permanent' in data:
            permanent = data.get('permanent')
            if not isinstance(permanent, bool):
                errors['permanent'] = 'permanent must be a boolean'
            else:
                cleaned_data['permanent'] = permanent
        
        # Validate is_active
        if 'is_active' in data:
            is_active = data.get('is_active')
            if not isinstance(is_active, bool):
                errors['is_active'] = 'is_active must be a boolean'
            else:
                cleaned_data['is_active'] = is_active
        
        # Validate IP address
        if 'ip_address' in data and data.get('ip_address'):
            try:
                ipaddress.ip_address(data['ip_address'])
                cleaned_data['ip_address'] = data['ip_address']
            except ValueError:
                errors['ip_address'] = 'Invalid IP address format'
        
        # Validate endpoints
        if 'endpoints' in data:
            endpoints = data.get('endpoints')
            if not isinstance(endpoints, list):
                errors['endpoints'] = 'Endpoints must be a list'
            else:
                for endpoint in endpoints:
                    if not isinstance(endpoint, str) or not endpoint.startswith('/'):
                        errors['endpoints'] = 'All endpoints must start with /'
                        break
                if 'endpoints' not in errors:
                    cleaned_data['endpoints'] = endpoints
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class RequestValidator:
    """
    Validator for HTTP requests in rate limiting context.
    """
    
    @staticmethod
    def validate_request_for_rate_limiting(request) -> Dict[str, Any]:
        """
        Validate request for rate limiting.
        
        Args:
            request: HTTP request object
            
        Returns:
            Validated request data
            
        Raises:
            ValidationError: If request is invalid
        """
        errors = {}
        validated_data = {}
        
        # Validate IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        try:
            ipaddress.ip_address(ip_address)
            validated_data['ip_address'] = ip_address
        except ValueError:
            errors['ip_address'] = 'Invalid client IP address'
        
        # Validate user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if len(user_agent) > 500:
            errors['user_agent'] = 'User agent too long'
        else:
            validated_data['user_agent'] = user_agent
        
        # Validate method
        valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        method = request.method
        if method not in valid_methods:
            errors['method'] = f'Invalid HTTP method: {method}'
        else:
            validated_data['method'] = method
        
        # Validate path
        path = request.path
        if not path or not path.startswith('/'):
            errors['path'] = 'Invalid request path'
        elif len(path) > 2000:
            errors['path'] = 'Request path too long'
        else:
            validated_data['path'] = path
        
        # Validate content length
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                content_length = int(content_length)
                if content_length > 100 * 1024 * 1024:  # 100MB
                    errors['content_length'] = 'Request too large'
                else:
                    validated_data['content_length'] = content_length
            except ValueError:
                errors['content_length'] = 'Invalid content length'
        
        if errors:
            raise ValidationError(errors)
        
        return validated_data
    
    @staticmethod
    def is_suspicious_request(request) -> bool:
        """
        Check if request appears suspicious.
        
        Args:
            request: HTTP request object
            
        Returns:
            True if request appears suspicious
        """
        suspicious_indicators = []
        
        # Check for suspicious user agents
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        suspicious_agents = ['bot', 'crawler', 'spider', 'scraper', 'automated']
        if any(agent in user_agent for agent in suspicious_agents):
            suspicious_indicators.append('suspicious_user_agent')
        
        # Check for missing common headers
        common_headers = ['HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING']
        missing_headers = [header for header in common_headers if header not in request.META]
        if len(missing_headers) > 1:
            suspicious_indicators.append('missing_common_headers')
        
        # Check for unusual request patterns
        path = request.path
        if path.count('/') > 10:  # Very deep path
            suspicious_indicators.append('deep_path')
        
        if len(path) > 500:  # Very long path
            suspicious_indicators.append('long_path')
        
        # Check for unusual parameter patterns
        query_string = request.META.get('QUERY_STRING', '')
        if query_string.count('&') > 20:  # Many parameters
            suspicious_indicators.append('many_parameters')
        
        return len(suspicious_indicators) >= 2


# Custom Django validators
class IPAddressValidator(RegexValidator):
    """
    Custom validator for IP addresses.
    """
    def __init__(self):
        # IPv4 and IPv6 regex pattern
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$|^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        super().__init__(regex=pattern, message='Enter a valid IP address.')


class CIDRValidator(RegexValidator):
    """
    Custom validator for CIDR notation.
    """
    def __init__(self):
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/(?:[0-9]|[1-2][0-9]|3[0-2])$'
        super().__init__(regex=pattern, message='Enter a valid CIDR notation.')


class EndpointValidator(RegexValidator):
    """
    Custom validator for API endpoints.
    """
    def __init__(self):
        pattern = r'^/[a-zA-Z0-9/_-]*$'
        super().__init__(regex=pattern, message='Endpoint must start with / and contain only letters, numbers, underscores, and hyphens.')


# Export validators
__all__ = [
    'RateLimitConfigValidator',
    'IPBlockValidator',
    'AbuseReportValidator',
    'RateLimitExceptionValidator',
    'RequestValidator',
    'IPAddressValidator',
    'CIDRValidator',
    'EndpointValidator'
]
