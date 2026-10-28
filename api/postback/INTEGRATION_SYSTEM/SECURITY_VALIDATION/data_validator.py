"""
data_validator.py – Data validation system for postback module.

Provides comprehensive data validation functionality including:
- Field validation rules
- Schema validation
- Business logic validation
- Validation error handling
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable, Type
from datetime import datetime, timedelta, date
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import re
import json

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)
User = get_user_model()


class ValidationType(Enum):
    """Validation type enumeration."""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    LENGTH = "length"
    RANGE = "range"
    PATTERN = "pattern"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    UUID = "uuid"
    JSON = "json"
    CUSTOM = "custom"
    BUSINESS_LOGIC = "business_logic"


class ValidationSeverity(Enum):
    """Validation severity enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationRule:
    """Validation rule data structure."""
    name: str
    field: str
    validation_type: ValidationType
    config: Dict[str, Any]
    required: bool = False
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    condition: Optional[str] = None  # Conditional validation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'field': self.field,
            'validation_type': self.validation_type.value,
            'config': self.config,
            'required': self.required,
            'message': self.message,
            'severity': self.severity.value,
            'enabled': self.enabled,
            'condition': self.condition,
        }


@dataclass
class ValidationResult:
    """Validation result data structure."""
    is_valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    validated_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, field: str, message: str, severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Add validation error."""
        self.errors.append({
            'field': field,
            'message': message,
            'severity': severity.value,
            'timestamp': timezone.now().isoformat(),
        })
        self.is_valid = False
    
    def add_warning(self, field: str, message: str):
        """Add validation warning."""
        self.warnings.append({
            'field': field,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        })
    
    def add_info(self, field: str, message: str):
        """Add validation info."""
        self.info.append({
            'field': field,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        })
    
    def has_errors(self) -> bool:
        """Check if there are errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary."""
        return {
            'is_valid': self.is_valid,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'info_count': len(self.info),
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
        }


class Validator(ABC):
    """
    Abstract base class for validators.
    
    Provides common interface for different
    validation implementations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate value.
        
        Args:
            value: Value to validate
            field_name: Field name
            context: Validation context
            
        Returns:
            Validation result
        """
        pass


class RequiredValidator(Validator):
    """Required field validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate required field."""
        result = ValidationResult(is_valid=True)
        
        if value is None or (isinstance(value, str) and value.strip() == ''):
            result.add_error(field_name or 'field', 'This field is required')
        
        return result


class TypeValidator(Validator):
    """Type validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate field type."""
        result = ValidationResult(is_valid=True)
        
        expected_type = self.config.get('type')
        if not expected_type:
            return result
        
        # Handle type conversion
        try:
            if expected_type == 'string':
                if not isinstance(value, str):
                    result.add_error(field_name or 'field', f'Must be a string, got {type(value).__name__}')
            elif expected_type == 'integer':
                if not isinstance(value, int):
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        result.add_error(field_name or 'field', f'Must be an integer, got {type(value).__name__}')
            elif expected_type == 'float':
                if not isinstance(value, (int, float)):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        result.add_error(field_name or 'field', f'Must be a number, got {type(value).__name__}')
            elif expected_type == 'boolean':
                if not isinstance(value, bool):
                    if isinstance(value, str):
                        if value.lower() not in ['true', 'false', '1', '0']:
                            result.add_error(field_name or 'field', f'Must be a boolean, got {value}')
                    else:
                        result.add_error(field_name or 'field', f'Must be a boolean, got {type(value).__name__}')
            elif expected_type == 'datetime':
                if not isinstance(value, (datetime, str)):
                    result.add_error(field_name or 'field', f'Must be a datetime, got {type(value).__name__}')
                elif isinstance(value, str):
                    try:
                        datetime.fromisoformat(value)
                    except ValueError:
                        result.add_error(field_name or 'field', f'Invalid datetime format: {value}')
            elif expected_type == 'decimal':
                if not isinstance(value, (Decimal, str, int, float)):
                    try:
                        Decimal(str(value))
                    except (ValueError, TypeError):
                        result.add_error(field_name or 'field', f'Must be a decimal, got {type(value).__name__}')
            elif expected_type == 'list':
                if not isinstance(value, list):
                    try:
                        json.loads(value)
                    except (ValueError, TypeError):
                        result.add_error(field_name or 'field', f'Must be a list, got {type(value).__name__}')
            elif expected_type == 'dict':
                if not isinstance(value, dict):
                    try:
                        json.loads(value)
                    except (ValueError, TypeError):
                        result.add_error(field_name or 'field', f'Must be a dictionary, got {type(value).__name__}')
        
        except Exception as e:
            result.add_error(field_name or 'field', f'Type validation error: {str(e)}')
        
        return result


class LengthValidator(Validator):
    """Length validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate field length."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, (str, list, dict)):
            return result
        
        length = len(value)
        min_length = self.config.get('min_length')
        max_length = self.config.get('max_length')
        
        if min_length is not None and length < min_length:
            result.add_error(field_name or 'field', f'Must be at least {min_length} characters long')
        
        if max_length is not None and length > max_length:
            result.add_error(field_name or 'field', f'Must be no more than {max_length} characters long')
        
        return result


