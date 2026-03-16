from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re


def validate_phone_number(value):
    """Validate Bangladesh phone number."""
    phone_regex = re.compile(r'^(\+8801|01)[3-9]\d{8}$')
    if not phone_regex.match(value):
        raise ValidationError(
            _('Invalid phone number format. Use: +8801XXXXXXXXX or 01XXXXXXXXX'),
            code='invalid_phone'
        )


def validate_password_strength(value):
    """Validate password strength."""
    if len(value) < 8:
        raise ValidationError(
            _('Password must be at least 8 characters long.'),
            code='password_too_short'
        )
    
    if not re.search(r'[A-Z]', value):
        raise ValidationError(
            _('Password must contain at least one uppercase letter.'),
            code='password_no_upper'
        )
    
    if not re.search(r'[a-z]', value):
        raise ValidationError(
            _('Password must contain at least one lowercase letter.'),
            code='password_no_lower'
        )
    
    if not re.search(r'\d', value):
        raise ValidationError(
            _('Password must contain at least one digit.'),
            code='password_no_digit'
        )


def validate_file_size(file, max_size_mb=5):
    """Validate file size."""
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            _(f'File size must not exceed {max_size_mb}MB.'),
            code='file_too_large'
        )