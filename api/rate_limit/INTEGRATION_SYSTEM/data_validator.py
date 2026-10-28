"""
Data Validator - Comprehensive Data Validation System

Comprehensive data validation framework with support for various validation
rules, custom validators, and detailed error reporting.
"""

import logging
import re
import json
import jsonschema
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import ipaddress
from django.core.validators import ValidationError as DjangoValidationError
from django.utils import timezone

from .integ_constants import IntegrationDataType
from .integ_exceptions import IntegrationError, ValidationError

logger = logging.getLogger(__name__)


class ValidationType(Enum):
    """Types of validation."""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    FORMAT_CHECK = "format_check"
    RANGE_CHECK = "range_check"
    LENGTH_CHECK = "length_check"
    PATTERN_CHECK = "pattern_check"
    CUSTOM = "custom"
    SCHEMA = "schema"
    BUSINESS_RULE = "business_rule"


class ValidationSeverity(Enum):
    """Validation error severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationRule:
    """Validation rule configuration."""
    name: str
    validation_type: ValidationType
    field_path: str  # JSON path like "user.email" or "items[*].price"
    parameters: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    custom_validator: Optional[str] = None
    is_required: bool = False
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Validation result."""
    is_valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    validated_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_time: float = 0.0


@dataclass
class ValidationError:
    """Validation error details."""
    field_path: str
    rule_name: str
    error_message: str
    severity: ValidationSeverity
    actual_value: Any
    expected_value: Any = None
    context: Dict[str, Any] = field(default_factory=dict)


