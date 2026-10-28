"""
Data Validator
Comprehensive data validation for integration data
"""

import logging
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import re
import json
from decimal import Decimal

from .integ_exceptions import IntegrationException, DataValidationException

logger = logging.getLogger(__name__)


class ValidationType(Enum):
    """Validation types"""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    FORMAT_CHECK = "format_check"
    RANGE_CHECK = "range_check"
    LENGTH_CHECK = "length_check"
    PATTERN_CHECK = "pattern_check"
    CUSTOM_CHECK = "custom_check"
    BUSINESS_RULE = "business_rule"
    SECURITY_CHECK = "security_check"


class ValidationSeverity(Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DataType(Enum):
    """Data types for validation"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    JSON = "json"
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    PHONE = "phone"
    LIST = "list"
    DICT = "dict"
    ANY = "any"


@dataclass
class ValidationRule:
    """Validation rule definition"""
    rule_id: str
    field_path: str  # Dot notation for nested fields (e.g., "user.profile.name")
    validation_type: ValidationType
    data_type: Optional[DataType] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    priority: int = 5


@dataclass
class ValidationResult:
    """Validation result"""
    is_valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None
    validation_time: float = 0.0
    validator_id: str = ""


@dataclass
class ValidationContext:
    """Validation context"""
    source_system: str
    target_system: Optional[str] = None
    validation_rules: List[ValidationRule] = field(default_factory=list)
    custom_validators: Dict[str, Callable] = field(default_factory=dict)
    strict_mode: bool = True
    stop_on_first_error: bool = False
    max_errors: int = 100


class DataValidator:
    """
    Comprehensive data validator for integration data
    """
    
    def __init__(self):
        self.builtin_validators = self._initialize_builtin_validators()
        self.custom_validators: Dict[str, Callable] = {}
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'total_errors': 0,
            'total_warnings': 0
        }
    
    def _initialize_builtin_validators(self) -> Dict[ValidationType, Callable]:
        """Initialize built-in validators"""
        return {
            ValidationType.REQUIRED: self._validate_required,
            ValidationType.TYPE_CHECK: self._validate_type,
            ValidationType.FORMAT_CHECK: self._validate_format,
            ValidationType.RANGE_CHECK: self._validate_range,
            ValidationType.LENGTH_CHECK: self._validate_length,
            ValidationType.PATTERN_CHECK: self._validate_pattern,
            ValidationType.CUSTOM_CHECK: self._validate_custom,
            ValidationType.BUSINESS_RULE: self._validate_business_rule,
            ValidationType.SECURITY_CHECK: self._validate_security,
        }
    
    def validate(self, data: Any, context: ValidationContext) -> ValidationResult:
        """
        Validate data against rules
        
        Args:
            data: Data to validate
            context: Validation context
            
        Returns:
            Validation result
        """
        start_time = datetime.utcnow()
        
        try:
            # Update statistics
            self.validation_stats['total_validations'] += 1
            
            # Initialize result
            result = ValidationResult(
                is_valid=True,
                validator_id=f"validator_{int(start_time.timestamp())}"
            )
            
            # Convert data to dict if needed
            if isinstance(data, dict):
                validated_data = data.copy()
            else:
                validated_data = {'value': data}
            
            # Sort rules by priority
            sorted_rules = sorted(context.validation_rules, key=lambda r: r.priority)
            
            # Apply validation rules
            for rule in sorted_rules:
                if not rule.enabled:
                    continue
                
                try:
                    # Get field value
                    field_value = self._get_field_value(validated_data, rule.field_path)
                    
                    # Apply validation
                    validation_result = self._apply_validation_rule(
                        field_value, rule, context, validated_data
                    )
                    
                    # Process validation result
                    if not validation_result['is_valid']:
                        result.is_valid = False
                        
                        error_info = {
                            'rule_id': rule.rule_id,
                            'field_path': rule.field_path,
                            'error_message': rule.error_message or validation_result.get('message', 'Validation failed'),
                            'severity': rule.severity.value,
                            'value': field_value,
                            'parameters': rule.parameters
                        }
                        
                        if rule.severity == ValidationSeverity.ERROR or rule.severity == ValidationSeverity.CRITICAL:
                            result.errors.append(error_info)
                            self.validation_stats['total_errors'] += 1
                        elif rule.severity == ValidationSeverity.WARNING:
                            result.warnings.append(error_info)
                            self.validation_stats['total_warnings'] += 1
                        else:
                            result.info.append(error_info)
                        
                        # Stop on first error if configured
                        if context.stop_on_first_error and rule.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                            break
                        
                        # Stop if max errors reached
                        if len(result.errors) >= context.max_errors:
                            break
                    else:
                        # Validation passed, update validated data if needed
                        if 'sanitized_value' in validation_result:
                            self._set_field_value(validated_data, rule.field_path, validation_result['sanitized_value'])
                
                except Exception as e:
                    logger.error(f"Error applying validation rule {rule.rule_id}: {e}")
                    
                    if context.strict_mode:
                        result.is_valid = False
                        result.errors.append({
                            'rule_id': rule.rule_id,
                            'field_path': rule.field_path,
                            'error_message': f"Validation error: {str(e)}",
                            'severity': ValidationSeverity.ERROR.value,
                            'value': None,
                            'parameters': rule.parameters
                        })
            
            # Update result
            result.validated_data = validated_data
            result.validation_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update statistics
            if result.is_valid:
                self.validation_stats['successful_validations'] += 1
            else:
                self.validation_stats['failed_validations'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[{
                    'error_message': f"Validation failed: {str(e)}",
                    'severity': ValidationSeverity.CRITICAL.value
                }],
                validation_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get field value using dot notation"""
        if '.' not in field_path:
            return data.get(field_path)
        
        parts = field_path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def _set_field_value(self, data: Dict[str, Any], field_path: str, value: Any):
        """Set field value using dot notation"""
        if '.' not in field_path:
            data[field_path] = value
            return
        
        parts = field_path.split('.')
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    def _apply_validation_rule(self, value: Any, rule: ValidationRule, 
                             context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a single validation rule"""
        validator = self.builtin_validators.get(rule.validation_type)
        
        if not validator:
            return {'is_valid': False, 'message': f'Unknown validation type: {rule.validation_type}'}
        
        return validator(value, rule, context, data)
    
    def _validate_required(self, value: Any, rule: ValidationRule, 
                          context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required field"""
        is_required = rule.parameters.get('required', True)
        
        if is_required and (value is None or value == ''):
            return {'is_valid': False, 'message': f'Field {rule.field_path} is required'}
        
        return {'is_valid': True}
    
    def _validate_type(self, value: Any, rule: ValidationRule, 
                      context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data type"""
        if value is None and not rule.parameters.get('nullable', False):
            return {'is_valid': False, 'message': f'Field {rule.field_path} cannot be null'}
        
        if value is None:
            return {'is_valid': True}
        
        expected_type = rule.data_type
        if not expected_type:
            return {'is_valid': True}
        
        # Type validation
        if expected_type == DataType.STRING:
            if not isinstance(value, str):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a string'}
        
        elif expected_type == DataType.INTEGER:
            try:
                int(value)
            except (ValueError, TypeError):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be an integer'}
        
        elif expected_type == DataType.FLOAT:
            try:
                float(value)
            except (ValueError, TypeError):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a number'}
        
        elif expected_type == DataType.DECIMAL:
            try:
                Decimal(str(value))
            except (ValueError, TypeError):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a decimal'}
        
        elif expected_type == DataType.BOOLEAN:
            if not isinstance(value, bool):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a boolean'}
        
        elif expected_type == DataType.DATETIME:
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid datetime'}
            elif not isinstance(value, datetime):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a datetime'}
        
        elif expected_type == DataType.EMAIL:
            if not isinstance(value, str) or not self._is_valid_email(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid email'}
        
        elif expected_type == DataType.URL:
            if not isinstance(value, str) or not self._is_valid_url(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid URL'}
        
        elif expected_type == DataType.UUID:
            if not isinstance(value, str) or not self._is_valid_uuid(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid UUID'}
        
        elif expected_type == DataType.LIST:
            if not isinstance(value, list):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a list'}
        
        elif expected_type == DataType.DICT:
            if not isinstance(value, dict):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a dictionary'}
        
        return {'is_valid': True}
    
    def _validate_format(self, value: Any, rule: ValidationRule, 
                        context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data format"""
        if value is None:
            return {'is_valid': True}
        
        format_type = rule.parameters.get('format')
        
        if format_type == 'email':
            if not isinstance(value, str) or not self._is_valid_email(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid email format'}
        
        elif format_type == 'phone':
            if not isinstance(value, str) or not self._is_valid_phone(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid phone format'}
        
        elif format_type == 'date':
            if isinstance(value, str):
                try:
                    datetime.strptime(value, rule.parameters.get('date_format', '%Y-%m-%d'))
                except ValueError:
                    return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid date format'}
        
        elif format_type == 'currency':
            if not isinstance(value, str) or not self._is_valid_currency(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} must be a valid currency format'}
        
        return {'is_valid': True}
    
    def _validate_range(self, value: Any, rule: ValidationRule, 
                       context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate value range"""
        if value is None:
            return {'is_valid': True}
        
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            return {'is_valid': False, 'message': f'Field {rule.field_path} must be numeric for range validation'}
        
        min_value = rule.parameters.get('min')
        max_value = rule.parameters.get('max')
        
        if min_value is not None and numeric_value < min_value:
            return {'is_valid': False, 'message': f'Field {rule.field_path} must be at least {min_value}'}
        
        if max_value is not None and numeric_value > max_value:
            return {'is_valid': False, 'message': f'Field {rule.field_path} must be at most {max_value}'}
        
        return {'is_valid': True}
    
    def _validate_length(self, value: Any, rule: ValidationRule, 
                        context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate value length"""
        if value is None:
            return {'is_valid': True}
        
        if not isinstance(value, (str, list, dict)):
            return {'is_valid': False, 'message': f'Field {rule.field_path} must have a length for validation'}
        
        length = len(value)
        min_length = rule.parameters.get('min_length')
        max_length = rule.parameters.get('max_length')
        
        if min_length is not None and length < min_length:
            return {'is_valid': False, 'message': f'Field {rule.field_path} must be at least {min_length} characters long'}
        
        if max_length is not None and length > max_length:
            return {'is_valid': False, 'message': f'Field {rule.field_path} must be at most {max_length} characters long'}
        
        return {'is_valid': True}
    
    def _validate_pattern(self, value: Any, rule: ValidationRule, 
                         context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pattern matching"""
        if value is None:
            return {'is_valid': True}
        
        if not isinstance(value, str):
            return {'is_valid': False, 'message': f'Field {rule.field_path} must be a string for pattern validation'}
        
        pattern = rule.parameters.get('pattern')
        if not pattern:
            return {'is_valid': True}
        
        try:
            regex = re.compile(pattern)
            if not regex.match(value):
                return {'is_valid': False, 'message': f'Field {rule.field_path} does not match required pattern'}
        except re.error:
            return {'is_valid': False, 'message': f'Invalid pattern in validation rule'}
        
        return {'is_valid': True}
    
    def _validate_custom(self, value: Any, rule: ValidationRule, 
                        context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate using custom validator"""
        validator_name = rule.parameters.get('validator')
        
        if not validator_name:
            return {'is_valid': False, 'message': 'Custom validator name not specified'}
        
        # Get custom validator
        validator = context.custom_validators.get(validator_name) or self.custom_validators.get(validator_name)
        
        if not validator:
            return {'is_valid': False, 'message': f'Custom validator {validator_name} not found'}
        
        try:
            result = validator(value, rule.parameters, data)
            if isinstance(result, bool):
                return {'is_valid': result}
            elif isinstance(result, dict):
                return result
            else:
                return {'is_valid': bool(result)}
        except Exception as e:
            return {'is_valid': False, 'message': f'Custom validator error: {str(e)}'}
    
    def _validate_business_rule(self, value: Any, rule: ValidationRule, 
                               context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate business rules"""
        rule_type = rule.parameters.get('rule_type')
        
        if rule_type == 'conditional':
            condition = rule.parameters.get('condition')
            if not self._evaluate_condition(data, condition):
                return {'is_valid': False, 'message': rule.error_message or 'Business rule condition not met'}
        
        elif rule_type == 'dependency':
            dependency_field = rule.parameters.get('dependency_field')
            dependency_value = rule.parameters.get('dependency_value')
            actual_dependency_value = self._get_field_value(data, dependency_field)
            
            if actual_dependency_value != dependency_value:
                return {'is_valid': False, 'message': f'Dependency field {dependency_field} must have value {dependency_value}'}
        
        elif rule_type == 'uniqueness':
            # This would require database access in a real implementation
            pass
        
        return {'is_valid': True}
    
    def _validate_security(self, value: Any, rule: ValidationRule, 
                          context: ValidationContext, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security rules"""
        if value is None:
            return {'is_valid': True}
        
        if not isinstance(value, str):
            return {'is_valid': True}
        
        security_type = rule.parameters.get('security_type')
        
        if security_type == 'no_sql_injection':
            sql_patterns = rule.parameters.get('sql_patterns', [
                r'\b(union|select|insert|update|delete|drop|create|alter)\b',
                r'[\'";]',
                r'\b(or|and)\s+\d+\s*=\s*\d+',
                r'\b(or|and)\s+\'\w+\'\s*=\s*\'\w+\''
            ])
            
            for pattern in sql_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    return {'is_valid': False, 'message': 'Potential SQL injection detected'}
        
        elif security_type == 'no_xss':
            xss_patterns = rule.parameters.get('xss_patterns', [
                r'<script[^>]*>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
                r'<iframe[^>]*>',
                r'<object[^>]*>',
                r'<embed[^>]*>'
            ])
            
            for pattern in xss_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    return {'is_valid': False, 'message': 'Potential XSS detected'}
        
        elif security_type == 'no_path_traversal':
            path_patterns = rule.parameters.get('path_patterns', [
                r'\.\./',
                r'\.\.\\',
                r'~[^/\\]',
                r'^[a-zA-Z]:\\'
            ])
            
            for pattern in path_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    return {'is_valid': False, 'message': 'Path traversal detected'}
        
        return {'is_valid': True}
    
    def _is_valid_email(self, email: str) -> bool:
        """Check if email is valid"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
        return re.match(pattern, url) is not None
    
    def _is_valid_uuid(self, uuid_str: str) -> bool:
        """Check if UUID is valid"""
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return re.match(pattern, uuid_str, re.IGNORECASE) is not None
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Check if phone number is valid"""
        # Simple phone validation - can be enhanced
        pattern = r'^\+?[\d\s\-\(\)]{10,}$'
        return re.match(pattern, phone) is not None
    
    def _is_valid_currency(self, currency: str) -> bool:
        """Check if currency format is valid"""
        pattern = r'^\$?\d{1,3}(,\d{3})*(\.\d{2})?$'
        return re.match(pattern, currency) is not None
    
    def _evaluate_condition(self, data: Dict[str, Any], condition: str) -> bool:
        """Evaluate a condition against data"""
        # This is a simplified implementation
        # In a real implementation, you'd want a more robust expression evaluator
        
        try:
            # Replace field references with actual values
            for field_path in re.findall(r'\{([^}]+)\}', condition):
                field_value = self._get_field_value(data, field_path)
                condition = condition.replace(f'{{{field_path}}}', repr(field_value))
            
            # Evaluate the condition
            return eval(condition)
        except Exception:
            return False
    
    def add_custom_validator(self, name: str, validator: Callable):
        """Add a custom validator"""
        self.custom_validators[name] = validator
    
    def remove_custom_validator(self, name: str):
        """Remove a custom validator"""
        self.custom_validators.pop(name, None)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics"""
        stats = self.validation_stats.copy()
        
        # Calculate success rate
        if stats['total_validations'] > 0:
            stats['success_rate'] = (stats['successful_validations'] / stats['total_validations']) * 100
        else:
            stats['success_rate'] = 0
        
        # Calculate average errors per validation
        if stats['total_validations'] > 0:
            stats['average_errors_per_validation'] = stats['total_errors'] / stats['total_validations']
        else:
            stats['average_errors_per_validation'] = 0
        
        return stats
    
    def reset_statistics(self):
        """Reset validation statistics"""
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'total_errors': 0,
            'total_warnings': 0
        }


# Export main classes and functions
__all__ = [
    'DataValidator',
    'ValidationRule',
    'ValidationResult',
    'ValidationContext',
    'ValidationType',
    'ValidationSeverity',
    'DataType',
]