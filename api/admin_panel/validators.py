# api/admin_panel/validators.py
"""
Validators for admin_panel app.
"""
import re
import json
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ==================== Config Validators ====================

def validate_config_key(value):
    """Config key must be snake_case alphanumeric."""
    if not re.match(r'^[a-z][a-z0-9_]*$', value):
        raise ValidationError(
            _('Config key must be lowercase, alphanumeric, and may contain underscores. '
              'Must start with a letter. Got: %(value)s'),
            params={'value': value},
            code='invalid_config_key'
        )


def validate_json_value(value):
    """Validate that a string is valid JSON."""
    if isinstance(value, str):
        try:
            json.loads(value)
        except (json.JSONDecodeError, ValueError):
            raise ValidationError(
                _('Enter valid JSON. Got: %(value)s'),
                params={'value': value[:50]},
                code='invalid_json'
            )


def validate_rollout_percentage(value):
    """Rollout percentage must be 0–100."""
    if not (0 <= value <= 100):
        raise ValidationError(
            _('Rollout percentage must be between 0 and 100. Got: %(value)s'),
            params={'value': value},
            code='invalid_rollout_percentage'
        )


# ==================== Cron Expression Validator ====================

CRON_PART_PATTERNS = {
    'minute': r'^(\*|([0-5]?\d)(-([0-5]?\d))?(/\d+)?)(,(\*|([0-5]?\d)(-([0-5]?\d))?(/\d+)?))*$',
    'hour': r'^(\*|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?)(,(\*|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?))*$',
    'day_of_month': r'^(\*|([1-9]|[12]\d|3[01])(-([1-9]|[12]\d|3[01]))?(/\d+)?|\?)(,(\*|([1-9]|[12]\d|3[01])(-([1-9]|[12]\d|3[01]))?(/\d+)?))*$',
    'month': r'^(\*|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?)(,(\*|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?))*$',
    'day_of_week': r'^(\*|[0-7](-[0-7])?(/\d+)?|\?)(,(\*|[0-7](-[0-7])?(/\d+)?))*$',
}


def validate_cron_expression(value):
    """Validate a 5-part cron expression (minute hour dom month dow)."""
    if not value or not isinstance(value, str):
        raise ValidationError(_('Cron expression cannot be empty.'), code='empty_cron')

    parts = value.strip().split()
    if len(parts) != 5:
        raise ValidationError(
            _('Cron expression must have exactly 5 parts (minute hour dom month dow). Got %(count)d parts.'),
            params={'count': len(parts)},
            code='invalid_cron_parts'
        )
    return value


# ==================== Maintenance Window Validator ====================

def validate_maintenance_end_after_start(start, end):
    """end_at must be after start_at."""
    if start and end and end <= start:
        raise ValidationError(
            _('Maintenance end time must be after start time.'),
            code='invalid_maintenance_window'
        )


# ==================== Report Validators ====================

def validate_report_format(value):
    from .constants import REPORT_ALLOWED_FORMATS
    if value not in REPORT_ALLOWED_FORMATS:
        raise ValidationError(
            _('Invalid report format "%(value)s". Allowed: %(allowed)s'),
            params={
                'value': value,
                'allowed': ', '.join(REPORT_ALLOWED_FORMATS)
            },
            code='invalid_report_format'
        )


# ==================== Dashboard Validators ====================

def validate_widget_position(value):
    """Widget position JSON must have x, y, w, h integer keys."""
    required_keys = {'x', 'y', 'w', 'h'}
    if not isinstance(value, dict):
        raise ValidationError(
            _('Widget position must be a JSON object with keys: x, y, w, h.'),
            code='invalid_widget_position'
        )
    missing = required_keys - set(value.keys())
    if missing:
        raise ValidationError(
            _('Widget position is missing keys: %(keys)s'),
            params={'keys': ', '.join(missing)},
            code='missing_position_keys'
        )
    for key in required_keys:
        if not isinstance(value.get(key), int):
            raise ValidationError(
                _('Widget position key "%(key)s" must be an integer.'),
                params={'key': key},
                code='invalid_position_type'
            )


# ==================== Bulk Action Validator ====================

def validate_bulk_action_ids(ids):
    from .constants import BULK_ACTION_MAX_IDS
    if not ids:
        raise ValidationError(
            _('At least one ID is required for a bulk action.'),
            code='empty_bulk_ids'
        )
    if len(ids) > BULK_ACTION_MAX_IDS:
        raise ValidationError(
            _('Too many IDs (%(count)d). Maximum %(max)d allowed.'),
            params={'count': len(ids), 'max': BULK_ACTION_MAX_IDS},
            code='bulk_action_limit_exceeded'
        )


# ==================== Admin Avatar Validator ====================

def validate_admin_avatar(image):
    """Max 2MB, must be JPEG or PNG."""
    max_size_mb = 2
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    if image.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            _('Avatar file size must not exceed %(max)s MB.'),
            params={'max': max_size_mb},
            code='avatar_too_large'
        )
    if hasattr(image, 'content_type') and image.content_type not in allowed_types:
        raise ValidationError(
            _('Avatar must be a JPEG, PNG, or WebP image.'),
            code='invalid_avatar_type'
        )


# ==================== URL Validator ====================

def validate_optional_url(value):
    """Validate URL if provided (allow blank)."""
    if not value:
        return
    from django.core.validators import URLValidator
    validator = URLValidator()
    try:
        validator(value)
    except ValidationError:
        raise ValidationError(
            _('Enter a valid URL.'),
            code='invalid_url'
        )


# ==================== Email Template Validator ====================

def validate_template_variables(value):
    """Validate that template variables JSON is a list of strings."""
    if not isinstance(value, list):
        raise ValidationError(
            _('Template variables must be a JSON array of strings.'),
            code='invalid_template_variables'
        )
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(
                _('Each template variable must be a string.'),
                code='invalid_variable_type'
            )