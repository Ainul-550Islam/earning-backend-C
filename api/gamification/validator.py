"""
Gamification Validator — Validation utilities for gamification module.

This module provides comprehensive validation functions and classes for
gamification data validation, business rules, and data integrity checks.
"""

from __future__ import annotations
from functools import wraps

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union, Callable
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError
from api.gamification.constants import (
    MIN_POINTS_VALUE, MAX_POINTS_VALUE, MAX_RANK_VALUE,
    MAX_CONTEST_NAME_LENGTH, MAX_REWARD_TITLE_LENGTH,
    MAX_ACHIEVEMENT_TITLE_LENGTH, MAX_DESCRIPTION_LENGTH,
    MAX_META_JSON_SIZE_BYTES
)

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the result."""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'metadata': self.metadata
        }


class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a value."""
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class PointsValidator(BaseValidator):
    """Validator for points values."""
    
    def __init__(self, min_value: int = MIN_POINTS_VALUE, max_value: int = MAX_POINTS_VALUE):
        super().__init__("PointsValidator")
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate points value."""
        result = ValidationResult(is_valid=True)
        
        try:
            # Convert to Decimal for precision
            if isinstance(value, str):
                points = Decimal(value)
            elif isinstance(value, (int, float)):
                points = Decimal(str(value))
            elif isinstance(value, Decimal):
                points = value
            else:
                result.add_error("Points must be a number")
                return result
            
            # Check range
            if points < self.min_value:
                result.add_error(f"Points cannot be less than {self.min_value}")
            
            if points > self.max_value:
                result.add_error(f"Points cannot exceed {self.max_value}")
            
            # Check for decimal places
            if points != points.to_integral_value():
                result.add_warning("Points should be whole numbers")
            
            result.add_metadata('validated_points', float(points))
            
        except (InvalidOperation, ValueError) as e:
            result.add_error(f"Invalid points format: {e}")
        
        return result


class RankValidator(BaseValidator):
    """Validator for rank values."""
    
    def __init__(self, min_value: int = 1, max_value: int = MAX_RANK_VALUE):
        super().__init__("RankValidator")
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate rank value."""
        result = ValidationResult(is_valid=True)
        
        try:
            rank = int(value)
            
            if rank < self.min_value:
                result.add_error(f"Rank cannot be less than {self.min_value}")
            
            if rank > self.max_value:
                result.add_error(f"Rank cannot exceed {self.max_value}")
            
            result.add_metadata('validated_rank', rank)
            
        except (ValueError, TypeError):
            result.add_error("Rank must be a whole number")
        
        return result


class NameValidator(BaseValidator):
    """Validator for name fields."""
    
    def __init__(self, max_length: int = 255, allow_empty: bool = False):
        super().__init__("NameValidator")
        self.max_length = max_length
        self.allow_empty = allow_empty
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate name field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("Name must be a string")
            return result
        
        if not value.strip() and not self.allow_empty:
            result.add_error("Name cannot be empty")
        
        if len(value) > self.max_length:
            result.add_error(f"Name cannot exceed {self.max_length} characters")
        
        # Check for invalid characters
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', value):
            result.add_warning("Name contains special characters that may cause issues")
        
        result.add_metadata('validated_name', value.strip())
        
        return result


class DescriptionValidator(BaseValidator):
    """Validator for description fields."""
    
    def __init__(self, max_length: int = MAX_DESCRIPTION_LENGTH, allow_empty: bool = True):
        super().__init__("DescriptionValidator")
        self.max_length = max_length
        self.allow_empty = allow_empty
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate description field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("Description must be a string")
            return result
        
        if not value.strip() and not self.allow_empty:
            result.add_error("Description cannot be empty")
        
        if len(value) > self.max_length:
            result.add_error(f"Description cannot exceed {self.max_length} characters")
        
        result.add_metadata('validated_description', value.strip())
        
        return result


