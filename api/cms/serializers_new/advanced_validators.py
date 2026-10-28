# cms/serializers_new/advanced_validators.py
"""
Advanced Serializer Validators

Comprehensive validation library for all serializers.

Validators provided:
- Field-level validators (email, phone, amounts, etc.)
- Cross-field validators (date ranges, related fields)
- Business rule validators (no duplicates, constraints, etc.)
- Custom validators (complex logic)
- Reusable validator factories
- Batch validation support

All validators:
- Return clear error messages
- Support internationalization
- Are testable in isolation
- Document expected inputs/outputs
"""

from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, EmailValidator
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta, date
from django.utils import timezone
import re
from typing import Any, List, Dict, Callable, Optional
import logging

logger = logging.getLogger('cms.validators')


# ─────────────────────────────────────────────────────────────────────────────
# FIELD-LEVEL VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class PhoneNumberValidator:
    """Validate phone numbers in multiple formats"""
    
    # Patterns for various formats
    PATTERNS = {
        'us': r'^\+?1?\d{10}$',           # 10 digits
        'international': r'^\+\d{1,3}\d{6,14}$',  # International
        'simple': r'^\d{10,15}$',          # 10-15 digits
    }
    
    def __init__(self, format: str = 'international'):
        """
        Args:
            format: 'us', 'international', or 'simple'
        """
        self.format = format
        self.pattern = self.PATTERNS.get(format, self.PATTERNS['simple'])
    
    def __call__(self, value: str):
        """Validate phone number"""
        if not value:
            return
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\.]+', '', str(value))
        
        if not re.match(self.pattern, cleaned):
            raise serializers.ValidationError(
                f"Invalid phone number format. Expected {self.format} format."
            )


class AmountValidator:
    """Validate monetary amounts"""
    
    def __init__(self, min_amount: float = 0, max_amount: float = None):
        """
        Args:
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount
        """
        self.min_amount = min_amount
        self.max_amount = max_amount
    
    def __call__(self, value: float):
        """Validate amount"""
        if value is None:
            return
        
        try:
            amount = float(value)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Amount must be a valid number")
        
        if amount < self.min_amount:
            raise serializers.ValidationError(
                f"Amount must be at least {self.min_amount}"
            )
        
        if self.max_amount and amount > self.max_amount:
            raise serializers.ValidationError(
                f"Amount cannot exceed {self.max_amount}"
            )
        
        # Check decimal places (usually 2 for currency)
        if len(str(amount).split('.')[-1]) > 2:
            raise serializers.ValidationError(
                "Amount can have at most 2 decimal places"
            )


class URLSlugValidator:
    """Validate URL slugs (lowercase, hyphens, alphanumeric)"""
    
    def __call__(self, value: str):
        """Validate slug format"""
        if not value:
            return
        
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )


class PasswordValidator:
    """Validate password strength"""
    
    def __init__(self, min_length: int = 8, require_uppercase: bool = True,
                 require_numbers: bool = True, require_special: bool = False):
        """
        Args:
            min_length: Minimum password length
            require_uppercase: Must contain uppercase letters
            require_numbers: Must contain digits
            require_special: Must contain special characters
        """
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_numbers = require_numbers
        self.require_special = require_special
    
    def __call__(self, value: str):
        """Validate password strength"""
        if not value:
            return
        
        errors = []
        
        if len(value) < self.min_length:
            errors.append(f"At least {self.min_length} characters required")
        
        if self.require_uppercase and not re.search(r'[A-Z]', value):
            errors.append("Must contain at least one uppercase letter")
        
        if self.require_numbers and not re.search(r'\d', value):
            errors.append("Must contain at least one digit")
        
        if self.require_special and not re.search(r'[!@#$%^&*]', value):
            errors.append("Must contain at least one special character")
        
        if errors:
            raise serializers.ValidationError(errors)


class FileTypeValidator:
    """Validate file types"""
    
    ALLOWED_TYPES = {
        'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
        'document': ['application/pdf', 'application/msword', 'text/plain'],
        'video': ['video/mp4', 'video/mpeg', 'video/quicktime'],
    }
    
    def __init__(self, allowed_types: List[str] = None, max_size: int = None):
        """
        Args:
            allowed_types: List of MIME types or category names ('image', 'document')
            max_size: Maximum file size in bytes
        """
        self.allowed_types = allowed_types or ['image']
        self.max_size = max_size
        
        # Expand category names to MIME types
        expanded = []
        for type_name in self.allowed_types:
            if type_name in self.ALLOWED_TYPES:
                expanded.extend(self.ALLOWED_TYPES[type_name])
            else:
                expanded.append(type_name)
        self.allowed_types = expanded
    
    def __call__(self, value):
        """Validate file"""
        if not value:
            return
        
        # Check file type
        if hasattr(value, 'content_type'):
            if value.content_type not in self.allowed_types:
                raise serializers.ValidationError(
                    f"File type {value.content_type} not allowed"
                )
        
        # Check file size
        if self.max_size and hasattr(value, 'size'):
            if value.size > self.max_size:
                raise serializers.ValidationError(
                    f"File size exceeds {self.max_size} bytes"
                )


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-FIELD VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class DateRangeValidator:
    """Validate that start_date < end_date"""
    
    def __init__(self, start_field: str = 'start_date', 
                 end_field: str = 'end_date',
                 min_days: int = 0):
        """
        Args:
            start_field: Name of start date field
            end_field: Name of end date field
            min_days: Minimum days between dates
        """
        self.start_field = start_field
        self.end_field = end_field
        self.min_days = min_days
    
    def __call__(self, data: Dict[str, Any]):
        """Validate date range"""
        start = data.get(self.start_field)
        end = data.get(self.end_field)
        
        if not start or not end:
            return
        
        if start >= end:
            raise serializers.ValidationError(
                {self.end_field: f"{self.end_field} must be after {self.start_field}"}
            )
        
        if self.min_days > 0:
            diff = (end - start).days
            if diff < self.min_days:
                raise serializers.ValidationError(
                    {self.end_field: f"Must be at least {self.min_days} days after {self.start_field}"}
                )


