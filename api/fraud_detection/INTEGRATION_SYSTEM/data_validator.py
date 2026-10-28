# =============================================================================
# INTEGRATION_SYSTEM/data_validator.py
# =============================================================================
"""
Data Validation for Integrations.

Provides comprehensive validation capabilities for integration
data including schema validation, business rules, and security checks.
"""

from __future__ import annotations

import logging
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator, EmailValidator, RegexValidator

from .integ_exceptions import DataValidationError, DataValidatorError
from .integ_constants import DataFormat

logger = logging.getLogger(__name__)


class ValidationType(Enum):
    """Types of validation."""
    SCHEMA = "schema"
    BUSINESS_RULE = "business_rule"
    SECURITY = "security"
    FORMAT = "format"
    TYPE = "type"
    RANGE = "range"
    PATTERN = "pattern"
    CUSTOM = "custom"


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Validation result information."""
    is_valid: bool
    severity: ValidationSeverity
    message: str
    field_name: Optional[str] = None
    validation_type: ValidationType = ValidationType.CUSTOM
    value: Optional[Any] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'is_valid': self.is_valid,
            'severity': self.severity.value,
            'message': self.message,
            'field_name': self.field_name,
            'validation_type': self.validation_type.value,
            'value': self.value,
            'expected': self.expected,
            'actual': self.actual,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ValidationRule:
    """Validation rule configuration."""
    name: str
    field_name: Optional[str]
    validation_type: ValidationType
    validator_func: Callable[[Any], bool]
    error_message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    required: bool = True
    allow_null: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ValidationSchema:
    """Validation schema configuration."""
    name: str
    version: str
    rules: List[ValidationRule]
    strict_mode: bool = True
    stop_on_first_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


class DataValidator(ABC):
    """
    Abstract base class for data validators.
    """
    
    @abstractmethod
    def validate(self, data: Any, schema: Optional[ValidationSchema] = None) -> List[ValidationResult]:
        """Validate data against schema."""
        pass
    
    @abstractmethod
    def is_supported_format(self, data_format: DataFormat) -> bool:
        """Check if data format is supported."""
        pass


class JSONValidator(DataValidator):
    """JSON data validator."""
    
    def validate(self, data: Any, schema: Optional[ValidationSchema] = None) -> List[ValidationResult]:
        """Validate JSON data."""
        results = []
        
        if not isinstance(data, dict):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Data must be a JSON object (dictionary)",
                validation_type=ValidationType.TYPE,
                actual=type(data).__name__
            ))
            return results
        
        # Apply schema rules if provided
        if schema:
            for rule in schema.rules:
                if not rule.enabled:
                    continue
                
                # Get field value
                field_value = self._get_field_value(data, rule.field_name)
                
                # Check if required field is missing
                if rule.required and field_value is None:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=rule.severity,
                        message=f"Required field '{rule.field_name}' is missing",
                        field_name=rule.field_name,
                        validation_type=rule.validation_type,
                        value=field_value
                    ))
                    continue
                
                # Skip validation if field is null and allowed
                if field_value is None and rule.allow_null:
                    continue
                
                # Apply validation rule
                try:
                    is_valid = rule.validator_func(field_value)
                    if not is_valid:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message,
                            field_name=rule.field_name,
                            validation_type=rule.validation_type,
                            value=field_value
                        ))
                    else:
                        results.append(ValidationResult(
                            is_valid=True,
                            severity=ValidationSeverity.INFO,
                            message=f"Field '{rule.field_name}' validation passed",
                            field_name=rule.field_name,
                            validation_type=rule.validation_type,
                            value=field_value
                        ))
                        
                except Exception as e:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Validation error for field '{rule.field_name}': {str(e)}",
                        field_name=rule.field_name,
                        validation_type=rule.validation_type,
                        value=field_value
                    ))
        
        return results
    
    def is_supported_format(self, data_format: DataFormat) -> bool:
        """Check if data format is supported."""
        return data_format == DataFormat.JSON
    
    def _get_field_value(self, data: Dict[str, Any], field_name: Optional[str]) -> Any:
        """Get field value from data dictionary."""
        if not field_name:
            return data
        
        # Support nested field names (e.g., "user.profile.name")
        keys = field_name.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value


class XMLValidator(DataValidator):
    """XML data validator."""
    
    def validate(self, data: Any, schema: Optional[ValidationSchema] = None) -> List[ValidationResult]:
        """Validate XML data."""
        results = []
        
        # Check if data is XML string
        if isinstance(data, str):
            try:
                root = ET.fromstring(data)
                data = root
            except ET.ParseError as e:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid XML format: {str(e)}",
                    validation_type=ValidationType.FORMAT
                ))
                return results
        
        # Check if data is XML element
        if not isinstance(data, ET.Element):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Data must be an XML element or string",
                validation_type=ValidationType.TYPE,
                actual=type(data).__name__
            ))
            return results
        
        # Apply schema rules if provided
        if schema:
            for rule in schema.rules:
                if not rule.enabled:
                    continue
                
                # Get element value
                element_value = self._get_element_value(data, rule.field_name)
                
                # Check if required element is missing
                if rule.required and element_value is None:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=rule.severity,
                        message=f"Required element '{rule.field_name}' is missing",
                        field_name=rule.field_name,
                        validation_type=rule.validation_type,
                        value=element_value
                    ))
                    continue
                
                # Apply validation rule
                try:
                    is_valid = rule.validator_func(element_value)
                    if not is_valid:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=rule.error_message,
                            field_name=rule.field_name,
                            validation_type=rule.validation_type,
                            value=element_value
                        ))
                        
                except Exception as e:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Validation error for element '{rule.field_name}': {str(e)}",
                        field_name=rule.field_name,
                        validation_type=rule.validation_type,
                        value=element_value
                    ))
        
        return results
    
    def is_supported_format(self, data_format: DataFormat) -> bool:
        """Check if data format is supported."""
        return data_format == DataFormat.XML
    
    def _get_element_value(self, root: ET.Element, field_name: Optional[str]) -> Optional[str]:
        """Get element value from XML tree."""
        if not field_name:
            return root.text
        
        element = root.find(field_name)
        return element.text if element is not None else None


class CSVValidator(DataValidator):
    """CSV data validator."""
    
    def validate(self, data: Any, schema: Optional[ValidationSchema] = None) -> List[ValidationResult]:
        """Validate CSV data."""
        results = []
        
        # Check if data is CSV string or list of dictionaries
        if isinstance(data, str):
            try:
                import csv
                import io
                
                reader = csv.DictReader(io.StringIO(data))
                data = list(reader)
                
            except Exception as e:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid CSV format: {str(e)}",
                    validation_type=ValidationType.FORMAT
                ))
                return results
        
        elif not isinstance(data, list):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Data must be a CSV string or list of dictionaries",
                validation_type=ValidationType.TYPE,
                actual=type(data).__name__
            ))
            return results
        
        # Validate each row
        for i, row in enumerate(data):
            if not isinstance(row, dict):
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Row {i} must be a dictionary",
                    field_name=f"row_{i}",
                    validation_type=ValidationType.TYPE,
                    actual=type(row).__name__
                ))
                continue
            
            # Apply schema rules if provided
            if schema:
                for rule in schema.rules:
                    if not rule.enabled:
                        continue
                    
                    field_value = row.get(rule.field_name)
                    
                    # Check if required field is missing
                    if rule.required and field_value is None:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=rule.severity,
                            message=f"Required field '{rule.field_name}' is missing in row {i}",
                            field_name=rule.field_name,
                            validation_type=rule.validation_type,
                            value=field_value,
                            metadata={'row_index': i}
                        ))
                        continue
                    
                    # Apply validation rule
                    try:
                        is_valid = rule.validator_func(field_value)
                        if not is_valid:
                            results.append(ValidationResult(
                                is_valid=False,
                                severity=rule.severity,
                                message=rule.error_message,
                                field_name=rule.field_name,
                                validation_type=rule.validation_type,
                                value=field_value,
                                metadata={'row_index': i}
                            ))
                            
                    except Exception as e:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            message=f"Validation error for field '{rule.field_name}' in row {i}: {str(e)}",
                            field_name=rule.field_name,
                            validation_type=rule.validation_type,
                            value=field_value,
                            metadata={'row_index': i}
                        ))
        
        return results
    
    def is_supported_format(self, data_format: DataFormat) -> bool:
        """Check if data format is supported."""
        return data_format == DataFormat.CSV


class ValidationEngine:
    """
    Main validation engine for integration data.
    
    Provides comprehensive validation capabilities including
    schema validation, business rules, and security checks.
    """
    
    def __init__(self):
        """Initialize validation engine."""
        self.validators: Dict[DataFormat, DataValidator] = {}
        self.schemas: Dict[str, ValidationSchema] = {}
        self.validation_stats: Dict[str, int] = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'total_errors': 0,
            'total_warnings': 0
        }
        
        # Initialize default validators
        self._initialize_default_validators()
        
        logger.info("ValidationEngine initialized")
    
    def _initialize_default_validators(self) -> None:
        """Initialize default validators."""
        self.validators[DataFormat.JSON] = JSONValidator()
        self.validators[DataFormat.XML] = XMLValidator()
        self.validators[DataFormat.CSV] = CSVValidator()
    
    def register_validator(self, data_format: DataFormat, validator: DataValidator) -> None:
        """Register custom validator."""
        self.validators[data_format] = validator
        logger.info(f"Registered validator for {data_format.value}")
    
    def register_schema(self, schema: ValidationSchema) -> None:
        """Register validation schema."""
        self.schemas[schema.name] = schema
        logger.info(f"Registered validation schema: {schema.name}")
    
    def validate_data(self, data: Any, data_format: DataFormat, 
                      schema_name: Optional[str] = None) -> List[ValidationResult]:
        """
        Validate data against format and schema.
        
        Args:
            data: Data to validate
            data_format: Data format
            schema_name: Optional schema name
            
        Returns:
            List of validation results
        """
        self.validation_stats['total_validations'] += 1
        
        # Get validator for format
        validator = self.validators.get(data_format)
        if not validator:
            error_result = ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"No validator available for {data_format.value} format",
                validation_type=ValidationType.FORMAT
            )
            self.validation_stats['failed_validations'] += 1
            self.validation_stats['total_errors'] += 1
            return [error_result]
        
        # Get schema if specified
        schema = self.schemas.get(schema_name) if schema_name else None
        
        # Validate data
        try:
            results = validator.validate(data, schema)
            
            # Update statistics
            has_errors = any(not r.is_valid and r.severity == ValidationSeverity.ERROR for r in results)
            has_warnings = any(not r.is_valid and r.severity == ValidationSeverity.WARNING for r in results)
            
            if has_errors:
                self.validation_stats['failed_validations'] += 1
                self.validation_stats['total_errors'] += len([r for r in results if not r.is_valid and r.severity == ValidationSeverity.ERROR])
            else:
                self.validation_stats['successful_validations'] += 1
            
            if has_warnings:
                self.validation_stats['total_warnings'] += len([r for r in results if not r.is_valid and r.severity == ValidationSeverity.WARNING])
            
            return results
            
        except Exception as e:
            error_result = ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Validation error: {str(e)}",
                validation_type=ValidationType.CUSTOM
            )
            self.validation_stats['failed_validations'] += 1
            self.validation_stats['total_errors'] += 1
            return [error_result]
    
    def validate_json(self, data: Union[str, Dict[str, Any]], 
                      schema_name: Optional[str] = None) -> List[ValidationResult]:
        """Validate JSON data."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                return [ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid JSON: {str(e)}",
                    validation_type=ValidationType.FORMAT
                )]
        
        return self.validate_data(data, DataFormat.JSON, schema_name)
    
    def validate_xml(self, data: Union[str, ET.Element], 
                     schema_name: Optional[str] = None) -> List[ValidationResult]:
        """Validate XML data."""
        return self.validate_data(data, DataFormat.XML, schema_name)
    
    def validate_csv(self, data: Union[str, List[Dict[str, Any]]], 
                     schema_name: Optional[str] = None) -> List[ValidationResult]:
        """Validate CSV data."""
        return self.validate_data(data, DataFormat.CSV, schema_name)
    
    def create_schema(self, name: str, rules: List[ValidationRule], **kwargs) -> ValidationSchema:
        """Create validation schema."""
        schema = ValidationSchema(
            name=name,
            version=kwargs.get('version', '1.0'),
            rules=rules,
            **kwargs
        )
        self.register_schema(schema)
        return schema
    
    def get_schema(self, name: str) -> Optional[ValidationSchema]:
        """Get validation schema by name."""
        return self.schemas.get(name)
    
    def list_schemas(self) -> List[ValidationSchema]:
        """List all validation schemas."""
        return list(self.schemas.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return {
            **self.validation_stats,
            'success_rate': (self.validation_stats['successful_validations'] / max(self.validation_stats['total_validations'], 1)) * 100,
            'total_schemas': len(self.schemas),
            'total_validators': len(self.validators),
            'supported_formats': [fmt.value for fmt in self.validators.keys()]
        }
    
    def reset_statistics(self) -> None:
        """Reset validation statistics."""
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'total_errors': 0,
            'total_warnings': 0
        }