class DataValidator:
    """Comprehensive data validation system."""
    
    def __init__(self):
        self.validation_rules: List[ValidationRule] = []
        self.custom_validators: Dict[str, Callable] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self._register_default_validators()
        self._register_default_schemas()
    
    def _register_default_validators(self):
        """Register default validation functions."""
        self.custom_validators.update({
            'email': self._validate_email,
            'phone': self._validate_phone,
            'url': self._validate_url,
            'ip_address': self._validate_ip_address,
            'uuid': self._validate_uuid,
            'json': self._validate_json,
            'xml': self._validate_xml,
            'base64': self._validate_base64,
            'slug': self._validate_slug,
            'username': self._validate_username,
            'password_strength': self._validate_password_strength,
            'credit_card': self._validate_credit_card,
            'ssn': self._validate_ssn,
            'date_range': self._validate_date_range,
            'file_size': self._validate_file_size,
            'mime_type': self._validate_mime_type,
            'coordinates': self._validate_coordinates,
            'color_hex': self._validate_color_hex,
            'semver': self._validate_semver
        })
    
    def _register_default_schemas(self):
        """Register default JSON schemas."""
        self.schemas.update({
            'user_profile': {
                "type": "object",
                "required": ["id", "email", "username"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-f0-9-]{36}$"},
                    "email": {"type": "string", "format": "email"},
                    "username": {"type": "string", "minLength": 3, "maxLength": 50},
                    "first_name": {"type": "string", "maxLength": 100},
                    "last_name": {"type": "string", "maxLength": 100},
                    "age": {"type": "integer", "minimum": 0, "maximum": 150},
                    "is_active": {"type": "boolean"},
                    "created_at": {"type": "string", "format": "date-time"}
                }
            },
            'rate_limit_config': {
                "type": "object",
                "required": ["name", "requests_per_unit", "time_unit", "time_value"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 100},
                    "requests_per_unit": {"type": "integer", "minimum": 1, "maximum": 100000},
                    "time_unit": {"type": "string", "enum": ["second", "minute", "hour", "day"]},
                    "time_value": {"type": "integer", "minimum": 1, "maximum": 365},
                    "is_active": {"type": "boolean"},
                    "description": {"type": "string", "maxLength": 500}
                }
            },
            'abuse_report': {
                "type": "object",
                "required": ["ip_address", "abuse_type", "severity"],
                "properties": {
                    "ip_address": {"type": "string", "format": "ipv4"},
                    "user_id": {"type": ["string", "null"]},
                    "abuse_type": {"type": "string", "enum": ["ddos", "brute_force", "scraping", "injection", "other"]},
                    "severity": {"type": "integer", "minimum": 1, "maximum": 5},
                    "details": {"type": "object"},
                    "evidence": {"type": "array", "items": {"type": "string"}}
                }
            }
        })
    
    def add_validation_rule(self, rule: ValidationRule):
        """Add validation rule."""
        self.validation_rules.append(rule)
        logger.info(f"Added validation rule: {rule.name}")
    
    def remove_validation_rule(self, rule_name: str) -> bool:
        """Remove validation rule by name."""
        for i, rule in enumerate(self.validation_rules):
            if rule.name == rule_name:
                self.validation_rules.pop(i)
                logger.info(f"Removed validation rule: {rule_name}")
                return True
        return False
    
    def register_custom_validator(self, name: str, validator: Callable):
        """Register custom validator function."""
        self.custom_validators[name] = validator
        logger.info(f"Registered custom validator: {name}")
    
    def register_schema(self, name: str, schema: Dict[str, Any]):
        """Register JSON schema."""
        self.schemas[name] = schema
        logger.info(f"Registered schema: {name}")
    
    def validate(self, data: Any, rules: List[ValidationRule] = None, 
                schema_name: str = None) -> ValidationResult:
        """Validate data against rules and/or schema."""
        start_time = timezone.now()
        result = ValidationResult(is_valid=True)
        
        try:
            # Use provided rules or default rules
            validation_rules = rules or self.validation_rules
            
            # Validate against schema if provided
            if schema_name:
                schema_result = self._validate_schema(data, schema_name)
                result.errors.extend(schema_result.errors)
                result.warnings.extend(schema_result.warnings)
                result.validated_data.update(schema_result.validated_data)
            
            # Validate against rules
            for rule in validation_rules:
                rule_result = self._validate_rule(data, rule)
                
                # Merge results
                result.errors.extend(rule_result.errors)
                result.warnings.extend(rule_result.warnings)
                result.info.extend(rule_result.info)
                
                # Update validated data
                if rule_result.validated_data:
                    result.validated_data.update(rule_result.validated_data)
            
            # Determine overall validity
            result.is_valid = len(result.errors) == 0
            
            # Calculate validation time
            result.validation_time = (timezone.now() - start_time).total_seconds()
            result.metadata['rules_validated'] = len(validation_rules)
            result.metadata['schema_validated'] = schema_name is not None
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            result.is_valid = False
            result.errors.append({
                'field_path': 'root',
                'rule_name': 'system_error',
                'error_message': f'Validation system error: {str(e)}',
                'severity': ValidationSeverity.CRITICAL.value,
                'actual_value': str(data)[:100]
            })
            result.validation_time = (timezone.now() - start_time).total_seconds()
        
        return result
    
    def _validate_rule(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate data against a single rule."""
        result = ValidationResult(is_valid=True)
        
        try:
            # Get field value
            field_value = self._get_field_value(data, rule.field_path)
            
            # Check if field is required
            if rule.is_required and field_value is None:
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    rule.error_message or f"Field '{rule.field_path}' is required",
                    rule.severity,
                    field_value
                )
                result.errors.append(error)
                result.is_valid = False
                return result
            
            # Skip validation if field is not required and value is None
            if not rule.is_required and field_value is None:
                return result
            
            # Validate based on type
            if rule.validation_type == ValidationType.REQUIRED:
                # Already handled above
                pass
            
            elif rule.validation_type == ValidationType.TYPE_CHECK:
                self._validate_type(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.FORMAT_CHECK:
                self._validate_format(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.RANGE_CHECK:
                self._validate_range(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.LENGTH_CHECK:
                self._validate_length(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.PATTERN_CHECK:
                self._validate_pattern(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.CUSTOM:
                self._validate_custom(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.SCHEMA:
                self._validate_field_schema(field_value, rule, result)
            
            elif rule.validation_type == ValidationType.BUSINESS_RULE:
                self._validate_business_rule(data, rule, result)
            
        except Exception as e:
            logger.error(f"Rule validation failed: {rule.name} - {str(e)}")
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Validation error: {str(e)}",
                ValidationSeverity.ERROR,
                self._get_field_value(data, rule.field_path)
            )
            result.errors.append(error)
            result.is_valid = False
        
        return result
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using JSON path."""
        if field_path == "root":
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                # Handle array indexing
                if '[' in key and key.endswith(']'):
                    field_name = key.split('[')[0]
                    index = int(key.split('[')[1].rstrip(']'))
                    current = current.get(field_name, [])
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                else:
                    current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                index = int(key)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        
        return current
    
    def _validate_type(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate data type."""
        expected_type = rule.parameters.get('type')
        
        if expected_type == 'string':
            if not isinstance(value, str):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Expected string, got {type(value).__name__}",
                    rule.severity,
                    value,
                    expected_type
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif expected_type == 'integer':
            if not isinstance(value, int) or isinstance(value, bool):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Expected integer, got {type(value).__name__}",
                    rule.severity,
                    value,
                    expected_type
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif expected_type == 'float':
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Expected number, got {type(value).__name__}",
                    rule.severity,
                    value,
                    expected_type
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif expected_type == 'boolean':
            if not isinstance(value, bool):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Expected boolean, got {type(value).__name__}",
                    rule.severity,
                    value,
                    expected_type
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif expected_type == 'array':
            if not isinstance(value, list):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Expected array, got {type(value).__name__}",
                    rule.severity,
                    value,
                    expected_type
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif expected_type == 'object':
            if not isinstance(value, dict):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Expected object, got {type(value).__name__}",
                    rule.severity,
                    value,
                    expected_type
                )
                result.errors.append(error)
                result.is_valid = False
    
    def _validate_format(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate data format."""
        format_type = rule.parameters.get('format')
        
        if format_type == 'email':
            if not self._validate_email(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid email format",
                    rule.severity,
                    value,
                    'email'
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif format_type == 'url':
            if not self._validate_url(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid URL format",
                    rule.severity,
                    value,
                    'url'
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif format_type == 'ipv4':
            if not self._validate_ip_address(value, version=4):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid IPv4 address",
                    rule.severity,
                    value,
                    'ipv4'
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif format_type == 'ipv6':
            if not self._validate_ip_address(value, version=6):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid IPv6 address",
                    rule.severity,
                    value,
                    'ipv6'
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif format_type == 'uuid':
            if not self._validate_uuid(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid UUID format",
                    rule.severity,
                    value,
                    'uuid'
                )
                result.errors.append(error)
                result.is_valid = False
        
        elif format_type == 'datetime':
            if not self._validate_datetime(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid datetime format",
                    rule.severity,
                    value,
                    'datetime'
                )
                result.errors.append(error)
                result.is_valid = False
    
        elif format_type == 'date':
            if not self._validate_date(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid date format",
                    rule.severity,
                    value,
                    'date'
                )
                result.errors.append(error)
                result.is_valid = False
    
        elif format_type == 'time':
            if not self._validate_time(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    "Invalid time format",
                    rule.severity,
                    value,
                    'time'
                )
                result.errors.append(error)
                result.is_valid = False
    
    def _validate_range(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate numeric range."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                "Range validation requires numeric value",
                rule.severity,
                value
            )
            result.errors.append(error)
            result.is_valid = False
            return
        
        min_value = rule.parameters.get('min')
        max_value = rule.parameters.get('max')
        
        if min_value is not None and value < min_value:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Value must be at least {min_value}",
                rule.severity,
                value,
                f">= {min_value}"
            )
            result.errors.append(error)
            result.is_valid = False
        
        if max_value is not None and value > max_value:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Value must be at most {max_value}",
                rule.severity,
                value,
                f"<= {max_value}"
            )
            result.errors.append(error)
            result.is_valid = False
    
    def _validate_length(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate string or array length."""
        if isinstance(value, str):
            length = len(value)
        elif isinstance(value, list):
            length = len(value)
        else:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                "Length validation requires string or array",
                rule.severity,
                value
            )
            result.errors.append(error)
            result.is_valid = False
            return
        
        min_length = rule.parameters.get('min_length')
        max_length = rule.parameters.get('max_length')
        
        if min_length is not None and length < min_length:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Length must be at least {min_length}",
                rule.severity,
                value,
                f"length >= {min_length}"
            )
            result.errors.append(error)
            result.is_valid = False
        
        if max_length is not None and length > max_length:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Length must be at most {max_length}",
                rule.severity,
                value,
                f"length <= {max_length}"
            )
            result.errors.append(error)
            result.is_valid = False
    
    def _validate_pattern(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate regex pattern."""
        if not isinstance(value, str):
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                "Pattern validation requires string",
                rule.severity,
                value
            )
            result.errors.append(error)
            result.is_valid = False
            return
        
        pattern = rule.parameters.get('pattern')
        if not pattern:
            return
        
        try:
            regex = re.compile(pattern)
            if not regex.match(value):
                error = self._create_validation_error(
                    rule.field_path,
                    rule.name,
                    f"Value does not match pattern: {pattern}",
                    rule.severity,
                    value,
                    pattern
                )
                result.errors.append(error)
                result.is_valid = False
        except re.error as e:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Invalid regex pattern: {str(e)}",
                ValidationSeverity.ERROR,
                value,
                pattern
            )
            result.errors.append(error)
            result.is_valid = False
    
    def _validate_custom(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate using custom validator."""
        validator_name = rule.custom_validator
        if not validator_name:
            return
        
        validator = self.custom_validators.get(validator_name)
        if not validator:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Custom validator not found: {validator_name}",
                ValidationSeverity.ERROR,
                value
            )
            result.errors.append(error)
            result.is_valid = False
            return
        
        try:
            validation_result = validator(value, rule.parameters)
            if isinstance(validation_result, bool):
                if not validation_result:
                    error = self._create_validation_error(
                        rule.field_path,
                        rule.name,
                        rule.error_message or f"Custom validation failed: {validator_name}",
                        rule.severity,
                        value
                    )
                    result.errors.append(error)
                    result.is_valid = False
            elif isinstance(validation_result, dict):
                if not validation_result.get('valid', False):
                    error = self._create_validation_error(
                        rule.field_path,
                        rule.name,
                        validation_result.get('message', f"Custom validation failed: {validator_name}"),
                        ValidationSeverity(validation_result.get('severity', rule.severity.value)),
                        value
                    )
                    
                    if validation_result.get('severity') == ValidationSeverity.CRITICAL.value:
                        result.errors.append(error)
                        result.is_valid = False
                    elif validation_result.get('severity') == ValidationSeverity.ERROR.value:
                        result.errors.append(error)
                        result.is_valid = False
                    elif validation_result.get('severity') == ValidationSeverity.WARNING.value:
                        result.warnings.append(error)
                    else:
                        result.info.append(error)
                
                # Add validated data if provided
                if 'validated_value' in validation_result:
                    result.validated_data[rule.field_path] = validation_result['validated_value']
        
        except Exception as e:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Custom validator error: {str(e)}",
                ValidationSeverity.ERROR,
                value
            )
            result.errors.append(error)
            result.is_valid = False
    
    def _validate_field_schema(self, value: Any, rule: ValidationRule, result: ValidationResult):
        """Validate field against JSON schema."""
        schema_name = rule.parameters.get('schema')
        if not schema_name:
            return
        
        schema = self.schemas.get(schema_name)
        if not schema:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Schema not found: {schema_name}",
                ValidationSeverity.ERROR,
                value
            )
            result.errors.append(error)
            result.is_valid = False
            return
        
        try:
            jsonschema.validate(value, schema)
        except jsonschema.ValidationError as e:
            error = self._create_validation_error(
                rule.field_path,
                rule.name,
                f"Schema validation failed: {e.message}",
                ValidationSeverity.ERROR,
                value,
                schema_name
            )
            result.errors.append(error)
            result.is_valid = False
    
    def _validate_business_rule(self, data: Any, rule: ValidationRule, result: ValidationResult):
        """Validate business rule."""
        business_rule = rule.parameters.get('rule')
        if not business_rule:
            return
        
        # This would implement custom business logic
        # For now, it's a placeholder
        pass
    
    def _validate_schema(self, data: Any, schema_name: str) -> ValidationResult:
        """Validate data against JSON schema."""
        result = ValidationResult(is_valid=True)
        
        schema = self.schemas.get(schema_name)
        if not schema:
            error = self._create_validation_error(
                'root',
                'schema_validation',
                f"Schema not found: {schema_name}",
                ValidationSeverity.ERROR,
                data
            )
            result.errors.append(error)
            result.is_valid = False
            return result
        
        try:
            jsonschema.validate(data, schema)
            result.validated_data = data
        except jsonschema.ValidationError as e:
            error = self._create_validation_error(
                'root',
                'schema_validation',
                f"Schema validation failed: {e.message}",
                ValidationSeverity.ERROR,
                data,
                schema_name
            )
            result.errors.append(error)
            result.is_valid = False
        
        return result
    
    def _create_validation_error(self, field_path: str, rule_name: str, 
                                message: str, severity: ValidationSeverity,
                                actual_value: Any, expected_value: Any = None) -> Dict[str, Any]:
        """Create validation error dictionary."""
        return {
            'field_path': field_path,
            'rule_name': rule_name,
            'error_message': message,
            'severity': severity.value,
            'actual_value': actual_value,
            'expected_value': expected_value,
            'timestamp': timezone.now().isoformat()
        }
    
    # Default validator implementations
    def _validate_email(self, value: Any) -> bool:
        """Validate email format."""
        if not isinstance(value, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, value))
    
    def _validate_phone(self, value: Any) -> bool:
        """Validate phone number format."""
        if not isinstance(value, str):
            return False
        
        # Remove all non-digit characters
        phone = re.sub(r'[^\d]', '', value)
        
        # Check if it's a valid phone number (10-15 digits)
        return 10 <= len(phone) <= 15
    
    def _validate_url(self, value: Any) -> bool:
        """Validate URL format."""
        if not isinstance(value, str):
            return False
        
        try:
            result = urlparse(value)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _validate_ip_address(self, value: Any, version: int = None) -> bool:
        """Validate IP address format."""
        if not isinstance(value, str):
            return False
        
        try:
            ip = ipaddress.ip_address(value)
            if version == 4:
                return isinstance(ip, ipaddress.IPv4Address)
            elif version == 6:
                return isinstance(ip, ipaddress.IPv6Address)
            else:
                return True
        except ValueError:
            return False
    
    def _validate_uuid(self, value: Any) -> bool:
        """Validate UUID format."""
        if not isinstance(value, str):
            return False
        
        uuid_pattern = r'^[a-f0-9-]{36}$'
        return bool(re.match(uuid_pattern, value))
    
    def _validate_json(self, value: Any) -> bool:
        """Validate JSON format."""
        if not isinstance(value, str):
            return False
        
        try:
            json.loads(value)
            return True
        except ValueError:
            return False
    
    def _validate_xml(self, value: Any) -> bool:
        """Validate XML format."""
        if not isinstance(value, str):
            return False
        
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(value)
            return True
        except ET.ParseError:
            return False
    
    def _validate_base64(self, value: Any) -> bool:
        """Validate Base64 format."""
        if not isinstance(value, str):
            return False
        
        try:
            import base64
            base64.b64decode(value, validate=True)
            return True
        except Exception:
            return False
    
    def _validate_slug(self, value: Any) -> bool:
        """Validate slug format."""
        if not isinstance(value, str):
            return False
        
        slug_pattern = r'^[a-z0-9-]+$'
        return bool(re.match(slug_pattern, value))
    
    def _validate_username(self, value: Any) -> bool:
        """Validate username format."""
        if not isinstance(value, str):
            return False
        
        username_pattern = r'^[a-zA-Z0-9_-]{3,30}$'
        return bool(re.match(username_pattern, value))
    
    def _validate_password_strength(self, value: Any) -> bool:
        """Validate password strength."""
        if not isinstance(value, str):
            return False
        
        # At least 8 characters, 1 uppercase, 1 lowercase, 1 digit, 1 special character
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        return bool(re.match(pattern, value))
    
    def _validate_credit_card(self, value: Any) -> bool:
        """Validate credit card format."""
        if not isinstance(value, str):
            return False
        
        # Remove spaces and dashes
        card_number = re.sub(r'[\s-]', '', value)
        
        # Check if it's all digits and 13-19 digits
        if not card_number.isdigit() or not (13 <= len(card_number) <= 19):
            return False
        
        # Luhn algorithm
        total = 0
        reverse_digits = card_number[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n = (n // 10) + (n % 10)
            total += n
        
        return total % 10 == 0
    
    def _validate_ssn(self, value: Any) -> bool:
        """Validate Social Security Number format."""
        if not isinstance(value, str):
            return False
        
        # SSN format: XXX-XX-XXXX
        ssn_pattern = r'^\d{3}-\d{2}-\d{4}$'
        return bool(re.match(ssn_pattern, value))
    
    def _validate_date_range(self, value: Any, *args) -> bool:
        """Validate date range."""
        if not args:
            return True
        
        try:
            if isinstance(value, str):
                date = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                date = value
            else:
                return False
            
            # Parse date range (e.g., "2020-01-01:2020-12-31")
            if len(args) >= 1 and ':' in args[0]:
                start_str, end_str = args[0].split(':')
                start_date = datetime.fromisoformat(start_str)
                end_date = datetime.fromisoformat(end_str)
                
                return start_date <= date <= end_date
            
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_file_size(self, value: Any, *args) -> bool:
        """Validate file size."""
        if not args:
            return True
        
        max_size = args[0]
        
        if isinstance(value, (int, float)):
            return value <= max_size
        elif isinstance(value, str):
            # Assume it's file size in bytes
            try:
                size = int(value)
                return size <= max_size
            except ValueError:
                return False
        
        return False
    
    def _validate_mime_type(self, value: Any, *args) -> bool:
        """Validate MIME type."""
        if not isinstance(value, str):
            return False
        
        if not args:
            return True
        
        allowed_types = args if isinstance(args[0], (list, tuple)) else [args[0]]
        return value in allowed_types
    
    def _validate_coordinates(self, value: Any) -> bool:
        """Validate geographic coordinates."""
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return False
        
        try:
            lat, lng = float(value[0]), float(value[1])
            return -90 <= lat <= 90 and -180 <= lng <= 180
        except (ValueError, TypeError):
            return False
    
    def _validate_color_hex(self, value: Any) -> bool:
        """Validate hex color code."""
        if not isinstance(value, str):
            return False
        
        color_pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
        return bool(re.match(color_pattern, value))
    
    def _validate_semver(self, value: Any) -> bool:
        """Validate semantic version."""
        if not isinstance(value, str):
            return False
        
        # Semantic version pattern: X.Y.Z
        semver_pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9-]+)?(?:\+[a-zA-Z0-9-]+)?$'
        return bool(re.match(semver_pattern, value))
    
    def _validate_datetime(self, value: Any) -> bool:
        """Validate datetime format."""
        if not isinstance(value, str):
            return False
        
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False
    
    def _validate_date(self, value: Any) -> bool:
        """Validate date format."""
        if not isinstance(value, str):
            return False
        
        try:
            datetime.strptime(value, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _validate_time(self, value: Any) -> bool:
        """Validate time format."""
        if not isinstance(value, str):
            return False
        
        try:
            datetime.strptime(value, '%H:%M:%S')
            return True
        except ValueError:
            return False


# Global data validator instance
data_validator = DataValidator()


# Convenience functions
def create_required_rule(field_path: str, error_message: str = None) -> ValidationRule:
    """Create required field validation rule."""
    return ValidationRule(
        name=f"required_{field_path}",
        validation_type=ValidationType.REQUIRED,
        field_path=field_path,
        error_message=error_message,
        is_required=True
    )


def create_type_rule(field_path: str, expected_type: str, error_message: str = None) -> ValidationRule:
    """Create type validation rule."""
    return ValidationRule(
        name=f"type_{field_path}",
        validation_type=ValidationType.TYPE_CHECK,
        field_path=field_path,
        parameters={'type': expected_type},
        error_message=error_message
    )


def create_range_rule(field_path: str, min_value: float = None, max_value: float = None,
                     error_message: str = None) -> ValidationRule:
    """Create range validation rule."""
    return ValidationRule(
        name=f"range_{field_path}",
        validation_type=ValidationType.RANGE_CHECK,
        field_path=field_path,
        parameters={'min': min_value, 'max': max_value},
        error_message=error_message
    )


def create_length_rule(field_path: str, min_length: int = None, max_length: int = None,
                      error_message: str = None) -> ValidationRule:
    """Create length validation rule."""
    return ValidationRule(
        name=f"length_{field_path}",
        validation_type=ValidationType.LENGTH_CHECK,
        field_path=field_path,
        parameters={'min_length': min_length, 'max_length': max_length},
        error_message=error_message
    )


def create_pattern_rule(field_path: str, pattern: str, error_message: str = None) -> ValidationRule:
    """Create pattern validation rule."""
    return ValidationRule(
        name=f"pattern_{field_path}",
        validation_type=ValidationType.PATTERN_CHECK,
        field_path=field_path,
        parameters={'pattern': pattern},
        error_message=error_message
    )


def create_format_rule(field_path: str, format_type: str, error_message: str = None) -> ValidationRule:
    """Create format validation rule."""
    return ValidationRule(
        name=f"format_{field_path}",
        validation_type=ValidationType.FORMAT_CHECK,
        field_path=field_path,
        parameters={'format': format_type},
        error_message=error_message
    )


def create_custom_rule(field_path: str, validator_name: str, parameters: Dict[str, Any] = None,
                      error_message: str = None) -> ValidationRule:
    """Create custom validation rule."""
    return ValidationRule(
        name=f"custom_{field_path}",
        validation_type=ValidationType.CUSTOM,
        field_path=field_path,
        parameters=parameters or {},
        custom_validator=validator_name,
        error_message=error_message
    )
