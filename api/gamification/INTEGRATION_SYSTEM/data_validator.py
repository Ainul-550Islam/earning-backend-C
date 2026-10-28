"""
Data Validator — Comprehensive data validation system.

This module provides extensive data validation capabilities for
ensuring data integrity, format compliance, and business rules.
"""

from __future__ import annotations

import logging
import re
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import (
    IntegrationError, ValidationError, DataFormatError,
    DataCorruptionError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Types
# ---------------------------------------------------------------------------

class ValidationType(Enum):
    """Validation type enumeration."""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    FORMAT_CHECK = "format_check"
    LENGTH_CHECK = "length_check"
    RANGE_CHECK = "range_check"
    PATTERN_CHECK = "pattern_check"
    ENUM_CHECK = "enum_check"
    CUSTOM = "custom"
    SCHEMA = "schema"
    BUSINESS_RULE = "business_rule"
    INTEGRITY_CHECK = "integrity_check"


class ValidationSeverity(Enum):
    """Validation severity enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DataType(Enum):
    """Data type enumeration."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    JSON = "json"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


# ---------------------------------------------------------------------------
# Validation Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ValidationRule:
    """Validation rule definition."""
    
    id: str
    name: str
    type: ValidationType
    field_path: str  # JSON path or field name
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    custom_validator: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "field_path": self.field_path,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "parameters": self.parameters,
            "error_message": self.error_message,
            "custom_validator": self.custom_validator.__name__ if self.custom_validator else None,
            "metadata": self.metadata
        }


@dataclass
class ValidationError:
    """Validation error result."""
    
    rule_id: str
    field_path: str
    severity: ValidationSeverity
    message: str
    actual_value: Any = None
    expected_value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "field_path": self.field_path,
            "severity": self.severity.value,
            "message": self.message,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ValidationResult:
    """Result of data validation."""
    
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    info: List[ValidationError] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0
    
    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return len(self.errors) + len(self.warnings) + len(self.info)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "info": [info.to_dict() for info in self.info],
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "total_issues": self.total_issues,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class ValidationSchema:
    """Validation schema definition."""
    
    id: str
    name: str
    version: str = "1.0.0"
    rules: List[ValidationRule] = field(default_factory=list)
    strict_mode: bool = True
    allow_unknown_fields: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "rules": [rule.to_dict() for rule in self.rules],
            "strict_mode": self.strict_mode,
            "allow_unknown_fields": self.allow_unknown_fields,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ---------------------------------------------------------------------------
# Abstract Validator Base Class
# ---------------------------------------------------------------------------