# Global validation engine instance
_validation_engine = None


def get_validation_engine() -> ValidationEngine:
    """Get global validation engine instance."""
    global _validation_engine
    if _validation_engine is None:
        _validation_engine = ValidationEngine()
    return _validation_engine


# Built-in validation functions
def validate_required(value: Any) -> bool:
    """Validate required field."""
    return value is not None and value != ""


def validate_email(value: Any) -> bool:
    """Validate email format."""
    if not isinstance(value, str):
        return False
    
    validator = EmailValidator()
    try:
        validator(value)
        return True
    except DjangoValidationError:
        return False


def validate_url(value: Any) -> bool:
    """Validate URL format."""
    if not isinstance(value, str):
        return False
    
    validator = URLValidator()
    try:
        validator(value)
        return True
    except DjangoValidationError:
        return False


def validate_numeric(value: Any) -> bool:
    """Validate numeric value."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_integer(value: Any) -> bool:
    """Validate integer value."""
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_positive_number(value: Any) -> bool:
    """Validate positive number."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False


def validate_range(min_val: float, max_val: float) -> Callable[[Any], bool]:
    """Create range validator."""
    def validator(value: Any) -> bool:
        try:
            num = float(value)
            return min_val <= num <= max_val
        except (ValueError, TypeError):
            return False
    
    return validator


