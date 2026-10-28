"""
Validators for alerts app - Advanced validation utilities
"""
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, EmailValidator, URLValidator
import re
import json
try:
    from croniter import croniter
except ImportError:
    croniter = None

logger = logging.getLogger(__name__)


def validate_alert_rule_condition(condition: Dict[str, Any]) -> Dict[str, Any]:
    """Validate alert rule condition"""
    errors = []
    warnings = []
    
    try:
        # Check required fields
        if not isinstance(condition, dict):
            errors.append("Condition must be a dictionary")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Validate field name
        field = condition.get('field')
        if not field:
            errors.append("Field name is required")
        elif not isinstance(field, str):
            errors.append("Field name must be a string")
        elif not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field):
            errors.append("Field name must be a valid identifier")
        
        # Validate operator
        operator = condition.get('operator')
        valid_operators = ['equals', 'not_equals', 'greater_than', 'less_than', 
                          'greater_equal', 'less_equal', 'contains', 'not_contains',
                          'in', 'not_in', 'regex', 'is_null', 'is_not_null']
        
        if not operator:
            errors.append("Operator is required")
        elif operator not in valid_operators:
            errors.append(f"Invalid operator. Must be one of: {', '.join(valid_operators)}")
        
        # Validate value
        value = condition.get('value')
        if value is None and operator not in ['is_null', 'is_not_null']:
            errors.append("Value is required for this operator")
        
        # Validate logical operators
        logical_op = condition.get('logical_operator')
        if logical_op and logical_op not in ['AND', 'OR']:
            errors.append("Logical operator must be 'AND' or 'OR'")
        
        # Validate nested conditions
        nested_conditions = condition.get('conditions')
        if nested_conditions:
            if not isinstance(nested_conditions, list):
                errors.append("Nested conditions must be a list")
            else:
                for i, nested in enumerate(nested_conditions):
                    nested_result = validate_alert_rule_condition(nested)
                    if not nested_result['valid']:
                        errors.extend([f"Condition {i}: {err}" for err in nested_result['errors']])
        
        # Add warnings for potential issues
        if operator == 'regex' and value:
            try:
                re.compile(value)
            except re.error as e:
                errors.append(f"Invalid regex pattern: {e}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating alert rule condition: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def validate_threshold_value(value: Any, threshold_type: str = 'numeric') -> Dict[str, Any]:
    """Validate threshold value"""
    errors = []
    warnings = []
    
    try:
        if threshold_type == 'numeric':
            # Check if value is numeric
            if not isinstance(value, (int, float)):
                errors.append("Threshold value must be numeric")
            else:
                # Check for reasonable ranges
                if value < 0:
                    warnings.append("Negative threshold values may not be meaningful")
                elif value > 1000000:
                    warnings.append("Very large threshold value detected")
        
        elif threshold_type == 'percentage':
            # Check if value is percentage
            if not isinstance(value, (int, float)):
                errors.append("Percentage threshold must be numeric")
            elif value < 0 or value > 100:
                errors.append("Percentage must be between 0 and 100")
        
        elif threshold_type == 'time':
            # Check if value is time in seconds
            if not isinstance(value, (int, float)):
                errors.append("Time threshold must be numeric (seconds)")
            elif value < 0:
                errors.append("Time threshold cannot be negative")
            elif value > 86400:  # 24 hours
                warnings.append("Time threshold exceeds 24 hours")
        
        elif threshold_type == 'count':
            # Check if value is count
            if not isinstance(value, int):
                errors.append("Count threshold must be an integer")
            elif value < 0:
                errors.append("Count threshold cannot be negative")
            elif value > 10000:
                warnings.append("Very large count threshold detected")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'normalized_value': float(value) if isinstance(value, (int, float)) else value
        }
        
    except Exception as e:
        logger.error(f"Error validating threshold value: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def validate_channel_config(config: Dict[str, Any], channel_type: str) -> Dict[str, Any]:
    """Validate notification channel configuration"""
    errors = []
    warnings = []
    
    try:
        # Common validations
        if not isinstance(config, dict):
            errors.append("Channel config must be a dictionary")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Check enabled status
        enabled = config.get('enabled', True)
        if not isinstance(enabled, bool):
            errors.append("Enabled status must be boolean")
        
        # Channel-specific validations
        if channel_type == 'email':
            email_errors = _validate_email_config(config)
            errors.extend(email_errors)
        
        elif channel_type == 'sms':
            sms_errors = _validate_sms_config(config)
            errors.extend(sms_errors)
        
        elif channel_type == 'slack':
            slack_errors = _validate_slack_config(config)
            errors.extend(slack_errors)
        
        elif channel_type == 'webhook':
            webhook_errors = _validate_webhook_config(config)
            errors.extend(webhook_errors)
        
        else:
            errors.append(f"Unknown channel type: {channel_type}")
        
        # Check rate limiting
        rate_limit = config.get('rate_limit')
        if rate_limit is not None:
            if not isinstance(rate_limit, int) or rate_limit <= 0:
                errors.append("Rate limit must be a positive integer")
            elif rate_limit > 10000:
                warnings.append("Very high rate limit may cause issues")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating channel config: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def _validate_email_config(config: Dict[str, Any]) -> List[str]:
    """Validate email channel configuration"""
    errors = []
    
    # SMTP settings
    smtp_host = config.get('smtp_host')
    if not smtp_host:
        errors.append("SMTP host is required")
    elif not isinstance(smtp_host, str):
        errors.append("SMTP host must be a string")
    
    smtp_port = config.get('smtp_port')
    if not smtp_port:
        errors.append("SMTP port is required")
    elif not isinstance(smtp_port, int) or not (1 <= smtp_port <= 65535):
        errors.append("SMTP port must be an integer between 1 and 65535")
    
    # Authentication
    smtp_username = config.get('smtp_username')
    smtp_password = config.get('smtp_password')
    
    if smtp_username and not isinstance(smtp_username, str):
        errors.append("SMTP username must be a string")
    
    if smtp_password and not isinstance(smtp_password, str):
        errors.append("SMTP password must be a string")
    
    # From email
    from_email = config.get('from_email')
    if from_email:
        try:
            EmailValidator()(from_email)
        except ValidationError:
            errors.append("Invalid from email address")
    
    return errors


def _validate_sms_config(config: Dict[str, Any]) -> List[str]:
    """Validate SMS channel configuration"""
    errors = []
    
    # API settings
    api_key = config.get('api_key')
    if not api_key:
        errors.append("SMS API key is required")
    elif not isinstance(api_key, str):
        errors.append("SMS API key must be a string")
    
    api_url = config.get('api_url')
    if not api_url:
        errors.append("SMS API URL is required")
    else:
        try:
            URLValidator()(api_url)
        except ValidationError:
            errors.append("Invalid SMS API URL")
    
    # From number
    from_number = config.get('from_number')
    if from_number and not isinstance(from_number, str):
        errors.append("From number must be a string")
    
    return errors


def _validate_slack_config(config: Dict[str, Any]) -> List[str]:
    """Validate Slack channel configuration"""
    errors = []
    
    # Webhook URL
    webhook_url = config.get('webhook_url')
    if not webhook_url:
        errors.append("Slack webhook URL is required")
    else:
        try:
            URLValidator()(webhook_url)
            if not webhook_url.startswith('https://hooks.slack.com'):
                errors.append("Invalid Slack webhook URL")
        except ValidationError:
            errors.append("Invalid Slack webhook URL")
    
    # Channel
    channel = config.get('channel')
    if channel and not isinstance(channel, str):
        errors.append("Slack channel must be a string")
    elif channel and not channel.startswith('#'):
        errors.append("Slack channel must start with #")
    
    return errors


def _validate_webhook_config(config: Dict[str, Any]) -> List[str]:
    """Validate webhook channel configuration"""
    errors = []
    
    # Webhook URL
    webhook_url = config.get('webhook_url')
    if not webhook_url:
        errors.append("Webhook URL is required")
    else:
        try:
            URLValidator()(webhook_url)
        except ValidationError:
            errors.append("Invalid webhook URL")
    
    # Method
    method = config.get('method', 'POST')
    valid_methods = ['GET', 'POST', 'PUT', 'PATCH']
    if method not in valid_methods:
        errors.append(f"Webhook method must be one of: {', '.join(valid_methods)}")
    
    # Headers
    headers = config.get('headers')
    if headers and not isinstance(headers, dict):
        errors.append("Webhook headers must be a dictionary")
    
    return errors


def validate_cron_expression(cron_expression: str) -> Dict[str, Any]:
    """Validate cron expression"""
    errors = []
    warnings = []
    
    try:
        if not isinstance(cron_expression, str):
            errors.append("Cron expression must be a string")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Try to parse with croniter
        try:
            croniter(cron_expression)
        except (ValueError, AttributeError) as e:
            errors.append(f"Invalid cron expression: {str(e)}")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Check for common patterns
        if cron_expression == '* * * * *':
            warnings.append("Cron expression runs every minute - ensure this is intended")
        
        if '@reboot' in cron_expression:
            warnings.append("@reboot is not supported in this scheduler")
        
        if '@yearly' in cron_expression or '@annually' in cron_expression:
            warnings.append("Consider using '0 0 1 1 *' instead of @yearly")
        
        # Validate field ranges
        fields = cron_expression.split()
        if len(fields) != 5:
            errors.append("Cron expression must have 5 fields: minute hour day month weekday")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'next_runs': _get_next_cron_runs(cron_expression, 5) if len(errors) == 0 else []
        }
        
    except Exception as e:
        logger.error(f"Error validating cron expression: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def _get_next_cron_runs(cron_expression: str, count: int = 5) -> List[str]:
    """Get next run times for cron expression"""
    try:
        cron = croniter(cron_expression)
        next_runs = []
        
        for _ in range(count):
            next_run = cron.get_next(datetime)
            next_runs.append(next_run.isoformat())
        
        return next_runs
    except Exception:
        return []


def _allow_private_webhook_targets() -> bool:
    from django.conf import settings
    return bool(getattr(settings, 'ALERTS_ALLOW_PRIVATE_WEBHOOK_URLS', False))


def _unsafe_webhook_host_reason(hostname):
    """Return why ``hostname`` is not a safe outbound target (SSRF guard), else None."""
    import ipaddress
    import socket
    if not hostname:
        return "Webhook URL has no host"
    host = hostname.strip('[]').lower().rstrip('.')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        return "Webhook URL points at a local/internal host"
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except (socket.gaierror, UnicodeError):
            return None  # cannot resolve now; delivery re-validates right before the request
        addresses = set()
        for info in infos:
            try:
                addresses.add(ipaddress.ip_address(info[4][0].split('%')[0]))
            except ValueError:
                continue
    for ip in addresses:
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:  # private, loopback, link-local (cloud metadata), reserved, ...
            return "Webhook URL resolves to a non-public address"
    return None


def validate_webhook_url(url: str, methods: List[str] = None) -> Dict[str, Any]:
    """Validate webhook URL configuration"""
    errors = []
    warnings = []
    
    try:
        if not isinstance(url, str):
            errors.append("Webhook URL must be a string")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Basic URL validation
        try:
            URLValidator()(url)
        except ValidationError as e:
            errors.append(f"Invalid URL: {str(e)}")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # HTTPS recommendation
        if not url.startswith('https://'):
            warnings.append("HTTPS is recommended for webhook URLs")
        
        # Check for localhost
        if 'localhost' in url or '127.0.0.1' in url:
            warnings.append("Localhost URLs may not be accessible from external services")

        # SSRF guard: http(s) only, and no private / loopback / link-local / metadata targets
        # unless the project opts in with ALERTS_ALLOW_PRIVATE_WEBHOOK_URLS = True.
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            errors.append("Webhook URL must use http or https")
        elif not _allow_private_webhook_targets():
            reason = _unsafe_webhook_host_reason(parsed.hostname)
            if reason:
                errors.append(reason)
        
        # Validate methods if provided
        if methods:
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            for method in methods:
                if method not in valid_methods:
                    errors.append(f"Invalid HTTP method: {method}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'url_info': {
                'scheme': url.split('://')[0] if '://' in url else None,
                'domain': url.split('://')[1].split('/')[0] if '://' in url else None,
                'is_https': url.startswith('https://'),
                'is_localhost': 'localhost' in url or '127.0.0.1' in url
            }
        }
        
    except Exception as e:
        logger.error(f"Error validating webhook URL: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def validate_integration_config(config: Dict[str, Any], integration_type: str) -> Dict[str, Any]:
    """Validate integration configuration"""
    errors = []
    warnings = []
    
    try:
        if not isinstance(config, dict):
            errors.append("Integration config must be a dictionary")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Common validations
        name = config.get('name')
        if not name:
            errors.append("Integration name is required")
        elif not isinstance(name, str):
            errors.append("Integration name must be a string")
        
        enabled = config.get('enabled', True)
        if not isinstance(enabled, bool):
            errors.append("Enabled status must be boolean")
        
        # Type-specific validations
        if integration_type == 'api':
            api_errors = _validate_api_integration_config(config)
            errors.extend(api_errors)
        
        elif integration_type == 'database':
            db_errors = _validate_database_integration_config(config)
            errors.extend(db_errors)
        
        elif integration_type == 'webhook':
            webhook_errors = _validate_webhook_integration_config(config)
            errors.extend(webhook_errors)
        
        else:
            errors.append(f"Unknown integration type: {integration_type}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating integration config: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def _validate_api_integration_config(config: Dict[str, Any]) -> List[str]:
    """Validate API integration configuration"""
    errors = []
    
    # Base URL
    base_url = config.get('base_url')
    if not base_url:
        errors.append("Base URL is required for API integration")
    else:
        try:
            URLValidator()(base_url)
        except ValidationError:
            errors.append("Invalid base URL")
    
    # Authentication
    auth_type = config.get('auth_type')
    if auth_type:
        valid_auth_types = ['none', 'basic', 'bearer', 'api_key']
        if auth_type not in valid_auth_types:
            errors.append(f"Invalid auth type. Must be one of: {', '.join(valid_auth_types)}")
        
        if auth_type in ['basic', 'bearer', 'api_key']:
            if not config.get('auth_token'):
                errors.append(f"Auth token is required for {auth_type} authentication")
    
    # Timeout
    timeout = config.get('timeout')
    if timeout is not None:
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            errors.append("Timeout must be a positive number")
        elif timeout > 300:
            errors.append("Timeout should not exceed 300 seconds")
    
    return errors


def _validate_database_integration_config(config: Dict[str, Any]) -> List[str]:
    """Validate database integration configuration"""
    errors = []
    
    # Database type
    db_type = config.get('db_type')
    if not db_type:
        errors.append("Database type is required")
    elif db_type not in ['postgresql', 'mysql', 'sqlite', 'mongodb']:
        errors.append("Database type must be one of: postgresql, mysql, sqlite, mongodb")
    
    # Connection string
    connection_string = config.get('connection_string')
    if not connection_string:
        errors.append("Connection string is required")
    elif not isinstance(connection_string, str):
        errors.append("Connection string must be a string")
    
    return errors


def _validate_webhook_integration_config(config: Dict[str, Any]) -> List[str]:
    """Validate webhook integration configuration"""
    errors = []
    
    # Webhook URL
    webhook_url = config.get('webhook_url')
    if not webhook_url:
        errors.append("Webhook URL is required")
    else:
        try:
            URLValidator()(webhook_url)
        except ValidationError:
            errors.append("Invalid webhook URL")
    
    # Secret
    secret = config.get('secret')
    if secret and not isinstance(secret, str):
        errors.append("Webhook secret must be a string")
    elif secret and len(secret) < 16:
        errors.append("Webhook secret should be at least 16 characters")
    
    return errors


def validate_alert_severity(severity: str) -> Dict[str, Any]:
    """Validate alert severity"""
    errors = []
    warnings = []
    
    try:
        valid_severities = ['low', 'medium', 'high', 'critical']
        
        if not isinstance(severity, str):
            errors.append("Severity must be a string")
        elif severity.lower() not in valid_severities:
            errors.append(f"Severity must be one of: {', '.join(valid_severities)}")
        
        # Add warnings
        if severity.lower() == 'low':
            warnings.append("Low severity alerts may be filtered out by some systems")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'normalized_severity': severity.lower() if isinstance(severity, str) else severity
        }
        
    except Exception as e:
        logger.error(f"Error validating alert severity: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def validate_time_window(time_window: Union[str, int], unit: str = 'minutes') -> Dict[str, Any]:
    """Validate time window"""
    errors = []
    warnings = []
    
    try:
        # Convert to minutes
        if isinstance(time_window, str):
            if time_window.isdigit():
                minutes = int(time_window)
            else:
                # Try to parse time strings like "1h", "30m", "2d"
                import re
                match = re.match(r'^(\d+)([smhd])$', time_window.lower())
                if not match:
                    errors.append("Invalid time window format. Use format like '30m', '1h', '2d'")
                    return {'valid': False, 'errors': errors, 'warnings': warnings}
                
                value, unit_char = match.groups()
                value = int(value)
                
                if unit_char == 's':
                    minutes = value / 60
                elif unit_char == 'm':
                    minutes = value
                elif unit_char == 'h':
                    minutes = value * 60
                elif unit_char == 'd':
                    minutes = value * 24 * 60
        else:
            minutes = int(time_window)
        
        # Validate range
        if minutes <= 0:
            errors.append("Time window must be positive")
        elif minutes > 525600:  # 1 year
            errors.append("Time window cannot exceed 1 year")
        elif minutes > 1440:  # 24 hours
            warnings.append("Time window exceeds 24 hours")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'minutes': minutes,
            'human_readable': _format_duration(minutes)
        }
        
    except Exception as e:
        logger.error(f"Error validating time window: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


def _format_duration(minutes: int) -> str:
    """Format duration in human readable format"""
    if minutes < 60:
        return f"{minutes} minutes"
    elif minutes < 1440:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m" if mins > 0 else f"{hours} hours"
    else:
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        return f"{days}d {hours}h" if hours > 0 else f"{days} days"


def validate_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JSON schema"""
    errors = []
    warnings = []
    
    try:
        if not isinstance(schema, dict):
            errors.append("Schema must be a dictionary")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Check required fields
        if 'type' not in schema:
            errors.append("Schema must have a 'type' field")
        
        # Validate type
        schema_type = schema.get('type')
        valid_types = ['string', 'number', 'integer', 'boolean', 'array', 'object', 'null']
        if schema_type and schema_type not in valid_types:
            errors.append(f"Invalid schema type. Must be one of: {', '.join(valid_types)}")
        
        # Check for common issues
        if schema_type == 'object' and 'properties' not in schema:
            warnings.append("Object type should have 'properties' field")
        
        if schema_type == 'array' and 'items' not in schema:
            warnings.append("Array type should have 'items' field")
        
        # Validate nested schemas
        for key, value in schema.items():
            if isinstance(value, dict) and 'type' in value:
                nested_result = validate_json_schema(value)
                if not nested_result['valid']:
                    errors.extend([f"{key}: {err}" for err in nested_result['errors']])
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating JSON schema: {e}")
        return {
            'valid': False,
            'errors': ['Validation error'],
            'warnings': warnings
        }


# Validation utility functions
def batch_validate(items: List[Dict[str, Any]], validator_func: callable) -> Dict[str, Any]:
    """Batch validate multiple items"""
    results = []
    total_errors = 0
    total_warnings = 0
    
    for i, item in enumerate(items):
        result = validator_func(item)
        result['index'] = i
        results.append(result)
        
        total_errors += len(result.get('errors', []))
        total_warnings += len(result.get('warnings', []))
    
    return {
        'total_items': len(items),
        'valid_items': len([r for r in results if r['valid']]),
        'invalid_items': len([r for r in results if not r['valid']]),
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'results': results
    }


def validate_and_sanitize(value: Any, validation_func: callable) -> Dict[str, Any]:
    """Validate and sanitize a value"""
    validation_result = validation_func(value)
    
    if validation_result['valid']:
        sanitized_value = validation_result.get('normalized_value', value)
        return {
            'valid': True,
            'sanitized_value': sanitized_value,
            'validation_result': validation_result
        }
    else:
        return {
            'valid': False,
            'sanitized_value': None,
            'validation_result': validation_result
        }
