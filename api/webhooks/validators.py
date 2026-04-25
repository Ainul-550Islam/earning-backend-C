"""Webhooks Validators Module

This module contains validation functions for the webhooks system,
including field validation, configuration validation, and security checks.
"""

import re
import json
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlparse

from .constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, InboundSource, ErrorType
)


def validate_webhook_url(url):
    """
    Validate webhook URL format and accessibility.
    
    Args:
        url (str): Webhook URL to validate
        
    Returns:
        str: Validated URL
        
    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError(_('Webhook URL is required'))
    
    try:
        parsed = urlparse(url)
        
        # Check if URL has a scheme
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(
                _('Webhook URL must include scheme and domain (e.g., https://example.com/webhook)')
            )
        
        # Check if scheme is HTTP or HTTPS
        if parsed.scheme not in ['http', 'https']:
            raise ValidationError(
                _('Webhook URL must use HTTP or HTTPS scheme')
            )
        
        # Check if URL is too long
        if len(url) > 2048:
            raise ValidationError(
                _('Webhook URL must be less than 2048 characters')
            )
        
        return url
        
    except Exception as e:
        raise ValidationError(
            _('Invalid webhook URL format: {}').format(str(e))
        )


def validate_secret(secret):
    """
    Validate webhook secret strength and format.
    
    Args:
        secret (str): Webhook secret to validate
        
    Returns:
        str: Validated secret
        
    Raises:
        ValidationError: If secret is invalid
    """
    if not secret:
        raise ValidationError(_('Webhook secret is required'))
    
    # Check minimum length
    if len(secret) < 32:
        raise ValidationError(
                _('Webhook secret must be at least 32 characters long')
            )
    
    # Check maximum length
    if len(secret) > 256:
        raise ValidationError(
                _('Webhook secret must be less than 256 characters long')
            )
    
    # Check for common weak patterns
    weak_patterns = [
        r'password',
        r'123456',
        r'qwerty',
        r'abc123',
        r'admin',
        r'root',
        r'test',
        r'webhook',
        r'secret',
        r'key',
    ]
    
    for pattern in weak_patterns:
        if re.search(pattern, secret.lower()):
            raise ValidationError(
                _('Webhook secret contains common weak patterns')
            )
    
    # Check for character variety
    has_upper = any(c.isupper() for c in secret)
    has_lower = any(c.islower() for c in secret)
    has_digit = any(c.isdigit() for c in secret)
    has_special = any(c in '!@#$%^&*()_+-=[]{}|;:<>?,./' for c in secret)
    
    if not (has_upper and has_lower and has_digit and has_special):
        raise ValidationError(
                _('Webhook secret must contain uppercase, lowercase, digits, and special characters')
            )
    
    return secret


def validate_event_type(event_type):
    """
    Validate event type format and ensure it's from allowed list.
    
    Args:
        event_type (str): Event type to validate
        
    Returns:
        str: Validated event type
        
    Raises:
        ValidationError: If event type is invalid
    """
    if not event_type:
        raise ValidationError(_('Event type is required'))
    
    # Check event type format
    if not re.match(r'^[a-z0-9_]+\.[a-z0-9_]+$', event_type):
        raise ValidationError(
                _('Event type must be in format: domain.action (e.g., user.created)')
            )
    
    # Check against allowed event types
    from .constants import EventType
    allowed_events = [choice[0] for choice in EventType.all_choices()]
    
    if event_type not in allowed_events:
        raise ValidationError(
                _('Event type "{}" is not allowed').format(event_type)
            )
    
    return event_type


def validate_filter_config(config):
    """
    Validate webhook filter configuration.
    
    Args:
        config (dict): Filter configuration to validate
        
    Returns:
        dict: Validated configuration
        
    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError(_('Filter configuration must be a JSON object'))
    
    # Validate filter rules
    for key, value in config.items():
        if key == 'field_path':
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(
                        _('Filter field path cannot be empty')
                    )
            
        elif key == 'operator':
            allowed_operators = [choice[0] for choice in FilterOperator.CHOICES]
            if value not in allowed_operators:
                raise ValidationError(
                        _('Filter operator "{}" is not allowed').format(value)
                    )
            
        elif key == 'value':
            if value is None:
                raise ValidationError(
                        _('Filter value cannot be null')
                    )
    
    return config


def validate_payload_template(template):
    """
    Validate webhook payload template syntax.
    
    Args:
        template (str): Jinja2 template to validate
        
    Returns:
        str: Validated template
        
    Raises:
        ValidationError: If template is invalid
    """
    if not isinstance(template, str):
        raise ValidationError(_('Payload template must be a string'))
    
    if not template.strip():
        raise ValidationError(_('Payload template cannot be empty'))
    
    # Basic Jinja2 syntax validation
    try:
        from jinja2 import Environment, TemplateSyntaxError
        env = Environment()
        env.from_string(template)
    except TemplateSyntaxError as e:
        raise ValidationError(
                _('Invalid Jinja2 template syntax: {}').format(str(e))
            )
    except ImportError:
        raise ValidationError(
                _('Jinja2 library is not available for template validation')
            )
    
    return template


