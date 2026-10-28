# engagement/validator.py
"""
Main validator module for engagement system.
Provides a unified interface for all validation operations.
"""
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from .validators import (
    # Field validators
    UsernameValidator, SlugValidator, ColorHexValidator,
    PhoneNumberValidator, URLValidator, EmojiValidator,
    
    # Business logic validators
    validate_positive_number, validate_non_negative_number,
    validate_percentage, validate_future_date, validate_past_date,
    validate_date_range, validate_max_length, validate_min_length,
    validate_email_domain, validate_age, validate_coins_amount,
    validate_xp_amount, validate_streak_days, validate_rank,
    validate_quest_progress, validate_achievement_requirements,
    validate_shop_item_price, validate_referral_code,
    validate_webhook_url, validate_webhook_secret,
    validate_feature_flag_key, validate_experiment_key,
    
    # Model validators
    validate_user_status, validate_quest_status,
    validate_achievement_difficulty, validate_shop_item_type,
    
    # Validation classes
    CheckInValidator, SpinValidator, QuestValidator,
    AchievementValidator, ShopValidator, LeaderboardValidator,
    
    # Serializer validators
    EngagementSerializerValidator,
    
    # Cross-field validators
    validate_date_range_consistency, validate_price_quantity_consistency,
    validate_progress_requirements,
    
    # Validation utilities
    ValidationMixin, validate_model_unique_together,
    validate_business_rules
)


class ValidationType(Enum):
    """Types of validation operations."""
    FIELD = "field"
    BUSINESS_LOGIC = "business_logic"
    MODEL = "model"
    SERIALIZER = "serializer"
    CROSS_FIELD = "cross_field"
    CUSTOM = "custom"


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.data is None:
            self.data = {}


class EngagementValidator:
    """Main validator class for engagement system."""
    
    def __init__(self):
        self.field_validators = self._setup_field_validators()
        self.business_validators = self._setup_business_validators()
        self.model_validators = self._setup_model_validators()
    
    def _setup_field_validators(self) -> Dict[str, List]:
        """Setup field validators."""
        return {
            'username': [UsernameValidator()],
            'slug': [SlugValidator()],
            'color_hex': [ColorHexValidator()],
            'phone_number': [PhoneNumberValidator()],
            'url': [URLValidator()],
            'emoji': [EmojiValidator()],
            'positive_number': [validate_positive_number],
            'non_negative_number': [validate_non_negative_number],
            'percentage': [validate_percentage],
            'future_date': [validate_future_date],
            'past_date': [validate_past_date],
            'email_domain': [validate_email_domain],
            'age': [validate_age],
            'coins_amount': [validate_coins_amount],
            'xp_amount': [validate_xp_amount],
            'streak_days': [validate_streak_days],
            'rank': [validate_rank],
            'shop_item_price': [validate_shop_item_price],
            'referral_code': [validate_referral_code],
            'webhook_url': [validate_webhook_url],
            'webhook_secret': [validate_webhook_secret],
            'feature_flag_key': [validate_feature_flag_key],
            'experiment_key': [validate_experiment_key],
        }
    
    def _setup_business_validators(self) -> Dict[str, Any]:
        """Setup business logic validators."""
        return {
            'checkin': CheckInValidator,
            'spin': SpinValidator,
            'quest': QuestValidator,
            'achievement': AchievementValidator,
            'shop': ShopValidator,
            'leaderboard': LeaderboardValidator,
        }
    
    def _setup_model_validators(self) -> Dict[str, List]:
        """Setup model validators."""
        return {
            'user_status': [validate_user_status],
            'quest_status': [validate_quest_status],
            'achievement_difficulty': [validate_achievement_difficulty],
            'shop_item_type': [validate_shop_item_type],
        }
    
    def validate_field(self, field_name: str, value: Any, **kwargs) -> ValidationResult:
        """Validate a field value."""
        errors = []
        warnings = []
        
        if field_name not in self.field_validators:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown field: {field_name}"]
            )
        
        validators = self.field_validators[field_name]
        
        for validator in validators:
            try:
                if callable(validator):
                    validator(value)
                else:
                    # For class-based validators
                    validator()(value)
            except Exception as e:
                errors.append(str(e))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_business_logic(self, validator_name: str, context: Dict[str, Any]) -> ValidationResult:
        """Validate business logic."""
        errors = []
        warnings = []
        
        if validator_name not in self.business_validators:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown business validator: {validator_name}"]
            )
        
        validator_class = self.business_validators[validator_name]
        
        try:
            # Determine which method to call based on context
            if 'user' in context and 'checkin_date' in context:
                result = validator_class.validate_daily_checkin(context['user'], context['checkin_date'])
            elif 'user' in context:
                result = validator_class.validate_spin_permission(context['user'])
            elif 'user_quest' in context and 'progress' in context:
                result = validator_class.validate_quest_completion(context['user_quest'], context['progress'])
            elif 'user' in context and 'achievement' in context:
                result = validator_class.validate_achievement_unlock(context['user'], context['achievement'])
            elif 'user' in context and 'item' in context and 'quantity' in context:
                result = validator_class.validate_purchase(context['user'], context['item'], context['quantity'])
            elif 'user' in context and 'date' in context and 'season' in context:
                result = validator_class.validate_leaderboard_entry(context['user'], context['date'], context['season'])
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=["Invalid context for business validation"]
                )
            
            if result is True:
                return ValidationResult(is_valid=True)
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=[str(result)]
                )
                
        except Exception as e:
            errors.append(str(e))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_model(self, model_name: str, value: Any) -> ValidationResult:
        """Validate model field."""
        errors = []
        warnings = []
        
        if model_name not in self.model_validators:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown model validator: {model_name}"]
            )
        
        validators = self.model_validators[model_name]
        
        for validator in validators:
            try:
                validator(value)
            except Exception as e:
                errors.append(str(e))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_cross_fields(self, validator_name: str, data: Dict[str, Any]) -> ValidationResult:
        """Validate cross-field relationships."""
        errors = []
        warnings = []
        
        try:
            if validator_name == 'date_range':
                validate_date_range_consistency(data)
            elif validator_name == 'price_quantity':
                validate_price_quantity_consistency(data)
            elif validator_name == 'progress':
                validate_progress_requirements(data)
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Unknown cross-field validator: {validator_name}"]
                )
                
        except Exception as e:
            errors.append(str(e))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_serializer(self, serializer_class, data: Dict[str, Any], context: Dict[str, Any] = None) -> ValidationResult:
        """Validate serializer data."""
        errors = []
        warnings = []
        
        try:
            serializer = serializer_class(data=data, context=context or {})
            
            if not serializer.is_valid():
                errors = [
                    f"{field}: {', '.join(messages)}"
                    for field, messages in serializer.errors.items()
                ]
            
        except Exception as e:
            errors.append(str(e))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_custom(self, validator_func: callable, *args, **kwargs) -> ValidationResult:
        """Validate using custom validator function."""
        errors = []
        warnings = []
        
        try:
            result = validator_func(*args, **kwargs)
            
            if result is True:
                return ValidationResult(is_valid=True)
            elif isinstance(result, str):
                errors.append(result)
            elif isinstance(result, list):
                errors.extend(result)
            elif isinstance(result, dict):
                errors.extend(result.get('errors', []))
                warnings.extend(result.get('warnings', []))
            else:
                errors.append("Invalid validator result")
                
        except Exception as e:
            errors.append(str(e))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


