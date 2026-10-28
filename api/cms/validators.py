# api/cms/validators.py
"""Custom validators for CMS models and forms."""
import re
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class SurveyValidator:
    """Validators for survey-related fields."""
    
    @staticmethod
    def validate_survey_title(value):
        """Validate survey title."""
        if len(value) < 10:
            raise ValidationError(_('Survey title must be at least 10 characters long.'))
        if len(value) > 200:
            raise ValidationError(_('Survey title cannot exceed 200 characters.'))
        return value
    
    @staticmethod
    def validate_survey_description(value):
        """Validate survey description."""
        if len(value) < 20:
            raise ValidationError(_('Survey description must be at least 20 characters long.'))
        if len(value) > 2000:
            raise ValidationError(_('Survey description cannot exceed 2000 characters.'))
        return value
    
    @staticmethod
    def validate_reward_amount(value):
        """Validate reward amount."""
        from decimal import Decimal
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise ValidationError(_('Reward amount must be greater than 0.'))
            if amount > Decimal('1000.00'):
                raise ValidationError(_('Reward amount cannot exceed $1000.00'))
            return amount
        except (ValueError, TypeError):
            raise ValidationError(_('Invalid reward amount format.'))
    
    @staticmethod
    def validate_completion_time(value):
        """Validate estimated completion time."""
        if value < 5:
            raise ValidationError(_('Estimated completion time must be at least 5 minutes.'))
        if value > 120:
            raise ValidationError(_('Estimated completion time cannot exceed 120 minutes.'))
        return value
    
    @staticmethod
    def validate_question_options(value):
        """Validate question options list."""
        if not isinstance(value, list):
            raise ValidationError(_('Question options must be a list.'))
        if len(value) < 2:
            raise ValidationError(_('Multiple choice questions must have at least 2 options.'))
        if len(value) > 10:
            raise ValidationError(_('Question options cannot exceed 10 items.'))
        
        # Check for duplicate options
        options = [str(option).strip().lower() for option in value]
        if len(options) != len(set(options)):
            raise ValidationError(_('Question options must be unique.'))
        
        return value


class ProfileValidator:
    """Validators for user profile fields."""
    
    @staticmethod
    def validate_date_of_birth(value):
        """Validate date of birth."""
        from datetime import date
        if not value:
            return value
        
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        
        if age < 13:
            raise ValidationError(_('You must be at least 13 years old.'))
        if age > 120:
            raise ValidationError(_('Invalid date of birth.'))
        
        return value
    
    @staticmethod
    def validate_interests(value):
        """Validate interests list."""
        if not isinstance(value, list):
            raise ValidationError(_('Interests must be a list.'))
        if len(value) > 20:
            raise ValidationError(_('Maximum 20 interests allowed.'))
        
        valid_interests = [
            'technology', 'gaming', 'sports', 'education', 'entertainment',
            'business', 'health', 'travel', 'science', 'arts', 'music',
            'food', 'fashion', 'automotive', 'finance', 'politics', 'religion'
        ]
        
        for interest in value:
            if str(interest).lower() not in valid_interests:
                raise ValidationError(_(f'Invalid interest: {interest}'))
        
        return value
    
    @staticmethod
    def validate_phone_number(value):
        """Validate phone number."""
        if not value:
            return value
        
        # Remove all non-digit characters
        digits_only = re.sub(r'[^\d]', '', value)
        
        if len(digits_only) < 10:
            raise ValidationError(_('Phone number must have at least 10 digits.'))
        if len(digits_only) > 15:
            raise ValidationError(_('Phone number cannot exceed 15 digits.'))
        
        return value