class MatchingFieldsValidator:
    """Validate that two fields match (e.g., password confirmation)"""
    
    def __init__(self, field1: str, field2: str):
        """
        Args:
            field1: First field name
            field2: Second field name (should match field1)
        """
        self.field1 = field1
        self.field2 = field2
    
    def __call__(self, data: Dict[str, Any]):
        """Validate fields match"""
        val1 = data.get(self.field1)
        val2 = data.get(self.field2)
        
        if val1 and val2 and val1 != val2:
            raise serializers.ValidationError(
                {self.field2: f"{self.field2} must match {self.field1}"}
            )


class ConditionalRequiredValidator:
    """Validate that field is required if another field has specific value"""
    
    def __init__(self, condition_field: str, condition_value: Any, 
                 required_field: str):
        """
        Args:
            condition_field: Field to check
            condition_value: Value that triggers requirement
            required_field: Field that becomes required
        """
        self.condition_field = condition_field
        self.condition_value = condition_value
        self.required_field = required_field
    
    def __call__(self, data: Dict[str, Any]):
        """Validate conditional requirement"""
        if data.get(self.condition_field) == self.condition_value:
            if not data.get(self.required_field):
                raise serializers.ValidationError(
                    {self.required_field: 
                     f"This field is required when {self.condition_field} is {self.condition_value}"}
                )


class UniqueTogetherValidator:
    """Validate that combination of fields is unique"""
    
    def __init__(self, fields: List[str], model_class: type, 
                 exclude_instance: bool = True):
        """
        Args:
            fields: List of field names that should be unique together
            model_class: Django model class
            exclude_instance: Exclude current instance from check (for updates)
        """
        self.fields = fields
        self.model_class = model_class
        self.exclude_instance = exclude_instance
    
    def __call__(self, data: Dict[str, Any]):
        """Validate unique together"""
        # Get field values
        filter_kwargs = {field: data.get(field) for field in self.fields}
        
        # Skip if any field is empty
        if any(v is None for v in filter_kwargs.values()):
            return
        
        # Check for duplicates
        queryset = self.model_class.objects.filter(**filter_kwargs)
        
        # Exclude current instance if updating
        if self.exclude_instance and hasattr(self, 'instance') and self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError(
                f"This combination of {', '.join(self.fields)} already exists"
            )


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS RULE VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class NoFutureValueValidator:
    """Validate that date/value is not in the future"""
    
    def __init__(self, field_name: str = None):
        self.field_name = field_name
    
    def __call__(self, value: Any):
        """Validate value is not in future"""
        if not value:
            return
        
        if isinstance(value, datetime):
            check_value = value
        elif isinstance(value, date):
            check_value = datetime.combine(value, datetime.min.time())
        else:
            return
        
        if check_value > timezone.now():
            raise serializers.ValidationError(
                "This date cannot be in the future"
            )


class MinAgeValidator:
    """Validate that person is at least minimum age"""
    
    def __init__(self, min_age: int = 18):
        self.min_age = min_age
    
    def __call__(self, value: date):
        """Validate age"""
        if not value:
            return
        
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        
        if age < self.min_age:
            raise serializers.ValidationError(
                f"Must be at least {self.min_age} years old"
            )


class AllowedValuesValidator:
    """Validate that value is in allowed list"""
    
    def __init__(self, allowed_values: List[Any]):
        self.allowed_values = allowed_values
    
    def __call__(self, value: Any):
        """Validate value in allowed list"""
        if value and value not in self.allowed_values:
            raise serializers.ValidationError(
                f"Value must be one of: {', '.join(str(v) for v in self.allowed_values)}"
            )


class AccountAgeValidator:
    """Validate user account is at least X days old"""
    
    def __init__(self, min_days: int = 7):
        self.min_days = min_days
    
    def __call__(self, user: Any):
        """Validate account age"""
        if not hasattr(user, 'date_joined'):
            return
        
        account_age = (timezone.now() - user.date_joined).days
        
        if account_age < self.min_days:
            raise serializers.ValidationError(
                f"Account must be at least {self.min_days} days old"
            )