# Global validator instance
engagement_validator = EngagementValidator()


# ── Convenience Functions ─────────────────────────────────────────────────────

def validate_username(username: str) -> ValidationResult:
    """Validate username."""
    return engagement_validator.validate_field('username', username)


def validate_email(email: str) -> ValidationResult:
    """Validate email."""
    return engagement_validator.validate_field('email_domain', email)


def validate_coins(amount: float) -> ValidationResult:
    """Validate coins amount."""
    return engagement_validator.validate_field('coins_amount', amount)


def validate_xp(amount: int) -> ValidationResult:
    """Validate XP amount."""
    return engagement_validator.validate_field('xp_amount', amount)


def validate_checkin(user, checkin_date) -> ValidationResult:
    """Validate check-in operation."""
    return engagement_validator.validate_business_logic('checkin', {
        'user': user,
        'checkin_date': checkin_date
    })


def validate_spin(user) -> ValidationResult:
    """Validate spin operation."""
    return engagement_validator.validate_business_logic('spin', {'user': user})


def validate_quest(user_quest, progress) -> ValidationResult:
    """Validate quest completion."""
    return engagement_validator.validate_business_logic('quest', {
        'user_quest': user_quest,
        'progress': progress
    })


def validate_purchase(user, item, quantity) -> ValidationResult:
    """Validate shop purchase."""
    return engagement_validator.validate_business_logic('shop', {
        'user': user,
        'item': item,
        'quantity': quantity
    })


def validate_date_range(data: Dict[str, Any]) -> ValidationResult:
    """Validate date range."""
    return engagement_validator.validate_cross_fields('date_range', data)


def validate_price_quantity(data: Dict[str, Any]) -> ValidationResult:
    """Validate price and quantity consistency."""
    return engagement_validator.validate_cross_fields('price_quantity', data)


# ── Validation Decorators ─────────────────────────────────────────────────────