class JSONValidator(BaseValidator):
    """Validator for JSON fields."""
    
    def __init__(self, max_size_bytes: int = MAX_META_JSON_SIZE_BYTES, required_fields: Optional[List[str]] = None):
        super().__init__("JSONValidator")
        self.max_size_bytes = max_size_bytes
        self.required_fields = required_fields or []
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate JSON field."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, dict):
            result.add_error("JSON must be a dictionary")
            return result
        
        # Check size
        import json
        json_str = json.dumps(value)
        if len(json_str.encode('utf-8')) > self.max_size_bytes:
            result.add_error(f"JSON size cannot exceed {self.max_size_bytes} bytes")
        
        # Check required fields
        for field in self.required_fields:
            if field not in value:
                result.add_error(f"Required field '{field}' is missing")
        
        result.add_metadata('validated_json', value)
        
        return result


class UserValidator(BaseValidator):
    """Validator for user references."""
    
    def __init__(self, require_active: bool = True):
        super().__init__("UserValidator")
        self.require_active = require_active
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate user reference."""
        result = ValidationResult(is_valid=True)
        
        try:
            if isinstance(value, str):
                user = User.objects.get(id=value)
            elif isinstance(value, User):
                user = value
            else:
                result.add_error("User must be a user ID or User object")
                return result
            
            if self.require_active and not user.is_active:
                result.add_error("User must be active")
            
            result.add_metadata('validated_user', user)
            
        except User.DoesNotExist:
            result.add_error("User not found")
        except Exception as e:
            result.add_error(f"Error validating user: {e}")
        
        return result


class DateRangeValidator(BaseValidator):
    """Validator for date ranges."""
    
    def __init__(self, allow_past: bool = True, allow_future: bool = True, min_duration_hours: int = 1):
        super().__init__("DateRangeValidator")
        self.allow_past = allow_past
        self.allow_future = allow_future
        self.min_duration_hours = min_duration_hours
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate date range."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, dict):
            result.add_error("Date range must be a dictionary")
            return result
        
        start_date = value.get('start_date')
        end_date = value.get('end_date')
        
        if not start_date or not end_date:
            result.add_error("Both start_date and end_date are required")
            return result
        
        try:
            if isinstance(start_date, str):
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                start_dt = start_date
            
            if isinstance(end_date, str):
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_dt = end_date
            
            # Check if dates are in the past/future
            now = timezone.now()
            
            if not self.allow_past and start_dt < now:
                result.add_error("Start date cannot be in the past")
            
            if not self.allow_future and end_date > now:
                result.add_error("End date cannot be in the future")
            
            # Check duration
            duration = end_dt - start_dt
            if duration.total_seconds() < self.min_duration_hours * 3600:
                result.add_error(f"Duration must be at least {self.min_duration_hours} hours")
            
            if end_dt <= start_dt:
                result.add_error("End date must be after start date")
            
            result.add_metadata('validated_start_date', start_dt)
            result.add_metadata('validated_end_date', end_dt)
            result.add_metadata('validated_duration', duration)
            
        except (ValueError, TypeError) as e:
            result.add_error(f"Invalid date format: {e}")
        
        return result


class EmailValidator(BaseValidator):
    """Validator for email addresses."""
    
    def __init__(self):
        super().__init__("EmailValidator")
        self.pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate email address."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("Email must be a string")
            return result
        
        if not self.pattern.match(value):
            result.add_error("Invalid email format")
        
        result.add_metadata('validated_email', value.lower())
        
        return result


class URLValidator(BaseValidator):
    """Validator for URLs."""
    
    def __init__(self):
        super().__init__("URLValidator")
        self.pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate URL."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, str):
            result.add_error("URL must be a string")
            return result
        
        if not self.pattern.match(value):
            result.add_error("Invalid URL format")
        
        result.add_metadata('validated_url', value)
        
        return result


class CompositeValidator(BaseValidator):
    """Validator that combines multiple validators."""
    
    def __init__(self, name: str, validators: List[BaseValidator], require_all: bool = True):
        super().__init__(name)
        self.validators = validators
        self.require_all = require_all
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate using all validators."""
        result = ValidationResult(is_valid=True)
        
        for validator in self.validators:
            validator_result = validator.validate(value, context)
            
            if not validator_result.is_valid:
                if self.require_all:
                    result.is_valid = False
                result.errors.extend(validator_result.errors)
            
            result.warnings.extend(validator_result.warnings)
            result.metadata.update(validator_result.metadata)
        
        return result


