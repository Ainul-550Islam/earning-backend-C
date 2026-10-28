"""
Rate Limit Validators

Validation functions for rate limiting configurations and values.
"""

import re
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from api.rate_limit.exceptions import InvalidRateLimitConfig


def validate_rate_limit_value(value, field_name=None):
    """
    Validate rate limit value (requests per unit).
    
    Args:
        value: The rate limit value to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        int: Validated rate limit value
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    if value is None:
        raise InvalidRateLimitConfig(
            message=_("Rate limit value cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
        )
    
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise InvalidRateLimitConfig(
            message=_("Rate limit value must be a number"),
            config_field=field_name,
            config_value=value,
            validation_error=_("Must be an integer")
        )
    
    if value <= 0:
        raise InvalidRateLimitConfig(
            message=_("Rate limit value must be greater than 0"),
            config_field=field_name,
            config_value=value,
            validation_error=_("Must be positive")
        )
    
    # Check for reasonable maximum values
    max_requests_per_unit = getattr(settings, 'RATE_LIMIT_MAX_REQUESTS_PER_UNIT', 1000000)
    if value > max_requests_per_unit:
        raise InvalidRateLimitConfig(
            message=_("Rate limit value cannot exceed %(max)s requests") % {
                'max': max_requests_per_unit
            },
            config_field=field_name,
            config_value=value,
            validation_error=_("Value too large")
        )
    
    return value


def validate_window_seconds(seconds, field_name=None):
    """
    Validate time window in seconds.
    
    Args:
        seconds: The time window in seconds to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        int: Validated time window in seconds
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    if seconds is None:
        raise InvalidRateLimitConfig(
            message=_("Time window cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
        )
    
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        raise InvalidRateLimitConfig(
            message=_("Time window must be a number"),
            config_field=field_name,
            config_value=seconds,
            validation_error=_("Must be an integer")
        )
    
    if seconds <= 0:
        raise InvalidRateLimitConfig(
            message=_("Time window must be greater than 0 seconds"),
            config_field=field_name,
            config_value=seconds,
            validation_error=_("Must be positive")
        )
    
    # Check for reasonable maximum time windows
    max_window_seconds = getattr(settings, 'RATE_LIMIT_MAX_WINDOW_SECONDS', 86400 * 30)  # 30 days
    if seconds > max_window_seconds:
        raise InvalidRateLimitConfig(
            message=_("Time window cannot exceed %(max)s seconds") % {
                'max': max_window_seconds
            },
            config_field=field_name,
            config_value=seconds,
            validation_error=_("Window too large")
        )
    
    return seconds


def validate_time_unit(time_unit, field_name=None):
    """
    Validate time unit (second, minute, hour, day).
    
    Args:
        time_unit: The time unit to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated time unit
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    valid_units = ['second', 'minute', 'hour', 'day']
    
    if time_unit not in valid_units:
        raise InvalidRateLimitConfig(
            message=_("Invalid time unit '%(unit)s'. Must be one of: %(units)s") % {
                'unit': time_unit,
                'units': ', '.join(valid_units)
            },
            config_field=field_name,
            config_value=time_unit,
            validation_error=_("Invalid time unit")
        )
    
    return time_unit


def validate_rate_limit_type(limit_type, field_name=None):
    """
    Validate rate limit type.
    
    Args:
        limit_type: The rate limit type to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated rate limit type
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    valid_types = ['user', 'ip', 'endpoint', 'global', 'referral', 'task']
    
    if limit_type not in valid_types:
        raise InvalidRateLimitConfig(
            message=_("Invalid rate limit type '%(type)s'. Must be one of: %(types)s") % {
                'type': limit_type,
                'types': ', '.join(valid_types)
            },
            config_field=field_name,
            config_value=limit_type,
            validation_error=_("Invalid rate limit type")
        )
    
    return limit_type


def validate_ip_address(ip_address, field_name=None):
    """
    Validate IP address format.
    
    Args:
        ip_address: The IP address to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated IP address
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    import ipaddress
    
    if not ip_address:
        raise InvalidRateLimitConfig(
            message=_("IP address cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
        )
    
    try:
        ip = ipaddress.ip_address(ip_address)
        return str(ip)
    except ValueError:
        raise InvalidRateLimitConfig(
            message=_("Invalid IP address format: '%(ip)s'") % {'ip': ip_address},
            config_field=field_name,
            config_value=ip_address,
            validation_error=_("Invalid IP address")
        )


def validate_ip_range(start_ip, end_ip, field_name=None):
    """
    Validate IP address range.
    
    Args:
        start_ip: Start IP address of the range
        end_ip: End IP address of the range
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        tuple: Validated (start_ip, end_ip) tuple
        
    Raises:
        ValidationError: If the values are invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    import ipaddress
    
    # Validate both IPs
    start_ip = validate_ip_address(start_ip, f"{field_name}_start" if field_name else "start_ip")
    end_ip = validate_ip_address(end_ip, f"{field_name}_end" if field_name else "end_ip")
    
    try:
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start >= end:
            raise InvalidRateLimitConfig(
                message=_("Start IP must be less than end IP address"),
                config_field=field_name,
                config_value=f"{start_ip}-{end_ip}",
                validation_error=_("Invalid IP range")
            )
        
        # Check if range is too large
        range_size = int(end) - int(start)
        max_range_size = getattr(settings, 'RATE_LIMIT_MAX_IP_RANGE_SIZE', 65536)  # /24 network
        if range_size > max_range_size:
            raise InvalidRateLimitConfig(
                message=_("IP range too large. Maximum size is %(max)s addresses") % {
                    'max': max_range_size
                },
                config_field=field_name,
                config_value=f"{start_ip}-{end_ip}",
                validation_error=_("Range too large")
            )
        
        return (str(start), str(end))
        
    except ValueError as e:
        raise InvalidRateLimitConfig(
            message=_("Invalid IP range: %(error)s") % {'error': str(e)},
            config_field=field_name,
            config_value=f"{start_ip}-{end_ip}",
            validation_error=_("Invalid IP range")
        )


def validate_subnet(subnet, field_name=None):
    """
    Validate subnet/CIDR notation.
    
    Args:
        subnet: The subnet to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated subnet
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    import ipaddress
    
    if not subnet:
        raise InvalidRateLimitConfig(
            message=_("Subnet cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
        )
    
    try:
        network = ipaddress.ip_network(subnet, strict=False)
        
        # Check if subnet is too large
        max_prefix_len = getattr(settings, 'RATE_LIMIT_MAX_SUBNET_PREFIX', 24)  # /24
        if network.prefixlen < max_prefix_len:
            raise InvalidRateLimitConfig(
                message=_("Subnet too large. Maximum prefix length is /%(max)s") % {
                    'max': max_prefix_len
                },
                config_field=field_name,
                config_value=subnet,
                validation_error=_("Subnet too large")
            )
        
        return str(network)
        
    except ValueError:
        raise InvalidRateLimitConfig(
            message=_("Invalid subnet format: '%(subnet)s'") % {'subnet': subnet},
            config_field=field_name,
            config_value=subnet,
            validation_error=_("Invalid subnet")
        )


def validate_endpoint(endpoint, field_name=None):
    """
    Validate endpoint URL pattern.
    
    Args:
        endpoint: The endpoint to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated endpoint
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    if not endpoint:
        raise InvalidRateLimitConfig(
            message=_("Endpoint cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
    )
    
    # Basic URL pattern validation
    if not endpoint.startswith('/'):
        raise InvalidRateLimitConfig(
            message=_("Endpoint must start with '/'"),
            config_field=field_name,
            config_value=endpoint,
            validation_error=_("Invalid endpoint format")
        )
    
    # Check for invalid characters
    invalid_chars = ['<', '>', '"', ' ', '|']
    if any(char in endpoint for char in invalid_chars):
        raise InvalidRateLimitConfig(
            message=_("Endpoint contains invalid characters"),
            config_field=field_name,
            config_value=endpoint,
            validation_error=_("Invalid characters in endpoint")
        )
    
    # Length validation
    max_length = getattr(settings, 'RATE_LIMIT_MAX_ENDPOINT_LENGTH', 500)
    if len(endpoint) > max_length:
        raise InvalidRateLimitConfig(
            message=_("Endpoint too long. Maximum length is %(max)s characters") % {
                'max': max_length
            },
            config_field=field_name,
            config_value=endpoint,
            validation_error=_("Endpoint too long")
        )
    
    return endpoint


def validate_user_agent(user_agent, field_name=None):
    """
    Validate user agent string.
    
    Args:
        user_agent: The user agent to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated user agent
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    if not user_agent:
        raise InvalidRateLimitConfig(
            message=_("User agent cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
    )
    
    # Length validation
    max_length = getattr(settings, 'RATE_LIMIT_MAX_USER_AGENT_LENGTH', 500)
    if len(user_agent) > max_length:
        raise InvalidRateLimitConfig(
            message=_("User agent too long. Maximum length is %(max)s characters") % {
                'max': max_length
            },
            config_field=field_name,
            config_value=user_agent[:50] + "...",
            validation_error=_("User agent too long")
        )
    
    return user_agent


def validate_abuse_type(abuse_type, field_name=None):
    """
    Validate abuse type.
    
    Args:
        abuse_type: The abuse type to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated abuse type
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    valid_types = ['rate_limit', 'spam', 'fraud', 'malicious', 'bot', 'other']
    
    if abuse_type not in valid_types:
        raise InvalidRateLimitConfig(
            message=_("Invalid abuse type '%(type)s'. Must be one of: %(types)s") % {
                'type': abuse_type,
                'types': ', '.join(valid_types)
            },
            config_field=field_name,
            config_value=abuse_type,
            validation_error=_("Invalid abuse type")
        )
    
    return abuse_type


def validate_severity(severity, field_name=None):
    """
    Validate severity level (1-5).
    
    Args:
        severity: The severity to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        int: Validated severity
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    try:
        severity = int(severity)
    except (ValueError, TypeError):
        raise InvalidRateLimitConfig(
            message=_("Severity must be a number"),
            config_field=field_name,
            config_value=severity,
            validation_error=_("Must be an integer")
        )
    
    if severity < 1 or severity > 5:
        raise InvalidRateLimitConfig(
            message=_("Severity must be between 1 and 5"),
            config_field=field_name,
            config_value=severity,
            validation_error=_("Invalid severity range")
        )
    
    return severity


def validate_multiplier(multiplier, field_name=None):
    """
    Validate rate limit multiplier.
    
    Args:
        multiplier: The multiplier to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        float: Validated multiplier
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    if multiplier is None:
        raise InvalidRateLimitConfig(
            message=_("Multiplier cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
    )
    
    try:
        multiplier = float(multiplier)
    except (ValueError, TypeError):
        raise InvalidRateLimitConfig(
            message=_("Multiplier must be a number"),
            config_field=field_name,
            config_value=multiplier,
            validation_error=_("Must be a number")
        )
    
    if multiplier <= 0:
        raise InvalidRateLimitConfig(
            message=_("Multiplier must be greater than 0"),
            config_field=field_name,
            config_value=multiplier,
            validation_error=_("Must be positive")
    )
    
    # Check for reasonable maximum multiplier
    max_multiplier = getattr(settings, 'RATE_LIMIT_MAX_MULTIPLIER', 100.0)
    if multiplier > max_multiplier:
        raise InvalidRateLimitConfig(
            message=_("Multiplier cannot exceed %(max)s") % {'max': max_multiplier},
            config_field=field_name,
            config_value=multiplier,
            validation_error=_("Multiplier too large")
        )
    
    return multiplier


def validate_json_list(json_list, field_name=None, max_items=None):
    """
    Validate JSON list field.
    
    Args:
        json_list: The JSON list to validate
        field_name: Name of the field being validated (for error messages)
        max_items: Maximum number of items allowed
        
    Returns:
        list: Validated list
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    import json
    
    if json_list is None:
        return []
    
    if isinstance(json_list, str):
        try:
            json_list = json.loads(json_list)
        except json.JSONDecodeError:
            raise InvalidRateLimitConfig(
                message=_("Invalid JSON format"),
                config_field=field_name,
                config_value=json_list[:50] + "...",
                validation_error=_("Invalid JSON")
            )
    
    if not isinstance(json_list, list):
        raise InvalidRateLimitConfig(
            message=_("Value must be a list"),
            config_field=field_name,
            config_value=str(type(json_list)),
            validation_error=_("Must be a list")
        )
    
    if max_items is not None and len(json_list) > max_items:
        raise InvalidRateLimitConfig(
            message=_("List cannot contain more than %(max)s items") % {
                'max': max_items
            },
            config_field=field_name,
            config_value=f"list with {len(json_list)} items",
            validation_error=_("List too large")
        )
    
    return json_list


def validate_regex_pattern(pattern, field_name=None):
    """
    Validate regex pattern.
    
    Args:
        pattern: The regex pattern to validate
        field_name: Name of the field being validated (for error messages)
        
    Returns:
        str: Validated regex pattern
        
    Raises:
        ValidationError: If the value is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    if not pattern:
        raise InvalidRateLimitConfig(
            message=_("Pattern cannot be empty"),
            config_field=field_name,
            validation_error=_("Value is required")
    )
    
    try:
        re.compile(pattern)
    except re.error as e:
        raise InvalidRateLimitConfig(
            message=_("Invalid regex pattern: %(error)s") % {'error': str(e)},
            config_field=field_name,
            config_value=pattern,
            validation_error=_("Invalid regex")
        )
    
    return pattern


# Composite validators for complex validation scenarios
def validate_rate_limit_config(config_data):
    """
    Validate complete rate limit configuration.
    
    Args:
        config_data: Dictionary containing configuration data
        
    Returns:
        dict: Validated configuration data
        
    Raises:
        ValidationError: If the configuration is invalid
        InvalidRateLimitConfig: If the configuration is invalid
    """
    validated = {}
    
    # Validate required fields
    if 'rate_limit_type' in config_data:
        validated['rate_limit_type'] = validate_rate_limit_type(
            config_data['rate_limit_type'], 'rate_limit_type'
        )
    
    if 'requests_per_unit' in config_data:
        validated['requests_per_unit'] = validate_rate_limit_value(
            config_data['requests_per_unit'], 'requests_per_unit'
        )
    
    if 'time_unit' in config_data:
        validated['time_unit'] = validate_time_unit(
            config_data['time_unit'], 'time_unit'
        )
    
    if 'time_value' in config_data:
        validated['time_value'] = validate_window_seconds(
            config_data['time_value'], 'time_value'
        )
    
    # Validate optional fields
    if 'ip_address' in config_data and config_data['ip_address']:
        validated['ip_address'] = validate_ip_address(
            config_data['ip_address'], 'ip_address'
        )
    
    if 'endpoint' in config_data and config_data['endpoint']:
        validated['endpoint'] = validate_endpoint(
            config_data['endpoint'], 'endpoint'
        )
    
    if 'whitelist' in config_data:
        validated['whitelist'] = validate_json_list(
            config_data['whitelist'], 'whitelist', max_items=100
        )
    
    if 'blacklist' in config_data:
        validated['blacklist'] = validate_json_list(
            config_data['blacklist'], 'blacklist', max_items=100
        )
    
    if 'bypass_keys' in config_data:
        validated['bypass_keys'] = validate_json_list(
            config_data['bypass_keys'], 'bypass_keys', max_items=50
        )
    
    # Cross-field validation
    if 'rate_limit_type' in validated and 'requests_per_unit' in validated:
        limit_type = validated['rate_limit_type']
        requests = validated['requests_per_unit']
        
        # Special validation for different limit types
        if limit_type == 'global' and requests < 1000:
            raise InvalidRateLimitConfig(
                message=_("Global rate limits should have at least 1000 requests per unit"),
                config_field='requests_per_unit',
                config_value=requests,
                validation_error=_("Global limit too low")
            )
        elif limit_type == 'user' and requests < 10:
            raise InvalidRateLimitConfig(
                message=_("User rate limits should have at least 10 requests per unit"),
                config_field='requests_per_unit',
                config_value=requests,
                validation_error=_("User limit too low")
            )
    
    return validated