class RangeValidator(Validator):
    """Range validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate field range."""
        result = ValidationResult(is_valid=True)
        
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            if self.config.get('type') in ['integer', 'float', 'decimal']:
                result.add_error(field_name or 'field', f'Must be a number')
            return result
        
        min_value = self.config.get('min_value')
        max_value = self.config.get('max_value')
        
        if min_value is not None and numeric_value < min_value:
            result.add_error(field_name or 'field', f'Must be at least {min_value}')
        
        if max_value is not None and numeric_value > max_value:
            result.add_error(field_name or 'field', f'Must be no more than {max_value}')
        
        return result


class PatternValidator(Validator):
    """Pattern validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate field pattern."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            return result
        
        pattern = self.config.get('pattern')
        if not pattern:
            return result
        
        try:
            if not re.match(pattern, value):
                result.add_error(field_name or 'field', f'Invalid format')
        except re.error:
            result.add_error(field_name or 'field', f'Invalid pattern configuration')
        
        return result


class EmailValidator(Validator):
    """Email validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate email field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            return result
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            result.add_error(field_name or 'field', 'Invalid email address')
        
        return result


class URLValidator(Validator):
    """URL validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate URL field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            return result
        
        url_pattern = r'^https?://(?:[-\w.])+(?:\.[a-zA-Z]{2,})+(?:/[\w._]*/)*(?:/[^\s]*)?$'
        if not re.match(url_pattern, value):
            result.add_error(field_name or 'field', 'Invalid URL')
        
        return result


class PhoneValidator(Validator):
    """Phone validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate phone field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            return result
        
        # Basic phone validation (can be enhanced)
        phone_pattern = r'^\+?1?[0-9]{10,15}$'
        if not re.match(phone_pattern, value.replace('-', '').replace(' ', '')):
            result.add_error(field_name or 'field', 'Invalid phone number')
        
        return result


class UUIDValidator(Validator):
    """UUID validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate UUID field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            return result
        
        uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        if not re.match(uuid_pattern, value):
            result.add_error(field_name or 'field', 'Invalid UUID format')
        
        return result


class JSONValidator(Validator):
    """JSON validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate JSON field."""
        result = ValidationResult(is_valid=True)
        
        if isinstance(value, dict):
            return result
        
        if not isinstance(value, str):
            result.add_error(field_name or 'field', 'Must be a JSON object or string')
            return result
        
        try:
            json.loads(value)
        except json.JSONDecodeError:
            result.add_error(field_name or 'field', 'Invalid JSON format')
        
        return result


class CustomValidator(Validator):
    """Custom validator with user-defined validation function."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate using custom function."""
        result = ValidationResult(is_valid=True)
        
        validator_func = self.config.get('validator')
        if not validator_func:
            result.add_error(field_name or 'field', 'Custom validator function not configured')
            return result
        
        try:
            validation_result = validator_func(value, field_name, context)
            if isinstance(validation_result, bool):
                if not validation_result:
                    result.add_error(field_name or 'field', 'Custom validation failed')
            elif isinstance(validation_result, dict):
                if validation_result.get('valid', True):
                    # Add any messages
                    if 'error' in validation_result:
                        result.add_error(field_name or 'field', validation_result['error'])
                    if 'warning' in validation_result:
                        result.add_warning(field_name or 'field', validation_result['warning'])
                    if 'info' in validation_result:
                        result.add_info(field_name or 'field', validation_result['info'])
                else:
                    result.add_error(field_name or 'field', 'Custom validation failed')
            elif isinstance(validation_result, str):
                result.add_error(field_name or 'field', validation_result)
        
        except Exception as e:
            result.add_error(field_name or 'field', f'Custom validation error: {str(e)}')
        
        return result