class ConditionalValidator(BaseValidator):
    """Validator that applies conditionally."""
    
    def __init__(self, name: str, condition: Callable[[Any, Dict[str, Any]], bool], 
                 validator: BaseValidator):
        super().__init__(name)
        self.condition = condition
        self.validator = validator
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate conditionally."""
        if self.condition(value, context or {}):
            return self.validator.validate(value, context)
        
        return ValidationResult(is_valid=True)


class ValidatorRegistry:
    """Registry for managing validators."""
    
    def __init__(self):
        self.validators: Dict[str, BaseValidator] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_validator(self, name: str, validator: BaseValidator) -> None:
        """Register a validator."""
        self.validators[name] = validator
        self.logger.info(f"Registered validator: {name}")
    
    def get_validator(self, name: str) -> Optional[BaseValidator]:
        """Get a validator by name."""
        return self.validators.get(name)
    
    def validate(self, name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate using a registered validator."""
        validator = self.get_validator(name)
        if not validator:
            raise ValueError(f"Validator not found: {name}")
        
        return validator.validate(value, context)
    
    def list_validators(self) -> List[str]:
        """List all registered validators."""
        return list(self.validators.keys())
    
    def clear_validators(self) -> None:
        """Clear all validators."""
        self.validators.clear()
        self.logger.info("Cleared all validators")


# Global validator registry
validator_registry = ValidatorRegistry()


# Initialize default validators
def initialize_default_validators() -> None:
    """Initialize default validators."""
    try:
        # Register common validators
        validator_registry.register_validator('points', PointsValidator())
        validator_registry.register_validator('rank', RankValidator())
        validator_registry.register_validator('name', NameValidator())
        validator_registry.register_validator('description', DescriptionValidator())
        validator_registry.register_validator('json', JSONValidator())
        validator_registry.register_validator('user', UserValidator())
        validator_registry.register_validator('date_range', DateRangeValidator())
        validator_registry.register_validator('email', EmailValidator())
        validator_registry.register_validator('url', URLValidator())
        
        logger.info("Initialized default validators")
        
    except Exception as e:
        logger.error(f"Error initializing default validators: {e}")


