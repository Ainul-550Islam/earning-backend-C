"""
validator.py – Advanced validation system for postback module.

Provides comprehensive validation capabilities including:
- Custom validation rules and schemas
- Conditional validation logic
- Validation result aggregation
- Real-time validation monitoring
"""
from django.core.cache import cache
import logging
import json
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.core.validators import RegexValidator, EmailValidator, URLValidator

from .models import PostbackLog, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """
    Validation result containing validation status and details.
    
    Provides comprehensive information about validation outcomes
    including errors, warnings, and recommendations.
    """
    is_valid: bool = True
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated_at: datetime = field(default_factory=timezone.now)
    validator_name: str = ""
    
    def add_error(self, message: str, field: str = None, code: str = None, severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Add an error to the validation result."""
        error_data = {
            'message': message,
            'field': field,
            'code': code,
            'severity': severity.value,
            'timestamp': timezone.now().isoformat(),
        }
        self.errors.append(error_data)
        self.is_valid = False
    
    def add_warning(self, message: str, field: str = None, code: str = None):
        """Add a warning to the validation result."""
        warning_data = {
            'message': message,
            'field': field,
            'code': code,
            'timestamp': timezone.now().isoformat(),
        }
        self.warnings.append(warning_data)
    
    def add_info(self, message: str, field: str = None, code: str = None):
        """Add informational message to the validation result."""
        info_data = {
            'message': message,
            'field': field,
            'code': code,
            'timestamp': timezone.now().isoformat(),
        }
        self.info.append(info_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
            'metadata': self.metadata,
            'validated_at': self.validated_at.isoformat(),
            'validator_name': self.validator_name,
        }


class BaseValidator:
    """
    Base validator class for postback validation.
    
    Provides common functionality for all validators including
    error handling, result management, and configuration.
    """
    
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.validation_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_validation = None
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate data and return validation result.
        
        Args:
            data: Data to validate
            context: Additional validation context
            
        Returns:
            ValidationResult instance
        """
        if not self.enabled:
            result = ValidationResult(validator_name=self.name)
            result.add_info("Validator is disabled")
            return result
        
        start_time = timezone.now()
        self.validation_count += 1
        
        try:
            result = self._validate_data(data, context or {})
            result.validator_name = self.name
            
            # Update statistics
            if result.is_valid:
                self.success_count += 1
            else:
                self.failure_count += 1
            
            self.last_validation = timezone.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in validator {self.name}: {str(e)}")
            
            result = ValidationResult(validator_name=self.name, is_valid=False)
            result.add_error(f"Validation error: {str(e)}", severity=ValidationSeverity.CRITICAL)
            
            self.failure_count += 1
            self.last_validation = timezone.now()
            
            return result
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        """
        Internal validation method to be overridden by subclasses.
        
        Args:
            data: Data to validate
            context: Validation context
            
        Returns:
            ValidationResult instance
        """
        raise NotImplementedError("Validator must implement _validate_data method")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validator statistics."""
        success_rate = (self.success_count / self.validation_count * 100) if self.validation_count > 0 else 0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'validation_count': self.validation_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': f"{success_rate:.2f}%",
            'last_validation': self.last_validation.isoformat() if self.last_validation else None,
        }
    
    def enable(self):
        """Enable the validator."""
        self.enabled = True
        logger.info(f"Validator {self.name} enabled")
    
    def disable(self):
        """Disable the validator."""
        self.enabled = False
        logger.info(f"Validator {self.name} disabled")


class RequiredFieldsValidator(BaseValidator):
    """Validator for required fields."""
    
    def __init__(self, required_fields: List[str], name: str = "required_fields_validator"):
        super().__init__(name)
        self.required_fields = required_fields
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        for field in self.required_fields:
            if field not in data or data[field] is None or data[field] == "":
                result.add_error(f"Required field '{field}' is missing or empty", field=field, code="required")
        
        return result


class DataTypeValidator(BaseValidator):
    """Validator for data types."""
    
    def __init__(self, field_types: Dict[str, type], name: str = "data_type_validator"):
        super().__init__(name)
        self.field_types = field_types
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        for field, expected_type in self.field_types.items():
            if field in data and data[field] is not None:
                try:
                    # Handle special cases
                    if expected_type == int:
                        int(data[field])
                    elif expected_type == float:
                        float(data[field])
                    elif expected_type == bool:
                        bool(data[field])
                    elif expected_type == str:
                        str(data[field])
                    elif expected_type == list:
                        list(data[field])
                    elif expected_type == dict:
                        dict(data[field])
                    else:
                        # Try to cast to expected type
                        expected_type(data[field])
                        
                except (ValueError, TypeError):
                    result.add_error(
                        f"Field '{field}' must be of type {expected_type.__name__}",
                        field=field,
                        code="type_mismatch"
                    )
        
        return result


class RegexValidator(BaseValidator):
    """Validator for regex patterns."""
    
    def __init__(self, field_patterns: Dict[str, str], name: str = "regex_validator"):
        super().__init__(name)
        self.field_patterns = field_patterns
        self.validators = {
            field: RegexValidator(pattern=pattern)
            for field, pattern in field_patterns.items()
        }
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        for field, validator in self.validators.items():
            if field in data and data[field] is not None:
                try:
                    validator(str(data[field]))
                except DjangoValidationError:
                    result.add_error(
                        f"Field '{field}' does not match required pattern",
                        field=field,
                        code="regex_mismatch"
                    )
        
        return result


class RangeValidator(BaseValidator):
    """Validator for numeric ranges."""
    
    def __init__(self, field_ranges: Dict[str, Dict[str, Any]], name: str = "range_validator"):
        super().__init__(name)
        self.field_ranges = field_ranges
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        for field, range_config in self.field_ranges.items():
            if field in data and data[field] is not None:
                try:
                    value = float(data[field])
                    
                    min_value = range_config.get('min')
                    max_value = range_config.get('max')
                    
                    if min_value is not None and value < min_value:
                        result.add_error(
                            f"Field '{field}' must be at least {min_value}",
                            field=field,
                            code="min_value"
                        )
                    
                    if max_value is not None and value > max_value:
                        result.add_error(
                            f"Field '{field}' must be at most {max_value}",
                            field=field,
                            code="max_value"
                        )
                        
                except (ValueError, TypeError):
                    result.add_error(
                        f"Field '{field}' must be a number for range validation",
                        field=field,
                        code="numeric_required"
                    )
        
        return result


class ConditionalValidator(BaseValidator):
    """Validator with conditional logic."""
    
    def __init__(self, conditions: List[Dict[str, Any]], name: str = "conditional_validator"):
        super().__init__(name)
        self.conditions = conditions
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        for condition in self.conditions:
            if self._evaluate_condition(condition, data, context):
                # Apply validation rule
                validation_rule = condition.get('validation')
                if validation_rule:
                    self._apply_validation_rule(validation_rule, data, result)
        
        return result
    
    def _evaluate_condition(self, condition: Dict[str, Any], data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate if condition is met."""
        condition_type = condition.get('type')
        
        if condition_type == 'field_exists':
            field = condition.get('field')
            return field in data and data[field] is not None
        
        elif condition_type == 'field_equals':
            field = condition.get('field')
            value = condition.get('value')
            return field in data and data[field] == value
        
        elif condition_type == 'field_in':
            field = condition.get('field')
            values = condition.get('values', [])
            return field in data and data[field] in values
        
        elif condition_type == 'custom':
            # Custom condition function
            condition_func = condition.get('function')
            if condition_func:
                return condition_func(data, context)
        
        return False
    
    def _apply_validation_rule(self, rule: Dict[str, Any], data: Dict[str, Any], result: ValidationResult):
        """Apply validation rule to data."""
        rule_type = rule.get('type')
        
        if rule_type == 'required_field':
            field = rule.get('field')
            if field not in data or data[field] is None or data[field] == "":
                result.add_error(f"Field '{field}' is required when condition is met", field=field, code="conditional_required")
        
        elif rule_type == 'custom':
            # Custom validation function
            validation_func = rule.get('function')
            if validation_func:
                try:
                    validation_result = validation_func(data)
                    if not validation_result:
                        result.add_error(f"Custom validation failed for condition", code="custom_validation")
                except Exception as e:
                    result.add_error(f"Custom validation error: {str(e)}", code="custom_validation_error")


class PostbackValidator(BaseValidator):
    """Specialized validator for postback data."""
    
    def __init__(self, network_config: NetworkPostbackConfig = None, name: str = "postback_validator"):
        super().__init__(name)
        self.network_config = network_config
    
    def _validate_data(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        # Validate required postback fields
        required_fields = ['network_key', 'lead_id']
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == "":
                result.add_error(f"Required postback field '{field}' is missing", field=field, code="postback_required")
        
        # Validate network configuration if available
        if self.network_config:
            self._validate_network_config(data, result)
        
        # Validate lead ID format
        if 'lead_id' in data and data['lead_id']:
            if not isinstance(data['lead_id'], str) or len(str(data['lead_id'])) < 3:
                result.add_error("Lead ID must be a string with at least 3 characters", field='lead_id', code="lead_id_format")
        
        # Validate payout amount if present
        if 'payout' in data and data['payout'] is not None:
            try:
                payout = float(data['payout'])
                if payout < 0:
                    result.add_error("Payout amount cannot be negative", field='payout', code="payout_negative")
                elif payout > 10000:  # Reasonable upper limit
                    result.add_warning("Payout amount seems unusually high", field='payout', code="payout_high")
            except (ValueError, TypeError):
                result.add_error("Payout must be a valid number", field='payout', code="payout_invalid")
        
        return result
    
    def _validate_network_config(self, data: Dict[str, Any], result: ValidationResult):
        """Validate against network configuration."""
        # Check if network is active
        if not self.network_config.is_active:
            result.add_error("Network is not active", code="network_inactive")
        
        # Validate required fields for this network
        if self.network_config.required_fields:
            for field in self.network_config.required_fields:
                if field not in data or data[field] is None or data[field] == "":
                    result.add_error(f"Required field '{field}' for network {self.network_config.network_key} is missing", 
                                field=field, code="network_required")
        
        # Validate payout limits
        if 'payout' in data and data['payout'] is not None:
            try:
                payout = float(data['payout'])
                if self.network_config.max_payout and payout > self.network_config.max_payout:
                    result.add_error(f"Payout exceeds maximum allowed amount of {self.network_config.max_payout}", 
                                field='payout', code="payout_exceeds_max")
            except (ValueError, TypeError):
                pass  # Already handled in main validation


class ValidationEngine:
    """
    Validation engine for managing and executing multiple validators.
    
    Provides centralized validation management with result
    aggregation and performance monitoring.
    """
    
    def __init__(self):
        self.validators: Dict[str, BaseValidator] = {}
        self.validation_history = []
        self.enabled = True
    
    def add_validator(self, validator: BaseValidator):
        """
        Add a validator to the engine.
        
        Args:
            validator: Validator instance to add
        """
        self.validators[validator.name] = validator
        logger.info(f"Added validator: {validator.name}")
    
    def remove_validator(self, validator_name: str):
        """
        Remove a validator from the engine.
        
        Args:
            validator_name: Name of validator to remove
        """
        if validator_name in self.validators:
            del self.validators[validator_name]
            logger.info(f"Removed validator: {validator_name}")
        else:
            logger.warning(f"Validator {validator_name} not found")
    
    def validate(self, data: Dict[str, Any], validator_names: List[str] = None, context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate data using specified validators.
        
        Args:
            data: Data to validate
            validator_names: Specific validators to use (None = all)
            context: Additional validation context
            
        Returns:
            Aggregated validation result
        """
        if not self.enabled:
            result = ValidationResult(validator_name="validation_engine")
            result.add_info("Validation engine is disabled")
            return result
        
        start_time = timezone.now()
        validation_id = self._generate_validation_id()
        
        try:
            # Determine which validators to use
            if validator_names:
                validators_to_use = [
                    self.validators[name] for name in validator_names
                    if name in self.validators
                ]
            else:
                validators_to_use = list(self.validators.values())
            
            if not validators_to_use:
                result = ValidationResult(validator_name="validation_engine")
                result.add_warning("No validators available")
                return result
            
            # Execute validators
            aggregated_result = ValidationResult(validator_name="validation_engine")
            
            for validator in validators_to_use:
                validator_result = validator.validate(data, context)
                
                # Aggregate results
                aggregated_result.errors.extend(validator_result.errors)
                aggregated_result.warnings.extend(validator_result.warnings)
                aggregated_result.info.extend(validator_result.info)
                
                # Update metadata
                aggregated_result.metadata[f'validator_{validator.name}'] = validator_result.to_dict()
            
            # Determine overall validity
            aggregated_result.is_valid = len(aggregated_result.errors) == 0
            
            # Record validation
            self._record_validation(validation_id, data, aggregated_result, (timezone.now() - start_time).total_seconds())
            
            return aggregated_result
            
        except Exception as e:
            logger.error(f"Error in validation engine: {str(e)}")
            
            result = ValidationResult(validator_name="validation_engine", is_valid=False)
            result.add_error(f"Validation engine error: {str(e)}", severity=ValidationSeverity.CRITICAL)
            
            return result
    
    def get_validator(self, validator_name: str) -> Optional[BaseValidator]:
        """Get a validator by name."""
        return self.validators.get(validator_name)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validation engine statistics."""
        return {
            'total_validators': len(self.validators),
            'enabled_validators': len([v for v in self.validators.values() if v.enabled]),
            'validator_stats': {
                name: validator.get_statistics()
                for name, validator in self.validators.items()
            },
            'validation_history_count': len(self.validation_history),
            'enabled': self.enabled,
        }
    
    def enable_all(self):
        """Enable all validators."""
        for validator in self.validators.values():
            validator.enable()
        
        self.enabled = True
        logger.info("All validators enabled")
    
    def disable_all(self):
        """Disable all validators."""
        for validator in self.validators.values():
            validator.disable()
        
        self.enabled = False
        logger.info("All validators disabled")
    
    def _generate_validation_id(self) -> str:
        """Generate unique validation ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _record_validation(self, validation_id: str, data: Dict[str, Any], result: ValidationResult, execution_time: float):
        """Record validation details."""
        validation_record = {
            'validation_id': validation_id,
            'data_hash': self._hash_data(data),
            'result': result.to_dict(),
            'execution_time': execution_time,
            'timestamp': timezone.now().isoformat(),
        }
        
        self.validation_history.append(validation_record)
        
        # Keep only last 100 validations
        if len(self.validation_history) > 100:
            self.validation_history = self.validation_history[-100:]
        
        # Cache validation record
        cache_key = f"validation_{validation_id}"
        cache.set(cache_key, validation_record, timeout=3600)  # 1 hour
    
    def _hash_data(self, data: Dict[str, Any]) -> str:
        """Generate hash of data for identification."""
        import hashlib
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()


# Global validation engine instance
validation_engine = ValidationEngine()


# Convenience functions
def validate_postback(data: Dict[str, Any], network_config: NetworkPostbackConfig = None) -> ValidationResult:
    """Validate postback data using standard validators."""
    # Create postback-specific validator
    postback_validator = PostbackValidator(network_config)
    
    # Add standard validators
    required_validator = RequiredFieldsValidator(['network_key', 'lead_id'])
    type_validator = DataTypeValidator({
        'payout': (int, float),
        'network_key': str,
        'lead_id': str,
    })
    
    # Temporarily add validators
    validation_engine.add_validator(postback_validator)
    validation_engine.add_validator(required_validator)
    validation_engine.add_validator(type_validator)
    
    try:
        result = validation_engine.validate(data)
        return result
    finally:
        # Clean up temporary validators
        validation_engine.remove_validator(postback_validator.name)
        validation_engine.remove_validator(required_validator.name)
        validation_engine.remove_validator(type_validator.name)


def get_validation_statistics() -> Dict[str, Any]:
    """Get validation system statistics."""
    return validation_engine.get_statistics()


# Validation system initialization
def initialize_validation_system():
    """Initialize the validation system."""
    try:
        # Add built-in validators
        # (Validators are added on-demand in convenience functions)
        logger.info("Validation system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing validation system: {str(e)}")