class BusinessLogicValidator(Validator):
    """Business logic validator."""
    
    def validate(self, value: Any, field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate business logic."""
        result = ValidationResult(is_valid=True)
        
        business_rule = self.config.get('rule')
        if not business_rule:
            return result
        
        try:
            # Execute business rule
            if callable(business_rule):
                rule_result = business_rule(value, field_name, context)
                if not rule_result:
                    rule_message = self.config.get('message', 'Business rule validation failed')
                    result.add_error(field_name or 'field', rule_message)
            else:
                result.add_error(field_name or 'field', 'Business rule must be callable')
        
        except Exception as e:
            result.add_error(field_name or 'field', f'Business logic validation error: {str(e)}')
        
        return result


class DataValidator:
    """
    Main data validator class.
    
    Orchestrates validation of data against
    multiple validation rules.
    """
    
    def __init__(self, rules: List[ValidationRule] = None):
        self.rules = rules or []
        self.validators = self._create_validators()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _create_validators(self) -> Dict[ValidationType, Validator]:
        """Create validator instances."""
        return {
            ValidationType.REQUIRED: RequiredValidator(),
            ValidationType.TYPE_CHECK: TypeValidator(),
            ValidationType.LENGTH: LengthValidator(),
            ValidationType.RANGE: RangeValidator(),
            ValidationType.PATTERN: PatternValidator(),
            ValidationType.EMAIL: EmailValidator(),
            ValidationType.URL: URLValidator(),
            ValidationType.PHONE: PhoneValidator(),
            ValidationType.UUID: UUIDValidator(),
            ValidationType.JSON: JSONValidator(),
            ValidationType.CUSTOM: CustomValidator(),
            ValidationType.BUSINESS_LOGIC: BusinessLogicValidator(),
        }
    
    def add_rule(self, rule: ValidationRule):
        """Add validation rule."""
        self.rules.append(rule)
        self.logger.info(f"Validation rule added: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove validation rule."""
        self.rules = [rule for rule in self.rules if rule.name != rule_name]
        self.logger.info(f"Validation rule removed: {rule_name}")
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate data against all rules.
        
        Args:
            data: Data to validate
            context: Validation context
            
        Returns:
            Validation result
        """
        context = context or {}
        result = ValidationResult(is_valid=True)
        validated_data = data.copy()
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Check conditional validation
            if rule.condition:
                if not self._evaluate_condition(rule.condition, data, context):
                    continue
            
            field_name = rule.field
            field_value = data.get(field_name)
            
            # Check required fields
            if rule.required and field_value is None:
                result.add_error(field_name, rule.message or f'{field_name} is required')
                continue
            
            # Skip validation if field is None and not required
            if field_value is None:
                continue
            
            # Get validator
            validator = self.validators.get(rule.validation_type)
            if not validator:
                result.add_error(field_name, f'Unknown validation type: {rule.validation_type.value}')
                continue
            
            # Configure validator
            validator.config = rule.config
            
            # Validate
            validation_result = validator.validate(field_value, field_name, context)
            
            # Merge results
            result.errors.extend(validation_result.errors)
            result.warnings.extend(validation_result.warnings)
            result.info.extend(validation_result.info)
            
            if validation_result.has_errors():
                result.is_valid = False
            
            # Update validated data
            if validation_result.validated_data:
                validated_data.update(validation_result.validated_data)
        
        result.validated_data = validated_data
        return result
    
    def _evaluate_condition(self, condition: str, data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate conditional validation."""
        try:
            # Simple condition evaluation (can be enhanced)
            field, operator, value = condition.split(' ', 2)
            field_value = data.get(field.strip())
            
            if operator == '==':
                return field_value == value.strip('\'"')
            elif operator == '!=':
                return field_value != value.strip('\'"')
            elif operator == 'in':
                return field_value in eval(value.strip())
            elif operator == 'not_in':
                return field_value not in eval(value.strip())
            
            return True
        
        except Exception:
            return True  # Default to allowing validation
    
    def validate_field(self, field_name: str, value: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate single field.
        
        Args:
            field_name: Field name
            value: Field value
            context: Validation context
            
        Returns:
            Validation result
        """
        field_rules = [rule for rule in self.rules if rule.field == field_name]
        
        if not field_rules:
            return ValidationResult(is_valid=True)
        
        # Create temporary validator with field rules
        temp_validator = DataValidator(field_rules)
        return temp_validator.validate({field_name: value}, context)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validator statistics."""
        return {
            'total_rules': len(self.rules),
            'enabled_rules': len([rule for rule in self.rules if rule.enabled]),
            'rules_by_type': {
                validation_type.value: len([rule for rule in self.rules if rule.validation_type == validation_type])
                for validation_type in ValidationType
            },
            'rules_by_severity': {
                severity.value: len([rule for rule in self.rules if rule.severity == severity])
                for severity in ValidationSeverity
            },
        }


# Factory functions
def create_validator(rules: List[ValidationRule] = None) -> DataValidator:
    """Create data validator."""
    return DataValidator(rules)


def create_validation_rule(name: str, field: str, validation_type: ValidationType,
                         config: Dict[str, Any] = None, required: bool = False,
                         message: str = "", severity: ValidationSeverity = ValidationSeverity.ERROR) -> ValidationRule:
    """Create validation rule."""
    return ValidationRule(
        name=name,
        field=field,
        validation_type=validation_type,
        config=config or {},
        required=required,
        message=message,
        severity=severity
    )


# Convenience functions
def validate_data(data: Dict[str, Any], rules: List[ValidationRule] = None,
                  context: Dict[str, Any] = None) -> ValidationResult:
    """Validate data with rules."""
    validator = create_validator(rules)
    return validator.validate(data, context)


def validate_field(field_name: str, value: Any, validation_type: ValidationType,
                   config: Dict[str, Any] = None, required: bool = False,
                   message: str = "") -> ValidationResult:
    """Validate single field."""
    rule = create_validation_rule(
        name=f"{field_name}_validation",
        field=field_name,
        validation_type=validation_type,
        config=config or {},
        required=required,
        message=message
    )
    
    validator = create_validator([rule])
    return validator.validate_field(field_name, value)


# Predefined validation rules
def create_email_validation(field_name: str, required: bool = False) -> ValidationRule:
    """Create email validation rule."""
    return create_validation_rule(
        name=f"{field_name}_email",
        field=field_name,
        validation_type=ValidationType.EMAIL,
        required=required,
        message="Please enter a valid email address"
    )


def create_phone_validation(field_name: str, required: bool = False) -> ValidationRule:
    """Create phone validation rule."""
    return create_validation_rule(
        name=f"{field_name}_phone",
        field=field_name,
        validation_type=ValidationType.PHONE,
        required=required,
        message="Please enter a valid phone number"
    )


def create_uuid_validation(field_name: str, required: bool = False) -> ValidationRule:
    """Create UUID validation rule."""
    return create_validation_rule(
        name=f"{field_name}_uuid",
        field=field_name,
        validation_type=ValidationType.UUID,
        required=required,
        message="Please enter a valid UUID"
    )


def create_range_validation(field_name: str, min_value: float = None, max_value: float = None,
                           required: bool = False) -> ValidationRule:
    """Create range validation rule."""
    config = {}
    if min_value is not None:
        config['min_value'] = min_value
    if max_value is not None:
        config['max_value'] = max_value
    
    return create_validation_rule(
        name=f"{field_name}_range",
        field=field_name,
        validation_type=ValidationType.RANGE,
        config=config,
        required=required,
        message=f"Value must be between {min_value} and {max_value}"
    )


def create_length_validation(field_name: str, min_length: int = None, max_length: int = None,
                           required: bool = False) -> ValidationRule:
    """Create length validation rule."""
    config = {}
    if min_length is not None:
        config['min_length'] = min_length
    if max_length is not None:
        config['max_length'] = max_length
    
    return create_validation_rule(
        name=f"{field_name}_length",
        field=field_name,
        validation_type=ValidationType.LENGTH,
        config=config,
        required=required,
        message=f"Length must be between {min_length} and {max_length} characters"
    )


def create_pattern_validation(field_name: str, pattern: str, required: bool = False,
                           message: str = "Invalid format") -> ValidationRule:
    """Create pattern validation rule."""
    return create_validation_rule(
        name=f"{field_name}_pattern",
        field=field_name,
        validation_type=ValidationType.PATTERN,
        config={'pattern': pattern},
        required=required,
        message=message
    )


def create_business_validation(field_name: str, rule_func: Callable, message: str = "",
                              required: bool = False) -> ValidationRule:
    """Create business logic validation rule."""
    return create_validation_rule(
        name=f"{field_name}_business",
        field=field_name,
        validation_type=ValidationType.BUSINESS_LOGIC,
        config={'validator': rule_func},
        required=required,
        message=message
    )