# Validation utilities
def validate_points(points: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate points value."""
    return validator_registry.validate('points', points, context)


def validate_rank(rank: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate rank value."""
    return validator_registry.validate('rank', rank, context)


def validate_name(name: Any, max_length: int = 255, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate name field."""
    validator = NameValidator(max_length=max_length)
    return validator.validate(name, context)


def validate_description(description: Any, max_length: int = MAX_DESCRIPTION_LENGTH, 
                       context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate description field."""
    validator = DescriptionValidator(max_length=max_length)
    return validator.validate(description, context)


def validate_user(user_id: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate user reference."""
    return validator_registry.validate('user', user_id, context)


def validate_date_range(date_range: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate date range."""
    return validator_registry.validate('date_range', date_range, context)


def validate_json(json_data: Any, required_fields: Optional[List[str]] = None,
                  context: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate JSON data."""
    validator = JSONValidator(required_fields=required_fields)
    return validator.validate(json_data, context)


# Business rule validators
class ContestValidator(BaseValidator):
    """Validator for contest business rules."""
    
    def __init__(self):
        super().__init__("ContestValidator")
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate contest data."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, dict):
            result.add_error("Contest data must be a dictionary")
            return result
        
        # Validate required fields
        required_fields = ['name', 'start_date', 'end_date']
        for field in required_fields:
            if field not in value:
                result.add_error(f"Required field '{field}' is missing")
        
        # Validate name
        if 'name' in value:
            name_result = validate_name(value['name'], MAX_CONTEST_NAME_LENGTH)
            if not name_result.is_valid:
                result.errors.extend(name_result.errors)
            result.warnings.extend(name_result.warnings)
        
        # Validate date range
        date_range_data = {
            'start_date': value.get('start_date'),
            'end_date': value.get('end_date')
        }
        date_result = validate_date_range(date_range_data)
        if not date_result.is_valid:
            result.errors.extend(date_result.errors)
        result.warnings.extend(date_result.warnings)
        
        return result


class RewardValidator(BaseValidator):
    """Validator for reward business rules."""
    
    def __init__(self):
        super().__init__("RewardValidator")
    
    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate reward data."""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(value, dict):
            result.add_error("Reward data must be a dictionary")
            return result
        
        # Validate required fields
        required_fields = ['title', 'reward_type']
        for field in required_fields:
            if field not in value:
                result.add_error(f"Required field '{field}' is missing")
        
        # Validate title
        if 'title' in value:
            name_result = validate_name(value['title'], MAX_REWARD_TITLE_LENGTH)
            if not name_result.is_valid:
                result.errors.extend(name_result.errors)
            result.warnings.extend(name_result.warnings)
        
        # Validate rank range if present
        if 'rank_from' in value and 'rank_to' in value:
            rank_from_result = validate_rank(value['rank_from'])
            rank_to_result = validate_rank(value['rank_to'])
            
            if not rank_from_result.is_valid:
                result.errors.extend(rank_from_result.errors)
            if not rank_to_result.is_valid:
                result.errors.extend(rank_to_result.errors)
            
            # Check range validity
            if rank_from_result.is_valid and rank_to_result.is_valid:
                rank_from = rank_from_result.metadata.get('validated_rank', 0)
                rank_to = rank_to_result.metadata.get('validated_rank', 0)
                
                if rank_from > rank_to:
                    result.add_error("Rank from cannot be greater than rank to")
        
        return result


# Validation decorators
def validate_with(validator_name: str, context_key: Optional[str] = None):
    """Decorator to validate function arguments."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the value to validate
            if context_key and context_key in kwargs:
                value = kwargs[context_key]
            elif args:
                value = args[0]
            else:
                raise ValueError("No value to validate")
            
            # Validate
            result = validator_registry.validate(validator_name, value, kwargs)
            
            if not result.is_valid:
                raise ValidationError(result.errors)
            
            # Call the function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Validation monitoring
class ValidationMonitor:
    """Monitor validation operations for debugging and analytics."""
    
    def __init__(self):
        self.validation_counts: Dict[str, int] = {}
        self.validation_errors: Dict[str, List[str]] = {}
        self.logger = logging.getLogger(__name__)
    
    def record_validation(self, validator_name: str, result: ValidationResult) -> None:
        """Record a validation operation."""
        self.validation_counts[validator_name] = self.validation_counts.get(validator_name, 0) + 1
        
        if not result.is_valid:
            if validator_name not in self.validation_errors:
                self.validation_errors[validator_name] = []
            self.validation_errors[validator_name].extend(result.errors)
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return {
            'total_validations': sum(self.validation_counts.values()),
            'validation_counts': self.validation_counts.copy(),
            'error_counts': {
                name: len(errors) for name, errors in self.validation_errors.items()
            }
        }
    
    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self.validation_counts.clear()
        self.validation_errors.clear()
        self.logger.info("Validation monitor stats reset")


# Global validation monitor
validation_monitor = ValidationMonitor()


# Initialize on module import
try:
    initialize_default_validators()
    logger.info("Gamification validator module initialized")
except Exception as e:
    logger.error(f"Error initializing validator module: {e}")
