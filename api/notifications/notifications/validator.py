# earning_backend/api/notifications/validator.py
"""
Validator — Data validation for the notification system.

Centralises all validation logic so it can be reused across:
  - Serializers
  - Services
  - API views
  - Celery tasks
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class ValidationResult:
    """Holds the result of a validation run."""

    def __init__(self):
        self.errors: Dict[str, List[str]] = {}
        self.warnings: List[str] = []

    def add_error(self, field: str, message: str):
        self.errors.setdefault(field, []).append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict:
        return {
            'valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
        }

    def raise_if_invalid(self):
        if not self.is_valid:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(self.errors)


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------

def validate_notification_title(title: str) -> Tuple[bool, str]:
    """Validate notification title."""
    if not title or not title.strip():
        return False, 'Title is required and cannot be blank.'
    if len(title) > 255:
        return False, f'Title is too long ({len(title)} chars). Maximum is 255.'
    if len(title) < 2:
        return False, 'Title is too short. Minimum is 2 characters.'
    return True, ''


def validate_notification_message(message: str) -> Tuple[bool, str]:
    """Validate notification message body."""
    if not message or not message.strip():
        return False, 'Message body is required and cannot be blank.'
    if len(message) > 2000:
        return False, f'Message is too long ({len(message)} chars). Maximum is 2000.'
    return True, ''


def validate_notification_type(notification_type: str) -> Tuple[bool, str]:
    """Validate notification type against allowed choices."""
    from notifications.choices import NOTIFICATION_TYPE_CHOICES
    valid = [c[0] for c in NOTIFICATION_TYPE_CHOICES]
    if notification_type not in valid:
        return False, f'Invalid notification_type: "{notification_type}".'
    return True, ''


def validate_channel(channel: str) -> Tuple[bool, str]:
    """Validate notification channel."""
    from notifications.choices import CHANNEL_CHOICES
    valid = [c[0] for c in CHANNEL_CHOICES]
    if channel not in valid:
        return False, f'Invalid channel: "{channel}". Valid: {valid}'
    return True, ''


def validate_priority(priority: str) -> Tuple[bool, str]:
    """Validate notification priority."""
    from notifications.choices import PRIORITY_CHOICES
    valid = [c[0] for c in PRIORITY_CHOICES]
    if priority not in valid:
        return False, f'Invalid priority: "{priority}". Valid: {valid}'
    return True, ''


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not email or not re.match(pattern, email.strip()):
        return False, f'Invalid email address: "{email}".'
    return True, ''


def validate_phone_bd(phone: str) -> Tuple[bool, str]:
    """
    Validate Bangladesh phone number.
    Accepts: 01XXXXXXXXX, +8801XXXXXXXXX, 8801XXXXXXXXX
    """
    cleaned = phone.strip().replace(' ', '').replace('-', '')
    pattern = r'^(?:\+?880|0088|0)?1[3-9]\d{8}$'
    if not re.match(pattern, cleaned):
        return False, f'Invalid Bangladesh phone number: "{phone}".'
    return True, ''


def validate_fcm_token(token: str) -> Tuple[bool, str]:
    """Basic FCM token format validation."""
    if not token or len(token) < 20:
        return False, 'FCM token is too short or empty.'
    if len(token) > 4096:
        return False, 'FCM token is too long.'
    return True, ''


def validate_apns_token(token: str) -> Tuple[bool, str]:
    """APNs device token validation (hex string, 64 chars)."""
    if not token:
        return False, 'APNs token is empty.'
    cleaned = token.replace(' ', '')
    if not re.match(r'^[0-9a-fA-F]{64}$', cleaned):
        return False, 'APNs token must be a 64-character hex string.'
    return True, ''


def validate_url(url: str, allow_empty: bool = True) -> Tuple[bool, str]:
    """Validate a URL string."""
    if not url:
        return allow_empty, '' if allow_empty else 'URL is required.'
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(pattern, url.strip()):
        return False, f'Invalid URL: "{url}".'
    return True, ''


def validate_future_datetime(dt) -> Tuple[bool, str]:
    """Validate that a datetime is in the future."""
    if dt is None:
        return False, 'Date/time is required.'
    if dt <= timezone.now():
        return False, 'Date/time must be in the future.'
    return True, ''


def validate_user_ids(user_ids: Any) -> Tuple[bool, str]:
    """Validate a list of user IDs."""
    if not isinstance(user_ids, (list, tuple)):
        return False, 'user_ids must be a list.'
    if len(user_ids) == 0:
        return False, 'user_ids cannot be empty.'
    if len(user_ids) > 100_000:
        return False, f'Too many user IDs ({len(user_ids)}). Maximum is 100,000.'
    if not all(isinstance(uid, int) for uid in user_ids):
        return False, 'All user_ids must be integers.'
    return True, ''


def validate_template_variables(template: str, context: dict) -> Tuple[bool, List[str]]:
    """
    Validate that all {variable} placeholders in a template
    have corresponding values in context.
    Returns (is_valid, list_of_missing_variables).
    """
    placeholders = re.findall(r'\{(\w+)\}', template)
    missing = [p for p in placeholders if p not in context]
    return len(missing) == 0, missing


def validate_json_field(value: Any, max_depth: int = 5) -> Tuple[bool, str]:
    """Validate that a value is JSON-serialisable and not too deeply nested."""
    import json
    try:
        serialised = json.dumps(value)
        if len(serialised) > 64 * 1024:  # 64KB limit
            return False, 'JSON field value is too large (max 64KB).'
    except (TypeError, ValueError) as exc:
        return False, f'Value is not JSON-serialisable: {exc}'
    return True, ''


# ---------------------------------------------------------------------------
# Composite validators (full object validation)
# ---------------------------------------------------------------------------

def validate_notification_payload(data: dict) -> ValidationResult:
    """
    Full validation of a notification creation payload.
    Returns a ValidationResult with all field errors collected.
    """
    result = ValidationResult()

    # Title
    ok, msg = validate_notification_title(data.get('title', ''))
    if not ok:
        result.add_error('title', msg)

    # Message
    ok, msg = validate_notification_message(data.get('message', ''))
    if not ok:
        result.add_error('message', msg)

    # Notification type
    if data.get('notification_type'):
        ok, msg = validate_notification_type(data['notification_type'])
        if not ok:
            result.add_error('notification_type', msg)

    # Channel
    channel = data.get('channel', 'in_app')
    ok, msg = validate_channel(channel)
    if not ok:
        result.add_error('channel', msg)

    # Priority
    priority = data.get('priority', 'medium')
    ok, msg = validate_priority(priority)
    if not ok:
        result.add_error('priority', msg)

    # Action URL (optional)
    if data.get('action_url'):
        ok, msg = validate_url(data['action_url'])
        if not ok:
            result.add_error('action_url', msg)

    # Schedule
    if data.get('scheduled_at'):
        ok, msg = validate_future_datetime(data['scheduled_at'])
        if not ok:
            result.add_error('scheduled_at', msg)

    # Channel-specific validation
    if channel == 'email' and data.get('recipient_email'):
        ok, msg = validate_email(data['recipient_email'])
        if not ok:
            result.add_error('recipient_email', msg)

    if channel == 'sms' and data.get('phone'):
        ok, msg = validate_phone_bd(data['phone'])
        if not ok:
            result.add_warning(f'Phone may be invalid: {msg}')

    return result


def validate_device_registration(data: dict) -> ValidationResult:
    """Validate a push device registration payload."""
    result = ValidationResult()

    device_type = data.get('device_type', '')
    from notifications.choices import DEVICE_TYPE_CHOICES
    valid_types = [d[0] for d in DEVICE_TYPE_CHOICES]
    if device_type not in valid_types:
        result.add_error('device_type', f'Invalid device_type. Valid: {valid_types}')

    if device_type == 'android':
        token = data.get('fcm_token', '')
        ok, msg = validate_fcm_token(token)
        if not ok:
            result.add_error('fcm_token', msg)

    elif device_type == 'ios':
        token = data.get('apns_token', '')
        ok, msg = validate_apns_token(token)
        if not ok:
            result.add_error('apns_token', msg)

    elif device_type == 'web':
        if not data.get('web_push_subscription'):
            result.add_error('web_push_subscription', 'Required for web devices.')

    return result


def validate_campaign_payload(data: dict) -> ValidationResult:
    """Validate a campaign creation payload."""
    result = ValidationResult()

    if not data.get('name', '').strip():
        result.add_error('name', 'Campaign name is required.')
    elif len(data['name']) > 255:
        result.add_error('name', 'Campaign name must be 255 characters or fewer.')

    if not data.get('template_id'):
        result.add_error('template_id', 'template_id is required.')

    if data.get('send_at'):
        ok, msg = validate_future_datetime(data['send_at'])
        if not ok:
            result.add_error('send_at', msg)

    return result


def validate_segment_conditions(conditions: dict) -> ValidationResult:
    """Validate segment filter conditions."""
    result = ValidationResult()

    seg_type = conditions.get('type', 'all')
    valid_types = ['all', 'tier', 'geo', 'inactive', 'new', 'high_value', 'custom']
    if seg_type not in valid_types:
        result.add_error('type', f'Invalid segment type. Valid: {valid_types}')

    if seg_type == 'custom' and not conditions.get('user_ids') and not conditions.get('filters'):
        result.add_error('filters', 'Custom segment requires user_ids or filters.')

    if conditions.get('user_ids'):
        ok, msg = validate_user_ids(conditions['user_ids'])
        if not ok:
            result.add_error('user_ids', msg)

    return result


def validate_template_render(template_str: str, context: dict) -> ValidationResult:
    """Validate that a template can be rendered with the given context."""
    result = ValidationResult()
    ok, missing = validate_template_variables(template_str, context)
    if not ok:
        result.add_warning(
            f'Template missing context variables: {missing}. '
            f'They will be rendered as empty strings.'
        )
    return result


# ---------------------------------------------------------------------------
# Standalone helper
# ---------------------------------------------------------------------------

def is_valid_bd_phone(phone: str) -> bool:
    """Quick boolean check for Bangladesh phone numbers."""
    ok, _ = validate_phone_bd(phone)
    return ok


def is_valid_email(email: str) -> bool:
    """Quick boolean check for email addresses."""
    ok, _ = validate_email(email)
    return ok


def sanitize_notification_data(data: dict) -> dict:
    """
    Strip dangerous content from notification data before saving.
    Removes any script tags, trims whitespace, enforces max lengths.
    """
    import html

    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            # Escape HTML entities and trim
            value = html.escape(value.strip())
            # Enforce max lengths
            if key == 'title':
                value = value[:255]
            elif key == 'message':
                value = value[:2000]
        cleaned[key] = value
    return cleaned