class RewardValidator:
    """Validators for reward-related fields."""
    
    @staticmethod
    def validate_transaction_amount(value):
        """Validate transaction amount."""
        from decimal import Decimal
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise ValidationError(_('Transaction amount must be greater than 0.'))
            if amount > Decimal('10000.00'):
                raise ValidationError(_('Transaction amount cannot exceed $10000.00'))
            return amount
        except (ValueError, TypeError):
            raise ValidationError(_('Invalid transaction amount format.'))
    
    @staticmethod
    def validate_pool_budget(value):
        """Validate reward pool budget."""
        from decimal import Decimal
        try:
            budget = Decimal(str(value))
            if budget <= 0:
                raise ValidationError(_('Pool budget must be greater than 0.'))
            if budget < Decimal('100.00'):
                raise ValidationError(_('Pool budget must be at least $100.00'))
            if budget > Decimal('100000.00'):
                raise ValidationError(_('Pool budget cannot exceed $100000.00'))
            return budget
        except (ValueError, TypeError):
            raise ValidationError(_('Invalid pool budget format.'))
    
    @staticmethod
    def validate_currency_code(value):
        """Validate currency code."""
        if not value or len(value) != 3:
            raise ValidationError(_('Currency code must be exactly 3 characters.'))
        
        # Basic currency code validation
        if not re.match(r'^[A-Z]{3}$', value):
            raise ValidationError(_('Currency code must be 3 uppercase letters.'))
        
        return value


class TaskValidator:
    """Validators for task management fields."""
    
    @staticmethod
    def validate_cron_expression(value):
        """Validate cron expression."""
        if not value:
            return value
        
        # Basic cron format validation (5 parts separated by spaces)
        parts = value.strip().split()
        if len(parts) != 5:
            raise ValidationError(_('Cron expression must have exactly 5 parts separated by spaces.'))
        
        # Validate each part
        valid_chars = r'[\d\*\/\-\,]'
        for part in parts:
            if not re.match(valid_chars, part):
                raise ValidationError(_(f'Invalid cron expression part: {part}'))
        
        return value
    
    @staticmethod
    def validate_task_name(value):
        """Validate task name."""
        if not value or len(value.strip()) < 3:
            raise ValidationError(_('Task name must be at least 3 characters long.'))
        if len(value) > 100:
            raise ValidationError(_('Task name cannot exceed 100 characters.'))
        
        # Allow only alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise ValidationError(_('Task name can only contain letters, numbers, hyphens, and underscores.'))
        
        return value
    
    @staticmethod
    def validate_timeout_seconds(value):
        """Validate timeout seconds."""
        if value < 30:
            raise ValidationError(_('Timeout must be at least 30 seconds.'))
        if value > 3600:
            raise ValidationError(_('Timeout cannot exceed 3600 seconds (1 hour).'))
        return value
    
    @staticmethod
    def validate_memory_limit(value):
        """Validate memory limit in MB."""
        if value < 64:
            raise ValidationError(_('Memory limit must be at least 64 MB.'))
        if value > 4096:
            raise ValidationError(_('Memory limit cannot exceed 4096 MB (4 GB).'))
        return value


class SecurityValidator:
    """Security-related validators."""
    
    @staticmethod
    def validate_api_key(value):
        """Validate API key format."""
        if not value:
            return value
        
        if len(value) < 32:
            raise ValidationError(_('API key must be at least 32 characters long.'))
        if len(value) > 128:
            raise ValidationError(_('API key cannot exceed 128 characters.'))
        
        # Allow only alphanumeric and some special characters
        if not re.match(r'^[a-zA-Z0-9_\-\.@]+$', value):
            raise ValidationError(_('Invalid API key format.'))
        
        return value
    
    @staticmethod
    def validate_webhook_url(value):
        """Validate webhook URL."""
        if not value:
            return value
        
        # Basic URL validation
        if not re.match(r'^https?://[^\s/$]', value):
            raise ValidationError(_('Webhook URL must be a valid HTTP/HTTPS URL.'))
        
        if len(value) > 2048:
            raise ValidationError(_('Webhook URL cannot exceed 2048 characters.'))
        
        return value