def validate_fields(field_validations: Dict[str, str]):
    """Decorator to validate function arguments."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            errors = []
            
            for field_name, validator_name in field_validations.items():
                if field_name in kwargs:
                    result = engagement_validator.validate_field(validator_name, kwargs[field_name])
                    if not result.is_valid:
                        errors.extend(result.errors)
            
            if errors:
                raise ValidationError(f"Validation failed: {', '.join(errors)}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_business(validator_name: str, context_mapping: Dict[str, str]):
    """Decorator to validate business logic."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            context = {}
            
            for kwarg_key, context_key in context_mapping.items():
                if kwarg_key in kwargs:
                    context[context_key] = kwargs[kwarg_key]
            
            result = engagement_validator.validate_business_logic(validator_name, context)
            
            if not result.is_valid:
                raise ValidationError(f"Business validation failed: {', '.join(result.errors)}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ── Validation Exceptions ─────────────────────────────────────────────────────

class ValidationError(Exception):
    """Custom validation exception."""
    pass


class BusinessValidationError(ValidationError):
    """Business logic validation exception."""
    pass


class FieldValidationError(ValidationError):
    """Field validation exception."""
    pass


class CrossFieldValidationError(ValidationError):
    """Cross-field validation exception."""
    pass


# ── Validation Utilities ─────────────────────────────────────────────────────

class ValidationContext:
    """Context for validation operations."""
    
    def __init__(self, user=None, tenant=None, request=None):
        self.user = user
        self.tenant = tenant
        self.request = request
        self.data = {}
        self.errors = []
        self.warnings = []
    
    def add_error(self, error: str):
        """Add an error to the context."""
        self.errors.append(error)
    
    def add_warning(self, warning: str):
        """Add a warning to the context."""
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        """Check if context has errors."""
        return len(self.errors) > 0
    
    def get_errors(self) -> List[str]:
        """Get all errors."""
        return self.errors
    
    def get_warnings(self) -> List[str]:
        """Get all warnings."""
        return self.warnings


class ValidationEngine:
    """Advanced validation engine with chaining and rules."""
    
    def __init__(self):
        self.rules = []
        self.context = ValidationContext()
    
    def add_rule(self, validator_func: callable, field_name: str = None, 
                 error_message: str = None, stop_on_failure: bool = False):
        """Add a validation rule."""
        rule = {
            'validator': validator_func,
            'field': field_name,
            'error_message': error_message,
            'stop_on_failure': stop_on_failure
        }
        self.rules.append(rule)
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against all rules."""
        errors = []
        warnings = []
        
        for rule in self.rules:
            try:
                validator = rule['validator']
                field_name = rule['field']
                
                if field_name and field_name in data:
                    result = validator(data[field_name])
                elif not field_name:
                    result = validator(data)
                else:
                    continue
                
                if isinstance(result, ValidationResult):
                    if not result.is_valid:
                        errors.extend(result.errors)
                        warnings.extend(result.warnings)
                        if rule['stop_on_failure']:
                            break
                elif result is not True:
                    error_msg = rule['error_message'] or str(result)
                    errors.append(error_msg)
                    if rule['stop_on_failure']:
                        break
                        
            except Exception as e:
                error_msg = rule['error_message'] or str(e)
                errors.append(error_msg)
                if rule['stop_on_failure']:
                    break
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def clear_rules(self):
        """Clear all validation rules."""
        self.rules.clear()


# ── Batch Validation ─────────────────────────────────────────────────────

def validate_batch(items: List[Dict[str, Any]], validator_config: Dict[str, Any]) -> List[ValidationResult]:
    """Validate multiple items."""
    results = []
    
    for item in items:
        if 'field' in validator_config:
            result = engagement_validator.validate_field(
                validator_config['field'], 
                item.get(validator_config['field'])
            )
        elif 'business' in validator_config:
            result = engagement_validator.validate_business_logic(
                validator_config['business'], 
                item
            )
        elif 'model' in validator_config:
            result = engagement_validator.validate_model(
                validator_config['model'], 
                item.get('value')
            )
        else:
            result = ValidationResult(is_valid=False, errors=["Invalid validator config"])
        
        results.append(result)
    
    return results


def validate_batch_summary(results: List[ValidationResult]) -> Dict[str, Any]:
    """Get summary of batch validation results."""
    total = len(results)
    valid = sum(1 for r in results if r.is_valid)
    invalid = total - valid
    
    all_errors = []
    all_warnings = []
    
    for result in results:
        all_errors.extend(result.errors)
        all_warnings.extend(result.warnings)
    
    return {
        'total': total,
        'valid': valid,
        'invalid': invalid,
        'success_rate': valid / total if total > 0 else 0,
        'total_errors': len(all_errors),
        'total_warnings': len(all_warnings),
        'unique_errors': list(set(all_errors)),
        'unique_warnings': list(set(all_warnings))
    }