class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    @abstractmethod
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate data against a rule."""
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[ValidationType]:
        """Get supported validation types."""
        pass


# ---------------------------------------------------------------------------
# Built-in Validators
# ---------------------------------------------------------------------------

class RequiredValidator(BaseValidator):
    """Validator for required fields."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate required field."""
        value = self._get_field_value(data, rule.field_path)
        
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' is required",
                actual_value=value
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.REQUIRED]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class TypeValidator(BaseValidator):
    """Validator for data type checking."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate data type."""
        value = self._get_field_value(data, rule.field_path)
        expected_type = rule.parameters.get("type")
        
        if not expected_type:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message="Type validator requires 'type' parameter"
            )
        
        type_mapping = {
            DataType.STRING: str,
            DataType.INTEGER: int,
            DataType.FLOAT: (int, float),
            DataType.BOOLEAN: bool,
            DataType.ARRAY: list,
            DataType.OBJECT: dict,
            DataType.NULL: type(None)
        }
        
        expected_python_type = type_mapping.get(DataType(expected_type))
        if not expected_python_type:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message=f"Unknown data type: {expected_type}"
            )
        
        if value is not None and not isinstance(value, expected_python_type):
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' must be of type {expected_type}",
                actual_value=type(value).__name__,
                expected_value=expected_type
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.TYPE_CHECK]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class LengthValidator(BaseValidator):
    """Validator for string/array length checking."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate length."""
        value = self._get_field_value(data, rule.field_path)
        
        if value is None:
            return None
        
        min_length = rule.parameters.get("min_length")
        max_length = rule.parameters.get("max_length")
        
        length = len(value) if hasattr(value, '__len__') else 0
        
        if min_length is not None and length < min_length:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' must be at least {min_length} characters",
                actual_value=length,
                expected_value=f">= {min_length}"
            )
        
        if max_length is not None and length > max_length:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' must be at most {max_length} characters",
                actual_value=length,
                expected_value=f"<= {max_length}"
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.LENGTH_CHECK]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class RangeValidator(BaseValidator):
    """Validator for numeric range checking."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate numeric range."""
        value = self._get_field_value(data, rule.field_path)
        
        if value is None:
            return None
        
        if not isinstance(value, (int, float)):
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message=f"Field '{rule.field_path}' must be numeric for range validation",
                actual_value=type(value).__name__
            )
        
        min_value = rule.parameters.get("min_value")
        max_value = rule.parameters.get("max_value")
        
        if min_value is not None and value < min_value:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' must be at least {min_value}",
                actual_value=value,
                expected_value=f">= {min_value}"
            )
        
        if max_value is not None and value > max_value:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' must be at most {max_value}",
                actual_value=value,
                expected_value=f"<= {max_value}"
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.RANGE_CHECK]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class PatternValidator(BaseValidator):
    """Validator for pattern matching."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate pattern."""
        value = self._get_field_value(data, rule.field_path)
        
        if value is None:
            return None
        
        pattern = rule.parameters.get("pattern")
        if not pattern:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message="Pattern validator requires 'pattern' parameter"
            )
        
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid regex pattern: {e}"
            )
        
        if not isinstance(value, str):
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message=f"Field '{rule.field_path}' must be a string for pattern validation",
                actual_value=type(value).__name__
            )
        
        if not regex.match(value):
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' does not match required pattern",
                actual_value=value,
                expected_value=pattern
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.PATTERN_CHECK]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class EnumValidator(BaseValidator):
    """Validator for enum value checking."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate enum value."""
        value = self._get_field_value(data, rule.field_path)
        
        if value is None:
            return None
        
        allowed_values = rule.parameters.get("values")
        if not allowed_values:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message="Enum validator requires 'values' parameter"
            )
        
        if value not in allowed_values:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=rule.severity,
                message=rule.error_message or f"Field '{rule.field_path}' must be one of: {allowed_values}",
                actual_value=value,
                expected_value=allowed_values
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.ENUM_CHECK]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class CustomValidator(BaseValidator):
    """Validator for custom validation logic."""
    
    def validate(self, data: Any, rule: ValidationRule) -> Optional[ValidationError]:
        """Validate using custom function."""
        if not rule.custom_validator:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message="Custom validator requires a validation function"
            )
        
        try:
            value = self._get_field_value(data, rule.field_path)
            is_valid = rule.custom_validator(value, rule.parameters)
            
            if not is_valid:
                return ValidationError(
                    rule_id=rule.id,
                    field_path=rule.field_path,
                    severity=rule.severity,
                    message=rule.error_message or f"Field '{rule.field_path}' failed custom validation",
                    actual_value=value
                )
        
        except Exception as e:
            return ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.ERROR,
                message=f"Custom validation error: {str(e)}"
            )
        
        return None
    
    def get_supported_types(self) -> List[ValidationType]:
        return [ValidationType.CUSTOM]
    
    def _get_field_value(self, data: Any, field_path: str) -> Any:
        """Get field value from data using dot notation."""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


# ---------------------------------------------------------------------------
# Validation Engine
# ---------------------------------------------------------------------------