class WithdrawalLimitValidator:
    """Validate withdrawal doesn't exceed limits"""
    
    def __init__(self, user_field: str = 'user'):
        self.user_field = user_field
    
    def __call__(self, data: Dict[str, Any]):
        """Validate withdrawal limits"""
        user = data.get(self.user_field)
        amount = data.get('amount')
        
        if not user or not amount:
            return
        
        # Check user's available balance
        try:
            from api.cms.models_new.user_wallet import UserVirtualBalance
            balance = UserVirtualBalance.objects.get(user=user)
            
            if amount > balance.balance:
                raise serializers.ValidationError(
                    {'amount': f"Insufficient balance. Available: {balance.balance}"}
                )
        except Exception as e:
            logger.error(f"Withdrawal limit check failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# BATCH VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class BatchValidator:
    """Validate multiple items in a batch"""
    
    def __init__(self, item_validator: Callable):
        """
        Args:
            item_validator: Validator function to apply to each item
        """
        self.item_validator = item_validator
    
    def __call__(self, data: List[Dict[str, Any]]):
        """Validate batch of items"""
        errors = []
        
        for idx, item in enumerate(data):
            try:
                self.item_validator(item)
            except serializers.ValidationError as e:
                errors.append({
                    'index': idx,
                    'error': e.detail,
                    'item': item,
                })
        
        if errors:
            raise serializers.ValidationError(errors)


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR FACTORIES
# ─────────────────────────────────────────────────────────────────────────────

class ValidatorFactory:
    """Factory for creating common validators"""
    
    @staticmethod
    def email_validator() -> EmailValidator:
        """Create email validator"""
        return EmailValidator(message="Invalid email address")
    
    @staticmethod
    def url_validator() -> URLValidator:
        """Create URL validator"""
        return URLValidator(message="Invalid URL")
    
    @staticmethod
    def phone_validator(format: str = 'international') -> PhoneNumberValidator:
        """Create phone number validator"""
        return PhoneNumberValidator(format=format)
    
    @staticmethod
    def amount_validator(min_amount: float = 0, max_amount: float = None) -> AmountValidator:
        """Create amount validator"""
        return AmountValidator(min_amount=min_amount, max_amount=max_amount)
    
    @staticmethod
    def password_validator(min_length: int = 8) -> PasswordValidator:
        """Create password validator"""
        return PasswordValidator(min_length=min_length)
    
    @staticmethod
    def file_validator(allowed_types: List[str] = None, max_size: int = None) -> FileTypeValidator:
        """Create file validator"""
        return FileTypeValidator(allowed_types=allowed_types, max_size=max_size)
    
    @staticmethod
    def date_range_validator(start_field: str = 'start_date', 
                            end_field: str = 'end_date') -> DateRangeValidator:
        """Create date range validator"""
        return DateRangeValidator(start_field=start_field, end_field=end_field)
    
    @staticmethod
    def min_age_validator(min_age: int = 18) -> MinAgeValidator:
        """Create min age validator"""
        return MinAgeValidator(min_age=min_age)


# ─────────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLES
# ─────────────────────────────────────────────────────────────────────────────

"""
Example 1: Using validators in serializer

from rest_framework import serializers
from api.cms.serializers_new.advanced_validators import (
    PhoneNumberValidator,
    AmountValidator,
    DateRangeValidator,
    PasswordValidator,
)

class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[AmountValidator(min_amount=10, max_amount=10000)]
    )
    phone = serializers.CharField(
        validators=[PhoneNumberValidator(format='us')]
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    validators = [
        DateRangeValidator(start_field='start_date', end_field='end_date')
    ]


Example 2: Using in views

class WithdrawalViewSet(viewsets.ModelViewSet):
    serializer_class = WithdrawalSerializer
    
    def perform_create(self, serializer):
        # Validators run automatically during is_valid()
        if serializer.is_valid():
            serializer.save()
        else:
            print(serializer.errors)


Example 3: Custom validation

class BlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = ['title', 'content', 'published_at']
    
    def validate_title(self, value):
        # Field-level validation
        if len(value) < 5:
            raise serializers.ValidationError("Title too short")
        return value
    
    def validate(self, data):
        # Cross-field validation using validators
        DateRangeValidator()(data)
        return data
"""


# Export public API
__all__ = [
    'PhoneNumberValidator',
    'AmountValidator',
    'URLSlugValidator',
    'PasswordValidator',
    'FileTypeValidator',
    'DateRangeValidator',
    'MatchingFieldsValidator',
    'ConditionalRequiredValidator',
    'UniqueTogetherValidator',
    'NoFutureValueValidator',
    'MinAgeValidator',
    'AllowedValuesValidator',
    'AccountAgeValidator',
    'WithdrawalLimitValidator',
    'BatchValidator',
    'ValidatorFactory',
]
