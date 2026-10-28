# engagement/integration_system/data_validator.py
"""
Data validation system for integration platform.
Provides comprehensive data validation, sanitization, and security checks.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Pattern
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import (
    RegexValidator, EmailValidator, URLValidator,
    MaxLengthValidator, MinLengthValidator,
    MaxValueValidator, MinValueValidator
)
from django.conf import settings

from .integ_constants import (
    ERROR_CODES, VALIDATION_RULES, SECURITY_CONFIG
)

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationType(Enum):
    """Types of validation."""
    REQUIRED = "required"
    TYPE = "type"
    FORMAT = "format"
    LENGTH = "length"
    RANGE = "range"
    PATTERN = "pattern"
    CUSTOM = "custom"
    SECURITY = "security"
    BUSINESS = "business"


@dataclass
class ValidationRule:
    """Validation rule definition."""
    id: str
    name: str
    type: ValidationType
    field: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    stop_on_failure: bool = True
    message: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    custom_validator: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Validation result."""
    valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    sanitized_data: Optional[Dict[str, Any]] = None
    validation_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseValidator(ABC):
    """Base validator class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate data against rule."""
        pass
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return True


class RequiredValidator(BaseValidator):
    """Required field validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate required field."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            
            if field_value is None or field_value == '':
                result.valid = False
                result.errors.append({
                    'field': rule.field,
                    'rule': rule.name,
                    'message': rule.message or f"Field '{rule.field}' is required",
                    'severity': rule.severity.value,
                    'value': field_value
                })
            
        except Exception as exc:
            self.logger.error(f"Required validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.REQUIRED
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class TypeValidator(BaseValidator):
    """Type validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate field type."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            expected_type = rule.config.get('type')
            
            if field_value is not None:
                if expected_type == 'string' and not isinstance(field_value, str):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be a string",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
                elif expected_type == 'integer' and not isinstance(field_value, int):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be an integer",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
                elif expected_type == 'float' and not isinstance(field_value, (float, int)):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be a number",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
                elif expected_type == 'boolean' and not isinstance(field_value, bool):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be a boolean",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
                elif expected_type == 'list' and not isinstance(field_value, list):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be a list",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
                elif expected_type == 'dict' and not isinstance(field_value, dict):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be a dictionary",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
                elif expected_type == 'datetime' and not isinstance(field_value, (datetime, str)):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be a datetime",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'expected_type': expected_type,
                        'actual_type': type(field_value).__name__
                    })
            
        except Exception as exc:
            self.logger.error(f"Type validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.TYPE
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class FormatValidator(BaseValidator):
    """Format validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate field format."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            format_type = rule.config.get('format')
            
            if field_value is not None:
                if format_type == 'email':
                    validator = EmailValidator()
                    try:
                        validator(str(field_value))
                    except ValidationError:
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' must be a valid email",
                            'severity': rule.severity.value,
                            'value': field_value
                        })
                
                elif format_type == 'url':
                    validator = URLValidator()
                    try:
                        validator(str(field_value))
                    except ValidationError:
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' must be a valid URL",
                            'severity': rule.severity.value,
                            'value': field_value
                        })
                
                elif format_type == 'phone':
                    phone_pattern = VALIDATION_RULES.get('phone', r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$')
                    if not re.match(phone_pattern, str(field_value)):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' must be a valid phone number",
                            'severity': rule.severity.value,
                            'value': field_value
                        })
                
                elif format_type == 'uuid':
                    uuid_pattern = VALIDATION_RULES.get('uuid', r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
                    if not re.match(uuid_pattern, str(field_value)):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' must be a valid UUID",
                            'severity': rule.severity.value,
                            'value': field_value
                        })
                
                elif format_type == 'date':
                    try:
                        if isinstance(field_value, str):
                            datetime.fromisoformat(field_value)
                        elif not isinstance(field_value, datetime):
                            raise ValueError("Invalid date format")
                    except (ValueError, TypeError):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' must be a valid date",
                            'severity': rule.severity.value,
                            'value': field_value
                        })
                
                elif format_type == 'json':
                    try:
                        if isinstance(field_value, str):
                            json.loads(field_value)
                        elif not isinstance(field_value, (dict, list)):
                            raise ValueError("Invalid JSON format")
                    except (ValueError, TypeError):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' must be valid JSON",
                            'severity': rule.severity.value,
                            'value': field_value
                        })
            
        except Exception as exc:
            self.logger.error(f"Format validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.FORMAT
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class LengthValidator(BaseValidator):
    """Length validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate field length."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            
            if field_value is not None:
                value_length = len(str(field_value))
                min_length = rule.config.get('min_length')
                max_length = rule.config.get('max_length')
                
                if min_length is not None and value_length < min_length:
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be at least {min_length} characters",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'length': value_length,
                        'min_length': min_length
                    })
                
                if max_length is not None and value_length > max_length:
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be at most {max_length} characters",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'length': value_length,
                        'max_length': max_length
                    })
            
        except Exception as exc:
            self.logger.error(f"Length validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.LENGTH
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class RangeValidator(BaseValidator):
    """Range validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate field range."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            
            if field_value is not None:
                min_value = rule.config.get('min_value')
                max_value = rule.config.get('max_value')
                
                # Convert to appropriate type for comparison
                if isinstance(field_value, str) and min_value is not None:
                    try:
                        if '.' in str(min_value):
                            field_value = float(field_value)
                        else:
                            field_value = int(field_value)
                    except ValueError:
                        pass
                
                if min_value is not None and field_value < min_value:
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be at least {min_value}",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'min_value': min_value
                    })
                
                if max_value is not None and field_value > max_value:
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' must be at most {max_value}",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'max_value': max_value
                    })
            
        except Exception as exc:
            self.logger.error(f"Range validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.RANGE
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class PatternValidator(BaseValidator):
    """Pattern validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate field pattern."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            pattern = rule.config.get('pattern')
            
            if field_value is not None and pattern:
                if not re.match(pattern, str(field_value)):
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Field '{rule.field}' does not match required pattern",
                        'severity': rule.severity.value,
                        'value': field_value,
                        'pattern': pattern
                    })
            
        except Exception as exc:
            self.logger.error(f"Pattern validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.PATTERN
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class SecurityValidator(BaseValidator):
    """Security validator."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate security constraints."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            field_value = self._get_field_value(data, rule.field)
            
            if field_value is not None:
                security_type = rule.config.get('security_type')
                
                if security_type == 'no_sql_injection':
                    if self._contains_sql_injection(str(field_value)):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' contains potentially malicious content",
                            'severity': ValidationSeverity.CRITICAL.value,
                            'value': field_value
                        })
                
                elif security_type == 'no_xss':
                    if self._contains_xss(str(field_value)):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' contains potentially malicious content",
                            'severity': ValidationSeverity.CRITICAL.value,
                            'value': field_value
                        })
                
                elif security_type == 'no_path_traversal':
                    if self._contains_path_traversal(str(field_value)):
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' contains potentially malicious content",
                            'severity': ValidationSeverity.CRITICAL.value,
                            'value': field_value
                        })
                
                elif security_type == 'max_size':
                    max_size = rule.config.get('max_size', SECURITY_CONFIG.get('MAX_REQUEST_SIZE', 10485760))
                    if len(str(field_value).encode()) > max_size:
                        result.valid = False
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Field '{rule.field}' exceeds maximum size",
                            'severity': ValidationSeverity.ERROR.value,
                            'value': field_value,
                            'max_size': max_size
                        })
            
        except Exception as exc:
            self.logger.error(f"Security validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.SECURITY
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None
    
    def _contains_sql_injection(self, value: str) -> bool:
        """Check for SQL injection patterns."""
        sql_patterns = [
            r'(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)',
            r'(?i)(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)',
            r'(?i)(\b(or|and)\b.*\b(=|like)\b)',
            r'(?i)(\b(where|having)\b.*\b(or|and)\b)',
            r'(?i)(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b.*\b(all|distinct|top)\b)',
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, value):
                return True
        return False
    
    def _contains_xss(self, value: str) -> bool:
        """Check for XSS patterns."""
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'javascript:',
            r'on\w+\s*=\s*["\'][^"\']*["\']',
            r'<\w+[^>]*\s+on\w+\s*=',
            r'<\w+[^>]*\s+src\s*=\s*["\']javascript:',
            r'(?i)(<|&lt;)(script|iframe|object|embed|form|input|textarea|link|meta|style)',
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    def _contains_path_traversal(self, value: str) -> bool:
        """Check for path traversal patterns."""
        path_patterns = [
            r'\.\./',
            r'\.\\\./',
            r'\.\.\\',
            r'%2e%2e%2f',
            r'%2e%2e\\',
            r'%2e\\%2f',
            r'/etc/passwd',
            r'/etc/shadow',
            r'\\windows\\system32',
        ]
        
        for pattern in path_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False


class CustomValidator(BaseValidator):
    """Custom validator with user-defined logic."""
    
    def validate(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate using custom function."""
        start_time = timezone.now()
        result = ValidationResult(valid=True)
        
        try:
            if rule.custom_validator:
                custom_result = rule.custom_validator(data, rule)
                
                if isinstance(custom_result, ValidationResult):
                    result = custom_result
                elif isinstance(custom_result, bool):
                    result.valid = custom_result
                    if not custom_result:
                        result.errors.append({
                            'field': rule.field,
                            'rule': rule.name,
                            'message': rule.message or f"Custom validation failed for field '{rule.field}'",
                            'severity': rule.severity.value
                        })
                else:
                    result.valid = False
                    result.errors.append({
                        'field': rule.field,
                        'rule': rule.name,
                        'message': rule.message or f"Custom validator returned invalid result",
                        'severity': rule.severity.value
                    })
            
        except Exception as exc:
            self.logger.error(f"Custom validation error: {exc}")
            result.valid = False
            result.errors.append({
                'field': rule.field,
                'rule': rule.name,
                'message': f"Validation error: {str(exc)}",
                'severity': ValidationSeverity.ERROR.value
            })
        
        result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
        return result
    
    def can_validate(self, rule: ValidationRule) -> bool:
        """Check if validator can handle rule."""
        return rule.type == ValidationType.CUSTOM
    
    def _get_field_value(self, data: Any, field: str) -> Any:
        """Get field value from data."""
        if isinstance(data, dict):
            return data.get(field)
        elif hasattr(data, field):
            return getattr(data, field)
        return None


class DataValidator:
    """Main data validator."""
    
    def __init__(self):
        self.validators = {
            ValidationType.REQUIRED: RequiredValidator('required'),
            ValidationType.TYPE: TypeValidator('type'),
            ValidationType.FORMAT: FormatValidator('format'),
            ValidationType.LENGTH: LengthValidator('length'),
            ValidationType.RANGE: RangeValidator('range'),
            ValidationType.PATTERN: PatternValidator('pattern'),
            ValidationType.SECURITY: SecurityValidator('security'),
            ValidationType.CUSTOM: CustomValidator('custom'),
        }
        self.logger = logging.getLogger(f"{__name__}.DataValidator")
    
    def validate(self, data: Any, rules: List[ValidationRule], 
                 sanitize: bool = True) -> ValidationResult:
        """Validate data against rules."""
        start_time = timezone.now()
        overall_result = ValidationResult(valid=True)
        
        try:
            # Sanitize data if requested
            sanitized_data = None
            if sanitize:
                sanitized_data = self._sanitize_data(data)
            
            # Apply validation rules
            for rule in rules:
                if not rule.enabled:
                    continue
                
                validator = self.validators.get(rule.type)
                if not validator or not validator.can_validate(rule):
                    self.logger.warning(f"No validator found for rule {rule.name} of type {rule.type}")
                    continue
                
                # Use sanitized data if available
                validation_data = sanitized_data if sanitized_data is not None else data
                
                result = validator.validate(validation_data, rule)
                
                # Merge results
                if not result.valid:
                    overall_result.valid = False
                
                overall_result.errors.extend(result.errors)
                overall_result.warnings.extend(result.warnings)
                overall_result.info.extend(result.info)
            
            # Set sanitized data
            if sanitize and sanitized_data is not None:
                overall_result.sanitized_data = sanitized_data
            
            overall_result.validation_time_ms = (timezone.now() - start_time).total_seconds() * 1000
            return overall_result
            
        except Exception as exc:
            self.logger.error(f"Validation failed: {exc}")
            return ValidationResult(
                valid=False,
                errors=[{
                    'message': f"Validation failed: {str(exc)}",
                    'severity': ValidationSeverity.CRITICAL.value
                }],
                validation_time_ms=(timezone.now() - start_time).total_seconds() * 1000
            )
    
    def validate_field(self, data: Any, field: str, rule_type: ValidationType, 
                       **config) -> ValidationResult:
        """Validate a single field."""
        rule = ValidationRule(
            id=f"field_{field}_{rule_type.value}",
            name=f"Validate {field}",
            type=rule_type,
            field=field,
            config=config
        )
        
        return self.validate(data, [rule])
    
    def add_validator(self, validation_type: ValidationType, validator: BaseValidator):
        """Add custom validator."""
        self.validators[validation_type] = validator
        self.logger.info(f"Added custom validator for {validation_type}")
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize data for security."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                sanitized[key] = self._sanitize_value(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_value(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_value(data)
        else:
            return data
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize a single value."""
        if isinstance(value, str):
            # Remove potentially dangerous characters
            value = re.sub(r'[<>"\']', '', value)
            
            # Limit length
            max_length = SECURITY_CONFIG.get('MAX_REQUEST_SIZE', 10485760)
            if len(value.encode()) > max_length:
                value = value[:max_length]
            
            return value
        elif isinstance(value, (dict, list)):
            return self._sanitize_data(value)
        else:
            return value


# Validation utilities
class ValidationUtils:
    """Utilities for validation."""
    
    @staticmethod
    def create_rule(rule_id: str, name: str, field: str, rule_type: ValidationType, 
                   **config) -> ValidationRule:
        """Create validation rule."""
        return ValidationRule(
            id=rule_id,
            name=name,
            type=rule_type,
            field=field,
            **config
        )
    
    @staticmethod
    def required_rule(field: str, message: str = None) -> ValidationRule:
        """Create required field rule."""
        return ValidationRule(
            id=f"required_{field}",
            name=f"Required {field}",
            type=ValidationType.REQUIRED,
            field=field,
            message=message or f"Field '{field}' is required"
        )
    
    @staticmethod
    def type_rule(field: str, expected_type: str, message: str = None) -> ValidationRule:
        """Create type validation rule."""
        return ValidationRule(
            id=f"type_{field}",
            name=f"Type {field}",
            type=ValidationType.TYPE,
            field=field,
            config={'type': expected_type},
            message=message or f"Field '{field}' must be of type {expected_type}"
        )
    
    @staticmethod
    def email_rule(field: str, message: str = None) -> ValidationRule:
        """Create email validation rule."""
        return ValidationRule(
            id=f"email_{field}",
            name=f"Email {field}",
            type=ValidationType.FORMAT,
            field=field,
            config={'format': 'email'},
            message=message or f"Field '{field}' must be a valid email"
        )
    
    @staticmethod
    def length_rule(field: str, min_length: int = None, max_length: int = None, 
                    message: str = None) -> ValidationRule:
        """Create length validation rule."""
        config = {}
        if min_length is not None:
            config['min_length'] = min_length
        if max_length is not None:
            config['max_length'] = max_length
        
        return ValidationRule(
            id=f"length_{field}",
            name=f"Length {field}",
            type=ValidationType.LENGTH,
            field=field,
            config=config,
            message=message or f"Field '{field}' length validation"
        )
    
    @staticmethod
    def range_rule(field: str, min_value: Any = None, max_value: Any = None,
                   message: str = None) -> ValidationRule:
        """Create range validation rule."""
        config = {}
        if min_value is not None:
            config['min_value'] = min_value
        if max_value is not None:
            config['max_value'] = max_value
        
        return ValidationRule(
            id=f"range_{field}",
            name=f"Range {field}",
            type=ValidationType.RANGE,
            field=field,
            config=config,
            message=message or f"Field '{field}' range validation"
        )
    
    @staticmethod
    def security_rule(field: str, security_type: str, message: str = None) -> ValidationRule:
        """Create security validation rule."""
        return ValidationRule(
            id=f"security_{field}",
            name=f"Security {field}",
            type=ValidationType.SECURITY,
            field=field,
            config={'security_type': security_type},
            severity=ValidationSeverity.CRITICAL,
            message=message or f"Field '{field}' security validation"
        )
    
    @staticmethod
    def custom_rule(field: str, validator_func: Callable, message: str = None) -> ValidationRule:
        """Create custom validation rule."""
        return ValidationRule(
            id=f"custom_{field}",
            name=f"Custom {field}",
            type=ValidationType.CUSTOM,
            field=field,
            custom_validator=validator_func,
            message=message or f"Field '{field}' custom validation"
        )


# Global data validator instance
data_validator = DataValidator()