class BusinessValidator:
    """Business logic validators."""
    
    @staticmethod
    def validate_segment_criteria(value):
        """Validate user segment criteria."""
        if not isinstance(value, dict):
            raise ValidationError(_('Segment criteria must be a dictionary.'))
        
        # Check for conflicting criteria
        age_min = value.get('age_min')
        age_max = value.get('age_max')
        
        if age_min and age_max and age_min > age_max:
            raise ValidationError(_('Minimum age cannot be greater than maximum age.'))
        
        # Check income level logic
        income_levels = value.get('income_levels', [])
        valid_income_levels = ['low', 'medium', 'high', 'very_high']
        
        for level in income_levels:
            if level not in valid_income_levels:
                raise ValidationError(_(f'Invalid income level: {level}'))
        
        return value
    
    @staticmethod
    def validate_reward_configuration(value):
        """Validate reward configuration."""
        if not isinstance(value, dict):
            raise ValidationError(_('Reward configuration must be a dictionary.'))
        
        reward_type = value.get('reward_type')
        valid_types = ['fixed', 'tiered', 'performance', 'bonus']
        
        if reward_type not in valid_types:
            raise ValidationError(_(f'Invalid reward type: {reward_type}'))
        
        # Validate tiered reward configuration
        if reward_type == 'tiered':
            bonus_amount = value.get('bonus_amount')
            min_quality = value.get('min_quality_for_bonus')
            
            if bonus_amount and bonus_amount < 0:
                raise ValidationError(_('Bonus amount cannot be negative.'))
            
            if min_quality and (min_quality < 0 or min_quality > 1):
                raise ValidationError(_('Quality threshold must be between 0 and 1.'))
        
        return value


class FileValidator:
    """File upload validators."""
    
    @staticmethod
    def validate_image_file(file_obj):
        """Validate uploaded image file."""
        if not file_obj:
            return file_obj
        
        # Check file size (max 5MB)
        if file_obj.size > 5 * 1024 * 1024:
            raise ValidationError(_('Image file size cannot exceed 5MB.'))
        
        # Check file extension
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        file_extension = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else ''
        
        if file_extension not in allowed_extensions:
            raise ValidationError(_(f'Invalid image format. Allowed formats: {", ".join(allowed_extensions)}'))
        
        return file_obj
    
    @staticmethod
    def validate_document_file(file_obj):
        """Validate uploaded document file."""
        if not file_obj:
            return file_obj
        
        # Check file size (max 10MB)
        if file_obj.size > 10 * 1024 * 1024:
            raise ValidationError(_('Document file size cannot exceed 10MB.'))
        
        # Check file extension
        allowed_extensions = ['pdf', 'doc', 'docx', 'txt', 'csv']
        file_extension = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else ''
        
        if file_extension not in allowed_extensions:
            raise ValidationError(_(f'Invalid document format. Allowed formats: {", ".join(allowed_extensions)}'))
        
        return file_obj


# Custom regex validators
class UsernameValidator(RegexValidator):
    """Username validator with custom regex."""
    regex = r'^[a-zA-Z0-9_\-\.@]+$'
    message = _('Enter a valid username. Only letters, numbers, hyphens, dots, and @ are allowed.')
    code = 'invalid_username'


class StrongPasswordValidator:
    """Strong password validator."""
    def __init__(self, min_length=8):
        self.min_length = min_length
    
    def validate(self, password, user=None):
        errors = []
        
        if len(password) < self.min_length:
            errors.append(_('Password must be at least %d characters long.' % self.min_length))
        
        if not re.search(r'[A-Z]', password):
            errors.append(_('Password must contain at least one uppercase letter.'))
        
        if not re.search(r'[a-z]', password):
            errors.append(_('Password must contain at least one lowercase letter.'))
        
        if not re.search(r'[0-9]', password):
            errors.append(_('Password must contain at least one digit.'))
        
        if not re.search(r'[!@#$%^&*()_+=\-\[\]{}|;:,.<>?]', password):
            errors.append(_('Password must contain at least one special character.'))
        
        if errors:
            raise ValidationError(errors)
        
        return password


# ─────────────────────────────────────────────────────────────────────────────
# FIX: register_custom_validators was called in apps.py ready() but didn't
# exist in this file. Added here so startup no longer silently skips it.
# ─────────────────────────────────────────────────────────────────────────────

def register_custom_validators():
    """
    Register any custom validators that need explicit setup at startup.

    Called from CmsConfig.ready(). Add any global validator registration
    logic here (e.g. plugging into third-party form frameworks, caching
    compiled regex patterns, etc.).

    Currently a no-op — validators work via Django's built-in system.
    Expand as needed.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.debug('register_custom_validators called — no custom validators to register')