def validate_transform_rules(rules):
    """
    Validate webhook transformation rules.
    
    Args:
        rules (dict): Transformation rules to validate
        
    Returns:
        dict: Validated rules
        
    Raises:
        ValidationError: If rules are invalid
    """
    if not isinstance(rules, dict):
        raise ValidationError(_('Transform rules must be a JSON object'))
    
    # Validate each rule
    for rule_name, rule_config in rules.items():
        if not isinstance(rule_config, dict):
            raise ValidationError(
                        _('Transform rule "{}" must be a JSON object').format(rule_name)
                    )
        
        # Validate rule type
        rule_type = rule_config.get('type')
        if not rule_type:
            raise ValidationError(
                        _('Transform rule "{}" must have a type').format(rule_name)
                    )
        
        # Validate supported rule types
        supported_types = [
            'add_field', 'remove_field', 'rename_field',
            'map_value', 'format_date', 'calculate_field'
        ]
        
        if rule_type not in supported_types:
            raise ValidationError(
                        _('Transform rule type "{}" is not supported').format(rule_type)
                    )
        
        # Validate required fields based on type
        if rule_type == 'add_field':
            if 'field_name' not in rule_config:
                raise ValidationError(
                            _('Add field rule must have field_name')
                        )
        elif rule_type == 'remove_field':
            if 'path' not in rule_config:
                raise ValidationError(
                            _('Remove field rule must have path')
                        )
        elif rule_type == 'rename_field':
            if 'old_name' not in rule_config or 'new_name' not in rule_config:
                raise ValidationError(
                            _('Rename field rule must have old_name and new_name')
                        )
    
    return rules


def validate_rate_limit_config(config):
    """
    Validate rate limiting configuration.
    
    Args:
        config (dict): Rate limit configuration to validate
        
    Returns:
        dict: Validated configuration
        
    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError(_('Rate limit configuration must be a JSON object'))
    
    # Validate required fields
    if 'window_seconds' not in config:
        raise ValidationError(_('Rate limit configuration must include window_seconds'))
    
    if 'max_requests' not in config:
        raise ValidationError(_('Rate limit configuration must include max_requests'))
    
    # Validate values
    window_seconds = config['window_seconds']
    max_requests = config['max_requests']
    
    if not isinstance(window_seconds, int) or window_seconds < 60:
        raise ValidationError(_('Rate limit window must be at least 60 seconds'))
    
    if not isinstance(max_requests, int) or max_requests < 1:
        raise ValidationError(_('Rate limit max requests must be at least 1'))
    
    # Validate reasonable limits
    if max_requests > 10000:
        raise ValidationError(_('Rate limit max requests cannot exceed 10000'))
    
    return config


def validate_ip_whitelist(whitelist):
    """
    Validate IP whitelist configuration.
    
    Args:
        whitelist (list): IP whitelist to validate
        
    Returns:
        list: Validated whitelist
        
    Raises:
        ValidationError: If whitelist is invalid
    """
    if not isinstance(whitelist, list):
        raise ValidationError(_('IP whitelist must be a list'))
    
    # Validate each IP address
    for ip in whitelist:
        if not isinstance(ip, str) or not ip.strip():
            raise ValidationError(_('IP addresses must be non-empty strings'))
        
        # Basic IP validation
        try:
            from ipaddress import ip_address
            ip_obj = ip_address(ip)
        except ValueError:
            raise ValidationError(
                        _('Invalid IP address format: {}').format(ip)
                    )
    
    return whitelist


def validate_headers(headers):
    """
    Validate webhook headers configuration.
    
    Args:
        headers (dict): Headers to validate
        
    Returns:
        dict: Validated headers
        
    Raises:
        ValidationError: If headers are invalid
    """
    if not isinstance(headers, dict):
        raise ValidationError(_('Headers must be a JSON object'))
    
    # Validate header names and values
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValidationError(
                        _('Header "{}" must be a string').format(key)
                    )
        
        # Check for common security headers that shouldn't be overridden
        restricted_headers = [
            'host', 'authorization', 'content-type',
            'content-length', 'user-agent'
        ]
        
        if key.lower() in restricted_headers:
            raise ValidationError(
                        _('Header "{}" is restricted and cannot be overridden').format(key)
                    )
    
    return headers


def validate_batch_size(size):
    """
    Validate webhook batch size.
    
    Args:
        size (int): Batch size to validate
        
    Returns:
        int: Validated batch size
        
    Raises:
        ValidationError: If size is invalid
    """
    if not isinstance(size, int):
        raise ValidationError(_('Batch size must be an integer'))
    
    if size < 1:
        raise ValidationError(_('Batch size must be at least 1'))
    
    if size > 1000:
        raise ValidationError(_('Batch size cannot exceed 1000'))
    
    return size


def validate_timeout(timeout):
    """
    Validate webhook timeout configuration.
    
    Args:
        timeout (int): Timeout in seconds
        
    Returns:
        int: Validated timeout
        
    Raises:
        ValidationError: If timeout is invalid
    """
    if not isinstance(timeout, int):
        raise ValidationError(_('Timeout must be an integer'))
    
    if timeout < 1:
        raise ValidationError(_('Timeout must be at least 1 second'))
    
    if timeout > 300:
        raise ValidationError(_('Timeout cannot exceed 300 seconds'))
    
    return timeout


def validate_max_retries(max_retries):
    """
    Validate webhook maximum retry attempts.
    
    Args:
        max_retries (int): Maximum retry attempts
        
    Returns:
        int: Validated max retries
        
    Raises:
        ValidationError: If max retries is invalid
    """
    if not isinstance(max_retries, int):
        raise ValidationError(_('Max retries must be an integer'))
    
    if max_retries < 0:
        raise ValidationError(_('Max retries must be at least 0'))
    
    if max_retries > 10:
        raise ValidationError(_('Max retries cannot exceed 10'))
    
    return max_retries