def validate_length(min_length: int, max_length: int) -> Callable[[Any], bool]:
    """Create length validator."""
    def validator(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return min_length <= len(value) <= max_length
    
    return validator


def validate_regex(pattern: str) -> Callable[[Any], bool]:
    """Create regex validator."""
    def validator(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return re.match(pattern, value) is not None
    
    return validator


def validate_date_format(format_string: str = "%Y-%m-%d") -> Callable[[Any], bool]:
    """Create date format validator."""
    def validator(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            datetime.strptime(value, format_string)
            return True
        except ValueError:
            return False
    
    return validator


def validate_choices(choices: List[Any]) -> Callable[[Any], bool]:
    """Create choices validator."""
    def validator(value: Any) -> bool:
        return value in choices
    
    return validator


# Convenience functions
def validate_integration_data(data: Any, data_format: DataFormat, 
                            schema_name: Optional[str] = None) -> List[ValidationResult]:
    """
    Convenience function for validating integration data.
    
    Args:
        data: Data to validate
        data_format: Data format
        schema_name: Optional schema name
        
    Returns:
        List of validation results
    """
    engine = get_validation_engine()
    return engine.validate_data(data, data_format, schema_name)


def create_common_schema(name: str) -> ValidationSchema:
    """
    Create common validation schema.
    
    Args:
        name: Schema name
        
    Returns:
        Validation schema with common rules
    """
    engine = get_validation_engine()
    
    rules = [
        ValidationRule(
            name="email_required",
            field_name="email",
            validation_type=ValidationType.FORMAT,
            validator_func=validate_email,
            error_message="Invalid email format",
            required=True
        ),
        ValidationRule(
            name="id_required",
            field_name="id",
            validation_type=ValidationType.TYPE,
            validator_func=validate_required,
            error_message="ID is required",
            required=True
        ),
        ValidationRule(
            name="created_at_format",
            field_name="created_at",
            validation_type=ValidationType.FORMAT,
            validator_func=validate_date_format("%Y-%m-%dT%H:%M:%S"),
            error_message="Invalid datetime format (expected: YYYY-MM-DDTHH:MM:SS)",
            required=False,
            allow_null=True
        )
    ]
    
    return engine.create_schema(name, rules)
