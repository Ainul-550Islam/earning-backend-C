# api/rate_limit/data_validator.py
"""
Data validation system for rate limit module.

Provides comprehensive validation rules and schemas for rate limiting data.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator, EmailValidator
from django.conf import settings
import json
import ipaddress

logger = logging.getLogger(__name__)


class ValidationRule:
    """Represents a validation rule."""
    
    def __init__(self, name: str, field: str, validator: Callable,
                 message: str = None, code: str = None, required: bool = True):
        self.name = name
        self.field = field
        self.validator = validator
        self.message = message or f"Invalid {field}"
        self.code = code or f"invalid_{field}"
        self.required = required
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate a value against the rule.
        
        Args:
            value: Value to validate
            context: Validation context
            
        Returns:
            Validation result
        """
        try:
            if value is None:
                if self.required:
                    return {
                        'valid': False,
                        'error': f"{self.field} is required",
                        'code': f"{self.code}_required"
                    }
                else:
                    return {'valid': True}
            
            result = self.validator(value, context or {})
            
            if isinstance(result, bool):
                return {'valid': result}
            elif isinstance(result, dict):
                return result
            else:
                return {'valid': bool(result)}
                
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'code': self.code
            }


class ValidationSchema:
    """Represents a validation schema."""
    
    def __init__(self, name: str, rules: List[ValidationRule] = None):
        self.name = name
        self.rules = rules or []
        self.global_validators = []
    
    def add_rule(self, rule: ValidationRule):
        """Add a validation rule."""
        self.rules.append(rule)
    
    def add_global_validator(self, validator: Callable):
        """Add a global validator."""
        self.global_validators.append(validator)
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data against schema.
        
        Args:
            data: Data to validate
            context: Validation context
            
        Returns:
            Validation result
        """
        errors = {}
        warnings = {}
        
        # Validate individual fields
        for rule in self.rules:
            field_value = data.get(rule.field)
            result = rule.validate(field_value, context)
            
            if not result['valid']:
                errors[rule.field] = {
                    'error': result.get('error', rule.message),
                    'code': result.get('code', rule.code)
                }
            elif 'warning' in result:
                warnings[rule.field] = result['warning']
        
        # Run global validators
        for validator in self.global_validators:
            try:
                result = validator(data, context)
                if isinstance(result, dict) and not result.get('valid', True):
                    if 'field' in result:
                        errors[result['field']] = {
                            'error': result.get('error', 'Validation failed'),
                            'code': result.get('code', 'validation_failed')
                        }
                    else:
                        errors['_global'] = {
                            'error': result.get('error', 'Validation failed'),
                            'code': result.get('code', 'validation_failed')
                        }
            except Exception as e:
                errors['_global'] = {
                    'error': str(e),
                    'code': 'validator_error'
                }
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'schema': self.name
        }


class RateLimitValidators:
    """Collection of rate limit validators."""
    
    @staticmethod
    def validate_ip_address(ip_address: str, context: Dict[str, Any] = None) -> bool:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_endpoint(endpoint: str, context: Dict[str, Any] = None) -> bool:
        """Validate endpoint format."""
        if not endpoint:
            return False
        
        # Should start with /
        if not endpoint.startswith('/'):
            return False
        
        # Check for invalid characters
        invalid_chars = ['<', '>', '"', "'", '&', '?', '#', ' ']
        if any(char in endpoint for char in invalid_chars):
            return False
        
        return True
    
    @staticmethod
    def validate_rate_limit_type(limit_type: str, context: Dict[str, Any] = None) -> bool:
        """Validate rate limit type."""
        valid_types = ['user', 'ip', 'endpoint', 'global', 'task', 'offer_wall']
        return limit_type in valid_types
    
    @staticmethod
    def validate_time_unit(time_unit: str, context: Dict[str, Any] = None) -> bool:
        """Validate time unit."""
        valid_units = ['second', 'minute', 'hour', 'day', 'week', 'month']
        return time_unit in valid_units
    
    @staticmethod
    def validate_requests_per_unit(requests: int, context: Dict[str, Any] = None) -> bool:
        """Validate requests per unit."""
        return isinstance(requests, int) and 1 <= requests <= 1000000
    
    @staticmethod
    def validate_time_value(time_value: int, context: Dict[str, Any] = None) -> bool:
        """Validate time value."""
        return isinstance(time_value, int) and 1 <= time_value <= 10080  # Max 1 week
    
    @staticmethod
    def validate_user_id(user_id: Union[int, str], context: Dict[str, Any] = None) -> bool:
        """Validate user ID."""
        if isinstance(user_id, int):
            return user_id > 0
        elif isinstance(user_id, str):
            return user_id.isdigit() and int(user_id) > 0
        return False
    
    @staticmethod
    def validate_suspicion_score(score: int, context: Dict[str, Any] = None) -> bool:
        """Validate suspicion score."""
        return isinstance(score, int) and 0 <= score <= 100
    
    @staticmethod
    def validate_api_health_score(score: int, context: Dict[str, Any] = None) -> bool:
        """Validate API health score."""
        return isinstance(score, int) and 0 <= score <= 100
    
    @staticmethod
    def validate_abuse_type(abuse_type: str, context: Dict[str, Any] = None) -> bool:
        """Validate abuse type."""
        valid_types = [
            'spam', 'bot', 'scraping', 'ddos', 'brute_force', 
            'injection', 'fraud', 'malicious', 'suspicious'
        ]
        return abuse_type in valid_types
    
    @staticmethod
    def validate_severity(severity: int, context: Dict[str, Any] = None) -> bool:
        """Validate severity level."""
        return isinstance(severity, int) and 1 <= severity <= 5
    
    @staticmethod
    def validate_block_reason(reason: str, context: Dict[str, Any] = None) -> bool:
        """Validate block reason."""
        if not reason:
            return False
        
        valid_reasons = [
            'abuse', 'security', 'manual', 'automatic', 
            'policy_violation', 'suspicious', 'threat'
        ]
        
        return reason in valid_reasons
    
    @staticmethod
    def validate_block_type(block_type: str, context: Dict[str, Any] = None) -> bool:
        """Validate block type."""
        valid_types = ['temporary', 'permanent']
        return block_type in valid_types
    
    @staticmethod
    def validate_exception_type(exception_type: str, context: Dict[str, Any] = None) -> bool:
        """Validate exception type."""
        valid_types = [
            'whitelist', 'premium_user', 'trusted_ip', 
            'emergency', 'maintenance', 'testing'
        ]
        return exception_type in valid_types
    
    @staticmethod
    def validate_custom_daily_limit(limit: int, context: Dict[str, Any] = None) -> bool:
        """Validate custom daily limit."""
        return isinstance(limit, int) and 0 <= limit <= 100000
    
    @staticmethod
    def validate_custom_hourly_limit(limit: int, context: Dict[str, Any] = None) -> bool:
        """Validate custom hourly limit."""
        return isinstance(limit, int) and 0 <= limit <= 10000


class DataValidator:
    """
    Main data validator for rate limiting.
    """
    
    def __init__(self):
        self.schemas: Dict[str, ValidationSchema] = {}
        self.global_validators = []
        self._initialize_schemas()
    
    def _initialize_schemas(self):
        """Initialize default validation schemas."""
        
        # Rate limit config schema
        config_schema = ValidationSchema('rate_limit_config')
        config_schema.add_rule(ValidationRule(
            'name_required', 'name', 
            lambda x: x is not None and isinstance(x, str) and len(x.strip()) > 0,
            'Name is required', 'name_required'
        ))
        config_schema.add_rule(ValidationRule(
            'rate_limit_type', 'rate_limit_type',
            RateLimitValidators.validate_rate_limit_type,
            'Invalid rate limit type', 'invalid_rate_limit_type'
        ))
        config_schema.add_rule(ValidationRule(
            'requests_per_unit', 'requests_per_unit',
            RateLimitValidators.validate_requests_per_unit,
            'Invalid requests per unit', 'invalid_requests_per_unit'
        ))
        config_schema.add_rule(ValidationRule(
            'time_unit', 'time_unit',
            RateLimitValidators.validate_time_unit,
            'Invalid time unit', 'invalid_time_unit'
        ))
        config_schema.add_rule(ValidationRule(
            'time_value', 'time_value',
            RateLimitValidators.validate_time_value,
            'Invalid time value', 'invalid_time_value'
        ))
        
        self.schemas['rate_limit_config'] = config_schema
        
        # Rate limit log schema
        log_schema = ValidationSchema('rate_limit_log')
        log_schema.add_rule(ValidationRule(
            'ip_address', 'ip_address',
            RateLimitValidators.validate_ip_address,
            'Invalid IP address', 'invalid_ip_address'
        ))
        log_schema.add_rule(ValidationRule(
            'endpoint', 'endpoint',
            RateLimitValidators.validate_endpoint,
            'Invalid endpoint', 'invalid_endpoint'
        ))
        log_schema.add_rule(ValidationRule(
            'request_method', 'request_method',
            lambda x: x in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'],
            'Invalid request method', 'invalid_request_method'
        ))
        log_schema.add_rule(ValidationRule(
            'status', 'status',
            lambda x: x in ['allowed', 'blocked', 'error'],
            'Invalid status', 'invalid_status'
        ))
        log_schema.add_rule(ValidationRule(
            'suspicion_score', 'suspicion_score',
            RateLimitValidators.validate_suspicion_score,
            'Invalid suspicion score', 'invalid_suspicion_score'
        ))
        
        self.schemas['rate_limit_log'] = log_schema
        
        # User profile schema
        profile_schema = ValidationSchema('user_profile')
        profile_schema.add_rule(ValidationRule(
            'user_id', 'user_id',
            RateLimitValidators.validate_user_id,
            'Invalid user ID', 'invalid_user_id'
        ))
        profile_schema.add_rule(ValidationRule(
            'api_health_score', 'api_health_score',
            RateLimitValidators.validate_api_health_score,
            'Invalid API health score', 'invalid_api_health_score'
        ))
        profile_schema.add_rule(ValidationRule(
            'suspicion_score', 'suspicion_score',
            RateLimitValidators.validate_suspicion_score,
            'Invalid suspicion score', 'invalid_suspicion_score'
        ))
        profile_schema.add_rule(ValidationRule(
            'custom_daily_limit', 'custom_daily_limit',
            RateLimitValidators.validate_custom_daily_limit,
            'Invalid custom daily limit', 'invalid_custom_daily_limit',
            required=False
        ))
        profile_schema.add_rule(ValidationRule(
            'custom_hourly_limit', 'custom_hourly_limit',
            RateLimitValidators.validate_custom_hourly_limit,
            'Invalid custom hourly limit', 'invalid_custom_hourly_limit',
            required=False
        ))
        
        self.schemas['user_profile'] = profile_schema
        
        # Abuse report schema
        abuse_schema = ValidationSchema('abuse_report')
        abuse_schema.add_rule(ValidationRule(
            'abuse_type', 'abuse_type',
            RateLimitValidators.validate_abuse_type,
            'Invalid abuse type', 'invalid_abuse_type'
        ))
        abuse_schema.add_rule(ValidationRule(
            'severity', 'severity',
            RateLimitValidators.validate_severity,
            'Invalid severity', 'invalid_severity'
        ))
        abuse_schema.add_rule(ValidationRule(
            'ip_address', 'ip_address',
            RateLimitValidators.validate_ip_address,
            'Invalid IP address', 'invalid_ip_address',
            required=False
        ))
        
        self.schemas['abuse_report'] = abuse_schema
        
        # IP block schema
        block_schema = ValidationSchema('ip_block')
        block_schema.add_rule(ValidationRule(
            'ip_address', 'ip_address',
            RateLimitValidators.validate_ip_address,
            'Invalid IP address', 'invalid_ip_address'
        ))
        block_schema.add_rule(ValidationRule(
            'block_reason', 'block_reason',
            RateLimitValidators.validate_block_reason,
            'Invalid block reason', 'invalid_block_reason'
        ))
        block_schema.add_rule(ValidationRule(
            'block_type', 'block_type',
            RateLimitValidators.validate_block_type,
            'Invalid block type', 'invalid_block_type'
        ))
        
        self.schemas['ip_block'] = block_schema
        
        # Exception schema
        exception_schema = ValidationSchema('rate_limit_exception')
        exception_schema.add_rule(ValidationRule(
            'exception_type', 'exception_type',
            RateLimitValidators.validate_exception_type,
            'Invalid exception type', 'invalid_exception_type'
        ))
        exception_schema.add_rule(ValidationRule(
            'ip_address', 'ip_address',
            RateLimitValidators.validate_ip_address,
            'Invalid IP address', 'invalid_ip_address',
            required=False
        ))
        
        self.schemas['rate_limit_exception'] = exception_schema
    
        # Add global validator for cross-field validation
        def validate_time_window_consistency(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
            """Validate time window consistency."""
            time_unit = data.get('time_unit')
            time_value = data.get('time_value')
            
            if time_unit and time_value:
                # Check for reasonable combinations
                if time_unit == 'second' and time_value > 3600:  # Max 1 hour
                    return {
                        'valid': False,
                        'field': 'time_value',
                        'error': 'Time value too large for second unit',
                        'code': 'time_value_too_large'
                    }
                elif time_unit == 'minute' and time_value > 1440:  # Max 1 day
                    return {
                        'valid': False,
                        'field': 'time_value',
                        'error': 'Time value too large for minute unit',
                        'code': 'time_value_too_large'
                    }
                elif time_unit == 'hour' and time_value > 168:  # Max 1 week
                    return {
                        'valid': False,
                        'field': 'time_value',
                        'error': 'Time value too large for hour unit',
                        'code': 'time_value_too_large'
                    }
            
            return {'valid': True}
        
        for schema in self.schemas.values():
            schema.add_global_validator(validate_time_window_consistency)
    
    def register_schema(self, name: str, schema: ValidationSchema):
        """Register a validation schema."""
        self.schemas[name] = schema
        logger.info(f"Registered validation schema: {name}")
    
    def unregister_schema(self, name: str):
        """Unregister a validation schema."""
        if name in self.schemas:
            del self.schemas[name]
            logger.info(f"Unregistered validation schema: {name}")
    
    def validate(self, schema_name: str, data: Dict[str, Any], 
                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate data against a schema.
        
        Args:
            schema_name: Schema name
            data: Data to validate
            context: Validation context
            
        Returns:
            Validation result
        """
        schema = self.schemas.get(schema_name)
        if not schema:
            return {
                'valid': False,
                'errors': {'_schema': f'Schema not found: {schema_name}'}
            }
        
        return schema.validate(data, context)
    
    def validate_rate_limit_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rate limit configuration."""
        return self.validate('rate_limit_config', config_data)
    
    def validate_rate_limit_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rate limit log."""
        return self.validate('rate_limit_log', log_data)
    
    def validate_user_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user profile."""
        return self.validate('user_profile', profile_data)
    
    def validate_abuse_report(self, abuse_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate abuse report."""
        return self.validate('abuse_report', abuse_data)
    
    def validate_ip_block(self, block_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate IP block."""
        return self.validate('ip_block', block_data)
    
    def validate_rate_limit_exception(self, exception_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rate limit exception."""
        return self.validate('rate_limit_exception', exception_data)
    
    def get_schema_info(self, schema_name: str = None) -> Dict[str, Any]:
        """Get schema information."""
        if schema_name:
            schema = self.schemas.get(schema_name)
            if schema:
                return {
                    'name': schema.name,
                    'rules': [
                        {
                            'name': rule.name,
                            'field': rule.field,
                            'required': rule.required
                        }
                        for rule in schema.rules
                    ]
                }
            else:
                return {'error': f'Schema not found: {schema_name}'}
        else:
            return {
                name: {
                    'name': schema.name,
                    'rules_count': len(schema.rules)
                }
                for name, schema in self.schemas.items()
            }
    
    def add_custom_rule(self, schema_name: str, rule: ValidationRule):
        """Add a custom rule to a schema."""
        schema = self.schemas.get(schema_name)
        if schema:
            schema.add_rule(rule)
            logger.info(f"Added custom rule to schema {schema_name}")
        else:
            logger.error(f"Schema not found: {schema_name}")
    
    def add_custom_validator(self, schema_name: str, validator: Callable):
        """Add a custom validator to a schema."""
        schema = self.schemas.get(schema_name)
        if schema:
            schema.add_global_validator(validator)
            logger.info(f"Added custom validator to schema {schema_name}")
        else:
            logger.error(f"Schema not found: {schema_name}")


# Global data validator instance
data_validator = DataValidator()


# Export classes and functions
__all__ = [
    'ValidationRule',
    'ValidationSchema',
    'RateLimitValidators',
    'DataValidator',
    'data_validator'
]
