import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .constants import (
    SLUG_MIN_LENGTH, SLUG_MAX_LENGTH, SLUG_ALLOWED_CHARS,
    SLUG_RESERVED_WORDS, MAX_SUB_PARAMS,
)


def validate_slug_format(value):
    """Validate smartlink slug: alphanumeric + hyphens, no reserved words."""
    if not value:
        raise ValidationError(_('Slug cannot be empty.'))

    if len(value) < SLUG_MIN_LENGTH:
        raise ValidationError(
            _(f'Slug must be at least {SLUG_MIN_LENGTH} characters long.')
        )

    if len(value) > SLUG_MAX_LENGTH:
        raise ValidationError(
            _(f'Slug cannot exceed {SLUG_MAX_LENGTH} characters.')
        )

    pattern = re.compile(r'^[a-z0-9][a-z0-9\-_]*[a-z0-9]$')
    if not pattern.match(value):
        raise ValidationError(
            _('Slug can only contain lowercase letters, digits, hyphens, and underscores. '
              'Must start and end with alphanumeric.')
        )

    if value.lower() in SLUG_RESERVED_WORDS:
        raise ValidationError(
            _(f'"{value}" is a reserved word and cannot be used as a slug.')
        )


def validate_weight(value):
    """Validate rotation weight 1-1000."""
    if not (1 <= value <= 1000):
        raise ValidationError(_('Weight must be between 1 and 1000.'))


def validate_ab_test_weights(variants):
    """Ensure A/B test variant weights sum to 100."""
    total = sum(v.get('weight', 0) for v in variants)
    if total != 100:
        raise ValidationError(
            _(f'A/B test variant weights must sum to 100. Current sum: {total}.')
        )


def validate_sub_id_value(value):
    """Validate sub1-sub5 values: alphanumeric, hyphen, underscore only."""
    if value and not re.match(r'^[a-zA-Z0-9_\-]{1,255}$', value):
        raise ValidationError(
            _('Sub ID values can only contain letters, digits, hyphens, and underscores.')
        )


def validate_cap_value(value):
    """Cap must be positive integer or None."""
    if value is not None and value < 0:
        raise ValidationError(_('Cap value must be a positive integer.'))


def validate_fraud_score(value):
    """Fraud score must be 0-100."""
    if not (0 <= value <= 100):
        raise ValidationError(_('Fraud score must be between 0 and 100.'))


def validate_offer_pool_not_empty(pool):
    """Offer pool must have at least one active entry."""
    if not pool.entries.filter(is_active=True).exists():
        raise ValidationError(_('Offer pool must have at least one active entry.'))


def validate_custom_domain(value):
    """Basic domain format validation."""
    pattern = re.compile(
        r'^(?:[a-zA-Z0-9]'
        r'(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)'
        r'+[a-zA-Z]{2,}$'
    )
    if not pattern.match(value):
        raise ValidationError(
            _(f'"{value}" is not a valid domain name.')
        )


def validate_redirect_url(value):
    """Redirect URL must be http or https."""
    if not value.startswith(('http://', 'https://')):
        raise ValidationError(
            _('Redirect URL must start with http:// or https://')
        )
    if len(value) > 2048:
        raise ValidationError(_('Redirect URL cannot exceed 2048 characters.'))


def validate_time_range(start_hour, end_hour):
    """Time targeting: start must be before end, 0-23."""
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        raise ValidationError(_('Hours must be between 0 and 23.'))
    if start_hour >= end_hour:
        raise ValidationError(_('Start hour must be less than end hour.'))