class ValidationEngine:
    """Engine for validating data against schemas."""
    
    def __init__(self):
        self.validators: Dict[ValidationType, BaseValidator] = {}
        self.schemas: Dict[str, ValidationSchema] = {}
        self.logger = logging.getLogger(__name__)
        
        # Register built-in validators
        self._register_builtin_validators()
    
    def _register_builtin_validators(self) -> None:
        """Register built-in validators."""
        validators = [
            RequiredValidator(),
            TypeValidator(),
            LengthValidator(),
            RangeValidator(),
            PatternValidator(),
            EnumValidator(),
            CustomValidator()
        ]
        
        for validator in validators:
            for validation_type in validator.get_supported_types():
                self.validators[validation_type] = validator
    
    def register_validator(self, validator: BaseValidator) -> None:
        """Register a custom validator."""
        for validation_type in validator.get_supported_types():
            self.validators[validation_type] = validator
            self.logger.info(f"Registered validator for type: {validation_type.value}")
    
    def register_schema(self, schema: ValidationSchema) -> None:
        """Register a validation schema."""
        self.schemas[schema.id] = schema
        self.logger.info(f"Registered validation schema: {schema.id}")
    
    def validate_data(self, data: Any, schema_id: str) -> ValidationResult:
        """Validate data against a schema."""
        import time
        start_time = time.time()
        
        schema = self.schemas.get(schema_id)
        if not schema:
            raise IntegrationError(f"Validation schema '{schema_id}' not found")
        
        result = ValidationResult(valid=True)
        
        try:
            # Validate against all rules
            for rule in schema.rules:
                if not rule.enabled:
                    continue
                
                validator = self.validators.get(rule.type)
                if not validator:
                    self.logger.warning(f"No validator found for rule type: {rule.type.value}")
                    continue
                
                validation_error = validator.validate(data, rule)
                if validation_error:
                    if validation_error.severity == ValidationSeverity.ERROR:
                        result.errors.append(validation_error)
                        result.valid = False
                    elif validation_error.severity == ValidationSeverity.WARNING:
                        result.warnings.append(validation_error)
                    else:
                        result.info.append(validation_error)
            
            # Check for unknown fields in strict mode
            if schema.strict_mode and not schema.allow_unknown_fields:
                unknown_fields = self._find_unknown_fields(data, schema)
                for field in unknown_fields:
                    error = ValidationError(
                        rule_id="unknown_field",
                        field_path=field,
                        severity=ValidationSeverity.ERROR,
                        message=f"Unknown field: {field}"
                    )
                    result.errors.append(error)
                    result.valid = False
        
        except Exception as e:
            result.valid = False
            result.errors.append(ValidationError(
                rule_id="validation_error",
                field_path="root",
                severity=ValidationSeverity.CRITICAL,
                message=f"Validation engine error: {str(e)}"
            ))
        
        result.execution_time = time.time() - start_time
        return result
    
    def validate_field(self, data: Any, rule: ValidationRule) -> ValidationResult:
        """Validate a single field against a rule."""
        import time
        start_time = time.time()
        
        result = ValidationResult(valid=True)
        
        try:
            validator = self.validators.get(rule.type)
            if not validator:
                result.valid = False
                result.errors.append(ValidationError(
                    rule_id=rule.id,
                    field_path=rule.field_path,
                    severity=ValidationSeverity.ERROR,
                    message=f"No validator found for rule type: {rule.type.value}"
                ))
                return result
            
            validation_error = validator.validate(data, rule)
            if validation_error:
                if validation_error.severity == ValidationSeverity.ERROR:
                    result.errors.append(validation_error)
                    result.valid = False
                elif validation_error.severity == ValidationSeverity.WARNING:
                    result.warnings.append(validation_error)
                else:
                    result.info.append(validation_error)
        
        except Exception as e:
            result.valid = False
            result.errors.append(ValidationError(
                rule_id=rule.id,
                field_path=rule.field_path,
                severity=ValidationSeverity.CRITICAL,
                message=f"Field validation error: {str(e)}"
            ))
        
        result.execution_time = time.time() - start_time
        return result
    
    def _find_unknown_fields(self, data: Any, schema: ValidationSchema) -> List[str]:
        """Find unknown fields in data."""
        if not isinstance(data, dict):
            return []
        
        # Get all known field paths
        known_fields = set()
        for rule in schema.rules:
            known_fields.add(rule.field_path.split('.')[0])
        
        # Find unknown fields
        unknown_fields = []
        for key in data.keys():
            if key not in known_fields:
                unknown_fields.append(key)
        
        return unknown_fields
    
    def get_schema(self, schema_id: str) -> Optional[ValidationSchema]:
        """Get a validation schema."""
        return self.schemas.get(schema_id)
    
    def list_schemas(self) -> List[ValidationSchema]:
        """List all registered schemas."""
        return list(self.schemas.values())


# Global validation engine instance
validation_engine = ValidationEngine()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_validation_rule(
    rule_id: str,
    name: str,
    validation_type: ValidationType,
    field_path: str,
    **kwargs: Any
) -> ValidationRule:
    """Create a validation rule."""
    return ValidationRule(
        id=rule_id,
        name=name,
        type=validation_type,
        field_path=field_path,
        **kwargs
    )


def create_validation_schema(
    schema_id: str,
    name: str,
    rules: List[ValidationRule],
    **kwargs: Any
) -> ValidationSchema:
    """Create a validation schema."""
    schema = ValidationSchema(
        id=schema_id,
        name=name,
        rules=rules,
        **kwargs
    )
    
    validation_engine.register_schema(schema)
    return schema


def validate_data(data: Any, schema_id: str) -> ValidationResult:
    """Validate data against a schema."""
    return validation_engine.validate_data(data, schema_id)


def validate_field(data: Any, rule: ValidationRule) -> ValidationResult:
    """Validate a field against a rule."""
    return validation_engine.validate_field(data, rule)


# Initialize logging
logger.info("Data validator module initialized")
